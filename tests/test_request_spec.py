from __future__ import annotations

import json
from pathlib import Path

from request_spec import parse_request_to_spec


TASKS_PATH = Path("examples/greenshot_7/tasks.json")


def _load_tasks() -> list[dict[str, object]]:
    return json.loads(TASKS_PATH.read_text())


def test_parser_matches_greenshot_7_fixture_specs() -> None:
    for task in _load_tasks():
        spec = parse_request_to_spec(
            str(task["prompt"]),
            task_name=str(task["name"]),
        )

        assert spec.to_record() == task["expected_spec"]


def test_parser_emits_request_specs_for_positive_calculator_rows() -> None:
    positives = [
        task for task in _load_tasks() if task["expected_action"] == "emit_request_spec"
    ]

    assert len(positives) == 8
    for task in positives:
        record = parse_request_to_spec(
            str(task["prompt"]),
            task_name=str(task["name"]),
        ).to_record()

        assert record["features"] == task["expected_features"]
        assert record["clarifications_needed"] == []
        assert record["artifacts"] == ["calculator.py", "tests/test_calculator_cli.py"]
        assert record["interfaces"] == [{"kind": "cli", "style": "argparse"}]
        assert record["validation"] == {
            "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
            "hidden_cases": True,
        }


def test_parser_preserves_expected_inferred_defaults() -> None:
    tasks = {str(task["name"]): task for task in _load_tasks()}

    for name in [
        "calculator_basic_etc",
        "calculator_short_calc",
        "calculator_operator_params",
        "calculator_ambiguous",
    ]:
        record = parse_request_to_spec(
            str(tasks[name]["prompt"]),
            task_name=name,
        ).to_record()

        assert record["inferred_defaults"] == tasks[name]["expected_spec"][
            "inferred_defaults"
        ]

    add_only = parse_request_to_spec(
        str(tasks["calculator_add_only"]["prompt"]),
        task_name="calculator_add_only",
    ).to_record()
    assert add_only["inferred_defaults"] == []
    assert add_only["operation_aliases"] == {"add": ["add", "plus", "+"]}


def test_parser_emits_blocking_clarifications_for_unclear_rows() -> None:
    unclear = [
        task for task in _load_tasks() if task["expected_action"] == "ask_clarification"
    ]

    assert len(unclear) == 2
    for task in unclear:
        record = parse_request_to_spec(
            str(task["prompt"]),
            task_name=str(task["name"]),
        ).to_record()

        assert record["features"] == []
        assert record["operation_aliases"] == {}
        assert record["artifacts"] == []
        assert record["interfaces"] == []
        assert record["validation"] == {"commands": [], "hidden_cases": False}
        assert record["clarifications_needed"] == task["expected_spec"][
            "clarifications_needed"
        ]
