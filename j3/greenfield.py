"""Structured greenfield planning for bounded GreenShot-7 repo creation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from j3.request_spec import (
    CALCULATOR_FEATURES,
    KV_PARSER_ARTIFACTS,
    SLUGIFY_ARTIFACTS,
    RequestSpec,
)


PLAN_SCHEMA_VERSION = "greenfield-plan-v1"
CALCULATOR_SOURCE = "calculator.py"
CALCULATOR_TESTS = "tests/test_calculator_cli.py"
BUILD_SCHEMA_VERSION = "greenfield-build-v1"


class GreenfieldActionKind(str, Enum):
    """Supported structured actions for deterministic greenfield creation."""

    CREATE_FILE = "create_file"
    ADD_IMPORT = "add_import"
    ADD_FUNCTION_DEF = "add_function_def"
    ADD_OPERATOR_DISPATCH = "add_operator_dispatch"
    ADD_CLI_ENTRYPOINT = "add_cli_entrypoint"
    CREATE_TEST_FILE = "create_test_file"
    ADD_CLI_BEHAVIOR_TESTS = "add_cli_behavior_tests"
    ADD_LIBRARY_BEHAVIOR_TESTS = "add_library_behavior_tests"
    ADD_PARSER_BEHAVIOR_TESTS = "add_parser_behavior_tests"
    ASK_CLARIFICATION = "ask_clarification"


@dataclass(frozen=True, slots=True)
class GreenfieldAction:
    """One add-only greenfield action before file materialization."""

    kind: GreenfieldActionKind
    target: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.target is None:
            return
        if PurePosixPath(self.target).is_absolute():
            raise ValueError("target must be relative to the repository root")

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible action record."""

        return {
            "kind": self.kind.value,
            "target": self.target,
            "payload": _json_copy(self.payload),
        }


@dataclass(frozen=True, slots=True)
class GreenfieldPlan:
    """A structured, JSON-compatible plan for a greenfield repo."""

    schema_version: str
    request_schema_version: str
    task_name: str
    domain: str
    language: str
    repo_mode: str
    status: str
    actions: list[GreenfieldAction] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible plan record."""

        return {
            "schema_version": self.schema_version,
            "request_schema_version": self.request_schema_version,
            "task_name": self.task_name,
            "domain": self.domain,
            "language": self.language,
            "repo_mode": self.repo_mode,
            "status": self.status,
            "actions": [action.to_record() for action in self.actions],
            "artifacts": list(self.artifacts),
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "blockers": [dict(blocker) for blocker in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Result of materializing a greenfield plan into a repository directory."""

    schema_version: str
    plan_schema_version: str
    task_name: str
    status: str
    out_dir: str
    artifacts: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)

    def to_record(self) -> dict[str, object]:
        """Return a JSON-compatible build result record."""

        return {
            "schema_version": self.schema_version,
            "plan_schema_version": self.plan_schema_version,
            "task_name": self.task_name,
            "status": self.status,
            "out_dir": self.out_dir,
            "artifacts": list(self.artifacts),
            "files_written": list(self.files_written),
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "blockers": [dict(blocker) for blocker in self.blockers],
        }


def plan_calculator_repo(spec: RequestSpec) -> GreenfieldPlan:
    """Convert a non-blocking calculator request spec into add-only actions."""

    if spec.clarifications_needed:
        return _blocked_plan(spec)

    _validate_calculator_spec(spec)

    operator_dispatch = _operator_dispatch_payload(spec)
    behavior_tests = _behavior_tests_payload(spec)

    actions = [
        GreenfieldAction(
            kind=GreenfieldActionKind.CREATE_FILE,
            target=CALCULATOR_SOURCE,
            payload={
                "artifact_role": "calculator_cli_module",
                "mode": "create",
            },
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_IMPORT,
            target=CALCULATOR_SOURCE,
            payload={"module": "argparse"},
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_FUNCTION_DEF,
            target=CALCULATOR_SOURCE,
            payload={
                "name": "calculate",
                "params": [
                    {"name": "left", "type": "float"},
                    {"name": "operator", "type": "str"},
                    {"name": "right", "type": "float"},
                ],
                "returns": "float",
                "raises": ["ValueError"],
            },
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_OPERATOR_DISPATCH,
            target=CALCULATOR_SOURCE,
            payload=operator_dispatch,
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_CLI_ENTRYPOINT,
            target=CALCULATOR_SOURCE,
            payload={
                "parser": "argparse",
                "arguments": [
                    {"name": "left", "type": "float"},
                    {"name": "operator", "type": "str"},
                    {"name": "right", "type": "float"},
                ],
                "calls": "calculate",
                "prints": "result",
                "handles_value_error": "parser.error(str(error))",
            },
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.CREATE_TEST_FILE,
            target=CALCULATOR_TESTS,
            payload={
                "artifact_role": "calculator_cli_tests",
                "mode": "create",
            },
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_CLI_BEHAVIOR_TESTS,
            target=CALCULATOR_TESTS,
            payload=behavior_tests,
        ),
    ]

    return GreenfieldPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        request_schema_version=spec.schema_version,
        task_name=spec.task_name,
        domain=spec.domain,
        language=spec.language,
        repo_mode=spec.repo_mode,
        status="ready",
        actions=actions,
        artifacts=[CALCULATOR_SOURCE, CALCULATOR_TESTS],
        validation=dict(spec.validation),
        blockers=[],
    )


