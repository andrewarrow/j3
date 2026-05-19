"""Repo-state-aware tests-only planning for real-repo ladder tasks."""

from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from j3.local_knowledge import (
    build_knowledge_use_record,
    validate_local_knowledge_record,
)
from j3.repo_state import encode_repo_state_coverage


REAL_REPO_TESTS_CANDIDATE_SCHEMA_VERSION = "real-repo-tests-candidate-v1"
REAL_REPO_TESTS_CANDIDATE_KIND = "real_repo_tests_only_candidate"
REAL_REPO_TESTS_ACTION_FAMILY = "tests_only_existing_repo_pytest"
TEST_CASE_MATERIALIZATION_BLOCKER = "test_case_materialization_gap"
REQUIRED_KNOWLEDGE_PURPOSES = ("test_location", "import_style", "validation")
INICONFIG_PARSE_COMMENTS_TASK_ID = "iniconfig-tests-parse-comments"
H11_BYTESIFY_MEMORYVIEW_TASK_ID = "h11-tests-bytesify-memoryview"
HUMANIZE_NATURALSIZE_NEGATIVE_STRINGS_TASK_ID = (
    "humanize-tests-naturalsize-negative-strings"
)
BOLTONS_SLUGIFY_DELIMITER_TASK_ID = "boltons-tests-slugify-delimiter"
CANDIDATE_VALIDATION_DEFERRED = "candidate_validation_deferred"


class RealRepoTestsPlannerError(ValueError):
    """Raised when a real-repo tests-only task cannot be planned."""

    def __init__(self, message: str, *, blocker: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.blocker = blocker or {
            "field": "real_repo_tests_planner",
            "reason": "unsupported_real_repo_tests_only_task",
            "message": message,
        }


class RealRepoTestsActionKind(str, Enum):
    """Structured actions in a real-repo tests-only candidate plan."""

    INSPECT_REPO_STATE = "inspect_repo_state"
    SELECT_TEST_FILE = "select_test_file"
    SELECT_IMPORT_STYLE = "select_import_style"
    MATERIALIZE_PYTEST_CASES = "materialize_pytest_cases"
    VALIDATE = "validate"


@dataclass(frozen=True, slots=True)
class RealRepoTestsAction:
    """One structured non-mutating action in a tests-only candidate."""

    kind: RealRepoTestsActionKind
    target: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.target is None:
            return
        _normalize_relative_path(self.target)

    def to_record(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "target": self.target,
            "payload": _json_copy(self.payload),
        }


@dataclass(frozen=True, slots=True)
class RealRepoTestsCandidate:
    """Structured candidate/action record for a real-repo tests-only task."""

    candidate_id: str
    repo_id: str
    repo_split: str
    checkout_ref: str
    task_id: str
    task_type: str
    prompt: str
    status: str
    target_test_file: str
    validation_commands: list[str] = field(default_factory=list)
    allowed_write_paths: list[str] = field(default_factory=list)
    hidden_like_checks: list[str] = field(default_factory=list)
    expected_failure_modes: list[str] = field(default_factory=list)
    production_files: list[str] = field(default_factory=list)
    production_file_hashes_before: dict[str, str] = field(default_factory=dict)
    actions: list[RealRepoTestsAction] = field(default_factory=list)
    repo_state_evidence: dict[str, object] = field(default_factory=dict)
    import_style_evidence: dict[str, object] = field(default_factory=dict)
    mutation_scope: dict[str, object] = field(default_factory=dict)
    candidate_after: dict[str, object] = field(default_factory=dict)
    validation: dict[str, object] = field(default_factory=dict)
    knowledge_citations: dict[str, list[str]] = field(default_factory=dict)
    knowledge_attribution: dict[str, object] = field(default_factory=dict)
    knowledge_use_record: dict[str, object] | None = None
    blockers: list[dict[str, str]] = field(default_factory=list)
    residual_labels: list[str] = field(default_factory=list)
    zero_hosted_usage_confirmed: bool = True

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": REAL_REPO_TESTS_CANDIDATE_SCHEMA_VERSION,
            "record_kind": REAL_REPO_TESTS_CANDIDATE_KIND,
            "candidate_id": self.candidate_id,
            "repo_id": self.repo_id,
            "repo_split": self.repo_split,
            "checkout_ref": self.checkout_ref,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "action_family": REAL_REPO_TESTS_ACTION_FAMILY,
            "status": self.status,
            "target_test_file": self.target_test_file,
            "validation_commands": list(self.validation_commands),
            "allowed_write_paths": list(self.allowed_write_paths),
            "hidden_like_checks": list(self.hidden_like_checks),
            "expected_failure_modes": list(self.expected_failure_modes),
            "production_files": list(self.production_files),
            "production_file_hashes_before": dict(self.production_file_hashes_before),
            "actions": [action.to_record() for action in self.actions],
            "repo_state_evidence": _json_copy(self.repo_state_evidence),
            "import_style_evidence": _json_copy(self.import_style_evidence),
            "mutation_scope": _json_copy(self.mutation_scope),
            "candidate_after": _json_copy(self.candidate_after),
            "validation": _json_copy(self.validation),
            "knowledge_citations": {
                purpose: list(record_ids)
                for purpose, record_ids in self.knowledge_citations.items()
            },
            "knowledge_attribution": _json_copy(self.knowledge_attribution),
            "knowledge_use_record": (
                _json_copy(self.knowledge_use_record)
                if self.knowledge_use_record is not None
                else None
            ),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "residual_labels": list(self.residual_labels),
            "zero_hosted_usage_confirmed": self.zero_hosted_usage_confirmed,
        }


