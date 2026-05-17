"""Narrow existing-repo calculator changes for the GreenShot-7 slice."""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

from prompt_intents import PromptIntentPrediction, PromptIntentTarget


CHANGE_SPEC_SCHEMA_VERSION = "existing-repo-change-spec-v1"
CHANGE_PLAN_SCHEMA_VERSION = "existing-repo-change-plan-v1"
CHANGE_RESULT_SCHEMA_VERSION = "existing-repo-change-result-v1"
CHANGE_ATTEMPT_SCHEMA_VERSION = "existing-repo-change-attempt-v1"
CHANGE_ATTEMPT_KIND = "greenshot_7_existing_repo_change_attempt"
CALCULATOR_SOURCE = "calculator.py"
CALCULATOR_TESTS = "tests/test_calculator_cli.py"
POWER_ALIASES = ["power", "pow", "^", "**"]
VALIDATION_COMMAND = "python -m pytest tests/test_calculator_cli.py -q"
KNOWN_CALCULATOR_FEATURES = {"add", "subtract", "multiply", "divide", "power"}


class ExistingRepoChangeError(ValueError):
    """Raised when a prompt or repository is outside the supported change slice."""


class ExistingRepoActionKind(str, Enum):
    """Supported structured existing-repo actions for calculator power support."""

    INSPECT_REPO = "inspect_repo"
    PARSE_EXISTING_CALCULATOR = "parse_existing_calculator"
    ADD_OPERATOR_ALIASES = "add_operator_aliases"
    ADD_OPERATOR_DISPATCH = "add_operator_dispatch"
    ADD_CLI_BEHAVIOR_TESTS = "add_cli_behavior_tests"
    VALIDATE = "validate"


@dataclass(frozen=True, slots=True)
class ExistingRepoChangeSpec:
    """A JSON-compatible contract for one bounded existing-repo change."""

    schema_version: str
    task_type: str
    repo_mode: str
    domain: str
    prompt: str
    target_files: list[str] = field(default_factory=list)
    features_to_add: list[str] = field(default_factory=list)
    operation_aliases: dict[str, list[str]] = field(default_factory=dict)
    validation: dict[str, object] = field(default_factory=dict)
    intent_source: str | None = None
    intent_record_id: str | None = None

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "schema_version": self.schema_version,
            "task_type": self.task_type,
            "repo_mode": self.repo_mode,
            "domain": self.domain,
            "prompt": self.prompt,
            "target_files": list(self.target_files),
            "features_to_add": list(self.features_to_add),
            "operation_aliases": {
                feature: list(aliases)
                for feature, aliases in self.operation_aliases.items()
            },
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
        }
        if self.intent_source:
            record["intent_source"] = self.intent_source
        if self.intent_record_id:
            record["intent_record_id"] = self.intent_record_id
        return record


@dataclass(frozen=True, slots=True)
class ExistingRepoAction:
    """One structured action in the existing-repo change plan."""

    kind: ExistingRepoActionKind
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
class ExistingRepoChangePlan:
    """Structured action plan for a bounded existing-repo edit."""

    schema_version: str
    spec_schema_version: str
    task_type: str
    repo_mode: str
    domain: str
    status: str
    target_files: list[str] = field(default_factory=list)
    actions: list[ExistingRepoAction] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "spec_schema_version": self.spec_schema_version,
            "task_type": self.task_type,
            "repo_mode": self.repo_mode,
            "domain": self.domain,
            "status": self.status,
            "target_files": list(self.target_files),
            "actions": [action.to_record() for action in self.actions],
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
            "blockers": [dict(blocker) for blocker in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class ExistingRepoChangeResult:
    """Result of applying a bounded existing-repo change."""

    schema_version: str
    plan_schema_version: str
    status: str
    repo_path: str
    files_changed: list[str] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "plan_schema_version": self.plan_schema_version,
            "status": self.status,
            "repo_path": self.repo_path,
            "files_changed": list(self.files_changed),
            "validation": _json_copy(self.validation),
            "blockers": [dict(blocker) for blocker in self.blockers],
        }