def plan_greenfield_repo(spec: RequestSpec) -> GreenfieldPlan:
    """Convert a bounded GreenShot-7 request spec into structured actions."""

    if spec.clarifications_needed:
        return _blocked_plan(spec)
    if spec.domain == "calculator":
        return plan_calculator_repo(spec)
    if spec.domain == "text_slugify":
        return plan_slugify_repo(spec)
    if spec.domain == "key_value_parser":
        return plan_key_value_parser_repo(spec)
    return _blocked_plan(
        spec,
        blockers=[
            {
                "field": "domain",
                "question": (
                    "No bounded greenfield builder exists for this request domain."
                ),
                "reason": "greenfield_builder_support",
            }
        ],
    )


def plan_slugify_repo(spec: RequestSpec) -> GreenfieldPlan:
    """Convert a slugify library request spec into add-only actions."""

    _validate_slugify_spec(spec)
    actions = [
        GreenfieldAction(
            kind=GreenfieldActionKind.CREATE_FILE,
            target="slugify.py",
            payload={"artifact_role": "slugify_library_module", "mode": "create"},
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_IMPORT,
            target="slugify.py",
            payload={"module": "re"},
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_FUNCTION_DEF,
            target="slugify.py",
            payload={
                "name": "slugify",
                "params": [{"name": "text", "type": "str"}],
                "returns": "str",
            },
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.CREATE_TEST_FILE,
            target="tests/test_slugify.py",
            payload={"artifact_role": "slugify_library_tests", "mode": "create"},
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_LIBRARY_BEHAVIOR_TESTS,
            target="tests/test_slugify.py",
            payload={
                "test_framework": "pytest",
                "import": {"module": "slugify", "name": "slugify"},
                "cases": [
                    {"input": "Hello, World!", "expected": "hello-world"},
                    {"input": "  Already--slugged  ", "expected": "already-slugged"},
                    {"input": "Release 2026: May 18", "expected": "release-2026-may-18"},
                ],
            },
        ),
    ]
    return GreenfieldPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        request_schema_version=spec.schema_version,
        task_name=spec.task_name,
        domain=spec.domain,
        language=spec.language,
        repo_mode=spec.repo_mode,
        status="ready",
        actions=actions,
        artifacts=list(SLUGIFY_ARTIFACTS),
        validation=dict(spec.validation),
        blockers=[],
    )


def plan_key_value_parser_repo(spec: RequestSpec) -> GreenfieldPlan:
    """Convert a key/value parser request spec into add-only actions."""

    _validate_key_value_parser_spec(spec)
    actions = [
        GreenfieldAction(
            kind=GreenfieldActionKind.CREATE_FILE,
            target="kv_parser.py",
            payload={"artifact_role": "key_value_parser_module", "mode": "create"},
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_FUNCTION_DEF,
            target="kv_parser.py",
            payload={
                "name": "parse_key_value_lines",
                "params": [{"name": "text", "type": "str"}],
                "returns": "dict[str, str]",
                "raises": ["ValueError"],
            },
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.CREATE_TEST_FILE,
            target="tests/test_kv_parser.py",
            payload={"artifact_role": "key_value_parser_tests", "mode": "create"},
        ),
        GreenfieldAction(
            kind=GreenfieldActionKind.ADD_PARSER_BEHAVIOR_TESTS,
            target="tests/test_kv_parser.py",
            payload={
                "test_framework": "pytest",
                "import": {
                    "module": "kv_parser",
                    "name": "parse_key_value_lines",
                },
                "valid_cases": [
                    {
                        "input": "host=localhost\nport=5432\n",
                        "expected": {"host": "localhost", "port": "5432"},
                    },
                    {
                        "input": "# ignored\n\nname = ada\nmode= test\n",
                        "expected": {"name": "ada", "mode": "test"},
                    },
                ],
                "error_cases": ["missing_equals", "=missing_key"],
            },
        ),
    ]
    return GreenfieldPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        request_schema_version=spec.schema_version,
        task_name=spec.task_name,
        domain=spec.domain,
        language=spec.language,
        repo_mode=spec.repo_mode,
        status="ready",
        actions=actions,
        artifacts=list(KV_PARSER_ARTIFACTS),
        validation=dict(spec.validation),
        blockers=[],
    )


