"""Held-out source-region candidate materialization with reusable actions."""

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
from j3.source_region_materializer import (
    SourceRegionAction,
    SourceRegionActionKind,
    SourceRegionConstraints,
    SourceRegionMaterializationError,
    SourceRegionMaterializationResult,
    SourceRegionTarget,
    materialize_source_region,
)


HELDOUT_SOURCE_REGION_CANDIDATE_SCHEMA_VERSION = (
    "heldout-source-region-candidate-v1"
)
PYTEST_INSERTION_SCHEMA_VERSION = "repo-convention-pytest-insertion-v1"
TEXT_INSERTION_SCHEMA_VERSION = "bounded-text-insertion-v1"
DEFAULT_REQUESTS_BASE_REF = "b684dcb9bbf3aa557d1238e72062c4a29737dd1c"
DEFAULT_REQUESTS_STREAM_WRAPPER_BASE_REF = (
    "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
)
DEFAULT_REQUESTS_STREAM_WRAPPER_HEAD_REF = (
    "ea1c36c1b1a8364e234b6ad49ea05e3261636f8a"
)
DEFAULT_REQUESTS_REDIRECT_HISTORY_BASE_REF = (
    "cbce031327be4f1b4b5fd041ff4dcaa8efa2ce53"
)
DEFAULT_REQUESTS_REDIRECT_HISTORY_HEAD_REF = (
    "3ee28b806f8bc414b29f7b4561e53c161924fe66"
)
DEFAULT_CLICK_WRITE_USAGE_BASE_REF = (
    "7c99ebe23b931f27562d926814423cce85fd9766"
)
DEFAULT_CLICK_WRITE_USAGE_HEAD_REF = (
    "0551bf53588ae87f462d336f24f853a156fefe3a"
)
DEFAULT_CLICK_DEFAULT_MAP_SPLIT_BASE_REF = (
    "8bd8b4a074c55c03b6eb5666edc44a9c43df38a2"
)
DEFAULT_CLICK_DEFAULT_MAP_SPLIT_HEAD_REF = (
    "94004f1b5a4a982e8e33ef8d5f00cfb0e1dabddd"
)
DEFAULT_PYTEST_SCANNER_BASE_REF = "7df5d80ff3a98714a1d3cdbe82941229e511f4b3"
DEFAULT_VALIDATION_COMMAND = (
    "python -m pytest "
    "tests/test_utils.py::test_should_bypass_proxies_no_proxy_domain_boundary -q"
)
DEFAULT_REQUESTS_STREAM_WRAPPER_VALIDATION_COMMAND = (
    "python -m pytest "
    "tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q"
)
DEFAULT_REQUESTS_REDIRECT_HISTORY_VALIDATION_COMMAND = (
    "PYTHONPATH=src python -m pytest "
    "tests/test_requests.py::TestRequests::test_redirect_history_no_self_reference -q"
)
DEFAULT_CLICK_WRITE_USAGE_VALIDATION_COMMAND = (
    "PYTHONPATH=src python -m pytest "
    "tests/test_formatting.py::test_help_formatter_write_usage "
    "tests/test_formatting.py::test_help_formatter_write_usage_without_args_styled_prefix "
    "tests/test_formatting.py::test_command_write_usage_no_args -q"
)
DEFAULT_CLICK_DEFAULT_MAP_SPLIT_VALIDATION_COMMAND = (
    "PYTHONPATH=src python -m pytest "
    "tests/test_defaults.py::test_default_map_nargs -q"
)
DEFAULT_PYTEST_SCANNER_VALIDATION_COMMAND = (
    "PYTHONPATH=src python -c "
    "\"from _pytest.mark.expression import Expression; "
    "matcher=lambda name, **kwargs: "
    "name in {r'\\\\nfoo\\\\n', r'test\\\\case', 'mark'}; "
    "assert Expression.compile(r'\\\\nfoo\\\\n and mark(x=\\\"y\\\")').evaluate(matcher); "
    "assert Expression.compile(r'mark(x=\\\"y\\\") and \\\\nfoo\\\\n').evaluate(matcher); "
    "assert Expression.compile(r'test\\\\case and mark(x=\\\"y\\\")').evaluate(matcher)\""
)
REQUESTS_UTILS_PATH = "src/requests/utils.py"
REQUESTS_TEST_UTILS_PATH = "tests/test_utils.py"
REQUESTS_MODELS_PATH = "src/requests/models.py"
REQUESTS_SESSIONS_PATH = "src/requests/sessions.py"
REQUESTS_TEST_REQUESTS_PATH = "tests/test_requests.py"
CLICK_FORMATTING_PATH = "src/click/formatting.py"
CLICK_TEST_FORMATTING_PATH = "tests/test_formatting.py"
CLICK_CORE_PATH = "src/click/core.py"
CLICK_TEST_DEFAULTS_PATH = "tests/test_defaults.py"
CLICK_COMMANDS_DOC_PATH = "docs/commands.md"
CLICK_DOCS_CONF_PATH = "docs/conf.py"
CLICK_CHANGES_PATH = "CHANGES.rst"
PYTEST_EXPRESSION_PATH = "src/_pytest/mark/expression.py"
PYTEST_MARK_EXPRESSION_TEST_PATH = "testing/test_mark_expression.py"


class HeldoutSourceRegionCandidateError(ValueError):
    """Raised when a held-out source-region candidate cannot be built."""

    def __init__(self, message: str, *, blocker: dict[str, str]) -> None:
        super().__init__(message)
        self.blocker = blocker


@dataclass(frozen=True, slots=True)
class PytestInsertionAction:
    """Reusable repo-convention action for inserting a pytest function."""

    target_file: str
    anchor_function_name: str
    function_name: str
    insertion_source: str
    kind: str = "insert_pytest_function_after_anchor"
    schema_version: str = PYTEST_INSERTION_SCHEMA_VERSION
    max_added_lines: int = 40
    surrounding_blank_lines: int | None = None
    trailing_blank_lines: int | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if self.max_added_lines < 1:
            raise ValueError("max_added_lines must be >= 1")
        if (
            self.surrounding_blank_lines is not None
            and self.surrounding_blank_lines < 0
        ):
            raise ValueError("surrounding_blank_lines must be >= 0")
        if self.trailing_blank_lines is not None and self.trailing_blank_lines < 0:
            raise ValueError("trailing_blank_lines must be >= 0")
        if not self.anchor_function_name:
            raise ValueError("anchor_function_name is required")
        if not self.function_name:
            raise ValueError("function_name is required")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "anchor_function_name": self.anchor_function_name,
                "function_name": self.function_name,
                "position": "after_anchor_function",
            },
            "constraints": {
                "max_added_lines": self.max_added_lines,
                "must_parse_ast": True,
                "preserve_existing_imports": True,
                "surrounding_blank_lines": self.surrounding_blank_lines,
                "trailing_blank_lines": self.trailing_blank_lines,
            },
            "insertion_source": self.insertion_source,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class TextInsertionAction:
    """Reusable bounded text insertion for docs, changelogs, and config files."""

    target_file: str
    anchor_text: str
    insertion_source: str
    insert_once_contains: str
    position: str = "after_anchor"
    kind: str = "insert_text_around_anchor"
    schema_version: str = TEXT_INSERTION_SCHEMA_VERSION
    max_added_lines: int = 80
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if self.position not in {"after_anchor", "before_anchor"}:
            raise ValueError("position must be after_anchor or before_anchor")
        if not self.anchor_text:
            raise ValueError("anchor_text is required")
        if not self.insert_once_contains:
            raise ValueError("insert_once_contains is required")
        if self.max_added_lines < 1:
            raise ValueError("max_added_lines must be >= 1")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "position": self.position,
            },
            "constraints": {
                "max_added_lines": self.max_added_lines,
                "insert_once_contains": self.insert_once_contains,
            },
            "anchor_text": self.anchor_text,
            "insertion_source": self.insertion_source,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class HeldoutSourceRegionSpec:
    """Parameterized source/test candidate replay spec."""

    candidate_id: str
    repo_id: str
    repo_url: str
    repo_split: str
    base_ref: str
    reference_pr_url: str
    prompt: str
    source_file: str
    test_file: str
    validation_command: str
    allowed_write_paths: tuple[str, ...]
    source_action: SourceRegionAction
    test_action: PytestInsertionAction
    text_actions: tuple[TextInsertionAction, ...] = field(default_factory=tuple)
    action_family_reuse_evidence: tuple[dict[str, object], ...] = field(
        default_factory=tuple
    )
    accepted_head_ref: str | None = None

    def __post_init__(self) -> None:
        for path in (self.source_file, self.test_file, *self.allowed_write_paths):
            _validate_relative_path(path)
        for action in self.text_actions:
            _validate_relative_path(action.target_file)


