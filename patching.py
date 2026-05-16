"""Patch planning and materialization for j3."""

from __future__ import annotations

import ast
import builtins
import difflib
import io
import json
import math
import shutil
import subprocess
import tempfile
import time
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from actions import PatchAction, PatchActionKind, PatchTarget
from candidate_ranking import CandidateRankerModel
from failure_hints import PytestFailureHint, parse_pytest_failure_hints
from features import embed_python_source, vector_delta
from repo import DEFAULT_EXCLUDE_DIRS, iter_python_sources
from synth import SourceEdit, apply_edit


DEFAULT_PATCH_TIMEOUT_SECONDS = 30
COMMON_IMPORTS = {
    "Counter": "from collections import Counter",
    "defaultdict": "from collections import defaultdict",
    "datetime": "from datetime import datetime",
    "Path": "from pathlib import Path",
}
BUILTIN_NAMES = set(dir(builtins))


@dataclass(frozen=True, slots=True)
class CandidatePatch:
    file_path: str
    action: PatchAction
    edit: SourceEdit
    original_source: str
    patched_source: str
    reason: str
    model_score: float | None = None
    failure_hint_score: float = 0.0
    ranker_score: float | None = None

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
    ranker_path: Path | None = None
    tested_candidates: tuple[CandidatePatch, ...] = ()
    failure_hints: tuple[PytestFailureHint, ...] = ()


@dataclass(frozen=True, slots=True)
class PatchRankingModel:
    """Prototype latent action model used to rank structured patch candidates."""

    path: Path
    embedding_dim: int
    action_delta_prototypes: dict[str, list[float]]
    action_delta_exemplars: dict[str, list[list[float]]]

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
        exemplars = {
            str(action): [
                [float(value) for value in vector]
                for vector in vectors
                if len(vector) == embedding_dim
            ]
            for action, vectors in payload.get("action_delta_exemplars", {}).items()
        }
        return cls(
            path=resolved,
            embedding_dim=embedding_dim,
            action_delta_prototypes=prototypes,
            action_delta_exemplars=exemplars,
        )

    def score(self, candidate: CandidatePatch) -> float:
        before = embed_python_source(candidate.original_source, dim=self.embedding_dim)
        after = embed_python_source(candidate.patched_source, dim=self.embedding_dim)
        delta = vector_delta(after, before)
        scores: list[tuple[float, float]] = []

        prototype = self.action_delta_prototypes.get(candidate.action.kind.value)
        if prototype is not None:
            scores.append((_cosine_similarity(delta, prototype), 0.50))

        action_exemplars = self.action_delta_exemplars.get(candidate.action.kind.value, [])
        action_score = _nearest_exemplar_similarity(delta, action_exemplars)
        if action_score is not None:
            scores.append((action_score, 0.30))

        git_score = _nearest_exemplar_similarity(delta, self.action_delta_exemplars.get("git_transition", []))
        if git_score is not None:
            scores.append((git_score, 0.20))

        if not scores:
            return -1.0

        total_weight = sum(weight for _, weight in scores)
        return sum(score * weight for score, weight in scores) / total_weight


