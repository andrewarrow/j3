from __future__ import annotations

from pathlib import Path

import pytest

from prompt_intents import (
    evaluate_prompt_intent_predictions,
    load_prompt_intent_records,
    predict_prompt_intent,
    profile_prompt_intents,
)


GREENSHOT_7_INTENTS = Path("examples/prompt_intents/greenshot_7_intents.jsonl")
SEED_CORPUS = Path("../prompts/coding_agent_prompts_seed.jsonl")


def test_loads_greenshot_7_prompt_intent_fixtures() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)
    profile = profile_prompt_intents(records)

    assert len(records) == 14
    assert profile["expected_action_counts"] == {
        "ask_clarification": 6,
        "emit_existing_repo_change_spec": 5,
        "emit_request_spec": 3,
    }
    assert profile["repo_mode_counts"] == {
        "existing_repo": 5,
        "new_repo": 8,
        "unknown": 1,
    }
    assert profile["unsupported_requirement_count"] == 6
    assert profile["existing_repo_change_count"] == 5

    unsupported = next(
        record
        for record in records
        if record.prompt == "make me a complex graphic calc app"
    )
    assert unsupported.target.expected_action == "ask_clarification"
    assert unsupported.target.requested_interfaces == ("graphic",)
    assert unsupported.target.unsupported_requirements == (
        "complex_scope",
        "graphical_interface",
    )
    assert unsupported.target.clarification_fields == ("interfaces",)

    power_change = next(record for record in records if record.prompt == "add exponent support")
    assert power_change.target.repo_mode == "existing_repo"
    assert power_change.target.expected_action == "emit_existing_repo_change_spec"
    assert power_change.target.features == ("power",)
    assert power_change.target.target_files == (
        "calculator.py",
        "tests/test_calculator_cli.py",
    )


def test_prompt_intent_eval_scores_future_predictors() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    perfect = evaluate_prompt_intent_predictions(records, lambda record: record.target)
    perfect_record = perfect.to_record()

    assert perfect_record["exact_accuracy"] == 1.0
    assert perfect_record["mismatches"] == []
    assert all(
        field["accuracy"] == 1.0
        for field in perfect_record["field_accuracy"].values()  # type: ignore[union-attr]
    )

    def misses_action(record):
        if record.row_id == "gs7-intent-0004":
            return {
                **record.target.to_record(),
                "expected_action": "emit_request_spec",
                "requested_interfaces": [],
            }
        return record.target

    result = evaluate_prompt_intent_predictions(records, misses_action).to_record()
    assert result["exact_matches"] == len(records) - 1
    assert result["field_accuracy"]["expected_action"]["correct"] == len(records) - 1  # type: ignore[index]
    assert result["field_accuracy"]["requested_interfaces"]["correct"] == len(records) - 1  # type: ignore[index]
    assert result["mismatches"][0]["id"] == "gs7-intent-0004"  # type: ignore[index]


def test_fixture_backed_prompt_intent_prediction_is_exact_boundary() -> None:
    prediction = predict_prompt_intent("make me a complex graphic calc app")

    assert prediction is not None
    assert prediction.source == "prompt_intent_fixture_exact_match"
    assert prediction.record_id == "gs7-intent-0004"
    assert prediction.target.expected_action == "ask_clarification"
    assert prediction.target.requested_interfaces == ("graphic",)
    assert prediction.target.unsupported_requirements == (
        "complex_scope",
        "graphical_interface",
    )

    assert predict_prompt_intent("make me a complex graphic spreadsheet") is None


def test_loads_external_seed_prompt_corpus_profile() -> None:
    if not SEED_CORPUS.exists():
        pytest.skip(f"seed prompt corpus is not available: {SEED_CORPUS}")

    records = load_prompt_intent_records(SEED_CORPUS)
    profile = profile_prompt_intents(records)

    assert profile["total"] >= 80
    assert profile["split_counts"]["train"] > 0  # type: ignore[index]
    assert profile["split_counts"]["validation"] > 0  # type: ignore[index]
    assert profile["split_counts"]["test"] > 0  # type: ignore[index]
    assert profile["repo_mode_counts"]["existing_repo"] > 0  # type: ignore[index]
    assert profile["repo_mode_counts"]["new_repo"] > 0  # type: ignore[index]
    assert profile["clarification_count"] > 0
    assert profile["existing_repo_change_count"] > 0


def test_prompt_intent_loader_validates_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        (
            '{"id":"missing-prompt","split":"train","source_type":"test",'
            '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator"}\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="prompt"):
        load_prompt_intent_records(path)
