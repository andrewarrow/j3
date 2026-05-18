"""Held-out typed-builder candidate materialization with reusable actions."""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from j3.ast_delta import python_ast_delta_metadata


HELDOUT_TYPED_BUILDER_SCHEMA_VERSION = "heldout-typed-builder-candidate-v1"
TYPED_ACTION_SCHEMA_VERSION = "typed-builder-action-v1"
DEFAULT_CLICK_3422_BASE_REF = "fc6c7c47edd6110b6bd5a1a5297b2035214b0cd1"
DEFAULT_CLICK_3422_HEAD_REF = "fc41aa1d0b62494eb93e92ff3929601221e3abf4"
DEFAULT_CLICK_3422_VALIDATION_COMMAND = "python -m py_compile src/click/utils.py"
CLICK_UTILS_PATH = "src/click/utils.py"


class HeldoutTypedBuilderCandidateError(ValueError):
    """Raised when a typed-builder candidate cannot be materialized."""

    def __init__(self, message: str, *, blocker: dict[str, str]) -> None:
        super().__init__(message)
        self.blocker = blocker


@dataclass(frozen=True, slots=True)
class ClassScopeAnnotationMoveAction:
    """Move or declare instance attribute annotations at class scope."""

    target_file: str
    class_name: str
    annotations: tuple[tuple[str, str], ...]
    source_method_name: str = "__init__"
    remove_instance_annotations: tuple[str, ...] = ()
    kind: str = "class_scope_annotation_move"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    max_added_annotations: int = 12
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.class_name:
            raise ValueError("class_name is required")
        if not self.annotations:
            raise ValueError("annotations are required")
        if len(self.annotations) > self.max_added_annotations:
            raise ValueError("annotation budget exceeded")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "source_method_name": self.source_method_name,
                "insertion_position": "class_scope_after_docstring_or_class_header",
            },
            "annotations": [
                {"attribute": name, "annotation": annotation}
                for name, annotation in self.annotations
            ],
            "remove_instance_annotations": list(self.remove_instance_annotations),
            "constraints": {
                "max_added_annotations": self.max_added_annotations,
                "must_parse_ast": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class TypeAnnotationUpdateAction:
    """Add or update a class-scope type annotation without moving an assignment."""

    target_file: str
    class_name: str
    annotations: tuple[tuple[str, str], ...]
    kind: str = "type_annotation_update"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    max_added_annotations: int = 8
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.class_name:
            raise ValueError("class_name is required")
        if not self.annotations:
            raise ValueError("annotations are required")
        if len(self.annotations) > self.max_added_annotations:
            raise ValueError("annotation budget exceeded")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "insertion_position": "class_scope_after_docstring_or_class_header",
            },
            "annotations": [
                {"attribute": name, "annotation": annotation}
                for name, annotation in self.annotations
            ],
            "constraints": {
                "max_added_annotations": self.max_added_annotations,
                "must_parse_ast": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ReturnAnnotationUpdateAction:
    """Add or update one function return annotation."""

    target_file: str
    function_name: str
    return_annotation: str
    class_name: str | None = None
    kind: str = "return_annotation_update"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.function_name:
            raise ValueError("function_name is required")
        if not self.return_annotation:
            raise ValueError("return_annotation is required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "function_name": self.function_name,
            },
            "return_annotation": self.return_annotation,
            "constraints": {
                "must_parse_ast": True,
                "single_signature_update": True,
            },
            "rationale": self.rationale,
        }


TypedAction = (
    ClassScopeAnnotationMoveAction
    | TypeAnnotationUpdateAction
    | ReturnAnnotationUpdateAction
)


@dataclass(frozen=True, slots=True)
class TypedActionResult:
    """Per-action before/after metadata."""

    action_kind: str
    target_file: str
    status: str
    diff: str
    diff_summary: dict[str, object]
    ast_delta: dict[str, object]
    ast_parse_ok: bool
    sha256_before: str
    sha256_after: str

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "typed-builder-action-result-v1",
            "action_kind": self.action_kind,
            "target_file": self.target_file,
            "status": self.status,
            "candidate_after": {
                "diff": self.diff,
                "diff_summary": dict(self.diff_summary),
                "ast_delta": _json_copy(self.ast_delta),
                "ast_parse_ok": self.ast_parse_ok,
                "sha256_before": self.sha256_before,
                "sha256_after": self.sha256_after,
            },
        }


