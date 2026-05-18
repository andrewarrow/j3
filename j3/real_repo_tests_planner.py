"""Repo-state-aware tests-only planning for real-repo ladder tasks."""

from __future__ import annotations

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
    validation: dict[str, object] = field(default_factory=dict)
    knowledge_citations: dict[str, list[str]] = field(default_factory=dict)
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
            "validation": _json_copy(self.validation),
            "knowledge_citations": {
                purpose: list(record_ids)
                for purpose, record_ids in self.knowledge_citations.items()
            },
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
) -> RealRepoTestsCandidate:
    """Plan a non-mutating tests-only candidate from repo state and knowledge.

    This first generic real-repo planner intentionally stops before behavior-
    specific pytest case materialization. The candidate is useful because it
    proves the planner can select the local test file and import style without
    editing production files, then emits a precise materialization blocker.
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

    production_files = _production_python_files(coverage)
    production_hashes = _file_hashes(resolved_repo, production_files)
    selected_validation_command = (
        _validation_command_for_target(validation_commands, target_test_file)
        or validation_commands[0]
    )
    residual_labels = [TEST_CASE_MATERIALIZATION_BLOCKER]
    if not citations:
        residual_labels.append("knowledge_not_used")

    blocker = {
        "field": "test_case_materialization",
        "reason": TEST_CASE_MATERIALIZATION_BLOCKER,
        "message": (
            "repo-state test placement and import style are selected, but "
            "behavior-specific pytest case materialization is not implemented"
        ),
    }
    validation = {
        "status": "not_run",
        "commands": list(validation_commands),
        "selected_command": selected_validation_command,
        "not_run_reason": TEST_CASE_MATERIALIZATION_BLOCKER,
        "candidate_validation_network_allowed": False,
    }
    mutation_scope = {
        "mode": "tests_only",
        "planned_write_files": [target_test_file],
        "files_changed": [],
        "production_files": list(production_files),
        "production_files_changed": [],
        "writes_outside_allowlist": _paths_outside_allowlist(
            [target_test_file],
            allowed_write_paths,
        ),
        "production_files_must_remain_unchanged": True,
    }

    candidate_id = _candidate_id(
        repo_id=repo_id,
        checkout_ref=checkout_ref,
        task_id=task_id,
        target_test_file=target_test_file,
        validation_command=selected_validation_command,
        citations=citations,
    )
    retrieved_record_ids = _unique(
        [record_id for record_ids in citations.values() for record_id in record_ids]
    )
    knowledge_use_record = None
    if retrieved_record_ids:
        knowledge_use_record = build_knowledge_use_record(
            candidate_id=candidate_id,
            task_id=task_id,
            retrieved_record_ids=retrieved_record_ids,
            action_family=REAL_REPO_TESTS_ACTION_FAMILY,
            validation_result={
                "status": "blocked",
                "command": selected_validation_command,
                "reason": TEST_CASE_MATERIALIZATION_BLOCKER,
            },
            split=repo_split,
            residual_labels=residual_labels,
            cited_purposes=citations,
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
                "status": "blocked",
                "blocker": TEST_CASE_MATERIALIZATION_BLOCKER,
                "write_policy": "append_or_refine_test_file_only",
                "production_files_must_remain_unchanged": True,
            },
        ),
        RealRepoTestsAction(
            RealRepoTestsActionKind.VALIDATE,
            payload={
                "commands": list(validation_commands),
                "selected_command": selected_validation_command,
                "status": "not_run",
                "not_run_reason": TEST_CASE_MATERIALIZATION_BLOCKER,
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
        status="blocked",
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
        validation=validation,
        knowledge_citations=citations,
        knowledge_use_record=knowledge_use_record,
        blockers=[blocker],
        residual_labels=residual_labels,
    )


def blocker_from_error(error: RealRepoTestsPlannerError) -> dict[str, str]:
    """Return a JSON-compatible planner blocker."""

    return dict(error.blocker)


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
        path = repo / Path(*PurePosixPath(relative_path).parts)
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _candidate_id(
    *,
    repo_id: str,
    checkout_ref: str,
    task_id: str,
    target_test_file: str,
    validation_command: str,
    citations: Mapping[str, Sequence[str]],
) -> str:
    return "real-repo-tests-" + _sha256_json(
        {
            "repo_id": repo_id,
            "checkout_ref": checkout_ref,
            "task_id": task_id,
            "target_test_file": target_test_file,
            "validation_command": validation_command,
            "citations": {key: list(value) for key, value in citations.items()},
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