def build_calculator_repo(
    spec_or_plan: RequestSpec | GreenfieldPlan,
    out_dir: Path,
) -> BuildResult:
    """Plan if needed, then materialize a deterministic calculator repo."""

    plan = (
        spec_or_plan
        if isinstance(spec_or_plan, GreenfieldPlan)
        else plan_calculator_repo(spec_or_plan)
    )
    return materialize_calculator_repo(plan, out_dir)


def build_greenfield_repo(
    spec_or_plan: RequestSpec | GreenfieldPlan,
    out_dir: Path,
) -> BuildResult:
    """Plan if needed, then materialize a bounded GreenShot-7 repo."""

    plan = (
        spec_or_plan
        if isinstance(spec_or_plan, GreenfieldPlan)
        else plan_greenfield_repo(spec_or_plan)
    )
    if plan.domain == "calculator" or plan.status == "blocked":
        return materialize_calculator_repo(plan, out_dir)
    if plan.domain == "text_slugify":
        return materialize_slugify_repo(plan, out_dir)
    if plan.domain == "key_value_parser":
        return materialize_key_value_parser_repo(plan, out_dir)
    return BuildResult(
        schema_version=BUILD_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        task_name=plan.task_name,
        status="blocked",
        out_dir=str(out_dir),
        artifacts=[],
        files_written=[],
        validation=dict(plan.validation),
        blockers=[dict(blocker) for blocker in plan.blockers],
    )


def materialize_calculator_repo(plan: GreenfieldPlan, out_dir: Path) -> BuildResult:
    """Write calculator source and tests from a greenfield-plan-v1 action list."""

    if plan.schema_version != PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported greenfield plan schema")

    if plan.status == "blocked":
        return BuildResult(
            schema_version=BUILD_SCHEMA_VERSION,
            plan_schema_version=plan.schema_version,
            task_name=plan.task_name,
            status="blocked",
            out_dir=str(out_dir),
            artifacts=[],
            files_written=[],
            validation=dict(plan.validation),
            blockers=[dict(blocker) for blocker in plan.blockers],
        )

    _validate_materializable_plan(plan)

    source_text = _render_calculator_source(plan)
    tests_text = _render_calculator_tests(plan)
    writes = {
        CALCULATOR_SOURCE: source_text,
        CALCULATOR_TESTS: tests_text,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, text in writes.items():
        target = _repo_path(out_dir, relative_path)
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    return BuildResult(
        schema_version=BUILD_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        task_name=plan.task_name,
        status="built",
        out_dir=str(out_dir),
        artifacts=list(plan.artifacts),
        files_written=list(writes),
        validation=dict(plan.validation),
        blockers=[],
    )


def materialize_slugify_repo(plan: GreenfieldPlan, out_dir: Path) -> BuildResult:
    """Write slugify source and tests from a greenfield-plan-v1 action list."""

    if plan.schema_version != PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported greenfield plan schema")
    if plan.status == "blocked":
        return _blocked_build_result(plan, out_dir)
    _validate_library_materializable_plan(
        plan,
        domain="text_slugify",
        artifacts=SLUGIFY_ARTIFACTS,
        expected_actions=[
            GreenfieldActionKind.CREATE_FILE,
            GreenfieldActionKind.ADD_IMPORT,
            GreenfieldActionKind.ADD_FUNCTION_DEF,
            GreenfieldActionKind.CREATE_TEST_FILE,
            GreenfieldActionKind.ADD_LIBRARY_BEHAVIOR_TESTS,
        ],
    )
    return _write_materialized_repo(
        plan,
        out_dir,
        {
            "slugify.py": _render_slugify_source(plan),
            "tests/test_slugify.py": _render_slugify_tests(plan),
        },
    )


def materialize_key_value_parser_repo(
    plan: GreenfieldPlan,
    out_dir: Path,
) -> BuildResult:
    """Write key/value parser source and tests from a greenfield-plan-v1 plan."""

    if plan.schema_version != PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported greenfield plan schema")
    if plan.status == "blocked":
        return _blocked_build_result(plan, out_dir)
    _validate_library_materializable_plan(
        plan,
        domain="key_value_parser",
        artifacts=KV_PARSER_ARTIFACTS,
        expected_actions=[
            GreenfieldActionKind.CREATE_FILE,
            GreenfieldActionKind.ADD_FUNCTION_DEF,
            GreenfieldActionKind.CREATE_TEST_FILE,
            GreenfieldActionKind.ADD_PARSER_BEHAVIOR_TESTS,
        ],
    )
    return _write_materialized_repo(
        plan,
        out_dir,
        {
            "kv_parser.py": _render_key_value_parser_source(plan),
            "tests/test_kv_parser.py": _render_key_value_parser_tests(plan),
        },
    )


def _blocked_plan(
    spec: RequestSpec,
    blockers: list[dict[str, str]] | None = None,
) -> GreenfieldPlan:
    resolved_blockers = (
        [dict(blocker) for blocker in blockers]
        if blockers is not None
        else [dict(clarification) for clarification in spec.clarifications_needed]
    )
    return GreenfieldPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        request_schema_version=spec.schema_version,
        task_name=spec.task_name,
        domain=spec.domain,
        language=spec.language,
        repo_mode=spec.repo_mode,
        status="blocked",
        actions=[
            GreenfieldAction(
                kind=GreenfieldActionKind.ASK_CLARIFICATION,
                payload={
                    "reason": "request_spec_has_blocking_clarifications",
                    "clarifications_needed": resolved_blockers,
                },
            )
        ],
        artifacts=[],
        validation=dict(spec.validation),
        blockers=resolved_blockers,
    )