@dataclass(frozen=True, slots=True)
class HeldoutTypedBuilderSpec:
    """Parameterized typed-builder candidate replay spec."""

    candidate_id: str
    repo_id: str
    repo_url: str
    repo_split: str
    base_ref: str
    accepted_head_ref: str
    reference_pr_url: str
    prompt: str
    target_file: str
    validation_command: str
    allowed_write_paths: tuple[str, ...]
    typed_actions: tuple[TypedAction, ...]
    action_family_reuse_evidence: tuple[dict[str, object], ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        for path in (self.target_file, *self.allowed_write_paths):
            _validate_relative_path(path)


@dataclass(frozen=True, slots=True)
class HeldoutTypedBuilderCandidate:
    """Structured candidate record for a held-out typed-builder attempt."""

    candidate_id: str
    repo_id: str
    repo_url: str
    repo_split: str
    base_ref: str
    accepted_head_ref: str
    reference_pr_url: str
    prompt: str
    status: str
    action_records: list[dict[str, object]]
    action_family_reuse_evidence: list[dict[str, object]]
    target_file: str
    validation_command: str
    allowed_write_paths: list[str]
    candidate_after: dict[str, object]
    mutation_scope: dict[str, object]
    accepted_diff_comparison: dict[str, object]
    validation: dict[str, object]
    blockers: list[dict[str, str]]
    residual_labels: list[str]
    zero_hosted_llm_source_judgment: bool = True

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": HELDOUT_TYPED_BUILDER_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "repo_id": self.repo_id,
            "repo_url": self.repo_url,
            "repo_split": self.repo_split,
            "base_ref": self.base_ref,
            "accepted_head_ref": self.accepted_head_ref,
            "reference_pr_url": self.reference_pr_url,
            "prompt": self.prompt,
            "status": self.status,
            "action_records": _json_copy(self.action_records),
            "action_family_reuse_evidence": _json_copy(
                self.action_family_reuse_evidence
            ),
            "target_file": self.target_file,
            "validation_command": self.validation_command,
            "allowed_write_paths": list(self.allowed_write_paths),
            "candidate_after": _json_copy(self.candidate_after),
            "mutation_scope": _json_copy(self.mutation_scope),
            "accepted_diff_comparison": _json_copy(self.accepted_diff_comparison),
            "validation": _json_copy(self.validation),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "residual_labels": list(self.residual_labels),
            "zero_hosted_llm_source_judgment": self.zero_hosted_llm_source_judgment,
        }


def build_click_utils_annotation_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_CLICK_3422_BASE_REF,
    accepted_head_ref: str = DEFAULT_CLICK_3422_HEAD_REF,
    validation_command: str = DEFAULT_CLICK_3422_VALIDATION_COMMAND,
) -> HeldoutTypedBuilderSpec:
    """Build the held-out click#3422 typed annotation candidate spec."""

    _repo_file(repo_path, CLICK_UTILS_PATH)
    return HeldoutTypedBuilderSpec(
        candidate_id="mat-010-click-utils-instance-annotations",
        repo_id="pallets/click",
        repo_url="https://github.com/pallets/click",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/pallets/click/pull/3422",
        prompt="Add type annotations for instance attributes in click.utils.",
        target_file=CLICK_UTILS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(CLICK_UTILS_PATH,),
        typed_actions=(
            ClassScopeAnnotationMoveAction(
                target_file=CLICK_UTILS_PATH,
                class_name="LazyFile",
                annotations=(
                    ("name", "str"),
                    ("mode", "str"),
                    ("encoding", "str | None"),
                    ("errors", "str | None"),
                    ("atomic", "bool"),
                    ("_f", "t.IO[t.Any] | None"),
                    ("should_close", "bool"),
                ),
                remove_instance_annotations=("name", "_f", "should_close"),
                rationale=(
                    "declare LazyFile instance attributes at class scope and "
                    "remove duplicate inline self annotations"
                ),
            ),
            ReturnAnnotationUpdateAction(
                target_file=CLICK_UTILS_PATH,
                class_name="LazyFile",
                function_name="__init__",
                return_annotation="None",
                rationale="annotate LazyFile.__init__ as returning None",
            ),
            ClassScopeAnnotationMoveAction(
                target_file=CLICK_UTILS_PATH,
                class_name="KeepOpenFile",
                annotations=(("_file", "t.IO[t.Any]"),),
                remove_instance_annotations=("_file",),
                rationale=(
                    "move KeepOpenFile._file annotation from constructor "
                    "assignment to class scope"
                ),
            ),
            TypeAnnotationUpdateAction(
                target_file=CLICK_UTILS_PATH,
                class_name="PacifyFlushWrapper",
                annotations=(("wrapped", "t.IO[t.Any]"),),
                rationale="declare wrapped proxy target at class scope",
            ),
        ),
        action_family_reuse_evidence=(
            {
                "action_kind": "class_scope_annotation_move",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "source_method_name",
                    "annotations",
                    "remove_instance_annotations",
                ],
                "evidence": (
                    "covers class-scope instance attribute annotations for "
                    "LazyFile and KeepOpenFile without a PR-named action kind"
                ),
            },
            {
                "action_kind": "return_annotation_update",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "function_name",
                    "return_annotation",
                ],
                "evidence": (
                    "updates a function or method return annotation by AST "
                    "target rather than by line-number patch"
                ),
            },
            {
                "action_kind": "type_annotation_update",
                "reusable_parameters": ["target_file", "class_name", "annotations"],
                "evidence": (
                    "adds class-scope annotations where no inline annotation "
                    "needs to be removed"
                ),
            },
        ),
    )


