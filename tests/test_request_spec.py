from __future__ import annotations

import json
from pathlib import Path

from j3.prompt_intents import predict_prompt_intent
from j3.request_spec import parse_request_to_spec


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


def test_request_spec_blocks_graphical_calculator_through_prompt_intent() -> None:
    prediction = predict_prompt_intent("make me a complex graphic calc app")
    spec = parse_request_to_spec(
        "make me a complex graphic calc app",
        task_name="graphic_calc",
        intent=prediction,
    )
    record = spec.to_record()

    assert record["domain"] == "calculator"
    assert record["artifacts"] == []
    assert record["features"] == []
    assert record["interfaces"] == []
    assert record["requested_interfaces"] == [
        {"kind": "graphic", "confidence": 1.0}
    ]
    assert record["supported_interfaces"] == [{"kind": "cli", "style": "argparse"}]
    assert record["unsupported_requirements"] == [
        {
            "field": "interfaces",
            "value": "complex_scope",
            "reason": "complex_scope",
        },
        {
            "field": "interfaces",
            "value": "graphical_interface",
            "reason": "graphical_interface",
        },
    ]
    assert record["clarifications_needed"] == [
        {
            "field": "interfaces",
            "question": (
                "This slice only supports a Python CLI calculator. Do you want a "
                "simple CLI calculator, or should a graphical app scope/framework "
                "be specified?"
            ),
        }
    ]


def test_request_spec_blocks_graphing_feature_scope_through_prompt_intent() -> None:
    prediction = predict_prompt_intent("make a graphing calculator")
    spec = parse_request_to_spec(
        "make a graphing calculator",
        task_name="graphing_calc",
        intent=prediction,
    )
    record = spec.to_record()

    assert record["domain"] == "calculator"
    assert record["artifacts"] == []
    assert record["features"] == []
    assert record["interfaces"] == []
    assert record["unsupported_requirements"] == [
        {
            "field": "features",
            "value": "graphing_feature_unspecified",
            "reason": "graphing_feature_unspecified",
        }
    ]
    assert record["clarifications_needed"] == [
        {
            "field": "features",
            "question": (
                "This slice only supports add, subtract, multiply, and divide in "
                "a Python CLI calculator. Which requested calculator features "
                "should be supported or deferred?"
            ),
        }
    ]