def plan_real_repo_tests_only_candidate(
    repo_path: Path,
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
    write: bool = True,
) -> RealRepoTestsCandidate:
    """Plan and optionally materialize a tests-only candidate from repo state.

    This slice remains deliberately narrow. It can materialize pytest cases for
    a small set of proven real-repo tests-only tasks after selecting the local
    test file and import style from repo-state and local-knowledge evidence.
    Unsupported real-repo tests-only tasks still receive an explicit
    materialization blocker instead of a repo-specific guess.
    """

    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise _blocker_error(
            f"repo does not exist: {resolved_repo}",
            field="repo_state",
            reason="missing_repo_state",
        )

    repo_id = _required_str(repo, "id")
    repo_split = str(repo.get("split", "unknown"))
    checkout_ref = _required_str(repo, "checkout_ref")
    task_id = _required_str(task, "id")
    task_type = _required_str(task, "task_type")
    if task_type != "tests_only":
        raise _blocker_error(
            f"real-repo tests planner requires task_type='tests_only', got {task_type!r}",
            field="task_type",
            reason="unsupported_task_type",
        )

    prompt = _required_str(task, "prompt")
    allowed_write_paths = _string_sequence(
        task.get("allowed_write_paths"),
        field="allowed_write_paths",
    )
    validation_commands = _string_sequence(
        task.get("public_validation_commands"),
        field="public_validation_commands",
    )
    hidden_like_checks = _string_sequence(
        task.get("hidden_like_checks"),
        field="hidden_like_checks",
    )
    expected_failure_modes = _string_sequence(
        task.get("expected_failure_modes"),
        field="expected_failure_modes",
    )

    coverage = encode_repo_state_coverage(resolved_repo).to_record()
    knowledge_records = _validated_knowledge_records(
        local_knowledge_records,
        repo_id=repo_id,
        task_id=task_id,
    )
    citations = _knowledge_citations(
        knowledge_records,
        task_id=task_id,
        allowed_write_paths=allowed_write_paths,
        validation_commands=validation_commands,
        coverage=coverage,
    )
    target_selection = _select_target_test_file(
        coverage=coverage,
        allowed_write_paths=allowed_write_paths,
        validation_commands=validation_commands,
        citations=citations,
    )
    target_test_file = str(target_selection["path"])
    import_style_evidence = _import_style_evidence(
        coverage=coverage,
        target_test_file=target_test_file,
        knowledge_records=knowledge_records,
    )
    if import_style_evidence["knowledge_record_ids"]:  # type: ignore[index]
        citations["import_style"] = _unique(
            [
                *citations.get("import_style", []),
                *_string_sequence(
                    import_style_evidence["knowledge_record_ids"],
                    field="knowledge_record_ids",
                ),
            ]
        )
    retrieved_record_ids = _knowledge_record_ids(knowledge_records)
    missing_knowledge_purposes = _missing_knowledge_purposes(citations)
    knowledge_residual_labels = _knowledge_residual_labels(
        retrieved_record_ids=retrieved_record_ids,
        citations=citations,
        missing_purposes=missing_knowledge_purposes,
    )

    production_files = _production_python_files(coverage)
    production_hashes = _file_hashes(resolved_repo, production_files)
    selected_validation_command = (
        _validation_command_for_target(validation_commands, target_test_file)
        or validation_commands[0]
    )
    materialization = _materialize_pytest_cases_for_task(
        resolved_repo,
        repo_id=repo_id,
        task_id=task_id,
        target_test_file=target_test_file,
        import_style_evidence=import_style_evidence,
        write=write,
    )
    files_changed = _string_sequence(
        materialization["files_changed"],
        field="materialization.files_changed",
    )
    candidate_after = _mapping(
        materialization["candidate_after"],
        field="materialization.candidate_after",
    )
    production_hashes_after = _file_hashes(resolved_repo, production_files)
    production_changed = [
        path
        for path in production_files
        if production_hashes.get(path) != production_hashes_after.get(path)
    ]

    blockers: list[dict[str, str]] = []
    materialization_blocker = materialization.get("blocker")
    if materialization_blocker is not None:
        blockers.append(dict(_mapping(materialization_blocker, field="blocker")))
    if production_changed:
        blockers.append(
            {
                "field": "production_files",
                "reason": "production_file_modified",
                "message": "tests-only materialization changed a production file",
            }
        )

    residual_labels: list[str] = []
    if blockers:
        residual_labels.extend(blocker["reason"] for blocker in blockers)
    else:
        residual_labels.append(CANDIDATE_VALIDATION_DEFERRED)
    residual_labels.extend(
        label for label in knowledge_residual_labels if label not in residual_labels
    )

    status = str(materialization["status"])
    if blockers:
        status = "blocked"
    validation_not_run_reason = (
        residual_labels[0] if residual_labels else CANDIDATE_VALIDATION_DEFERRED
    )
    validation = {
        "status": "not_run",
        "commands": list(validation_commands),
        "selected_command": selected_validation_command,
        "not_run_reason": validation_not_run_reason,
        "candidate_validation_network_allowed": False,
    }
    mutation_scope = {
        "mode": "tests_only",
        "planned_write_files": [target_test_file],
        "files_changed": list(files_changed),
        "production_files": list(production_files),
        "production_files_changed": production_changed,
        "writes_outside_allowlist": _paths_outside_allowlist(
            files_changed,
            allowed_write_paths,
        ),
        "production_files_must_remain_unchanged": True,
        "candidate_after": {
            "target_test_file": target_test_file,
            "test_case_ids": list(candidate_after.get("test_case_ids", [])),
            "sha256_before": candidate_after.get("sha256_before"),
            "sha256_after": candidate_after.get("sha256_after"),
            "planned_changed_files": list(
                candidate_after.get("planned_changed_files", [])
            ),
        },
    }

    candidate_id = _candidate_id(
        repo_id=repo_id,
        checkout_ref=checkout_ref,
        task_id=task_id,
        target_test_file=target_test_file,
        validation_command=selected_validation_command,
        citations=citations,
        test_case_ids=_string_sequence(
            candidate_after.get("test_case_ids", []),
            field="candidate_after.test_case_ids",
        ),
    )
    knowledge_attribution = {
        "retrieved_record_ids": list(retrieved_record_ids),
        "cited_purposes": {
            purpose: list(record_ids) for purpose, record_ids in citations.items()
        },
        "required_purposes": list(REQUIRED_KNOWLEDGE_PURPOSES),
        "missing_purposes": list(missing_knowledge_purposes),
        "residual_labels": list(knowledge_residual_labels),
    }
    knowledge_use_record = build_knowledge_use_record(
        candidate_id=candidate_id,
        task_id=task_id,
        retrieved_record_ids=retrieved_record_ids,
        action_family=REAL_REPO_TESTS_ACTION_FAMILY,
        validation_result={
            "status": status,
            "command": selected_validation_command,
            "reason": validation_not_run_reason,
        },
        split=repo_split,
        residual_labels=residual_labels,
        cited_purposes=citations,
        required_purposes=REQUIRED_KNOWLEDGE_PURPOSES,
        missing_purposes=missing_knowledge_purposes,
    )

    actions = [
        RealRepoTestsAction(
            RealRepoTestsActionKind.INSPECT_REPO_STATE,
            payload={
                "coverage_schema_version": coverage.get("schema_version"),
                "test_files": _coverage_test_paths(coverage),
                "production_files": list(production_files),
                "packages": _json_copy(coverage.get("packages", [])),
                "configs": _json_copy(coverage.get("configs", [])),
            },
        ),
        RealRepoTestsAction(
            RealRepoTestsActionKind.SELECT_TEST_FILE,
            target=target_test_file,
            payload=target_selection,
        ),
        RealRepoTestsAction(
            RealRepoTestsActionKind.SELECT_IMPORT_STYLE,
            target=target_test_file,
            payload=import_style_evidence,
        ),
        RealRepoTestsAction(
            RealRepoTestsActionKind.MATERIALIZE_PYTEST_CASES,
            target=target_test_file,
            payload={
                "status": status,
                "test_framework": "pytest",
                "cases": _json_copy(materialization["cases"]),
                "blocker": materialization.get("blocker"),
                "write_policy": "append_or_refine_test_file_only",
                "production_files_must_remain_unchanged": True,
                "candidate_after": _json_copy(candidate_after),
            },
        ),
        RealRepoTestsAction(
            RealRepoTestsActionKind.VALIDATE,
            payload={
                "commands": list(validation_commands),
                "selected_command": selected_validation_command,
                "status": "not_run",
                "not_run_reason": validation_not_run_reason,
            },
        ),
    ]

    return RealRepoTestsCandidate(
        candidate_id=candidate_id,
        repo_id=repo_id,
        repo_split=repo_split,
        checkout_ref=checkout_ref,
        task_id=task_id,
        task_type=task_type,
        prompt=prompt,
        status=status,
        target_test_file=target_test_file,
        validation_commands=list(validation_commands),
        allowed_write_paths=list(allowed_write_paths),
        hidden_like_checks=list(hidden_like_checks),
        expected_failure_modes=list(expected_failure_modes),
        production_files=list(production_files),
        production_file_hashes_before=production_hashes,
        actions=actions,
        repo_state_evidence={
            "coverage_schema_version": coverage.get("schema_version"),
            "selected_test_file": target_test_file,
            "repo_state_confirmed_test_file": bool(
                target_selection["repo_state_confirmed"]
            ),
            "parse_errors": _json_copy(coverage.get("parse_errors", [])),
        },
        import_style_evidence=import_style_evidence,
        mutation_scope=mutation_scope,
        candidate_after=dict(candidate_after),
        validation=validation,
        knowledge_citations=citations,
        knowledge_attribution=knowledge_attribution,
        knowledge_use_record=knowledge_use_record,
        blockers=blockers,
        residual_labels=residual_labels,
    )


