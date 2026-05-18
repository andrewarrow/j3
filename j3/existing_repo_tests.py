"""Tests-only existing-repo support for one-file GreenShot-7 libraries."""

from __future__ import annotations

import ast
import hashlib
import json
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from j3.repo_state import encode_repo_state_coverage
from j3.request_spec import RequestSpec


TESTS_SPEC_SCHEMA_VERSION = "existing-repo-tests-spec-v1"
TESTS_PLAN_SCHEMA_VERSION = "existing-repo-tests-plan-v1"
TESTS_RESULT_SCHEMA_VERSION = "existing-repo-tests-result-v1"
TESTS_ATTEMPT_SCHEMA_VERSION = "existing-repo-tests-attempt-v1"
TESTS_ATTEMPT_KIND = "greenshot_7_existing_repo_tests_attempt"
SLUGIFY_SOURCE = "slugify.py"
SLUGIFY_TESTS = "tests/test_slugify.py"
SLUGIFY_FEATURES = ["slugify_ascii_lowercase"]
SLUGIFY_INTERFACES = [
    {"kind": "python_api", "module": "slugify", "callable": "slugify"}
]
SLUGIFY_VALIDATION_COMMAND = "python -m pytest tests/test_slugify.py -q"


class ExistingRepoTestsError(ValueError):
    """Raised when an existing repo is outside the tests-only support slice."""

    def __init__(self, message: str, *, blocker: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.blocker = blocker or {
            "field": "existing_repo_tests",
            "reason": "unsupported_existing_repo_tests_slice",
            "message": message,
        }


class ExistingRepoTestsActionKind(str, Enum):
    """Supported actions for one-file existing-repo tests-only changes."""

    INSPECT_REPO = "inspect_repo"
    INSPECT_ONE_FILE_LIBRARY = "inspect_one_file_library"
    ADD_EXISTING_REPO_TESTS = "add_existing_repo_tests"
    VALIDATE = "validate"


@dataclass(frozen=True, slots=True)
class ExistingRepoTestsSpec:
    """A JSON-compatible contract for adding tests to an existing small library."""

    schema_version: str
    task_name: str
    task_type: str
    repo_mode: str
    domain: str
    prompt: str
    source_files: list[str] = field(default_factory=list)
    target_test_files: list[str] = field(default_factory=list)
    production_files: list[str] = field(default_factory=list)
    interfaces: list[dict[str, str]] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_name": self.task_name,
            "task_type": self.task_type,
            "repo_mode": self.repo_mode,
            "domain": self.domain,
            "prompt": self.prompt,
            "source_files": list(self.source_files),
            "target_test_files": list(self.target_test_files),
            "production_files": list(self.production_files),
            "interfaces": [dict(interface) for interface in self.interfaces],
            "features": list(self.features),
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "change_policy": {
                "mode": "tests_only",
                "production_files_must_remain_unchanged": True,
            },
        }


@dataclass(frozen=True, slots=True)
class ExistingRepoTestsAction:
    """One structured action in the existing-repo tests-only plan."""

    kind: ExistingRepoTestsActionKind
    target: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.target is None:
            return
        pure_path = PurePosixPath(self.target)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise ValueError("target must be relative to the repository root")

    def to_record(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "target": self.target,
            "payload": _json_copy(self.payload),
        }


@dataclass(frozen=True, slots=True)
class ExistingRepoTestsPlan:
    """Structured action plan for a tests-only existing-repo edit."""

    schema_version: str
    spec_schema_version: str
    task_name: str
    task_type: str
    repo_mode: str
    domain: str
    status: str
    source_files: list[str] = field(default_factory=list)
    target_test_files: list[str] = field(default_factory=list)
    production_files: list[str] = field(default_factory=list)
    actions: list[ExistingRepoTestsAction] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "spec_schema_version": self.spec_schema_version,
            "task_name": self.task_name,
            "task_type": self.task_type,
            "repo_mode": self.repo_mode,
            "domain": self.domain,
            "status": self.status,
            "source_files": list(self.source_files),
            "target_test_files": list(self.target_test_files),
            "production_files": list(self.production_files),
            "actions": [action.to_record() for action in self.actions],
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "blockers": [dict(blocker) for blocker in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class ExistingRepoTestsResult:
    """Result of adding tests without modifying production files."""

    schema_version: str
    plan_schema_version: str
    status: str
    repo_path: str
    files_changed: list[str] = field(default_factory=list)
    target_test_files: list[str] = field(default_factory=list)
    production_files: list[str] = field(default_factory=list)
    production_files_changed: list[str] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)
    source_hashes_before: dict[str, str] = field(default_factory=dict)
    source_hashes_after: dict[str, str] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "plan_schema_version": self.plan_schema_version,
            "status": self.status,
            "repo_path": self.repo_path,
            "files_changed": list(self.files_changed),
            "target_test_files": list(self.target_test_files),
            "production_files": list(self.production_files),
            "production_files_changed": list(self.production_files_changed),
            "validation": _json_copy(self.validation),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "source_hashes_before": dict(self.source_hashes_before),
            "source_hashes_after": dict(self.source_hashes_after),
        }


