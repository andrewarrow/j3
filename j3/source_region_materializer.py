"""Bounded source-region materialization for constrained local generation probes."""

from __future__ import annotations

import ast
import difflib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from j3.ast_delta import python_ast_delta_metadata


ACTION_SCHEMA_VERSION = "source-region-action-v1"
CANDIDATE_AFTER_SCHEMA_VERSION = "source-region-candidate-after-v1"


class SourceRegionMaterializationError(ValueError):
    """Raised when a source-region action cannot be safely materialized."""

    def __init__(self, message: str, *, residual: str = "validation") -> None:
        super().__init__(message)
        self.residual = residual


class SourceRegionActionKind(str, Enum):
    """Supported bounded source-region actions."""

    REPLACE_FUNCTION_REGION = "replace_function_region"
    REPLACE_DELIMITED_REGION = "replace_delimited_region"


@dataclass(frozen=True, slots=True)
class SourceRegionConstraints:
    """Safety constraints for one bounded source-region replacement."""

    max_changed_source_lines: int = 12
    must_parse_ast: bool = True
    must_preserve_signature: bool = True
    allowed_import_changes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.max_changed_source_lines < 1:
            raise ValueError("max_changed_source_lines must be >= 1")

    def to_record(self) -> dict[str, object]:
        return {
            "max_changed_source_lines": self.max_changed_source_lines,
            "must_parse_ast": self.must_parse_ast,
            "must_preserve_signature": self.must_preserve_signature,
            "allowed_import_changes": list(self.allowed_import_changes),
        }


@dataclass(frozen=True, slots=True)
class SourceRegionTarget:
    """Stable target for a bounded source-region replacement."""

    file_path: str
    function_name: str | None = None
    region_name: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    start_marker: str | None = None
    end_marker: str | None = None

    def __post_init__(self) -> None:
        pure_path = PurePosixPath(self.file_path)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise ValueError("file_path must be relative to the repository root")

        has_line_selector = self.start_line is not None or self.end_line is not None
        has_marker_selector = (
            self.start_marker is not None or self.end_marker is not None
        )
        if has_line_selector == has_marker_selector:
            raise ValueError(
                "target must use exactly one selector: start/end lines or markers"
            )
        if has_line_selector:
            if self.start_line is None or self.end_line is None:
                raise ValueError("line selector requires start_line and end_line")
            if self.start_line < 1:
                raise ValueError("start_line must be >= 1")
            if self.end_line < self.start_line:
                raise ValueError("end_line must be >= start_line")
        if has_marker_selector:
            if not self.start_marker or not self.end_marker:
                raise ValueError("marker selector requires start_marker and end_marker")
            if "\n" in self.start_marker or "\n" in self.end_marker:
                raise ValueError("region markers must be single-line strings")

    def to_record(self) -> dict[str, object]:
        return {
            "file_path": self.file_path,
            "function_name": self.function_name,
            "region_name": self.region_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_marker": self.start_marker,
            "end_marker": self.end_marker,
        }


@dataclass(frozen=True, slots=True)
class SourceRegionAction:
    """Structured action before bounded source-region materialization."""

    kind: SourceRegionActionKind
    target: SourceRegionTarget
    replacement_source: str
    schema_version: str = ACTION_SCHEMA_VERSION
    constraints: SourceRegionConstraints = field(default_factory=SourceRegionConstraints)
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != ACTION_SCHEMA_VERSION:
            raise ValueError("unsupported source-region action schema")
        if (
            self.kind == SourceRegionActionKind.REPLACE_FUNCTION_REGION
            and self.target.function_name is None
        ):
            raise ValueError("replace_function_region requires a function_name")
        if self.kind == SourceRegionActionKind.REPLACE_DELIMITED_REGION and (
            self.target.start_marker is None or self.target.end_marker is None
        ):
            raise ValueError("replace_delimited_region requires explicit markers")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "target": self.target.to_record(),
            "constraints": self.constraints.to_record(),
            "replacement_source": self.replacement_source,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class SourceRegionMaterializationResult:
    """Candidate-after metadata for one safely materialized source region."""

    schema_version: str
    action_schema_version: str
    status: str
    file_path: str
    target_function: str | None
    touched_region: dict[str, object]
    changed_line_count: int
    added_line_count: int
    removed_line_count: int
    diff: str
    diff_summary: dict[str, object]
    import_changes: dict[str, list[str]]
    ast_delta: dict[str, object]
    ast_parse_ok: bool
    signature_preserved: bool | None
    patched_source: str = field(repr=False)
    wrote_file: bool = False

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "action_schema_version": self.action_schema_version,
            "status": self.status,
            "file_path": self.file_path,
            "target_function": self.target_function,
            "touched_region": _json_copy(self.touched_region),
            "wrote_file": self.wrote_file,
            "candidate_after": {
                "changed_line_count": self.changed_line_count,
                "added_line_count": self.added_line_count,
                "removed_line_count": self.removed_line_count,
                "ast_parse_ok": self.ast_parse_ok,
                "signature_preserved": self.signature_preserved,
                "import_changes": _json_copy(self.import_changes),
                "diff_summary": _json_copy(self.diff_summary),
                "diff": self.diff,
                "ast_delta": _json_copy(self.ast_delta),
            },
        }