def materialize_heldout_typed_builder_candidate(
    repo_path: Path,
    spec: HeldoutTypedBuilderSpec,
    *,
    write: bool = True,
    validate: bool = False,
    accepted_diff_path: Path | None = None,
    validation_timeout_seconds: int = 180,
) -> HeldoutTypedBuilderCandidate:
    """Materialize typed-builder actions and record candidate-after metadata."""

    repo = repo_path.expanduser().resolve()
    blockers: list[dict[str, str]] = []
    action_records = [action.to_record() for action in spec.typed_actions]

    head = _git_stdout(repo, ("rev-parse", "HEAD"))
    if head and head != spec.base_ref:
        blockers.append(
            {
                "field": "repo_before_ref",
                "reason": "repo_before_ref_mismatch",
                "message": f"expected {spec.base_ref}, got {head}",
            }
        )

    target_path = _repo_file(repo, spec.target_file)
    before_file = target_path.read_text(encoding="utf-8")
    hashes_before = _file_hashes(repo, spec.allowed_write_paths)
    action_results: list[TypedActionResult] = []
    current_source = before_file

    if not blockers:
        for action in spec.typed_actions:
            try:
                next_source = _apply_typed_action(current_source, action)
            except HeldoutTypedBuilderCandidateError as error:
                blockers.append(error.blocker)
                break
            action_results.append(
                _typed_action_result(
                    current_source,
                    next_source,
                    action_kind=action.kind,
                    target_file=action.target_file,
                )
            )
            current_source = next_source

    if write and not blockers and current_source != before_file:
        target_path.write_text(current_source, encoding="utf-8")

    hashes_after = _file_hashes(repo, spec.allowed_write_paths)
    candidate_diff = _git_diff(repo, spec.allowed_write_paths)
    changed_files = _git_changed_files(repo, spec.allowed_write_paths)
    writes_outside_allowlist = _paths_outside_allowlist(
        changed_files,
        spec.allowed_write_paths,
    )
    if writes_outside_allowlist:
        blockers.append(
            {
                "field": "mutation_scope",
                "reason": "writes_outside_allowlist",
                "message": "candidate changed files outside the allowed write paths",
            }
        )

    validation = _deferred_validation(spec.validation_command)
    if validate and not blockers:
        validation = _run_validation(
            repo,
            spec.validation_command,
            timeout_seconds=validation_timeout_seconds,
        )

    accepted_diff_comparison = _accepted_diff_comparison(
        candidate_diff,
        accepted_diff_path=accepted_diff_path,
    )
    if accepted_diff_comparison.get("accepted_diff_available") is False:
        blockers.append(
            {
                "field": "accepted_diff",
                "reason": "accepted_diff_unavailable",
                "message": str(accepted_diff_comparison.get("message", "")),
            }
        )

    final_ast_delta = python_ast_delta_metadata(before_file, current_source)
    candidate_after = {
        "target_file": {
            "schema_version": "typed-builder-file-candidate-after-v1",
            "target_file": spec.target_file,
            "wrote_file": bool(write and not blockers and current_source != before_file),
            "candidate_after": {
                "diff": _unified_diff(before_file, current_source, spec.target_file),
                "diff_summary": _diff_summary(
                    _unified_diff(before_file, current_source, spec.target_file)
                ),
                "ast_delta": final_ast_delta,
                "ast_parse_ok": final_ast_delta.get("ast_parse_ok") is True,
                "sha256_before": _sha256_text(before_file),
                "sha256_after": _sha256_text(current_source),
            },
        },
        "action_results": [result.to_record() for result in action_results],
        "candidate_diff": candidate_diff,
        "candidate_diff_summary": _diff_summary(candidate_diff),
        "candidate_changed_files": changed_files,
        "file_hashes_before": hashes_before,
        "file_hashes_after": hashes_after,
    }
    mutation_scope = {
        "mode": "heldout_typed_builder_one_file",
        "allowed_write_paths": list(spec.allowed_write_paths),
        "planned_write_files": [spec.target_file],
        "actual_changed_files": changed_files,
        "writes_outside_allowlist": writes_outside_allowlist,
        "only_accepted_files_changed": (
            not writes_outside_allowlist
            and set(changed_files) <= set(spec.allowed_write_paths)
        ),
    }
    status = "blocked" if blockers else "planned"
    if not blockers and write:
        status = "validated" if validation["status"] == "passed" else "materialized"

    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation["status"] == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation['status']}"]
        else:
            residual_labels = ["candidate_validation_deferred"]

    return HeldoutTypedBuilderCandidate(
        candidate_id=spec.candidate_id,
        repo_id=spec.repo_id,
        repo_url=spec.repo_url,
        repo_split=spec.repo_split,
        base_ref=spec.base_ref,
        accepted_head_ref=spec.accepted_head_ref,
        reference_pr_url=spec.reference_pr_url,
        prompt=spec.prompt,
        status=status,
        action_records=action_records,
        action_family_reuse_evidence=[
            dict(item) for item in spec.action_family_reuse_evidence
        ],
        target_file=spec.target_file,
        validation_command=spec.validation_command,
        allowed_write_paths=list(spec.allowed_write_paths),
        candidate_after=candidate_after,
        mutation_scope=mutation_scope,
        accepted_diff_comparison=accepted_diff_comparison,
        validation=validation,
        blockers=blockers,
        residual_labels=residual_labels,
    )


