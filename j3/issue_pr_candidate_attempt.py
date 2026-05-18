"""Candidate attempt materializer for bounded issue/PR replay proofs."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from j3.ast_delta import python_ast_delta_metadata
from j3.issue_pr_preflight import (
    load_issue_pr_replay_manifest,
    select_issue_pr_replay_record,
)
from j3.source_region_materializer import (
    SourceRegionAction,
    SourceRegionActionKind,
    SourceRegionConstraints,
    SourceRegionMaterializationError,
    SourceRegionTarget,
    materialize_source_region,
)


ISSUE_PR_CANDIDATE_ATTEMPT_SCHEMA_VERSION = "issue-pr-candidate-attempt-v1"
ISSUE_PR_CANDIDATE_ATTEMPT_KIND = "issue_pr_candidate_attempt"
REQUESTS_REPLAY_ID = "psf__requests-issue-7432-pr-7433"
REQUESTS_ACTION_FAMILY = "requests_prepare_body_getattr_stream_candidate"
REQUESTS_SOURCE_PATH = "src/requests/models.py"
REQUESTS_TEST_PATH = "tests/test_requests.py"
REQUESTS_VALIDATION_COMMAND = (
    ".venv/bin/python -m pytest tests/test_requests.py -q "
    "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
)
REQUESTS_SETUP_COMMAND = (
    "python -m venv .venv && "
    ".venv/bin/python -m pip install -q --upgrade pip setuptools wheel && "
    ".venv/bin/python -m pip install -q -e . pytest pytest-httpbin==2.1.0 "
    "httpbin~=0.10.0 trustme"
)
CLICK_DEFAULT_MAP_REPLAY_ID = "pallets__click-issue-2745-pr-3364"
CLICK_DEFAULT_MAP_ACTION_FAMILY = "click_default_map_multi_value_candidate"
CLICK_DEFAULT_MAP_SOURCE_PATH = "src/click/core.py"
CLICK_DEFAULT_MAP_TEST_PATH = "tests/test_defaults.py"
CLICK_DEFAULT_MAP_VALIDATION_COMMAND = "pytest tests/test_defaults.py -q"
CLICK_DEFAULT_MAP_SETUP_COMMAND = "python -m pip install -e . pytest"
CLICK_SEMVER_REPLAY_ID = "pallets__click-issue-3298-pr-3299"
CLICK_SEMVER_ACTION_FAMILY = "click_semver_non_string_default_help_candidate"
CLICK_SEMVER_SOURCE_PATH = "src/click/core.py"
CLICK_SEMVER_TEST_PATH = "tests/test_options.py"
CLICK_SEMVER_VALIDATION_COMMAND = "pytest tests/test_options.py -q"
CLICK_SEMVER_SETUP_COMMAND = "python -m pip install -e . pytest"
PYTEST_STRICT_ADDOPTS_REPLAY_ID = "pytest-dev__pytest-issue-14442-pr-14443"
PYTEST_STRICT_ADDOPTS_ACTION_FAMILY = "pytest_strict_addopts_source_test_candidate"
PYTEST_STRICT_ADDOPTS_FULL_SCOPE_ACTION_FAMILY = (
    "pytest_strict_addopts_full_scope_candidate"
)
PYTEST_STRICT_ADDOPTS_SOURCE_PATH = "src/_pytest/config/__init__.py"
PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH = "testing/test_config.py"
PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH = "testing/test_mark.py"
PYTEST_STRICT_ADDOPTS_AUTHORS_PATH = "AUTHORS"
PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH = "changelog/14442.bugfix.rst"
PYTEST_STRICT_ADDOPTS_AUTHOR_ENTRIES = [
    "Hamza Mobeen",
    "Praneeth Kodumagulla",
]
PYTEST_STRICT_ADDOPTS_CHANGELOG_TEXT = "\n".join(
    [
        "Fixed a regression in pytest 9.0 where :option:`--strict-markers` and :option:`--strict-config` specified through :confval:`addopts` were silently ignored.",
        "",
        "Note that when targeting pytest >= 9.0, it's nicer to use :confval:`strict_markers` and :confval:`strict_config`, or :ref:`strict mode <strict mode>`.",
        "",
    ]
)
PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS = [
    PYTEST_STRICT_ADDOPTS_AUTHORS_PATH,
    PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH,
]
PYTEST_STRICT_ADDOPTS_SOURCE_TEST_PATHS = [
    PYTEST_STRICT_ADDOPTS_SOURCE_PATH,
    PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH,
    PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH,
]
PYTEST_STRICT_ADDOPTS_ACCEPTED_PATHS = [
    *PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS,
    *PYTEST_STRICT_ADDOPTS_SOURCE_TEST_PATHS,
]
PYTEST_STRICT_ADDOPTS_VALIDATION_COMMAND = (
    "pytest testing/test_config.py testing/test_mark.py -q"
)
PYTEST_STRICT_ADDOPTS_SETUP_COMMAND = "python -m pip install -e . pytest"
PYTEST_TIMEDELTA_APPROX_REPLAY_ID = "pytest-dev__pytest-issue-14462-pr-14466"
PYTEST_TIMEDELTA_APPROX_ACTION_FAMILY = "pytest_timedelta_approx_source_test_candidate"
PYTEST_TIMEDELTA_APPROX_SOURCE_PATH = "src/_pytest/python_api.py"
PYTEST_TIMEDELTA_APPROX_TEST_PATH = "testing/python/approx.py"
PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS = [
    PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
    PYTEST_TIMEDELTA_APPROX_TEST_PATH,
]
PYTEST_TIMEDELTA_APPROX_SETUP_COMMAND = "python -m pip install -e . pytest"
PYTEST_TIMEDELTA_APPROX_VALIDATION_COMMAND = (
    "python -m py_compile src/_pytest/python_api.py && "
    "pytest testing/python/approx.py -q"
)
SCRAPY_DOWNLOADER_AWARE_REPLAY_ID = "scrapy__scrapy-issue-7293-pr-7351"
SCRAPY_DOWNLOADER_AWARE_ACTION_FAMILY = (
    "scrapy_downloader_aware_slot_rotation_source_test_candidate"
)
SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH = "scrapy/pqueues.py"
SCRAPY_DOWNLOADER_AWARE_TEST_PATH = "tests/test_pqueues.py"
SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS = [
    SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
    SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
]
SCRAPY_DOWNLOADER_AWARE_SETUP_COMMAND = "python -m pip install -e ."
SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND = (
    "python -m py_compile scrapy/pqueues.py && pytest tests/test_pqueues.py -q"
)


class IssuePrCandidateAttemptError(ValueError):
    """Raised when the bounded issue/PR candidate attempt cannot proceed."""

    def __init__(self, message: str, *, blocker: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.blocker = blocker or {
            "field": "issue_pr_candidate_attempt",
            "reason": "candidate_attempt_blocked",
            "message": message,
        }


@dataclass(frozen=True, slots=True)
class IssuePrCandidateAttempt:
    """Structured result for one issue/PR candidate attempt."""

    candidate_id: str
    replay_id: str
    repo: str
    repo_before_ref: str
    prompt: str
    status: str
    action_family: str
    allowed_write_paths: list[str] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)
    actions: list[dict[str, object]] = field(default_factory=list)
    auxiliary_materialization: dict[str, object] = field(default_factory=dict)
    source_materialization: dict[str, object] = field(default_factory=dict)
    test_materialization: dict[str, object] = field(default_factory=dict)
    candidate_diff: dict[str, object] = field(default_factory=dict)
    mutation_scope: dict[str, object] = field(default_factory=dict)
    validation: dict[str, object] = field(default_factory=dict)
    structured_action_coverage: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)
    residual_labels: list[str] = field(default_factory=list)
    zero_hosted_usage_confirmed: bool = True

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": ISSUE_PR_CANDIDATE_ATTEMPT_SCHEMA_VERSION,
            "record_kind": ISSUE_PR_CANDIDATE_ATTEMPT_KIND,
            "candidate_id": self.candidate_id,
            "replay_id": self.replay_id,
            "repo": self.repo,
            "repo_before_ref": self.repo_before_ref,
            "prompt": self.prompt,
            "status": self.status,
            "action_family": self.action_family,
            "allowed_write_paths": list(self.allowed_write_paths),
            "evidence": _json_copy(self.evidence),
            "actions": _json_copy(self.actions),
            "auxiliary_materialization": _json_copy(self.auxiliary_materialization),
            "source_materialization": _json_copy(self.source_materialization),
            "test_materialization": _json_copy(self.test_materialization),
            "candidate_diff": _json_copy(self.candidate_diff),
            "mutation_scope": _json_copy(self.mutation_scope),
            "validation": _json_copy(self.validation),
            "structured_action_coverage": _json_copy(self.structured_action_coverage),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "residual_labels": list(self.residual_labels),
            "zero_hosted_usage_confirmed": self.zero_hosted_usage_confirmed,
        }


def run_requests_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = REQUESTS_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Attempt the bounded Requests #7432/#7433 candidate in a repo checkout."""

    if replay_id != REQUESTS_REPLAY_ID:
        raise IssuePrCandidateAttemptError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_candidate",
                "message": "DATA-012 may attempt only psf__requests-issue-7432-pr-7433",
            },
        )
    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrCandidateAttemptError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record["repo_before_ref"])
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record["accepted_change"])
    allowed_write_paths = _string_sequence(accepted_change.get("changed_files"))
    if allowed_write_paths != [REQUESTS_SOURCE_PATH, REQUESTS_TEST_PATH]:
        raise IssuePrCandidateAttemptError(
            "Requests candidate allowlist changed unexpectedly",
            blocker={
                "field": "accepted_change.changed_files",
                "reason": "unexpected_allowed_write_scope",
                "message": "DATA-012 expects the accepted source and test paths only",
            },
        )

    blockers: list[dict[str, str]] = []
    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        }
    ]
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    source_action: SourceRegionAction | None = None
    source_materialization: dict[str, object] = {}
    if not blockers:
        try:
            source_text = _repo_file(resolved_repo, REQUESTS_SOURCE_PATH).read_text(
                encoding="utf-8"
            )
            source_action = _requests_prepare_body_stream_detection_action(source_text)
            actions.append(source_action.to_record())
            source_result = materialize_source_region(
                resolved_repo,
                source_action,
                write=write,
            )
            source_materialization = source_result.to_record()
        except SourceRegionMaterializationError as error:
            source_materialization = {
                "status": "blocked",
                "file_path": REQUESTS_SOURCE_PATH,
                "not_available_reason": error.residual,
            }
            blockers.append(
                {
                    "field": "source_materialization",
                    "reason": error.residual,
                    "message": str(error),
                }
            )

    test_materialization: dict[str, object] = {}
    if not blockers:
        try:
            test_materialization = _materialize_requests_redirect_stream_test(
                resolved_repo,
                write=write,
            )
            actions.append(
                {
                    "kind": "insert_pytest_method",
                    "target": REQUESTS_TEST_PATH,
                    "payload": {
                        "class_name": "TestRequests",
                        "method_name": "test_getattr_proxy_stream_follows_redirect",
                        "anchor": "def _patch_adapter_gzipped_redirect",
                    },
                }
            )
        except IssuePrCandidateAttemptError as error:
            test_materialization = {
                "status": "blocked",
                "target_test_file": REQUESTS_TEST_PATH,
            }
            blockers.append(error.blocker)

    candidate_diff = _candidate_diff(resolved_repo, allowed_write_paths)
    changed_files = _string_sequence(candidate_diff.get("changed_files"))
    planned_changed_files = _unique(
        [
            *_string_sequence(
                _mapping(source_materialization.get("candidate_after")).get(
                    "diff_summary", {}
                )
                and [REQUESTS_SOURCE_PATH],
            ),
            *_string_sequence(test_materialization.get("planned_changed_files")),
        ]
    )
    files_changed = changed_files or planned_changed_files
    writes_outside_allowlist = _paths_outside_allowlist(files_changed, allowed_write_paths)
    if writes_outside_allowlist:
        blockers.append(
            {
                "field": "allowed_write_paths",
                "reason": "writes_outside_allowlist",
                "message": "candidate wrote paths outside DATA-010 allowed scope",
            }
        )
    missing_allowed_paths = [
        path for path in allowed_write_paths if path not in files_changed
    ]
    if not blockers and missing_allowed_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "accepted_edit_not_fully_materialized",
                "message": "candidate did not materialize all accepted change paths: "
                + ", ".join(missing_allowed_paths),
            }
        )

    selected_setup = setup_command or REQUESTS_SETUP_COMMAND
    selected_validation = validation_command or _selected_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
        replay_id=REQUESTS_REPLAY_ID,
        default_command=REQUESTS_VALIDATION_COMMAND,
    )
    validation = _deferred_validation_record(
        setup_command=selected_setup,
        validation_command=selected_validation,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            resolved_repo,
            setup_command=selected_setup,
            validation_command=selected_validation,
            timeout_seconds=validation_timeout_seconds,
        )

    if validation.get("status") == "failed":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_failed",
                "message": "focused DATA-008 validation command failed",
            }
        )
    elif validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_timeout",
                "message": "focused DATA-008 validation command timed out",
            }
        )

    structured_action_coverage = _requests_structured_action_coverage(
        blockers=blockers,
        source_action=source_action,
        files_changed=files_changed,
        allowed_write_paths=allowed_write_paths,
        validation=validation,
    )
    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation.get("status") == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation.get('status')}"]
        else:
            residual_labels = ["candidate_validation_deferred"]

    status = "blocked" if blockers else "materialized"
    if not blockers and validation.get("status") == "passed":
        status = "validated"
    elif not blockers and not write:
        status = "planned"

    evidence = _evidence_summary(
        readiness_records=readiness_records,
        prompt_spec_records=prompt_spec_records,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        repo_before_ref=expected_sha,
        candidate_diff=str(candidate_diff.get("diff", "")),
        validation_status=str(validation.get("status", "")),
    )
    mutation_scope = {
        "mode": "issue_pr_candidate_attempt",
        "allowed_write_paths": list(allowed_write_paths),
        "planned_write_files": list(allowed_write_paths),
        "files_changed": files_changed,
        "writes_outside_allowlist": writes_outside_allowlist,
        "allowed_write_path_check_passed": not writes_outside_allowlist,
        "missing_allowed_write_paths": missing_allowed_paths,
    }
    return IssuePrCandidateAttempt(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=REQUESTS_ACTION_FAMILY,
        allowed_write_paths=list(allowed_write_paths),
        evidence=evidence,
        actions=actions,
        source_materialization=source_materialization,
        test_materialization=test_materialization,
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        structured_action_coverage=structured_action_coverage,
        blockers=blockers,
        residual_labels=residual_labels,
    )