def _blocked_build_result(plan: GreenfieldPlan, out_dir: Path) -> BuildResult:
    return BuildResult(
        schema_version=BUILD_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        task_name=plan.task_name,
        status="blocked",
        out_dir=str(out_dir),
        artifacts=[],
        files_written=[],
        validation=dict(plan.validation),
        blockers=[dict(blocker) for blocker in plan.blockers],
    )


def _write_materialized_repo(
    plan: GreenfieldPlan,
    out_dir: Path,
    writes: dict[str, str],
) -> BuildResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, text in writes.items():
        target = _repo_path(out_dir, relative_path)
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    return BuildResult(
        schema_version=BUILD_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        task_name=plan.task_name,
        status="built",
        out_dir=str(out_dir),
        artifacts=list(plan.artifacts),
        files_written=list(writes),
        validation=dict(plan.validation),
        blockers=[],
    )


def _validate_calculator_spec(spec: RequestSpec) -> None:
    if spec.schema_version != "request-spec-v1":
        raise ValueError("unsupported request spec schema")
    if spec.task_type != "create_app":
        raise ValueError("greenfield planning requires task_type=create_app")
    if spec.language != "python":
        raise ValueError("calculator greenfield planning only supports python")
    if spec.repo_mode != "new_repo":
        raise ValueError("calculator greenfield planning only supports new_repo")
    if spec.domain != "calculator":
        raise ValueError("calculator greenfield planning only supports calculator specs")
    if not any(
        interface.get("kind") == "cli" and interface.get("style") == "argparse"
        for interface in spec.interfaces
    ):
        raise ValueError("calculator specs must include an argparse cli interface")
    if not spec.features:
        raise ValueError("calculator specs must include at least one feature")

    supported = set(CALCULATOR_FEATURES)
    unknown_features = [feature for feature in spec.features if feature not in supported]
    if unknown_features:
        raise ValueError(f"unsupported calculator features: {unknown_features}")

    missing_aliases = [
        feature for feature in spec.features if feature not in spec.operation_aliases
    ]
    if missing_aliases:
        raise ValueError(f"missing operation aliases for features: {missing_aliases}")


def _validate_slugify_spec(spec: RequestSpec) -> None:
    _validate_library_spec(
        spec,
        domain="text_slugify",
        artifacts=SLUGIFY_ARTIFACTS,
        features=["slugify_ascii_lowercase"],
    )


