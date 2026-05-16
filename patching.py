"""Patch planning and materialization for j3."""

from __future__ import annotations

import ast
import difflib
import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from actions import PatchAction, PatchActionKind, PatchTarget
from features import embed_python_source, vector_delta
from repo import DEFAULT_EXCLUDE_DIRS, iter_python_sources
from synth import SourceEdit, apply_edit


DEFAULT_PATCH_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class CandidatePatch:
    file_path: str
    action: PatchAction
    edit: SourceEdit
    original_source: str
    patched_source: str
    reason: str
    model_score: float | None = None

    def diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.original_source.splitlines(keepends=True),
                self.patched_source.splitlines(keepends=True),
                fromfile=f"a/{self.file_path}",
                tofile=f"b/{self.file_path}",
            )
        )


@dataclass(frozen=True, slots=True)
class PatchPlanResult:
    repo: Path
    test_command: str
    baseline_exit_code: int
    candidates_generated: int
    candidates_tested: int
    selected: CandidatePatch | None
    applied: bool
    test_output: str
    model_path: Path | None = None


@dataclass(frozen=True, slots=True)
class PatchRankingModel:
    """Prototype latent action model used to rank structured patch candidates."""

    path: Path
    embedding_dim: int
    action_delta_prototypes: dict[str, list[float]]

    @classmethod
    def load(cls, path: Path) -> "PatchRankingModel":
        resolved = path.expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if payload.get("format") != "j3.prototype-jepa.v1":
            raise ValueError(f"unsupported model format in {resolved}")
        embedding_dim = int(payload["embedding_dim"])
        prototypes = {
            str(action): [float(value) for value in vector]
            for action, vector in payload.get("action_delta_prototypes", {}).items()
        }
        return cls(
            path=resolved,
            embedding_dim=embedding_dim,
            action_delta_prototypes=prototypes,
        )

    def score(self, candidate: CandidatePatch) -> float:
        prototype = self.action_delta_prototypes.get(candidate.action.kind.value)
        if prototype is None:
            return -1.0

        before = embed_python_source(candidate.original_source, dim=self.embedding_dim)
        after = embed_python_source(candidate.patched_source, dim=self.embedding_dim)
        delta = vector_delta(after, before)
        return _cosine_similarity(delta, prototype)


def plan_and_maybe_apply_patch(
    *,
    repo: Path,
    test_command: str,
    dry_run: bool,
    timeout_seconds: int = DEFAULT_PATCH_TIMEOUT_SECONDS,
    max_candidates: int = 80,
    model_path: Path | None = None,
) -> PatchPlanResult:
    """Find the first candidate patch that makes the requested test pass."""

    root = repo.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repo is not a directory: {root}")

    baseline = _run_test(root, test_command, timeout_seconds)
    if baseline.returncode == 0:
        return PatchPlanResult(
            repo=root,
            test_command=test_command,
            baseline_exit_code=0,
            candidates_generated=0,
            candidates_tested=0,
            selected=None,
            applied=False,
            test_output=_combined_output(baseline),
            model_path=None,
        )

    candidates = generate_candidate_patches(root)
    model = _load_model_if_available(model_path)
    if model is not None:
        candidates = rank_candidate_patches(candidates, model)
    candidates_tested = 0
    for candidate in candidates[:max_candidates]:
        candidates_tested += 1
        with tempfile.TemporaryDirectory(prefix="j3-patch-") as tmp:
            tmp_repo = Path(tmp) / root.name
            _copy_repo(root, tmp_repo)
            _write_candidate(tmp_repo, candidate)
            attempt = _run_test(tmp_repo, test_command, timeout_seconds)
            if attempt.returncode == 0:
                if not dry_run:
                    _write_candidate(root, candidate)
                return PatchPlanResult(
                    repo=root,
                    test_command=test_command,
                    baseline_exit_code=baseline.returncode,
                    candidates_generated=len(candidates),
                    candidates_tested=candidates_tested,
                    selected=candidate,
                    applied=not dry_run,
                    test_output=_combined_output(attempt),
                    model_path=model.path if model else None,
                )

    return PatchPlanResult(
        repo=root,
        test_command=test_command,
        baseline_exit_code=baseline.returncode,
        candidates_generated=len(candidates),
        candidates_tested=candidates_tested,
        selected=None,
        applied=False,
        test_output=_combined_output(baseline),
        model_path=model.path if model else None,
    )