@dataclass(frozen=True, slots=True)
class PytestInsertionResult:
    """Candidate-after metadata for a pytest insertion action."""

    status: str
    target_file: str
    function_name: str
    insertion_line: int | None
    added_line_count: int
    diff: str
    diff_summary: dict[str, object]
    ast_delta: dict[str, object]
    ast_parse_ok: bool
    sha256_before: str
    sha256_after: str
    patched_source: str = field(repr=False)
    wrote_file: bool = False

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "pytest-insertion-candidate-after-v1",
            "status": self.status,
            "target_file": self.target_file,
            "function_name": self.function_name,
            "insertion_line": self.insertion_line,
            "wrote_file": self.wrote_file,
            "candidate_after": {
                "added_line_count": self.added_line_count,
                "diff_summary": dict(self.diff_summary),
                "diff": self.diff,
                "ast_parse_ok": self.ast_parse_ok,
                "ast_delta": _json_copy(self.ast_delta),
                "sha256_before": self.sha256_before,
                "sha256_after": self.sha256_after,
            },
        }


@dataclass(frozen=True, slots=True)
class TextInsertionResult:
    """Candidate-after metadata for a bounded text insertion action."""

    status: str
    target_file: str
    insertion_line: int | None
    added_line_count: int
    diff: str
    diff_summary: dict[str, object]
    sha256_before: str
    sha256_after: str
    patched_source: str = field(repr=False)
    wrote_file: bool = False

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "bounded-text-insertion-candidate-after-v1",
            "status": self.status,
            "target_file": self.target_file,
            "insertion_line": self.insertion_line,
            "wrote_file": self.wrote_file,
            "candidate_after": {
                "added_line_count": self.added_line_count,
                "diff_summary": dict(self.diff_summary),
                "diff": self.diff,
                "sha256_before": self.sha256_before,
                "sha256_after": self.sha256_after,
            },
        }


@dataclass(frozen=True, slots=True)
class HeldoutSourceRegionCandidate:
    """Structured candidate record for a held-out source-region attempt."""

    candidate_id: str
    repo_id: str
    repo_url: str
    repo_split: str
    base_ref: str
    reference_pr_url: str
    accepted_head_ref: str | None
    prompt: str
    status: str
    action_records: list[dict[str, object]]
    action_family_reuse_evidence: list[dict[str, object]]
    target_source_file: str
    target_test_file: str
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
            "schema_version": HELDOUT_SOURCE_REGION_CANDIDATE_SCHEMA_VERSION,
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
            "target_source_file": self.target_source_file,
            "target_test_file": self.target_test_file,
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


def build_requests_no_proxy_domain_boundary_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_REQUESTS_BASE_REF,
    validation_command: str = DEFAULT_VALIDATION_COMMAND,
) -> HeldoutSourceRegionSpec:
    """Build the held-out no_proxy domain-boundary candidate spec."""

    source_text = _repo_file(repo_path, REQUESTS_UTILS_PATH).read_text(
        encoding="utf-8"
    )
    source_action = _no_proxy_domain_boundary_source_action(source_text)
    test_action = PytestInsertionAction(
        target_file=REQUESTS_TEST_UTILS_PATH,
        anchor_function_name="test_should_bypass_proxies_no_proxy",
        function_name="test_should_bypass_proxies_no_proxy_domain_boundary",
        insertion_source=_no_proxy_domain_boundary_test_source(),
        rationale=(
            "insert a focused pytest regression after the existing "
            "should_bypass_proxies no_proxy test"
        ),
    )
    return HeldoutSourceRegionSpec(
        candidate_id="mat-008-no-proxy-domain-boundary",
        repo_id="psf/requests",
        repo_url="https://github.com/psf/requests",
        repo_split="held_out",
        base_ref=base_ref,
        reference_pr_url="https://github.com/psf/requests/pull/7427",
        prompt=(
            "Fix no_proxy host matching so entries respect domain boundaries "
            "and exact host:port matches."
        ),
        source_file=REQUESTS_UTILS_PATH,
        test_file=REQUESTS_TEST_UTILS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(REQUESTS_UTILS_PATH, REQUESTS_TEST_UTILS_PATH),
        source_action=source_action,
        test_action=test_action,
        action_family_reuse_evidence=(
            {
                "action_kind": SourceRegionActionKind.REPLACE_FUNCTION_REGION.value,
                "reused_from": ["MAT-002", "MAT-003", "MAT-005", "MAT-006"],
                "evidence": (
                    "same bounded source-region action schema; target file, "
                    "symbol, line range, and replacement are parameters"
                ),
            },
            {
                "action_kind": "insert_pytest_function_after_anchor",
                "reused_from": ["GS7-008", "GS7-009", "DATA-014"],
                "evidence": (
                    "same repo-convention pytest insertion shape; target "
                    "test file, anchor function, and inserted function are parameters"
                ),
            },
        ),
    )


def build_pytest_mark_expression_scanner_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_PYTEST_SCANNER_BASE_REF,
    validation_command: str = DEFAULT_PYTEST_SCANNER_VALIDATION_COMMAND,
) -> HeldoutSourceRegionSpec:
    """Build the held-out pytest mark-expression scanner candidate spec."""

    source_text = _repo_file(repo_path, PYTEST_EXPRESSION_PATH).read_text(
        encoding="utf-8"
    )
    source_action = _mark_expression_scanner_source_action(source_text)
    test_action = PytestInsertionAction(
        target_file=PYTEST_MARK_EXPRESSION_TEST_PATH,
        anchor_function_name="test_backslash_not_treated_specially",
        function_name="test_backslash_in_identifier_with_string_literal",
        insertion_source=_mark_expression_scanner_test_source(),
        rationale=(
            "insert a focused regression after the existing mark expression "
            "backslash scanner test"
        ),
    )
    return HeldoutSourceRegionSpec(
        candidate_id="mat-009-pytest-mark-expression-scanner",
        repo_id="pytest-dev/pytest",
        repo_url="https://github.com/pytest-dev/pytest",
        repo_split="held_out",
        base_ref=base_ref,
        reference_pr_url="https://github.com/pytest-dev/pytest/pull/14475",
        prompt=(
            "Fix mark expression scanning so a backslash outside the current "
            "string literal does not reject expressions that also contain "
            "string literal arguments."
        ),
        source_file=PYTEST_EXPRESSION_PATH,
        test_file=PYTEST_MARK_EXPRESSION_TEST_PATH,
        validation_command=validation_command,
        allowed_write_paths=(PYTEST_EXPRESSION_PATH, PYTEST_MARK_EXPRESSION_TEST_PATH),
        source_action=source_action,
        test_action=test_action,
        action_family_reuse_evidence=(
            {
                "action_kind": SourceRegionActionKind.REPLACE_FUNCTION_REGION.value,
                "reused_from": ["MAT-008"],
                "evidence": (
                    "same bounded function-region action schema; target file, "
                    "method, line range, and replacement are parameters"
                ),
            },
            {
                "action_kind": "insert_pytest_function_after_anchor",
                "reused_from": ["MAT-008", "GS7-008", "GS7-009", "DATA-014"],
                "evidence": (
                    "same repo-convention pytest insertion shape; target "
                    "test file, anchor function, and inserted function are parameters"
                ),
            },
        ),
    )