@dataclass(frozen=True, slots=True)
class CalculatorRepoInspection:
    """Minimal facts proving a repo has the generated calculator shape."""

    source_path: Path
    tests_path: Path
    operation_aliases: dict[str, list[str]]
    has_power_dispatch: bool


def parse_existing_repo_change_to_spec(
    prompt: str,
    *,
    intent: PromptIntentPrediction | PromptIntentTarget | None = None,
) -> ExistingRepoChangeSpec:
    """Parse a supported existing-repo prompt into a change spec."""

    target = _intent_target(intent)
    if not _is_supported_power_change(target):
        raise ExistingRepoChangeError(
            "unsupported change prompt: this slice only supports labeled "
            "existing-repo calculator power/exponent requests"
        )

    return ExistingRepoChangeSpec(
        schema_version=CHANGE_SPEC_SCHEMA_VERSION,
        task_type="modify_app",
        repo_mode="existing_repo",
        domain="calculator",
        prompt=prompt,
        target_files=[CALCULATOR_SOURCE, CALCULATOR_TESTS],
        features_to_add=["power"],
        operation_aliases={"power": list(POWER_ALIASES)},
        validation={
            "commands": [VALIDATION_COMMAND],
            "hidden_cases": True,
        },
        intent_source=getattr(intent, "source", None),
        intent_record_id=getattr(intent, "record_id", None),
    )


def plan_existing_repo_change(
    spec: ExistingRepoChangeSpec,
    repo: Path,
) -> ExistingRepoChangePlan:
    """Build a structured plan after confirming the repo shape."""

    _validate_change_spec(spec)
    inspection = inspect_generated_calculator_repo(repo)
    return ExistingRepoChangePlan(
        schema_version=CHANGE_PLAN_SCHEMA_VERSION,
        spec_schema_version=spec.schema_version,
        task_type=spec.task_type,
        repo_mode=spec.repo_mode,
        domain=spec.domain,
        status="ready",
        target_files=list(spec.target_files),
        actions=[
            ExistingRepoAction(
                ExistingRepoActionKind.INSPECT_REPO,
                payload={
                    "required_files": [CALCULATOR_SOURCE, CALCULATOR_TESTS],
                    "confirmed_files": [
                        str(inspection.source_path.relative_to(repo)),
                        str(inspection.tests_path.relative_to(repo)),
                    ],
                },
            ),
            ExistingRepoAction(
                ExistingRepoActionKind.PARSE_EXISTING_CALCULATOR,
                target=CALCULATOR_SOURCE,
                payload={
                    "operation_aliases": dict(inspection.operation_aliases),
                    "has_power_dispatch": inspection.has_power_dispatch,
                },
            ),
            ExistingRepoAction(
                ExistingRepoActionKind.ADD_OPERATOR_ALIASES,
                target=CALCULATOR_SOURCE,
                payload={"feature": "power", "aliases": list(POWER_ALIASES)},
            ),
            ExistingRepoAction(
                ExistingRepoActionKind.ADD_OPERATOR_DISPATCH,
                target=CALCULATOR_SOURCE,
                payload={"feature": "power", "expression": "left ** right"},
            ),
            ExistingRepoAction(
                ExistingRepoActionKind.ADD_CLI_BEHAVIOR_TESTS,
                target=CALCULATOR_TESTS,
                payload={"feature": "power", "cases": _power_passing_cases()},
            ),
            ExistingRepoAction(
                ExistingRepoActionKind.VALIDATE,
                payload={"commands": [VALIDATION_COMMAND]},
            ),
        ],
        validation=dict(spec.validation),
        blockers=[],
    )