def run_click_default_map_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = CLICK_DEFAULT_MAP_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Attempt the bounded Click #2745/#3364 default_map candidate."""

    if replay_id != CLICK_DEFAULT_MAP_REPLAY_ID:
        raise IssuePrCandidateAttemptError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_candidate",
                "message": "DATA-014 may attempt only pallets__click-issue-2745-pr-3364",
            },
        )
    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrCandidateAttemptError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record["repo_before_ref"])
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record["accepted_change"])
    allowed_write_paths = _string_sequence(accepted_change.get("changed_files"))
    required_paths = [
        "CHANGES.rst",
        "docs/commands.md",
        "docs/conf.py",
        CLICK_DEFAULT_MAP_SOURCE_PATH,
        CLICK_DEFAULT_MAP_TEST_PATH,
    ]
    if allowed_write_paths != required_paths:
        raise IssuePrCandidateAttemptError(
            "Click default_map candidate allowlist changed unexpectedly",
            blocker={
                "field": "accepted_change.changed_files",
                "reason": "unexpected_allowed_write_scope",
                "message": "DATA-014 expects the accepted Click #3364 paths only",
            },
        )

    blockers: list[dict[str, str]] = []
    materialization_gaps: list[dict[str, str]] = []
    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        }
    ]
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    source_action: SourceRegionAction | None = None
    source_materialization: dict[str, object] = {}
    if not blockers:
        try:
            source_text = _repo_file(resolved_repo, CLICK_DEFAULT_MAP_SOURCE_PATH).read_text(
                encoding="utf-8"
            )
            source_action = _click_default_map_string_split_action(source_text)
            actions.append(source_action.to_record())
            source_result = materialize_source_region(
                resolved_repo,
                source_action,
                write=write,
            )
            source_materialization = source_result.to_record()
        except SourceRegionMaterializationError as error:
            source_materialization = {
                "status": "blocked",
                "file_path": CLICK_DEFAULT_MAP_SOURCE_PATH,
                "not_available_reason": error.residual,
            }
            blockers.append(
                {
                    "field": "source_materialization",
                    "reason": error.residual,
                    "message": str(error),
                }
            )

    test_materialization: dict[str, object] = {}
    if not blockers:
        try:
            test_materialization = _materialize_click_default_map_nargs_test(
                resolved_repo,
                write=write,
            )
            actions.append(
                {
                    "kind": "insert_pytest_function",
                    "target": CLICK_DEFAULT_MAP_TEST_PATH,
                    "payload": {
                        "function_name": "test_default_map_nargs",
                        "anchor": "def test_unset_in_default_map",
                    },
                }
            )
        except IssuePrCandidateAttemptError as error:
            test_materialization = {
                "status": "blocked",
                "target_test_file": CLICK_DEFAULT_MAP_TEST_PATH,
            }
            blockers.append(error.blocker)

    candidate_diff = _candidate_diff(resolved_repo, allowed_write_paths)
    changed_files = _string_sequence(candidate_diff.get("changed_files"))
    planned_changed_files = _unique(
        [
            *_source_planned_changed_files(
                source_materialization, CLICK_DEFAULT_MAP_SOURCE_PATH
            ),
            *_string_sequence(test_materialization.get("planned_changed_files")),
        ]
    )
    files_changed = changed_files or planned_changed_files
    writes_outside_allowlist = _paths_outside_allowlist(files_changed, allowed_write_paths)
    if writes_outside_allowlist:
        blockers.append(
            {
                "field": "allowed_write_paths",
                "reason": "writes_outside_allowlist",
                "message": "candidate wrote paths outside DATA-010 allowed scope",
            }
        )
    missing_allowed_paths = [
        path for path in allowed_write_paths if path not in files_changed
    ]
    auxiliary_missing_paths = [
        path
        for path in missing_allowed_paths
        if path not in {CLICK_DEFAULT_MAP_SOURCE_PATH, CLICK_DEFAULT_MAP_TEST_PATH}
    ]
    behavior_missing_paths = [
        path
        for path in missing_allowed_paths
        if path in {CLICK_DEFAULT_MAP_SOURCE_PATH, CLICK_DEFAULT_MAP_TEST_PATH}
    ]
    if not blockers and behavior_missing_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "accepted_behavior_edit_not_fully_materialized",
                "message": "candidate did not materialize required source/test paths: "
                + ", ".join(behavior_missing_paths),
            }
        )
    if auxiliary_missing_paths:
        materialization_gaps.append(
            {
                "field": "accepted_change.changed_files",
                "reason": "accepted_auxiliary_paths_not_materialized",
                "message": (
                    "current candidate-attempt surface has no changelog/docs/config "
                    "materialization action for: "
                    + ", ".join(auxiliary_missing_paths)
                ),
            }
        )

    selected_setup = setup_command or CLICK_DEFAULT_MAP_SETUP_COMMAND
    selected_validation = validation_command or _selected_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
        replay_id=CLICK_DEFAULT_MAP_REPLAY_ID,
        default_command=CLICK_DEFAULT_MAP_VALIDATION_COMMAND,
    )
    validation = _deferred_validation_record(
        setup_command=selected_setup,
        validation_command=selected_validation,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            resolved_repo,
            setup_command=selected_setup,
            validation_command=selected_validation,
            timeout_seconds=validation_timeout_seconds,
        )

    if validation.get("status") == "failed":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_failed",
                "message": "focused DATA-010 validation command failed",
            }
        )
    elif validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_timeout",
                "message": "focused DATA-010 validation command timed out",
            }
        )

    structured_action_coverage = _click_default_map_structured_action_coverage(
        blockers=blockers,
        materialization_gaps=materialization_gaps,
        source_action=source_action,
        files_changed=files_changed,
        validation=validation,
    )
    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation.get("status") == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation.get('status')}"]
        else:
            residual_labels = ["candidate_validation_deferred"]
    residual_labels.extend(gap["reason"] for gap in materialization_gaps)

    status = "blocked" if blockers else "materialized"
    if not blockers and validation.get("status") == "passed":
        status = "validated"
    elif not blockers and not write:
        status = "planned"

    evidence = _evidence_summary(
        readiness_records=readiness_records,
        prompt_spec_records=prompt_spec_records,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
        replay_id=CLICK_DEFAULT_MAP_REPLAY_ID,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        repo_before_ref=expected_sha,
        candidate_diff=str(candidate_diff.get("diff", "")),
        validation_status=str(validation.get("status", "")),
    )
    mutation_scope = {
        "mode": "issue_pr_candidate_attempt",
        "allowed_write_paths": list(allowed_write_paths),
        "planned_write_files": [
            CLICK_DEFAULT_MAP_SOURCE_PATH,
            CLICK_DEFAULT_MAP_TEST_PATH,
        ],
        "files_changed": files_changed,
        "writes_outside_allowlist": writes_outside_allowlist,
        "allowed_write_path_check_passed": not writes_outside_allowlist,
        "missing_allowed_write_paths": missing_allowed_paths,
        "materialization_gap_paths": auxiliary_missing_paths,
    }
    return IssuePrCandidateAttempt(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=CLICK_DEFAULT_MAP_ACTION_FAMILY,
        allowed_write_paths=list(allowed_write_paths),
        evidence=evidence,
        actions=actions,
        source_materialization=source_materialization,
        test_materialization=test_materialization,
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        structured_action_coverage=structured_action_coverage,
        blockers=[*blockers, *materialization_gaps],
        residual_labels=_unique(residual_labels),
    )


def run_click_semver_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = CLICK_SEMVER_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Attempt the bounded Click #3298/#3299 semver default candidate."""

    if replay_id != CLICK_SEMVER_REPLAY_ID:
        raise IssuePrCandidateAttemptError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_candidate",
                "message": "DATA-016 may attempt only pallets__click-issue-3298-pr-3299",
            },
        )
    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrCandidateAttemptError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record["repo_before_ref"])
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record["accepted_change"])
    allowed_write_paths = _string_sequence(accepted_change.get("changed_files"))
    required_paths = [CLICK_SEMVER_SOURCE_PATH, CLICK_SEMVER_TEST_PATH]
    if allowed_write_paths != required_paths:
        raise IssuePrCandidateAttemptError(
            "Click semver candidate allowlist changed unexpectedly",
            blocker={
                "field": "accepted_change.changed_files",
                "reason": "unexpected_allowed_write_scope",
                "message": "DATA-016 expects only the Click #3299 source and test paths",
            },
        )

    blockers: list[dict[str, str]] = []
    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        }
    ]
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    source_action: SourceRegionAction | None = None
    source_materialization: dict[str, object] = {}
    if not blockers:
        try:
            source_text = _repo_file(resolved_repo, CLICK_SEMVER_SOURCE_PATH).read_text(
                encoding="utf-8"
            )
            source_action = _click_semver_empty_string_guard_action(source_text)
            actions.append(source_action.to_record())
            source_result = materialize_source_region(
                resolved_repo,
                source_action,
                write=write,
            )
            source_materialization = source_result.to_record()
        except SourceRegionMaterializationError as error:
            source_materialization = {
                "status": "blocked",
                "file_path": CLICK_SEMVER_SOURCE_PATH,
                "not_available_reason": error.residual,
            }
            blockers.append(
                {
                    "field": "source_materialization",
                    "reason": error.residual,
                    "message": str(error),
                }
            )

    test_materialization: dict[str, object] = {}
    if not blockers:
        try:
            test_materialization = _materialize_click_semver_default_help_test(
                resolved_repo,
                write=write,
            )
            actions.append(
                {
                    "kind": "replace_pytest_function",
                    "target": CLICK_SEMVER_TEST_PATH,
                    "payload": {
                        "function_name": "test_show_default_with_empty_string",
                        "helper_class": "_StrictEq",
                    },
                }
            )
        except IssuePrCandidateAttemptError as error:
            test_materialization = {
                "status": "blocked",
                "target_test_file": CLICK_SEMVER_TEST_PATH,
            }
            blockers.append(error.blocker)

    candidate_diff = _candidate_diff(resolved_repo, allowed_write_paths)
    changed_files = _string_sequence(candidate_diff.get("changed_files"))
    planned_changed_files = _unique(
        [
            *_source_planned_changed_files(source_materialization, CLICK_SEMVER_SOURCE_PATH),
            *_string_sequence(test_materialization.get("planned_changed_files")),
        ]
    )
    files_changed = changed_files or planned_changed_files
    writes_outside_allowlist = _paths_outside_allowlist(files_changed, allowed_write_paths)
    if writes_outside_allowlist:
        blockers.append(
            {
                "field": "allowed_write_paths",
                "reason": "writes_outside_allowlist",
                "message": "candidate wrote paths outside DATA-015/DATA-010 allowed scope",
            }
        )
    missing_allowed_paths = [
        path for path in allowed_write_paths if path not in files_changed
    ]
    if not blockers and missing_allowed_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "accepted_edit_not_fully_materialized",
                "message": "candidate did not materialize all accepted change paths: "
                + ", ".join(missing_allowed_paths),
            }
        )

    selected_setup = setup_command or CLICK_SEMVER_SETUP_COMMAND
    selected_validation = validation_command or _selected_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
        replay_id=CLICK_SEMVER_REPLAY_ID,
        default_command=CLICK_SEMVER_VALIDATION_COMMAND,
    )
    validation = _deferred_validation_record(
        setup_command=selected_setup,
        validation_command=selected_validation,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            resolved_repo,
            setup_command=selected_setup,
            validation_command=selected_validation,
            timeout_seconds=validation_timeout_seconds,
        )

    if validation.get("status") == "failed":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_failed",
                "message": "focused Click #3298 validation command failed",
            }
        )
    elif validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_timeout",
                "message": "focused Click #3298 validation command timed out",
            }
        )

    structured_action_coverage = _click_semver_structured_action_coverage(
        blockers=blockers,
        source_action=source_action,
        files_changed=files_changed,
        allowed_write_paths=allowed_write_paths,
        validation=validation,
    )
    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation.get("status") == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation.get('status')}"]
        else:
            residual_labels = ["candidate_validation_deferred"]

    status = "blocked" if blockers else "materialized"
    if not blockers and validation.get("status") == "passed":
        status = "validated"
    elif not blockers and not write:
        status = "planned"

    evidence = _evidence_summary(
        readiness_records=readiness_records,
        prompt_spec_records=prompt_spec_records,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
        replay_id=CLICK_SEMVER_REPLAY_ID,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        repo_before_ref=expected_sha,
        candidate_diff=str(candidate_diff.get("diff", "")),
        validation_status=str(validation.get("status", "")),
    )
    mutation_scope = {
        "mode": "issue_pr_candidate_attempt",
        "allowed_write_paths": list(allowed_write_paths),
        "planned_write_files": [CLICK_SEMVER_SOURCE_PATH, CLICK_SEMVER_TEST_PATH],
        "files_changed": files_changed,
        "writes_outside_allowlist": writes_outside_allowlist,
        "allowed_write_path_check_passed": not writes_outside_allowlist,
        "missing_allowed_write_paths": missing_allowed_paths,
        "materialization_gap_paths": [],
    }
    return IssuePrCandidateAttempt(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=CLICK_SEMVER_ACTION_FAMILY,
        allowed_write_paths=list(allowed_write_paths),
        evidence=evidence,
        actions=actions,
        source_materialization=source_materialization,
        test_materialization=test_materialization,
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        structured_action_coverage=structured_action_coverage,
        blockers=blockers,
        residual_labels=_unique(residual_labels),
    )