@dataclass(frozen=True, slots=True)
class SlugifyRepoInspection:
    """Facts proving a repo fits the one-file slugify test-authoring slice."""

    source_path: Path
    tests_path: Path
    source_sha256: str
    source_byte_count: int
    function_names: list[str]
    slugify_arg_count: int


def existing_repo_tests_spec_from_request(spec: RequestSpec) -> ExistingRepoTestsSpec:
    """Convert a supported request-spec-v1 row into a tests-only change spec."""

    _validate_request_spec(spec)
    return ExistingRepoTestsSpec(
        schema_version=TESTS_SPEC_SCHEMA_VERSION,
        task_name=spec.task_name,
        task_type=spec.task_type,
        repo_mode=spec.repo_mode,
        domain=spec.domain,
        prompt=spec.prompt,
        source_files=[SLUGIFY_SOURCE],
        target_test_files=[SLUGIFY_TESTS],
        production_files=[SLUGIFY_SOURCE],
        interfaces=[dict(interface) for interface in SLUGIFY_INTERFACES],
        features=list(SLUGIFY_FEATURES),
        validation={
            "commands": [SLUGIFY_VALIDATION_COMMAND],
            "hidden_cases": True,
        },
    )


def plan_existing_repo_tests(
    spec: ExistingRepoTestsSpec,
    repo: Path,
) -> ExistingRepoTestsPlan:
    """Inspect an existing one-file slugify library and plan a tests-only edit."""

    _validate_tests_spec(spec)
    inspection = inspect_slugify_one_file_repo(repo)
    coverage = encode_repo_state_coverage(repo).to_record()
    return ExistingRepoTestsPlan(
        schema_version=TESTS_PLAN_SCHEMA_VERSION,
        spec_schema_version=spec.schema_version,
        task_name=spec.task_name,
        task_type=spec.task_type,
        repo_mode=spec.repo_mode,
        domain=spec.domain,
        status="ready",
        source_files=list(spec.source_files),
        target_test_files=list(spec.target_test_files),
        production_files=list(spec.production_files),
        actions=[
            ExistingRepoTestsAction(
                ExistingRepoTestsActionKind.INSPECT_REPO,
                payload={
                    "required_files": [SLUGIFY_SOURCE],
                    "confirmed_files": [
                        str(inspection.source_path.relative_to(repo.resolve()))
                    ],
                    "repo_state_coverage": coverage,
                },
            ),
            ExistingRepoTestsAction(
                ExistingRepoTestsActionKind.INSPECT_ONE_FILE_LIBRARY,
                target=SLUGIFY_SOURCE,
                payload={
                    "module": "slugify",
                    "public_callable": "slugify",
                    "function_names": list(inspection.function_names),
                    "slugify_arg_count": inspection.slugify_arg_count,
                    "source_sha256": inspection.source_sha256,
                    "source_byte_count": inspection.source_byte_count,
                },
            ),
            ExistingRepoTestsAction(
                ExistingRepoTestsActionKind.ADD_EXISTING_REPO_TESTS,
                target=SLUGIFY_TESTS,
                payload={
                    "test_framework": "pytest",
                    "import": {"module": "slugify", "name": "slugify"},
                    "cases": _slugify_case_records(),
                    "write_policy": "create_or_refine_test_file_only",
                    "production_files_must_remain_unchanged": True,
                },
            ),
            ExistingRepoTestsAction(
                ExistingRepoTestsActionKind.VALIDATE,
                payload={"commands": [SLUGIFY_VALIDATION_COMMAND]},
            ),
        ],
        validation=dict(spec.validation),
        blockers=[],
    )


