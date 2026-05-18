"""Candidate attempt materializer for bounded issue/PR replay proofs."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

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


def run_issue_pr_candidate_attempt(
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
    raise IssuePrCandidateAttemptError(
        f"unsupported replay id: {replay_id}",
        blocker={
            "field": "replay_id",
            "reason": "unsupported_issue_pr_candidate",
            "message": "supported candidate attempts are DATA-012 Requests and DATA-014 Click default_map",
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
    parser.add_argument("--setup-command", default=REQUESTS_SETUP_COMMAND)
    parser.add_argument("--validation-command", default=REQUESTS_VALIDATION_COMMAND)
    parser.add_argument("--validation-timeout-seconds", type=int, default=120)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--validate", action="store_true")
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

    attempt = run_issue_pr_candidate_attempt(
        args.repo_path,
        manifest_path=args.manifest,
        replay_id=args.replay_id,
        readiness_records=load_jsonl_many(args.readiness_evidence),
        prompt_spec_records=load_jsonl_many(args.prompt_spec_evidence),
        validation_records=load_jsonl_many(args.validation_evidence),
        local_knowledge_records=load_jsonl_many(args.local_knowledge_evidence),
        setup_command=setup_command,
        validation_command=validation_command,
        write=not args.plan_only,
        validate=args.validate,
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
    diff = _git_stdout(repo_path, ("diff", "--", *paths))
    changed = _git_stdout(repo_path, ("diff", "--name-only", "--", *paths))
    changed_files = [line for line in changed.splitlines() if line]
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