def run_pytest_strict_addopts_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    materialization_audit_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    include_auxiliary_paths: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Attempt the pytest #14442/#14443 candidate in source/test or full scope."""

    if replay_id != PYTEST_STRICT_ADDOPTS_REPLAY_ID:
        raise IssuePrCandidateAttemptError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_candidate",
                "message": (
                    "DATA-024 may attempt only "
                    "pytest-dev__pytest-issue-14442-pr-14443"
                ),
            },
        )
    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrCandidateAttemptError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record["repo_before_ref"])
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record["accepted_change"])
    accepted_paths = _string_sequence(accepted_change.get("changed_files"))
    if accepted_paths != PYTEST_STRICT_ADDOPTS_ACCEPTED_PATHS:
        raise IssuePrCandidateAttemptError(
            "pytest strict addopts candidate allowlist changed unexpectedly",
            blocker={
                "field": "accepted_change.changed_files",
                "reason": "unexpected_allowed_write_scope",
                "message": "DATA-024 expects exactly the pytest #14443 accepted paths",
            },
        )

    blockers: list[dict[str, str]] = []
    materialization_gaps: list[dict[str, str]] = []
    allowed_write_paths = (
        PYTEST_STRICT_ADDOPTS_ACCEPTED_PATHS
        if include_auxiliary_paths
        else PYTEST_STRICT_ADDOPTS_SOURCE_TEST_PATHS
    )
    planned_write_files = list(allowed_write_paths)
    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        },
        {
            "kind": (
                "declare_full_accepted_edit_scope"
                if include_auxiliary_paths
                else "declare_source_test_only_scope"
            ),
            "target": replay_id,
            "payload": {
                "planned_write_files": planned_write_files,
                "included_auxiliary_paths": (
                    list(PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS)
                    if include_auxiliary_paths
                    else []
                ),
                "excluded_auxiliary_paths": (
                    []
                    if include_auxiliary_paths
                    else list(PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS)
                ),
            },
        },
    ]
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    source_materialization: dict[str, object] = {}
    test_config_materialization: dict[str, object] = {}
    test_mark_materialization: dict[str, object] = {}
    auxiliary_materialization: dict[str, object] = {}
    authors_materialization: dict[str, object] = {}
    changelog_materialization: dict[str, object] = {}
    if include_auxiliary_paths and not blockers:
        try:
            authors_materialization = _materialize_pytest_strict_addopts_authors(
                resolved_repo,
                write=write,
            )
            actions.append(_pytest_strict_addopts_authors_action())
        except IssuePrCandidateAttemptError as error:
            authors_materialization = {
                "status": "blocked",
                "target_file": PYTEST_STRICT_ADDOPTS_AUTHORS_PATH,
            }
            blockers.append(error.blocker)

    if include_auxiliary_paths and not blockers:
        try:
            changelog_materialization = _materialize_pytest_strict_addopts_changelog(
                resolved_repo,
                write=write,
            )
            actions.append(_pytest_strict_addopts_changelog_action())
        except IssuePrCandidateAttemptError as error:
            changelog_materialization = {
                "status": "blocked",
                "target_file": PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH,
            }
            blockers.append(error.blocker)

    if include_auxiliary_paths:
        auxiliary_materialization = {
            "status": (
                "materialized"
                if authors_materialization and changelog_materialization
                else "blocked"
            ),
            "targets": [
                authors_materialization,
                changelog_materialization,
            ],
        }

    if not blockers:
        try:
            source_materialization = _materialize_pytest_strict_addopts_source(
                resolved_repo,
                write=write,
            )
            actions.extend(_pytest_strict_addopts_source_actions())
        except IssuePrCandidateAttemptError as error:
            source_materialization = {
                "status": "blocked",
                "target_source_file": PYTEST_STRICT_ADDOPTS_SOURCE_PATH,
            }
            blockers.append(error.blocker)

    if not blockers:
        try:
            test_config_materialization = (
                _materialize_pytest_strict_config_addopts_test(
                    resolved_repo,
                    write=write,
                )
            )
            actions.append(
                {
                    "kind": "pytest_parametrize_existing_test_refine",
                    "target": PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH,
                    "payload": {
                        "test_name": "TestParseIni.test_strict_config_ini_option",
                        "added_case": "addopts = --strict-config",
                    },
                }
            )
        except IssuePrCandidateAttemptError as error:
            test_config_materialization = {
                "status": "blocked",
                "target_test_file": PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH,
            }
            blockers.append(error.blocker)

    if not blockers:
        try:
            test_mark_materialization = _materialize_pytest_strict_markers_addopts_test(
                resolved_repo,
                write=write,
            )
            actions.append(
                {
                    "kind": "pytest_parametrize_existing_test_refine",
                    "target": PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH,
                    "payload": {
                        "test_name": "test_strict_prohibits_unregistered_markers",
                        "added_case": "addopts = --strict-markers",
                    },
                }
            )
        except IssuePrCandidateAttemptError as error:
            test_mark_materialization = {
                "status": "blocked",
                "target_test_file": PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH,
            }
            blockers.append(error.blocker)

    candidate_diff = _candidate_diff(resolved_repo, PYTEST_STRICT_ADDOPTS_ACCEPTED_PATHS)
    changed_files = _string_sequence(candidate_diff.get("changed_files"))
    planned_changed_files = _unique(
        [
            *_string_sequence(authors_materialization.get("planned_changed_files")),
            *_string_sequence(changelog_materialization.get("planned_changed_files")),
            *_source_planned_changed_files(
                source_materialization, PYTEST_STRICT_ADDOPTS_SOURCE_PATH
            ),
            *_string_sequence(test_config_materialization.get("planned_changed_files")),
            *_string_sequence(test_mark_materialization.get("planned_changed_files")),
        ]
    )
    files_changed = changed_files or planned_changed_files
    writes_outside_allowed_scope = _paths_outside_allowlist(
        files_changed,
        allowed_write_paths,
    )
    if writes_outside_allowed_scope:
        blockers.append(
            {
                "field": "mutation_scope",
                "reason": (
                    "writes_outside_accepted_scope"
                    if include_auxiliary_paths
                    else "writes_outside_source_test_scope"
                ),
                "message": (
                    "candidate wrote outside the accepted pytest #14442 scope"
                    if include_auxiliary_paths
                    else "DATA-024 candidate wrote outside the explicit "
                    "source/test-only scope"
                ),
            }
        )
    source_test_missing_paths = [
        path
        for path in PYTEST_STRICT_ADDOPTS_SOURCE_TEST_PATHS
        if path not in files_changed
    ]
    if not blockers and source_test_missing_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "source_test_edit_not_fully_materialized",
                "message": "candidate did not materialize required source/test paths: "
                + ", ".join(source_test_missing_paths),
            }
        )
    auxiliary_missing_paths = [
        path for path in PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS if path not in files_changed
    ]
    if auxiliary_missing_paths:
        if include_auxiliary_paths:
            blockers.append(
                {
                    "field": "candidate_diff",
                    "reason": "accepted_auxiliary_edit_not_fully_materialized",
                    "message": (
                        "DATA-025 full-scope candidate did not materialize: "
                        + ", ".join(auxiliary_missing_paths)
                    ),
                }
            )
        else:
            materialization_gaps.append(
                {
                    "field": "accepted_change.changed_files",
                    "reason": "accepted_auxiliary_paths_not_materialized",
                    "message": (
                        "DATA-024 is explicitly source/test-only and did not "
                        "materialize: "
                        + ", ".join(auxiliary_missing_paths)
                    ),
                }
            )
    accepted_missing_paths = [
        path for path in PYTEST_STRICT_ADDOPTS_ACCEPTED_PATHS if path not in files_changed
    ]
    if include_auxiliary_paths and not blockers and accepted_missing_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "accepted_edit_not_fully_materialized",
                "message": "candidate did not materialize accepted paths: "
                + ", ".join(accepted_missing_paths),
            }
        )

    selected_setup = setup_command or PYTEST_STRICT_ADDOPTS_SETUP_COMMAND
    selected_validation = validation_command or _selected_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
        replay_id=PYTEST_STRICT_ADDOPTS_REPLAY_ID,
        default_command=PYTEST_STRICT_ADDOPTS_VALIDATION_COMMAND,
    )
    validation = _deferred_validation_record(
        setup_command=selected_setup,
        validation_command=selected_validation,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            resolved_repo,
            setup_command=selected_setup,
            validation_command=selected_validation,
            timeout_seconds=validation_timeout_seconds,
        )

    if validation.get("status") == "failed":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_failed",
                "message": "focused pytest #14442 validation command failed",
            }
        )
    elif validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_timeout",
                "message": "focused pytest #14442 validation command timed out",
            }
        )

    structured_action_coverage = _pytest_strict_addopts_structured_action_coverage(
        blockers=blockers,
        materialization_gaps=materialization_gaps,
        files_changed=files_changed,
        validation=validation,
        include_auxiliary_paths=include_auxiliary_paths,
    )
    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation.get("status") == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation.get('status')}"]
        else:
            residual_labels = ["candidate_validation_deferred"]
    residual_labels.extend(gap["reason"] for gap in materialization_gaps)

    status = "blocked" if blockers else "materialized"
    if not blockers and validation.get("status") == "passed":
        status = "validated"
    elif not blockers and not write:
        status = "planned"

    evidence = _evidence_summary(
        readiness_records=readiness_records,
        prompt_spec_records=prompt_spec_records,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
        materialization_audit_records=materialization_audit_records,
        replay_id=PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        repo_before_ref=expected_sha,
        candidate_diff=str(candidate_diff.get("diff", "")),
        validation_status=str(validation.get("status", "")),
    )
    mutation_scope = {
        "mode": (
            "issue_pr_candidate_attempt_full_accepted_scope"
            if include_auxiliary_paths
            else "issue_pr_candidate_attempt_source_test_only"
        ),
        "accepted_write_paths": list(accepted_paths),
        "allowed_write_paths": list(allowed_write_paths),
        "planned_write_files": planned_write_files,
        "included_auxiliary_paths": (
            list(PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS)
            if include_auxiliary_paths
            else []
        ),
        "excluded_auxiliary_paths": (
            [] if include_auxiliary_paths else list(PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS)
        ),
        "files_changed": files_changed,
        "writes_outside_allowlist": writes_outside_allowed_scope,
        "allowed_write_path_check_passed": not writes_outside_allowed_scope,
        "missing_allowed_write_paths": source_test_missing_paths,
        "materialization_gap_paths": auxiliary_missing_paths,
        "accepted_missing_paths": accepted_missing_paths,
        "full_accepted_edit_coverage_expressible": (
            include_auxiliary_paths and not accepted_missing_paths and not blockers
        ),
    }
    return IssuePrCandidateAttempt(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=(
            PYTEST_STRICT_ADDOPTS_FULL_SCOPE_ACTION_FAMILY
            if include_auxiliary_paths
            else PYTEST_STRICT_ADDOPTS_ACTION_FAMILY
        ),
        allowed_write_paths=list(allowed_write_paths),
        evidence=evidence,
        actions=actions,
        auxiliary_materialization=auxiliary_materialization,
        source_materialization=source_materialization,
        test_materialization={
            "status": (
                "materialized"
                if test_config_materialization and test_mark_materialization
                else "blocked"
            ),
            "targets": [
                test_config_materialization,
                test_mark_materialization,
            ],
        },
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        structured_action_coverage=structured_action_coverage,
        blockers=[*blockers, *materialization_gaps],
        residual_labels=_unique(residual_labels),
    )


def run_pytest_timedelta_approx_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    materialization_audit_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Attempt the pytest #14462/#14466 timedelta approx source/test candidate."""

    if replay_id != PYTEST_TIMEDELTA_APPROX_REPLAY_ID:
        raise IssuePrCandidateAttemptError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_candidate",
                "message": (
                    "DATA-029 may attempt only "
                    "pytest-dev__pytest-issue-14462-pr-14466"
                ),
            },
        )
    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrCandidateAttemptError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record["repo_before_ref"])
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record["accepted_change"])
    accepted_paths = _string_sequence(accepted_change.get("changed_files"))
    if accepted_paths != PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta approx candidate allowlist changed unexpectedly",
            blocker={
                "field": "accepted_change.changed_files",
                "reason": "unexpected_allowed_write_scope",
                "message": "DATA-029 expects exactly the pytest #14466 source/test paths",
            },
        )

    blockers: list[dict[str, str]] = []
    allowed_write_paths = list(PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS)
    planned_write_files = list(PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS)
    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        },
        {
            "kind": "declare_source_test_only_scope",
            "target": replay_id,
            "payload": {
                "planned_write_files": planned_write_files,
                "provenance": ["DATA-018", "DATA-026", "DATA-027", "DATA-028"],
            },
        },
    ]
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    source_materialization: dict[str, object] = {}
    test_materialization: dict[str, object] = {}
    if not blockers:
        try:
            source_materialization = _materialize_pytest_timedelta_approx_source(
                resolved_repo,
                write=write,
            )
            actions.extend(_pytest_timedelta_approx_source_actions())
        except IssuePrCandidateAttemptError as error:
            source_materialization = {
                "status": "blocked",
                "target_source_file": PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
            }
            blockers.append(error.blocker)

    if not blockers:
        try:
            test_materialization = _materialize_pytest_timedelta_approx_tests(
                resolved_repo,
                write=write,
            )
            actions.append(_pytest_timedelta_approx_test_action())
        except IssuePrCandidateAttemptError as error:
            test_materialization = {
                "status": "blocked",
                "target_test_file": PYTEST_TIMEDELTA_APPROX_TEST_PATH,
            }
            blockers.append(error.blocker)

    candidate_diff = _candidate_diff(resolved_repo, PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS)
    changed_files = _string_sequence(candidate_diff.get("changed_files"))
    planned_changed_files = _unique(
        [
            *_source_planned_changed_files(
                source_materialization, PYTEST_TIMEDELTA_APPROX_SOURCE_PATH
            ),
            *_string_sequence(test_materialization.get("planned_changed_files")),
        ]
    )
    files_changed = changed_files or planned_changed_files
    writes_outside_allowed_scope = _paths_outside_allowlist(
        files_changed,
        allowed_write_paths,
    )
    if writes_outside_allowed_scope:
        blockers.append(
            {
                "field": "mutation_scope",
                "reason": "writes_outside_source_test_scope",
                "message": "DATA-029 candidate wrote outside the explicit source/test scope",
            }
        )
    missing_allowed_paths = [
        path for path in allowed_write_paths if path not in files_changed
    ]
    if not blockers and missing_allowed_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "source_test_edit_not_fully_materialized",
                "message": "candidate did not materialize required source/test paths: "
                + ", ".join(missing_allowed_paths),
            }
        )

    selected_setup = setup_command or PYTEST_TIMEDELTA_APPROX_SETUP_COMMAND
    selected_validation = validation_command or _selected_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
        replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        default_command=PYTEST_TIMEDELTA_APPROX_VALIDATION_COMMAND,
    )
    validation = _deferred_validation_record(
        setup_command=selected_setup,
        validation_command=selected_validation,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            resolved_repo,
            setup_command=selected_setup,
            validation_command=selected_validation,
            timeout_seconds=validation_timeout_seconds,
        )

    if validation.get("status") == "failed":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_failed",
                "message": "focused pytest #14462 validation command failed",
            }
        )
    elif validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_timeout",
                "message": "focused pytest #14462 validation command timed out",
            }
        )

    structured_action_coverage = _pytest_timedelta_approx_structured_action_coverage(
        blockers=blockers,
        files_changed=files_changed,
        validation=validation,
    )
    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation.get("status") == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation.get('status')}"]
        else:
            residual_labels = ["candidate_validation_deferred"]

    status = "blocked" if blockers else "materialized"
    if not blockers and validation.get("status") == "passed":
        status = "validated"
    elif not blockers and not write:
        status = "planned"

    evidence = _evidence_summary(
        readiness_records=readiness_records,
        prompt_spec_records=prompt_spec_records,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
        materialization_audit_records=materialization_audit_records,
        replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        repo_before_ref=expected_sha,
        candidate_diff=str(candidate_diff.get("diff", "")),
        validation_status=str(validation.get("status", "")),
    )
    mutation_scope = {
        "mode": "issue_pr_candidate_attempt_source_test_only",
        "accepted_write_paths": list(accepted_paths),
        "allowed_write_paths": list(allowed_write_paths),
        "planned_write_files": planned_write_files,
        "included_auxiliary_paths": [],
        "excluded_auxiliary_paths": [],
        "files_changed": files_changed,
        "writes_outside_allowlist": writes_outside_allowed_scope,
        "allowed_write_path_check_passed": not writes_outside_allowed_scope,
        "missing_allowed_write_paths": missing_allowed_paths,
        "materialization_gap_paths": [],
        "accepted_missing_paths": missing_allowed_paths,
        "full_accepted_edit_coverage_expressible": (
            not missing_allowed_paths and not blockers
        ),
    }
    return IssuePrCandidateAttempt(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=PYTEST_TIMEDELTA_APPROX_ACTION_FAMILY,
        allowed_write_paths=list(allowed_write_paths),
        evidence=evidence,
        actions=actions,
        source_materialization=source_materialization,
        test_materialization=test_materialization,
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        structured_action_coverage=structured_action_coverage,
        blockers=blockers,
        residual_labels=_unique(residual_labels),
    )


def run_scrapy_downloader_aware_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    materialization_audit_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Attempt the Scrapy #7293/#7351 downloader-aware queue candidate."""

    if replay_id != SCRAPY_DOWNLOADER_AWARE_REPLAY_ID:
        raise IssuePrCandidateAttemptError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_candidate",
                "message": (
                    "DATA-035 may attempt only "
                    "scrapy__scrapy-issue-7293-pr-7351"
                ),
            },
        )
    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrCandidateAttemptError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record["repo_before_ref"])
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record["accepted_change"])
    accepted_paths = _string_sequence(accepted_change.get("changed_files"))
    if accepted_paths != SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS:
        raise IssuePrCandidateAttemptError(
            "Scrapy downloader-aware candidate allowlist changed unexpectedly",
            blocker={
                "field": "accepted_change.changed_files",
                "reason": "unexpected_allowed_write_scope",
                "message": "DATA-035 expects exactly the Scrapy #7351 source/test paths",
            },
        )

    blockers: list[dict[str, str]] = []
    allowed_write_paths = list(SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS)
    planned_write_files = list(SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS)
    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        },
        {
            "kind": "declare_source_test_only_scope",
            "target": replay_id,
            "payload": {
                "planned_write_files": planned_write_files,
                "provenance": ["DATA-030", "DATA-031", "DATA-033", "DATA-034"],
            },
        },
    ]
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    source_materialization: dict[str, object] = {}
    test_materialization: dict[str, object] = {}
    if not blockers:
        try:
            source_materialization = _materialize_scrapy_downloader_aware_source(
                resolved_repo,
                write=write,
            )
            actions.extend(_scrapy_downloader_aware_source_actions())
        except IssuePrCandidateAttemptError as error:
            source_materialization = {
                "status": "blocked",
                "target_source_file": SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            }
            blockers.append(error.blocker)

    if not blockers:
        try:
            test_materialization = _materialize_scrapy_downloader_aware_tests(
                resolved_repo,
                write=write,
            )
            actions.append(_scrapy_downloader_aware_test_action())
        except IssuePrCandidateAttemptError as error:
            test_materialization = {
                "status": "blocked",
                "target_test_file": SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
            }
            blockers.append(error.blocker)

    candidate_diff = _candidate_diff(
        resolved_repo,
        SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS,
    )
    changed_files = _string_sequence(candidate_diff.get("changed_files"))
    planned_changed_files = _unique(
        [
            *_source_planned_changed_files(
                source_materialization, SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH
            ),
            *_string_sequence(test_materialization.get("planned_changed_files")),
        ]
    )
    files_changed = changed_files or planned_changed_files
    writes_outside_allowed_scope = _paths_outside_allowlist(
        files_changed,
        allowed_write_paths,
    )
    if writes_outside_allowed_scope:
        blockers.append(
            {
                "field": "mutation_scope",
                "reason": "writes_outside_source_test_scope",
                "message": "DATA-035 candidate wrote outside the explicit source/test scope",
            }
        )
    missing_allowed_paths = [
        path for path in allowed_write_paths if path not in files_changed
    ]
    if not blockers and missing_allowed_paths:
        blockers.append(
            {
                "field": "candidate_diff",
                "reason": "source_test_edit_not_fully_materialized",
                "message": "candidate did not materialize required source/test paths: "
                + ", ".join(missing_allowed_paths),
            }
        )

    selected_setup = setup_command or SCRAPY_DOWNLOADER_AWARE_SETUP_COMMAND
    selected_validation = validation_command or _scrapy_downloader_aware_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
    )
    validation = _deferred_validation_record(
        setup_command=selected_setup,
        validation_command=selected_validation,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            resolved_repo,
            setup_command=selected_setup,
            validation_command=selected_validation,
            timeout_seconds=validation_timeout_seconds,
        )

    if validation.get("status") == "failed":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_failed",
                "message": "focused Scrapy #7293 validation command failed",
            }
        )
    elif validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "candidate_validation_timeout",
                "message": "focused Scrapy #7293 validation command timed out",
            }
        )

    structured_action_coverage = _scrapy_downloader_aware_structured_action_coverage(
        blockers=blockers,
        files_changed=files_changed,
        validation=validation,
    )
    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation.get("status") == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation.get('status')}"]
        else:
            residual_labels = ["candidate_validation_deferred"]

    status = "blocked" if blockers else "materialized"
    if not blockers and validation.get("status") == "passed":
        status = "validated"
    elif not blockers and not write:
        status = "planned"

    evidence = _evidence_summary(
        readiness_records=readiness_records,
        prompt_spec_records=prompt_spec_records,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
        materialization_audit_records=materialization_audit_records,
        replay_id=SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        repo_before_ref=expected_sha,
        candidate_diff=str(candidate_diff.get("diff", "")),
        validation_status=str(validation.get("status", "")),
    )
    mutation_scope = {
        "mode": "issue_pr_candidate_attempt_source_test_only",
        "accepted_write_paths": list(accepted_paths),
        "allowed_write_paths": list(allowed_write_paths),
        "planned_write_files": planned_write_files,
        "included_auxiliary_paths": [],
        "excluded_auxiliary_paths": [],
        "files_changed": files_changed,
        "writes_outside_allowlist": writes_outside_allowed_scope,
        "allowed_write_path_check_passed": not writes_outside_allowed_scope,
        "missing_allowed_write_paths": missing_allowed_paths,
        "materialization_gap_paths": [],
        "accepted_missing_paths": missing_allowed_paths,
        "full_accepted_edit_coverage_expressible": (
            not missing_allowed_paths and not blockers
        ),
    }
    return IssuePrCandidateAttempt(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=SCRAPY_DOWNLOADER_AWARE_ACTION_FAMILY,
        allowed_write_paths=list(allowed_write_paths),
        evidence=evidence,
        actions=actions,
        source_materialization=source_materialization,
        test_materialization=test_materialization,
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        structured_action_coverage=structured_action_coverage,
        blockers=blockers,
        residual_labels=_unique(residual_labels),
    )