def apply_existing_repo_tests(
    spec_or_plan: ExistingRepoTestsSpec | ExistingRepoTestsPlan,
    repo: Path,
    *,
    validate: bool = True,
) -> ExistingRepoTestsResult:
    """Create or refine a slugify pytest file without editing production files."""

    plan = (
        spec_or_plan
        if isinstance(spec_or_plan, ExistingRepoTestsPlan)
        else plan_existing_repo_tests(spec_or_plan, repo)
    )
    _validate_tests_plan(plan)

    resolved_repo = repo.expanduser().resolve()
    before_hashes = _file_hashes(resolved_repo, plan.production_files)
    tests_path = _repo_path(resolved_repo, SLUGIFY_TESTS)
    tests_before = tests_path.read_text(encoding="utf-8") if tests_path.exists() else None
    tests_after = _merge_slugify_tests(tests_before)

    files_changed: list[str] = []
    if tests_after != tests_before:
        tests_path.parent.mkdir(parents=True, exist_ok=True)
        tests_path.write_text(tests_after, encoding="utf-8")
        files_changed.append(SLUGIFY_TESTS)

    after_hashes = _file_hashes(resolved_repo, plan.production_files)
    production_changed = [
        path
        for path in plan.production_files
        if before_hashes.get(path) != after_hashes.get(path)
    ]
    blockers: list[dict[str, str]] = []
    if production_changed:
        blockers.append(
            {
                "field": "production_files",
                "reason": "production_file_modified",
                "message": "tests-only materialization changed a production file",
            }
        )

    validation = (
        run_existing_repo_tests_validation(resolved_repo)
        if validate and not production_changed
        else {
            "status": "skipped" if not production_changed else "not_run",
            "command": SLUGIFY_VALIDATION_COMMAND,
            "exit_code": None,
            "reason": "production_file_modified" if production_changed else "validation_disabled",
        }
    )
    status = "validated" if validation["status"] == "passed" else "changed"
    if validation["status"] == "failed":
        status = "validation_failed"
    if production_changed:
        status = "blocked"
    if not files_changed and validation["status"] != "failed" and not production_changed:
        status = "already_applied"

    return ExistingRepoTestsResult(
        schema_version=TESTS_RESULT_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        status=status,
        repo_path=str(resolved_repo),
        files_changed=files_changed,
        target_test_files=list(plan.target_test_files),
        production_files=list(plan.production_files),
        production_files_changed=production_changed,
        validation=validation,
        blockers=blockers,
        source_hashes_before=before_hashes,
        source_hashes_after=after_hashes,
    )


def inspect_slugify_one_file_repo(repo: Path) -> SlugifyRepoInspection:
    """Inspect the repo state required for one-file slugify test authoring."""

    resolved_repo = repo.expanduser().resolve()
    if not resolved_repo.exists():
        raise _blocker_error(
            f"repo does not exist: {resolved_repo}",
            field="repo_state",
            reason="missing_repo_state",
        )
    if not resolved_repo.is_dir():
        raise _blocker_error(
            f"repo is not a directory: {resolved_repo}",
            field="repo_state",
            reason="missing_repo_state",
        )

    source_path = resolved_repo / SLUGIFY_SOURCE
    if not source_path.exists():
        raise _blocker_error(
            "missing one-file slugify library: expected slugify.py",
            field="repo_state",
            reason="missing_repo_state",
        )
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    source_tree = _parse_python(source_text, source_path)
    functions = [node for node in source_tree.body if isinstance(node, ast.FunctionDef)]
    function_names = [node.name for node in functions]
    slugify = next((node for node in functions if node.name == "slugify"), None)
    if slugify is None:
        raise _blocker_error(
            "missing top-level slugify function in slugify.py",
            field="local_knowledge",
            reason="missing_public_api",
        )
    arg_count = len(slugify.args.posonlyargs) + len(slugify.args.args)
    if arg_count != 1:
        raise _blocker_error(
            "unsupported slugify signature: expected one text argument",
            field="local_knowledge",
            reason="unsupported_public_api",
        )

    return SlugifyRepoInspection(
        source_path=source_path,
        tests_path=resolved_repo / SLUGIFY_TESTS,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        source_byte_count=len(source_bytes),
        function_names=function_names,
        slugify_arg_count=arg_count,
    )