def write_candidate_artifacts(
    candidate: HeldoutTypedBuilderCandidate,
    *,
    out_path: Path,
    report_path: Path | None = None,
    diff_path: Path | None = None,
) -> None:
    """Write JSON, optional markdown, and optional diff artifacts."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(candidate.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_candidate_report(candidate), encoding="utf-8")
    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(
            str(candidate.candidate_after.get("candidate_diff", "")),
            encoding="utf-8",
        )


def render_candidate_report(candidate: HeldoutTypedBuilderCandidate) -> str:
    """Render a compact markdown report for a held-out typed-builder candidate."""

    validation = candidate.validation
    comparison = candidate.accepted_diff_comparison
    lines = [
        "# Held-Out Typed-Builder Candidate",
        "",
        f"- Candidate: `{candidate.candidate_id}`",
        f"- Repo: `{candidate.repo_id}`",
        f"- Base ref: `{candidate.base_ref}`",
        f"- Accepted head ref: `{candidate.accepted_head_ref}`",
        f"- Reference PR: {candidate.reference_pr_url}",
        f"- Status: `{candidate.status}`",
        f"- Changed files: `{candidate.mutation_scope.get('actual_changed_files')}`",
        f"- Accepted changed files: "
        f"`{comparison.get('accepted_changed_files')}`",
        f"- Validation: `{validation.get('status')}` "
        f"(`{candidate.validation_command}`)",
        f"- Accepted diff normalized match: "
        f"`{comparison.get('normalized_diff_equal')}`",
        f"- Zero hosted LLM source judgment: "
        f"`{candidate.zero_hosted_llm_source_judgment}`",
        "",
        "## Reusable Actions",
        "",
    ]
    for action in candidate.action_records:
        lines.append(f"- `{action.get('kind')}`")
    lines.extend(["", "## Residuals", ""])
    if candidate.blockers:
        for blocker in candidate.blockers:
            lines.append(
                f"- `{blocker['field']}`: `{blocker['reason']}` - "
                f"{blocker['message']}"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _apply_typed_action(source: str, action: TypedAction) -> str:
    if isinstance(action, ClassScopeAnnotationMoveAction):
        patched = _ensure_class_annotations(
            source,
            target_file=action.target_file,
            class_name=action.class_name,
            annotations=action.annotations,
        )
        return _remove_instance_assignment_annotations(
            patched,
            target_file=action.target_file,
            class_name=action.class_name,
            method_name=action.source_method_name,
            attributes=action.remove_instance_annotations,
        )
    if isinstance(action, TypeAnnotationUpdateAction):
        return _ensure_class_annotations(
            source,
            target_file=action.target_file,
            class_name=action.class_name,
            annotations=action.annotations,
        )
    if isinstance(action, ReturnAnnotationUpdateAction):
        return _ensure_return_annotation(
            source,
            target_file=action.target_file,
            class_name=action.class_name,
            function_name=action.function_name,
            return_annotation=action.return_annotation,
        )
    raise TypeError(f"unsupported typed action: {type(action).__name__}")


def _ensure_class_annotations(
    source: str,
    *,
    target_file: str,
    class_name: str,
    annotations: Sequence[tuple[str, str]],
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    class_node = _find_class(tree, class_name)
    if class_node is None:
        raise HeldoutTypedBuilderCandidateError(
            f"class not found: {class_name}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"class not found: {class_name}",
            },
        )

    existing = _class_scope_annotation_names(class_node)
    missing = [(name, annotation) for name, annotation in annotations if name not in existing]
    if not missing:
        return source

    lines = source.splitlines(keepends=True)
    indent = _indent_for_class_body(lines[class_node.lineno - 1])
    insert_index = _class_annotation_insert_index(lines, class_node)
    insertion = [f"{indent}{name}: {annotation}\n" for name, annotation in missing]
    insertion.append("\n")
    patched = "".join(lines[:insert_index] + insertion + lines[insert_index:])
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _remove_instance_assignment_annotations(
    source: str,
    *,
    target_file: str,
    class_name: str,
    method_name: str,
    attributes: Sequence[str],
) -> str:
    if not attributes:
        return source
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    class_node = _find_class(tree, class_name)
    method = _find_method(class_node, method_name) if class_node is not None else None
    if class_node is None or method is None or method.end_lineno is None:
        raise HeldoutTypedBuilderCandidateError(
            f"method not found: {class_name}.{method_name}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"method not found: {class_name}.{method_name}",
            },
        )

    attr_set = set(attributes)
    lines = source.splitlines(keepends=True)
    patched_lines = list(lines)
    for index in range(method.lineno - 1, method.end_lineno):
        line = patched_lines[index]
        for attr in attr_set:
            replacement = _remove_self_annotation_from_line(line, attr)
            if replacement is not None:
                patched_lines[index] = replacement
                break
    patched = "".join(patched_lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _ensure_return_annotation(
    source: str,
    *,
    target_file: str,
    class_name: str | None,
    function_name: str,
    return_annotation: str,
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    function = _find_function_or_method(tree, class_name, function_name)
    if function is None:
        target = f"{class_name}.{function_name}" if class_name else function_name
        raise HeldoutTypedBuilderCandidateError(
            f"function not found: {target}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"function not found: {target}",
            },
        )
    current_return = ast.unparse(function.returns) if function.returns is not None else None
    if current_return == return_annotation:
        return source
    if function.body:
        signature_end_lineno = function.body[0].lineno - 1
    else:
        signature_end_lineno = function.end_lineno or function.lineno

    lines = source.splitlines(keepends=True)
    line = lines[signature_end_lineno - 1]
    if "->" in line:
        patched_line = re.sub(r"\)\s*->\s*[^:]+:", f") -> {return_annotation}:", line)
    else:
        patched_line = re.sub(r"\)\s*:", f") -> {return_annotation}:", line)
    if patched_line == line:
        raise HeldoutTypedBuilderCandidateError(
            f"could not update return annotation for {function_name}",
            blocker={
                "field": "typed_builder",
                "reason": "return_annotation_update_blocked",
                "message": f"could not update return annotation for {function_name}",
            },
        )
    lines[signature_end_lineno - 1] = patched_line
    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _typed_action_result(
    before: str,
    after: str,
    *,
    action_kind: str,
    target_file: str,
) -> TypedActionResult:
    diff = _unified_diff(before, after, target_file)
    ast_delta = python_ast_delta_metadata(before, after)
    return TypedActionResult(
        action_kind=action_kind,
        target_file=target_file,
        status="materialized" if before != after else "already_applied",
        diff=diff,
        diff_summary=_diff_summary(diff),
        ast_delta=ast_delta,
        ast_parse_ok=ast_delta.get("ast_parse_ok") is True,
        sha256_before=_sha256_text(before),
        sha256_after=_sha256_text(after),
    )


def _find_class(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _find_method(
    class_node: ast.ClassDef | None,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    if class_node is None:
        return None
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == method_name:
            return node
    return None


def _find_function_or_method(
    tree: ast.Module,
    class_name: str | None,
    function_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    if class_name is not None:
        return _find_method(_find_class(tree, class_name), function_name)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function_name:
            return node
    return None


def _class_scope_annotation_names(class_node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for node in class_node.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _class_annotation_insert_index(lines: Sequence[str], class_node: ast.ClassDef) -> int:
    if class_node.body:
        first = class_node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and first.end_lineno is not None
        ):
            index = first.end_lineno
            while index < len(lines) and not lines[index].strip():
                index += 1
            return index
    return class_node.lineno


def _indent_for_class_body(class_line: str) -> str:
    base_indent = class_line[: len(class_line) - len(class_line.lstrip())]
    return f"{base_indent}    "


def _remove_self_annotation_from_line(line: str, attribute: str) -> str | None:
    pattern = rf"^(?P<indent>\s*)self\.{re.escape(attribute)}:\s*(?P<annotation>[^=\n]+?)(?P<tail>\s*=\s*.*)?(?P<newline>\n?)$"
    match = re.match(pattern, line)
    if match is None:
        return None
    tail = match.group("tail")
    if tail is None:
        return ""
    return f"{match.group('indent')}self.{attribute}{tail}{match.group('newline')}"


def _repo_file(repo: Path, relative_path: str) -> Path:
    _validate_relative_path(relative_path)
    path = repo / relative_path
    if not path.exists():
        raise HeldoutTypedBuilderCandidateError(
            f"file does not exist: {relative_path}",
            blocker={
                "field": "repo_state",
                "reason": "missing_target_file",
                "message": f"file does not exist: {relative_path}",
            },
        )
    return path


def _validate_relative_path(path: str) -> None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError("paths must be relative to the repository root")


def _parse_python(source: str, *, filename: str, field: str) -> ast.Module:
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError as error:
        raise HeldoutTypedBuilderCandidateError(
            f"invalid Python in {filename}: {error}",
            blocker={
                "field": field,
                "reason": "python_ast_parse_failed",
                "message": str(error),
            },
        ) from error


def _file_hashes(repo: Path, paths: Sequence[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        file_path = repo / path
        hashes[path] = _sha256_bytes(file_path.read_bytes()) if file_path.exists() else ""
    return hashes


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_text(content: str) -> str:
    return _sha256_bytes(content.encode("utf-8"))


def _git_stdout(repo: Path, args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _git_diff(repo: Path, paths: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", "diff", "--", *paths],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _git_changed_files(repo: Path, paths: Sequence[str]) -> list[str]:
    output = _git_stdout(repo, ("diff", "--name-only", "--", *paths))
    return [line for line in output.splitlines() if line]


def _paths_outside_allowlist(paths: Sequence[str], allowed: Sequence[str]) -> list[str]:
    allowed_set = set(allowed)
    return [path for path in paths if path not in allowed_set]


def _run_validation(
    repo: Path,
    command: str,
    *,
    timeout_seconds: int,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            shell=True,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        runtime = time.monotonic() - started
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "command": command,
            "returncode": completed.returncode,
            "runtime_seconds": round(runtime, 3),
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as error:
        runtime = time.monotonic() - started
        return {
            "status": "timeout",
            "command": command,
            "returncode": None,
            "runtime_seconds": round(runtime, 3),
            "stdout_tail": (error.stdout or "")[-4000:],
            "stderr_tail": (error.stderr or "")[-4000:],
        }


def _deferred_validation(command: str) -> dict[str, object]:
    return {
        "status": "deferred",
        "command": command,
        "returncode": None,
        "runtime_seconds": None,
    }


def _accepted_diff_comparison(
    candidate_diff: str,
    *,
    accepted_diff_path: Path | None,
) -> dict[str, object]:
    if accepted_diff_path is None:
        return {
            "accepted_diff_available": False,
            "message": "no accepted diff path was provided",
        }
    if not accepted_diff_path.exists():
        return {
            "accepted_diff_available": False,
            "message": f"accepted diff path does not exist: {accepted_diff_path}",
        }
    accepted_diff = accepted_diff_path.read_text(encoding="utf-8")
    normalized_candidate = _normalize_diff(candidate_diff)
    normalized_accepted = _normalize_diff(accepted_diff)
    candidate_changed_files = _diff_changed_files(candidate_diff)
    accepted_changed_files = _diff_changed_files(accepted_diff)
    scoped_accepted_diff = _filter_diff_to_paths(
        accepted_diff,
        candidate_changed_files,
    )
    normalized_scoped_accepted = _normalize_diff(scoped_accepted_diff)
    return {
        "accepted_diff_available": True,
        "candidate_changed_files": candidate_changed_files,
        "accepted_changed_files": accepted_changed_files,
        "changed_file_sets_equal": candidate_changed_files == accepted_changed_files,
        "candidate_diff_line_count": len(candidate_diff.splitlines()),
        "accepted_diff_line_count": len(accepted_diff.splitlines()),
        "normalized_diff_equal": normalized_candidate == normalized_accepted,
        "scoped_paths": candidate_changed_files,
        "scoped_accepted_diff_line_count": len(scoped_accepted_diff.splitlines()),
        "scoped_normalized_diff_equal": (
            normalized_candidate == normalized_scoped_accepted
        ),
        "parity_diff": ""
        if normalized_candidate == normalized_accepted
        else "".join(
            difflib.unified_diff(
                normalized_accepted.splitlines(keepends=True),
                normalized_candidate.splitlines(keepends=True),
                fromfile="accepted.diff",
                tofile="candidate.diff",
            )
        ),
    }


def _normalize_diff(diff: str) -> str:
    lines = []
    for line in diff.splitlines():
        if line.startswith("index "):
            continue
        if line.startswith("@@ "):
            line = re.sub(r"^(@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@).*$", r"\1", line)
        lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def _diff_changed_files(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        path = parts[3]
        if path.startswith("b/"):
            path = path[2:]
        files.append(path)
    return files


def _filter_diff_to_paths(diff: str, paths: Sequence[str]) -> str:
    path_set = set(paths)
    sections: list[list[str]] = []
    current: list[str] = []
    include_current = False
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current and include_current:
                sections.append(current)
            current = [line]
            parts = line.split()
            path = parts[3][2:] if len(parts) >= 4 and parts[3].startswith("b/") else ""
            include_current = path in path_set
            continue
        if current:
            current.append(line)
    if current and include_current:
        sections.append(current)
    return "".join("".join(section) for section in sections)


def _diff_summary(diff: str) -> dict[str, object]:
    added = 0
    removed = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {
        "hunk_count": diff.count("\n@@ "),
        "changed_line_count": added + removed,
        "added_line_count": added,
        "removed_line_count": removed,
    }


def _unified_diff(before: str, after: str, file_path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize a held-out typed-builder candidate."
    )
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--accepted-diff", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--diff-out", type=Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--validation-timeout-seconds", type=int, default=180)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    spec = build_click_utils_annotation_spec(args.repo_path)
    candidate = materialize_heldout_typed_builder_candidate(
        args.repo_path,
        spec,
        write=not args.no_write,
        validate=args.validate,
        accepted_diff_path=args.accepted_diff,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    write_candidate_artifacts(
        candidate,
        out_path=args.out,
        report_path=args.report,
        diff_path=args.diff_out,
    )
    return 0 if candidate.status != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