def build_requests_stream_wrapper_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_REQUESTS_STREAM_WRAPPER_BASE_REF,
    accepted_head_ref: str = DEFAULT_REQUESTS_STREAM_WRAPPER_HEAD_REF,
    validation_command: str = DEFAULT_REQUESTS_STREAM_WRAPPER_VALIDATION_COMMAND,
) -> HeldoutSourceRegionSpec:
    """Build the held-out Requests stream-wrapper detection candidate spec."""

    source_text = _repo_file(repo_path, REQUESTS_MODELS_PATH).read_text(
        encoding="utf-8"
    )
    source_action = _requests_stream_wrapper_source_action(source_text)
    test_action = PytestInsertionAction(
        target_file=REQUESTS_TEST_REQUESTS_PATH,
        anchor_function_name="test_rewind_body_failed_tell",
        function_name="test_getattr_proxy_stream_follows_redirect",
        insertion_source=_requests_stream_wrapper_test_source(),
        max_added_lines=20,
        surrounding_blank_lines=1,
        rationale=(
            "insert a focused redirect/body regression after existing rewind "
            "body stream tests"
        ),
    )
    return HeldoutSourceRegionSpec(
        candidate_id="mat-020-requests-stream-wrapper",
        repo_id="psf/requests",
        repo_url="https://github.com/psf/requests",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/psf/requests/pull/7433",
        prompt=(
            "Fix prepare_body stream detection so file wrappers that expose "
            "__iter__ through __getattr__ are treated as streamed bodies and "
            "can follow redirects with their request body preserved."
        ),
        source_file=REQUESTS_MODELS_PATH,
        test_file=REQUESTS_TEST_REQUESTS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(REQUESTS_MODELS_PATH, REQUESTS_TEST_REQUESTS_PATH),
        source_action=source_action,
        test_action=test_action,
        action_family_reuse_evidence=(
            {
                "action_kind": SourceRegionActionKind.REPLACE_FUNCTION_REGION.value,
                "reused_from": ["MAT-008", "MAT-009"],
                "evidence": (
                    "same bounded function-region action schema; target file, "
                    "method, local predicate region, and replacement are parameters"
                ),
            },
            {
                "action_kind": "insert_pytest_function_after_anchor",
                "reused_from": ["MAT-008", "MAT-009", "GS7-008", "GS7-009"],
                "evidence": (
                    "same repo-convention pytest insertion shape; target "
                    "test file, anchor method/function, and inserted pytest "
                    "body are parameters"
                ),
            },
        ),
    )


def build_requests_redirect_history_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_REQUESTS_REDIRECT_HISTORY_BASE_REF,
    accepted_head_ref: str = DEFAULT_REQUESTS_REDIRECT_HISTORY_HEAD_REF,
    validation_command: str = DEFAULT_REQUESTS_REDIRECT_HISTORY_VALIDATION_COMMAND,
) -> HeldoutSourceRegionSpec:
    """Build the held-out Requests redirect-history candidate spec."""

    source_text = _repo_file(repo_path, REQUESTS_SESSIONS_PATH).read_text(
        encoding="utf-8"
    )
    source_action = _requests_redirect_history_source_action(source_text)
    test_action = PytestInsertionAction(
        target_file=REQUESTS_TEST_REQUESTS_PATH,
        anchor_function_name="test_HTTP_302_ALLOW_REDIRECT_GET",
        function_name="test_redirect_history_no_self_reference",
        insertion_source=_requests_redirect_history_test_source(),
        max_added_lines=10,
        surrounding_blank_lines=1,
        rationale=(
            "insert a focused redirect history regression after the existing "
            "302 redirect test"
        ),
    )
    return HeldoutSourceRegionSpec(
        candidate_id="mat-022-requests-redirect-history",
        repo_id="psf/requests",
        repo_url="https://github.com/psf/requests",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/psf/requests/pull/7328",
        prompt=(
            "Fix redirect history mutation so each Response history snapshot "
            "does not include the response itself and preserves prior redirects."
        ),
        source_file=REQUESTS_SESSIONS_PATH,
        test_file=REQUESTS_TEST_REQUESTS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(REQUESTS_SESSIONS_PATH, REQUESTS_TEST_REQUESTS_PATH),
        source_action=source_action,
        test_action=test_action,
        action_family_reuse_evidence=(
            {
                "action_kind": SourceRegionActionKind.REPLACE_FUNCTION_REGION.value,
                "reused_from": ["MAT-008", "MAT-009", "MAT-020"],
                "evidence": (
                    "same bounded function-region action schema; target file, "
                    "method, redirect-history mutation region, and replacement "
                    "are parameters"
                ),
            },
            {
                "action_kind": "insert_pytest_function_after_anchor",
                "reused_from": ["MAT-008", "MAT-009", "MAT-020", "GS7-008"],
                "evidence": (
                    "same repo-convention pytest insertion shape; target "
                    "test file, anchor method/function, and inserted pytest "
                    "body are parameters"
                ),
            },
        ),
    )


def build_click_write_usage_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_CLICK_WRITE_USAGE_BASE_REF,
    accepted_head_ref: str = DEFAULT_CLICK_WRITE_USAGE_HEAD_REF,
    validation_command: str = DEFAULT_CLICK_WRITE_USAGE_VALIDATION_COMMAND,
) -> HeldoutSourceRegionSpec:
    """Build the held-out Click write_usage empty-args candidate spec."""

    source_text = _repo_file(repo_path, CLICK_FORMATTING_PATH).read_text(
        encoding="utf-8"
    )
    source_action = _click_write_usage_source_action(source_text)
    test_action = PytestInsertionAction(
        target_file=CLICK_TEST_FORMATTING_PATH,
        anchor_function_name="test_write_usage_styled_prefix_keeps_options_on_one_line",
        function_name="test_help_formatter_write_usage",
        insertion_source=_click_write_usage_test_source(),
        max_added_lines=120,
        surrounding_blank_lines=2,
        trailing_blank_lines=0,
        rationale=(
            "insert formatter usage regressions after the existing "
            "write_usage styled-prefix coverage"
        ),
    )
    return HeldoutSourceRegionSpec(
        candidate_id="mat-023-click-write-usage-empty-args",
        repo_id="pallets/click",
        repo_url="https://github.com/pallets/click",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/pallets/click/pull/3434",
        prompt=(
            "Fix HelpFormatter.write_usage so commands with no rendered args "
            "still emit the usage prefix and program name without a trailing "
            "separator space."
        ),
        source_file=CLICK_FORMATTING_PATH,
        test_file=CLICK_TEST_FORMATTING_PATH,
        validation_command=validation_command,
        allowed_write_paths=(CLICK_FORMATTING_PATH, CLICK_TEST_FORMATTING_PATH),
        source_action=source_action,
        test_action=test_action,
        action_family_reuse_evidence=(
            {
                "action_kind": SourceRegionActionKind.REPLACE_FUNCTION_REGION.value,
                "reused_from": ["MAT-008", "MAT-009", "MAT-020", "MAT-022"],
                "evidence": (
                    "same bounded function-region action schema; target file, "
                    "method, local branch insertion point, and replacement are "
                    "parameters"
                ),
            },
            {
                "action_kind": "insert_pytest_function_after_anchor",
                "reused_from": ["MAT-008", "MAT-009", "MAT-020", "MAT-022"],
                "evidence": (
                    "same repo-convention pytest insertion shape; target "
                    "test file, anchor function, and inserted pytest block "
                    "are parameters"
                ),
            },
        ),
    )