def run_existing_repo_tests_validation(repo: Path) -> dict[str, object]:
    """Run the targeted pytest command for the generated tests-only change."""

    command = shlex.split(SLUGIFY_VALIDATION_COMMAND)
    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": SLUGIFY_VALIDATION_COMMAND,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def append_existing_repo_tests_attempt(
    path: Path,
    *,
    raw_prompt: str,
    request_spec: RequestSpec,
    spec: ExistingRepoTestsSpec,
    plan: ExistingRepoTestsPlan,
    result: ExistingRepoTestsResult,
    source: str = "j3 tests-only change",
) -> Path:
    """Append one existing-repo tests-only prompt/spec/action/outcome JSONL row."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    row = existing_repo_tests_attempt_row(
        raw_prompt=raw_prompt,
        request_spec=request_spec,
        spec=spec,
        plan=plan,
        result=result,
        source=source,
    )
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def existing_repo_tests_attempt_row(
    *,
    raw_prompt: str,
    request_spec: RequestSpec,
    spec: ExistingRepoTestsSpec,
    plan: ExistingRepoTestsPlan,
    result: ExistingRepoTestsResult,
    source: str = "j3 tests-only change",
) -> dict[str, object]:
    """Return a structured outcome row for an existing-repo tests-only change."""

    validation = result.validation
    failure_observation = None
    if result.production_files_changed:
        failure_observation = {
            "kind": "production_files_modified",
            "production_files_changed": list(result.production_files_changed),
        }
    elif result.status == "validation_failed":
        failure_observation = {
            "kind": "validation_failed",
            "command": validation.get("command"),
            "exit_code": validation.get("exit_code"),
            "stdout": validation.get("stdout", ""),
            "stderr": validation.get("stderr", ""),
        }
    elif result.blockers:
        failure_observation = {
            "kind": "blocked",
            "blockers": [dict(blocker) for blocker in result.blockers],
        }

    plan_record = plan.to_record()
    return {
        "schema_version": TESTS_ATTEMPT_SCHEMA_VERSION,
        "record_kind": TESTS_ATTEMPT_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "source": source,
            "request_schema_version": request_spec.schema_version,
            "tests_spec_schema_version": spec.schema_version,
            "tests_plan_schema_version": plan.schema_version,
            "tests_result_schema_version": result.schema_version,
        },
        "raw_prompt": raw_prompt,
        "normalized_request_spec": request_spec.to_record(),
        "existing_repo_tests_spec": spec.to_record(),
        "existing_repo_tests_plan": plan_record,
        "existing_repo_actions": list(plan_record["actions"]),  # type: ignore[index]
        "tests_result": result.to_record(),
        "changed_files": list(result.files_changed),
        "target_test_files": list(result.target_test_files),
        "production_files": list(result.production_files),
        "production_files_changed": list(result.production_files_changed),
        "validation": _json_copy(validation),
        "passed": failure_observation is None,
        "failure_observation": failure_observation,
        "repo_path": result.repo_path,
    }


def blocker_from_error(error: ExistingRepoTestsError) -> dict[str, str]:
    """Return a JSON-compatible blocker from a tests-only planning error."""

    return dict(error.blocker)


def _validate_request_spec(spec: RequestSpec) -> None:
    if spec.schema_version != "request-spec-v1":
        raise ExistingRepoTestsError("unsupported request spec schema")
    if spec.task_type != "add_tests":
        raise ExistingRepoTestsError("existing-repo tests require task_type=add_tests")
    if spec.repo_mode != "existing_repo":
        raise ExistingRepoTestsError("existing-repo tests require repo_mode=existing_repo")
    if spec.language != "python":
        raise ExistingRepoTestsError("existing-repo tests only support python")
    if spec.domain != "text_slugify":
        raise ExistingRepoTestsError("existing-repo tests only support text_slugify")
    if spec.features != SLUGIFY_FEATURES:
        raise ExistingRepoTestsError("slugify tests require slugify_ascii_lowercase")
    if spec.artifacts != [SLUGIFY_SOURCE, SLUGIFY_TESTS]:
        raise ExistingRepoTestsError("slugify tests require slugify.py and test target")


def _validate_tests_spec(spec: ExistingRepoTestsSpec) -> None:
    if spec.schema_version != TESTS_SPEC_SCHEMA_VERSION:
        raise ExistingRepoTestsError("unsupported existing-repo tests spec schema")
    if spec.task_type != "add_tests":
        raise ExistingRepoTestsError("existing-repo tests require task_type=add_tests")
    if spec.repo_mode != "existing_repo":
        raise ExistingRepoTestsError("existing-repo tests require repo_mode=existing_repo")
    if spec.domain != "text_slugify":
        raise ExistingRepoTestsError("existing-repo tests only support text_slugify")
    if spec.source_files != [SLUGIFY_SOURCE]:
        raise ExistingRepoTestsError("slugify tests require source_files=['slugify.py']")
    if spec.target_test_files != [SLUGIFY_TESTS]:
        raise ExistingRepoTestsError("slugify tests require tests/test_slugify.py")
    if spec.production_files != [SLUGIFY_SOURCE]:
        raise ExistingRepoTestsError("slugify tests require production_files=['slugify.py']")
    if spec.features != SLUGIFY_FEATURES:
        raise ExistingRepoTestsError("slugify tests require slugify_ascii_lowercase")


def _validate_tests_plan(plan: ExistingRepoTestsPlan) -> None:
    if plan.schema_version != TESTS_PLAN_SCHEMA_VERSION:
        raise ExistingRepoTestsError("unsupported existing-repo tests plan schema")
    if plan.status != "ready":
        raise ExistingRepoTestsError(f"tests-only plan is not ready: {plan.status}")
    expected = [
        ExistingRepoTestsActionKind.INSPECT_REPO,
        ExistingRepoTestsActionKind.INSPECT_ONE_FILE_LIBRARY,
        ExistingRepoTestsActionKind.ADD_EXISTING_REPO_TESTS,
        ExistingRepoTestsActionKind.VALIDATE,
    ]
    actual = [action.kind for action in plan.actions]
    if actual != expected:
        raise ExistingRepoTestsError(f"unexpected tests-only action plan: {actual}")
    if plan.production_files != [SLUGIFY_SOURCE]:
        raise ExistingRepoTestsError("tests-only plan must protect slugify.py")
    if plan.target_test_files != [SLUGIFY_TESTS]:
        raise ExistingRepoTestsError("tests-only plan must target tests/test_slugify.py")


def _merge_slugify_tests(existing_text: str | None) -> str:
    new_text = _render_slugify_tests()
    if existing_text is None or not existing_text.strip():
        return new_text
    if "def test_slugify_cases" in existing_text and "def test_slugify_empty_text" in existing_text:
        return existing_text
    return existing_text.rstrip() + "\n\n\n" + _render_slugify_tests_append_block()


def _render_slugify_tests() -> str:
    cases_literal = _format_case_literal(_slugify_case_records())
    return (
        "from __future__ import annotations\n"
        "\n"
        "from slugify import slugify\n"
        "\n"
        "\n"
        f"SLUGIFY_CASES = {cases_literal}"
        "\n"
        "\n"
        "def test_slugify_cases() -> None:\n"
        "    for case in SLUGIFY_CASES:\n"
        '        assert slugify(case["input"]) == case["expected"]\n'
        "\n"
        "\n"
        "def test_slugify_empty_text() -> None:\n"
        '    assert slugify("...") == ""\n'
    )


def _render_slugify_tests_append_block() -> str:
    cases_literal = _format_case_literal(_slugify_case_records())
    return (
        "from slugify import slugify\n"
        "\n"
        "\n"
        f"SLUGIFY_CASES = {cases_literal}"
        "\n"
        "\n"
        "def test_slugify_cases() -> None:\n"
        "    for case in SLUGIFY_CASES:\n"
        '        assert slugify(case["input"]) == case["expected"]\n'
        "\n"
        "\n"
        "def test_slugify_empty_text() -> None:\n"
        '    assert slugify("...") == ""\n'
    )


def _slugify_case_records() -> list[dict[str, str]]:
    return [
        {"input": "Hello, World!", "expected": "hello-world"},
        {"input": "  Already--slugged  ", "expected": "already-slugged"},
        {"input": "Release 2026: May 18", "expected": "release-2026-may-18"},
    ]


def _format_case_literal(cases: list[dict[str, str]]) -> str:
    lines = ["["]
    for case in cases:
        lines.append("    {")
        for key in sorted(case):
            lines.append(f"        {key!r}: {case[key]!r},")
        lines.append("    },")
    lines.append("]\n")
    return "\n".join(lines)


def _parse_python(text: str, path: Path) -> ast.Module:
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError as error:
        raise _blocker_error(
            f"invalid Python in {path.name}: {error}",
            field="repo_state",
            reason="invalid_python_source",
        ) from error


def _file_hashes(repo: Path, relative_paths: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_path in relative_paths:
        path = _repo_path(repo, relative_path)
        hashes[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _repo_path(repo: Path, relative_path: str) -> Path:
    pure_path = PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ExistingRepoTestsError("target path must stay inside the repository")
    return repo / Path(*pure_path.parts)


def _blocker_error(
    message: str,
    *,
    field: str,
    reason: str,
) -> ExistingRepoTestsError:
    return ExistingRepoTestsError(
        message,
        blocker={
            "field": field,
            "reason": reason,
            "message": message,
        },
    )


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))
