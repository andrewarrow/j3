"""Repo-state-aware existing-repo convention support for small libraries."""

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

from j3.repo_state import RepoStateCoverage, encode_repo_state_coverage
from j3.request_spec import RequestSpec


CONVENTION_SPEC_SCHEMA_VERSION = "existing-repo-convention-spec-v1"
CONVENTION_PLAN_SCHEMA_VERSION = "existing-repo-convention-plan-v1"
CONVENTION_RESULT_SCHEMA_VERSION = "existing-repo-convention-result-v1"
CONVENTION_ATTEMPT_SCHEMA_VERSION = "existing-repo-convention-attempt-v1"
CONVENTION_ATTEMPT_KIND = "greenshot_7_existing_repo_convention_attempt"
SLUGIFY_SRC_MODULE = "src/acme_slug/text.py"
SLUGIFY_PACKAGE_INIT = "src/acme_slug/__init__.py"
SLUGIFY_PACKAGE_PATH = "src/acme_slug"
SLUGIFY_PACKAGE_NAME = "acme_slug"
SLUGIFY_CONVENTION_TEST = "tests/test_acme_slug.py"
SLUGIFY_CONVENTION_FEATURES = ["src_package_slugify_export"]
SLUGIFY_CONVENTION_INTERFACES = [
    {"kind": "python_api", "module": "acme_slug", "callable": "slugify"}
]
SLUGIFY_CONVENTION_VALIDATION_COMMAND = "python -m pytest tests/test_acme_slug.py -q"


class ExistingRepoConventionError(ValueError):
    """Raised when a repo falls outside the supported convention slice."""

    def __init__(self, message: str, *, blocker: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.blocker = blocker or {
            "field": "existing_repo_convention",
            "reason": "unsupported_existing_repo_convention_slice",
            "message": message,
        }


class ExistingRepoConventionActionKind(str, Enum):
    """Supported actions for the narrow src-package export convention."""

    INSPECT_REPO = "inspect_repo"
    INSPECT_SRC_PACKAGE_LAYOUT = "inspect_src_package_layout"
    ADD_PACKAGE_EXPORT = "add_package_export"
    VALIDATE = "validate"


@dataclass(frozen=True, slots=True)
class ExistingRepoConventionSpec:
    """A JSON-compatible contract for one small-library convention edit."""

    schema_version: str
    task_name: str
    task_type: str
    repo_mode: str
    domain: str
    prompt: str
    source_files: list[str] = field(default_factory=list)
    source_edit_files: list[str] = field(default_factory=list)
    protected_source_files: list[str] = field(default_factory=list)
    validation_files: list[str] = field(default_factory=list)
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
            "source_edit_files": list(self.source_edit_files),
            "protected_source_files": list(self.protected_source_files),
            "validation_files": list(self.validation_files),
            "interfaces": [dict(interface) for interface in self.interfaces],
            "features": list(self.features),
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "change_policy": _source_edit_scope_record(
                source_edit_files=self.source_edit_files,
                protected_source_files=self.protected_source_files,
            ),
        }


@dataclass(frozen=True, slots=True)
class ExistingRepoConventionAction:
    """One structured action in the src-package convention plan."""

    kind: ExistingRepoConventionActionKind
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
class ExistingRepoConventionPlan:
    """Structured plan for a narrow src-package convention edit."""

    schema_version: str
    spec_schema_version: str
    task_name: str
    task_type: str
    repo_mode: str
    domain: str
    status: str
    source_files: list[str] = field(default_factory=list)
    source_edit_files: list[str] = field(default_factory=list)
    protected_source_files: list[str] = field(default_factory=list)
    validation_files: list[str] = field(default_factory=list)
    actions: list[ExistingRepoConventionAction] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    repo_state_evidence: dict[str, object] = field(default_factory=dict)
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
            "source_edit_files": list(self.source_edit_files),
            "protected_source_files": list(self.protected_source_files),
            "validation_files": list(self.validation_files),
            "actions": [action.to_record() for action in self.actions],
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "repo_state_evidence": _json_copy(self.repo_state_evidence),
            "blockers": [dict(blocker) for blocker in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class ExistingRepoConventionResult:
    """Result of applying a bounded src-package convention edit."""

    schema_version: str
    plan_schema_version: str
    status: str
    repo_path: str
    files_changed: list[str] = field(default_factory=list)
    source_edit_files: list[str] = field(default_factory=list)
    source_files_changed: list[str] = field(default_factory=list)
    protected_source_files: list[str] = field(default_factory=list)
    protected_source_files_changed: list[str] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)
    source_hashes_before: dict[str, str] = field(default_factory=dict)
    source_hashes_after: dict[str, str] = field(default_factory=dict)
    source_edit_scope: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "plan_schema_version": self.plan_schema_version,
            "status": self.status,
            "repo_path": self.repo_path,
            "files_changed": list(self.files_changed),
            "source_edit_files": list(self.source_edit_files),
            "source_files_changed": list(self.source_files_changed),
            "protected_source_files": list(self.protected_source_files),
            "protected_source_files_changed": list(self.protected_source_files_changed),
            "validation": _json_copy(self.validation),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "source_hashes_before": dict(self.source_hashes_before),
            "source_hashes_after": dict(self.source_hashes_after),
            "source_edit_scope": _json_copy(self.source_edit_scope),
        }


