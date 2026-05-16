"""Patch planning and materialization for j3."""

from __future__ import annotations

import ast
import difflib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from actions import PatchAction, PatchActionKind, PatchTarget
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


def plan_and_maybe_apply_patch(
    *,
    repo: Path,
    test_command: str,
    dry_run: bool,
    timeout_seconds: int = DEFAULT_PATCH_TIMEOUT_SECONDS,
    max_candidates: int = 80,
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
        )

    candidates = generate_candidate_patches(root)
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

        for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
            arg_names = {arg.arg for arg in function.args.args}
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    candidates.extend(_return_candidates(source.relative_path, source.text, node, arg_names))
                elif isinstance(node, ast.Compare):
                    candidates.extend(_compare_candidates(source.relative_path, source.text, node))
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