def materialize_source_region(
    repo: Path,
    action: SourceRegionAction,
    *,
    write: bool = False,
) -> SourceRegionMaterializationResult:
    """Return candidate-after metadata for a bounded source-region replacement."""

    source_path = repo.expanduser().resolve() / action.target.file_path
    if not source_path.exists():
        raise SourceRegionMaterializationError(
            f"target file does not exist: {action.target.file_path}",
            residual="target_selection",
        )
    if not source_path.is_file():
        raise SourceRegionMaterializationError(
            f"target is not a file: {action.target.file_path}",
            residual="target_selection",
        )

    before_source = source_path.read_text(encoding="utf-8")
    patched_source, touched_region = materialize_source_region_text(
        before_source,
        action,
    )

    if write:
        source_path.write_text(patched_source, encoding="utf-8")

    return _candidate_after_result(
        before_source,
        patched_source,
        action,
        touched_region=touched_region,
        wrote_file=write,
    )


def materialize_source_region_text(
    source: str,
    action: SourceRegionAction,
) -> tuple[str, dict[str, object]]:
    """Apply a source-region action to text after validating the target region."""

    before_tree = _parse_python_source(
        source,
        filename=action.target.file_path,
        residual="target_selection",
    )
    target_function = _target_function(before_tree, action.target.function_name)
    start_line, end_line, selector = _resolve_region_lines(source, action.target)

    if target_function is not None:
        _validate_region_inside_function(
            target_function,
            start_line=start_line,
            end_line=end_line,
            function_name=action.target.function_name or target_function.name,
        )
    elif action.kind != SourceRegionActionKind.REPLACE_DELIMITED_REGION:
        raise SourceRegionMaterializationError(
            "non-function source regions must be explicitly delimited by markers",
            residual="target_selection",
        )

    source_lines = source.splitlines(keepends=True)
    replacement_lines = _replacement_lines(action.replacement_source)
    patched_source = "".join(
        source_lines[: start_line - 1]
        + replacement_lines
        + source_lines[end_line:]
    )

    after_tree = _parse_after_source(patched_source, action)
    signature_preserved: bool | None = None
    if target_function is not None and action.constraints.must_preserve_signature:
        after_function = _target_function(after_tree, action.target.function_name)
        signature_preserved = _function_signature(target_function) == _function_signature(
            after_function
        )
        if not signature_preserved:
            raise SourceRegionMaterializationError(
                f"target function signature changed: {target_function.name}",
                residual="validation",
            )

    import_changes = _import_changes(before_tree, after_tree)
    _validate_import_changes(import_changes, action.constraints.allowed_import_changes)

    stats = _line_change_stats(source, patched_source)
    if stats["changed_line_count"] > action.constraints.max_changed_source_lines:
        raise SourceRegionMaterializationError(
            "changed line budget exceeded: "
            f"{stats['changed_line_count']} > "
            f"{action.constraints.max_changed_source_lines}",
            residual="validation",
        )

    return patched_source, {
        "start_line": start_line,
        "end_line": end_line,
        "region_name": action.target.region_name,
        "selector": selector,
    }


def _candidate_after_result(
    before_source: str,
    patched_source: str,
    action: SourceRegionAction,
    *,
    touched_region: dict[str, object],
    wrote_file: bool,
) -> SourceRegionMaterializationResult:
    stats = _line_change_stats(before_source, patched_source)
    before_tree = _parse_python_source(
        before_source,
        filename=action.target.file_path,
        residual="target_selection",
    )
    after_tree = _parse_after_source(patched_source, action)
    import_changes = _import_changes(before_tree, after_tree)
    diff = _unified_diff(before_source, patched_source, action.target.file_path)
    diff_summary = {
        "hunk_count": diff.count("\n@@ "),
        "changed_line_count": stats["changed_line_count"],
        "added_line_count": stats["added_line_count"],
        "removed_line_count": stats["removed_line_count"],
    }

    signature_preserved: bool | None = None
    if action.target.function_name is not None:
        before_function = _target_function(before_tree, action.target.function_name)
        after_function = _target_function(after_tree, action.target.function_name)
        signature_preserved = _function_signature(before_function) == _function_signature(
            after_function
        )

    return SourceRegionMaterializationResult(
        schema_version=CANDIDATE_AFTER_SCHEMA_VERSION,
        action_schema_version=action.schema_version,
        status="materialized" if wrote_file else "candidate_after",
        file_path=action.target.file_path,
        target_function=action.target.function_name,
        touched_region=touched_region,
        changed_line_count=stats["changed_line_count"],
        added_line_count=stats["added_line_count"],
        removed_line_count=stats["removed_line_count"],
        diff=diff,
        diff_summary=diff_summary,
        import_changes=import_changes,
        ast_delta=python_ast_delta_metadata(before_source, patched_source),
        ast_parse_ok=True,
        signature_preserved=signature_preserved,
        patched_source=patched_source,
        wrote_file=wrote_file,
    )