def blocker_from_error(error: RealRepoTestsPlannerError) -> dict[str, str]:
    """Return a JSON-compatible planner blocker."""

    return dict(error.blocker)


def _materialize_pytest_cases_for_task(
    repo: Path,
    *,
    repo_id: str,
    task_id: str,
    target_test_file: str,
    import_style_evidence: Mapping[str, object],
    write: bool,
) -> dict[str, object]:
    if repo_id == "iniconfig" and task_id == INICONFIG_PARSE_COMMENTS_TASK_ID:
        return _materialize_iniconfig_parse_comments_tests(
            repo,
            target_test_file=target_test_file,
            import_style_evidence=import_style_evidence,
            write=write,
        )
    if repo_id == "h11" and task_id == H11_BYTESIFY_MEMORYVIEW_TASK_ID:
        return _materialize_h11_bytesify_memoryview_tests(
            repo,
            target_test_file=target_test_file,
            import_style_evidence=import_style_evidence,
            write=write,
        )
    if (
        repo_id == "humanize"
        and task_id == HUMANIZE_NATURALSIZE_NEGATIVE_STRINGS_TASK_ID
    ):
        return _materialize_humanize_naturalsize_negative_strings_tests(
            repo,
            target_test_file=target_test_file,
            import_style_evidence=import_style_evidence,
            write=write,
        )
    if repo_id == "boltons" and task_id == BOLTONS_SLUGIFY_DELIMITER_TASK_ID:
        return _materialize_boltons_slugify_delimiter_tests(
            repo,
            target_test_file=target_test_file,
            import_style_evidence=import_style_evidence,
            write=write,
        )

    blocker = {
        "field": "test_case_materialization",
        "reason": TEST_CASE_MATERIALIZATION_BLOCKER,
        "message": (
            "behavior-specific pytest case materialization is only "
            "implemented for iniconfig-tests-parse-comments and "
            "h11-tests-bytesify-memoryview and "
            "humanize-tests-naturalsize-negative-strings and "
            "boltons-tests-slugify-delimiter"
        ),
    }
    return _blocked_materialization(target_test_file, blocker)


