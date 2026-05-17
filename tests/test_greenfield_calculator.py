from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from j3.greenfield import (
    build_calculator_repo,
    materialize_calculator_repo,
    plan_calculator_repo,
)
from j3.request_spec import parse_request_to_spec


TASKS_PATH = Path("examples/greenshot_7/tasks.json")


def _task(name: str) -> dict[str, object]:
    tasks = json.loads(TASKS_PATH.read_text())
    return next(task for task in tasks if task["name"] == name)


def _spec_from_fixture(name: str):
    task = _task(name)
    return parse_request_to_spec(str(task["prompt"]), task_name=name)


def _action(record: dict[str, object], kind: str) -> dict[str, object]:
    return next(action for action in record["actions"] if action["kind"] == kind)  # type: ignore[index]


def _run_calculator(repo: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "calculator.py"), *argv],
        text=True,
        capture_output=True,
        check=False,
    )


def _run_generated_pytest(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_calculator_cli.py", "-q"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


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


def test_materialize_four_operation_calculator_repo(tmp_path: Path) -> None:
    plan = plan_calculator_repo(_spec_from_fixture("calculator_named_ops"))
    result = materialize_calculator_repo(plan, tmp_path)

    assert result.to_record()["status"] == "built"
    assert result.files_written == ["calculator.py", "tests/test_calculator_cli.py"]
    assert sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    ) == ["calculator.py", "tests/test_calculator_cli.py"]

    generated_pytest = _run_generated_pytest(tmp_path)
    assert (
        generated_pytest.returncode == 0
    ), generated_pytest.stdout + generated_pytest.stderr

    assert _run_calculator(tmp_path, "2", "+", "3").stdout.strip() == "5"
    assert _run_calculator(tmp_path, "2", "add", "3").stdout.strip() == "5"
    assert _run_calculator(tmp_path, "5", "-", "2").stdout.strip() == "3"
    assert _run_calculator(tmp_path, "4", "multiply", "3").stdout.strip() == "12"
    assert _run_calculator(tmp_path, "4", "x", "3").stdout.strip() == "12"
    assert _run_calculator(tmp_path, "8", "/", "2").stdout.strip() == "4"
    assert _run_calculator(tmp_path, "9", "div", "4").stdout.strip() == "2.25"

    unknown_operator = _run_calculator(tmp_path, "2", "power", "3")
    assert unknown_operator.returncode != 0
    assert "Unknown operator" in unknown_operator.stderr

    divide_by_zero = _run_calculator(tmp_path, "8", "/", "0")
    assert divide_by_zero.returncode != 0
    assert "Cannot divide by zero" in divide_by_zero.stderr


def test_materialize_add_only_calculator_repo(tmp_path: Path) -> None:
    result = build_calculator_repo(_spec_from_fixture("calculator_add_only"), tmp_path)

    assert result.status == "built"
    source = (tmp_path / "calculator.py").read_text(encoding="utf-8")
    assert '"add": (' in source
    assert '"subtract": (' not in source
    assert '"multiply": (' not in source
    assert '"divide": (' not in source

    generated_pytest = _run_generated_pytest(tmp_path)
    assert (
        generated_pytest.returncode == 0
    ), generated_pytest.stdout + generated_pytest.stderr

    assert _run_calculator(tmp_path, "2", "+", "3").stdout.strip() == "5"
    assert _run_calculator(tmp_path, "2", "plus", "3").stdout.strip() == "5"

    subtract = _run_calculator(tmp_path, "5", "-", "2")
    assert subtract.returncode != 0
    assert "Unknown operator" in subtract.stderr

    divide = _run_calculator(tmp_path, "8", "/", "2")
    assert divide.returncode != 0
    assert "Unknown operator" in divide.stderr


def test_materialize_reports_blocked_clarification_plan(tmp_path: Path) -> None:
    plan = plan_calculator_repo(_spec_from_fixture("calculator_scientific_unclear"))
    result = materialize_calculator_repo(plan, tmp_path)

    assert result.status == "blocked"
    assert result.files_written == []
    assert result.blockers == [
        {
            "field": "features",
            "question": "Which scientific calculator operations should be supported?",
        }
    ]
    assert not (tmp_path / "calculator.py").exists()
    assert not (tmp_path / "tests").exists()