def _resolve_region_lines(
    source: str,
    target: SourceRegionTarget,
) -> tuple[int, int, str]:
    if target.start_line is not None and target.end_line is not None:
        return target.start_line, target.end_line, "line_range"

    if target.start_marker is None or target.end_marker is None:
        raise SourceRegionMaterializationError(
            "target region is missing line range or explicit markers",
            residual="target_selection",
        )

    lines = source.splitlines()
    start_marker_line: int | None = None
    end_marker_line: int | None = None
    for index, line in enumerate(lines, start=1):
        if target.start_marker in line and start_marker_line is None:
            start_marker_line = index
            continue
        if target.end_marker in line and start_marker_line is not None:
            end_marker_line = index
            break

    if start_marker_line is None or end_marker_line is None:
        raise SourceRegionMaterializationError(
            "explicit region markers were not found",
            residual="target_selection",
        )
    if end_marker_line <= start_marker_line + 1:
        raise SourceRegionMaterializationError(
            "explicit marker region must contain at least one source line",
            residual="target_selection",
        )
    return start_marker_line + 1, end_marker_line - 1, "markers"


def _validate_region_inside_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    start_line: int,
    end_line: int,
    function_name: str,
) -> None:
    if function.end_lineno is None:
        raise SourceRegionMaterializationError(
            f"target function is missing end line: {function_name}",
            residual="target_selection",
        )
    if start_line < function.lineno or end_line > function.end_lineno:
        raise SourceRegionMaterializationError(
            f"target region is outside function: {function_name}",
            residual="target_selection",
        )


def _parse_after_source(source: str, action: SourceRegionAction) -> ast.Module:
    if not action.constraints.must_parse_ast:
        return _parse_python_source(
            source,
            filename=action.target.file_path,
            residual="source_region_synthesis",
        )
    return _parse_python_source(
        source,
        filename=action.target.file_path,
        residual="source_region_synthesis",
    )


def _parse_python_source(source: str, *, filename: str, residual: str) -> ast.Module:
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError as error:
        raise SourceRegionMaterializationError(
            f"invalid Python in {filename}: {error}",
            residual=residual,
        ) from error


def _target_function(
    tree: ast.Module,
    function_name: str | None,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    if function_name is None:
        return None

    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name == function_name
    ]
    if not matches:
        raise SourceRegionMaterializationError(
            f"target function not found: {function_name}",
            residual="target_selection",
        )
    if len(matches) > 1:
        raise SourceRegionMaterializationError(
            f"target function is ambiguous: {function_name}",
            residual="target_selection",
        )
    return matches[0]


def _function_signature(
    function: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object] | None:
    if function is None:
        return None
    return {
        "kind": type(function).__name__,
        "name": function.name,
        "args": ast.dump(function.args, include_attributes=False),
        "returns": (
            ast.dump(function.returns, include_attributes=False)
            if function.returns is not None
            else None
        ),
    }


def _import_changes(
    before_tree: ast.Module,
    after_tree: ast.Module,
) -> dict[str, list[str]]:
    before_imports = set(_import_fingerprints(before_tree))
    after_imports = set(_import_fingerprints(after_tree))
    return {
        "added": sorted(after_imports - before_imports),
        "removed": sorted(before_imports - after_imports),
    }


def _import_fingerprints(tree: ast.Module) -> list[str]:
    fingerprints: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases = ", ".join(_alias_fingerprint(alias) for alias in node.names)
            fingerprints.append(f"import {aliases}")
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            aliases = ", ".join(_alias_fingerprint(alias) for alias in node.names)
            fingerprints.append(f"from {module} import {aliases}")
    return fingerprints


def _alias_fingerprint(alias: ast.alias) -> str:
    if alias.asname:
        return f"{alias.name} as {alias.asname}"
    return alias.name


def _validate_import_changes(
    import_changes: dict[str, list[str]],
    allowed_import_changes: tuple[str, ...],
) -> None:
    added = set(import_changes["added"])
    removed = set(import_changes["removed"])
    if not added and not removed:
        return

    allowed = set(allowed_import_changes)
    if added <= allowed and removed <= allowed:
        return
    raise SourceRegionMaterializationError(
        "import changes are not allowed by this source-region action",
        residual="validation",
    )


def _line_change_stats(before_source: str, after_source: str) -> dict[str, int]:
    before_lines = before_source.splitlines()
    after_lines = after_source.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    added = 0
    removed = 0
    for tag, start_a, end_a, start_b, end_b in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed += end_a - start_a
        added += end_b - start_b
    return {
        "changed_line_count": added + removed,
        "added_line_count": added,
        "removed_line_count": removed,
    }


def _replacement_lines(replacement_source: str) -> list[str]:
    if not replacement_source:
        return []
    lines = replacement_source.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def _unified_diff(before_source: str, after_source: str, file_path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before_source.splitlines(keepends=True),
            after_source.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))