@dataclass(frozen=True, slots=True)
class SlugifySrcConventionInspection:
    """Facts proving a repo fits the narrow src-package export convention."""

    package_name: str
    package_path: str
    source_root: str
    module_path: str
    init_path: str
    validation_path: str
    public_callable: str
    function_names: list[str]
    slugify_arg_count: int
    module_sha256: str
    init_sha256: str
    repo_state_evidence: dict[str, object]


def existing_repo_convention_spec_from_request(
    spec: RequestSpec,
) -> ExistingRepoConventionSpec:
    """Convert a supported request-spec-v1 row into a src-convention spec."""

    _validate_request_spec(spec)
    return ExistingRepoConventionSpec(
        schema_version=CONVENTION_SPEC_SCHEMA_VERSION,
        task_name=spec.task_name,
        task_type=spec.task_type,
        repo_mode=spec.repo_mode,
        domain=spec.domain,
        prompt=spec.prompt,
        source_files=[SLUGIFY_SRC_MODULE, SLUGIFY_PACKAGE_INIT],
        source_edit_files=[SLUGIFY_PACKAGE_INIT],
        protected_source_files=[SLUGIFY_SRC_MODULE],
        validation_files=[SLUGIFY_CONVENTION_TEST],
        interfaces=[dict(interface) for interface in SLUGIFY_CONVENTION_INTERFACES],
        features=list(SLUGIFY_CONVENTION_FEATURES),
        validation={
            "commands": [SLUGIFY_CONVENTION_VALIDATION_COMMAND],
            "hidden_cases": True,
        },
    )


def plan_existing_repo_convention(
    spec: ExistingRepoConventionSpec,
    repo: Path,
) -> ExistingRepoConventionPlan:
    """Inspect repo-state coverage and plan the package export edit."""

    _validate_convention_spec(spec)
    inspection = inspect_slugify_src_convention_repo(repo)
    coverage = encode_repo_state_coverage(repo).to_record()
    return ExistingRepoConventionPlan(
        schema_version=CONVENTION_PLAN_SCHEMA_VERSION,
        spec_schema_version=spec.schema_version,
        task_name=spec.task_name,
        task_type=spec.task_type,
        repo_mode=spec.repo_mode,
        domain=spec.domain,
        status="ready",
        source_files=list(spec.source_files),
        source_edit_files=list(spec.source_edit_files),
        protected_source_files=list(spec.protected_source_files),
        validation_files=list(spec.validation_files),
        actions=[
            ExistingRepoConventionAction(
                ExistingRepoConventionActionKind.INSPECT_REPO,
                payload={
                    "required_files": [
                        SLUGIFY_SRC_MODULE,
                        SLUGIFY_PACKAGE_INIT,
                        SLUGIFY_CONVENTION_TEST,
                    ],
                    "confirmed_files": [
                        SLUGIFY_SRC_MODULE,
                        SLUGIFY_PACKAGE_INIT,
                        SLUGIFY_CONVENTION_TEST,
                    ],
                    "repo_state_coverage": coverage,
                },
            ),
            ExistingRepoConventionAction(
                ExistingRepoConventionActionKind.INSPECT_SRC_PACKAGE_LAYOUT,
                target=inspection.package_path,
                payload={
                    "source_root": inspection.source_root,
                    "package_name": inspection.package_name,
                    "package_path": inspection.package_path,
                    "module_path": inspection.module_path,
                    "init_path": inspection.init_path,
                    "validation_path": inspection.validation_path,
                    "public_callable": inspection.public_callable,
                    "function_names": list(inspection.function_names),
                    "slugify_arg_count": inspection.slugify_arg_count,
                    "module_sha256": inspection.module_sha256,
                    "init_sha256": inspection.init_sha256,
                    "repo_state_evidence": _json_copy(inspection.repo_state_evidence),
                },
            ),
            ExistingRepoConventionAction(
                ExistingRepoConventionActionKind.ADD_PACKAGE_EXPORT,
                target=SLUGIFY_PACKAGE_INIT,
                payload={
                    "import": {"module": ".text", "name": "slugify"},
                    "all": ["slugify"],
                    "write_policy": "package_export_file_only",
                    "protected_source_files_must_remain_unchanged": True,
                },
            ),
            ExistingRepoConventionAction(
                ExistingRepoConventionActionKind.VALIDATE,
                payload={"commands": [SLUGIFY_CONVENTION_VALIDATION_COMMAND]},
            ),
        ],
        validation=dict(spec.validation),
        repo_state_evidence=dict(inspection.repo_state_evidence),
        blockers=[],
    )


