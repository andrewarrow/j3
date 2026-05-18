from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from j3.greenfield import (
    build_calculator_repo,
    build_greenfield_repo,
    materialize_calculator_repo,
    plan_calculator_repo,
    plan_greenfield_repo,
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


def _run_generated_pytest_file(
    repo: Path,
    test_path: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q"],
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
    payload = record["actions"][0]["payload"]  # type: ignore[index]
    assert payload["reason"] == "request_spec_has_blocking_clarifications"  # type: ignore[index]
    assert payload["clarifications_needed"] == record["blockers"]  # type: ignore[index]
    assert payload["clarification_response"] == record["clarification_response"]  # type: ignore[index]
    assert record["clarification_response"] == {
        "schema_version": "clarification-response-v1",
        "status": "needs_clarification",
        "task_name": "math_tool_unclear",
        "task_type": "create_app",
        "language": "python",
        "repo_mode": "new_repo",
        "domain": "unknown",
        "prompt": "make a math thing",
        "questions": [
            {
                "id": "q1",
                "field": "domain",
                "question": (
                    "Should this be a basic CLI calculator, and which operations "
                    "should it support?"
                ),
                "required": True,
            }
        ],
        "unsupported_requirements": [],
    }
    assert {
        "reason": payload["reason"],  # type: ignore[index]
        "clarifications_needed": payload["clarifications_needed"],  # type: ignore[index]
    } == {
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


def test_plan_and_materialize_slugify_library_repo(tmp_path: Path) -> None:
    spec = _spec_from_fixture("slugify_library_basic")
    plan = plan_greenfield_repo(spec)
    record = plan.to_record()

    assert record["status"] == "ready"
    assert record["domain"] == "text_slugify"
    assert record["artifacts"] == ["slugify.py", "tests/test_slugify.py"]
    assert [action["kind"] for action in record["actions"]] == [
        "create_file",
        "add_import",
        "add_function_def",
        "create_test_file",
        "add_library_behavior_tests",
    ]

    result = build_greenfield_repo(plan, tmp_path)
    assert result.status == "built"
    assert result.files_written == ["slugify.py", "tests/test_slugify.py"]
    generated_pytest = _run_generated_pytest_file(tmp_path, "tests/test_slugify.py")
    assert (
        generated_pytest.returncode == 0
    ), generated_pytest.stdout + generated_pytest.stderr

    source = (tmp_path / "slugify.py").read_text(encoding="utf-8")
    assert "def slugify(text: str) -> str:" in source
    assert '"-".join(parts)' in source


def test_plan_and_materialize_key_value_parser_repo(tmp_path: Path) -> None:
    spec = _spec_from_fixture("key_value_parser_basic")
    plan = plan_greenfield_repo(spec)
    record = plan.to_record()

    assert record["status"] == "ready"
    assert record["domain"] == "key_value_parser"
    assert record["artifacts"] == ["kv_parser.py", "tests/test_kv_parser.py"]
    assert [action["kind"] for action in record["actions"]] == [
        "create_file",
        "add_function_def",
        "create_test_file",
        "add_parser_behavior_tests",
    ]

    result = build_greenfield_repo(plan, tmp_path)
    assert result.status == "built"
    assert result.files_written == ["kv_parser.py", "tests/test_kv_parser.py"]
    generated_pytest = _run_generated_pytest_file(tmp_path, "tests/test_kv_parser.py")
    assert (
        generated_pytest.returncode == 0
    ), generated_pytest.stdout + generated_pytest.stderr

    source = (tmp_path / "kv_parser.py").read_text(encoding="utf-8")
    assert "def parse_key_value_lines(text: str) -> dict[str, str]:" in source
    assert "line.split(\"=\", 1)" in source


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
    assert result.to_record()["clarification_response"] == {
        "schema_version": "clarification-response-v1",
        "status": "needs_clarification",
        "task_name": "calculator_scientific_unclear",
        "task_type": "create_app",
        "language": "python",
        "repo_mode": "new_repo",
        "domain": "calculator",
        "prompt": "make a scientific calculator",
        "questions": [
            {
                "id": "q1",
                "field": "features",
                "question": "Which scientific calculator operations should be supported?",
                "required": True,
            }
        ],
        "unsupported_requirements": [],
    }
    assert not (tmp_path / "calculator.py").exists()
    assert not (tmp_path / "tests").exists()