def _validate_key_value_parser_spec(spec: RequestSpec) -> None:
    _validate_library_spec(
        spec,
        domain="key_value_parser",
        artifacts=KV_PARSER_ARTIFACTS,
        features=["parse_key_value_lines"],
    )


def _validate_library_spec(
    spec: RequestSpec,
    *,
    domain: str,
    artifacts: list[str],
    features: list[str],
) -> None:
    if spec.schema_version != "request-spec-v1":
        raise ValueError("unsupported request spec schema")
    if spec.task_type != "create_library":
        raise ValueError("library greenfield planning requires task_type=create_library")
    if spec.language != "python":
        raise ValueError("library greenfield planning only supports python")
    if spec.repo_mode != "new_repo":
        raise ValueError("library greenfield planning only supports new_repo")
    if spec.domain != domain:
        raise ValueError(f"library greenfield planning only supports {domain} specs")
    if spec.artifacts != artifacts:
        raise ValueError(f"{domain} specs must include expected artifacts")
    if spec.features != features:
        raise ValueError(f"{domain} specs must include expected features")


def _validate_materializable_plan(plan: GreenfieldPlan) -> None:
    if plan.status != "ready":
        raise ValueError(f"greenfield plan is not ready to build: {plan.status}")
    if plan.domain != "calculator":
        raise ValueError("calculator materialization only supports calculator plans")
    if plan.language != "python":
        raise ValueError("calculator materialization only supports python plans")
    if plan.repo_mode != "new_repo":
        raise ValueError("calculator materialization only supports new_repo plans")
    if plan.artifacts != [CALCULATOR_SOURCE, CALCULATOR_TESTS]:
        raise ValueError("calculator materialization requires calculator source and tests")

    expected_actions = [
        GreenfieldActionKind.CREATE_FILE,
        GreenfieldActionKind.ADD_IMPORT,
        GreenfieldActionKind.ADD_FUNCTION_DEF,
        GreenfieldActionKind.ADD_OPERATOR_DISPATCH,
        GreenfieldActionKind.ADD_CLI_ENTRYPOINT,
        GreenfieldActionKind.CREATE_TEST_FILE,
        GreenfieldActionKind.ADD_CLI_BEHAVIOR_TESTS,
    ]
    actual_actions = [action.kind for action in plan.actions]
    if actual_actions != expected_actions:
        raise ValueError(f"unexpected calculator action sequence: {actual_actions}")

    for action in plan.actions:
        if action.kind in {
            GreenfieldActionKind.CREATE_FILE,
            GreenfieldActionKind.ADD_IMPORT,
            GreenfieldActionKind.ADD_FUNCTION_DEF,
            GreenfieldActionKind.ADD_OPERATOR_DISPATCH,
            GreenfieldActionKind.ADD_CLI_ENTRYPOINT,
        } and action.target != CALCULATOR_SOURCE:
            raise ValueError(f"unexpected calculator source action target: {action.target}")
        if action.kind in {
            GreenfieldActionKind.CREATE_TEST_FILE,
            GreenfieldActionKind.ADD_CLI_BEHAVIOR_TESTS,
        } and action.target != CALCULATOR_TESTS:
            raise ValueError(f"unexpected calculator test action target: {action.target}")


def _validate_library_materializable_plan(
    plan: GreenfieldPlan,
    *,
    domain: str,
    artifacts: list[str],
    expected_actions: list[GreenfieldActionKind],
) -> None:
    if plan.status != "ready":
        raise ValueError(f"greenfield plan is not ready to build: {plan.status}")
    if plan.domain != domain:
        raise ValueError(f"materialization only supports {domain} plans")
    if plan.language != "python":
        raise ValueError("materialization only supports python plans")
    if plan.repo_mode != "new_repo":
        raise ValueError("materialization only supports new_repo plans")
    if plan.artifacts != artifacts:
        raise ValueError(f"{domain} materialization requires expected artifacts")
    actual_actions = [action.kind for action in plan.actions]
    if actual_actions != expected_actions:
        raise ValueError(f"unexpected {domain} action sequence: {actual_actions}")


def _operator_dispatch_payload(spec: RequestSpec) -> dict[str, object]:
    return {
        "function": "calculate",
        "operations": [
            {
                "name": feature,
                "aliases": list(spec.operation_aliases[feature]),
                "implementation": _operation_implementation(feature),
            }
            for feature in spec.features
        ],
        "unknown_operator": {
            "raises": "ValueError",
            "message": "Unknown operator: {operator}",
        },
    }