def apply_existing_repo_convention(
    spec_or_plan: ExistingRepoConventionSpec | ExistingRepoConventionPlan,
    repo: Path,
    *,
    validate: bool = True,
) -> ExistingRepoConventionResult:
    """Expose ``slugify`` from a src-layout package ``__init__.py`` file."""

    plan = (
        spec_or_plan
        if isinstance(spec_or_plan, ExistingRepoConventionPlan)
        else plan_existing_repo_convention(spec_or_plan, repo)
    )
    _validate_convention_plan(plan)

    resolved_repo = repo.expanduser().resolve()
    tracked_sources = plan.source_edit_files + plan.protected_source_files
    before_hashes = _file_hashes(resolved_repo, tracked_sources)
    init_path = _repo_path(resolved_repo, SLUGIFY_PACKAGE_INIT)
    init_before = init_path.read_text(encoding="utf-8")
    init_after = _merge_slugify_package_export(init_before, init_path)

    files_changed: list[str] = []
    if init_after != init_before:
        init_path.write_text(init_after, encoding="utf-8")
        files_changed.append(SLUGIFY_PACKAGE_INIT)

    after_hashes = _file_hashes(resolved_repo, tracked_sources)
    protected_changed = [
        path
        for path in plan.protected_source_files
        if before_hashes.get(path) != after_hashes.get(path)
    ]
    source_files_changed = [
        path
        for path in tracked_sources
        if before_hashes.get(path) != after_hashes.get(path)
    ]
    blockers: list[dict[str, str]] = []
    if protected_changed:
        blockers.append(
            {
                "field": "source_edit_scope",
                "reason": "protected_source_file_modified",
                "message": "convention materialization changed a protected source file",
            }
        )

    validation = (
        run_existing_repo_convention_validation(resolved_repo)
        if validate and not protected_changed
        else {
            "status": "skipped" if not protected_changed else "not_run",
            "command": SLUGIFY_CONVENTION_VALIDATION_COMMAND,
            "exit_code": None,
            "reason": (
                "protected_source_file_modified"
                if protected_changed
                else "validation_disabled"
            ),
        }
    )
    status = "validated" if validation["status"] == "passed" else "changed"
    if validation["status"] == "failed":
        status = "validation_failed"
    if protected_changed:
        status = "blocked"
    if not files_changed and validation["status"] != "failed" and not protected_changed:
        status = "already_applied"

    return ExistingRepoConventionResult(
        schema_version=CONVENTION_RESULT_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        status=status,
        repo_path=str(resolved_repo),
        files_changed=files_changed,
        source_edit_files=list(plan.source_edit_files),
        source_files_changed=source_files_changed,
        protected_source_files=list(plan.protected_source_files),
        protected_source_files_changed=protected_changed,
        validation=validation,
        blockers=blockers,
        source_hashes_before=before_hashes,
        source_hashes_after=after_hashes,
        source_edit_scope=_source_edit_scope_record(
            source_edit_files=plan.source_edit_files,
            protected_source_files=plan.protected_source_files,
        ),
    )