def plan_and_maybe_apply_patch(
    *,
    repo: Path,
    test_command: str,
    dry_run: bool,
    timeout_seconds: int = DEFAULT_PATCH_TIMEOUT_SECONDS,
    max_candidates: int = 80,
    model_path: Path | None = None,
    ranker_path: Path | None = None,
    use_failure_hints: bool = True,
    progress: Callable[[str], None] | None = None,
) -> PatchPlanResult:
    """Find the first candidate patch that makes the requested test pass."""

    root = repo.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repo is not a directory: {root}")

    _emit_progress(progress, f"baseline: running `{test_command}`")
    started = time.perf_counter()
    baseline = _run_test(root, test_command, timeout_seconds)
    _emit_progress(
        progress,
        f"baseline: exit={baseline.returncode} elapsed={time.perf_counter() - started:.2f}s",
    )
    baseline_output = _combined_output(baseline)
    if baseline.returncode == 0:
        return PatchPlanResult(
            repo=root,
            test_command=test_command,
            baseline_exit_code=0,
            candidates_generated=0,
            candidates_tested=0,
            selected=None,
            applied=False,
            test_output=baseline_output,
            model_path=None,
            ranker_path=None,
        )

    _emit_progress(progress, "candidates: generating structured patches")
    started = time.perf_counter()
    candidates = generate_candidate_patches(root)
    _emit_progress(
        progress,
        f"candidates: generated={len(candidates)} elapsed={time.perf_counter() - started:.2f}s",
    )
    model = _load_model_if_available(model_path)
    if model is not None:
        _emit_progress(progress, f"rank: scoring with model {model.path}")
        candidates = rank_candidate_patches(candidates, model)
    baseline_hints = parse_pytest_failure_hints(baseline_output)
    hints = baseline_hints if use_failure_hints else []
    ranker = _load_candidate_ranker_if_available(ranker_path)
    if hints:
        _emit_progress(progress, f"hints: parsed={len(hints)}; prioritizing candidates")
        candidates = prioritize_candidate_patches(candidates, hints, ranker=ranker)
    elif ranker is not None:
        _emit_progress(progress, f"rank: scoring with candidate ranker {ranker.path}")
        candidates = rank_with_candidate_ranker(candidates, ranker, hints=[])
    candidates_tested = 0
    tested_candidates: list[CandidatePatch] = []
    for candidate in candidates[:max_candidates]:
        candidates_tested += 1
        _emit_progress(
            progress,
            "test: "
            f"candidate={candidates_tested}/{min(max_candidates, len(candidates))} "
            f"action={candidate.action.kind.value} "
            f"symbol={candidate.action.target.symbol or '-'} "
            f"reason={candidate.reason}",
        )
        with tempfile.TemporaryDirectory(prefix="j3-patch-") as tmp:
            tmp_repo = Path(tmp) / root.name
            _copy_repo(root, tmp_repo)
            _write_candidate(tmp_repo, candidate)
            started = time.perf_counter()
            attempt = _run_test(tmp_repo, test_command, timeout_seconds)
            elapsed = time.perf_counter() - started
            tested_candidates.append(candidate)
            _emit_progress(
                progress,
                f"test: candidate={candidates_tested} exit={attempt.returncode} elapsed={elapsed:.2f}s",
            )
            if attempt.returncode == 0:
                _emit_progress(progress, f"selected: candidate={candidates_tested} passed")
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
                    ranker_path=ranker.path if ranker else None,
                    tested_candidates=tuple(tested_candidates),
                    failure_hints=tuple(baseline_hints),
                )

    _emit_progress(progress, f"status: no passing candidate within tested={candidates_tested}")
    return PatchPlanResult(
        repo=root,
        test_command=test_command,
        baseline_exit_code=baseline.returncode,
        candidates_generated=len(candidates),
        candidates_tested=candidates_tested,
        selected=None,
        applied=False,
        test_output=baseline_output,
        model_path=model.path if model else None,
        ranker_path=ranker.path if ranker else None,
        tested_candidates=tuple(tested_candidates),
        failure_hints=tuple(baseline_hints),
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
            failure_hint_score=candidate.failure_hint_score,
            ranker_score=candidate.ranker_score,
        )
        for candidate in candidates
    ]
    return sorted(scored, key=lambda candidate: candidate.model_score or -1.0, reverse=True)


def prioritize_candidate_patches(
    candidates: list[CandidatePatch],
    hints: list[PytestFailureHint],
    ranker: CandidateRankerModel | None = None,
) -> list[CandidatePatch]:
    """Sort candidates by structured evidence from the failing test output."""

    scored = [
        CandidatePatch(
            file_path=candidate.file_path,
            action=candidate.action,
            edit=candidate.edit,
            original_source=candidate.original_source,
            patched_source=candidate.patched_source,
            reason=candidate.reason,
            model_score=candidate.model_score,
            failure_hint_score=_failure_hint_score(candidate, hints),
            ranker_score=ranker.score(candidate, hints) if ranker is not None else candidate.ranker_score,
        )
        for candidate in candidates
    ]
    return sorted(
        scored,
        key=lambda candidate: (
            candidate.failure_hint_score,
            candidate.ranker_score if candidate.ranker_score is not None else 0.0,
            candidate.model_score if candidate.model_score is not None else 0.0,
        ),
        reverse=True,
    )