def build_click_default_map_split_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_CLICK_DEFAULT_MAP_SPLIT_BASE_REF,
    accepted_head_ref: str = DEFAULT_CLICK_DEFAULT_MAP_SPLIT_HEAD_REF,
    validation_command: str = DEFAULT_CLICK_DEFAULT_MAP_SPLIT_VALIDATION_COMMAND,
) -> HeldoutSourceRegionSpec:
    """Build the held-out Click default_map multi-value splitting candidate."""

    source_text = _repo_file(repo_path, CLICK_CORE_PATH).read_text(encoding="utf-8")
    source_action = _click_default_map_split_source_action(source_text)
    test_action = PytestInsertionAction(
        target_file=CLICK_TEST_DEFAULTS_PATH,
        anchor_function_name="test_default_map_with_callable_flag_value",
        function_name="test_default_map_nargs",
        insertion_source=_click_default_map_split_test_source(),
        max_added_lines=60,
        surrounding_blank_lines=2,
        rationale=(
            "insert default_map multi-value regression after the existing "
            "default_map flag-value precedence coverage"
        ),
    )
    text_actions = (
        TextInsertionAction(
            target_file=CLICK_CHANGES_PATH,
            anchor_text=".. currentmodule:: click\n",
            insertion_source=_click_default_map_split_changelog_source(),
            insert_once_contains=":pr:`3364`",
            max_added_lines=30,
            rationale=(
                "record the behavior fix in the current changelog section "
                "without using a PR-specific action kind"
            ),
        ),
        TextInsertionAction(
            target_file=CLICK_COMMANDS_DOC_PATH,
            anchor_text="## Context Defaults",
            insertion_source=_click_default_map_split_commands_doc_source(),
            insert_once_contains="### Multi-value parameters",
            position="before_anchor",
            max_added_lines=40,
            rationale=(
                "document multi-value default_map splitting next to the "
                "default_map command example"
            ),
        ),
        TextInsertionAction(
            target_file=CLICK_DOCS_CONF_PATH,
            anchor_text=(
                'intersphinx_mapping = {\n'
                '    "python": ("https://docs.python.org/3/", None),\n'
                "}\n"
            ),
            insertion_source="myst_heading_anchors = 3\n",
            insert_once_contains="myst_heading_anchors = 3",
            max_added_lines=1,
            rationale=(
                "enable stable MyST heading anchors for the docs cross-reference "
                "inserted by the commands documentation"
            ),
        ),
    )
    return HeldoutSourceRegionSpec(
        candidate_id="mat-024-click-default-map-split",
        repo_id="pallets/click",
        repo_url="https://github.com/pallets/click",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/pallets/click/pull/3364",
        prompt=(
            "Split string values read from default_map for multi-value Click "
            "parameters the same way environment variable values are split."
        ),
        source_file=CLICK_CORE_PATH,
        test_file=CLICK_TEST_DEFAULTS_PATH,
        validation_command=validation_command,
        allowed_write_paths=(
            CLICK_CHANGES_PATH,
            CLICK_COMMANDS_DOC_PATH,
            CLICK_DOCS_CONF_PATH,
            CLICK_CORE_PATH,
            CLICK_TEST_DEFAULTS_PATH,
        ),
        source_action=source_action,
        test_action=test_action,
        text_actions=text_actions,
        action_family_reuse_evidence=(
            {
                "action_kind": SourceRegionActionKind.REPLACE_DELIMITED_REGION.value,
                "reused_from": [
                    "MAT-008",
                    "MAT-009",
                    "MAT-020",
                    "MAT-022",
                    "MAT-023",
                ],
                "evidence": (
                    "same bounded source-region action schema; target file, "
                    "local default_map branch, and replacement are "
                    "parameters"
                ),
            },
            {
                "action_kind": "insert_pytest_function_after_anchor",
                "reused_from": ["MAT-008", "MAT-009", "MAT-020", "MAT-022"],
                "evidence": (
                    "same repo-convention pytest insertion shape; target "
                    "test file, anchor function, and inserted pytest block "
                    "are parameters"
                ),
            },
            {
                "action_kind": "insert_text_around_anchor",
                "reused_from": ["MAT-017", "MAT-023-doc-gap"],
                "evidence": (
                    "same bounded text insertion shape; target file, anchor, "
                    "position, and inserted docs text are parameters"
                ),
            },
        ),
    )


