from __future__ import annotations

from pathlib import Path

import pytest

from prompt_intents import (
    evaluate_prompt_intent_predictions,
    load_prompt_intent_records,
    predict_prompt_intent,
    profile_prompt_intents,
    train_prompt_intent_token_baseline,
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
    assert profile["artifact_counts"]["module"] > 0  # type: ignore[index]
    assert profile["artifact_counts"]["pyproject"] > 0  # type: ignore[index]
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


def test_trains_token_baseline_only_from_train_split(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    path.write_text(
        "\n".join(
            [
                (
                    '{"id":"train-create-1","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator",'
                    '"prompt":"create a new calculator cli","expected":{"action":"emit_request_spec"}}'
                ),
                (
                    '{"id":"train-create-2","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"timer",'
                    '"prompt":"build a fresh timer cli","expected":{"action":"emit_request_spec"}}'
                ),
                (
                    '{"id":"train-change-1","split":"train","source_type":"test",'
                    '"task_type":"add_feature","repo_mode":"existing_repo","domain":"calculator",'
                    '"prompt":"change the existing calculator","expected":'
                    '{"action":"emit_existing_repo_change_spec"}}'
                ),
                (
                    '{"id":"train-change-2","split":"train","source_type":"test",'
                    '"task_type":"bugfix","repo_mode":"existing_repo","domain":"parser",'
                    '"prompt":"fix an existing parser bug","expected":'
                    '{"action":"emit_existing_repo_change_spec"}}'
                ),
                (
                    '{"id":"validation-unseen","split":"validation","source_type":"test",'
                    '"task_type":"clarify","repo_mode":"unknown","domain":"math",'
                    '"prompt":"validation only vague math thing","expected":'
                    '{"action":"ask_clarification"}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_prompt_intent_records(path)
    result = train_prompt_intent_token_baseline(
        records,
        target_field="expected_action",
        eval_splits=("train", "validation"),
    )

    assert result.train_rows == 4
    assert result.decision == "evaluation_only_not_wired_to_production"
    assert result.majority_label == "emit_existing_repo_change_spec"
    assert result.model.labels == (
        "emit_existing_repo_change_spec",
        "emit_request_spec",
    )
    assert "ask_clarification" not in result.model.labels
    assert result.metrics["train"].accuracy == 1.0
    assert result.metrics["validation"].total == 1
    assert result.metrics["validation"].correct == 0
    assert result.metrics["validation"].residuals[0].to_record() == {
        "target_field": "expected_action",
        "id": "validation-unseen",
        "split": "validation",
        "source_type": "test",
        "prompt": "validation only vague math thing",
        "expected": "ask_clarification",
        "predicted": "emit_request_spec",
        "baseline_label": "emit_existing_repo_change_spec",
        "baseline_correct": False,
        "tags": [],
    }


def test_seed_corpus_learned_baseline_reports_held_out_metrics() -> None:
    if not SEED_CORPUS.exists():
        pytest.skip(f"seed prompt corpus is not available: {SEED_CORPUS}")

    records = load_prompt_intent_records(SEED_CORPUS)

    expected_action = train_prompt_intent_token_baseline(
        records,
        target_field="expected_action",
    )
    repo_mode = train_prompt_intent_token_baseline(
        records,
        target_field="repo_mode",
    )

    assert expected_action.metrics["validation"].accuracy >= 0.66
    assert expected_action.metrics["test"].accuracy >= 0.75
    assert (
        expected_action.metrics["validation"].accuracy
        > expected_action.metrics["validation"].baseline_accuracy
    )
    assert (
        expected_action.metrics["test"].accuracy
        > expected_action.metrics["test"].baseline_accuracy
    )
    assert repo_mode.metrics["validation"].accuracy >= 0.86
    assert repo_mode.metrics["test"].accuracy >= 0.91
    assert (
        repo_mode.metrics["validation"].accuracy
        > repo_mode.metrics["validation"].baseline_accuracy
    )
    assert repo_mode.metrics["test"].accuracy > repo_mode.metrics["test"].baseline_accuracy
    assert [residual.row_id for residual in expected_action.metrics["validation"].residuals] == [
        "seed-0015",
        "seed-0059",
        "seed-0067",
        "seed-0074",
        "seed-0078",
    ]
    assert [residual.row_id for residual in expected_action.metrics["test"].residuals] == [
        "seed-0065",
        "seed-0076",
        "seed-0080",
    ]
    assert [residual.row_id for residual in repo_mode.metrics["validation"].residuals] == [
        "seed-0015",
        "seed-0062",
    ]
    assert [residual.row_id for residual in repo_mode.metrics["test"].residuals] == [
        "seed-0065",
    ]
    assert expected_action.decision == "evaluation_only_not_wired_to_production"
    assert repo_mode.decision == "evaluation_only_not_wired_to_production"