def rank_with_candidate_ranker(
    candidates: list[CandidatePatch],
    ranker: CandidateRankerModel,
    *,
    hints: list[PytestFailureHint],
) -> list[CandidatePatch]:
    scored = [
        CandidatePatch(
            file_path=candidate.file_path,
            action=candidate.action,
            edit=candidate.edit,
            original_source=candidate.original_source,
            patched_source=candidate.patched_source,
            reason=candidate.reason,
            model_score=candidate.model_score,
            failure_hint_score=candidate.failure_hint_score,
            ranker_score=ranker.score(candidate, hints),
        )
        for candidate in candidates
    ]
    return sorted(
        scored,
        key=lambda candidate: (
            candidate.ranker_score if candidate.ranker_score is not None else 0.0,
            candidate.model_score if candidate.model_score is not None else 0.0,
        ),
        reverse=True,
    )


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

        class_fields = _class_fields(tree)
        module_symbols = _module_symbols(tree)
        candidates.extend(_add_import_candidates(source.relative_path, source.text, tree))
        candidates.extend(_signature_propagation_candidates(source.relative_path, source.text, tree))
        for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
            arg_names = {arg.arg for arg in function.args.args}
            arg_types = _function_arg_types(function)
            local_symbols = module_symbols | _local_symbols(function)
            candidates.extend(_guard_candidates(source.relative_path, source.text, function, arg_names))
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    candidates.extend(
                        _return_candidates(source.relative_path, source.text, function, node, arg_names)
                    )
                    candidates.extend(_wrap_try_except_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Compare):
                    candidates.extend(_compare_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Constant):
                    candidates.extend(_literal_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.If):
                    candidates.extend(_modify_condition_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    candidates.extend(
                        _rename_symbol_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            local_symbols,
                        )
                    )
                elif isinstance(node, ast.Call):
                    candidates.extend(_swap_call_arg_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Attribute):
                    candidates.extend(
                        _attribute_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            arg_types,
                            class_fields,
                        )
                    )
    return candidates


def _add_import_candidates(file_path: str, source: str, tree: ast.Module) -> list[CandidatePatch]:
    imported_names = _imported_names(tree)
    defined_names = _defined_names(tree)
    used_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    candidates: list[CandidatePatch] = []
    for name, import_line in COMMON_IMPORTS.items():
        if name in imported_names or name in defined_names or name not in used_names:
            continue
        insert_line = _import_insert_line(tree)
        edit = SourceEdit(
            start_line=insert_line,
            start_col=0,
            end_line=insert_line,
            end_col=0,
            replacement=f"{import_line}\n",
        )
        patched = apply_edit(source, edit)
        action = PatchAction(
            kind=PatchActionKind.ADD_IMPORT,
            target=PatchTarget(
                file_path=file_path,
                start_line=insert_line,
                end_line=insert_line,
                symbol=name,
                node_kind="Import",
            ),
            params={"name": name, "module": _import_module(import_line), "import": import_line},
        )
        candidates.append(
            CandidatePatch(
                file_path=file_path,
                action=action,
                edit=edit,
                original_source=source,
                patched_source=patched,
                reason=f"add missing import for {name}",
            )
        )
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
    function: ast.FunctionDef,
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
                symbol=function.name,
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
                    symbol=function.name,
                )
            )

    if isinstance(node.value, ast.Subscript):
        subscript_candidate = _last_item_candidate(file_path, source, function, node.value)
        if subscript_candidate is not None:
            candidates.append(subscript_candidate)

    return candidates


