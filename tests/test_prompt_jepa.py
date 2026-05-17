from __future__ import annotations

import json
from pathlib import Path

import pytest

from existing_repo_change import parse_existing_repo_change_to_spec
from prompt_intents import load_prompt_intent_records, predict_prompt_intent
from prompt_jepa import (
    PROMPT_JEPA_INDEX_FORMAT,
    build_prompt_jepa_index,
    compare_prompt_jepa_retrieval_modes,
    encode_prompt_context,
    encode_prompt_target,
    evaluate_prompt_jepa_predicted_target_retrieval,
    evaluate_prompt_jepa_retrieval,
    load_prompt_jepa_predictor,
    load_prompt_jepa_index,
    query_prompt_jepa_predicted_target,
    save_prompt_jepa_predictor,
    save_prompt_jepa_index,
    train_prompt_jepa_predictor,
)
from request_spec import parse_request_to_spec


GREENSHOT_7_INTENTS = Path("examples/prompt_intents/greenshot_7_intents.jsonl")


def test_prompt_jepa_encoders_are_deterministic_and_separate() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)
    record = records[0]

    context_a = encode_prompt_context(
        record.prompt,
        dim=32,
        source_type=record.source_type,
        task_type=record.target.task_type,
        tags=record.tags,
    )
    context_b = encode_prompt_context(
        record.prompt,
        dim=32,
        source_type=record.source_type,
        task_type=record.target.task_type,
        tags=record.tags,
    )
    target_a = encode_prompt_target(record.target, dim=32)
    target_b = encode_prompt_target(record.target, dim=32)

    assert context_a == context_b
    assert target_a == target_b
    assert len(context_a) == 32
    assert len(target_a) == 32
    assert context_a != target_a


def test_prompt_jepa_index_builds_from_local_fixture_records() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    index = build_prompt_jepa_index(
        records,
        embedding_dim=64,
        source_path=GREENSHOT_7_INTENTS,
    )
    record = index.to_record()

    assert record["format"] == PROMPT_JEPA_INDEX_FORMAT
    assert record["embedding_dim"] == 64
    assert record["context_encoder"] == {
        "kind": "feature_hashing",
        "schema_version": "prompt-context-v2",
    }
    assert record["target_encoder"] == {
        "kind": "feature_hashing",
        "schema_version": "prompt-target-v2",
    }
    assert len(index.rows) == len(records)
    assert {row.split for row in index.rows} == {"train", "validation", "test"}
    assert index.rows[0].row_id == "gs7-intent-0001"
    assert index.rows[0].source_path == str(GREENSHOT_7_INTENTS)
    assert len(index.rows[0].context_embedding) == 64
    assert len(index.rows[0].target_embedding) == 64
    assert index.rows[0].target["expected_action"] == "emit_request_spec"


def test_prompt_jepa_save_load_round_trip_validates_json(tmp_path: Path) -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)[:4]
    index = build_prompt_jepa_index(records, embedding_dim=32)
    path = tmp_path / "prompt-jepa-index.json"

    save_prompt_jepa_index(index, path)
    loaded = load_prompt_jepa_index(path)

    assert loaded.to_record() == index.to_record()
    assert json.loads(path.read_text(encoding="utf-8")) == index.to_record()


def test_prompt_jepa_load_rejects_bad_format_and_dimensions(tmp_path: Path) -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)[:2]
    index = build_prompt_jepa_index(records, embedding_dim=32)

    bad_format = index.to_record()
    bad_format["format"] = "j3.prompt-jepa-index.v0"
    bad_format_path = tmp_path / "bad-format.json"
    bad_format_path.write_text(json.dumps(bad_format), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported Prompt-JEPA index format"):
        load_prompt_jepa_index(bad_format_path)

    bad_dimension = index.to_record()
    bad_dimension["rows"][0]["context_embedding"] = [0.0] * 31  # type: ignore[index]
    bad_dimension_path = tmp_path / "bad-dimension.json"
    bad_dimension_path.write_text(json.dumps(bad_dimension), encoding="utf-8")

    with pytest.raises(ValueError, match="must have dimension 32"):
        load_prompt_jepa_index(bad_dimension_path)


def test_prompt_jepa_query_returns_sensible_nearest_neighbor() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)
    index = build_prompt_jepa_index(records, embedding_dim=128)

    results = index.query("make me a simple cli calc", top_k=3)

    assert results[0].row_id == "gs7-intent-0001"
    assert results[0].prompt == "make me a simple cli calc"
    assert results[0].split == "train"
    assert results[0].score > results[-1].score
    assert results[0].target_metadata == {
        "repo_mode": "new_repo",
        "task_type": "create_app",
        "domain": "calculator",
        "expected_action": "emit_request_spec",
        "requires_clarification": "no",
        "primary_artifact": "none",
        "unsupported_requirement": "none",
        "unsupported_requirement_family": "none",
        "requested_interfaces": ["cli"],
        "features": ["add", "subtract", "multiply", "divide"],
        "artifacts": [],
        "unsupported_requirements": [],
        "clarification_fields": [],
        "target_files": [],
    }