def run_issue_pr_candidate_attempt(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = REQUESTS_REPLAY_ID,
    readiness_records: Sequence[Mapping[str, object]] = (),
    prompt_spec_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    materialization_audit_records: Sequence[Mapping[str, object]] = (),
    setup_command: str | None = None,
    validation_command: str | None = None,
    write: bool = True,
    validate: bool = False,
    include_pytest_auxiliaries: bool = False,
    validation_timeout_seconds: int = 120,
) -> IssuePrCandidateAttempt:
    """Dispatch to the bounded candidate attempt for a supported replay id."""

    if replay_id == REQUESTS_REPLAY_ID:
        return run_requests_issue_pr_candidate_attempt(
            repo_path,
            manifest_path=manifest_path,
            replay_id=replay_id,
            readiness_records=readiness_records,
            prompt_spec_records=prompt_spec_records,
            validation_records=validation_records,
            local_knowledge_records=local_knowledge_records,
            setup_command=setup_command,
            validation_command=validation_command,
            write=write,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    if replay_id == CLICK_DEFAULT_MAP_REPLAY_ID:
        return run_click_default_map_issue_pr_candidate_attempt(
            repo_path,
            manifest_path=manifest_path,
            replay_id=replay_id,
            readiness_records=readiness_records,
            prompt_spec_records=prompt_spec_records,
            validation_records=validation_records,
            local_knowledge_records=local_knowledge_records,
            setup_command=setup_command,
            validation_command=validation_command,
            write=write,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    if replay_id == CLICK_SEMVER_REPLAY_ID:
        return run_click_semver_issue_pr_candidate_attempt(
            repo_path,
            manifest_path=manifest_path,
            replay_id=replay_id,
            readiness_records=readiness_records,
            prompt_spec_records=prompt_spec_records,
            validation_records=validation_records,
            local_knowledge_records=local_knowledge_records,
            setup_command=setup_command,
            validation_command=validation_command,
            write=write,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    if replay_id == PYTEST_STRICT_ADDOPTS_REPLAY_ID:
        return run_pytest_strict_addopts_issue_pr_candidate_attempt(
            repo_path,
            manifest_path=manifest_path,
            replay_id=replay_id,
            readiness_records=readiness_records,
            prompt_spec_records=prompt_spec_records,
            validation_records=validation_records,
            local_knowledge_records=local_knowledge_records,
            materialization_audit_records=materialization_audit_records,
            setup_command=setup_command,
            validation_command=validation_command,
            write=write,
            validate=validate,
            include_auxiliary_paths=include_pytest_auxiliaries,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    if replay_id == PYTEST_TIMEDELTA_APPROX_REPLAY_ID:
        return run_pytest_timedelta_approx_issue_pr_candidate_attempt(
            repo_path,
            manifest_path=manifest_path,
            replay_id=replay_id,
            readiness_records=readiness_records,
            prompt_spec_records=prompt_spec_records,
            validation_records=validation_records,
            local_knowledge_records=local_knowledge_records,
            materialization_audit_records=materialization_audit_records,
            setup_command=setup_command,
            validation_command=validation_command,
            write=write,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    if replay_id == SCRAPY_DOWNLOADER_AWARE_REPLAY_ID:
        return run_scrapy_downloader_aware_issue_pr_candidate_attempt(
            repo_path,
            manifest_path=manifest_path,
            replay_id=replay_id,
            readiness_records=readiness_records,
            prompt_spec_records=prompt_spec_records,
            validation_records=validation_records,
            local_knowledge_records=local_knowledge_records,
            materialization_audit_records=materialization_audit_records,
            setup_command=setup_command,
            validation_command=validation_command,
            write=write,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    raise IssuePrCandidateAttemptError(
        f"unsupported replay id: {replay_id}",
        blocker={
            "field": "replay_id",
            "reason": "unsupported_issue_pr_candidate",
            "message": (
                "supported candidate attempts are DATA-012 Requests, DATA-014 "
                "Click default_map, DATA-016 Click semver default, and DATA-024 "
                "pytest strict addopts, DATA-029 pytest timedelta approx, and "
                "DATA-035 Scrapy downloader-aware queue"
            ),
        },
    )


def validate_issue_pr_candidate(
    repo_path: Path,
    *,
    setup_command: str,
    validation_command: str,
    timeout_seconds: int = 120,
) -> dict[str, object]:
    """Run setup plus focused validation for one candidate checkout."""

    setup = _run_shell(
        repo_path,
        setup_command,
        name="setup",
        timeout_seconds=timeout_seconds,
    )
    validation: dict[str, object] | None = None
    if setup["status"] == "passed":
        validation = _run_shell(
            repo_path,
            validation_command,
            name="validation",
            timeout_seconds=timeout_seconds,
        )
    status = "passed" if validation and validation["status"] == "passed" else "failed"
    if setup["status"] == "timeout" or (
        validation is not None and validation["status"] == "timeout"
    ):
        status = "timeout"
    return {
        "status": status,
        "setup_command": setup_command,
        "validation_command": validation_command,
        "commands": [setup] + ([validation] if validation is not None else []),
        "runtime_seconds": round(
            float(setup.get("runtime_seconds", 0.0))
            + float((validation or {}).get("runtime_seconds", 0.0)),
            3,
        ),
        "setup_network_allowed": True,
        "candidate_validation_network_allowed": False,
    }


def write_issue_pr_candidate_attempt_json(
    attempt: IssuePrCandidateAttempt | Mapping[str, object],
    path: Path,
) -> Path:
    """Write one candidate attempt record to JSON."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    record = (
        attempt.to_record()
        if isinstance(attempt, IssuePrCandidateAttempt)
        else dict(attempt)
    )
    resolved.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved


def write_issue_pr_candidate_attempt_report(
    attempt: IssuePrCandidateAttempt | Mapping[str, object],
    path: Path,
) -> Path:
    """Write a compact Markdown report for the candidate attempt."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    record = (
        attempt.to_record()
        if isinstance(attempt, IssuePrCandidateAttempt)
        else dict(attempt)
    )
    mutation_scope = _mapping(record.get("mutation_scope"))
    validation = _mapping(record.get("validation"))
    coverage = _mapping(record.get("structured_action_coverage"))
    title = (
        "DATA-014 Click default_map Issue/PR Candidate Attempt"
        if record.get("replay_id") == CLICK_DEFAULT_MAP_REPLAY_ID
        else "DATA-016 Click semver Issue/PR Candidate Attempt"
        if record.get("replay_id") == CLICK_SEMVER_REPLAY_ID
        else "DATA-025 Pytest #14442 Full-Scope Candidate Attempt"
        if record.get("action_family") == PYTEST_STRICT_ADDOPTS_FULL_SCOPE_ACTION_FAMILY
        else "DATA-024 Pytest #14442 Source/Test Candidate Attempt"
        if record.get("replay_id") == PYTEST_STRICT_ADDOPTS_REPLAY_ID
        else "DATA-029 Pytest #14462 Source/Test Candidate Attempt"
        if record.get("replay_id") == PYTEST_TIMEDELTA_APPROX_REPLAY_ID
        else "DATA-035 Scrapy #7293 Source/Test Candidate Attempt"
        if record.get("replay_id") == SCRAPY_DOWNLOADER_AWARE_REPLAY_ID
        else "DATA-012 Requests Issue/PR Candidate Attempt"
    )
    lines = [
        f"# {title}",
        "",
        "No hosted LLM source generation was used.",
        "",
        "## Summary",
        "",
        f"- Replay: `{record.get('replay_id')}`",
        f"- Status: `{record.get('status')}`",
        f"- Residual labels: `{_json_inline(record.get('residual_labels', []))}`",
        f"- Files changed: `{_json_inline(mutation_scope.get('files_changed', []))}`",
        "- Writes outside allowlist: "
        f"`{_json_inline(mutation_scope.get('writes_outside_allowlist', []))}`",
        f"- Validation status: `{validation.get('status')}`",
        f"- Validation runtime: `{validation.get('runtime_seconds', 0.0)}` seconds",
        "- Accepted edit covered by current bounded surface: "
        f"`{str(coverage.get('accepted_edit_covered')).lower()}`",
        "",
        "## Structured Action Coverage",
        "",
        f"- Coverage labels: `{_json_inline(coverage.get('coverage_labels', []))}`",
        f"- Materialization gap: `{coverage.get('materialization_gap')}`",
        f"- Note: {coverage.get('note')}",
        "",
        "## Candidate Diff",
        "",
        "```diff",
        str(_mapping(record.get("candidate_diff")).get("diff", "")),
        "```",
    ]
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolved


def load_jsonl_many(paths: Sequence[Path]) -> tuple[dict[str, object], ...]:
    """Load optional JSONL evidence records."""

    rows: list[dict[str, object]] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            continue
        for line_number, line in enumerate(
            resolved.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{resolved}:{line_number}: row must be an object")
            row.setdefault("_source_path", str(resolved))
            rows.append(row)
    return tuple(rows)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for supported bounded issue/PR candidate attempts."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--replay-id", default=REQUESTS_REPLAY_ID)
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--readiness-evidence", type=Path, action="append", default=[])
    parser.add_argument("--prompt-spec-evidence", type=Path, action="append", default=[])
    parser.add_argument("--validation-evidence", type=Path, action="append", default=[])
    parser.add_argument("--local-knowledge-evidence", type=Path, action="append", default=[])
    parser.add_argument(
        "--materialization-audit-evidence",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--setup-command", default=REQUESTS_SETUP_COMMAND)
    parser.add_argument("--validation-command", default=REQUESTS_VALIDATION_COMMAND)
    parser.add_argument("--validation-timeout-seconds", type=int, default=120)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--include-pytest-auxiliaries",
        action="store_true",
        help=(
            "For pytest #14442 only, materialize AUTHORS and the changelog "
            "fragment with the DATA-024 source/test candidate."
        ),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    setup_command = args.setup_command
    validation_command = args.validation_command
    if args.replay_id == CLICK_DEFAULT_MAP_REPLAY_ID:
        if setup_command == REQUESTS_SETUP_COMMAND:
            setup_command = CLICK_DEFAULT_MAP_SETUP_COMMAND
        if validation_command == REQUESTS_VALIDATION_COMMAND:
            validation_command = CLICK_DEFAULT_MAP_VALIDATION_COMMAND
    elif args.replay_id == CLICK_SEMVER_REPLAY_ID:
        if setup_command == REQUESTS_SETUP_COMMAND:
            setup_command = CLICK_SEMVER_SETUP_COMMAND
        if validation_command == REQUESTS_VALIDATION_COMMAND:
            validation_command = CLICK_SEMVER_VALIDATION_COMMAND
    elif args.replay_id == PYTEST_STRICT_ADDOPTS_REPLAY_ID:
        if setup_command == REQUESTS_SETUP_COMMAND:
            setup_command = PYTEST_STRICT_ADDOPTS_SETUP_COMMAND
        if validation_command == REQUESTS_VALIDATION_COMMAND:
            validation_command = PYTEST_STRICT_ADDOPTS_VALIDATION_COMMAND
    elif args.replay_id == PYTEST_TIMEDELTA_APPROX_REPLAY_ID:
        if setup_command == REQUESTS_SETUP_COMMAND:
            setup_command = PYTEST_TIMEDELTA_APPROX_SETUP_COMMAND
        if validation_command == REQUESTS_VALIDATION_COMMAND:
            validation_command = PYTEST_TIMEDELTA_APPROX_VALIDATION_COMMAND
    elif args.replay_id == SCRAPY_DOWNLOADER_AWARE_REPLAY_ID:
        if setup_command == REQUESTS_SETUP_COMMAND:
            setup_command = SCRAPY_DOWNLOADER_AWARE_SETUP_COMMAND
        if validation_command == REQUESTS_VALIDATION_COMMAND:
            validation_command = SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND

    attempt = run_issue_pr_candidate_attempt(
        args.repo_path,
        manifest_path=args.manifest,
        replay_id=args.replay_id,
        readiness_records=load_jsonl_many(args.readiness_evidence),
        prompt_spec_records=load_jsonl_many(args.prompt_spec_evidence),
        validation_records=load_jsonl_many(args.validation_evidence),
        local_knowledge_records=load_jsonl_many(args.local_knowledge_evidence),
        materialization_audit_records=load_jsonl_many(
            args.materialization_audit_evidence
        ),
        setup_command=setup_command,
        validation_command=validation_command,
        write=not args.plan_only,
        validate=args.validate,
        include_pytest_auxiliaries=args.include_pytest_auxiliaries,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    out_path = write_issue_pr_candidate_attempt_json(attempt, args.out)
    report_path = None
    if args.report is not None:
        report_path = write_issue_pr_candidate_attempt_report(attempt, args.report)
    summary = {
        "record_kind": "issue_pr_candidate_attempt_summary",
        "replay_id": attempt.replay_id,
        "status": attempt.status,
        "residual_labels": attempt.residual_labels,
        "out_path": str(out_path),
        "report_path": str(report_path) if report_path else None,
        "validation_status": attempt.validation.get("status"),
        "files_changed": attempt.mutation_scope.get("files_changed"),
        "zero_hosted_usage_confirmed": attempt.zero_hosted_usage_confirmed,
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if attempt.status != "blocked" else 1


def _requests_prepare_body_stream_detection_action(source: str) -> SourceRegionAction:
    if (
        "is_iterable = isinstance(data, Iterable) or hasattr(data, \"__iter__\")"
        in source
    ):
        raise SourceRegionMaterializationError(
            "Requests prepare_body getattr stream edit is already applied",
            residual="already_applied",
        )
    start_line = _line_number(
        source,
        "        if isinstance(data, Iterable) and not isinstance(",
    )
    end_line = _line_number_after(source, "        ):", start_line=start_line)
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=REQUESTS_SOURCE_PATH,
            function_name="prepare_body",
            region_name="getattr_proxy_stream_detection",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source="\n".join(
            [
                "        # data that proxies attributes to underlying objects needs hasattr",
                '        is_iterable = isinstance(data, Iterable) or hasattr(data, "__iter__")',
                "        if is_iterable and not isinstance(data, (str, bytes, list, tuple, Mapping)):",
            ]
        ),
        constraints=SourceRegionConstraints(max_changed_source_lines=8),
        rationale=(
            "stream wrappers that expose __iter__ through __getattr__ must enter "
            "the streamed-body branch so redirects can rewind the body"
        ),
    )


def _click_default_map_string_split_action(source: str) -> SourceRegionAction:
    if "value = self.type.split_envvar_value(value)" in source:
        raise SourceRegionMaterializationError(
            "Click default_map string splitting edit is already applied",
            residual="already_applied",
        )
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_DELIMITED_REGION,
        target=SourceRegionTarget(
            file_path=CLICK_DEFAULT_MAP_SOURCE_PATH,
            region_name="default_map_multi_value_string_split",
            start_marker="            default_map_value = ctx.lookup_default(self.name)",
            end_marker="        if value is UNSET:",
        ),
        replacement_source="\n".join(
            [
                "            if default_map_value is not None or ctx._default_map_has(self.name):",
                "                value = default_map_value",
                "                source = ParameterSource.DEFAULT_MAP",
                "",
                "                # A string from default_map must be split for multi-value",
                "                # parameters, matching value_from_envvar behavior.",
                "                if isinstance(value, str) and self.nargs != 1:",
                "                    value = self.type.split_envvar_value(value)",
                "",
            ]
        ),
        constraints=SourceRegionConstraints(
            max_changed_source_lines=8,
            must_preserve_signature=False,
        ),
        rationale=(
            "string default_map values for multi-value options must follow the "
            "same splitting path as environment variable values before type casting"
        ),
    )


def _click_semver_empty_string_guard_action(source: str) -> SourceRegionAction:
    accepted_line = (
        '            elif isinstance(default_value, str) and default_value == "":'
    )
    if accepted_line in source:
        raise SourceRegionMaterializationError(
            "Click semver empty-string guard edit is already applied",
            residual="already_applied",
        )
    target_line = '            elif default_value == "":'
    line_number = _line_number(source, target_line)
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=CLICK_SEMVER_SOURCE_PATH,
            function_name="get_help_extra",
            region_name="non_string_default_empty_string_guard",
            start_line=line_number,
            end_line=line_number,
        ),
        replacement_source=accepted_line,
        constraints=SourceRegionConstraints(max_changed_source_lines=2),
        rationale=(
            "the empty-string display branch must be string-specific so arbitrary "
            "non-string default objects can fall through to str(default_value)"
        ),
    )


def _materialize_requests_redirect_stream_test(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, REQUESTS_TEST_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    if "def test_getattr_proxy_stream_follows_redirect" in before_text:
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=REQUESTS_TEST_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )
    marker = "    def _patch_adapter_gzipped_redirect(self, session, url):"
    if marker not in before_text:
        raise IssuePrCandidateAttemptError(
            "Requests redirect test insertion anchor not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_anchor_not_found",
                "message": "could not find _patch_adapter_gzipped_redirect anchor",
            },
        )
    test_source = "\n".join(
        [
            "    def test_getattr_proxy_stream_follows_redirect(self, httpbin):",
            "        \"\"\"Ensure stream wrappers that don't implement __iter__ directly are still detected.\"\"\"",
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
            "",
            "",
        ]
    )
    after_text = before_text.replace(marker, test_source + marker, 1)
    planned_changed_files = [REQUESTS_TEST_PATH] if after_text != before_text else []
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    return _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=REQUESTS_TEST_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _materialize_click_default_map_nargs_test(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, CLICK_DEFAULT_MAP_TEST_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    if "def test_default_map_nargs(" in before_text:
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=CLICK_DEFAULT_MAP_TEST_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )
    marker = "def test_unset_in_default_map(runner):"
    if marker not in before_text:
        raise IssuePrCandidateAttemptError(
            "Click default_map test insertion anchor not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_anchor_not_found",
                "message": "could not find test_unset_in_default_map anchor",
            },
        )
    test_source = "\n".join(
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
            "",
            "",
            "",
        ]
    )
    after_text = before_text.replace(marker, test_source + marker, 1)
    planned_changed_files = [CLICK_DEFAULT_MAP_TEST_PATH] if after_text != before_text else []
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    return _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=CLICK_DEFAULT_MAP_TEST_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _materialize_click_semver_default_help_test(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, CLICK_SEMVER_TEST_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    if "class _StrictEq:" in before_text and "non-string-comparable-object" in before_text:
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=CLICK_SEMVER_TEST_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    old_test = "\n".join(
        [
            "def test_show_default_with_empty_string(runner):",
            '    """When show_default is True and default is set to an empty string."""',
            '    opt = click.Option(["--limit"], default="", show_default=True)',
            '    ctx = click.Context(click.Command("cli"))',
            "    message = opt.get_help_record(ctx)[1]",
            '    assert \'[default: ""]\' in message',
        ]
    )
    if old_test not in before_text:
        raise IssuePrCandidateAttemptError(
            "Click semver test replacement anchor not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_anchor_not_found",
                "message": (
                    "could not find test_show_default_with_empty_string empty-string "
                    "test body"
                ),
            },
        )

    new_test = "\n".join(
        [
            "class _StrictEq:",
            '    """Object whose ``__eq__`` raises on string comparison (like semver.Version)."""',
            "",
            "    def __eq__(self, other):",
            "        if isinstance(other, str):",
            '            raise ValueError("cannot compare to string")',
            "        return NotImplemented",
            "",
            "    def __str__(self):",
            '        return "strict"',
            "",
            "",
            "@pytest.mark.parametrize(",
            '    ("default", "expected"),',
            "    [",
            '        ("", \'[default: ""]\'),',
            '        (_StrictEq(), "[default: strict]"),',
            "    ],",
            '    ids=["empty-string", "non-string-comparable-object"],',
            ")",
            "def test_show_default_with_empty_string(runner, default, expected):",
            '    """The empty-string check in help rendering must not break on objects',
            "    whose ``__eq__`` raises for string operands.",
            "",
            "    Regression test for https://github.com/pallets/click/issues/3298.",
            '    """',
            '    opt = click.Option(["--limit"], default=default, show_default=True)',
            '    ctx = click.Context(click.Command("cli"))',
            "    message = opt.get_help_record(ctx)[1]",
            "    assert expected in message",
        ]
    )
    after_text = before_text.replace(old_test, new_test, 1)
    planned_changed_files = [CLICK_SEMVER_TEST_PATH] if after_text != before_text else []
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    return _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=CLICK_SEMVER_TEST_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _pytest_strict_addopts_source_actions() -> list[dict[str, object]]:
    return [
        {
            "kind": "python_from_import_insert",
            "target": PYTEST_STRICT_ADDOPTS_SOURCE_PATH,
            "payload": {
                "module": ".findpaths",
                "name": "parse_override_ini",
                "after_import": "from .findpaths import determine_setup",
            },
        },
        {
            "kind": "config_parse_addopts_override_source_region",
            "target": PYTEST_STRICT_ADDOPTS_SOURCE_PATH,
            "payload": {
                "function_name": "Config.parse",
                "anchor": "post_addopts_parse_known_args",
                "effect": "update _inicfg from addopts-supplied override_ini once",
            },
        },
    ]


def _pytest_strict_addopts_authors_action() -> dict[str, object]:
    return {
        "kind": "newline_delimited_sorted_unique_insert",
        "target": PYTEST_STRICT_ADDOPTS_AUTHORS_PATH,
        "payload": {
            "entries": list(PYTEST_STRICT_ADDOPTS_AUTHOR_ENTRIES),
            "sort_key": "casefold",
            "provenance": ["DATA-021", "DATA-023", "DATA-024", "DATA-025"],
        },
    }


def _pytest_strict_addopts_changelog_action() -> dict[str, object]:
    return {
        "kind": "towncrier_fragment_create",
        "target": PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH,
        "payload": {
            "issue_number": 14442,
            "fragment_type": "bugfix",
            "content_source": "pytest_strict_addopts_changelog_fragment_v1",
            "provenance": ["DATA-021", "DATA-023", "DATA-024", "DATA-025"],
        },
    }


def _materialize_pytest_strict_addopts_authors(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    authors_path = _repo_file(repo_path, PYTEST_STRICT_ADDOPTS_AUTHORS_PATH)
    if not authors_path.exists():
        raise IssuePrCandidateAttemptError(
            "pytest AUTHORS file not found",
            blocker={
                "field": "auxiliary_materialization",
                "reason": "authors_file_not_found",
                "message": "could not find AUTHORS in the pytest checkout",
            },
        )
    before_text = authors_path.read_text(encoding="utf-8")
    before_lines = before_text.splitlines()
    existing = set(before_lines)
    missing_entries = [
        entry for entry in PYTEST_STRICT_ADDOPTS_AUTHOR_ENTRIES if entry not in existing
    ]
    if not missing_entries:
        return _text_file_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_file=PYTEST_STRICT_ADDOPTS_AUTHORS_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
            metadata={
                "inserted_entries": [],
                "sort_key": "contributors_section_ascii_casefold",
            },
        )

    after_lines = list(before_lines)
    for entry in sorted(missing_entries, key=str.casefold):
        entry_key = _authors_sort_key(entry)
        insert_at = len(after_lines)
        for index, line in enumerate(after_lines):
            if index < _authors_contributor_start_line(after_lines):
                continue
            if line.strip() and _authors_sort_key(line) > entry_key:
                insert_at = index
                break
        after_lines.insert(insert_at, entry)
    after_text = "\n".join(after_lines) + ("\n" if before_text.endswith("\n") else "")
    planned_changed_files = (
        [PYTEST_STRICT_ADDOPTS_AUTHORS_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        authors_path.write_text(after_text, encoding="utf-8")
    return _text_file_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_file=PYTEST_STRICT_ADDOPTS_AUTHORS_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
        metadata={
            "inserted_entries": missing_entries,
            "sort_key": "contributors_section_ascii_casefold",
        },
    )


def _materialize_pytest_strict_addopts_changelog(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    changelog_path = _repo_file(repo_path, PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH)
    changelog_dir = changelog_path.parent
    if not changelog_dir.is_dir():
        raise IssuePrCandidateAttemptError(
            "pytest changelog directory not found",
            blocker={
                "field": "auxiliary_materialization",
                "reason": "changelog_directory_not_found",
                "message": "could not find changelog/ in the pytest checkout",
            },
        )
    before_text = (
        changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    )
    after_text = PYTEST_STRICT_ADDOPTS_CHANGELOG_TEXT
    if before_text == after_text:
        return _text_file_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_file=PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
            metadata={
                "issue_number": 14442,
                "fragment_type": "bugfix",
                "created_new_file": False,
            },
        )
    if before_text:
        raise IssuePrCandidateAttemptError(
            "pytest changelog fragment already exists with different content",
            blocker={
                "field": "auxiliary_materialization",
                "reason": "changelog_fragment_conflict",
                "message": (
                    "changelog/14442.bugfix.rst exists and does not match the "
                    "DATA-025 deterministic fragment"
                ),
            },
        )
    if write:
        changelog_path.write_text(after_text, encoding="utf-8")
    return _text_file_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_file=PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH,
        planned_changed_files=[PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH],
        wrote_file=write,
        status="materialized",
        metadata={
            "issue_number": 14442,
            "fragment_type": "bugfix",
            "created_new_file": True,
        },
    )


def _authors_contributor_start_line(lines: Sequence[str]) -> int:
    for index, line in enumerate(lines):
        if line == "Contributors include::":
            return index + 1
    return 0


def _authors_sort_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_value.casefold()


def _materialize_pytest_strict_addopts_source(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    source_path = _repo_file(repo_path, PYTEST_STRICT_ADDOPTS_SOURCE_PATH)
    before_text = source_path.read_text(encoding="utf-8")
    after_text = before_text

    import_line = "from .findpaths import parse_override_ini\n"
    if import_line not in after_text:
        anchor = "from .findpaths import determine_setup\n"
        if anchor not in after_text:
            raise IssuePrCandidateAttemptError(
                "pytest strict addopts import anchor not found",
                blocker={
                    "field": "source_materialization",
                    "reason": "source_import_anchor_not_found",
                    "message": "could not find determine_setup import anchor",
                },
            )
        after_text = after_text.replace(anchor, anchor + import_line, 1)

    override_block = "\n".join(
        [
            "        if addopts:",
            "            # addopts may have added overrides (especially via OverrideIniAction).",
            "            # The thing can be endlessly circular but we only do one level (#14442).",
            "            if overrides := parse_override_ini(self.known_args_namespace.override_ini):",
            "                self._inicfg.update(overrides)",
            "                self._inicache.clear()",
        ]
    )
    if override_block not in after_text:
        old_block = "\n".join(
            [
                "        self.known_args_namespace = self._parser.parse_known_args(",
                "            args, namespace=copy.copy(self.option)",
                "        )",
                "        self._checkversion()",
            ]
        )
        new_block = "\n".join(
            [
                "        self.known_args_namespace = self._parser.parse_known_args(",
                "            args, namespace=copy.copy(self.option)",
                "        )",
                override_block,
                "        self._checkversion()",
            ]
        )
        if old_block not in after_text:
            raise IssuePrCandidateAttemptError(
                "pytest strict addopts Config.parse anchor not found",
                blocker={
                    "field": "source_materialization",
                    "reason": "source_region_anchor_not_found",
                    "message": (
                        "could not find post-addopts parse_known_args anchor in "
                        "Config.parse"
                    ),
                },
            )
        after_text = after_text.replace(old_block, new_block, 1)

    planned_changed_files = (
        [PYTEST_STRICT_ADDOPTS_SOURCE_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        source_path.write_text(after_text, encoding="utf-8")
    return _python_source_candidate_after(
        before_text=before_text,
        after_text=after_text,
        source_file=PYTEST_STRICT_ADDOPTS_SOURCE_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "already_applied",
    )


def _materialize_pytest_strict_config_addopts_test(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    if '"addopts = --strict-config"' in before_text:
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    old_test = "\n".join(
        [
            '    @pytest.mark.parametrize("option_name", ["strict_config", "strict"])',
            "    def test_strict_config_ini_option(",
            "        self, pytester: Pytester, option_name: str",
            "    ) -> None:",
            "        \"\"\"Test that strict_config and strict ini options enable strict config checking.\"\"\"",
            "        pytester.makeini(",
            "            f\"\"\"",
            "            [pytest]",
            "            unknown_option = 1",
            "            {option_name} = True",
            "            \"\"\"",
            "        )",
            "        result = pytester.runpytest()",
            "        result.stderr.fnmatch_lines(\"ERROR: Unknown config option: unknown_option\")",
            "        assert result.ret == pytest.ExitCode.USAGE_ERROR",
        ]
    )
    new_test = "\n".join(
        [
            "    @pytest.mark.parametrize(",
            '        "option",',
            "        [",
            '            "strict_config = true",',
            '            "strict = true",',
            '            "addopts = --strict-config",',
            "        ],",
            "    )",
            "    def test_strict_config_ini_option(self, pytester: Pytester, option: str) -> None:",
            "        \"\"\"Test that strict_config and strict ini options enable strict config checking.\"\"\"",
            "        pytester.makeini(",
            "            f\"\"\"",
            "            [pytest]",
            "            unknown_option = 1",
            "            {option}",
            "            \"\"\"",
            "        )",
            "        result = pytester.runpytest()",
            "        result.stderr.fnmatch_lines(\"ERROR: Unknown config option: unknown_option\")",
            "        assert result.ret == pytest.ExitCode.USAGE_ERROR",
        ]
    )
    if old_test not in before_text:
        raise IssuePrCandidateAttemptError(
            "pytest strict config test replacement anchor not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_anchor_not_found",
                "message": "could not find TestParseIni.test_strict_config_ini_option",
            },
        )
    after_text = before_text.replace(old_test, new_test, 1)
    planned_changed_files = (
        [PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    return _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _materialize_pytest_strict_markers_addopts_test(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    if '"addopts = --strict-markers"' in before_text:
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    old_test = "\n".join(
        [
            "@pytest.mark.parametrize(",
            '    "option_name", ["--strict-markers", "--strict", "strict_markers", "strict"]',
            ")",
            "def test_strict_prohibits_unregistered_markers(",
            "    pytester: Pytester, option_name: str",
            ") -> None:",
            "    pytester.makepyfile(",
            "        \"\"\"",
            "        import pytest",
            "        @pytest.mark.unregisteredmark",
            "        def test_hello():",
            "            pass",
            "    \"\"\"",
            "    )",
            '    if option_name in ("strict_markers", "strict"):',
            "        pytester.makeini(",
            "            f\"\"\"",
            "            [pytest]",
            "            {option_name} = true",
            "            \"\"\"",
            "        )",
            "        result = pytester.runpytest()",
            "    else:",
            "        result = pytester.runpytest(option_name)",
            "    assert result.ret != 0",
            "    result.stdout.fnmatch_lines(",
            "        [\"'unregisteredmark' not found in `markers` configuration option\"]",
            "    )",
        ]
    )
    new_test = "\n".join(
        [
            "@pytest.mark.parametrize(",
            '    "option",',
            "    [",
            '        "--strict-markers",',
            '        "--strict",',
            '        "strict_markers = true",',
            '        "strict = true",',
            '        "addopts = --strict-markers",',
            "    ],",
            ")",
            "def test_strict_prohibits_unregistered_markers(pytester: Pytester, option: str) -> None:",
            "    pytester.makepyfile(",
            "        \"\"\"",
            "        import pytest",
            "        @pytest.mark.unregisteredmark",
            "        def test_hello():",
            "            pass",
            "    \"\"\"",
            "    )",
            '    if option.startswith("-"):',
            "        result = pytester.runpytest(option)",
            "    else:",
            "        pytester.makeini(",
            "            f\"\"\"",
            "            [pytest]",
            "            {option}",
            "            \"\"\"",
            "        )",
            "        result = pytester.runpytest()",
            "    assert result.ret != 0",
            "    result.stdout.fnmatch_lines(",
            "        [\"'unregisteredmark' not found in `markers` configuration option\"]",
            "    )",
        ]
    )
    if old_test not in before_text:
        raise IssuePrCandidateAttemptError(
            "pytest strict markers test replacement anchor not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_anchor_not_found",
                "message": "could not find test_strict_prohibits_unregistered_markers",
            },
        )
    after_text = before_text.replace(old_test, new_test, 1)
    planned_changed_files = (
        [PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    return _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _pytest_timedelta_approx_source_actions() -> list[dict[str, object]]:
    return [
        {
            "kind": "python_dispatch_branch_insert",
            "target": PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
            "payload": {
                "class_name": "ApproxBase",
                "method_name": "_approx_scalar",
                "branch": "datetime_or_timedelta_to_ApproxTimedelta",
                "provenance": ["DATA-026", "DATA-028", "DATA-029"],
            },
        },
        {
            "kind": "pytest_approx_timedelta_source_region_update",
            "target": PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
            "payload": {
                "class_name": "ApproxTimedelta",
                "method_name": "__init__",
                "rel_semantics": "numeric_fraction_times_abs_expected",
                "preserve_datetime_rel_rejection": True,
                "provenance": ["DATA-026", "DATA-028", "DATA-029"],
            },
        },
        {
            "kind": "python_docstring_region_update",
            "target": PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
            "payload": {
                "function_name": "approx",
                "topic": "datetime_timedelta_rel_abs_policy",
                "provenance": ["DATA-028", "DATA-029"],
            },
        },
    ]


def _pytest_timedelta_approx_test_action() -> dict[str, object]:
    return {
        "kind": "pytest_existing_class_method_refine_and_insert",
        "target": PYTEST_TIMEDELTA_APPROX_TEST_PATH,
        "payload": {
            "class_name": "TestApproxDatetime",
            "refined_methods": [
                "test_timedelta_rel_within_tolerance",
                "test_timedelta_rel_outside_tolerance",
                "test_timedelta_rel_must_be_timedelta",
            ],
            "inserted_methods": [
                "test_timedelta_rel_must_be_non_negative",
                "test_timedelta_rel_must_not_be_nan",
                "test_timedelta_abs_must_be_non_negative",
                "test_timedelta_rel_with_abs",
                "test_timedelta_rel_zero",
                "test_timedelta_rel_scales_with_expected",
                "test_timedelta_in_sequence",
                "test_timedelta_in_mapping",
                "test_datetime_in_sequence",
                "test_datetime_in_mapping",
            ],
            "provenance": ["DATA-026", "DATA-028", "DATA-029"],
        },
    }


def _materialize_pytest_timedelta_approx_source(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    source_path = _repo_file(repo_path, PYTEST_TIMEDELTA_APPROX_SOURCE_PATH)
    before_text = source_path.read_text(encoding="utf-8")
    after_text = before_text
    accepted_markers = [
        "    def _approx_scalar(self, x) -> ApproxBase:",
        "        if isinstance(x, (datetime, timedelta)):",
        "    Requires an explicit tolerance as a timedelta for abs, or a float for rel.",
        '                    f"number, got {type(rel).__name__}"',
        "        rel_tolerance = rel * builtins.abs(expected) if rel is not None else None",
        "        super().__init__(expected, rel=rel, abs=tolerance, nan_ok=False)",
        "    For timedelta comparisons, ``rel`` is a number (not a timedelta) that",
    ]
    if all(marker in after_text for marker in accepted_markers):
        return _python_source_candidate_after(
            before_text=before_text,
            after_text=before_text,
            source_file=PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    old_scalar = "\n".join(
        [
            "    def _approx_scalar(self, x) -> ApproxScalar:",
            "        if isinstance(x, Decimal):",
            "            return ApproxDecimal(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
            "        return ApproxScalar(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
        ]
    )
    new_scalar = "\n".join(
        [
            "    def _approx_scalar(self, x) -> ApproxBase:",
            "        if isinstance(x, Decimal):",
            "            return ApproxDecimal(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
            "        if isinstance(x, (datetime, timedelta)):",
            "            return ApproxTimedelta(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
            "        return ApproxScalar(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
        ]
    )
    if old_scalar not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta approx _approx_scalar anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_dispatch_anchor_not_found",
                "message": "could not find ApproxBase._approx_scalar Decimal branch",
            },
        )
    after_text = after_text.replace(old_scalar, new_scalar, 1)

    old_class_doc_line = "    Requires an explicit tolerance as a timedelta."
    new_class_doc_line = (
        "    Requires an explicit tolerance as a timedelta for abs, or a float for rel."
    )
    if old_class_doc_line not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta approx class doc anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_doc_anchor_not_found",
                "message": "could not find ApproxTimedelta tolerance docstring line",
            },
        )
    after_text = after_text.replace(old_class_doc_line, new_class_doc_line, 1)

    old_requires_message = "\n".join(
        [
            '                "pytest.approx() requires an explicit tolerance for "',
            '                "datetime/timedelta comparisons: "',
            '                "e.g. approx(expected, abs=timedelta(seconds=1))"',
        ]
    )
    new_requires_message = "\n".join(
        [
            '                "pytest.approx() requires an explicit tolerance for "',
            '                "datetime/timedelta comparisons: "',
            '                "e.g. approx(expected, abs=timedelta(seconds=1)) "',
            '                "or approx(expected, rel=0.01)"',
        ]
    )
    if old_requires_message not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta approx explicit-tolerance message anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_error_message_anchor_not_found",
                "message": "could not find ApproxTimedelta requires-tolerance message",
            },
        )
    after_text = after_text.replace(old_requires_message, new_requires_message, 1)

    old_rel_block = "\n".join(
        [
            "        if rel is not None and not isinstance(rel, timedelta):",
            "            raise TypeError(",
            "                f\"relative tolerance for timedelta must be a \"",
            "                f\"timedelta, got {type(rel).__name__}\"",
            "            )",
            "        tolerance = max(t for t in (abs, rel) if t is not None)",
            "        super().__init__(expected, rel=None, abs=tolerance, nan_ok=False)",
        ]
    )
    new_rel_block = "\n".join(
        [
            "        if abs is not None and abs < timedelta(0):",
            "            raise ValueError(f\"absolute tolerance can't be negative: {abs}\")",
            "        if rel is not None:",
            "            if not isinstance(rel, (int, float)):",
            "                raise TypeError(",
            "                    f\"relative tolerance for timedelta must be a \"",
            "                    f\"number, got {type(rel).__name__}\"",
            "                )",
            "            if rel < 0:",
            "                raise ValueError(f\"relative tolerance can't be negative: {rel}\")",
            "            if math.isnan(rel):",
            "                raise ValueError(\"relative tolerance can't be NaN.\")",
            "        # Compute the effective tolerance. abs_tolerance is a timedelta, rel * expected",
            "        # gives a timedelta (timedelta * float works in Python).",
            "        abs_tolerance = abs",
            "        rel_tolerance = rel * builtins.abs(expected) if rel is not None else None",
            "        if abs_tolerance is not None and rel_tolerance is not None:",
            "            tolerance = max(abs_tolerance, rel_tolerance)",
            "        else:",
            "            tolerance = abs_tolerance if abs_tolerance is not None else rel_tolerance",
            "        super().__init__(expected, rel=rel, abs=tolerance, nan_ok=False)",
        ]
    )
    if old_rel_block not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta approx relative-tolerance source anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_region_anchor_not_found",
                "message": "could not find ApproxTimedelta old rel validation block",
            },
        )
    after_text = after_text.replace(old_rel_block, new_rel_block, 1)

    old_approx_doc = "\n".join(
        [
            "    Note that ``rel`` is not supported for datetime comparisons,",
            "    and ``abs`` or ``rel`` must be explicitly provided as a ``timedelta`` object.",
        ]
    )
    new_approx_doc = "\n".join(
        [
            "    Note that ``rel`` is not supported for datetime comparisons.",
            "    For timedelta comparisons, ``rel`` is a number (not a timedelta) that",
            "    represents a relative tolerance -- a fraction of the expected value.",
            "    ``abs`` must be a ``timedelta`` object in both cases.",
        ]
    )
    if old_approx_doc not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta approx function doc anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_doc_anchor_not_found",
                "message": "could not find approx() datetime/timedelta docstring note",
            },
        )
    after_text = after_text.replace(old_approx_doc, new_approx_doc, 1)

    planned_changed_files = (
        [PYTEST_TIMEDELTA_APPROX_SOURCE_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        source_path.write_text(after_text, encoding="utf-8")
    return _python_source_candidate_after(
        before_text=before_text,
        after_text=after_text,
        source_file=PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _materialize_pytest_timedelta_approx_tests(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, PYTEST_TIMEDELTA_APPROX_TEST_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    after_text = before_text
    if "class TestApproxDatetime:" not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest approx TestApproxDatetime class not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_class_anchor_not_found",
                "message": "could not find TestApproxDatetime in testing/python/approx.py",
            },
        )
    accepted_markers = [
        "        assert td1 == approx(td2, rel=0.01)",
        "    def test_timedelta_rel_must_be_number(self):",
        "    def test_timedelta_rel_scales_with_expected(self):",
        "    def test_timedelta_in_sequence(self):",
        "    def test_datetime_in_mapping(self):",
    ]
    if all(marker in after_text for marker in accepted_markers):
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=PYTEST_TIMEDELTA_APPROX_TEST_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    rel_replacements = [
        (
            "        assert td1 == approx(td2, rel=timedelta(seconds=1))",
            "        assert td1 == approx(td2, rel=0.01)",
        ),
        (
            "        assert td1 != approx(td2, rel=timedelta(seconds=1))",
            "        assert td1 != approx(td2, rel=0.01)",
        ),
    ]
    for old, new in rel_replacements:
        if old not in after_text:
            raise IssuePrCandidateAttemptError(
                "pytest timedelta rel assertion anchor not found",
                blocker={
                    "field": "test_materialization",
                    "reason": "test_assertion_anchor_not_found",
                    "message": f"could not find old assertion: {old.strip()}",
                },
            )
        after_text = after_text.replace(old, new, 1)

    old_type_test = "\n".join(
        [
            "    def test_timedelta_rel_must_be_timedelta(self):",
            "        from datetime import timedelta",
            "",
            "        with pytest.raises(TypeError, match=\"must be a timedelta\"):",
            "            approx(timedelta(seconds=1), rel=0.1)",
        ]
    )
    new_type_and_validation_tests = "\n".join(
        [
            "    def test_timedelta_rel_must_be_number(self):",
            "        from datetime import timedelta",
            "",
            "        with pytest.raises(TypeError, match=\"must be a number\"):",
            "            approx(timedelta(seconds=1), rel=timedelta(seconds=1))",
            "",
            "    def test_timedelta_rel_must_be_non_negative(self):",
            "        from datetime import timedelta",
            "",
            "        with pytest.raises(ValueError, match=\"relative tolerance can't be negative\"):",
            "            approx(timedelta(seconds=1), rel=-0.1)",
            "",
            "    def test_timedelta_rel_must_not_be_nan(self):",
            "        from datetime import timedelta",
            "",
            "        with pytest.raises(ValueError, match=\"relative tolerance can't be NaN\"):",
            "            approx(timedelta(seconds=1), rel=float(\"nan\"))",
            "",
            "    def test_timedelta_abs_must_be_non_negative(self):",
            "        from datetime import timedelta",
            "",
            "        with pytest.raises(ValueError, match=\"absolute tolerance can't be negative\"):",
            "            approx(timedelta(seconds=1), abs=timedelta(seconds=-1))",
            "",
            "    def test_timedelta_rel_with_abs(self):",
            "        from datetime import timedelta",
            "",
            "        # rel=0.05 gives 5s tolerance, abs=timedelta(seconds=1) gives 1s.",
            "        # max(1s, 5s) = 5s tolerance.",
            "        td1 = timedelta(seconds=100)",
            "        td2 = timedelta(seconds=104)",
            "        assert td1 == approx(td2, rel=0.05, abs=timedelta(seconds=1))",
            "",
            "    def test_timedelta_rel_zero(self):",
            "        from datetime import timedelta",
            "",
            "        # rel=0 means exact match required (0 * expected = 0)",
            "        td1 = timedelta(seconds=100)",
            "        assert td1 == approx(td1, rel=0.0, abs=timedelta(seconds=0))",
            "        assert td1 != approx(timedelta(seconds=101), rel=0.0, abs=timedelta(seconds=0))",
            "",
            "    def test_timedelta_rel_scales_with_expected(self):",
            "        from datetime import timedelta",
            "",
            "        # Same rel=0.1, but different expected values.",
            "        # 10% of 100s = 10s, 10% of 200s = 20s.",
            "        assert timedelta(seconds=109) == approx(timedelta(seconds=100), rel=0.1)",
            "        assert timedelta(seconds=218) == approx(timedelta(seconds=200), rel=0.1)",
            "        # 11s is > 10% of 100s, but < 10% of 200s",
            "        assert timedelta(seconds=111) != approx(timedelta(seconds=100), rel=0.1)",
            "        assert timedelta(seconds=211) == approx(timedelta(seconds=200), rel=0.1)",
        ]
    )
    if old_type_test not in after_text:
        raise IssuePrCandidateAttemptError(
            "pytest timedelta rel type test anchor not found",
            blocker={
                "field": "test_materialization",
                "reason": "test_method_anchor_not_found",
                "message": "could not find test_timedelta_rel_must_be_timedelta body",
            },
        )
    after_text = after_text.replace(old_type_test, new_type_and_validation_tests, 1)

    container_tests = "\n".join(
        [
            "    def test_timedelta_in_sequence(self):",
            "        from datetime import timedelta",
            "",
            "        assert [timedelta(seconds=105)] == approx([timedelta(seconds=100)], rel=0.05)",
            "        assert [timedelta(seconds=110)] != approx([timedelta(seconds=100)], rel=0.05)",
            "        assert [timedelta(seconds=105)] == approx(",
            "            [timedelta(seconds=100)], abs=timedelta(seconds=10)",
            "        )",
            "",
            "    def test_timedelta_in_mapping(self):",
            "        from datetime import timedelta",
            "",
            "        assert {\"x\": timedelta(seconds=105)} == approx(",
            "            {\"x\": timedelta(seconds=100)}, rel=0.05",
            "        )",
            "        assert {\"x\": timedelta(seconds=110)} != approx(",
            "            {\"x\": timedelta(seconds=100)}, rel=0.05",
            "        )",
            "        assert {\"x\": timedelta(seconds=105)} == approx(",
            "            {\"x\": timedelta(seconds=100)}, abs=timedelta(seconds=10)",
            "        )",
            "",
            "    def test_datetime_in_sequence(self):",
            "        from datetime import datetime",
            "        from datetime import timedelta",
            "",
            "        assert [datetime(2024, 1, 1, 12, 0, 0, 500_000)] == approx(",
            "            [datetime(2024, 1, 1, 12, 0, 0)], abs=timedelta(seconds=1)",
            "        )",
            "        assert [datetime(2024, 1, 1, 12, 0, 5)] != approx(",
            "            [datetime(2024, 1, 1, 12, 0, 0)], abs=timedelta(seconds=1)",
            "        )",
            "",
            "    def test_datetime_in_mapping(self):",
            "        from datetime import datetime",
            "        from datetime import timedelta",
            "",
            "        assert {\"t\": datetime(2024, 1, 1, 12, 0, 0, 500_000)} == approx(",
            "            {\"t\": datetime(2024, 1, 1, 12, 0, 0)}, abs=timedelta(seconds=1)",
            "        )",
            "        assert {\"t\": datetime(2024, 1, 1, 12, 0, 5)} != approx(",
            "            {\"t\": datetime(2024, 1, 1, 12, 0, 0)}, abs=timedelta(seconds=1)",
            "        )",
        ]
    )
    class_anchor = "\n\nclass MyVec3:"
    if "    def test_timedelta_in_sequence(self):" not in after_text:
        if class_anchor not in after_text:
            raise IssuePrCandidateAttemptError(
                "pytest approx TestApproxDatetime insertion boundary not found",
                blocker={
                    "field": "test_materialization",
                    "reason": "test_insertion_anchor_not_found",
                    "message": "could not find class MyVec3 boundary after TestApproxDatetime",
                },
            )
        after_text = after_text.replace(
            class_anchor, "\n" + container_tests + "\n" + class_anchor, 1
        )

    planned_changed_files = (
        [PYTEST_TIMEDELTA_APPROX_TEST_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    result = _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=PYTEST_TIMEDELTA_APPROX_TEST_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )
    result["metadata"] = {
        "target_class": "TestApproxDatetime",
        "obsolete_assertions_replaced": 2,
        "container_dispatch_methods_inserted": 4,
        "invalid_tolerance_methods_inserted": 3,
        "expected_value_scaling_methods_inserted": 3,
    }
    return result


def _scrapy_downloader_aware_source_actions() -> list[dict[str, object]]:
    return [
        {
            "kind": "python_instance_state_insert",
            "target": SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            "payload": {
                "class_name": "DownloaderAwarePriorityQueue",
                "attribute": "_last_selected_slot",
                "initial_value": None,
                "provenance": ["DATA-031", "DATA-034", "DATA-035"],
            },
        },
        {
            "kind": "python_method_insert",
            "target": SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            "payload": {
                "class_name": "DownloaderAwarePriorityQueue",
                "method_name": "_next_slot",
                "semantics": "rotate_equal_active_download_slots_after_last_selected",
                "provenance": ["DATA-031", "DATA-034", "DATA-035"],
            },
        },
        {
            "kind": "python_callsite_replace",
            "target": SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            "payload": {
                "method_name": "pop",
                "old_call": "min(stats)[1]",
                "new_call": "self._next_slot(stats, update_state=True)",
                "provenance": ["DATA-034", "DATA-035"],
            },
        },
        {
            "kind": "python_callsite_replace",
            "target": SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            "payload": {
                "method_name": "peek",
                "old_call": "min(stats)[1]",
                "new_call": "self._next_slot(stats, update_state=False)",
                "provenance": ["DATA-034", "DATA-035"],
            },
        },
    ]


def _scrapy_downloader_aware_test_action() -> dict[str, object]:
    return {
        "kind": "scrapy_pqueue_pytest_class_method_insert",
        "target": SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
        "payload": {
            "import_added": "from scrapy.core.downloader import Downloader",
            "class_name": "TestDownloaderAwarePriorityQueue",
            "inserted_methods": [
                "test_tie_breaking_rotates_slots",
                "test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted",
            ],
            "slot_metadata": "Downloader.DOWNLOAD_SLOT",
            "provenance": ["DATA-031", "DATA-034", "DATA-035"],
        },
    }


def _materialize_scrapy_downloader_aware_source(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    source_path = _repo_file(repo_path, SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH)
    before_text = source_path.read_text(encoding="utf-8")
    after_text = before_text
    accepted_markers = [
        "        self._last_selected_slot: str | None = None",
        "    def _next_slot(self, stats: list[tuple[int, str]], *, update_state: bool) -> str:",
        "        slot = self._next_slot(stats, update_state=True)",
        "        slot = self._next_slot(stats, update_state=False)",
    ]
    if all(marker in after_text for marker in accepted_markers):
        return _python_source_candidate_after(
            before_text=before_text,
            after_text=before_text,
            source_file=SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    old_state_block = "\n".join(
        [
            "        self.pqueues: dict[str, ScrapyPriorityQueue] = {}  # slot -> priority queue",
            "        if slot_startprios:",
        ]
    )
    new_state_block = "\n".join(
        [
            "        self.pqueues: dict[str, ScrapyPriorityQueue] = {}  # slot -> priority queue",
            "        self._last_selected_slot: str | None = None",
            "        if slot_startprios:",
        ]
    )
    if old_state_block not in after_text:
        raise IssuePrCandidateAttemptError(
            "Scrapy downloader-aware state anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_state_anchor_not_found",
                "message": (
                    "could not find DownloaderAwarePriorityQueue.pqueues "
                    "initialization anchor"
                ),
            },
        )
    after_text = after_text.replace(old_state_block, new_state_block, 1)

    next_slot_method = "\n".join(
        [
            "    def _next_slot(self, stats: list[tuple[int, str]], *, update_state: bool) -> str:",
            "        last = self._last_selected_slot",
            "        min_active: int | None = None",
            "        best_slot: str | None = None",
            "        best_slot_after_last: str | None = None",
            "        for active, slot in stats:",
            "            if min_active is None or active < min_active:",
            "                min_active = active",
            "                best_slot = slot",
            "                best_slot_after_last = None",
            "                if last is not None and slot > last:",
            "                    best_slot_after_last = slot",
            "            elif active == min_active:",
            "                if best_slot is None or slot < best_slot:",
            "                    best_slot = slot",
            "                if (",
            "                    last is not None",
            "                    and slot > last",
            "                    and (best_slot_after_last is None or slot < best_slot_after_last)",
            "                ):",
            "                    best_slot_after_last = slot",
            "        assert best_slot is not None",
            "        slot = best_slot_after_last if best_slot_after_last is not None else best_slot",
            "        if update_state:",
            "            self._last_selected_slot = slot",
            "        return slot",
        ]
    )
    method_anchor = "    def pqfactory(\n"
    if "    def _next_slot(" not in after_text:
        if method_anchor not in after_text:
            raise IssuePrCandidateAttemptError(
                "Scrapy downloader-aware method insertion anchor not found",
                blocker={
                    "field": "source_materialization",
                    "reason": "source_method_anchor_not_found",
                    "message": "could not find DownloaderAwarePriorityQueue.pqfactory",
                },
            )
        after_text = after_text.replace(
            method_anchor,
            next_slot_method + "\n\n" + method_anchor,
            1,
        )

    old_pop_slot = "\n".join(
        [
            "        slot = min(stats)[1]",
            "        queue = self.pqueues[slot]",
            "        request = queue.pop()",
        ]
    )
    new_pop_slot = "\n".join(
        [
            "        slot = self._next_slot(stats, update_state=True)",
            "        queue = self.pqueues[slot]",
            "        request = queue.pop()",
        ]
    )
    if old_pop_slot not in after_text:
        raise IssuePrCandidateAttemptError(
            "Scrapy downloader-aware pop slot-selection anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_pop_anchor_not_found",
                "message": "could not find DownloaderAwarePriorityQueue.pop min(stats)",
            },
        )
    after_text = after_text.replace(old_pop_slot, new_pop_slot, 1)

    old_peek_slot = "\n".join(
        [
            "        slot = min(stats)[1]",
            "        queue = self.pqueues[slot]",
            "        return queue.peek()",
        ]
    )
    new_peek_slot = "\n".join(
        [
            "        slot = self._next_slot(stats, update_state=False)",
            "        queue = self.pqueues[slot]",
            "        return queue.peek()",
        ]
    )
    if old_peek_slot not in after_text:
        raise IssuePrCandidateAttemptError(
            "Scrapy downloader-aware peek slot-selection anchor not found",
            blocker={
                "field": "source_materialization",
                "reason": "source_peek_anchor_not_found",
                "message": "could not find DownloaderAwarePriorityQueue.peek min(stats)",
            },
        )
    after_text = after_text.replace(old_peek_slot, new_peek_slot, 1)

    planned_changed_files = (
        [SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        source_path.write_text(after_text, encoding="utf-8")
    return _python_source_candidate_after(
        before_text=before_text,
        after_text=after_text,
        source_file=SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )


def _materialize_scrapy_downloader_aware_tests(
    repo_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    test_path = _repo_file(repo_path, SCRAPY_DOWNLOADER_AWARE_TEST_PATH)
    before_text = test_path.read_text(encoding="utf-8")
    after_text = before_text
    accepted_markers = [
        "from scrapy.core.downloader import Downloader",
        "    def test_tie_breaking_rotates_slots(self):",
        "    def test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted(self):",
    ]
    if all(marker in after_text for marker in accepted_markers):
        return _test_candidate_after(
            before_text=before_text,
            after_text=before_text,
            target_test_file=SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
            planned_changed_files=[],
            wrote_file=False,
            status="already_applied",
        )

    import_anchor = "import queuelib\n\n"
    downloader_import = "from scrapy.core.downloader import Downloader\n"
    if downloader_import not in after_text:
        if import_anchor not in after_text:
            raise IssuePrCandidateAttemptError(
                "Scrapy pqueue Downloader import anchor not found",
                blocker={
                    "field": "test_materialization",
                    "reason": "test_import_anchor_not_found",
                    "message": "could not find queuelib import block in tests/test_pqueues.py",
                },
            )
        after_text = after_text.replace(
            import_anchor,
            import_anchor + downloader_import,
            1,
        )

    test_methods = "\n".join(
        [
            "    def test_tie_breaking_rotates_slots(self):",
            "        # No active downloads are tracked in the downloader, so every slot has",
            "        # the same score and tie-breaking must not starve a slot.",
            '        req_a1 = Request("https://example.org/a1")',
            '        req_a1.meta[Downloader.DOWNLOAD_SLOT] = "slot-a"',
            '        req_b1 = Request("https://example.org/b1")',
            '        req_b1.meta[Downloader.DOWNLOAD_SLOT] = "slot-b"',
            '        req_a2 = Request("https://example.org/a2")',
            '        req_a2.meta[Downloader.DOWNLOAD_SLOT] = "slot-a"',
            '        req_b2 = Request("https://example.org/b2")',
            '        req_b2.meta[Downloader.DOWNLOAD_SLOT] = "slot-b"',
            "",
            "        for request in (req_a1, req_b1, req_a2, req_b2):",
            "            self.queue.push(request)",
            "",
            "        slots = [",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "        ]",
            "",
            '        assert slots == ["slot-a", "slot-b", "slot-a", "slot-b"]',
            "",
            "    def test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted(self):",
            "        # If the selected slot becomes empty, rotation should continue from",
            "        # that slot marker to avoid restarting from the smallest slot.",
            '        req_a1 = Request("https://example.org/a1")',
            '        req_a1.meta[Downloader.DOWNLOAD_SLOT] = "slot-a"',
            '        req_a2 = Request("https://example.org/a2")',
            '        req_a2.meta[Downloader.DOWNLOAD_SLOT] = "slot-a"',
            '        req_b1 = Request("https://example.org/b1")',
            '        req_b1.meta[Downloader.DOWNLOAD_SLOT] = "slot-b"',
            '        req_c1 = Request("https://example.org/c1")',
            '        req_c1.meta[Downloader.DOWNLOAD_SLOT] = "slot-c"',
            "",
            "        for request in (req_a1, req_a2, req_b1, req_c1):",
            "            self.queue.push(request)",
            "",
            "        slots = [",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "            self.queue.pop().meta[Downloader.DOWNLOAD_SLOT],",
            "        ]",
            "",
            '        assert slots == ["slot-a", "slot-b", "slot-c", "slot-a"]',
        ]
    )
    class_boundary = "\n\n@pytest.mark.parametrize(\n"
    if "    def test_tie_breaking_rotates_slots(self):" not in after_text:
        if class_boundary not in after_text:
            raise IssuePrCandidateAttemptError(
                "Scrapy pqueue test insertion boundary not found",
                blocker={
                    "field": "test_materialization",
                    "reason": "test_insertion_anchor_not_found",
                    "message": (
                        "could not find boundary after "
                        "TestDownloaderAwarePriorityQueue in tests/test_pqueues.py"
                    ),
                },
            )
        after_text = after_text.replace(
            class_boundary,
            "\n" + test_methods + "\n" + class_boundary,
            1,
        )

    planned_changed_files = (
        [SCRAPY_DOWNLOADER_AWARE_TEST_PATH] if after_text != before_text else []
    )
    if write and planned_changed_files:
        test_path.write_text(after_text, encoding="utf-8")
    result = _test_candidate_after(
        before_text=before_text,
        after_text=after_text,
        target_test_file=SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
        planned_changed_files=planned_changed_files,
        wrote_file=write and bool(planned_changed_files),
        status="materialized" if planned_changed_files else "unchanged",
    )
    result["metadata"] = {
        "target_class": "TestDownloaderAwarePriorityQueue",
        "import_added": downloader_import.strip(),
        "inserted_methods": [
            "test_tie_breaking_rotates_slots",
            "test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted",
        ],
    }
    return result


def _python_source_candidate_after(
    *,
    before_text: str,
    after_text: str,
    source_file: str,
    planned_changed_files: Sequence[str],
    wrote_file: bool,
    status: str,
) -> dict[str, object]:
    diff = _unified_diff(before_text, after_text, source_file)
    compile(after_text, source_file, "exec")
    return {
        "status": status,
        "target_source_file": source_file,
        "planned_changed_files": list(planned_changed_files),
        "wrote_file": wrote_file,
        "sha256_before": _sha256_text(before_text),
        "sha256_after": _sha256_text(after_text),
        "diff_summary": _diff_summary(before_text, after_text),
        "diff": diff,
        "ast_parse_ok": True,
        "ast_delta": python_ast_delta_metadata(before_text, after_text),
    }


def _test_candidate_after(
    *,
    before_text: str,
    after_text: str,
    target_test_file: str,
    planned_changed_files: Sequence[str],
    wrote_file: bool,
    status: str,
) -> dict[str, object]:
    diff = _unified_diff(before_text, after_text, target_test_file)
    return {
        "status": status,
        "target_test_file": target_test_file,
        "planned_changed_files": list(planned_changed_files),
        "wrote_file": wrote_file,
        "sha256_before": _sha256_text(before_text),
        "sha256_after": _sha256_text(after_text),
        "diff_summary": _diff_summary(before_text, after_text),
        "diff": diff,
    }


def _text_file_candidate_after(
    *,
    before_text: str,
    after_text: str,
    target_file: str,
    planned_changed_files: Sequence[str],
    wrote_file: bool,
    status: str,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "target_file": target_file,
        "planned_changed_files": list(planned_changed_files),
        "wrote_file": wrote_file,
        "sha256_before": _sha256_text(before_text),
        "sha256_after": _sha256_text(after_text),
        "diff_summary": _diff_summary(before_text, after_text),
        "diff": _unified_diff(before_text, after_text, target_file),
        "metadata": dict(metadata or {}),
    }


def _selected_validation_command(
    *,
    validation_records: Sequence[Mapping[str, object]],
    readiness_records: Sequence[Mapping[str, object]],
    replay_id: str,
    default_command: str,
) -> str:
    for record in validation_records:
        if record.get("replay_id") == replay_id and record.get("status") == "passed":
            command = str(record.get("validation_command") or "")
            if command:
                return command
    for record in readiness_records:
        if record.get("replay_id") == replay_id:
            command = str(record.get("validation_command") or "")
            if command:
                return command
    return default_command


def _evidence_summary(
    *,
    readiness_records: Sequence[Mapping[str, object]],
    prompt_spec_records: Sequence[Mapping[str, object]],
    validation_records: Sequence[Mapping[str, object]],
    local_knowledge_records: Sequence[Mapping[str, object]],
    materialization_audit_records: Sequence[Mapping[str, object]] = (),
    replay_id: str = REQUESTS_REPLAY_ID,
) -> dict[str, object]:
    return {
        "readiness": _matching_evidence(
            readiness_records,
            replay_field="replay_id",
            replay_id=replay_id,
        ),
        "prompt_spec": _matching_evidence(
            prompt_spec_records,
            replay_field="replay_id",
            replay_id=replay_id,
        ),
        "validation": _matching_evidence(
            validation_records,
            replay_field="replay_id",
            replay_id=replay_id,
        ),
        "local_knowledge": _matching_local_knowledge(
            local_knowledge_records,
            replay_id=replay_id,
        ),
        "materialization_audit": _matching_evidence(
            materialization_audit_records,
            replay_field="replay_id",
            replay_id=replay_id,
        ),
    }


def _matching_evidence(
    records: Sequence[Mapping[str, object]],
    *,
    replay_field: str,
    replay_id: str,
) -> list[dict[str, object]]:
    return [
        {
            "record_kind": record.get("record_kind"),
            "id": record.get("id")
            or record.get("audit_id")
            or record.get("candidate_id")
            or f"{record.get('record_kind', 'evidence')}/{replay_id}",
            "source": record.get("_source_path") or record.get("_readiness_source_path"),
            "status": record.get("status")
            or record.get("ready_for_candidate_attempt")
            or record.get("blocker_recommendation"),
        }
        for record in records
        if record.get(replay_field) == replay_id
    ]


def _matching_local_knowledge(
    records: Sequence[Mapping[str, object]],
    *,
    replay_id: str,
) -> list[dict[str, object]]:
    matched: list[dict[str, object]] = []
    for record in records:
        links = _mapping(record.get("links"))
        if replay_id not in _string_sequence(links.get("task_ids")):
            continue
        data = _mapping(record.get("data"))
        matched.append(
            {
                "record_kind": record.get("record_type"),
                "id": record.get("id"),
                "source": record.get("_source_path"),
                "knowledge_category": data.get("knowledge_category"),
            }
        )
    return matched


def _requests_structured_action_coverage(
    *,
    blockers: Sequence[Mapping[str, str]],
    source_action: SourceRegionAction | None,
    files_changed: Sequence[str],
    allowed_write_paths: Sequence[str],
    validation: Mapping[str, object],
) -> dict[str, object]:
    covered = (
        not blockers
        and set(files_changed) == set(allowed_write_paths)
        and source_action is not None
    )
    labels = []
    if source_action is not None:
        labels.append("source_region_replace_covered")
    if REQUESTS_TEST_PATH in files_changed:
        labels.append("repo_convention_pytest_method_insert_covered")
    if validation.get("status") == "passed":
        labels.append("focused_validation_covered")
    return {
        "accepted_edit_covered": covered,
        "coverage_labels": labels,
        "materialization_gap": None if covered else "requests_getattr_stream_candidate_gap",
        "note": (
            "Covered only by the bounded DATA-012 Requests materializer using the "
            "existing source-region action plus a deterministic pytest-method "
            "insertion; this is not evidence of a general issue/PR generator."
        ),
    }


def _click_default_map_structured_action_coverage(
    *,
    blockers: Sequence[Mapping[str, str]],
    materialization_gaps: Sequence[Mapping[str, str]],
    source_action: SourceRegionAction | None,
    files_changed: Sequence[str],
    validation: Mapping[str, object],
) -> dict[str, object]:
    behavior_paths = {CLICK_DEFAULT_MAP_SOURCE_PATH, CLICK_DEFAULT_MAP_TEST_PATH}
    behavior_covered = (
        not blockers
        and behavior_paths.issubset(set(files_changed))
        and source_action is not None
    )
    accepted_edit_covered = behavior_covered and not materialization_gaps
    labels = []
    if source_action is not None:
        labels.append("source_region_replace_covered")
    if CLICK_DEFAULT_MAP_TEST_PATH in files_changed:
        labels.append("repo_convention_pytest_function_insert_covered")
    if validation.get("status") == "passed":
        labels.append("focused_validation_covered")
    if materialization_gaps:
        labels.append("accepted_auxiliary_paths_not_covered")
    return {
        "accepted_edit_covered": accepted_edit_covered,
        "behavior_edit_covered": behavior_covered,
        "coverage_labels": labels,
        "materialization_gap": (
            None
            if accepted_edit_covered
            else "accepted_auxiliary_changelog_docs_config_materialization_gap"
        ),
        "note": (
            "The Click source and focused pytest behavior are covered by the "
            "bounded source-region action plus deterministic pytest-function "
            "insertion. The accepted PR also adds CHANGES/docs/conf updates, "
            "and the current structured-action surface has no changelog/docs/"
            "Sphinx config materializer for those auxiliary paths."
        ),
    }


def _click_semver_structured_action_coverage(
    *,
    blockers: Sequence[Mapping[str, str]],
    source_action: SourceRegionAction | None,
    files_changed: Sequence[str],
    allowed_write_paths: Sequence[str],
    validation: Mapping[str, object],
) -> dict[str, object]:
    covered = (
        not blockers
        and set(files_changed) == set(allowed_write_paths)
        and source_action is not None
    )
    labels = []
    if source_action is not None:
        labels.append("source_region_replace_covered")
    if CLICK_SEMVER_TEST_PATH in files_changed:
        labels.append("repo_convention_pytest_function_replace_covered")
    if validation.get("status") == "passed":
        labels.append("focused_validation_covered")
    return {
        "accepted_edit_covered": covered,
        "behavior_edit_covered": covered,
        "coverage_labels": labels,
        "materialization_gap": None if covered else "click_semver_candidate_gap",
        "note": (
            "The Click #3298 accepted source/test edit is covered only by the "
            "bounded DATA-016 source-region action plus deterministic pytest "
            "function replacement. This is local issue/PR replay evidence, not "
            "a general source generator."
        ),
    }


def _pytest_strict_addopts_structured_action_coverage(
    *,
    blockers: Sequence[Mapping[str, str]],
    materialization_gaps: Sequence[Mapping[str, str]],
    files_changed: Sequence[str],
    validation: Mapping[str, object],
    include_auxiliary_paths: bool,
) -> dict[str, object]:
    source_test_paths = set(PYTEST_STRICT_ADDOPTS_SOURCE_TEST_PATHS)
    auxiliary_paths = set(PYTEST_STRICT_ADDOPTS_AUXILIARY_PATHS)
    accepted_paths = set(PYTEST_STRICT_ADDOPTS_ACCEPTED_PATHS)
    changed = set(files_changed)
    behavior_covered = not blockers and source_test_paths.issubset(changed)
    auxiliary_covered = auxiliary_paths.issubset(changed)
    accepted_edit_covered = (
        behavior_covered
        and auxiliary_covered
        and accepted_paths == changed
        and not materialization_gaps
    )
    labels = []
    if PYTEST_STRICT_ADDOPTS_AUTHORS_PATH in changed:
        labels.append("newline_delimited_sorted_unique_insert_authors_covered")
    if PYTEST_STRICT_ADDOPTS_CHANGELOG_PATH in changed:
        labels.append("towncrier_bugfix_fragment_create_covered")
    if PYTEST_STRICT_ADDOPTS_SOURCE_PATH in changed:
        labels.extend(
            [
                "python_from_import_insert_covered",
                "config_parse_addopts_override_source_region_covered",
            ]
        )
    if PYTEST_STRICT_ADDOPTS_TEST_CONFIG_PATH in changed:
        labels.append("pytest_parametrize_existing_test_refine_config_covered")
    if PYTEST_STRICT_ADDOPTS_TEST_MARK_PATH in changed:
        labels.append("pytest_parametrize_existing_test_refine_mark_covered")
    if validation.get("status") == "passed":
        labels.append("focused_validation_covered")
    if materialization_gaps:
        labels.append("accepted_auxiliary_paths_not_covered")
    return {
        "accepted_edit_covered": accepted_edit_covered,
        "behavior_edit_covered": behavior_covered,
        "auxiliary_edit_covered": auxiliary_covered,
        "source_test_only_scope": not include_auxiliary_paths,
        "full_accepted_scope": include_auxiliary_paths,
        "coverage_labels": labels,
        "materialization_gap": (
            None
            if accepted_edit_covered
            else "accepted_auxiliary_authors_changelog_materialization_gap"
        ),
        "note": (
            "The DATA-025 full-scope candidate covers the accepted pytest #14442 "
            "AUTHORS, changelog, source, and test paths with deterministic "
            "bounded materializers."
            if include_auxiliary_paths
            else "The DATA-024 candidate covers only the behavior-changing pytest "
            "source/test slice with a deterministic import inserter, a bounded "
            "Config.parse insertion, and two constrained existing-pytest-test "
            "refinements. Full accepted-edit parity remains false because AUTHORS "
            "and changelog/14442.bugfix.rst are deliberately excluded auxiliary "
            "paths in this slice."
        ),
    }


def _pytest_timedelta_approx_structured_action_coverage(
    *,
    blockers: Sequence[Mapping[str, str]],
    files_changed: Sequence[str],
    validation: Mapping[str, object],
) -> dict[str, object]:
    accepted_paths = set(PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS)
    changed = set(files_changed)
    source_covered = PYTEST_TIMEDELTA_APPROX_SOURCE_PATH in changed
    test_covered = PYTEST_TIMEDELTA_APPROX_TEST_PATH in changed
    accepted_edit_covered = not blockers and accepted_paths == changed
    labels = []
    if source_covered:
        labels.extend(
            [
                "python_dispatch_branch_insert_datetime_timedelta_covered",
                "pytest_approx_timedelta_numeric_rel_source_region_covered",
                "approx_datetime_timedelta_doc_region_covered",
            ]
        )
    if test_covered:
        labels.append("pytest_testapproxdatetime_method_refine_insert_covered")
    if validation.get("status") == "passed":
        labels.append("focused_validation_covered")
    return {
        "accepted_edit_covered": accepted_edit_covered,
        "behavior_edit_covered": accepted_edit_covered,
        "source_test_only_scope": True,
        "full_accepted_scope": True,
        "coverage_labels": labels,
        "materialization_gap": (
            None
            if accepted_edit_covered
            else "pytest_timedelta_approx_source_test_candidate_gap"
        ),
        "provenance_task_ids": ["DATA-018", "DATA-026", "DATA-027", "DATA-028", "DATA-029"],
        "note": (
            "The DATA-029 candidate covers the full accepted pytest #14462 "
            "source/test scope with a bounded ApproxBase dispatch insertion, "
            "ApproxTimedelta numeric relative-tolerance source-region update, "
            "and constrained TestApproxDatetime refiner. This is local "
            "issue/PR replay evidence, not a general source generator."
        ),
    }


def _scrapy_downloader_aware_structured_action_coverage(
    *,
    blockers: Sequence[Mapping[str, str]],
    files_changed: Sequence[str],
    validation: Mapping[str, object],
) -> dict[str, object]:
    accepted_paths = set(SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS)
    changed = set(files_changed)
    source_covered = SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH in changed
    test_covered = SCRAPY_DOWNLOADER_AWARE_TEST_PATH in changed
    accepted_edit_covered = not blockers and accepted_paths == changed
    labels = []
    if source_covered:
        labels.extend(
            [
                "scrapy_downloader_slot_rotation_state_insert_covered",
                "scrapy_downloader_next_slot_method_insert_covered",
                "scrapy_downloader_pop_peek_callsite_replace_covered",
            ]
        )
    if test_covered:
        labels.append("scrapy_pqueue_pytest_class_method_insert_covered")
    if validation.get("status") == "passed":
        labels.append("focused_validation_covered")
    return {
        "accepted_edit_covered": accepted_edit_covered,
        "behavior_edit_covered": accepted_edit_covered,
        "source_test_only_scope": True,
        "full_accepted_scope": True,
        "coverage_labels": labels,
        "materialization_gap": (
            None
            if accepted_edit_covered
            else "scrapy_downloader_aware_source_test_candidate_gap"
        ),
        "provenance_task_ids": [
            "DATA-030",
            "DATA-031",
            "DATA-033",
            "DATA-034",
            "DATA-035",
        ],
        "note": (
            "The DATA-035 candidate covers the full accepted Scrapy #7293 "
            "source/test scope with a bounded DownloaderAwarePriorityQueue "
            "slot-rotation source update and a constrained "
            "TestDownloaderAwarePriorityQueue method inserter. This is local "
            "issue/PR replay evidence, not a general source generator."
        ),
    }


def _scrapy_downloader_aware_validation_command(
    *,
    validation_records: Sequence[Mapping[str, object]],
    readiness_records: Sequence[Mapping[str, object]],
) -> str:
    selected = _selected_validation_command(
        validation_records=validation_records,
        readiness_records=readiness_records,
        replay_id=SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        default_command=SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND,
    )
    if selected == "pytest tests/test_pqueues.py -q":
        return SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND
    return selected


def _deferred_validation_record(
    *,
    setup_command: str,
    validation_command: str,
) -> dict[str, object]:
    return {
        "status": "not_run",
        "setup_command": setup_command,
        "validation_command": validation_command,
        "runtime_seconds": 0.0,
        "not_run_reason": "candidate_validation_deferred",
        "candidate_validation_network_allowed": False,
    }


def _run_shell(
    repo_path: Path,
    command: str,
    *,
    name: str,
    timeout_seconds: int,
) -> dict[str, object]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        runtime_seconds = round(time.monotonic() - started, 3)
        return {
            "name": name,
            "command": command,
            "status": "passed" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "runtime_seconds": runtime_seconds,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "name": name,
            "command": command,
            "status": "timeout",
            "returncode": None,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
            "runtime_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": timeout_seconds,
        }


def _candidate_diff(repo_path: Path, paths: Sequence[str]) -> dict[str, object]:
    diff_parts = []
    tracked_diff = _git_stdout(repo_path, ("diff", "--", *paths))
    if tracked_diff:
        diff_parts.append(tracked_diff)
    changed = _git_stdout(repo_path, ("diff", "--name-only", "--", *paths))
    changed_files = [line for line in changed.splitlines() if line]
    inside_git_worktree = (
        _git_stdout(repo_path, ("rev-parse", "--is-inside-work-tree")) == "true"
    )
    if not inside_git_worktree:
        return {
            "diff": tracked_diff,
            "changed_files": changed_files,
            "diff_summary": _diff_text_summary(tracked_diff),
        }
    for path in paths:
        repo_file = _repo_file(repo_path, path)
        if not repo_file.is_file():
            continue
        tracked = _git_stdout(repo_path, ("ls-files", "--", path))
        if tracked:
            continue
        file_text = repo_file.read_text(encoding="utf-8")
        diff_parts.append(_unified_diff("", file_text, path))
        if path not in changed_files:
            changed_files.append(path)
    changed_set = set(changed_files)
    changed_files = [path for path in paths if path in changed_set]
    diff = "\n".join(part for part in diff_parts if part)
    return {
        "diff": diff,
        "changed_files": changed_files,
        "diff_summary": _diff_text_summary(diff),
    }


def _git_stdout(repo_path: Path, args: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _repo_file(repo_path: Path, relative_path: str) -> Path:
    pure_path = PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ValueError("repo-relative path expected")
    return repo_path / pure_path


def _line_number(source: str, needle: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if line == needle:
            return index
    raise SourceRegionMaterializationError(
        f"target line not found: {needle}",
        residual="target_selection",
    )


def _line_number_after(source: str, needle: str, *, start_line: int) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if index <= start_line:
            continue
        if line == needle:
            return index
    raise SourceRegionMaterializationError(
        f"target line not found after {start_line}: {needle}",
        residual="target_selection",
    )


def _paths_outside_allowlist(paths: Sequence[str], allowlist: Sequence[str]) -> list[str]:
    allowed = set(allowlist)
    return sorted({path for path in paths if path not in allowed})


def _source_planned_changed_files(
    source_materialization: Mapping[str, object],
    file_path: str,
) -> list[str]:
    if not source_materialization:
        return []
    if source_materialization.get("status") == "blocked":
        return []
    direct_diff = str(source_materialization.get("diff") or "")
    if direct_diff:
        return [file_path]
    candidate_after = _mapping(source_materialization.get("candidate_after"))
    diff = str(candidate_after.get("diff") or "")
    return [file_path] if diff else []


def _candidate_id(
    *,
    replay_id: str,
    repo_before_ref: str,
    candidate_diff: str,
    validation_status: str,
) -> str:
    digest = hashlib.sha256(
        "\n".join([replay_id, repo_before_ref, candidate_diff, validation_status]).encode()
    ).hexdigest()
    return f"issue-pr-candidate/{replay_id}/{digest[:16]}"


def _diff_summary(before_text: str, after_text: str) -> dict[str, int]:
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    diff = _unified_diff(before_text, after_text, "candidate")
    return {
        "hunk_count": diff.count("\n@@ ") + (1 if diff.startswith("@@ ") else 0),
        "changed_line_count": sum(
            max(i2 - i1, j2 - j1)
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                a=before_lines, b=after_lines
            ).get_opcodes()
            if tag != "equal"
        ),
        "added_line_count": sum(
            1 for line in difflib.ndiff(before_lines, after_lines) if line.startswith("+ ")
        ),
        "removed_line_count": sum(
            1 for line in difflib.ndiff(before_lines, after_lines) if line.startswith("- ")
        ),
    }


def _diff_text_summary(diff: str) -> dict[str, int]:
    lines = diff.splitlines()
    return {
        "hunk_count": sum(1 for line in lines if line.startswith("@@ ")),
        "added_line_count": sum(
            1 for line in lines if line.startswith("+") and not line.startswith("+++")
        ),
        "removed_line_count": sum(
            1 for line in lines if line.startswith("-") and not line.startswith("---")
        ),
    }


def _unified_diff(before_text: str, after_text: str, file_path: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_inline(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _string_sequence(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence):
        return []
    return [str(item) for item in value if isinstance(item, str)]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