def _materialize_iniconfig_parse_comments_tests(
    repo: Path,
    *,
    target_test_file: str,
    import_style_evidence: Mapping[str, object],
    write: bool,
) -> dict[str, object]:
    api_blocker = _iniconfig_api_blocker(import_style_evidence)
    if api_blocker is not None:
        return _blocked_materialization(target_test_file, api_blocker)

    target_path = _repo_path(repo, target_test_file)
    before_text = (
        target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    )
    after_text = _merge_iniconfig_parse_comments_tests(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")

    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []

    case_records = _iniconfig_parse_comments_case_records()
    return {
        "status": status,
        "files_changed": files_changed,
        "cases": case_records,
        "candidate_after": _candidate_after_record(
            target_test_file=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            case_records=case_records,
        ),
    }


def _materialize_h11_bytesify_memoryview_tests(
    repo: Path,
    *,
    target_test_file: str,
    import_style_evidence: Mapping[str, object],
    write: bool,
) -> dict[str, object]:
    api_blocker = _h11_bytesify_api_blocker(import_style_evidence)
    if api_blocker is not None:
        return _blocked_materialization(target_test_file, api_blocker)

    target_path = _repo_path(repo, target_test_file)
    before_text = (
        target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    )
    after_text = _merge_h11_bytesify_memoryview_tests(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")

    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []

    case_records = _h11_bytesify_memoryview_case_records()
    return {
        "status": status,
        "files_changed": files_changed,
        "cases": case_records,
        "candidate_after": _candidate_after_record(
            target_test_file=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            case_records=case_records,
        ),
    }


def _materialize_humanize_naturalsize_negative_strings_tests(
    repo: Path,
    *,
    target_test_file: str,
    import_style_evidence: Mapping[str, object],
    write: bool,
) -> dict[str, object]:
    api_blocker = _humanize_naturalsize_api_blocker(import_style_evidence)
    if api_blocker is not None:
        return _blocked_materialization(target_test_file, api_blocker)

    target_path = _repo_path(repo, target_test_file)
    before_text = (
        target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    )
    after_text = _merge_humanize_naturalsize_negative_strings_tests(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")

    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []

    case_records = _humanize_naturalsize_negative_strings_case_records()
    return {
        "status": status,
        "files_changed": files_changed,
        "cases": case_records,
        "candidate_after": _candidate_after_record(
            target_test_file=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            case_records=case_records,
        ),
    }


def _materialize_boltons_slugify_delimiter_tests(
    repo: Path,
    *,
    target_test_file: str,
    import_style_evidence: Mapping[str, object],
    write: bool,
) -> dict[str, object]:
    api_blocker = _boltons_slugify_api_blocker(import_style_evidence)
    if api_blocker is not None:
        return _blocked_materialization(target_test_file, api_blocker)

    target_path = _repo_path(repo, target_test_file)
    before_text = (
        target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    )
    after_text = _merge_boltons_slugify_delimiter_tests(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")

    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []

    case_records = _boltons_slugify_delimiter_case_records()
    return {
        "status": status,
        "files_changed": files_changed,
        "cases": case_records,
        "candidate_after": _candidate_after_record(
            target_test_file=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            case_records=case_records,
        ),
    }


def _blocked_materialization(
    target_test_file: str,
    blocker: Mapping[str, str],
) -> dict[str, object]:
    return {
        "status": "blocked",
        "files_changed": [],
        "cases": [],
        "blocker": dict(blocker),
        "candidate_after": {
            "target_test_file": target_test_file,
            "available": False,
            "test_case_ids": [],
            "planned_changed_files": [],
            "wrote_file": False,
            "not_available_reason": blocker["reason"],
        },
    }


def _iniconfig_api_blocker(
    import_style_evidence: Mapping[str, object],
) -> dict[str, str] | None:
    selected = {
        (str(item.get("module", "")), str(item.get("imported", "")))
        for item_value in _sequence(
            import_style_evidence.get("selected_public_imports", []),
            field="selected_public_imports",
        )
        for item in [_mapping(item_value, field="selected_public_import")]
    }
    required = {("iniconfig", "IniConfig"), ("iniconfig", "ParseError")}
    missing = sorted(f"{module}.{name}" for module, name in required - selected)
    if not missing:
        return None
    return {
        "field": "public_api",
        "reason": "unsupported_public_api",
        "message": (
            "iniconfig test materialization requires existing tests to import "
            "IniConfig and ParseError; missing " + ", ".join(missing)
        ),
    }


def _h11_bytesify_api_blocker(
    import_style_evidence: Mapping[str, object],
) -> dict[str, str] | None:
    repo_imports = {
        (str(item.get("module", "")), str(item.get("imported", "")))
        for item_value in _sequence(
            import_style_evidence.get("repo_state_imports", []),
            field="repo_state_imports",
        )
        for item in [_mapping(item_value, field="repo_state_import")]
    }
    if (".._util", "bytesify") in repo_imports:
        return None
    return {
        "field": "public_api",
        "reason": "unsupported_public_api",
        "message": (
            "h11 bytesify test materialization requires the selected test file "
            "to import bytesify from .._util"
        ),
    }


def _humanize_naturalsize_api_blocker(
    import_style_evidence: Mapping[str, object],
) -> dict[str, str] | None:
    selected = {
        (str(item.get("module", "")), item.get("imported"))
        for item_value in _sequence(
            import_style_evidence.get("selected_public_imports", []),
            field="selected_public_imports",
        )
        for item in [_mapping(item_value, field="selected_public_import")]
    }
    if ("humanize", None) in selected:
        return None
    return {
        "field": "public_api",
        "reason": "unsupported_public_api",
        "message": (
            "humanize naturalsize test materialization requires the selected "
            "test file to import the public humanize module"
        ),
    }


def _boltons_slugify_api_blocker(
    import_style_evidence: Mapping[str, object],
) -> dict[str, str] | None:
    selected = {
        (str(item.get("module", "")), item.get("imported"))
        for item_value in _sequence(
            import_style_evidence.get("selected_public_imports", []),
            field="selected_public_imports",
        )
        for item in [_mapping(item_value, field="selected_public_import")]
    }
    if ("boltons", "strutils") in selected:
        return None
    return {
        "field": "public_api",
        "reason": "unsupported_public_api",
        "message": (
            "boltons slugify test materialization requires the selected test "
            "file to import strutils from the public boltons package"
        ),
    }


def _merge_iniconfig_parse_comments_tests(existing_text: str) -> str:
    required_functions = [
        "test_comment_only_lines_are_ignored_between_entries",
        "test_inline_section_comments_are_stripped",
        "test_duplicate_key_error_reports_offending_key",
    ]
    if all(f"def {name}" in existing_text for name in required_functions):
        return existing_text

    append_block = _render_iniconfig_parse_comments_tests_append_block()
    if not existing_text.strip():
        return (
            "from __future__ import annotations\n"
            "\n"
            "import pytest\n"
            "\n"
            "from iniconfig import IniConfig, ParseError\n"
            "\n\n"
            + append_block
        )
    return existing_text.rstrip() + "\n\n\n" + append_block


def _render_iniconfig_parse_comments_tests_append_block() -> str:
    return (
        '@pytest.mark.parametrize("marker", ["#", ";"])\n'
        "def test_comment_only_lines_are_ignored_between_entries(marker: str) -> None:\n"
        "    config = IniConfig(\n"
        '        "comments.ini",\n'
        "        data=(\n"
        '            f"{marker} file header comment\\n"\n'
        '            "[section]\\n"\n'
        '            f"{marker} comment before first key\\n"\n'
        '            "name = Alice\\n"\n'
        '            f"{marker} comment before second key\\n"\n'
        '            "role = Developer\\n"\n'
        "        ),\n"
        "    )\n"
        "\n"
        '    assert config["section"]["name"] == "Alice"\n'
        '    assert config["section"]["role"] == "Developer"\n'
        '    assert list(config["section"]) == ["name", "role"]\n'
        "\n\n"
        "@pytest.mark.parametrize(\n"
        '    ("marker", "section_name"),\n'
        '    [("#", "main"), (";", "secondary")],\n'
        ")\n"
        "def test_inline_section_comments_are_stripped(\n"
        "    marker: str, section_name: str\n"
        ") -> None:\n"
        "    config = IniConfig(\n"
        '        "comments.ini",\n'
        "        data=(\n"
        '            f"[{section_name}] {marker} inline section comment\\n"\n'
        '            "key = value\\n"\n'
        "        ),\n"
        "    )\n"
        "\n"
        "    assert list(config.sections) == [section_name]\n"
        '    assert config[section_name]["key"] == "value"\n'
        "\n\n"
        "def test_duplicate_key_error_reports_offending_key() -> None:\n"
        "    with pytest.raises(ParseError) as excinfo:\n"
        "        IniConfig(\n"
        '            "comments.ini",\n'
        '            data="[section]\\nname = Alice\\nname = Bob\\n",\n'
        "        )\n"
        "\n"
        "    assert excinfo.value.msg == \"duplicate name 'name'\"\n"
        "    assert excinfo.value.lineno == 2\n"
        '    assert "name" in str(excinfo.value)\n'
    )


def _merge_h11_bytesify_memoryview_tests(existing_text: str) -> str:
    required_functions = [
        "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
        "test_bytesify_rejects_non_ascii_str",
        "test_bytesify_rejects_int",
    ]
    if all(f"def {name}" in existing_text for name in required_functions):
        return existing_text

    append_block = _render_h11_bytesify_memoryview_tests_append_block()
    if not existing_text.strip():
        return (
            "from __future__ import annotations\n"
            "\n"
            "import pytest\n"
            "\n"
            "from .._util import bytesify\n"
            "\n\n"
            + append_block
        )
    return existing_text.rstrip() + "\n\n\n" + append_block


def _render_h11_bytesify_memoryview_tests_append_block() -> str:
    return (
        "@pytest.mark.parametrize(\n"
        '    ("value", "expected"),\n'
        "    [\n"
        '        (bytearray(b"hello"), b"hello"),\n'
        '        (memoryview(b"world"), b"world"),\n'
        '        ("ascii", b"ascii"),\n'
        "    ],\n"
        ")\n"
        "def test_bytesify_accepts_bytes_like_inputs_and_ascii_str(\n"
        "    value: object, expected: bytes\n"
        ") -> None:\n"
        "    assert bytesify(value) == expected\n"
        "\n\n"
        "def test_bytesify_rejects_non_ascii_str() -> None:\n"
        "    with pytest.raises(UnicodeEncodeError):\n"
        '        bytesify("snowman: \\u2603")\n'
        "\n\n"
        "def test_bytesify_rejects_int() -> None:\n"
        "    with pytest.raises(TypeError, match=\"int\"):\n"
        "        bytesify(10)\n"
    )


def _merge_humanize_naturalsize_negative_strings_tests(existing_text: str) -> str:
    required_functions = [
        "test_naturalsize_accepts_negative_numeric_strings",
        "test_naturalsize_formats_negative_gnu_suffixes",
        "test_naturalsize_formats_negative_binary_suffixes",
    ]
    if all(f"def {name}" in existing_text for name in required_functions):
        return existing_text

    append_block = _render_humanize_naturalsize_negative_strings_tests_append_block()
    if not existing_text.strip():
        return (
            "from __future__ import annotations\n"
            "\n"
            "import pytest\n"
            "\n"
            "import humanize\n"
            "\n\n"
            + append_block
        )
    return existing_text.rstrip() + "\n\n\n" + append_block


def _render_humanize_naturalsize_negative_strings_tests_append_block() -> str:
    return (
        "@pytest.mark.parametrize(\n"
        '    ("value", "expected"),\n'
        "    [\n"
        '        ("-300", "-300 Bytes"),\n'
        '        ("-1000", "-1.0 kB"),\n'
        '        ("-1000000", "-1.0 MB"),\n'
        "    ],\n"
        ")\n"
        "def test_naturalsize_accepts_negative_numeric_strings(\n"
        "    value: str, expected: str\n"
        ") -> None:\n"
        "    assert humanize.naturalsize(value) == expected\n"
        "\n\n"
        "@pytest.mark.parametrize(\n"
        '    ("value", "expected"),\n'
        "    [\n"
        '        ("-1024", "-1.0K"),\n'
        '        ("-1048576", "-1.0M"),\n'
        '        ("-1073741824", "-1.0G"),\n'
        "    ],\n"
        ")\n"
        "def test_naturalsize_formats_negative_gnu_suffixes(\n"
        "    value: str, expected: str\n"
        ") -> None:\n"
        "    assert humanize.naturalsize(value, gnu=True) == expected\n"
        "\n\n"
        "@pytest.mark.parametrize(\n"
        '    ("value", "expected"),\n'
        "    [\n"
        '        ("-1024", "-1.0 KiB"),\n'
        '        ("-1048576", "-1.0 MiB"),\n'
        '        ("-1073741824", "-1.0 GiB"),\n'
        "    ],\n"
        ")\n"
        "def test_naturalsize_formats_negative_binary_suffixes(\n"
        "    value: str, expected: str\n"
        ") -> None:\n"
        "    assert humanize.naturalsize(value, binary=True) == expected\n"
    )


def _merge_boltons_slugify_delimiter_tests(existing_text: str) -> str:
    required_functions = [
        "test_slugify_accepts_custom_delimiters",
        "test_slugify_empty_string_stays_empty",
        "test_slugify_ascii_mode_returns_bytes",
        "test_slugify_preserves_case_when_lower_false",
    ]
    if all(f"def {name}" in existing_text for name in required_functions):
        return existing_text

    append_block = _render_boltons_slugify_delimiter_tests_append_block()
    if not existing_text.strip():
        return (
            "from __future__ import annotations\n"
            "\n"
            "from boltons import strutils\n"
            "\n\n"
            + append_block
        )
    return existing_text.rstrip() + "\n\n\n" + append_block


def _render_boltons_slugify_delimiter_tests_append_block() -> str:
    return (
        "def test_slugify_accepts_custom_delimiters() -> None:\n"
        "    assert strutils.slugify(\n"
        '        "First post! Hi!!!!~1    ", delim="-"\n'
        '    ) == "first-post-hi-1"\n'
        "    assert strutils.slugify(\n"
        '        "dots.and spaces / symbols", delim="--"\n'
        '    ) == "dots--and--spaces--symbols"\n'
        "\n\n"
        "def test_slugify_empty_string_stays_empty() -> None:\n"
        '    assert strutils.slugify("") == ""\n'
        '    assert strutils.slugify("", delim="-") == ""\n'
        "\n\n"
        "def test_slugify_ascii_mode_returns_bytes() -> None:\n"
        "    result = strutils.slugify(\"Kurt G\\u00f6del's pretty cool.\", ascii=True)\n"
        "\n"
        "    assert result == b\"kurt_goedel_s_pretty_cool\"\n"
        "    assert isinstance(result, bytes)\n"
        "\n\n"
        "def test_slugify_preserves_case_when_lower_false() -> None:\n"
        "    assert strutils.slugify(\n"
        '        "MiXeD Case Input", delim="-", lower=False\n'
        '    ) == "MiXeD-Case-Input"\n'
    )


def _h11_bytesify_memoryview_case_records() -> list[dict[str, object]]:
    return [
        {
            "id": "h11_bytesify_bytearray",
            "behavior": "bytearray input is converted to exact bytes",
            "function": "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
            "assertions": ["bytearray(b'hello') returns b'hello'"],
        },
        {
            "id": "h11_bytesify_memoryview",
            "behavior": "memoryview input is converted to exact bytes",
            "function": "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
            "assertions": ["memoryview(b'world') returns b'world'"],
        },
        {
            "id": "h11_bytesify_ascii_str",
            "behavior": "ASCII str input is encoded as ASCII bytes",
            "function": "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
            "assertions": ["'ascii' returns b'ascii'"],
        },
        {
            "id": "h11_bytesify_non_ascii_str",
            "behavior": "non-ASCII str input preserves UnicodeEncodeError behavior",
            "function": "test_bytesify_rejects_non_ascii_str",
            "assertions": ["non-ASCII str raises UnicodeEncodeError"],
        },
        {
            "id": "h11_bytesify_int_type_error",
            "behavior": "int input preserves TypeError behavior",
            "function": "test_bytesify_rejects_int",
            "assertions": ["int input raises TypeError mentioning int"],
        },
    ]


def _humanize_naturalsize_negative_strings_case_records() -> list[dict[str, object]]:
    return [
        {
            "id": "humanize_naturalsize_negative_numeric_strings",
            "behavior": "negative numeric strings keep their sign in decimal mode",
            "function": "test_naturalsize_accepts_negative_numeric_strings",
            "assertions": [
                "negative string bytes below base stay negative",
                "negative string decimal suffixes keep the leading minus sign",
            ],
        },
        {
            "id": "humanize_naturalsize_negative_gnu_suffixes",
            "behavior": "negative numeric strings use compact GNU suffixes",
            "function": "test_naturalsize_formats_negative_gnu_suffixes",
            "assertions": [
                "negative string KiB-scale values render with K",
                "negative string MiB/GiB-scale values render with M/G",
            ],
        },
        {
            "id": "humanize_naturalsize_negative_binary_suffixes",
            "behavior": "negative numeric strings use binary suffix labels",
            "function": "test_naturalsize_formats_negative_binary_suffixes",
            "assertions": [
                "negative string KiB-scale values render with KiB",
                "negative string MiB/GiB-scale values render with MiB/GiB",
            ],
        },
    ]


def _boltons_slugify_delimiter_case_records() -> list[dict[str, object]]:
    return [
        {
            "id": "boltons_slugify_custom_delimiters",
            "behavior": "custom delimiters join punctuation and whitespace splits",
            "function": "test_slugify_accepts_custom_delimiters",
            "assertions": [
                "hyphen delimiter replaces default underscore",
                "multi-character delimiter is preserved between words",
            ],
        },
        {
            "id": "boltons_slugify_empty_string",
            "behavior": "empty string input remains empty for default and custom delimiters",
            "function": "test_slugify_empty_string_stays_empty",
            "assertions": ["empty input returns an empty string"],
        },
        {
            "id": "boltons_slugify_ascii_output",
            "behavior": "ascii=True returns ascii bytes output",
            "function": "test_slugify_ascii_mode_returns_bytes",
            "assertions": [
                "unicode characters are asciified",
                "result type is bytes",
            ],
        },
        {
            "id": "boltons_slugify_lower_false",
            "behavior": "lower=False preserves case while still applying delimiters",
            "function": "test_slugify_preserves_case_when_lower_false",
            "assertions": ["mixed-case words retain their original case"],
        },
    ]


def _iniconfig_parse_comments_case_records() -> list[dict[str, object]]:
    return [
        {
            "id": "iniconfig_comment_only_lines",
            "behavior": "comment-only lines are ignored between entries",
            "function": "test_comment_only_lines_are_ignored_between_entries",
            "comment_markers": ["#", ";"],
            "assertions": [
                "parsed section keeps real keys",
                "comment-only lines are not materialized as keys",
            ],
        },
        {
            "id": "iniconfig_inline_section_comments",
            "behavior": "inline section comments are stripped from section names",
            "function": "test_inline_section_comments_are_stripped",
            "comment_markers": ["#", ";"],
            "assertions": [
                "section name excludes inline comment text",
                "key after commented section remains accessible",
            ],
        },
        {
            "id": "iniconfig_duplicate_key_reports_name",
            "behavior": "duplicate key ParseError reports offending key name",
            "function": "test_duplicate_key_error_reports_offending_key",
            "comment_markers": [],
            "assertions": [
                "ParseError.msg includes duplicate key name",
                "ParseError line number points at duplicate assignment",
            ],
        },
    ]


def _candidate_after_record(
    *,
    target_test_file: str,
    before_text: str,
    after_text: str,
    planned_changed_files: Sequence[str],
    wrote_file: bool,
    case_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    diff_lines = list(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=f"a/{target_test_file}",
            tofile=f"b/{target_test_file}",
            lineterm="",
        )
    )
    added_lines = [
        line
        for line in diff_lines
        if line.startswith("+") and not line.startswith("+++")
    ]
    removed_lines = [
        line
        for line in diff_lines
        if line.startswith("-") and not line.startswith("---")
    ]
    return {
        "target_test_file": target_test_file,
        "available": True,
        "wrote_file": wrote_file,
        "planned_changed_files": list(planned_changed_files),
        "test_case_ids": [str(case["id"]) for case in case_records],
        "test_functions": [str(case["function"]) for case in case_records],
        "sha256_before": hashlib.sha256(before_text.encode("utf-8")).hexdigest(),
        "sha256_after": hashlib.sha256(after_text.encode("utf-8")).hexdigest(),
        "byte_count_before": len(before_text.encode("utf-8")),
        "byte_count_after": len(after_text.encode("utf-8")),
        "diff_summary": {
            "added_line_count": len(added_lines),
            "removed_line_count": len(removed_lines),
            "changed": before_text != after_text,
        },
        "diff": "\n".join(diff_lines),
    }


def _validated_knowledge_records(
    records: Sequence[Mapping[str, object]],
    *,
    repo_id: str,
    task_id: str,
) -> tuple[Mapping[str, object], ...]:
    validated = []
    for record in records:
        validate_local_knowledge_record(record)
        source = _mapping(record.get("source"), field="knowledge.source")
        links = _mapping(record.get("links"), field="knowledge.links")
        task_ids = _string_sequence(links.get("task_ids", []), field="task_ids")
        source_repo = str(source.get("repo", ""))
        if source_repo == repo_id or task_id in task_ids:
            validated.append(record)
    return tuple(validated)


def _knowledge_record_ids(records: Sequence[Mapping[str, object]]) -> list[str]:
    return _unique([_required_str(record, "id") for record in records])


def _missing_knowledge_purposes(
    citations: Mapping[str, Sequence[str]],
) -> list[str]:
    return [
        purpose
        for purpose in REQUIRED_KNOWLEDGE_PURPOSES
        if not citations.get(purpose)
    ]


def _knowledge_residual_labels(
    *,
    retrieved_record_ids: Sequence[str],
    citations: Mapping[str, Sequence[str]],
    missing_purposes: Sequence[str],
) -> list[str]:
    if not retrieved_record_ids or not citations:
        return ["knowledge_not_used"]
    if missing_purposes:
        return ["missing_knowledge"]
    return []


def _knowledge_citations(
    records: Sequence[Mapping[str, object]],
    *,
    task_id: str,
    allowed_write_paths: Sequence[str],
    validation_commands: Sequence[str],
    coverage: Mapping[str, object],
) -> dict[str, list[str]]:
    citations: dict[str, list[str]] = {}
    test_roots = {PurePosixPath(path).parts[0] for path in allowed_write_paths}
    coverage_tests = set(_coverage_test_paths(coverage))
    for record in records:
        record_id = _required_str(record, "id")
        record_type = record.get("record_type")
        data = _mapping(record.get("data"), field="knowledge.data")
        links = _mapping(record.get("links"), field="knowledge.links")

        if record_type == "pytest_layout_record":
            roots = set(_string_sequence(data.get("test_roots", []), field="test_roots"))
            examples = _sequence(data.get("adjacent_examples", []), field="adjacent_examples")
            example_paths = {
                str(_mapping(example, field="adjacent_example").get("path", ""))
                for example in examples
            }
            if roots & test_roots or example_paths & coverage_tests:
                citations.setdefault("test_location", []).append(record_id)
        elif record_type == "validation_recipe_record":
            linked_task_ids = _string_sequence(
                links.get("task_ids", []),
                field="links.task_ids",
            )
            focused = _string_sequence(
                data.get("focused_commands", []),
                field="focused_commands",
            )
            allowed = _string_sequence(
                data.get("allowed_write_paths", []),
                field="allowed_write_paths",
            )
            if task_id in linked_task_ids:
                if set(allowed) & set(allowed_write_paths):
                    citations.setdefault("test_location", []).append(record_id)
                if set(focused) & set(validation_commands):
                    citations.setdefault("validation", []).append(record_id)
        elif record_type == "pytest_pattern_record":
            source_path = str(data.get("source_path", ""))
            if source_path in coverage_tests:
                citations.setdefault("pytest_style", []).append(record_id)

    return {
        purpose: _unique(record_ids)
        for purpose, record_ids in sorted(citations.items())
    }


def _select_target_test_file(
    *,
    coverage: Mapping[str, object],
    allowed_write_paths: Sequence[str],
    validation_commands: Sequence[str],
    citations: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    coverage_tests = set(_coverage_test_paths(coverage))
    normalized_allowed = [_normalize_relative_path(path) for path in allowed_write_paths]
    command_paths = [
        path
        for command in validation_commands
        for path in _pytest_paths_from_command(command)
    ]
    candidates = _unique([*normalized_allowed, *command_paths])
    target = next((path for path in candidates if path in coverage_tests), None)
    if target is None:
        target = next((path for path in candidates if _is_test_path(path)), None)
    if target is None:
        raise _blocker_error(
            "could not select a repository-relative pytest target file",
            field="target_test_file",
            reason="wrong_test_location",
        )

    return {
        "path": target,
        "selection_sources": _unique(
            [
                *(
                    ["task.allowed_write_paths"]
                    if target in normalized_allowed
                    else []
                ),
                *(
                    ["task.public_validation_commands"]
                    if target in command_paths
                    else []
                ),
                *(
                    ["local_knowledge.validation_recipe_record"]
                    if citations.get("validation")
                    else []
                ),
                *(
                    ["local_knowledge.pytest_layout_record"]
                    if citations.get("test_location")
                    else []
                ),
            ]
        ),
        "repo_state_confirmed": target in coverage_tests,
        "coverage_test_files": sorted(coverage_tests),
        "allowed_write_paths": list(normalized_allowed),
        "validation_commands": list(validation_commands),
        "knowledge_record_ids": _unique(
            [
                *citations.get("test_location", ()),
                *citations.get("validation", ()),
            ]
        ),
    }


def _import_style_evidence(
    *,
    coverage: Mapping[str, object],
    target_test_file: str,
    knowledge_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    repo_state_imports = [
        _json_copy(item)
        for item in _sequence(coverage.get("imports", []), field="coverage.imports")
        if _mapping(item, field="coverage.import")["path"] == target_test_file
    ]
    public_imports = [
        item
        for item in repo_state_imports
        if _is_public_import(_mapping(item, field="repo_state_import"))
    ]
    examples: list[dict[str, object]] = []
    record_ids: list[str] = []
    for record in knowledge_records:
        if record.get("record_type") != "public_api_record":
            continue
        data = _mapping(record.get("data"), field="public_api.data")
        for example in _sequence(
            data.get("test_import_examples", []),
            field="test_import_examples",
        ):
            example_record = _mapping(example, field="test_import_example")
            if example_record.get("path") == target_test_file:
                examples.append(dict(example_record))
                record_ids.append(_required_str(record, "id"))

    return {
        "target_test_file": target_test_file,
        "repo_state_imports": repo_state_imports,
        "selected_public_imports": public_imports,
        "local_knowledge_import_examples": examples,
        "knowledge_record_ids": _unique(record_ids),
    }


def _production_python_files(coverage: Mapping[str, object]) -> list[str]:
    production_files = []
    for file_value in _sequence(coverage.get("files", []), field="coverage.files"):
        file_record = _mapping(file_value, field="coverage.file")
        path = _required_str(file_record, "path")
        roles = _string_sequence(file_record.get("roles"), field="coverage.file.roles")
        if "python" not in roles or "test" in roles or "config" in roles:
            continue
        if PurePosixPath(path).name == "conftest.py":
            continue
        production_files.append(path)
    return sorted(production_files)


def _coverage_test_paths(coverage: Mapping[str, object]) -> list[str]:
    return [
        _required_str(_mapping(item, field="coverage.test"), "path")
        for item in _sequence(coverage.get("tests", []), field="coverage.tests")
    ]


def _validation_command_for_target(
    validation_commands: Sequence[str],
    target_test_file: str,
) -> str | None:
    for command in validation_commands:
        if target_test_file in _pytest_paths_from_command(command):
            return command
    return None


def _pytest_paths_from_command(command: str) -> list[str]:
    paths = []
    for token in command.split():
        if token.startswith("-"):
            continue
        if token.endswith(".py") and "/" in token:
            try:
                paths.append(_normalize_relative_path(token))
            except ValueError:
                continue
    return paths


def _paths_outside_allowlist(
    candidate_paths: Sequence[str],
    allowed_write_paths: Sequence[str],
) -> list[str]:
    allowed = tuple(_normalize_relative_path(path) for path in allowed_write_paths)
    violations = []
    for candidate_path in candidate_paths:
        candidate = _normalize_relative_path(candidate_path)
        if not any(
            candidate == allowed_path
            or candidate.startswith(f"{allowed_path.rstrip('/')}/")
            for allowed_path in allowed
        ):
            violations.append(candidate)
    return violations


def _file_hashes(repo: Path, relative_paths: Sequence[str]) -> dict[str, str]:
    hashes = {}
    for relative_path in relative_paths:
        path = _repo_path(repo, relative_path)
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _repo_path(repo: Path, relative_path: str) -> Path:
    return repo / Path(*PurePosixPath(_normalize_relative_path(relative_path)).parts)


def _candidate_id(
    *,
    repo_id: str,
    checkout_ref: str,
    task_id: str,
    target_test_file: str,
    validation_command: str,
    citations: Mapping[str, Sequence[str]],
    test_case_ids: Sequence[str],
) -> str:
    return "real-repo-tests-" + _sha256_json(
        {
            "repo_id": repo_id,
            "checkout_ref": checkout_ref,
            "task_id": task_id,
            "target_test_file": target_test_file,
            "validation_command": validation_command,
            "citations": {key: list(value) for key, value in citations.items()},
            "test_case_ids": list(test_case_ids),
        }
    )[:16]


def _is_public_import(import_record: Mapping[str, object]) -> bool:
    module = str(import_record.get("module", ""))
    if not module or module == "__future__" or module.startswith("."):
        return False
    root = module.split(".", 1)[0]
    return root not in {"pytest", "unittest", "typing", "pathlib", "os", "sys"}


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        "tests" in pure.parts
        or "testing" in pure.parts
        or pure.name.startswith("test_")
        or pure.name.endswith("_test.py")
    )


def _normalize_relative_path(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"path must be repository-relative: {path}")
    normalized = pure.as_posix().strip("/")
    if not normalized or normalized == ".":
        raise ValueError("path must not be empty")
    return normalized


def _blocker_error(
    message: str,
    *,
    field: str,
    reason: str,
) -> RealRepoTestsPlannerError:
    return RealRepoTestsPlannerError(
        message,
        blocker={
            "field": field,
            "reason": reason,
            "message": message,
        },
    )


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_sequence(value: object, *, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence of strings")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{field} entries must be non-empty strings")
        result.append(item)
    return result


def _sequence(value: object, *, field: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence")
    return tuple(value)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