def _operation_implementation(feature: str) -> dict[str, object]:
    if feature == "add":
        return {"expression": "left + right"}
    if feature == "subtract":
        return {"expression": "left - right"}
    if feature == "multiply":
        return {"expression": "left * right"}
    if feature == "divide":
        return {
            "guard": {
                "condition": "right == 0",
                "raises": "ValueError",
                "message": "Cannot divide by zero",
            },
            "expression": "left / right",
        }
    raise ValueError(f"unsupported calculator feature: {feature}")


def _behavior_tests_payload(spec: RequestSpec) -> dict[str, object]:
    error_cases = [
        {
            "name": "unknown_operator_exits_nonzero",
            "argv": ["2", "power", "3"],
            "exit_code": "nonzero",
            "stderr_contains": "Unknown operator",
        }
    ]
    if "divide" in spec.features:
        error_cases.append(
            {
                "name": "divide_by_zero_exits_nonzero",
                "argv": ["8", "/", "0"],
                "exit_code": "nonzero",
                "stderr_contains": "Cannot divide by zero",
            }
        )

    return {
        "test_framework": "pytest",
        "execution": "subprocess",
        "command": ["python", "calculator.py"],
        "passing_cases": [
            _passing_case(feature, spec.operation_aliases[feature])
            for feature in spec.features
        ],
        "error_cases": error_cases,
    }


def _passing_case(feature: str, aliases: list[str]) -> dict[str, object]:
    examples = {
        "add": {
            "argv": ["2", "+", "3"],
            "stdout": "5",
        },
        "subtract": {
            "argv": ["5", "-", "2"],
            "stdout": "3",
        },
        "multiply": {
            "argv": ["4", "multiply", "3"],
            "stdout": "12",
        },
        "divide": {
            "argv": ["8", "/", "2"],
            "stdout": "4",
        },
    }
    if feature not in examples:
        raise ValueError(f"unsupported calculator feature: {feature}")
    return {
        "operation": feature,
        "aliases": list(aliases),
        **examples[feature],
    }


def _json_copy(value: Any) -> object:
    if isinstance(value, dict):
        return {str(key): _json_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_copy(item) for item in value]
    return value