def materialize_heldout_source_region_candidate(
    repo_path: Path,
    spec: HeldoutSourceRegionSpec,
    *,
    write: bool = True,
    validate: bool = False,
    accepted_diff_path: Path | None = None,
    validation_timeout_seconds: int = 180,
) -> HeldoutSourceRegionCandidate:
    """Materialize source/test actions and record candidate-after metadata."""

    repo = repo_path.expanduser().resolve()
    blockers: list[dict[str, str]] = []
    action_records = [
        spec.source_action.to_record(),
        spec.test_action.to_record(),
        *[action.to_record() for action in spec.text_actions],
    ]

    head = _git_stdout(repo, ("rev-parse", "HEAD"))
    if head and head != spec.base_ref:
        blockers.append(
            {
                "field": "repo_before_ref",
                "reason": "repo_before_ref_mismatch",
                "message": f"expected {spec.base_ref}, got {head}",
            }
        )

    hashes_before = _file_hashes(repo, spec.allowed_write_paths)
    source_result: SourceRegionMaterializationResult | None = None
    test_result: PytestInsertionResult | None = None
    text_results: list[TextInsertionResult] = []

    if not blockers:
        try:
            source_result = materialize_source_region(
                repo,
                spec.source_action,
                write=write,
            )
        except SourceRegionMaterializationError as error:
            blockers.append(
                {
                    "field": "source_region",
                    "reason": error.residual,
                    "message": str(error),
                }
            )

    if not blockers:
        try:
            test_result = materialize_pytest_insertion(
                repo,
                spec.test_action,
                write=write,
            )
        except HeldoutSourceRegionCandidateError as error:
            blockers.append(error.blocker)

    if not blockers:
        for text_action in spec.text_actions:
            try:
                text_results.append(
                    materialize_text_insertion(repo, text_action, write=write)
                )
            except HeldoutSourceRegionCandidateError as error:
                blockers.append(error.blocker)
                break

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
        scope_path_sets={
            "source_test": (spec.source_file, spec.test_file),
            "source_docs_test": tuple(spec.allowed_write_paths),
        },
    )
    if accepted_diff_comparison.get("accepted_diff_available") is False:
        blockers.append(
            {
                "field": "accepted_diff",
                "reason": "accepted_diff_unavailable",
                "message": str(accepted_diff_comparison.get("message", "")),
            }
        )

    source_record: dict[str, object]
    if source_result is None:
        source_record = {"available": False, "target_file": spec.source_file}
    else:
        source_record = source_result.to_record()

    test_record: dict[str, object]
    if test_result is None:
        test_record = {"available": False, "target_file": spec.test_file}
    else:
        test_record = test_result.to_record()

    text_records = [result.to_record() for result in text_results]
    candidate_after = {
        "source_file": source_record,
        "test_file": test_record,
        "text_files": text_records,
        "candidate_diff": candidate_diff,
        "candidate_diff_summary": _diff_summary(candidate_diff),
        "candidate_changed_files": changed_files,
        "file_hashes_before": hashes_before,
        "file_hashes_after": hashes_after,
    }
    mutation_scope = {
        "mode": "heldout_source_region_source_test",
        "allowed_write_paths": list(spec.allowed_write_paths),
        "planned_write_files": [
            spec.source_file,
            spec.test_file,
            *[action.target_file for action in spec.text_actions],
        ],
        "actual_changed_files": changed_files,
        "writes_outside_allowlist": writes_outside_allowlist,
        "only_accepted_source_test_files_changed": (
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

    return HeldoutSourceRegionCandidate(
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
        target_source_file=spec.source_file,
        target_test_file=spec.test_file,
        validation_command=spec.validation_command,
        allowed_write_paths=list(spec.allowed_write_paths),
        candidate_after=candidate_after,
        mutation_scope=mutation_scope,
        accepted_diff_comparison=accepted_diff_comparison,
        validation=validation,
        blockers=blockers,
        residual_labels=residual_labels,
    )


def materialize_pytest_insertion(
    repo_path: Path,
    action: PytestInsertionAction,
    *,
    write: bool = False,
) -> PytestInsertionResult:
    """Insert a pytest function after an anchor function and record metadata."""

    repo = repo_path.expanduser().resolve()
    test_path = _repo_file(repo, action.target_file)
    before = test_path.read_text(encoding="utf-8")
    if f"def {action.function_name}(" in before:
        return PytestInsertionResult(
            status="already_applied",
            target_file=action.target_file,
            function_name=action.function_name,
            insertion_line=None,
            added_line_count=0,
            diff="",
            diff_summary={"hunk_count": 0, "changed_line_count": 0},
            ast_delta=python_ast_delta_metadata(before, before),
            ast_parse_ok=True,
            sha256_before=_sha256_text(before),
            sha256_after=_sha256_text(before),
            patched_source=before,
            wrote_file=False,
        )

    tree = _parse_python(before, filename=action.target_file, field="test_insertion")
    anchor = _find_function(tree, action.anchor_function_name)
    if anchor is None or anchor.end_lineno is None:
        raise HeldoutSourceRegionCandidateError(
            f"anchor function not found: {action.anchor_function_name}",
            blocker={
                "field": "test_insertion",
                "reason": "repo_convention_test_insertion_blocked",
                "message": f"anchor function not found: {action.anchor_function_name}",
            },
        )

    insertion_lines = _insertion_lines(action.insertion_source)
    if len([line for line in insertion_lines if line.strip()]) > action.max_added_lines:
        raise HeldoutSourceRegionCandidateError(
            "pytest insertion added-line budget exceeded",
            blocker={
                "field": "test_insertion",
                "reason": "repo_convention_test_insertion_blocked",
                "message": "pytest insertion added-line budget exceeded",
            },
        )

    source_lines = before.splitlines(keepends=True)
    insert_index = anchor.end_lineno
    while insert_index < len(source_lines) and not source_lines[insert_index].strip():
        insert_index += 1
    leading_blank_lines = _surrounding_blank_lines(action)
    trailing_blank_lines = (
        action.trailing_blank_lines
        if action.trailing_blank_lines is not None
        else leading_blank_lines
    )
    leading_separator = ["\n"] * leading_blank_lines
    trailing_separator = ["\n"] * trailing_blank_lines
    patched = "".join(
        source_lines[: anchor.end_lineno]
        + leading_separator
        + insertion_lines
        + trailing_separator
        + source_lines[insert_index:]
    )
    _parse_python(patched, filename=action.target_file, field="test_insertion")
    if write:
        test_path.write_text(patched, encoding="utf-8")

    diff = _unified_diff(before, patched, action.target_file)
    return PytestInsertionResult(
        status="materialized" if write else "candidate_after",
        target_file=action.target_file,
        function_name=action.function_name,
        insertion_line=anchor.end_lineno + leading_blank_lines,
        added_line_count=sum(1 for line in insertion_lines if line.strip()),
        diff=diff,
        diff_summary=_diff_summary(diff),
        ast_delta=python_ast_delta_metadata(before, patched),
        ast_parse_ok=True,
        sha256_before=_sha256_text(before),
        sha256_after=_sha256_text(patched),
        patched_source=patched,
        wrote_file=write,
    )


def materialize_text_insertion(
    repo_path: Path,
    action: TextInsertionAction,
    *,
    write: bool = False,
) -> TextInsertionResult:
    """Insert bounded text before or after an anchor and record metadata."""

    repo = repo_path.expanduser().resolve()
    target_path = _repo_file(repo, action.target_file)
    before = target_path.read_text(encoding="utf-8")
    if action.insert_once_contains in before:
        return TextInsertionResult(
            status="already_applied",
            target_file=action.target_file,
            insertion_line=None,
            added_line_count=0,
            diff="",
            diff_summary={"hunk_count": 0, "changed_line_count": 0},
            sha256_before=_sha256_text(before),
            sha256_after=_sha256_text(before),
            patched_source=before,
            wrote_file=False,
        )

    added_line_count = sum(
        1 for line in action.insertion_source.splitlines() if line.strip()
    )
    if added_line_count > action.max_added_lines:
        raise HeldoutSourceRegionCandidateError(
            "text insertion added-line budget exceeded",
            blocker={
                "field": "text_insertion",
                "reason": "bounded_text_insertion_blocked",
                "message": "text insertion added-line budget exceeded",
            },
        )

    anchor_index = before.find(action.anchor_text)
    if anchor_index == -1:
        raise HeldoutSourceRegionCandidateError(
            f"text anchor not found in {action.target_file}",
            blocker={
                "field": "text_insertion",
                "reason": "bounded_text_insertion_blocked",
                "message": f"text anchor not found in {action.target_file}",
            },
        )

    if action.position == "after_anchor":
        insertion_index = anchor_index + len(action.anchor_text)
    else:
        insertion_index = anchor_index
    patched = (
        before[:insertion_index] + action.insertion_source + before[insertion_index:]
    )
    if write:
        target_path.write_text(patched, encoding="utf-8")

    insertion_line = before[:insertion_index].count("\n") + 1
    diff = _unified_diff(before, patched, action.target_file)
    return TextInsertionResult(
        status="materialized" if write else "candidate_after",
        target_file=action.target_file,
        insertion_line=insertion_line,
        added_line_count=added_line_count,
        diff=diff,
        diff_summary=_diff_summary(diff),
        sha256_before=_sha256_text(before),
        sha256_after=_sha256_text(patched),
        patched_source=patched,
        wrote_file=write,
    )


def write_candidate_artifacts(
    candidate: HeldoutSourceRegionCandidate,
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


def render_candidate_report(candidate: HeldoutSourceRegionCandidate) -> str:
    """Render a compact markdown report for a held-out candidate."""

    validation = candidate.validation
    comparison = candidate.accepted_diff_comparison
    lines = [
        "# Held-Out Source-Region Candidate",
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
        f"- Accepted source/test scoped match: "
        f"`{comparison.get('scope_comparisons', {}).get('source_test', {}).get('normalized_diff_equal', comparison.get('scoped_normalized_diff_equal'))}`",
        f"- Accepted source/docs/test scoped match: "
        f"`{comparison.get('scope_comparisons', {}).get('source_docs_test', {}).get('normalized_diff_equal')}`",
        f"- Zero hosted LLM source judgment: "
        f"`{candidate.zero_hosted_llm_source_judgment}`",
        "",
        "## Reusable Actions",
        "",
    ]
    for action in candidate.action_records:
        lines.append(f"- `{action.get('kind')}`")
    lines.extend(
        [
            "",
            "## Residuals",
            "",
        ]
    )
    if candidate.blockers:
        for blocker in candidate.blockers:
            lines.append(
                f"- `{blocker['field']}`: `{blocker['reason']}` - "
                f"{blocker['message']}"
            )
    elif candidate.residual_labels:
        for label in candidate.residual_labels:
            lines.append(f"- `{label}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _no_proxy_domain_boundary_source_action(source: str) -> SourceRegionAction:
    already_applied = "                host = host.lstrip(\".\")" in source
    start_line = _line_number(
        source,
        (
            "                host = host.lstrip(\".\")"
            if already_applied
            else "                if hostname.endswith(host) or host_with_port.endswith(host):"
        ),
    )
    end_line = _first_line_after(source, start_line, "                    return True")
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=REQUESTS_UTILS_PATH,
            function_name="should_bypass_proxies",
            region_name="no_proxy_host_matching_loop",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source=_no_proxy_domain_boundary_source_replacement(),
        constraints=SourceRegionConstraints(max_changed_source_lines=12),
        rationale="no_proxy domain-boundary matching inside the host loop",
    )


def _no_proxy_domain_boundary_source_replacement() -> str:
    return "\n".join(
        [
            '                host = host.lstrip(".")',
            "                if hostname == host or host_with_port == host:",
            "                    return True",
            '                host = "." + host',
            "                if hostname.endswith(host) or host_with_port.endswith(host):",
            "                    return True",
            "",
        ]
    )


def _no_proxy_domain_boundary_test_source() -> str:
    return "\n".join(
        [
            "@pytest.mark.parametrize(",
            '    "url, expected",',
            "    (",
            '        ("http://localhost/", True),',
            '        ("http://anotherdomain.com:8888/", True),',
            '        ("http://newdomain.com:1234/", True),',
            '        ("http://www.newdomain.com:1234/", True),',
            '        ("http://foo.d.o.t/", True),',
            '        ("http://d.o.t/", True),',
            '        ("http://prelocalhost/", False),',
            '        ("http://newdomain.com/", False),',
            '        ("http://newdomain.com:1235/", False),',
            "    ),",
            ")",
            "def test_should_bypass_proxies_no_proxy_domain_boundary(url, expected):",
            '    """Ensure no_proxy matching respects domain boundaries and does not',
            "    greedily match domains that merely endswith the no_proxy entry.",
            "    See CPython bpo-39057.",
            '    """',
            '    no_proxy = "localhost, anotherdomain.com, newdomain.com:1234, .d.o.t"',
            "    assert should_bypass_proxies(url, no_proxy=no_proxy) == expected",
        ]
    )


def _mark_expression_scanner_source_action(source: str) -> SourceRegionAction:
    already_applied = '                if (backslash_pos := value.find("\\\\")) != -1:'
    original = '                if (backslash_pos := input.find("\\\\")) != -1:'
    start_line = _line_number(source, already_applied if already_applied in source else original)
    end_needle = "                    )"
    end_line = _first_line_after(source, start_line, end_needle)
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=PYTEST_EXPRESSION_PATH,
            function_name="lex",
            region_name="current_string_literal_backslash_check",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source=_mark_expression_scanner_source_replacement(),
        constraints=SourceRegionConstraints(max_changed_source_lines=6),
        rationale=(
            "search for unsupported escaping within the current string token "
            "and report the token-relative column"
        ),
    )


def _mark_expression_scanner_source_replacement() -> str:
    return "\n".join(
        [
            '                if (backslash_pos := value.find("\\\\")) != -1:',
            "                    raise SyntaxError(",
            "                        r'escaping with \"\\\" not supported in marker expression',",
            "                        (FILE_NAME, 1, pos + backslash_pos + 1, input),",
            "                    )",
        ]
    )


def _mark_expression_scanner_test_source() -> str:
    return "\n".join(
        [
            "def test_backslash_in_identifier_with_string_literal() -> None:",
            '    r"""Backslashes in identifiers should not cause false rejections when the',
            "    expression also contains string literals. Regression test for a bug where",
            "    the scanner searched the entire input for backslashes instead of only the",
            '    current string literal value."""',
            "",
            "    def matcher(name: str, /, **kwargs: str | int | bool | None) -> bool:",
            '        return {r"\\nfoo\\n", r"test\\case", "mark"}.__contains__(name)',
            "",
            '    assert evaluate(r\'\\nfoo\\n and mark(x="y")\', matcher)',
            '    assert evaluate(r\'mark(x="y") and \\nfoo\\n\', matcher)',
            '    assert evaluate(r\'test\\case and mark(x="y")\', matcher)',
        ]
    )


def _requests_stream_wrapper_source_action(source: str) -> SourceRegionAction:
    already_applied = (
        "        # data that proxies attributes to underlying objects needs hasattr"
    )
    original = "        if isinstance(data, Iterable) and not isinstance("
    if already_applied in source:
        start_line = _line_number(source, already_applied)
        end_line = _first_line_after(
            source,
            start_line,
            "        if is_iterable and not isinstance(data, (str, bytes, list, tuple, Mapping)):",
        )
    else:
        start_line = _line_number(source, original)
        end_line = _first_line_after(source, start_line, "        ):")
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=REQUESTS_MODELS_PATH,
            function_name="prepare_body",
            region_name="stream_wrapper_iterable_predicate",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source=_requests_stream_wrapper_source_replacement(),
        constraints=SourceRegionConstraints(max_changed_source_lines=6),
        rationale=(
            "treat __getattr__-proxied iterators as streamed request bodies "
            "inside prepare_body"
        ),
    )


def _requests_stream_wrapper_source_replacement() -> str:
    return "\n".join(
        [
            "        # data that proxies attributes to underlying objects needs hasattr",
            '        is_iterable = isinstance(data, Iterable) or hasattr(data, "__iter__")',
            "        if is_iterable and not isinstance(data, (str, bytes, list, tuple, Mapping)):",
        ]
    )


def _requests_stream_wrapper_test_source() -> str:
    return "\n".join(
        [
            "    def test_getattr_proxy_stream_follows_redirect(self, httpbin):",
            '        """Ensure stream wrappers that don\'t implement __iter__ directly are still detected."""',
            "",
            "        class AttrProxy:",
            "            def __init__(self):",
            '                self._file = io.BytesIO(b"data")',
            "",
            "            def __getattr__(self, name):",
            "                return getattr(self._file, name)",
            "",
            "        r = requests.post(",
            '            httpbin("redirect-to?url=/post&status_code=307"), data=AttrProxy()',
            "        )",
            '        assert r.json()["data"] == "data"',
        ]
    )


def _requests_redirect_history_source_action(source: str) -> SourceRegionAction:
    already_applied = "            resp.history = hist[:]"
    original = "            # resp.history must ignore the original request in this loop"
    if already_applied in source:
        start_line = _line_number(source, already_applied)
        end_line = _first_line_after(source, start_line, "            hist.append(resp)")
    else:
        start_line = _line_number(source, original)
        end_line = _first_line_after(
            source,
            start_line,
            "            resp.history = hist[1:]",
        )
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=REQUESTS_SESSIONS_PATH,
            function_name="resolve_redirects",
            region_name="redirect_history_snapshot_order",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source=_requests_redirect_history_source_replacement(),
        constraints=SourceRegionConstraints(max_changed_source_lines=3),
        rationale=(
            "snapshot redirect history before appending the current response "
            "so response histories never self-reference"
        ),
    )