def _wrap_try_except_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Return,
) -> list[CandidatePatch]:
    value = ast.get_source_segment(source, node.value) if node.value is not None else None
    if value is None or not isinstance(node.value, ast.Call):
        return []

    exception = _call_exception(node.value)
    if exception is None:
        return []

    inner_indent = " " * (node.col_offset + 4)
    outer_indent = " " * node.col_offset
    replacement = f"try:\n{inner_indent}return {value}\n{outer_indent}except {exception}:\n{inner_indent}return 0"
    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.WRAP_TRY_EXCEPT,
            replacement=replacement,
            reason=f"wrap return in {exception} handler",
            params={"exception": exception, "return": 0},
            symbol=function.name,
        )
    ]


def _swap_call_arg_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Call,
) -> list[CandidatePatch]:
    if len(node.args) < 2:
        return []
    func = ast.get_source_segment(source, node.func)
    args = [ast.get_source_segment(source, arg) for arg in node.args]
    if not func or any(arg is None for arg in args):
        return []

    keyword_parts: list[str] = []
    for keyword in node.keywords:
        value = ast.get_source_segment(source, keyword.value)
        if value is None:
            return []
        if keyword.arg is None:
            keyword_parts.append(f"**{value}")
        else:
            keyword_parts.append(f"{keyword.arg}={value}")

    candidates: list[CandidatePatch] = []
    for left in range(len(args) - 1):
        right = left + 1
        swapped = list(args)
        swapped[left], swapped[right] = swapped[right], swapped[left]
        call_args = [arg for arg in swapped if arg is not None] + keyword_parts
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node,
                kind=PatchActionKind.SWAP_CALL_ARG,
                replacement=f"{func}({', '.join(call_args)})",
                reason=f"swap call arguments {left} and {right}",
                params={"left": left, "right": right},
                symbol=function.name,
            )
        )
    return candidates


def _attribute_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Attribute,
    arg_types: dict[str, str],
    class_fields: dict[str, set[str]],
) -> list[CandidatePatch]:
    if not isinstance(node.value, ast.Name):
        return []

    class_name = arg_types.get(node.value.id)
    if class_name is None:
        return []

    fields = class_fields.get(class_name, set())
    alternatives = sorted(field for field in fields if field != node.attr)
    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.CHANGE_ATTRIBUTE,
            replacement=f"{node.value.id}.{field}",
            reason=f"try attribute {field}",
            params={"from": node.attr, "to": field},
            symbol=function.name,
        )
        for field in alternatives
    ]


def _last_item_candidate(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Subscript,
) -> CandidatePatch | None:
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
        symbol=function.name,
    )


def _literal_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Constant,
) -> list[CandidatePatch]:
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
                symbol=function.name,
            )
        )
    return candidates


def _compare_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Compare,
) -> list[CandidatePatch]:
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
            symbol=function.name,
        )
        for operator in alternatives
    ]


def _modify_condition_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.If,
) -> list[CandidatePatch]:
    condition = ast.get_source_segment(source, node.test)
    if not condition:
        return []

    candidates: list[CandidatePatch] = []
    if isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not):
        operand = ast.get_source_segment(source, node.test.operand)
        if operand:
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=node.test,
                    kind=PatchActionKind.MODIFY_CONDITION,
                    replacement=operand,
                    reason="remove condition negation",
                    params={"operation": "remove_not", "from": condition, "to": operand},
                    symbol=function.name,
                )
            )
    else:
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node.test,
                kind=PatchActionKind.MODIFY_CONDITION,
                replacement=f"not ({condition})",
                reason="negate condition",
                params={"operation": "add_not", "from": condition, "to": f"not ({condition})"},
                symbol=function.name,
            )
        )

    if isinstance(node.test, ast.BoolOp):
        for index, value in enumerate(node.test.values):
            replacement = ast.get_source_segment(source, value)
            if not replacement or replacement == condition:
                continue
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=node.test,
                    kind=PatchActionKind.MODIFY_CONDITION,
                    replacement=replacement,
                    reason=f"simplify condition to branch {index}",
                    params={"operation": "simplify_boolop", "branch": index, "from": condition, "to": replacement},
                    symbol=function.name,
                )
            )

    return candidates