def _render_calculator_source(plan: GreenfieldPlan) -> str:
    dispatch = _required_action(plan, GreenfieldActionKind.ADD_OPERATOR_DISPATCH).payload
    cli = _required_action(plan, GreenfieldActionKind.ADD_CLI_ENTRYPOINT).payload
    if cli.get("parser") != "argparse":
        raise ValueError("calculator source rendering requires argparse cli action")

    operations = _operation_records(dispatch)
    aliases_literal = _format_aliases_literal(operations)
    branches = "\n".join(_render_operation_branch(operation) for operation in operations)
    return (
        '"""Dependency-free CLI calculator generated from a GreenShot-7 plan."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "import argparse\n"
        "\n"
        "\n"
        f"OPERATION_ALIASES = {aliases_literal}\n"
        "\n"
        "\n"
        "def calculate(left: float, operator: str, right: float) -> float:\n"
        '    """Return the result for a supported binary calculator operation."""\n'
        "\n"
        f"{branches}\n"
        '    raise ValueError(f"Unknown operator: {operator}")\n'
        "\n"
        "\n"
        "def format_result(value: float) -> str:\n"
        '    """Format integer-valued floats without a trailing .0."""\n'
        "\n"
        "    if value.is_integer():\n"
        "        return str(int(value))\n"
        "    return str(value)\n"
        "\n"
        "\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        '    parser = argparse.ArgumentParser(description="Run a basic calculator.")\n'
        '    parser.add_argument("left", type=float)\n'
        '    parser.add_argument("operator")\n'
        '    parser.add_argument("right", type=float)\n'
        "    args = parser.parse_args(argv)\n"
        "\n"
        "    try:\n"
        "        result = calculate(args.left, args.operator, args.right)\n"
        "    except ValueError as error:\n"
        "        parser.error(str(error))\n"
        "\n"
        "    print(format_result(result))\n"
        "    return 0\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )


def _render_slugify_source(plan: GreenfieldPlan) -> str:
    function_action = _required_action(plan, GreenfieldActionKind.ADD_FUNCTION_DEF)
    if function_action.payload.get("name") != "slugify":
        raise ValueError("slugify source rendering requires slugify function")
    return (
        '"""Small text slugification helpers generated from a GreenShot-7 plan."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "import re\n"
        "\n"
        "\n"
        "def slugify(text: str) -> str:\n"
        '    """Return a lowercase, hyphen-separated slug for text."""\n'
        "\n"
        r'    parts = re.findall(r"[a-z0-9]+", text.lower())' + "\n"
        '    return "-".join(parts)\n'
    )


def _render_key_value_parser_source(plan: GreenfieldPlan) -> str:
    function_action = _required_action(plan, GreenfieldActionKind.ADD_FUNCTION_DEF)
    if function_action.payload.get("name") != "parse_key_value_lines":
        raise ValueError("parser source rendering requires parse_key_value_lines")
    return (
        '"""Key/value parsing helpers generated from a GreenShot-7 plan."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def parse_key_value_lines(text: str) -> dict[str, str]:\n"
        '    """Parse key=value lines, ignoring blanks and full-line comments."""\n'
        "\n"
        "    values: dict[str, str] = {}\n"
        "    for line_number, raw_line in enumerate(text.splitlines(), start=1):\n"
        "        line = raw_line.strip()\n"
        "        if not line or line.startswith(\"#\"):\n"
        "            continue\n"
        "        if \"=\" not in line:\n"
        "            raise ValueError(f\"Line {line_number} is missing '='\")\n"
        "        key, value = line.split(\"=\", 1)\n"
        "        key = key.strip()\n"
        "        if not key:\n"
        "            raise ValueError(f\"Line {line_number} has an empty key\")\n"
        "        values[key] = value.strip()\n"
        "    return values\n"
    )


def _render_calculator_tests(plan: GreenfieldPlan) -> str:
    behavior = _required_action(plan, GreenfieldActionKind.ADD_CLI_BEHAVIOR_TESTS).payload
    passing_cases = _case_records(behavior, "passing_cases")
    error_cases = _case_records(behavior, "error_cases")

    passing_literal = _format_case_literal(passing_cases)
    error_literal = _format_case_literal(error_cases)
    return (
        "from __future__ import annotations\n"
        "\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        'CALCULATOR = Path(__file__).resolve().parents[1] / "calculator.py"\n'
        f"PASSING_CASES = {passing_literal}\n"
        f"ERROR_CASES = {error_literal}\n"
        "\n"
        "\n"
        "def run_calculator(argv: list[str]) -> subprocess.CompletedProcess[str]:\n"
        "    return subprocess.run(\n"
        "        [sys.executable, str(CALCULATOR), *argv],\n"
        "        text=True,\n"
        "        capture_output=True,\n"
        "        check=False,\n"
        "    )\n"
        "\n"
        "\n"
        "def test_cli_passing_cases() -> None:\n"
        "    for case in PASSING_CASES:\n"
        '        result = run_calculator(case["argv"])\n'
        "        assert result.returncode == 0, result.stderr\n"
        '        assert result.stdout.strip() == case["stdout"]\n'
        "\n"
        "\n"
        "def test_cli_error_cases() -> None:\n"
        "    for case in ERROR_CASES:\n"
        '        result = run_calculator(case["argv"])\n'
        "        assert result.returncode != 0\n"
        '        assert case["stderr_contains"] in result.stderr\n'
    )


def _render_slugify_tests(plan: GreenfieldPlan) -> str:
    behavior = _required_action(plan, GreenfieldActionKind.ADD_LIBRARY_BEHAVIOR_TESTS)
    cases = _dict_case_records(behavior.payload, "cases")
    cases_literal = _format_case_literal(cases)
    return (
        "from __future__ import annotations\n"
        "\n"
        "from slugify import slugify\n"
        "\n"
        "\n"
        f"CASES = {cases_literal}"
        "\n"
        "\n"
        "def test_slugify_cases() -> None:\n"
        "    for case in CASES:\n"
        '        assert slugify(case["input"]) == case["expected"]\n'
        "\n"
        "\n"
        "def test_slugify_empty_text() -> None:\n"
        '    assert slugify("...") == ""\n'
    )


def _render_key_value_parser_tests(plan: GreenfieldPlan) -> str:
    behavior = _required_action(plan, GreenfieldActionKind.ADD_PARSER_BEHAVIOR_TESTS)
    valid_cases = _dict_case_records(behavior.payload, "valid_cases")
    error_cases = behavior.payload.get("error_cases")
    if not isinstance(error_cases, list) or not all(
        isinstance(case, str) for case in error_cases
    ):
        raise ValueError("parser tests require string error_cases")
    valid_literal = _format_case_literal(valid_cases)
    error_literal = _format_literal(error_cases)
    return (
        "from __future__ import annotations\n"
        "\n"
        "import pytest\n"
        "\n"
        "from kv_parser import parse_key_value_lines\n"
        "\n"
        "\n"
        f"VALID_CASES = {valid_literal}"
        f"ERROR_CASES = {error_literal}\n"
        "\n"
        "\n"
        "def test_parse_key_value_lines_valid_cases() -> None:\n"
        "    for case in VALID_CASES:\n"
        '        assert parse_key_value_lines(case["input"]) == case["expected"]\n'
        "\n"
        "\n"
        "def test_parse_key_value_lines_rejects_invalid_lines() -> None:\n"
        "    for text in ERROR_CASES:\n"
        "        with pytest.raises(ValueError):\n"
        "            parse_key_value_lines(text)\n"
    )


def _required_action(
    plan: GreenfieldPlan,
    kind: GreenfieldActionKind,
) -> GreenfieldAction:
    for action in plan.actions:
        if action.kind == kind:
            return action
    raise ValueError(f"missing required action: {kind.value}")


def _operation_records(dispatch: dict[str, Any]) -> list[dict[str, Any]]:
    if dispatch.get("function") != "calculate":
        raise ValueError("operator dispatch must target calculate")
    operations = dispatch.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("operator dispatch requires at least one operation")

    records: list[dict[str, Any]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("operator records must be objects")
        name = operation.get("name")
        aliases = operation.get("aliases")
        implementation = operation.get("implementation")
        if name not in CALCULATOR_FEATURES:
            raise ValueError(f"unsupported calculator operation: {name}")
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) for alias in aliases
        ):
            raise ValueError(f"operation aliases must be strings: {name}")
        if not isinstance(implementation, dict):
            raise ValueError(f"operation implementation must be an object: {name}")
        records.append(
            {
                "name": name,
                "aliases": aliases,
                "implementation": implementation,
            }
        )
    return records