def inspect_slugify_src_convention_repo(repo: Path) -> SlugifySrcConventionInspection:
    """Inspect repo-state coverage required for the src-layout export slice."""

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

    coverage = encode_repo_state_coverage(resolved_repo)
    if coverage.parse_errors:
        raise _blocker_error(
            "repo-state coverage has Python parse errors",
            field="repo_state",
            reason="invalid_repo_state_python",
        )

    evidence = _slugify_src_evidence(coverage)
    source_path = _repo_path(resolved_repo, SLUGIFY_SRC_MODULE)
    init_path = _repo_path(resolved_repo, SLUGIFY_PACKAGE_INIT)
    source_text = source_path.read_text(encoding="utf-8")
    source_bytes = source_text.encode("utf-8")
    init_bytes = init_path.read_bytes()
    source_tree = _parse_python(source_text, source_path)
    functions = [node for node in source_tree.body if isinstance(node, ast.FunctionDef)]
    function_names = [node.name for node in functions]
    slugify = next((node for node in functions if node.name == "slugify"), None)
    if slugify is None:
        raise _blocker_error(
            "missing top-level slugify function in src/acme_slug/text.py",
            field="repo_state",
            reason="missing_src_slugify_function",
        )
    arg_count = len(slugify.args.posonlyargs) + len(slugify.args.args)
    if arg_count != 1:
        raise _blocker_error(
            "unsupported slugify signature: expected one text argument",
            field="source_materialization",
            reason="unsupported_public_api",
        )

    return SlugifySrcConventionInspection(
        package_name=SLUGIFY_PACKAGE_NAME,
        package_path=SLUGIFY_PACKAGE_PATH,
        source_root="src",
        module_path=SLUGIFY_SRC_MODULE,
        init_path=SLUGIFY_PACKAGE_INIT,
        validation_path=SLUGIFY_CONVENTION_TEST,
        public_callable="slugify",
        function_names=function_names,
        slugify_arg_count=arg_count,
        module_sha256=hashlib.sha256(source_bytes).hexdigest(),
        init_sha256=hashlib.sha256(init_bytes).hexdigest(),
        repo_state_evidence=evidence,
    )


