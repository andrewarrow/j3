from __future__ import annotations

import json
from pathlib import Path

from greenfield import plan_calculator_repo
from request_spec import parse_request_to_spec


TASKS_PATH = Path("examples/greenshot_7/tasks.json")


def _task(name: str) -> dict[str, object]:
    tasks = json.loads(TASKS_PATH.read_text())
    return next(task for task in tasks if task["name"] == name)


def _spec_from_fixture(name: str):
    task = _task(name)
    return parse_request_to_spec(str(task["prompt"]), task_name=name)


def _action(record: dict[str, object], kind: str) -> dict[str, object]:
    return next(action for action in record["actions"] if action["kind"] == kind)  # type: ignore[index]


def test_plan_calculator_repo_for_four_operation_fixture() -> None:
    spec = _spec_from_fixture("calculator_named_ops")
    plan = plan_calculator_repo(spec)
    record = plan.to_record()

    assert json.loads(json.dumps(record)) == record
    assert record["schema_version"] == "greenfield-plan-v1"
    assert record["request_schema_version"] == "request-spec-v1"
    assert record["status"] == "ready"
    assert record["artifacts"] == ["calculator.py", "tests/test_calculator_cli.py"]
    assert [action["kind"] for action in record["actions"]] == [
        "create_file",
        "add_import",
        "add_function_def",
        "add_operator_dispatch",
        "add_cli_entrypoint",
        "create_test_file",
        "add_cli_behavior_tests",
    ]

    import_action = _action(record, "add_import")
    assert import_action["target"] == "calculator.py"
    assert import_action["payload"] == {"module": "argparse"}

    function_action = _action(record, "add_function_def")
    assert function_action["payload"]["name"] == "calculate"  # type: ignore[index]
    assert function_action["payload"]["params"] == [  # type: ignore[index]
        {"name": "left", "type": "float"},
        {"name": "operator", "type": "str"},
        {"name": "right", "type": "float"},
    ]

    dispatch = _action(record, "add_operator_dispatch")["payload"]
    operations = dispatch["operations"]  # type: ignore[index]
    assert [operation["name"] for operation in operations] == [  # type: ignore[index]
        "add",
        "subtract",
        "multiply",
        "divide",
    ]
    assert operations[0]["aliases"] == ["add", "plus", "+"]  # type: ignore[index]
    assert operations[3]["aliases"] == ["divide", "div", "/"]  # type: ignore[index]
    assert operations[3]["implementation"] == {  # type: ignore[index]
        "guard": {
            "condition": "right == 0",
            "raises": "ValueError",
            "message": "Cannot divide by zero",
        },
        "expression": "left / right",
    }
    assert dispatch["unknown_operator"] == {  # type: ignore[index]
        "raises": "ValueError",
        "message": "Unknown operator: {operator}",
    }

    tests = _action(record, "add_cli_behavior_tests")["payload"]
    assert [case["operation"] for case in tests["passing_cases"]] == [  # type: ignore[index]
        "add",
        "subtract",
        "multiply",
        "divide",
    ]
    assert tests["passing_cases"][0]["argv"] == ["2", "+", "3"]  # type: ignore[index]
    assert tests["passing_cases"][3]["stdout"] == "4"  # type: ignore[index]
    assert [case["name"] for case in tests["error_cases"]] == [  # type: ignore[index]
        "unknown_operator_exits_nonzero",
        "divide_by_zero_exits_nonzero",
    ]


def test_plan_calculator_repo_for_add_only_fixture() -> None:
    spec = _spec_from_fixture("calculator_add_only")
    record = plan_calculator_repo(spec).to_record()

    dispatch = _action(record, "add_operator_dispatch")["payload"]
    operations = dispatch["operations"]  # type: ignore[index]
    assert operations == [  # type: ignore[index]
        {
            "name": "add",
            "aliases": ["add", "plus", "+"],
            "implementation": {"expression": "left + right"},
        }
    ]

    tests = _action(record, "add_cli_behavior_tests")["payload"]
    assert tests["passing_cases"] == [  # type: ignore[index]
        {
            "operation": "add",
            "aliases": ["add", "plus", "+"],
            "argv": ["2", "+", "3"],
            "stdout": "5",
        }
    ]
    assert tests["error_cases"] == [  # type: ignore[index]
        {
            "name": "unknown_operator_exits_nonzero",
            "argv": ["2", "power", "3"],
            "exit_code": "nonzero",
            "stderr_contains": "Unknown operator",
        }
    ]


def test_plan_calculator_repo_reports_blocked_clarification_specs() -> None:
    spec = _spec_from_fixture("math_tool_unclear")
    record = plan_calculator_repo(spec).to_record()

    assert record["status"] == "blocked"
    assert record["artifacts"] == []
    assert record["blockers"] == [
        {
            "field": "domain",
            "question": (
                "Should this be a basic CLI calculator, and which operations "
                "should it support?"
            ),
        }
    ]
    assert [action["kind"] for action in record["actions"]] == ["ask_clarification"]
    assert record["actions"][0]["payload"] == {  # type: ignore[index]
        "reason": "request_spec_has_blocking_clarifications",
        "clarifications_needed": record["blockers"],
    }