def _case_records(behavior: dict[str, Any], key: str) -> list[dict[str, Any]]:
    cases = behavior.get(key)
    if not isinstance(cases, list):
        raise ValueError(f"behavior tests require {key}")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"{key} must contain objects")
        argv = case.get("argv")
        if not isinstance(argv, list) or not all(isinstance(arg, str) for arg in argv):
            raise ValueError(f"{key} case argv must be a list of strings")
    return cases


def _dict_case_records(behavior: dict[str, Any], key: str) -> list[dict[str, Any]]:
    cases = behavior.get(key)
    if not isinstance(cases, list):
        raise ValueError(f"behavior tests require {key}")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"{key} must contain objects")
    return cases


def _render_operation_branch(operation: dict[str, Any]) -> str:
    name = str(operation["name"])
    implementation = operation["implementation"]
    expression = implementation.get("expression")
    if expression != _operation_implementation(name).get("expression"):
        raise ValueError(f"unexpected expression for operation: {name}")

    lines = [f'    if operator in OPERATION_ALIASES["{name}"]:']
    guard = implementation.get("guard")
    if guard is not None:
        expected_guard = _operation_implementation(name).get("guard")
        if guard != expected_guard:
            raise ValueError(f"unexpected guard for operation: {name}")
        lines.extend(
            [
                "        if right == 0:",
                '            raise ValueError("Cannot divide by zero")',
            ]
        )
    lines.append(f"        return {expression}")
    return "\n".join(lines)


def _format_aliases_literal(operations: list[dict[str, Any]]) -> str:
    lines = ["{"]
    for operation in operations:
        aliases = ", ".join(repr(alias) for alias in operation["aliases"])
        lines.append(f'    "{operation["name"]}": ({aliases}),')
    lines.append("}")
    return "\n".join(lines)


def _format_case_literal(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "[]\n"

    lines = ["["]
    for case in cases:
        lines.append("    {")
        for key in sorted(case):
            value = case[key]
            lines.append(f"        {key!r}: {_format_literal(value)},")
        lines.append("    },")
    lines.append("]\n")
    return "\n".join(lines)


def _format_literal(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_format_literal(item) for item in value) + "]"
    return repr(value)


def _repo_path(out_dir: Path, relative_path: str) -> Path:
    pure_path = PurePosixPath(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ValueError(f"unsafe generated path: {relative_path}")
    return out_dir.joinpath(*pure_path.parts)