def _requests_redirect_history_source_replacement() -> str:
    return "\n".join(
        [
            "            resp.history = hist[:]",
            "            hist.append(resp)",
            "",
        ]
    )


def _requests_redirect_history_test_source() -> str:
    return "\n".join(
        [
            "    def test_redirect_history_no_self_reference(self, httpbin):",
            '        r = requests.get(httpbin("redirect", "3"))',
            "        assert r.status_code == 200",
            "        assert len(r.history) == 3",
            "        for i, resp in enumerate(r.history):",
            "            assert resp not in resp.history",
            "            assert resp.history == r.history[:i]",
        ]
    )


def _click_write_usage_source_action(source: str) -> SourceRegionAction:
    already_applied = "        if not args:"
    insertion_anchor = "        text_width = self.width - self.current_indent"
    if already_applied in source:
        start_line = _line_number(source, insertion_anchor)
        end_line = _first_line_after(source, start_line, "            return")
    else:
        start_line = _line_number(source, insertion_anchor)
        end_line = start_line
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=CLICK_FORMATTING_PATH,
            function_name="write_usage",
            region_name="empty_args_usage_line_branch",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source=_click_write_usage_source_replacement(),
        constraints=SourceRegionConstraints(max_changed_source_lines=9),
        rationale=(
            "emit the prefix/program line directly when write_usage has no "
            "arguments to wrap"
        ),
    )


