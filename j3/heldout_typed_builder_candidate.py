"""Held-out typed-builder candidate materialization with reusable actions."""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
import subprocess
import textwrap
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
DEFAULT_REQUESTS_7441_BASE_REF = "b7b549b54571d03950b16afd2d01bc6ff0348224"
DEFAULT_REQUESTS_7441_HEAD_REF = "412f581d7e7c27bfee4f042fcac89bae9a804afe"
DEFAULT_REQUESTS_7441_VALIDATION_COMMAND = (
    "python -m py_compile src/requests/_types.py src/requests/models.py"
)
REQUESTS_TYPES_PATH = "src/requests/_types.py"
REQUESTS_MODELS_PATH = "src/requests/models.py"
DEFAULT_CLICK_3396_BASE_REF = "fed9049f7a07550d560a91b30c5b0b3e17d54981"
DEFAULT_CLICK_3396_HEAD_REF = "3df4d601a5f1d1db50cbf0b33e5b0816189bc5a8"
DEFAULT_CLICK_3396_VALIDATION_COMMAND = (
    "python -m py_compile src/click/_utils.py src/click/core.py src/click/parser.py"
)
CLICK_INTERNAL_UTILS_PATH = "src/click/_utils.py"
CLICK_CORE_PATH = "src/click/core.py"
CLICK_PARSER_PATH = "src/click/parser.py"
DEFAULT_REQUESTS_7437_BASE_REF = "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
DEFAULT_REQUESTS_7437_HEAD_REF = "dfe9ab8143fb71c72673738f25f0571347226b63"
DEFAULT_REQUESTS_7437_VALIDATION_COMMAND = "python -m py_compile src/requests/models.py"


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
class TypeAliasUpdateAction:
    """Update the value expression for a named TypeAlias assignment."""

    target_file: str
    alias_name: str
    value: str
    kind: str = "type_alias_update"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.alias_name:
            raise ValueError("alias_name is required")
        if not self.value:
            raise ValueError("value is required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "alias_name": self.alias_name,
            },
            "value": self.value,
            "constraints": {
                "must_parse_ast": True,
                "single_type_alias_assignment": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ImportMemberRemoveAction:
    """Remove one or more imported names from a from-import statement."""

    target_file: str
    module: str
    names: tuple[str, ...]
    type_checking_only: bool = False
    kind: str = "import_member_remove"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.module:
            raise ValueError("module is required")
        if not self.names:
            raise ValueError("names are required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "module": self.module,
                "type_checking_only": self.type_checking_only,
            },
            "names": list(self.names),
            "constraints": {
                "must_parse_ast": True,
                "single_line_from_import": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class AssignmentAnnotationUpdateAction:
    """Add or update an assignment annotation in a module, function, or method."""

    target_file: str
    assignment_name: str
    annotation: str
    value: str | None = None
    function_name: str | None = None
    class_name: str | None = None
    kind: str = "assignment_annotation_update"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.assignment_name:
            raise ValueError("assignment_name is required")
        if not self.annotation:
            raise ValueError("annotation is required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "function_name": self.function_name,
                "assignment_name": self.assignment_name,
            },
            "annotation": self.annotation,
            "value": self.value,
            "constraints": {
                "must_parse_ast": True,
                "single_assignment_target": True,
                "single_line_assignment": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class AssignmentTypeIgnoreUpdateAction:
    """Add or update a type-ignore comment for one assignment target."""

    target_file: str
    assignment_name: str
    type_ignore_codes: tuple[str, ...]
    function_name: str
    class_name: str | None = None
    kind: str = "assignment_type_ignore_update"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.assignment_name:
            raise ValueError("assignment_name is required")
        if not self.type_ignore_codes:
            raise ValueError("type_ignore_codes are required")
        if not self.function_name:
            raise ValueError("function_name is required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "function_name": self.function_name,
                "assignment_name": self.assignment_name,
            },
            "type_ignore_codes": list(self.type_ignore_codes),
            "constraints": {
                "must_parse_ast": True,
                "single_assignment_target": True,
                "single_line_assignment": True,
                "assignment_target_must_match_exactly_once": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class FunctionSignatureUpdateAction:
    """Update parameter and return annotations for one function target."""

    target_file: str
    function_name: str
    parameter_annotations: tuple[tuple[str, str], ...] = ()
    return_annotation: str | None = None
    class_name: str | None = None
    parent_function_name: str | None = None
    kind: str = "function_signature_update"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    max_parameter_updates: int = 6
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.function_name:
            raise ValueError("function_name is required")
        if not self.parameter_annotations and not self.return_annotation:
            raise ValueError("parameter or return annotation update is required")
        if len(self.parameter_annotations) > self.max_parameter_updates:
            raise ValueError("parameter annotation budget exceeded")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "parent_function_name": self.parent_function_name,
                "function_name": self.function_name,
            },
            "parameter_annotations": [
                {"parameter": name, "annotation": annotation}
                for name, annotation in self.parameter_annotations
            ],
            "return_annotation": self.return_annotation,
            "constraints": {
                "max_parameter_updates": self.max_parameter_updates,
                "must_parse_ast": True,
                "single_signature_update": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class BooleanConditionInsertAction:
    """Insert a boolean conjunct next to an existing anchored condition."""

    target_file: str
    function_name: str
    anchor_condition: str
    condition: str
    class_name: str | None = None
    position: str = "after"
    kind: str = "boolean_condition_insert"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if self.position not in {"before", "after"}:
            raise ValueError("position must be before or after")
        if not self.function_name:
            raise ValueError("function_name is required")
        if not self.anchor_condition:
            raise ValueError("anchor_condition is required")
        if not self.condition:
            raise ValueError("condition is required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "function_name": self.function_name,
                "anchor_condition": self.anchor_condition,
                "position": self.position,
            },
            "condition": self.condition,
            "constraints": {
                "must_parse_ast": True,
                "condition_must_parse_as_expression": True,
                "anchor_line_must_be_unique_in_function": True,
            },
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class StatementBlockReplaceAction:
    """Replace a small exact statement block inside a function or method."""

    target_file: str
    function_name: str
    old_block: str
    new_block: str
    class_name: str | None = None
    parent_function_name: str | None = None
    kind: str = "statement_block_replace"
    schema_version: str = TYPED_ACTION_SCHEMA_VERSION
    max_old_lines: int = 8
    max_new_lines: int = 8
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if not self.function_name:
            raise ValueError("function_name is required")
        if not self.old_block.strip():
            raise ValueError("old_block is required")
        if not self.new_block.strip():
            raise ValueError("new_block is required")
        if len(_normalized_block_lines(self.old_block)) > self.max_old_lines:
            raise ValueError("old block line budget exceeded")
        if len(_normalized_block_lines(self.new_block)) > self.max_new_lines:
            raise ValueError("new block line budget exceeded")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "class_name": self.class_name,
                "parent_function_name": self.parent_function_name,
                "function_name": self.function_name,
            },
            "old_block": self.old_block,
            "new_block": self.new_block,
            "constraints": {
                "max_old_lines": self.max_old_lines,
                "max_new_lines": self.max_new_lines,
                "must_parse_ast": True,
                "old_block_must_match_exactly_once": True,
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
    | TypeAliasUpdateAction
    | ImportMemberRemoveAction
    | AssignmentAnnotationUpdateAction
    | AssignmentTypeIgnoreUpdateAction
    | FunctionSignatureUpdateAction
    | BooleanConditionInsertAction
    | StatementBlockReplaceAction
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
        allowed = set(self.allowed_write_paths)
        for action in self.typed_actions:
            if action.target_file not in allowed:
                raise ValueError(
                    f"action target_file must be in allowed_write_paths: {action.target_file}"
                )


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
    typed_builder_layer_judgment: dict[str, object]
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
            "typed_builder_layer_judgment": _json_copy(
                self.typed_builder_layer_judgment
            ),
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


def build_requests_headers_mapping_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_REQUESTS_7441_BASE_REF,
    accepted_head_ref: str = DEFAULT_REQUESTS_7441_HEAD_REF,
    validation_command: str = DEFAULT_REQUESTS_7441_VALIDATION_COMMAND,
) -> HeldoutTypedBuilderSpec:
    """Build the held-out requests#7441 headers Mapping candidate spec."""

    _repo_file(repo_path, REQUESTS_TYPES_PATH)
    _repo_file(repo_path, REQUESTS_MODELS_PATH)
    return HeldoutTypedBuilderSpec(
        candidate_id="mat-011-requests-headers-mapping",
        repo_id="psf/requests",
        repo_url="https://github.com/psf/requests",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/psf/requests/pull/7441",
        prompt=(
            "Move Request.headers typing back from MutableMapping to Mapping "
            "while keeping accepted type-checking imports minimal."
        ),
        target_file=REQUESTS_MODELS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(REQUESTS_TYPES_PATH, REQUESTS_MODELS_PATH),
        typed_actions=(
            TypeAliasUpdateAction(
                target_file=REQUESTS_TYPES_PATH,
                alias_name="HeadersType",
                value="Mapping[str, str | bytes] | None",
                rationale=(
                    "change the request headers input alias from mutable to "
                    "read-only mapping"
                ),
            ),
            ImportMemberRemoveAction(
                target_file=REQUESTS_MODELS_PATH,
                module="collections.abc",
                names=("MutableMapping",),
                type_checking_only=True,
                rationale=(
                    "remove the no-longer-used type-checking import after the "
                    "headers annotation update"
                ),
            ),
            TypeAnnotationUpdateAction(
                target_file=REQUESTS_MODELS_PATH,
                class_name="Request",
                annotations=(("headers", "Mapping[str, str | bytes]"),),
                rationale=(
                    "update the Request.headers class annotation to use the "
                    "already imported Mapping type"
                ),
            ),
        ),
        action_family_reuse_evidence=(
            {
                "action_kind": "type_annotation_update",
                "reusable_parameters": ["target_file", "class_name", "annotations"],
                "evidence": (
                    "extends the MAT-010 class annotation family from insert-only "
                    "annotations to updates of existing annotations"
                ),
            },
            {
                "action_kind": "type_alias_update",
                "reusable_parameters": ["target_file", "alias_name", "value"],
                "evidence": (
                    "generalizes typed-builder changes to TypeAlias value "
                    "updates without a requests-specific action"
                ),
            },
            {
                "action_kind": "import_member_remove",
                "reusable_parameters": [
                    "target_file",
                    "module",
                    "names",
                    "type_checking_only",
                ],
                "evidence": (
                    "removes stale typing imports by module/name parameters "
                    "rather than by PR-specific source replacement"
                ),
            },
        ),
    )


def build_click_sentinel_parser_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_CLICK_3396_BASE_REF,
    accepted_head_ref: str = DEFAULT_CLICK_3396_HEAD_REF,
    validation_command: str = DEFAULT_CLICK_3396_VALIDATION_COMMAND,
) -> HeldoutTypedBuilderSpec:
    """Build the held-out click#3396 sentinel/parser typing candidate spec."""

    _repo_file(repo_path, CLICK_INTERNAL_UTILS_PATH)
    _repo_file(repo_path, CLICK_CORE_PATH)
    _repo_file(repo_path, CLICK_PARSER_PATH)
    return HeldoutTypedBuilderSpec(
        candidate_id="mat-012-click-sentinel-parser-typing",
        repo_id="pallets/click",
        repo_url="https://github.com/pallets/click",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/pallets/click/pull/3396",
        prompt=(
            "Fix sentinel typing and parser annotations without introducing "
            "a click#3396-specific source patch."
        ),
        target_file=CLICK_PARSER_PATH,
        validation_command=validation_command,
        allowed_write_paths=(
            CLICK_INTERNAL_UTILS_PATH,
            CLICK_CORE_PATH,
            CLICK_PARSER_PATH,
        ),
        typed_actions=(
            AssignmentAnnotationUpdateAction(
                target_file=CLICK_INTERNAL_UTILS_PATH,
                assignment_name="UNSET",
                annotation="t.Literal[Sentinel.UNSET]",
                value="Sentinel.UNSET",
                rationale="type the UNSET sentinel binding as its literal enum value",
            ),
            AssignmentAnnotationUpdateAction(
                target_file=CLICK_INTERNAL_UTILS_PATH,
                assignment_name="FLAG_NEEDS_VALUE",
                annotation="t.Literal[Sentinel.FLAG_NEEDS_VALUE]",
                value="Sentinel.FLAG_NEEDS_VALUE",
                rationale=(
                    "type the FLAG_NEEDS_VALUE sentinel binding as its literal "
                    "enum value"
                ),
            ),
            AssignmentAnnotationUpdateAction(
                target_file=CLICK_INTERNAL_UTILS_PATH,
                assignment_name="T_UNSET",
                annotation="t.TypeAlias",
                value="t.Literal[Sentinel.UNSET]",
                rationale="convert the sentinel helper to an explicit TypeAlias",
            ),
            AssignmentAnnotationUpdateAction(
                target_file=CLICK_INTERNAL_UTILS_PATH,
                assignment_name="T_FLAG_NEEDS_VALUE",
                annotation="t.TypeAlias",
                value="t.Literal[Sentinel.FLAG_NEEDS_VALUE]",
                rationale="convert the flag sentinel helper to an explicit TypeAlias",
            ),
            BooleanConditionInsertAction(
                target_file=CLICK_CORE_PATH,
                class_name="Option",
                function_name="consume_value",
                anchor_condition="value is not UNSET",
                condition="isinstance(value, cabc.Iterable)",
                rationale=(
                    "guard iteration over parser values after UNSET is no "
                    "longer typed as None"
                ),
            ),
            FunctionSignatureUpdateAction(
                target_file=CLICK_PARSER_PATH,
                function_name="_unpack_args",
                return_annotation=(
                    "tuple[cabc.Sequence[str | cabc.Sequence[str | T_UNSET] | "
                    "T_UNSET], list[str]]"
                ),
                rationale="propagate sentinel aliases into unpacked parser output",
            ),
            FunctionSignatureUpdateAction(
                target_file=CLICK_PARSER_PATH,
                parent_function_name="_unpack_args",
                function_name="_fetch",
                parameter_annotations=(("c", "deque[str]"),),
                return_annotation="str | T_UNSET",
                rationale="narrow the nested fetch helper to argument strings",
            ),
            StatementBlockReplaceAction(
                target_file=CLICK_PARSER_PATH,
                function_name="_unpack_args",
                old_block="""
                    nargs = _fetch(nargs_spec)

                    if nargs is None:
                        continue
                """,
                new_block="""
                    if spos is None:
                        nargs = nargs_spec.popleft()
                    else:
                        nargs = nargs_spec.pop()
                """,
                rationale=(
                    "avoid routing integer nargs values through the sentinel "
                    "fetch helper"
                ),
            ),
            StatementBlockReplaceAction(
                target_file=CLICK_PARSER_PATH,
                function_name="_unpack_args",
                old_block="rv.append(_fetch(args))  # type: ignore[arg-type]",
                new_block="rv.append(_fetch(args))",
                rationale="remove the obsolete arg-type ignore after helper narrowing",
            ),
            AssignmentAnnotationUpdateAction(
                target_file=CLICK_PARSER_PATH,
                function_name="_unpack_args",
                assignment_name="x",
                annotation="list[str | T_UNSET]",
                rationale="record the sentinel-aware temporary list type",
            ),
            FunctionSignatureUpdateAction(
                target_file=CLICK_PARSER_PATH,
                class_name="_Argument",
                function_name="process",
                parameter_annotations=(
                    (
                        "value",
                        "str | cabc.Sequence[str | T_UNSET] | T_UNSET",
                    ),
                ),
                rationale="remove None from argument parser value typing",
            ),
            StatementBlockReplaceAction(
                target_file=CLICK_PARSER_PATH,
                class_name="_Argument",
                function_name="process",
                old_block="holes = sum(1 for x in value if x is UNSET)",
                new_block="holes = sum(x is UNSET for x in value)",
                rationale="count sentinel holes with a boolean generator",
            ),
            FunctionSignatureUpdateAction(
                target_file=CLICK_PARSER_PATH,
                class_name="_OptionParser",
                function_name="_get_value_from_state",
                return_annotation=(
                    "str | cabc.Sequence[str] | T_UNSET | T_FLAG_NEEDS_VALUE"
                ),
                rationale="include UNSET in option parser value returns",
            ),
            AssignmentAnnotationUpdateAction(
                target_file=CLICK_PARSER_PATH,
                class_name="_OptionParser",
                function_name="_get_value_from_state",
                assignment_name="value",
                annotation="str | cabc.Sequence[str] | T_UNSET | T_FLAG_NEEDS_VALUE",
                rationale="include UNSET in the local option value type",
            ),
        ),
        action_family_reuse_evidence=(
            {
                "action_kind": "assignment_annotation_update",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "function_name",
                    "assignment_name",
                    "annotation",
                    "value",
                ],
                "evidence": (
                    "extends typed-builder coverage from TypeAlias-only edits "
                    "to module and local assignment annotations without a "
                    "click-specific action"
                ),
            },
            {
                "action_kind": "function_signature_update",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "parent_function_name",
                    "function_name",
                    "parameter_annotations",
                    "return_annotation",
                ],
                "evidence": (
                    "updates top-level, nested, and method signatures by AST "
                    "scope and annotation text"
                ),
            },
            {
                "action_kind": "boolean_condition_insert",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "function_name",
                    "anchor_condition",
                    "condition",
                    "position",
                ],
                "evidence": (
                    "adds a parsed conjunct inside an existing boolean chain "
                    "using an anchor condition"
                ),
            },
            {
                "action_kind": "statement_block_replace",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "parent_function_name",
                    "function_name",
                    "old_block",
                    "new_block",
                ],
                "evidence": (
                    "bounded exact-block replacement is constrained by line "
                    "budgets, a unique old-block match, and AST parse checks; "
                    "this is a general AST action family but broader than the "
                    "MAT-010/MAT-011 pure typing actions"
                ),
            },
        ),
    )