def run_existing_repo_convention_validation(repo: Path) -> dict[str, object]:
    """Run the targeted pytest command for the package export convention."""

    command = shlex.split(SLUGIFY_CONVENTION_VALIDATION_COMMAND)
    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": SLUGIFY_CONVENTION_VALIDATION_COMMAND,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def append_existing_repo_convention_attempt(
    path: Path,
    *,
    raw_prompt: str,
    request_spec: RequestSpec,
    spec: ExistingRepoConventionSpec,
    plan: ExistingRepoConventionPlan,
    result: ExistingRepoConventionResult,
    source: str = "j3 convention change",
) -> Path:
    """Append one existing-repo convention prompt/spec/action/outcome JSONL row."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    row = existing_repo_convention_attempt_row(
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


def existing_repo_convention_attempt_row(
    *,
    raw_prompt: str,
    request_spec: RequestSpec,
    spec: ExistingRepoConventionSpec,
    plan: ExistingRepoConventionPlan,
    result: ExistingRepoConventionResult,
    source: str = "j3 convention change",
) -> dict[str, object]:
    """Return a structured outcome row for an existing-repo convention edit."""

    validation = result.validation
    failure_observation = None
    if result.protected_source_files_changed:
        failure_observation = {
            "kind": "protected_source_files_modified",
            "protected_source_files_changed": list(result.protected_source_files_changed),
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
        "schema_version": CONVENTION_ATTEMPT_SCHEMA_VERSION,
        "record_kind": CONVENTION_ATTEMPT_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "source": source,
            "request_schema_version": request_spec.schema_version,
            "convention_spec_schema_version": spec.schema_version,
            "convention_plan_schema_version": plan.schema_version,
            "convention_result_schema_version": result.schema_version,
        },
        "raw_prompt": raw_prompt,
        "normalized_request_spec": request_spec.to_record(),
        "existing_repo_convention_spec": spec.to_record(),
        "existing_repo_convention_plan": plan_record,
        "existing_repo_actions": list(plan_record["actions"]),  # type: ignore[index]
        "convention_result": result.to_record(),
        "changed_files": list(result.files_changed),
        "source_files_changed": list(result.source_files_changed),
        "protected_source_files_changed": list(result.protected_source_files_changed),
        "validation": _json_copy(validation),
        "validation_commands": list(spec.validation.get("commands", [])),
        "repo_state_evidence_used": _json_copy(plan.repo_state_evidence),
        "source_edit_scope": _json_copy(result.source_edit_scope),
        "passed": failure_observation is None,
        "failure_observation": failure_observation,
        "repo_path": result.repo_path,
    }


def blocker_from_error(error: ExistingRepoConventionError) -> dict[str, str]:
    """Return a JSON-compatible blocker from a convention planning error."""

    return dict(error.blocker)


def _slugify_src_evidence(coverage: RepoStateCoverage) -> dict[str, object]:
    files_by_path = {item.path: item for item in coverage.files}
    packages_by_path = {item.path: item for item in coverage.packages}
    required_files = [
        SLUGIFY_SRC_MODULE,
        SLUGIFY_PACKAGE_INIT,
        SLUGIFY_CONVENTION_TEST,
    ]
    missing_files = [path for path in required_files if path not in files_by_path]
    if missing_files:
        field = "validation" if SLUGIFY_CONVENTION_TEST in missing_files else "repo_state"
        reason = (
            "missing_validation_layer"
            if SLUGIFY_CONVENTION_TEST in missing_files
            else "missing_src_layout_package"
        )
        raise _blocker_error(
            "missing required src-layout convention files: " + ", ".join(missing_files),
            field=field,
            reason=reason,
        )
    if SLUGIFY_PACKAGE_PATH not in packages_by_path:
        raise _blocker_error(
            "repo-state coverage did not identify src/acme_slug as a package",
            field="repo_state",
            reason="missing_src_layout_package",
        )

    slugify_functions = [
        item
        for item in coverage.functions
        if item.path == SLUGIFY_SRC_MODULE
        and item.name == "slugify"
        and item.kind == "function"
    ]
    if not slugify_functions:
        raise _blocker_error(
            "repo-state coverage did not find slugify in src/acme_slug/text.py",
            field="repo_state",
            reason="missing_src_slugify_function",
        )

    public_export_imports = [
        item
        for item in coverage.imports
        if item.path == SLUGIFY_CONVENTION_TEST
        and item.module == SLUGIFY_PACKAGE_NAME
        and item.imported == "slugify"
    ]
    if not public_export_imports:
        raise _blocker_error(
            "validation layer does not import slugify from the package public API",
            field="validation",
            reason="missing_validation_layer",
        )

    return {
        "schema_version": "existing-repo-convention-evidence-v1",
        "coverage_schema_version": coverage.schema_version,
        "source_root": "src",
        "package": packages_by_path[SLUGIFY_PACKAGE_PATH].to_record(),
        "module_file": files_by_path[SLUGIFY_SRC_MODULE].to_record(),
        "init_file": files_by_path[SLUGIFY_PACKAGE_INIT].to_record(),
        "validation_file": files_by_path[SLUGIFY_CONVENTION_TEST].to_record(),
        "slugify_functions": [item.to_record() for item in slugify_functions],
        "public_export_validation_imports": [
            item.to_record() for item in public_export_imports
        ],
        "tests": [item.to_record() for item in coverage.tests],
        "configs": list(coverage.configs),
    }


def _validate_request_spec(spec: RequestSpec) -> None:
    if spec.schema_version != "request-spec-v1":
        raise ExistingRepoConventionError("unsupported request spec schema")
    if spec.task_type != "modify_library":
        raise ExistingRepoConventionError(
            "existing-repo convention edits require task_type=modify_library"
        )
    if spec.repo_mode != "existing_repo":
        raise ExistingRepoConventionError(
            "existing-repo convention edits require repo_mode=existing_repo"
        )
    if spec.language != "python":
        raise ExistingRepoConventionError("existing-repo conventions only support python")
    if spec.domain != "text_slugify":
        raise ExistingRepoConventionError(
            "existing-repo conventions only support text_slugify"
        )
    if spec.artifacts != [
        SLUGIFY_SRC_MODULE,
        SLUGIFY_PACKAGE_INIT,
        SLUGIFY_CONVENTION_TEST,
    ]:
        raise ExistingRepoConventionError("slugify convention requires the src fixture")
    if spec.features != SLUGIFY_CONVENTION_FEATURES:
        raise ExistingRepoConventionError(
            "slugify convention requires src_package_slugify_export"
        )


def _validate_convention_spec(spec: ExistingRepoConventionSpec) -> None:
    if spec.schema_version != CONVENTION_SPEC_SCHEMA_VERSION:
        raise ExistingRepoConventionError("unsupported convention spec schema")
    if spec.task_type != "modify_library":
        raise ExistingRepoConventionError(
            "existing-repo convention edits require task_type=modify_library"
        )
    if spec.repo_mode != "existing_repo":
        raise ExistingRepoConventionError(
            "existing-repo convention edits require repo_mode=existing_repo"
        )
    if spec.domain != "text_slugify":
        raise ExistingRepoConventionError(
            "existing-repo conventions only support text_slugify"
        )
    if spec.source_files != [SLUGIFY_SRC_MODULE, SLUGIFY_PACKAGE_INIT]:
        raise ExistingRepoConventionError("slugify convention requires src package files")
    if spec.source_edit_files != [SLUGIFY_PACKAGE_INIT]:
        raise ExistingRepoConventionError("slugify convention may only edit __init__.py")
    if spec.protected_source_files != [SLUGIFY_SRC_MODULE]:
        raise ExistingRepoConventionError("slugify convention must protect text.py")
    if spec.validation_files != [SLUGIFY_CONVENTION_TEST]:
        raise ExistingRepoConventionError("slugify convention requires package export tests")
    if spec.features != SLUGIFY_CONVENTION_FEATURES:
        raise ExistingRepoConventionError(
            "slugify convention requires src_package_slugify_export"
        )


def _validate_convention_plan(plan: ExistingRepoConventionPlan) -> None:
    if plan.schema_version != CONVENTION_PLAN_SCHEMA_VERSION:
        raise ExistingRepoConventionError("unsupported convention plan schema")
    if plan.status != "ready":
        raise ExistingRepoConventionError(f"convention plan is not ready: {plan.status}")
    expected = [
        ExistingRepoConventionActionKind.INSPECT_REPO,
        ExistingRepoConventionActionKind.INSPECT_SRC_PACKAGE_LAYOUT,
        ExistingRepoConventionActionKind.ADD_PACKAGE_EXPORT,
        ExistingRepoConventionActionKind.VALIDATE,
    ]
    actual = [action.kind for action in plan.actions]
    if actual != expected:
        raise ExistingRepoConventionError(f"unexpected convention action plan: {actual}")
    if plan.source_edit_files != [SLUGIFY_PACKAGE_INIT]:
        raise ExistingRepoConventionError("convention plan may only edit __init__.py")
    if plan.protected_source_files != [SLUGIFY_SRC_MODULE]:
        raise ExistingRepoConventionError("convention plan must protect text.py")


def _merge_slugify_package_export(text: str, path: Path) -> str:
    normalized_text = text if text.endswith("\n") or not text else text + "\n"
    tree = _parse_python(normalized_text, path)
    needs_import = not _has_slugify_import(tree)
    needs_all = not _has_slugify_all(tree)
    if not needs_import and not needs_all:
        return text

    lines = normalized_text.splitlines(keepends=True)
    insertion_index = _export_insertion_index(tree)
    block = _render_export_block(needs_import=needs_import, needs_all=needs_all)
    insert_lines: list[str] = []
    if insertion_index > 0 and lines and lines[insertion_index - 1].strip():
        insert_lines.append("\n")
    insert_lines.extend(block)
    if insertion_index < len(lines) and lines[insertion_index].strip():
        insert_lines.append("\n")
    lines[insertion_index:insertion_index] = insert_lines
    merged = "".join(lines)
    _parse_python(merged, path)
    return merged


def _has_slugify_import(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 1 and node.module == "text":
            if any(alias.name == "slugify" for alias in node.names):
                return True
    return False


def _has_slugify_all(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            values = [
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
            return "slugify" in values
    return False


def _export_insertion_index(tree: ast.Module) -> int:
    index = 0
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and _is_string_constant(body[0].value):
        index = body[0].end_lineno or body[0].lineno
    for node in body[1 if index else 0 :]:
        if not (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == "__future__"
        ):
            break
        index = node.end_lineno or node.lineno
    return index


def _render_export_block(*, needs_import: bool, needs_all: bool) -> list[str]:
    lines: list[str] = []
    if needs_import:
        lines.append("from .text import slugify\n")
    if needs_import and needs_all:
        lines.append("\n")
    if needs_all:
        lines.append('__all__ = ["slugify"]\n')
    return lines


def _is_string_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


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
        raise ExistingRepoConventionError("target path must stay inside the repository")
    return repo / Path(*pure_path.parts)


def _source_edit_scope_record(
    *,
    source_edit_files: list[str],
    protected_source_files: list[str],
) -> dict[str, object]:
    return {
        "mode": "package_export_only",
        "allowed_source_files": list(source_edit_files),
        "protected_source_files": list(protected_source_files),
        "max_source_files_changed": 1,
    }


def _blocker_error(
    message: str,
    *,
    field: str,
    reason: str,
) -> ExistingRepoConventionError:
    return ExistingRepoConventionError(
        message,
        blocker={
            "field": field,
            "reason": reason,
            "message": message,
        },
    )


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))