def rank_candidate_patches(
    candidates: list[CandidatePatch],
    model: PatchRankingModel,
) -> list[CandidatePatch]:
    """Sort candidates by learned latent delta similarity."""

    scored = [
        CandidatePatch(
            file_path=candidate.file_path,
            action=candidate.action,
            edit=candidate.edit,
            original_source=candidate.original_source,
            patched_source=candidate.patched_source,
            reason=candidate.reason,
            model_score=model.score(candidate),
        )
        for candidate in candidates
    ]
    return sorted(scored, key=lambda candidate: candidate.model_score or -1.0, reverse=True)


def generate_candidate_patches(repo: Path) -> list[CandidatePatch]:
    """Generate structured candidate edits for source files in a repo."""

    candidates: list[CandidatePatch] = []
    for source in iter_python_sources(repo):
        path = Path(source.relative_path)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(source.text)
        except SyntaxError:
            continue

        for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
            arg_names = {arg.arg for arg in function.args.args}
            candidates.extend(_guard_candidates(source.relative_path, source.text, function, arg_names))
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    candidates.extend(_return_candidates(source.relative_path, source.text, node, arg_names))
                elif isinstance(node, ast.Compare):
                    candidates.extend(_compare_candidates(source.relative_path, source.text, node))
                elif isinstance(node, ast.Constant):
                    candidates.extend(_literal_candidates(source.relative_path, source.text, node))
    return candidates


def _guard_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    arg_names: set[str],
) -> list[CandidatePatch]:
    if not function.body:
        return []

    candidates: list[CandidatePatch] = []
    for arg_name in sorted(arg_names):
        if not _function_uses_len_of(function, arg_name):
            continue
        first_statement = function.body[0]
        indent = " " * first_statement.col_offset
        guard = f"if not {arg_name}:\n{indent}    return 0\n{indent}"
        edit = SourceEdit(
            start_line=first_statement.lineno,
            start_col=first_statement.col_offset,
            end_line=first_statement.lineno,
            end_col=first_statement.col_offset,
            replacement=guard,
        )
        patched = apply_edit(source, edit)
        action = PatchAction(
            kind=PatchActionKind.INSERT_GUARD,
            target=PatchTarget(
                file_path=file_path,
                start_line=first_statement.lineno,
                end_line=first_statement.lineno,
                symbol=function.name,
                node_kind=type(first_statement).__name__,
            ),
            params={"condition": f"not {arg_name}", "return": 0},
        )
        candidates.append(
            CandidatePatch(
                file_path=file_path,
                action=action,
                edit=edit,
                original_source=source,
                patched_source=patched,
                reason=f"insert empty-sequence guard for {arg_name}",
            )
        )
    return candidates


def _return_candidates(
    file_path: str,
    source: str,
    node: ast.Return,
    arg_names: set[str],
) -> list[CandidatePatch]:
    expr = ast.get_source_segment(source, node.value)
    if not expr:
        return []

    candidates: list[CandidatePatch] = []
    if {"price", "percent"}.issubset(arg_names) and "percent" in expr and "100" in expr:
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node.value,
                kind=PatchActionKind.REPLACE_EXPR,
                replacement="price * (1 - percent / 100)",
                reason="discount formula candidate",
            )
        )

    if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mult):
        left = ast.get_source_segment(source, node.value.left)
        right = ast.get_source_segment(source, node.value.right)
        if left and right:
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=node.value,
                    kind=PatchActionKind.REPLACE_EXPR,
                    replacement=f"{left} - ({left} * {right})",
                    reason="convert multiplier into subtraction from base value",
                )
            )

    if isinstance(node.value, ast.Subscript):
        subscript_candidate = _last_item_candidate(file_path, source, node.value)
        if subscript_candidate is not None:
            candidates.append(subscript_candidate)

    return candidates


