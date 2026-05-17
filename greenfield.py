"""Structured greenfield planning for the GreenShot-7 calculator slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any

from request_spec import CALCULATOR_FEATURES, RequestSpec


PLAN_SCHEMA_VERSION = "greenfield-plan-v1"
CALCULATOR_SOURCE = "calculator.py"
CALCULATOR_TESTS = "tests/test_calculator_cli.py"


class GreenfieldActionKind(str, Enum):
    """Supported structured actions for deterministic greenfield creation."""

    CREATE_FILE = "create_file"
    ADD_IMPORT = "add_import"
    ADD_FUNCTION_DEF = "add_function_def"
    ADD_OPERATOR_DISPATCH = "add_operator_dispatch"
    ADD_CLI_ENTRYPOINT = "add_cli_entrypoint"
    CREATE_TEST_FILE = "create_test_file"
    ADD_CLI_BEHAVIOR_TESTS = "add_cli_behavior_tests"
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


def plan_calculator_repo(spec: RequestSpec) -> GreenfieldPlan:
    """Convert a non-blocking calculator request spec into add-only actions."""

    if spec.clarifications_needed:
        blockers = [dict(clarification) for clarification in spec.clarifications_needed]
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
                        "clarifications_needed": blockers,
                    },
                )
            ],
            artifacts=[],
            validation=dict(spec.validation),
            blockers=blockers,
        )

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