def _click_write_usage_source_replacement() -> str:
    return "\n".join(
        [
            "        text_width = self.width - self.current_indent",
            "",
            "        if not args:",
            "            # Without args, the prefix's trailing space and the wrap_text",
            "            # call that would normally place args on the line are both",
            "            # unnecessary. Emit just the prefix line.",
            '            self.write(usage_prefix.rstrip(" "))',
            '            self.write("\\n")',
            "            return",
        ]
    )


def _click_write_usage_test_source() -> str:
    return "\n".join(
        [
            "@pytest.mark.parametrize(",
            '    ("formatter_kwargs", "current_indent", "prog", "args", "prefix", "expected"),',
            "    [",
            "        # Issue #3360: the default prefix used to emit only",
            "        # a blank line because ``wrap_text(\"\", initial_indent=usage_prefix)``",
            "        # returned ``\"\"`` and discarded the prefix.",
            "        pytest.param(",
            "            {},",
            "            0,",
            '            "Program",',
            '            "",',
            "            None,",
            '            "Usage: Program\\n",',
            '            id="empty-args-default-prefix",',
            "        ),",
            "        # A caller-supplied prefix is preserved verbatim.",
            "        pytest.param(",
            "            {},",
            "            0,",
            '            "Program",',
            '            "",',
            '            "Run: ",',
            '            "Run: Program\\n",',
            '            id="empty-args-custom-prefix",',
            "        ),",
            "        # ``current_indent`` is preserved even with no args to render.",
            "        pytest.param(",
            "            {},",
            "            4,",
            '            "Program",',
            '            "",',
            "            None,",
            '            "Usage: Program\\n",',
            '            id="empty-args-indented",',
            "        ),",
            "        # Prog too long to share a line with args: the wrap branch must not",
            "        # emit a second line.",
            "        pytest.param(",
            '            {"width": 20},',
            "            0,",
            '            "VeryLongProgramName",',
            '            "",',
            "            None,",
            '            "Usage: VeryLongProgramName\\n",',
            '            id="empty-args-long-prog",',
            "        ),",
            "        # With non-empty args, the separator space between prog and args is preserved.",
            "        pytest.param(",
            "            {},",
            "            0,",
            '            "Program",',
            '            "[OPTIONS]",',
            "            None,",
            '            "Usage: Program [OPTIONS]\\n",',
            '            id="with-args-default-prefix",',
            "        ),",
            "    ],",
            ")",
            "def test_help_formatter_write_usage(",
            "    formatter_kwargs, current_indent, prog, args, prefix, expected",
            "):",
            "    \"\"\"``HelpFormatter.write_usage`` renders a single usage line whose",
            "    trailing separator tracks whether ``args`` is non-empty.",
            "    \"\"\"",
            "    f = click.HelpFormatter(**formatter_kwargs)",
            "    f.current_indent = current_indent",
            "    if prefix is None:",
            "        f.write_usage(prog, args)",
            "    else:",
            "        f.write_usage(prog, args, prefix=prefix)",
            "    assert f.getvalue() == expected",
            "",
            "",
            "def test_help_formatter_write_usage_without_args_styled_prefix():",
            "    \"\"\"A downstream-styled prefix is preserved when ``args`` is empty:",
            "    the ANSI escape sequences survive, only the trailing separator is",
            "    removed.",
            "    \"\"\"",
            '    styled_prefix = "\\x1b[38;2;38;139;210m\\x1b[1mUsage:\\x1b[0m "',
            "    f = click.HelpFormatter()",
            '    f.write_usage("cli", prefix=styled_prefix)',
            "    rendered = f.getvalue()",
            '    assert strip_ansi(rendered) == "Usage: cli\\n"',
            '    assert "\\x1b[" in rendered',
            "",
            "",
            "@pytest.mark.parametrize(",
            '    ("command_kwargs", "expected_usage_line"),',
            "    [",
            "        # End-to-end regression for #3360: an empty ``options_metavar`` with",
            "        # no parameters used to render a blank usage line.",
            "        pytest.param(",
            '            {"options_metavar": ""},',
            '            "Usage: cli",',
            '            id="empty-options-metavar-no-params",',
            "        ),",
            "        # End-to-end regression: ``options_metavar=None`` is the documented",
            "        # way to suppress the ``[OPTIONS]`` slot entirely.",
            "        pytest.param(",
            '            {"options_metavar": None},',
            '            "Usage: cli",',
            '            id="none-options-metavar-no-params",',
            "        ),",
            "    ],",
            ")",
            "def test_command_write_usage_no_args(runner, command_kwargs, expected_usage_line):",
            "    \"\"\"End-to-end: a command with no parameters and an empty or absent",
            "    ``options_metavar`` renders a usage line with just the program name,",
            "    no trailing space.",
            "    \"\"\"",
            '    cli = click.Command("cli", **command_kwargs)',
            '    result = runner.invoke(cli, ["--help"])',
            "    assert result.output.splitlines()[0] == expected_usage_line",
        ]
    )


def _click_default_map_split_source_action(source: str) -> SourceRegionAction:
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_DELIMITED_REGION,
        target=SourceRegionTarget(
            file_path=CLICK_CORE_PATH,
            region_name="default_map_multivalue_string_split",
            start_marker=(
                "if default_map_value is not None or ctx._default_map_has(self.name):"
            ),
            end_marker="if value is UNSET:",
        ),
        replacement_source=_click_default_map_split_source_replacement(),
        constraints=SourceRegionConstraints(
            max_changed_source_lines=7,
            must_preserve_signature=False,
        ),
        rationale=(
            "split string default_map values for multi-value parameters before "
            "the normal type-cast path sees them"
        ),
    )


def _click_default_map_split_source_replacement() -> str:
    return "\n".join(
        [
            "                value = default_map_value",
            "                source = ParameterSource.DEFAULT_MAP",
            "",
            "                # A string from default_map must be split for multi-value",
            "                # parameters, matching value_from_envvar behavior.",
            "                if isinstance(value, str) and self.nargs != 1:",
            "                    value = self.type.split_envvar_value(value)",
            "",
            "",
        ]
    )