def _rename_symbol_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Name,
    local_symbols: set[str],
) -> list[CandidatePatch]:
    if node.id in local_symbols or node.id in BUILTIN_NAMES:
        return []

    alternatives = difflib.get_close_matches(node.id, sorted(local_symbols), n=3, cutoff=0.72)
    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.RENAME_SYMBOL,
            replacement=alternative,
            reason=f"rename unknown symbol {node.id} to {alternative}",
            params={"from": node.id, "to": alternative},
            symbol=function.name,
        )
        for alternative in alternatives
    ]


def _signature_propagation_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
) -> list[CandidatePatch]:
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    if not functions:
        return []

    calls_by_name: dict[str, list[ast.Call]] = {name: [] for name in functions}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
            calls_by_name[node.func.id].append(node)

    candidates: list[CandidatePatch] = []
    for function_name, function in functions.items():
        params = [arg.arg for arg in function.args.args]
        if not params:
            continue

        calls = calls_by_name[function_name]
        for call in calls:
            for keyword in [keyword for keyword in call.keywords if keyword.arg]:
                if keyword.arg in params:
                    continue

                close_params = difflib.get_close_matches(keyword.arg, params, n=2, cutoff=0.65)
                for parameter in close_params:
                    replacement = _render_call_with_keyword_rename(source, call, keyword.arg, parameter)
                    if replacement:
                        candidates.append(
                            _candidate(
                                file_path=file_path,
                                source=source,
                                node=call,
                                kind=PatchActionKind.RENAME_SYMBOL,
                                replacement=replacement,
                                reason=f"rename call keyword {keyword.arg} to {parameter}",
                                params={"from": keyword.arg, "to": parameter, "scope": "call_site"},
                                symbol=function_name,
                            )
                        )

                candidate = _signature_candidate_from_keyword(
                    file_path=file_path,
                    source=source,
                    function=function,
                    calls=calls,
                    keyword_name=keyword.arg,
                    params=params,
                )
                if candidate is not None:
                    candidates.append(candidate)

    return candidates


def _signature_candidate_from_keyword(
    *,
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    calls: list[ast.Call],
    keyword_name: str,
    params: list[str],
) -> CandidatePatch | None:
    keyword_names = {
        keyword.arg
        for call in calls
        for keyword in call.keywords
        if keyword.arg
    }
    rename_from = [param for param in params if param not in keyword_names]
    if len(rename_from) != 1 or keyword_name in params:
        return None

    old_name = rename_from[0]
    function_segment = ast.get_source_segment(source, function)
    if function_segment is None:
        return None

    replacements: list[tuple[ast.AST, str]] = [
        (function, _rename_identifier_in_text(function_segment, old_name, keyword_name))
    ]
    for call in calls:
        replacement = _render_call_with_keyword_rename(source, call, old_name, keyword_name)
        if replacement is not None:
            replacements.append((call, replacement))

    patched = _apply_node_replacements(source, replacements)
    if patched == source or not _is_valid_python(patched):
        return None

    edit = _full_source_edit(source)
    action = PatchAction(
        kind=PatchActionKind.PROPAGATE_SIGNATURE,
        target=PatchTarget(
            file_path=file_path,
            start_line=function.lineno,
            end_line=function.end_lineno,
            symbol=function.name,
            node_kind="FunctionDef",
        ),
        params={"from": old_name, "to": keyword_name},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=f"propagate signature name {old_name} to {keyword_name}",
    )