def _last_item_candidate(file_path: str, source: str, node: ast.Subscript) -> CandidatePatch | None:
    if not isinstance(node.slice, ast.Constant) or node.slice.value != 0:
        return None

    collection = ast.get_source_segment(source, node.value)
    if not collection:
        return None
    return _candidate(
        file_path=file_path,
        source=source,
        node=node,
        kind=PatchActionKind.REPLACE_EXPR,
        replacement=f"{collection}[-1]",
        reason="replace first item access with last item access",
    )


def _literal_candidates(file_path: str, source: str, node: ast.Constant) -> list[CandidatePatch]:
    if isinstance(node.value, bool) or not isinstance(node.value, int | float):
        return []

    candidates: list[CandidatePatch] = []
    for replacement in _nearby_literals(node.value):
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node,
                kind=PatchActionKind.CHANGE_LITERAL,
                replacement=repr(replacement),
                reason=f"try nearby literal {replacement!r}",
                params={"from": node.value, "to": replacement},
            )
        )
    return candidates


def _compare_candidates(file_path: str, source: str, node: ast.Compare) -> list[CandidatePatch]:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return []

    original = _operator_text(node.ops[0])
    alternatives = _operator_alternatives(original)
    if not alternatives:
        return []

    left = ast.get_source_segment(source, node.left)
    right = ast.get_source_segment(source, node.comparators[0])
    if not left or not right:
        return []

    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.CHANGE_OPERATOR,
            replacement=f"{left} {operator} {right}",
            reason=f"try comparison operator {operator}",
            params={"from": original, "to": operator},
        )
        for operator in alternatives
    ]


def _candidate(
    *,
    file_path: str,
    source: str,
    node: ast.AST,
    kind: PatchActionKind,
    replacement: str,
    reason: str,
    params: dict[str, object] | None = None,
) -> CandidatePatch:
    edit = _node_edit(node, replacement)
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=kind,
        target=PatchTarget(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            node_kind=type(node).__name__,
        ),
        params=params or {"replacement": replacement},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=reason,
    )


def _node_edit(node: ast.AST, replacement: str) -> SourceEdit:
    return SourceEdit(
        start_line=node.lineno,
        start_col=node.col_offset,
        end_line=node.end_lineno,
        end_col=node.end_col_offset,
        replacement=replacement,
    )


def _write_candidate(repo: Path, candidate: CandidatePatch) -> None:
    path = repo / candidate.file_path
    path.write_text(candidate.patched_source, encoding="utf-8")


def _run_test(repo: Path, command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repo,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _copy_repo(source: Path, destination: Path) -> None:
    def ignore(_: str, names: list[str]) -> set[str]:
        return {name for name in names if name in DEFAULT_EXCLUDE_DIRS or name == "runs"}

    shutil.copytree(source, destination, ignore=ignore)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + result.stderr).strip()


def _load_model_if_available(model_path: Path | None) -> PatchRankingModel | None:
    if model_path is None:
        return None
    resolved = model_path.expanduser().resolve()
    if not resolved.exists():
        return None
    return PatchRankingModel.load(resolved)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _operator_text(op: ast.cmpop) -> str | None:
    table = {
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Is: "is",
        ast.IsNot: "is not",
        ast.In: "in",
        ast.NotIn: "not in",
    }
    return table.get(type(op))


def _operator_alternatives(operator: str | None) -> list[str]:
    table = {
        "==": ["!=", "<=", ">="],
        "!=": ["=="],
        "<": ["<=", ">", ">="],
        "<=": ["<", ">", ">="],
        ">": [">=", "<", "<="],
        ">=": [">", "<", "<="],
        "is": ["is not"],
        "is not": ["is"],
        "in": ["not in"],
        "not in": ["in"],
    }
    if operator is None:
        return []
    return table.get(operator, [])


def _nearby_literals(value: int | float) -> list[int | float]:
    if isinstance(value, int):
        return [value - 2, value - 1, value + 1, value + 2]
    return [round(value - 0.1, 10), round(value + 0.1, 10)]


def _function_uses_len_of(function: ast.FunctionDef, arg_name: str) -> bool:
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "len"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == arg_name
        ):
            return True
    return False