def _click_default_map_split_test_source() -> str:
    return "\n".join(
        [
            "@pytest.mark.parametrize(",
            '    ("default_map", "option_kwargs", "cli_args", "expected"),',
            "    [",
            "        # String is split for nargs=2 option.",
            '        ({"point": "3 4"}, {"nargs": 2, "type": int}, [], (3, 4)),',
            "        # String is split for explicit Tuple type.",
            '        ({"point": "hello world"}, {"type": (str, str)}, [], ("hello", "world")),',
            "        # Already-structured tuple passes through unchanged.",
            '        ({"point": ("a", "b")}, {"nargs": 2}, [], ("a", "b")),',
            "        # Already-structured list passes through unchanged.",
            '        ({"point": [5, 6]}, {"nargs": 2, "type": int}, [], (5, 6)),',
            "        # CLI args override default_map for nargs > 1.",
            "        (",
            '            {"point": "3 4"},',
            '            {"nargs": 2, "type": int},',
            '            ["--point", "10", "20"],',
            "            (10, 20),",
            "        ),",
            "    ],",
            ")",
            "def test_default_map_nargs(runner, default_map, option_kwargs, cli_args, expected):",
            "    \"\"\"A string in ``default_map`` for an option with ``nargs > 1`` should be",
            "    split the same way an environment variable string is split.",
            "",
            "    Regression test for https://github.com/pallets/click/issues/2745.",
            "    \"\"\"",
            "",
            "    @click.command()",
            '    @click.option("--point", **option_kwargs)',
            "    def cli(point):",
            "        click.echo(repr(point))",
            "",
            "    result = runner.invoke(cli, cli_args, default_map=default_map)",
            "    assert result.exit_code == 0",
            "    assert result.output.strip() == repr(expected)",
        ]
    )


def _click_default_map_split_changelog_source() -> str:
    return "\n".join(
        [
            "",
            "Version 8.4.0",
            "-------------",
            "",
            "Unreleased",
            "",
            "-   :class:`ParamType` typing improvements. :pr:`3371`",
            "",
            "    -   :class:`ParamType` is now a generic abstract base class,",
            "        parameterized by its converted value type.",
            "    -   :meth:`~ParamType.convert` return types are narrowed on all",
            "        concrete types (``str`` for :class:`STRING`, ``int`` for",
            "        :class:`INT`, etc.).",
            "    -   :meth:`~ParamType.to_info_dict` returns specific",
            "        :class:`~typing.TypedDict` subclasses instead of",
            "        ``dict[str, Any]``.",
            "    -   :class:`CompositeParamType` and the number-range base are now",
            "        generic with abstract methods.",
            "-   Split string values from ``default_map`` for parameters with ``nargs > 1``",
            "    or :class:`Tuple` type, matching environment variable behavior.",
            "    :issue:`2745` :pr:`3364`",
            "",
        ]
    )


def _click_default_map_split_commands_doc_source() -> str:
    return "\n".join(
        [
            "### Multi-value parameters",
            "",
            "When a `default_map` value is a string for a parameter with `nargs > 1` or a",
            "{class}`Tuple` type, the string is split automatically, the same way an",
            "environment variable would be. By default, values are split on whitespace. See",
            "[Multiple Options from Environment",
            "Values](options.md#multiple-options-from-environment-values) for details on",
            "splitting behavior.",
            "",
            "```python",
            "default_map = {",
            '    "draw": {',
            '        "point": "3 4",  # split into ("3", "4") for nargs=2',
            '        "color": "red",  # passed as-is for nargs=1',
            "    }",
            "}",
            "```",
            "",
            "You can also pass an already-structured tuple or list, which will be used as-is",
            "without splitting:",
            "",
            "```python",
            "default_map = {",
            '    "draw": {',
            '        "point": (3, 4),  # used directly',
            "    }",
            "}",
            "```",
            "",
            "",
        ]
    )


def _line_number(source: str, needle: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if line == needle:
            return index
    raise SourceRegionMaterializationError(
        f"source-region anchor not found: {needle}",
        residual="target_selection",
    )


def _first_line_after(source: str, start_line: int, needle: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if index < start_line:
            continue
        if line == needle:
            return index
    raise SourceRegionMaterializationError(
        f"source-region end anchor not found: {needle}",
        residual="target_selection",
    )


def _repo_file(repo: Path, relative_path: str) -> Path:
    _validate_relative_path(relative_path)
    path = repo / relative_path
    if not path.exists():
        raise HeldoutSourceRegionCandidateError(
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
        raise HeldoutSourceRegionCandidateError(
            f"invalid Python in {filename}: {error}",
            blocker={
                "field": field,
                "reason": "python_ast_parse_failed",
                "message": str(error),
            },
        ) from error


def _find_function(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    return None


def _insertion_lines(source: str) -> list[str]:
    lines = source.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def _surrounding_blank_lines(action: PytestInsertionAction) -> int:
    if action.surrounding_blank_lines is not None:
        return action.surrounding_blank_lines
    for line in action.insertion_source.splitlines():
        if not line.strip():
            continue
        return 1 if line.startswith((" ", "\t")) else 2
    return 2


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
    scope_path_sets: dict[str, Sequence[str]] | None = None,
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
    scope_comparisons: dict[str, dict[str, object]] = {}
    for name, paths in (scope_path_sets or {}).items():
        scope_comparisons[name] = _diff_scope_comparison(
            candidate_diff,
            accepted_diff,
            paths,
        )
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
        "scope_comparisons": scope_comparisons,
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


def _diff_scope_comparison(
    candidate_diff: str,
    accepted_diff: str,
    paths: Sequence[str],
) -> dict[str, object]:
    candidate_scoped_diff = _filter_diff_to_paths(candidate_diff, paths)
    accepted_scoped_diff = _filter_diff_to_paths(accepted_diff, paths)
    normalized_candidate = _normalize_diff(candidate_scoped_diff)
    normalized_accepted = _normalize_diff(accepted_scoped_diff)
    return {
        "paths": list(paths),
        "candidate_changed_files": _diff_changed_files(candidate_scoped_diff),
        "accepted_changed_files": _diff_changed_files(accepted_scoped_diff),
        "candidate_diff_line_count": len(candidate_scoped_diff.splitlines()),
        "accepted_diff_line_count": len(accepted_scoped_diff.splitlines()),
        "normalized_diff_equal": normalized_candidate == normalized_accepted,
        "parity_diff": ""
        if normalized_candidate == normalized_accepted
        else "".join(
            difflib.unified_diff(
                normalized_accepted.splitlines(keepends=True),
                normalized_candidate.splitlines(keepends=True),
                fromfile="accepted.scope.diff",
                tofile="candidate.scope.diff",
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
        description="Materialize a held-out source-region candidate."
    )
    parser.add_argument(
        "--candidate",
        choices=(
            "requests-7427",
            "pytest-14475",
            "requests-7433",
            "requests-7328",
            "click-3434",
            "click-3364",
        ),
        default="requests-7427",
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

    if args.candidate == "pytest-14475":
        spec = build_pytest_mark_expression_scanner_spec(args.repo_path)
    elif args.candidate == "requests-7433":
        spec = build_requests_stream_wrapper_spec(args.repo_path)
    elif args.candidate == "requests-7328":
        spec = build_requests_redirect_history_spec(args.repo_path)
    elif args.candidate == "click-3434":
        spec = build_click_write_usage_spec(args.repo_path)
    elif args.candidate == "click-3364":
        spec = build_click_default_map_split_spec(args.repo_path)
    else:
        spec = build_requests_no_proxy_domain_boundary_spec(args.repo_path)
    candidate = materialize_heldout_source_region_candidate(
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