def apply_existing_repo_change(
    spec_or_plan: ExistingRepoChangeSpec | ExistingRepoChangePlan,
    repo: Path,
    *,
    validate: bool = True,
) -> ExistingRepoChangeResult:
    """Apply the supported calculator power change to a generated repo."""

    plan = (
        spec_or_plan
        if isinstance(spec_or_plan, ExistingRepoChangePlan)
        else plan_existing_repo_change(spec_or_plan, repo)
    )
    _validate_change_plan(plan)

    resolved_repo = repo.expanduser().resolve()
    source_path = resolved_repo / CALCULATOR_SOURCE
    tests_path = resolved_repo / CALCULATOR_TESTS
    source_before = source_path.read_text(encoding="utf-8")
    tests_before = tests_path.read_text(encoding="utf-8")
    source_after = _add_power_to_source(source_before)
    tests_after = _add_power_to_tests(tests_before)

    files_changed: list[str] = []
    if source_after != source_before:
        source_path.write_text(source_after, encoding="utf-8")
        files_changed.append(CALCULATOR_SOURCE)
    if tests_after != tests_before:
        tests_path.write_text(tests_after, encoding="utf-8")
        files_changed.append(CALCULATOR_TESTS)

    validation = (
        run_existing_repo_validation(resolved_repo)
        if validate
        else {
            "status": "skipped",
            "command": VALIDATION_COMMAND,
            "exit_code": None,
        }
    )
    status = "validated" if validation["status"] == "passed" else "changed"
    if validation["status"] == "skipped":
        status = "changed"
    if validation["status"] == "failed":
        status = "validation_failed"
    if not files_changed and validation["status"] != "failed":
        status = "already_applied"

    return ExistingRepoChangeResult(
        schema_version=CHANGE_RESULT_SCHEMA_VERSION,
        plan_schema_version=plan.schema_version,
        status=status,
        repo_path=str(resolved_repo),
        files_changed=files_changed,
        validation=validation,
        blockers=[],
    )


def inspect_generated_calculator_repo(repo: Path) -> CalculatorRepoInspection:
    """Reject repos that do not look like j3's generated calculator."""

    resolved_repo = repo.expanduser().resolve()
    if not resolved_repo.exists():
        raise ExistingRepoChangeError(f"repo does not exist: {resolved_repo}")
    if not resolved_repo.is_dir():
        raise ExistingRepoChangeError(f"repo is not a directory: {resolved_repo}")

    source_path = resolved_repo / CALCULATOR_SOURCE
    tests_path = resolved_repo / CALCULATOR_TESTS
    if not source_path.exists() or not tests_path.exists():
        raise ExistingRepoChangeError(
            "unsupported repo shape: expected generated calculator.py and "
            "tests/test_calculator_cli.py"
        )

    source_text = source_path.read_text(encoding="utf-8")
    tests_text = tests_path.read_text(encoding="utf-8")
    source_tree = _parse_python(source_text, source_path)
    tests_tree = _parse_python(tests_text, tests_path)

    docstring = ast.get_docstring(source_tree)
    if docstring != "Dependency-free CLI calculator generated from a GreenShot-7 plan.":
        raise ExistingRepoChangeError(
            "unsupported repo shape: calculator.py is not the known generated calculator"
        )

    aliases = _operation_aliases(source_tree)
    if not aliases:
        raise ExistingRepoChangeError(
            "unsupported repo shape: missing OPERATION_ALIASES in calculator.py"
        )
    unknown_features = sorted(set(aliases) - KNOWN_CALCULATOR_FEATURES)
    if unknown_features:
        raise ExistingRepoChangeError(
            f"unsupported repo shape: unknown calculator operations {unknown_features}"
        )

    calculate = _function_def(source_tree, "calculate")
    if calculate is None:
        raise ExistingRepoChangeError(
            "unsupported repo shape: missing calculate function in calculator.py"
        )
    for feature in aliases:
        if feature != "power" and not _has_operation_branch(calculate, feature):
            raise ExistingRepoChangeError(
                f"unsupported repo shape: missing dispatch for operation {feature}"
            )

    if _assignment(tests_tree, "PASSING_CASES") is None:
        raise ExistingRepoChangeError(
            "unsupported repo shape: missing PASSING_CASES in generated tests"
        )
    if _assignment(tests_tree, "ERROR_CASES") is None:
        raise ExistingRepoChangeError(
            "unsupported repo shape: missing ERROR_CASES in generated tests"
        )

    return CalculatorRepoInspection(
        source_path=source_path,
        tests_path=tests_path,
        operation_aliases=aliases,
        has_power_dispatch=_has_operation_branch(calculate, "power"),
    )


