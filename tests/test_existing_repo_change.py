from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from j3.existing_repo_change import (
    ExistingRepoChangeError,
    apply_existing_repo_change,
    inspect_generated_calculator_repo,
    parse_existing_repo_change_to_spec,
    plan_existing_repo_change,
)
from j3.greenfield import build_calculator_repo
from j3.prompt_intents import predict_prompt_intent
from j3.request_spec import parse_request_to_spec


def _generate_calculator_repo(path: Path) -> None:
    spec = parse_request_to_spec(
        "make me a simple cli calc",
        intent=predict_prompt_intent("make me a simple cli calc"),
    )
    result = build_calculator_repo(spec, path)
    assert result.status == "built"


def _run_calculator(repo: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "calculator.py"), *argv],
        text=True,
        capture_output=True,
        check=False,
    )


def test_parse_existing_repo_power_prompt_to_change_spec() -> None:
    prediction = predict_prompt_intent("add exponent support")
    spec = parse_existing_repo_change_to_spec(
        "add exponent support",
        intent=prediction,
    )
    record = spec.to_record()

    assert json.loads(json.dumps(record)) == record
    assert record["schema_version"] == "existing-repo-change-spec-v1"
    assert record["task_type"] == "modify_app"
    assert record["repo_mode"] == "existing_repo"
    assert record["domain"] == "calculator"
    assert record["target_files"] == ["calculator.py", "tests/test_calculator_cli.py"]
    assert record["features_to_add"] == ["power"]
    assert record["operation_aliases"] == {
        "power": ["power", "pow", "^", "**"]
    }
    assert record["validation"] == {
        "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
        "hidden_cases": True,
    }
    assert record["intent_record_id"] == "gs7-intent-0010"


def test_plan_existing_repo_power_change_inspects_generated_shape(tmp_path: Path) -> None:
    _generate_calculator_repo(tmp_path)
    spec = parse_existing_repo_change_to_spec(
        "support power operator",
        intent=predict_prompt_intent("support power operator"),
    )

    plan = plan_existing_repo_change(spec, tmp_path)
    record = plan.to_record()

    assert record["schema_version"] == "existing-repo-change-plan-v1"
    assert record["status"] == "ready"
    assert record["target_files"] == ["calculator.py", "tests/test_calculator_cli.py"]
    assert [action["kind"] for action in record["actions"]] == [
        "inspect_repo",
        "parse_existing_calculator",
        "add_operator_aliases",
        "add_operator_dispatch",
        "add_cli_behavior_tests",
        "validate",
    ]
    assert record["actions"][2]["payload"] == {  # type: ignore[index]
        "feature": "power",
        "aliases": ["power", "pow", "^", "**"],
    }
    assert record["actions"][3]["payload"] == {  # type: ignore[index]
        "feature": "power",
        "expression": "left ** right",
    }


def test_apply_existing_repo_power_change_updates_source_tests_and_validates(
    tmp_path: Path,
) -> None:
    _generate_calculator_repo(tmp_path)
    spec = parse_existing_repo_change_to_spec(
        "make calculator.py handle 2 ^ 3",
        intent=predict_prompt_intent("make calculator.py handle 2 ^ 3"),
    )

    result = apply_existing_repo_change(spec, tmp_path)

    assert result.status == "validated"
    assert result.files_changed == ["calculator.py", "tests/test_calculator_cli.py"]
    assert result.validation["status"] == "passed"
    assert _run_calculator(tmp_path, "2", "^", "3").stdout.strip() == "8"
    assert _run_calculator(tmp_path, "2", "power", "3").stdout.strip() == "8"
    assert _run_calculator(tmp_path, "2", "**", "3").stdout.strip() == "8"

    source = (tmp_path / "calculator.py").read_text(encoding="utf-8")
    tests = (tmp_path / "tests/test_calculator_cli.py").read_text(encoding="utf-8")
    assert '"power": (\'power\', \'pow\', \'^\', \'**\'),' in source
    assert "return left ** right" in source
    assert "'argv': ['2', 'power', '3']" in tests
    assert "'argv': ['2', 'mod', '3']" in tests


def test_existing_repo_change_rejects_unrelated_repo(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text("print('not generated')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_calculator_cli.py").write_text("", encoding="utf-8")

    with pytest.raises(ExistingRepoChangeError, match="known generated calculator"):
        inspect_generated_calculator_repo(tmp_path)


def test_existing_repo_change_rejects_unlabeled_prompt() -> None:
    with pytest.raises(ExistingRepoChangeError, match="unsupported change prompt"):
        parse_existing_repo_change_to_spec(
            "rewrite the calculator into a web app",
            intent=predict_prompt_intent("rewrite the calculator into a web app"),
        )