def _candidate(
    *,
    file_path: str,
    source: str,
    node: ast.AST,
    kind: PatchActionKind,
    replacement: str,
    reason: str,
    params: dict[str, object] | None = None,
    symbol: str | None = None,
) -> CandidatePatch:
    edit = _node_edit(node, replacement)
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=kind,
        target=PatchTarget(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            symbol=symbol,
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


def _full_source_edit(source: str) -> SourceEdit:
    lines = source.splitlines(keepends=True)
    if not lines:
        return SourceEdit(start_line=1, start_col=0, end_line=1, end_col=0, replacement="")
    return SourceEdit(
        start_line=1,
        start_col=0,
        end_line=len(lines),
        end_col=len(lines[-1]),
        replacement=source,
    )


def _render_call_with_keyword_rename(
    source: str,
    node: ast.Call,
    old_name: str,
    new_name: str,
) -> str | None:
    func = ast.get_source_segment(source, node.func)
    if not func:
        return None

    parts: list[str] = []
    for arg in node.args:
        value = ast.get_source_segment(source, arg)
        if value is None:
            return None
        parts.append(value)
    changed = False
    for keyword in node.keywords:
        value = ast.get_source_segment(source, keyword.value)
        if value is None:
            return None
        if keyword.arg is None:
            parts.append(f"**{value}")
            continue
        name = new_name if keyword.arg == old_name else keyword.arg
        changed = changed or keyword.arg == old_name
        parts.append(f"{name}={value}")
    if not changed:
        return None
    return f"{func}({', '.join(parts)})"


def _rename_identifier_in_text(source: str, old_name: str, new_name: str) -> str:
    tokens = []
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if token.type == tokenize.NAME and token.string == old_name:
            token = tokenize.TokenInfo(token.type, new_name, token.start, token.end, token.line)
        tokens.append(token)
    return tokenize.untokenize(tokens)


def _apply_node_replacements(source: str, replacements: list[tuple[ast.AST, str]]) -> str:
    lines = source.splitlines(keepends=True)
    spans = [
        (
            _offset(lines, node.lineno, node.col_offset),
            _offset(lines, node.end_lineno, node.end_col_offset),
            replacement,
        )
        for node, replacement in replacements
    ]
    patched = source
    for start, end, replacement in sorted(spans, reverse=True):
        patched = patched[:start] + replacement + patched[end:]
    return patched


def _is_valid_python(source: str) -> bool:
    try:
        ast.parse(source)
    except SyntaxError:
        return False
    return True


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


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _load_model_if_available(model_path: Path | None) -> PatchRankingModel | None:
    if model_path is None:
        return None
    resolved = model_path.expanduser().resolve()
    if not resolved.exists():
        return None
    return PatchRankingModel.load(resolved)


def _load_candidate_ranker_if_available(ranker_path: Path | None) -> CandidateRankerModel | None:
    if ranker_path is None:
        return None
    resolved = ranker_path.expanduser().resolve()
    if not resolved.exists():
        return None
    return CandidateRankerModel.load(resolved)


def _failure_hint_score(candidate: CandidatePatch, hints: list[PytestFailureHint]) -> float:
    if not hints:
        return 0.0
    return max(_score_against_hint(candidate, hint) for hint in hints)


def _score_against_hint(candidate: CandidatePatch, hint: PytestFailureHint) -> float:
    score = 0.0
    symbol = candidate.action.target.symbol
    if symbol and symbol in hint.function_names:
        score += 40.0

    if candidate.file_path in hint.source_files:
        score += 20.0

    for location in hint.traceback_locations:
        if candidate.file_path == location.file_path and candidate.action.target.start_line == location.line:
            score += 12.0
            break

    for diagnostic in hint.tool_diagnostics:
        if candidate.file_path == diagnostic.file_path and candidate.action.target.start_line == diagnostic.line:
            score += 12.0
            break

    if hint.exception_type == "ZeroDivisionError" and candidate.action.kind == PatchActionKind.INSERT_GUARD:
        score += 20.0

    if candidate.action.kind == PatchActionKind.ADD_IMPORT:
        imported = str(candidate.action.params.get("name", ""))
        module = str(candidate.action.params.get("module", ""))
        if imported in hint.missing_names or module in hint.missing_modules:
            score += 60.0

    if candidate.action.kind == PatchActionKind.CHANGE_ATTRIBUTE:
        original = str(candidate.action.params.get("from", ""))
        if original in hint.missing_attributes:
            score += 50.0

    if candidate.action.kind == PatchActionKind.WRAP_TRY_EXCEPT:
        exception = str(candidate.action.params.get("exception", ""))
        if exception and exception == hint.exception_type:
            score += 35.0

    if candidate.action.kind == PatchActionKind.SWAP_CALL_ARG and hint.assertions:
        score += 10.0

    if candidate.action.kind in {PatchActionKind.RENAME_SYMBOL, PatchActionKind.PROPAGATE_SIGNATURE}:
        original = str(candidate.action.params.get("from", ""))
        replacement = str(candidate.action.params.get("to", ""))
        if original in hint.missing_names or original in hint.type_error_names:
            score += 45.0
        if replacement in hint.type_error_names:
            score += 20.0

    if any(isinstance(assertion.expected, bool) for assertion in hint.assertions):
        if candidate.action.kind in {PatchActionKind.CHANGE_OPERATOR, PatchActionKind.MODIFY_CONDITION}:
            score += 10.0

    literal_delta_score = _literal_delta_score(candidate, hint)
    if literal_delta_score:
        score += literal_delta_score

    if candidate.action.kind == PatchActionKind.REPLACE_EXPR and hint.assertions:
        score += 5.0

    return score


def _literal_delta_score(candidate: CandidatePatch, hint: PytestFailureHint) -> float:
    if candidate.action.kind != PatchActionKind.CHANGE_LITERAL:
        return 0.0
    original = candidate.action.params.get("from")
    replacement = candidate.action.params.get("to")
    if not isinstance(original, (int, float)) or isinstance(original, bool):
        return 0.0
    if not isinstance(replacement, (int, float)) or isinstance(replacement, bool):
        return 0.0

    score = 0.0
    for assertion in hint.assertions:
        delta = assertion.numeric_delta
        if original != 0 and delta is not None and replacement == original + delta:
            score += 40.0
        if replacement == assertion.expected:
            score += 10.0
    return score


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _nearest_exemplar_similarity(delta: list[float], exemplars: list[list[float]]) -> float | None:
    if not exemplars:
        return None
    return max(_cosine_similarity(delta, exemplar) for exemplar in exemplars)


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


def _call_exception(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name) and node.func.id in {"int", "float"}:
        return "ValueError"
    return None


def _function_arg_types(function: ast.FunctionDef) -> dict[str, str]:
    arg_types: dict[str, str] = {}
    for arg in function.args.args:
        if isinstance(arg.annotation, ast.Name):
            arg_types[arg.arg] = arg.annotation.id
    return arg_types


def _class_fields(tree: ast.Module) -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        class_fields: set[str] = set()
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                class_fields.add(statement.target.id)
            elif isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        class_fields.add(target.id)
        fields[node.name] = class_fields
    return fields


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _module_symbols(tree: ast.Module) -> set[str]:
    return _imported_names(tree) | _defined_names(tree)


def _local_symbols(function: ast.FunctionDef) -> set[str]:
    names = {arg.arg for arg in function.args.args}
    names.update(arg.arg for arg in function.args.kwonlyargs)
    if function.args.vararg is not None:
        names.add(function.args.vararg.arg)
    if function.args.kwarg is not None:
        names.add(function.args.kwarg.arg)
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.For):
            names.update(_target_names(node.target))
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars is not None:
                    names.update(_target_names(item.optional_vars))
    return names


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in node.elts:
            names.update(_target_names(element))
        return names
    return set()


def _import_insert_line(tree: ast.Module) -> int:
    insert_line = 1
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            insert_line = (node.end_lineno or node.lineno) + 1
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_line = (node.end_lineno or node.lineno) + 1
            continue
        break
    return insert_line


def _import_module(import_line: str) -> str:
    if import_line.startswith("from "):
        return import_line.split()[1]
    if import_line.startswith("import "):
        return import_line.split()[1].split(".", maxsplit=1)[0]
    return ""


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


def _offset(lines: list[str], line: int, col: int) -> int:
    return sum(len(value) for value in lines[: line - 1]) + col