def run_existing_repo_validation(repo: Path) -> dict[str, object]:
    command = ["python", "-m", "pytest", "tests/test_calculator_cli.py", "-q"]
    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def append_existing_repo_change_attempt(
    path: Path,
    *,
    raw_prompt: str,
    spec: ExistingRepoChangeSpec,
    plan: ExistingRepoChangePlan,
    result: ExistingRepoChangeResult,
    source: str = "j3 change",
) -> Path:
    """Append one existing-repo prompt/spec/action/outcome JSONL row."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    row = existing_repo_change_attempt_row(
        raw_prompt=raw_prompt,
        spec=spec,
        plan=plan,
        result=result,
        source=source,
    )
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def existing_repo_change_attempt_row(
    *,
    raw_prompt: str,
    spec: ExistingRepoChangeSpec,
    plan: ExistingRepoChangePlan,
    result: ExistingRepoChangeResult,
    source: str = "j3 change",
) -> dict[str, object]:
    validation = result.validation
    failure_observation = None
    if result.status == "validation_failed":
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
        "schema_version": CHANGE_ATTEMPT_SCHEMA_VERSION,
        "record_kind": CHANGE_ATTEMPT_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "source": source,
            "change_spec_schema_version": spec.schema_version,
            "change_plan_schema_version": plan.schema_version,
            "change_result_schema_version": result.schema_version,
        },
        "raw_prompt": raw_prompt,
        "existing_repo_change_spec": spec.to_record(),
        "existing_repo_change_plan": plan_record,
        "existing_repo_actions": list(plan_record["actions"]),  # type: ignore[index]
        "change_result": result.to_record(),
        "validation": _json_copy(validation),
        "passed": failure_observation is None,
        "failure_observation": failure_observation,
        "repo_path": result.repo_path,
    }


def _intent_target(
    intent: PromptIntentPrediction | PromptIntentTarget | None,
) -> PromptIntentTarget | None:
    if isinstance(intent, PromptIntentPrediction):
        return intent.target
    if isinstance(intent, PromptIntentTarget):
        return intent
    return None


def _is_supported_power_change(target: PromptIntentTarget | None) -> bool:
    if target is None:
        return False
    return (
        target.expected_action == "emit_existing_repo_change_spec"
        and target.repo_mode == "existing_repo"
        and target.domain == "calculator"
        and "power" in target.features
    )


def _validate_change_spec(spec: ExistingRepoChangeSpec) -> None:
    if spec.schema_version != CHANGE_SPEC_SCHEMA_VERSION:
        raise ExistingRepoChangeError("unsupported existing-repo change spec schema")
    if spec.task_type != "modify_app":
        raise ExistingRepoChangeError("existing-repo changes require task_type=modify_app")
    if spec.repo_mode != "existing_repo":
        raise ExistingRepoChangeError("existing-repo changes require repo_mode=existing_repo")
    if spec.domain != "calculator":
        raise ExistingRepoChangeError("only calculator changes are supported")
    if spec.target_files != [CALCULATOR_SOURCE, CALCULATOR_TESTS]:
        raise ExistingRepoChangeError("calculator power change requires known target files")
    if spec.features_to_add != ["power"]:
        raise ExistingRepoChangeError("only the power calculator feature is supported")
    if spec.operation_aliases.get("power") != POWER_ALIASES:
        raise ExistingRepoChangeError("power aliases must be power, pow, ^, **")


def _validate_change_plan(plan: ExistingRepoChangePlan) -> None:
    if plan.schema_version != CHANGE_PLAN_SCHEMA_VERSION:
        raise ExistingRepoChangeError("unsupported existing-repo change plan schema")
    if plan.status != "ready":
        raise ExistingRepoChangeError(f"change plan is not ready: {plan.status}")
    kinds = [action.kind for action in plan.actions]
    expected = [
        ExistingRepoActionKind.INSPECT_REPO,
        ExistingRepoActionKind.PARSE_EXISTING_CALCULATOR,
        ExistingRepoActionKind.ADD_OPERATOR_ALIASES,
        ExistingRepoActionKind.ADD_OPERATOR_DISPATCH,
        ExistingRepoActionKind.ADD_CLI_BEHAVIOR_TESTS,
        ExistingRepoActionKind.VALIDATE,
    ]
    if kinds != expected:
        raise ExistingRepoChangeError(f"unexpected existing-repo action plan: {kinds}")


def _add_power_to_source(text: str) -> str:
    tree = _parse_python_text(text, filename=CALCULATOR_SOURCE)
    assignment = _assignment(tree, "OPERATION_ALIASES")
    if assignment is None:
        raise ExistingRepoChangeError("missing OPERATION_ALIASES in calculator.py")

    aliases = _operation_aliases(tree)
    if aliases.get("power") != POWER_ALIASES:
        aliases["power"] = list(POWER_ALIASES)
        text = _replace_node_lines(text, assignment, _render_aliases_assignment(aliases))
        tree = _parse_python_text(text, filename=CALCULATOR_SOURCE)

    calculate = _function_def(tree, "calculate")
    if calculate is None:
        raise ExistingRepoChangeError("missing calculate function in calculator.py")
    if not _has_operation_branch(calculate, "power"):
        unknown_raise = _unknown_operator_raise(calculate)
        if unknown_raise is None:
            raise ExistingRepoChangeError(
                "missing generated unknown-operator raise in calculator.py"
            )
        lines = text.splitlines(keepends=True)
        insertion_index = unknown_raise.lineno - 1
        lines[insertion_index:insertion_index] = [
            '    if operator in OPERATION_ALIASES["power"]:\n',
            "        return left ** right\n",
        ]
        text = "".join(lines)

    return text


def _add_power_to_tests(text: str) -> str:
    tree = _parse_python_text(text, filename=CALCULATOR_TESTS)
    passing_assignment = _assignment(tree, "PASSING_CASES")
    error_assignment = _assignment(tree, "ERROR_CASES")
    if passing_assignment is None or error_assignment is None:
        raise ExistingRepoChangeError("generated calculator tests are missing case tables")

    passing_cases = _literal_assignment_list(passing_assignment, "PASSING_CASES")
    existing_argv = {
        tuple(case.get("argv", []))
        for case in passing_cases
        if isinstance(case, dict)
    }
    for case in _power_passing_cases():
        if tuple(case["argv"]) not in existing_argv:
            passing_cases.append(case)

    error_cases = _literal_assignment_list(error_assignment, "ERROR_CASES")
    for case in error_cases:
        if not isinstance(case, dict):
            continue
        argv = case.get("argv")
        if (
            isinstance(argv, list)
            and len(argv) == 3
            and argv[1] in POWER_ALIASES
            and "Unknown operator" in str(case.get("stderr_contains", ""))
        ):
            case["argv"] = ["2", "mod", "3"]

    text = _replace_node_lines(
        text,
        passing_assignment,
        "PASSING_CASES = " + _format_case_literal(passing_cases),
    )
    tree = _parse_python_text(text, filename=CALCULATOR_TESTS)
    error_assignment = _assignment(tree, "ERROR_CASES")
    if error_assignment is None:
        raise ExistingRepoChangeError("generated calculator tests lost ERROR_CASES")
    return _replace_node_lines(
        text,
        error_assignment,
        "ERROR_CASES = " + _format_case_literal(error_cases),
    )


def _parse_python(text: str, path: Path) -> ast.Module:
    return _parse_python_text(text, filename=str(path))


def _parse_python_text(text: str, *, filename: str) -> ast.Module:
    try:
        return ast.parse(text, filename=filename)
    except SyntaxError as error:
        raise ExistingRepoChangeError(f"invalid Python in {filename}: {error}") from error


def _assignment(tree: ast.Module, name: str) -> ast.Assign | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node
    return None


def _function_def(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _operation_aliases(tree: ast.Module) -> dict[str, list[str]]:
    assignment = _assignment(tree, "OPERATION_ALIASES")
    if assignment is None:
        return {}
    try:
        value = ast.literal_eval(assignment.value)
    except (ValueError, SyntaxError) as error:
        raise ExistingRepoChangeError("OPERATION_ALIASES must be a literal dict") from error
    if not isinstance(value, dict):
        raise ExistingRepoChangeError("OPERATION_ALIASES must be a dict")

    aliases: dict[str, list[str]] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ExistingRepoChangeError("OPERATION_ALIASES keys must be strings")
        if not isinstance(item, (tuple, list)) or not all(
            isinstance(alias, str) for alias in item
        ):
            raise ExistingRepoChangeError("OPERATION_ALIASES values must be string lists")
        aliases[key] = list(item)
    return aliases


def _literal_assignment_list(assignment: ast.Assign, name: str) -> list[dict[str, object]]:
    try:
        value = ast.literal_eval(assignment.value)
    except (ValueError, SyntaxError) as error:
        raise ExistingRepoChangeError(f"{name} must be a literal list") from error
    if not isinstance(value, list) or not all(isinstance(case, dict) for case in value):
        raise ExistingRepoChangeError(f"{name} must be a list of dict cases")
    return value


def _has_operation_branch(function: ast.FunctionDef, feature: str) -> bool:
    return any(_if_tests_operation(node, feature) for node in function.body)


def _if_tests_operation(node: ast.stmt, feature: str) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "operator"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.In)
        and len(test.comparators) == 1
        and _subscript_alias_key(test.comparators[0]) == feature
    )


def _subscript_alias_key(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Subscript):
        return None
    if not isinstance(node.value, ast.Name) or node.value.id != "OPERATION_ALIASES":
        return None
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
        return node.slice.value
    return None


def _unknown_operator_raise(function: ast.FunctionDef) -> ast.Raise | None:
    for node in function.body:
        if not isinstance(node, ast.Raise):
            continue
        if _raises_value_error_with_unknown_operator(node):
            return node
    return None


def _raises_value_error_with_unknown_operator(node: ast.Raise) -> bool:
    call = node.exc
    if not isinstance(call, ast.Call):
        return False
    if not isinstance(call.func, ast.Name) or call.func.id != "ValueError":
        return False
    if len(call.args) != 1:
        return False
    arg = call.args[0]
    if isinstance(arg, ast.JoinedStr):
        return any(
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and "Unknown operator:" in value.value
            for value in arg.values
        )
    return (
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and "Unknown operator:" in arg.value
    )


def _replace_node_lines(text: str, node: ast.AST, replacement: str) -> str:
    if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
        raise ExistingRepoChangeError("Python AST node is missing line numbers")
    lines = text.splitlines(keepends=True)
    start = node.lineno - 1  # type: ignore[attr-defined]
    end = node.end_lineno  # type: ignore[attr-defined]
    return "".join(lines[:start] + [replacement.rstrip("\n") + "\n"] + lines[end:])


def _render_aliases_assignment(aliases: dict[str, list[str]]) -> str:
    lines = ["OPERATION_ALIASES = {"]
    for feature, feature_aliases in aliases.items():
        aliases_literal = ", ".join(repr(alias) for alias in feature_aliases)
        lines.append(f'    "{feature}": ({aliases_literal}),')
    lines.append("}")
    return "\n".join(lines)


def _power_passing_cases() -> list[dict[str, object]]:
    return [
        {
            "operation": "power",
            "aliases": list(POWER_ALIASES),
            "argv": ["2", "^", "3"],
            "stdout": "8",
        },
        {
            "operation": "power",
            "aliases": list(POWER_ALIASES),
            "argv": ["2", "power", "3"],
            "stdout": "8",
        },
        {
            "operation": "power",
            "aliases": list(POWER_ALIASES),
            "argv": ["2", "**", "3"],
            "stdout": "8",
        },
    ]


def _format_case_literal(cases: list[dict[str, object]]) -> str:
    if not cases:
        return "[]\n"

    lines = ["["]
    for case in cases:
        lines.append("    {")
        for key in sorted(case):
            lines.append(f"        {key!r}: {_format_literal(case[key])},")
        lines.append("    },")
    lines.append("]\n")
    return "\n".join(lines)


def _format_literal(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_format_literal(item) for item in value) + "]"
    return repr(value)


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))