def test_prompt_jepa_retrieval_eval_scores_held_out_splits() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    result = evaluate_prompt_jepa_retrieval(
        records,
        embedding_dim=128,
        top_k=3,
        miss_limit=5,
    )
    record = result.to_record()

    assert record["schema_version"] == "prompt-jepa-retrieval-eval-v1"
    assert record["decision"] == "evaluation_only_not_wired_to_production"
    assert result.train_split == "train"
    assert result.train_rows == sum(1 for row in records if row.split == "train")
    assert result.fields == (
        "expected_action",
        "repo_mode",
        "domain",
        "unsupported_requirement_family",
    )
    assert set(result.split_results) == {"validation", "test"}

    validation = result.split_results["validation"]
    expected_action = validation.field_metrics["expected_action"]
    assert validation.total == sum(1 for row in records if row.split == "validation")
    assert expected_action.total == validation.total
    assert 0 <= expected_action.top_1_correct <= expected_action.total
    assert expected_action.top_1_correct <= expected_action.top_k_correct
    assert expected_action.top_k_correct <= expected_action.total

    test = result.split_results["test"]
    assert test.field_metrics["repo_mode"].total == test.total
    assert all(miss.nearest_neighbor_id for miss in test.misses)
    assert all(miss.expected for miss in test.misses)


def test_prompt_jepa_predictor_round_trips_and_queries_target_space(
    tmp_path: Path,
) -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)
    index = build_prompt_jepa_index(records, embedding_dim=64)
    predictor = train_prompt_jepa_predictor(index, train_split="train")
    path = tmp_path / "prompt-jepa-predictor.json"

    save_prompt_jepa_predictor(predictor, path)
    loaded = load_prompt_jepa_predictor(path)
    results = query_prompt_jepa_predicted_target(
        index,
        loaded,
        "make me a simple cli calc",
        top_k=3,
    )

    assert loaded.to_record() == predictor.to_record()
    assert loaded.to_record()["format"] == "j3.prompt-jepa-predictor.v0"
    assert loaded.to_record()["kind"] == "nearest_context_delta"
    assert loaded.to_record()["train_rows"] == sum(
        1 for row in records if row.split == "train"
    )
    assert results[0].split == "train"
    assert results[0].target_metadata["expected_action"] == "emit_request_spec"
    assert len(
        loaded.predict_target_embedding(
            index.rows[0].context_embedding,
            index=index,
        )
    ) == 64


def test_prompt_jepa_predicted_target_eval_scores_held_out_splits() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    result = evaluate_prompt_jepa_predicted_target_retrieval(
        records,
        embedding_dim=128,
        top_k=3,
        miss_limit=5,
    )
    record = result.to_record()

    assert record["schema_version"] == "prompt-jepa-predicted-target-eval-v1"
    assert record["mode"] == "predicted-target"
    assert record["predictor"]["format"] == "j3.prompt-jepa-predictor.v0"
    assert record["predictor"]["kind"] == "nearest_context_delta"
    assert result.train_rows == sum(1 for row in records if row.split == "train")
    assert set(result.split_results) == {"validation", "test"}

    validation = result.split_results["validation"]
    expected_action = validation.field_metrics["expected_action"]
    assert validation.total == sum(1 for row in records if row.split == "validation")
    assert expected_action.total == validation.total
    assert 0 <= expected_action.top_1_correct <= expected_action.total
    assert expected_action.top_1_correct <= expected_action.top_k_correct
    assert expected_action.top_k_correct <= expected_action.total


def test_prompt_jepa_compare_modes_reports_residual_movement() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    result = compare_prompt_jepa_retrieval_modes(
        records,
        embedding_dim=128,
        top_k=3,
        miss_limit=3,
    )
    record = result.to_record()

    assert record["schema_version"] == "prompt-jepa-mode-comparison-v1"
    assert record["decision"] == "evaluation_only_not_wired_to_production"
    assert record["context_neighbor"]["mode"] == "context-neighbor"
    assert record["predicted_target"]["mode"] == "predicted-target"
    assert result.context_neighbor.train_rows == result.predicted_target.train_rows
    assert result.residual_comparisons
    assert {
        (comparison.split, comparison.field)
        for comparison in result.residual_comparisons
    } >= {
        ("validation", "domain"),
        ("test", "expected_action"),
    }
    assert all(
        len(comparison.fixed_by_predicted_target) <= 3
        for comparison in result.residual_comparisons
    )


def test_prompt_jepa_target_summary_features_share_lexical_space() -> None:
    query = encode_prompt_context("add tests for missing token", dim=128)
    auth_target = encode_prompt_target(
        {
            "repo_mode": "existing_repo",
            "task_type": "add_tests",
            "domain": "auth",
            "expected_action": "emit_existing_repo_change_spec",
            "features": ["token_auth"],
            "artifacts": ["tests"],
            "requested_interfaces": ["python_api"],
        },
        dim=128,
    )
    cli_target = encode_prompt_target(
        {
            "repo_mode": "existing_repo",
            "task_type": "add_tests",
            "domain": "cli",
            "expected_action": "emit_existing_repo_change_spec",
            "features": ["test_help", "test_invalid_args"],
            "artifacts": ["tests"],
            "requested_interfaces": ["cli"],
        },
        dim=128,
    )

    auth_score = sum(left * right for left, right in zip(query, auth_target))
    cli_score = sum(left * right for left, right in zip(query, cli_target))

    assert auth_score > cli_score


def test_prompt_jepa_target_encoder_accepts_structured_spec_records() -> None:
    request_spec = parse_request_to_spec("make me a simple cli calc")
    request_vector = encode_prompt_target(request_spec, dim=32)

    intent = predict_prompt_intent("add exponent support")
    assert intent is not None
    change_spec = parse_existing_repo_change_to_spec(
        "add exponent support",
        intent=intent,
    )
    change_vector = encode_prompt_target(change_spec, dim=32)

    assert len(request_vector) == 32
    assert len(change_vector) == 32
    assert request_vector != change_vector