def build_requests_response_reason_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_REQUESTS_7437_BASE_REF,
    accepted_head_ref: str = DEFAULT_REQUESTS_7437_HEAD_REF,
    validation_command: str = DEFAULT_REQUESTS_7437_VALIDATION_COMMAND,
) -> HeldoutTypedBuilderSpec:
    """Build the held-out requests#7437 Response.reason typing candidate spec."""

    _repo_file(repo_path, REQUESTS_MODELS_PATH)
    return HeldoutTypedBuilderSpec(
        candidate_id="mat-014-requests-response-reason-typing",
        repo_id="psf/requests",
        repo_url="https://github.com/psf/requests",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/psf/requests/pull/7437",
        prompt=(
            "Tighten Response.reason typing while placing the accepted "
            "assignment type-ignore without a statement-block replacement."
        ),
        target_file=REQUESTS_MODELS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(REQUESTS_MODELS_PATH,),
        typed_actions=(
            TypeAnnotationUpdateAction(
                target_file=REQUESTS_MODELS_PATH,
                class_name="Response",
                annotations=(("reason", "str"),),
                rationale="update the class-scope Response.reason annotation",
            ),
            AssignmentTypeIgnoreUpdateAction(
                target_file=REQUESTS_MODELS_PATH,
                class_name="Response",
                function_name="__init__",
                assignment_name="self.reason",
                type_ignore_codes=("assignment",),
                rationale=(
                    "place the accepted assignment type-ignore on the "
                    "constructor initialization of Response.reason"
                ),
            ),
        ),
        action_family_reuse_evidence=(
            {
                "action_kind": "type_annotation_update",
                "reusable_parameters": ["target_file", "class_name", "annotations"],
                "evidence": (
                    "reuses the MAT-010/MAT-011 class annotation updater for "
                    "an existing Response attribute annotation"
                ),
            },
            {
                "action_kind": "assignment_type_ignore_update",
                "reusable_parameters": [
                    "target_file",
                    "class_name",
                    "function_name",
                    "assignment_name",
                    "type_ignore_codes",
                ],
                "evidence": (
                    "places a typed assignment-level ignore by scoped AST "
                    "target and ignore code, avoiding statement_block_replace"
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

    action_paths = tuple(dict.fromkeys(action.target_file for action in spec.typed_actions))
    if not action_paths:
        action_paths = (spec.target_file,)
    before_sources = {
        path: _repo_file(repo, path).read_text(encoding="utf-8")
        for path in action_paths
    }
    hashes_before = _file_hashes(repo, spec.allowed_write_paths)
    action_results: list[TypedActionResult] = []
    current_sources = dict(before_sources)

    if not blockers:
        for action in spec.typed_actions:
            current_source = current_sources[action.target_file]
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
            current_sources[action.target_file] = next_source

    if write and not blockers:
        for path, before_source in before_sources.items():
            current_source = current_sources[path]
            if current_source != before_source:
                _repo_file(repo, path).write_text(current_source, encoding="utf-8")

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

    primary_file = spec.target_file if spec.target_file in before_sources else action_paths[0]
    primary_before = before_sources[primary_file]
    primary_after = current_sources[primary_file]
    file_candidate_after = {
        path: _file_candidate_after_record(
            before_sources[path],
            current_sources[path],
            path,
            wrote_file=bool(
                write and not blockers and before_sources[path] != current_sources[path]
            ),
        )
        for path in action_paths
    }
    candidate_after = {
        "target_file": file_candidate_after[primary_file],
        "files": file_candidate_after,
        "action_results": [result.to_record() for result in action_results],
        "candidate_diff": candidate_diff,
        "candidate_diff_summary": _diff_summary(candidate_diff),
        "candidate_changed_files": changed_files,
        "file_hashes_before": hashes_before,
        "file_hashes_after": hashes_after,
    }
    mutation_scope = {
        "mode": (
            "heldout_typed_builder_one_file"
            if len(spec.allowed_write_paths) == 1
            else "heldout_typed_builder_multi_file"
        ),
        "allowed_write_paths": list(spec.allowed_write_paths),
        "planned_write_files": list(action_paths),
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

    typed_builder_layer_judgment = _typed_builder_layer_judgment(spec.typed_actions)

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
        typed_builder_layer_judgment=typed_builder_layer_judgment,
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
        f"- Typed-builder layer: "
        f"`{candidate.typed_builder_layer_judgment.get('layer')}`",
        f"- Stays pure typed-builder: "
        f"`{candidate.typed_builder_layer_judgment.get('stays_pure_typed_builder_layer')}`",
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


def _typed_builder_layer_judgment(actions: Sequence[TypedAction]) -> dict[str, object]:
    action_kinds = [action.kind for action in actions]
    uses_statement_block_replace = "statement_block_replace" in action_kinds
    return {
        "schema_version": "typed-builder-layer-judgment-v1",
        "layer": (
            "general_ast_typed_builder"
            if uses_statement_block_replace
            else "pure_typed_builder"
        ),
        "stays_pure_typed_builder_layer": not uses_statement_block_replace,
        "uses_statement_block_replace": uses_statement_block_replace,
        "action_kinds": action_kinds,
    }


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
    if isinstance(action, TypeAliasUpdateAction):
        return _ensure_type_alias_value(
            source,
            target_file=action.target_file,
            alias_name=action.alias_name,
            value=action.value,
        )
    if isinstance(action, ImportMemberRemoveAction):
        return _remove_import_members(
            source,
            target_file=action.target_file,
            module=action.module,
            names=action.names,
            type_checking_only=action.type_checking_only,
        )
    if isinstance(action, AssignmentAnnotationUpdateAction):
        return _ensure_assignment_annotation(
            source,
            target_file=action.target_file,
            assignment_name=action.assignment_name,
            annotation=action.annotation,
            value=action.value,
            class_name=action.class_name,
            function_name=action.function_name,
        )
    if isinstance(action, AssignmentTypeIgnoreUpdateAction):
        return _ensure_assignment_type_ignore(
            source,
            target_file=action.target_file,
            assignment_name=action.assignment_name,
            type_ignore_codes=action.type_ignore_codes,
            class_name=action.class_name,
            function_name=action.function_name,
        )
    if isinstance(action, FunctionSignatureUpdateAction):
        return _ensure_function_signature(
            source,
            target_file=action.target_file,
            class_name=action.class_name,
            parent_function_name=action.parent_function_name,
            function_name=action.function_name,
            parameter_annotations=action.parameter_annotations,
            return_annotation=action.return_annotation,
        )
    if isinstance(action, BooleanConditionInsertAction):
        return _insert_boolean_condition(
            source,
            target_file=action.target_file,
            class_name=action.class_name,
            function_name=action.function_name,
            anchor_condition=action.anchor_condition,
            condition=action.condition,
            position=action.position,
        )
    if isinstance(action, StatementBlockReplaceAction):
        return _replace_statement_block(
            source,
            target_file=action.target_file,
            class_name=action.class_name,
            parent_function_name=action.parent_function_name,
            function_name=action.function_name,
            old_block=action.old_block,
            new_block=action.new_block,
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

    existing = _class_scope_annotation_nodes(class_node)
    lines = source.splitlines(keepends=True)
    patched_lines = list(lines)
    for name, annotation in annotations:
        node = existing.get(name)
        if node is None:
            continue
        current = ast.unparse(node.annotation)
        if current == annotation:
            continue
        if node.end_lineno != node.lineno:
            raise HeldoutTypedBuilderCandidateError(
                f"multi-line annotation update is not supported: {class_name}.{name}",
                blocker={
                    "field": "typed_builder",
                    "reason": "type_annotation_update_blocked",
                    "message": (
                        "multi-line annotation update is not supported: "
                        f"{class_name}.{name}"
                    ),
                },
            )
        replacement = _replace_class_annotation_line(
            patched_lines[node.lineno - 1],
            name=name,
            annotation=annotation,
        )
        if replacement is None:
            raise HeldoutTypedBuilderCandidateError(
                f"could not update annotation for {class_name}.{name}",
                blocker={
                    "field": "typed_builder",
                    "reason": "type_annotation_update_blocked",
                    "message": f"could not update annotation for {class_name}.{name}",
                },
            )
        patched_lines[node.lineno - 1] = replacement

    source = "".join(patched_lines)
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    class_node = _find_class(tree, class_name)
    if class_node is None:
        raise HeldoutTypedBuilderCandidateError(
            f"class not found after annotation update: {class_name}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"class not found after annotation update: {class_name}",
            },
        )
    existing = _class_scope_annotation_nodes(class_node)
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


def _ensure_type_alias_value(
    source: str,
    *,
    target_file: str,
    alias_name: str,
    value: str,
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    alias_node = _find_type_alias_assignment(tree, alias_name)
    if alias_node is None:
        raise HeldoutTypedBuilderCandidateError(
            f"type alias not found: {alias_name}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"type alias not found: {alias_name}",
            },
        )
    if alias_node.value is not None and ast.unparse(alias_node.value) == value:
        return source
    if alias_node.value is None or alias_node.end_lineno != alias_node.lineno:
        raise HeldoutTypedBuilderCandidateError(
            f"could not update type alias: {alias_name}",
            blocker={
                "field": "typed_builder",
                "reason": "type_alias_update_blocked",
                "message": f"could not update type alias: {alias_name}",
            },
        )

    lines = source.splitlines(keepends=True)
    line = lines[alias_node.lineno - 1]
    pattern = rf"^(?P<prefix>\s*{re.escape(alias_name)}\s*:\s*TypeAlias\s*=\s*).*(?P<newline>\n?)$"
    match = re.match(pattern, line)
    if match is None:
        raise HeldoutTypedBuilderCandidateError(
            f"could not update type alias line: {alias_name}",
            blocker={
                "field": "typed_builder",
                "reason": "type_alias_update_blocked",
                "message": f"could not update type alias line: {alias_name}",
            },
        )
    lines[alias_node.lineno - 1] = f"{match.group('prefix')}{value}{match.group('newline')}"
    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _remove_import_members(
    source: str,
    *,
    target_file: str,
    module: str,
    names: Sequence[str],
    type_checking_only: bool,
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    import_node = _find_import_from(
        tree,
        module=module,
        names=set(names),
        type_checking_only=type_checking_only,
    )
    if import_node is None:
        return source
    if import_node.end_lineno != import_node.lineno:
        raise HeldoutTypedBuilderCandidateError(
            f"multi-line import removal is not supported: {module}",
            blocker={
                "field": "typed_builder",
                "reason": "import_member_remove_blocked",
                "message": f"multi-line import removal is not supported: {module}",
            },
        )

    remove_names = set(names)
    remaining = [
        alias
        for alias in import_node.names
        if alias.name not in remove_names and (alias.asname or alias.name) not in remove_names
    ]
    lines = source.splitlines(keepends=True)
    original = lines[import_node.lineno - 1]
    newline = "\n" if original.endswith("\n") else ""
    if remaining:
        indent = original[: len(original) - len(original.lstrip())]
        imports = ", ".join(
            alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"
            for alias in remaining
        )
        lines[import_node.lineno - 1] = f"{indent}from {module} import {imports}{newline}"
    else:
        lines[import_node.lineno - 1] = ""
    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _ensure_assignment_annotation(
    source: str,
    *,
    target_file: str,
    assignment_name: str,
    annotation: str,
    value: str | None,
    class_name: str | None,
    function_name: str | None,
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    assignment = _find_assignment(
        tree,
        assignment_name=assignment_name,
        class_name=class_name,
        function_name=function_name,
    )
    if assignment is None:
        raise HeldoutTypedBuilderCandidateError(
            f"assignment not found: {assignment_name}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"assignment not found: {assignment_name}",
            },
        )
    if assignment.end_lineno != assignment.lineno:
        raise HeldoutTypedBuilderCandidateError(
            f"multi-line assignment update is not supported: {assignment_name}",
            blocker={
                "field": "typed_builder",
                "reason": "assignment_annotation_update_blocked",
                "message": (
                    "multi-line assignment update is not supported: "
                    f"{assignment_name}"
                ),
            },
        )

    existing_value = _assignment_value(assignment)
    next_value = value if value is not None else existing_value
    if next_value is None:
        replacement = f"{assignment_name}: {annotation}"
    else:
        replacement = f"{assignment_name}: {annotation} = {next_value}"

    lines = source.splitlines(keepends=True)
    original = lines[assignment.lineno - 1]
    current = original.strip()
    if current == replacement:
        return source
    indent = original[: len(original) - len(original.lstrip())]
    newline = "\n" if original.endswith("\n") else ""
    lines[assignment.lineno - 1] = f"{indent}{replacement}{newline}"
    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _ensure_assignment_type_ignore(
    source: str,
    *,
    target_file: str,
    assignment_name: str,
    type_ignore_codes: Sequence[str],
    class_name: str | None,
    function_name: str,
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    function = _find_scoped_function(
        tree,
        class_name=class_name,
        parent_function_name=None,
        function_name=function_name,
    )
    if function is None or function.end_lineno is None:
        target = _function_target_label(class_name, None, function_name)
        raise HeldoutTypedBuilderCandidateError(
            f"function not found: {target}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"function not found: {target}",
            },
        )

    matches = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assign | ast.AnnAssign)
        and _assignment_target_name(node) == assignment_name
    ]
    if len(matches) != 1:
        raise HeldoutTypedBuilderCandidateError(
            f"assignment target match count was {len(matches)}: {assignment_name}",
            blocker={
                "field": "typed_builder",
                "reason": "assignment_type_ignore_update_blocked",
                "message": (
                    "assignment target must match exactly once in function: "
                    f"{assignment_name}"
                ),
            },
        )
    assignment = matches[0]
    if assignment.end_lineno != assignment.lineno:
        raise HeldoutTypedBuilderCandidateError(
            f"multi-line assignment type-ignore update is not supported: {assignment_name}",
            blocker={
                "field": "typed_builder",
                "reason": "assignment_type_ignore_update_blocked",
                "message": (
                    "multi-line assignment type-ignore update is not supported: "
                    f"{assignment_name}"
                ),
            },
        )

    lines = source.splitlines(keepends=True)
    original = lines[assignment.lineno - 1]
    updated = _append_or_replace_type_ignore(
        original,
        type_ignore_codes=type_ignore_codes,
    )
    if updated == original:
        return source
    lines[assignment.lineno - 1] = updated
    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _ensure_function_signature(
    source: str,
    *,
    target_file: str,
    class_name: str | None,
    parent_function_name: str | None,
    function_name: str,
    parameter_annotations: Sequence[tuple[str, str]],
    return_annotation: str | None,
) -> str:
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    function = _find_scoped_function(
        tree,
        class_name=class_name,
        parent_function_name=parent_function_name,
        function_name=function_name,
    )
    if function is None:
        target = _function_target_label(class_name, parent_function_name, function_name)
        raise HeldoutTypedBuilderCandidateError(
            f"function not found: {target}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"function not found: {target}",
            },
        )

    lines = source.splitlines(keepends=True)
    signature_end_lineno = _function_signature_end_lineno(function)
    start_index = function.lineno - 1
    end_index = signature_end_lineno - 1

    for parameter_name, parameter_annotation in parameter_annotations:
        if _function_parameter_annotation(function, parameter_name) == parameter_annotation:
            continue
        updated = _replace_parameter_annotation_in_signature(
            lines,
            start_index=start_index,
            end_index=end_index,
            parameter_name=parameter_name,
            annotation=parameter_annotation,
        )
        if not updated:
            raise HeldoutTypedBuilderCandidateError(
                f"could not update parameter annotation: {parameter_name}",
                blocker={
                    "field": "typed_builder",
                    "reason": "function_signature_update_blocked",
                    "message": (
                        "could not update parameter annotation: "
                        f"{function_name}.{parameter_name}"
                    ),
                },
            )

    if return_annotation is not None:
        current_return = (
            ast.unparse(function.returns) if function.returns is not None else None
        )
        if current_return != return_annotation:
            updated = _replace_return_annotation_in_signature(
                lines,
                signature_end_index=end_index,
                return_annotation=return_annotation,
            )
            if not updated:
                raise HeldoutTypedBuilderCandidateError(
                    f"could not update return annotation for {function_name}",
                    blocker={
                        "field": "typed_builder",
                        "reason": "function_signature_update_blocked",
                        "message": (
                            "could not update return annotation for "
                            f"{function_name}"
                        ),
                    },
                )

    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _insert_boolean_condition(
    source: str,
    *,
    target_file: str,
    class_name: str | None,
    function_name: str,
    anchor_condition: str,
    condition: str,
    position: str,
) -> str:
    _parse_expression(anchor_condition, target_file=target_file)
    _parse_expression(condition, target_file=target_file)
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    function = _find_scoped_function(
        tree,
        class_name=class_name,
        parent_function_name=None,
        function_name=function_name,
    )
    if function is None or function.end_lineno is None:
        target = _function_target_label(class_name, None, function_name)
        raise HeldoutTypedBuilderCandidateError(
            f"function not found: {target}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"function not found: {target}",
            },
        )

    lines = source.splitlines(keepends=True)
    anchor_line = f"and {anchor_condition}"
    condition_line = f"and {condition}"
    matches = []
    for index in range(function.lineno - 1, function.end_lineno):
        stripped = lines[index].strip()
        if stripped == condition_line:
            return source
        if stripped == anchor_line:
            matches.append(index)
    if len(matches) != 1:
        raise HeldoutTypedBuilderCandidateError(
            f"boolean anchor match count was {len(matches)}: {anchor_condition}",
            blocker={
                "field": "typed_builder",
                "reason": "boolean_condition_insert_blocked",
                "message": (
                    "boolean anchor must match exactly once in function: "
                    f"{anchor_condition}"
                ),
            },
        )

    anchor_index = matches[0]
    indent = lines[anchor_index][: len(lines[anchor_index]) - len(lines[anchor_index].lstrip())]
    insert_index = anchor_index if position == "before" else anchor_index + 1
    lines.insert(insert_index, f"{indent}{condition_line}\n")
    patched = "".join(lines)
    _parse_python(patched, filename=target_file, field="typed_builder")
    return patched


def _replace_statement_block(
    source: str,
    *,
    target_file: str,
    class_name: str | None,
    parent_function_name: str | None,
    function_name: str,
    old_block: str,
    new_block: str,
) -> str:
    _parse_statement_block(old_block, target_file=target_file)
    _parse_statement_block(new_block, target_file=target_file)
    tree = _parse_python(source, filename=target_file, field="typed_builder")
    function = _find_scoped_function(
        tree,
        class_name=class_name,
        parent_function_name=parent_function_name,
        function_name=function_name,
    )
    if function is None or function.end_lineno is None:
        target = _function_target_label(class_name, parent_function_name, function_name)
        raise HeldoutTypedBuilderCandidateError(
            f"function not found: {target}",
            blocker={
                "field": "typed_builder",
                "reason": "typed_target_not_found",
                "message": f"function not found: {target}",
            },
        )

    old_lines = _normalized_block_lines(old_block)
    new_lines = _normalized_block_lines(new_block)
    lines = source.splitlines(keepends=True)
    matches: list[tuple[int, str]] = []
    for start in range(function.lineno - 1, function.end_lineno - len(old_lines) + 1):
        first_line = lines[start]
        base_indent = first_line[: len(first_line) - len(first_line.lstrip())]
        if _block_matches_at(lines, start=start, base_indent=base_indent, block_lines=old_lines):
            matches.append((start, base_indent))
    if len(matches) != 1:
        raise HeldoutTypedBuilderCandidateError(
            f"statement block match count was {len(matches)}",
            blocker={
                "field": "typed_builder",
                "reason": "statement_block_replace_blocked",
                "message": "old statement block must match exactly once",
            },
        )

    start, base_indent = matches[0]
    replacement = [
        "\n" if line == "" else f"{base_indent}{line}\n"
        for line in new_lines
    ]
    patched = "".join(
        lines[:start] + replacement + lines[start + len(old_lines) :]
    )
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


def _file_candidate_after_record(
    before: str,
    after: str,
    target_file: str,
    *,
    wrote_file: bool,
) -> dict[str, object]:
    diff = _unified_diff(before, after, target_file)
    ast_delta = python_ast_delta_metadata(before, after)
    return {
        "schema_version": "typed-builder-file-candidate-after-v1",
        "target_file": target_file,
        "wrote_file": wrote_file,
        "candidate_after": {
            "diff": diff,
            "diff_summary": _diff_summary(diff),
            "ast_delta": ast_delta,
            "ast_parse_ok": ast_delta.get("ast_parse_ok") is True,
            "sha256_before": _sha256_text(before),
            "sha256_after": _sha256_text(after),
        },
    }


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


def _find_scoped_function(
    tree: ast.Module,
    *,
    class_name: str | None,
    parent_function_name: str | None,
    function_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parent = _find_function_or_method(tree, class_name, parent_function_name)
    if parent_function_name is not None:
        if parent is None:
            return None
        for node in parent.body:
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == function_name
            ):
                return node
        return None
    return _find_function_or_method(tree, class_name, function_name)


def _function_target_label(
    class_name: str | None,
    parent_function_name: str | None,
    function_name: str,
) -> str:
    parts = [part for part in (class_name, parent_function_name, function_name) if part]
    return ".".join(parts)


def _function_signature_end_lineno(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    if function.body:
        return function.body[0].lineno - 1
    return function.end_lineno or function.lineno


def _function_parameter_annotation(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    parameter_name: str,
) -> str | None:
    args = (
        list(function.args.posonlyargs)
        + list(function.args.args)
        + list(function.args.kwonlyargs)
    )
    if function.args.vararg is not None:
        args.append(function.args.vararg)
    if function.args.kwarg is not None:
        args.append(function.args.kwarg)
    for arg in args:
        if arg.arg == parameter_name:
            return ast.unparse(arg.annotation) if arg.annotation is not None else None
    return None


def _replace_parameter_annotation_in_signature(
    lines: list[str],
    *,
    start_index: int,
    end_index: int,
    parameter_name: str,
    annotation: str,
) -> bool:
    pattern = re.compile(
        rf"(?P<prefix>\b{re.escape(parameter_name)}\s*:\s*)"
        rf"(?P<annotation>[^,\)\n]+)"
        rf"(?P<suffix>[,\)])"
    )
    for index in range(start_index, end_index + 1):
        line = lines[index]

        def replace(match: re.Match[str]) -> str:
            return (
                f"{match.group('prefix')}{annotation}{match.group('suffix')}"
            )

        replaced, count = pattern.subn(replace, line, count=1)
        if count:
            lines[index] = replaced
            return True
    return False


def _replace_return_annotation_in_signature(
    lines: list[str],
    *,
    signature_end_index: int,
    return_annotation: str,
) -> bool:
    line = lines[signature_end_index]
    if "->" in line:
        replaced, count = re.subn(
            r"\)\s*->\s*[^:]+:",
            f") -> {return_annotation}:",
            line,
            count=1,
        )
    else:
        replaced, count = re.subn(
            r"\)\s*:",
            f") -> {return_annotation}:",
            line,
            count=1,
        )
    if count:
        lines[signature_end_index] = replaced
        return True
    return False


def _find_assignment(
    tree: ast.Module,
    *,
    assignment_name: str,
    class_name: str | None,
    function_name: str | None,
) -> ast.Assign | ast.AnnAssign | None:
    if function_name is not None:
        function = _find_function_or_method(tree, class_name, function_name)
        nodes: Sequence[ast.AST] = list(ast.walk(function)) if function is not None else ()
    elif class_name is not None:
        class_node = _find_class(tree, class_name)
        nodes = class_node.body if class_node is not None else ()
    else:
        nodes = tree.body

    for node in nodes:
        if isinstance(node, ast.AnnAssign) and _assignment_target_name(node) == assignment_name:
            return node
        if isinstance(node, ast.Assign) and _assignment_target_name(node) == assignment_name:
            return node
    return None


def _assignment_target_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    if isinstance(node, ast.AnnAssign):
        return _assignment_target_label(node.target)
    if len(node.targets) != 1:
        return None
    return _assignment_target_label(node.targets[0])


def _assignment_target_label(target: ast.expr) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return ast.unparse(target)
    return None


def _assignment_value(node: ast.Assign | ast.AnnAssign) -> str | None:
    value = node.value
    return ast.unparse(value) if value is not None else None


def _append_or_replace_type_ignore(
    line: str,
    *,
    type_ignore_codes: Sequence[str],
) -> str:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    type_ignore = f"# type: ignore[{', '.join(type_ignore_codes)}]"
    if type_ignore in body:
        return line
    if "# type: ignore" in body:
        body = re.sub(r"# type: ignore(?:\[[^\]]+\])?", type_ignore, body, count=1)
    else:
        body = f"{body.rstrip()}  {type_ignore}"
    return f"{body}{newline}"


def _class_scope_annotation_names(class_node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for node in class_node.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _class_scope_annotation_nodes(class_node: ast.ClassDef) -> dict[str, ast.AnnAssign]:
    nodes: dict[str, ast.AnnAssign] = {}
    for node in class_node.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nodes[node.target.id] = node
    return nodes


def _replace_class_annotation_line(
    line: str,
    *,
    name: str,
    annotation: str,
) -> str | None:
    pattern = rf"^(?P<indent>\s*){re.escape(name)}\s*:\s*[^=\n#]+(?P<tail>[ \t]*(?:=.*)?(?:#.*)?)(?P<newline>\n?)$"
    match = re.match(pattern, line)
    if match is None:
        return None
    tail = match.group("tail").rstrip()
    if tail and not tail.startswith((" ", "\t", "#", "=")):
        tail = f" {tail}"
    return f"{match.group('indent')}{name}: {annotation}{tail}{match.group('newline')}"


def _find_type_alias_assignment(tree: ast.Module, alias_name: str) -> ast.AnnAssign | None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == alias_name
            and ast.unparse(node.annotation) == "TypeAlias"
        ):
            return node
    return None


def _find_import_from(
    tree: ast.Module,
    *,
    module: str,
    names: set[str],
    type_checking_only: bool,
) -> ast.ImportFrom | None:
    nodes = (
        _iter_type_checking_nodes(tree.body)
        if type_checking_only
        else ast.walk(tree)
    )
    for node in nodes:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != module:
            continue
        imported = {alias.name for alias in node.names} | {
            alias.asname for alias in node.names if alias.asname is not None
        }
        if imported & names:
            return node
    return None


def _iter_type_checking_nodes(nodes: Sequence[ast.stmt]) -> Sequence[ast.AST]:
    found: list[ast.AST] = []
    for node in nodes:
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            for child in node.body:
                found.extend(ast.walk(child))
        for child in ast.iter_child_nodes(node):
            child_body = getattr(child, "body", None)
            if isinstance(child_body, list):
                found.extend(_iter_type_checking_nodes(child_body))
    return found


def _is_type_checking_test(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "TYPE_CHECKING"


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


def _parse_expression(expression: str, *, target_file: str) -> ast.Expression:
    try:
        return ast.parse(expression, filename=target_file, mode="eval")
    except SyntaxError as error:
        raise HeldoutTypedBuilderCandidateError(
            f"invalid Python expression in {target_file}: {error}",
            blocker={
                "field": "typed_builder",
                "reason": "python_ast_parse_failed",
                "message": str(error),
            },
        ) from error


def _parse_statement_block(block: str, *, target_file: str) -> ast.Module:
    lines = _normalized_block_lines(block)
    body = "\n".join(f"        {line}" if line else "" for line in lines)
    wrapped = f"def _j3_block_probe():\n    while True:\n{body}\n"
    return _parse_python(wrapped, filename=target_file, field="typed_builder")


def _normalized_block_lines(block: str) -> list[str]:
    return textwrap.dedent(block).strip("\n").splitlines()


def _block_matches_at(
    lines: Sequence[str],
    *,
    start: int,
    base_indent: str,
    block_lines: Sequence[str],
) -> bool:
    for offset, expected in enumerate(block_lines):
        actual = lines[start + offset].rstrip("\n")
        if expected == "":
            if actual.strip():
                return False
            continue
        if actual != f"{base_indent}{expected}":
            return False
    return True


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
    parser.add_argument(
        "--candidate",
        choices=("click-3422", "requests-7441", "click-3396", "requests-7437"),
        default="click-3422",
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

    if args.candidate == "click-3396":
        spec = build_click_sentinel_parser_spec(args.repo_path)
    elif args.candidate == "requests-7437":
        spec = build_requests_response_reason_spec(args.repo_path)
    elif args.candidate == "requests-7441":
        spec = build_requests_headers_mapping_spec(args.repo_path)
    else:
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
