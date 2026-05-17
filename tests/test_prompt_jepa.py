from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.existing_repo_change import parse_existing_repo_change_to_spec
from j3.prompt_intents import load_prompt_intent_records, predict_prompt_intent
from j3.prompt_jepa import (
    PROMPT_JEPA_INDEX_FORMAT,
    build_prompt_jepa_index,
    build_prompt_jepa_outcome_index_from_path,
    compare_prompt_jepa_retrieval_modes,
    encode_prompt_context,
    encode_prompt_target,
    evaluate_prompt_jepa_predicted_target_retrieval,
    evaluate_prompt_jepa_retrieval,
    load_prompt_jepa_predictor,
    load_prompt_jepa_index,
    load_prompt_jepa_outcome_records,
    propose_from_prompt_jepa,
    query_prompt_jepa_predicted_target,
    save_prompt_jepa_predictor,
    save_prompt_jepa_index,
    train_prompt_jepa_predictor,
)
from j3.request_spec import parse_request_to_spec


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


def test_prompt_jepa_outcome_index_normalizes_real_attempt_rows(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "attempts.jsonl"
    _write_outcome_rows(records_path)

    records = load_prompt_jepa_outcome_records(records_path)
    index = build_prompt_jepa_outcome_index_from_path(records_path, embedding_dim=32)

    assert [record.row_id for record in records] == [
        "request-repo-attempt-0002",
        "existing-repo-change-attempt-0003",
    ]
    assert len(index.rows) == 2
    assert index.metadata.sources == (str(records_path),)
    request_row = index.rows[0]
    assert request_row.prompt == "make me a simple cli calc"
    assert request_row.source_type == "greenshot_7_request_to_repo_attempt"
    assert request_row.tags == (
        "outcome",
        "greenshot_7_request_to_repo_attempt",
        "passed",
        "new_repo",
        "create_app",
        "calculator",
        "add",
        "subtract",
    )
    assert request_row.target["expected_action"] == "emit_request_spec"
    assert request_row.target["validation_status"] == "passed"
    assert request_row.target["files_written"] == [
        "calculator.py",
        "tests/test_calculator_cli.py",
        "request-spec.json",
    ]
    assert request_row.target["action_kinds"] == ["create_file", "validate"]
    assert "request_spec" in request_row.target
    assert "outcome" in request_row.target

    change_row = index.rows[1]
    assert change_row.source_type == "greenshot_7_existing_repo_change_attempt"
    assert change_row.target["expected_action"] == "emit_existing_repo_change_spec"
    assert change_row.target["features_to_add"] == ["power"]
    assert change_row.target["files_changed"] == [
        "calculator.py",
        "tests/test_calculator_cli.py",
    ]
    assert len(change_row.context_embedding) == 32
    assert len(change_row.target_embedding) == 32
    assert index.query("add exponent support", top_k=1)[0].row_id == (
        "existing-repo-change-attempt-0003"
    )


def test_prompt_jepa_proposal_dry_run_uses_real_outcome_neighbors(
    tmp_path: Path,
) -> None:
    records_path = tmp_path / "attempts.jsonl"
    _write_planner_proposal_outcome_rows(records_path)
    index = build_prompt_jepa_outcome_index_from_path(records_path, embedding_dim=128)

    simple = propose_from_prompt_jepa(
        index,
        "build a simple command line calculator",
        top_k=3,
    ).to_record()
    assert simple["schema_version"] == "prompt-jepa-planner-proposal-v1"
    assert simple["mode"] == "dry_run"
    assert simple["applies_changes"] is False
    assert simple["decision"] == "evaluation_only_not_wired_to_production"
    assert simple["suggested_outcome_kind"] == "greenshot_7_request_to_repo_attempt"
    assert simple["suggested_outcome_status"] == "built"
    assert simple["confidence"]["clear_nearest"] is True  # type: ignore[index]
    assert simple["suggested_target_summary"]["expected_action"] == "emit_request_spec"  # type: ignore[index]
    assert simple["suggested_target_summary"]["repo_mode"] == "new_repo"  # type: ignore[index]
    assert simple["suggested_target_summary"]["validation_status"] == "passed"  # type: ignore[index]
    assert simple["top_neighbors"][0]["id"] == "request-repo-attempt-0001"  # type: ignore[index]
    assert simple["evidence"]["uses_real_outcome_metadata"] is True  # type: ignore[index]

    power = propose_from_prompt_jepa(
        index,
        "add power operator to the calculator",
        top_k=3,
    ).to_record()
    assert power["suggested_outcome_kind"] == (
        "greenshot_7_existing_repo_change_attempt"
    )
    assert power["suggested_outcome_status"] == "validated"
    assert power["suggested_target_summary"]["expected_action"] == (  # type: ignore[index]
        "emit_existing_repo_change_spec"
    )
    assert power["suggested_target_summary"]["repo_mode"] == "existing_repo"  # type: ignore[index]
    assert power["top_neighbors"][0]["id"] == "existing-repo-change-attempt-0003"  # type: ignore[index]

    graphical = propose_from_prompt_jepa(
        index,
        "build a graphical calculator app",
        top_k=3,
    ).to_record()
    assert graphical["suggested_outcome_kind"] == "greenshot_7_request_to_repo_attempt"
    assert graphical["suggested_outcome_status"] == "blocked"
    assert graphical["suggested_target_summary"]["requires_clarification"] == "yes"  # type: ignore[index]
    assert graphical["suggested_target_summary"]["failure_kind"] == (  # type: ignore[index]
        "blocking_clarification"
    )
    assert graphical["top_neighbors"][0]["id"] == "request-repo-attempt-0002"  # type: ignore[index]


def _write_outcome_rows(path: Path) -> None:
    rows = [
        {"existing": True},
        {
            "schema_version": "request-repo-attempt-v1",
            "record_kind": "greenshot_7_request_to_repo_attempt",
            "raw_prompt": "make me a simple cli calc",
            "normalized_request_spec": {
                "schema_version": "request-spec-v1",
                "task_name": "simple-cli-calc",
                "task_type": "create_app",
                "language": "python",
                "repo_mode": "new_repo",
                "domain": "calculator",
                "prompt": "make me a simple cli calc",
                "artifacts": ["calculator.py", "tests/test_calculator_cli.py"],
                "interfaces": [{"kind": "cli", "style": "argparse"}],
                "features": ["add", "subtract"],
                "operation_aliases": {"add": ["add", "+"], "subtract": ["-"]},
                "inferred_defaults": [],
                "clarifications_needed": [],
                "validation": {
                    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
                    "hidden_cases": True,
                },
            },
            "greenfield_actions": [
                {"kind": "create_file", "target": "calculator.py", "payload": {}},
                {"kind": "validate", "target": None, "payload": {}},
            ],
            "build_result": {
                "schema_version": "greenfield-build-v1",
                "status": "built",
                "files_written": ["calculator.py", "tests/test_calculator_cli.py"],
                "cli_files_written": [
                    "calculator.py",
                    "tests/test_calculator_cli.py",
                    "request-spec.json",
                ],
            },
            "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            "passed": True,
            "failure_observation": None,
            "output_repo_path": "/tmp/calc",
        },
        {
            "schema_version": "existing-repo-change-attempt-v1",
            "record_kind": "greenshot_7_existing_repo_change_attempt",
            "raw_prompt": "add exponent support",
            "existing_repo_change_spec": {
                "schema_version": "existing-repo-change-spec-v1",
                "task_type": "modify_app",
                "repo_mode": "existing_repo",
                "domain": "calculator",
                "prompt": "add exponent support",
                "target_files": ["calculator.py", "tests/test_calculator_cli.py"],
                "features_to_add": ["power"],
                "operation_aliases": {"power": ["power", "pow", "^", "**"]},
                "validation": {
                    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
                    "hidden_cases": True,
                },
            },
            "existing_repo_actions": [
                {"kind": "inspect_repo", "target": None, "payload": {}},
                {"kind": "add_operator_dispatch", "target": "calculator.py", "payload": {}},
            ],
            "change_result": {
                "schema_version": "existing-repo-change-result-v1",
                "status": "validated",
                "repo_path": "/tmp/calc",
                "files_changed": ["calculator.py", "tests/test_calculator_cli.py"],
                "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            },
            "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            "passed": True,
            "failure_observation": None,
            "repo_path": "/tmp/calc",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_planner_proposal_outcome_rows(path: Path) -> None:
    rows = [
        {
            "schema_version": "request-repo-attempt-v1",
            "record_kind": "greenshot_7_request_to_repo_attempt",
            "raw_prompt": "make me a simple cli calc",
            "normalized_request_spec": {
                "schema_version": "request-spec-v1",
                "task_name": "simple-cli-calc",
                "task_type": "create_app",
                "language": "python",
                "repo_mode": "new_repo",
                "domain": "calculator",
                "prompt": "make me a simple cli calc",
                "artifacts": ["calculator.py", "tests/test_calculator_cli.py"],
                "interfaces": [{"kind": "cli", "style": "argparse"}],
                "features": ["add", "subtract", "multiply", "divide"],
                "operation_aliases": {"add": ["add", "+"], "subtract": ["-"]},
                "inferred_defaults": [],
                "clarifications_needed": [],
                "validation": {
                    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
                    "hidden_cases": True,
                },
            },
            "greenfield_actions": [
                {"kind": "create_file", "target": "calculator.py", "payload": {}},
                {"kind": "add_cli_entrypoint", "target": "calculator.py", "payload": {}},
                {"kind": "validate", "target": None, "payload": {}},
            ],
            "build_result": {
                "schema_version": "greenfield-build-v1",
                "status": "built",
                "files_written": ["calculator.py", "tests/test_calculator_cli.py"],
                "cli_files_written": [
                    "calculator.py",
                    "tests/test_calculator_cli.py",
                    "request-spec.json",
                ],
            },
            "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            "passed": True,
            "failure_observation": None,
            "output_repo_path": "/tmp/calc",
        },
        {
            "schema_version": "request-repo-attempt-v1",
            "record_kind": "greenshot_7_request_to_repo_attempt",
            "raw_prompt": "make me a complex graphic calc app",
            "normalized_request_spec": {
                "schema_version": "request-spec-v1",
                "task_name": "graphical-calculator",
                "task_type": "create_app",
                "language": "python",
                "repo_mode": "new_repo",
                "domain": "calculator",
                "prompt": "make me a complex graphic calc app",
                "artifacts": [],
                "interfaces": [],
                "features": [],
                "operation_aliases": {},
                "inferred_defaults": [],
                "clarifications_needed": [
                    {
                        "field": "interface",
                        "question": "Only CLI calculator apps are supported.",
                    }
                ],
                "validation": {"commands": [], "hidden_cases": False},
            },
            "greenfield_actions": [
                {"kind": "ask_clarification", "target": None, "payload": {}},
            ],
            "build_result": {
                "schema_version": "greenfield-build-v1",
                "status": "blocked",
                "files_written": [],
                "blockers": [
                    {
                        "field": "interface",
                        "question": "Only CLI calculator apps are supported.",
                    }
                ],
                "cli_files_written": [],
            },
            "validation": {
                "status": "not_run",
                "command": None,
                "exit_code": None,
                "reason": "blocked_clarification",
            },
            "passed": False,
            "failure_observation": {
                "kind": "blocking_clarification",
                "clarifications_needed": [
                    {
                        "field": "interface",
                        "question": "Only CLI calculator apps are supported.",
                    }
                ],
            },
            "output_repo_path": "/tmp/blocked-graphic",
        },
        {
            "schema_version": "existing-repo-change-attempt-v1",
            "record_kind": "greenshot_7_existing_repo_change_attempt",
            "raw_prompt": "add exponent support",
            "existing_repo_change_spec": {
                "schema_version": "existing-repo-change-spec-v1",
                "task_type": "modify_app",
                "repo_mode": "existing_repo",
                "domain": "calculator",
                "prompt": "add exponent support",
                "target_files": ["calculator.py", "tests/test_calculator_cli.py"],
                "features_to_add": ["power"],
                "operation_aliases": {"power": ["power", "pow", "^", "**"]},
                "validation": {
                    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
                    "hidden_cases": True,
                },
            },
            "existing_repo_actions": [
                {"kind": "inspect_repo", "target": None, "payload": {}},
                {"kind": "add_operator_dispatch", "target": "calculator.py", "payload": {}},
                {"kind": "validate", "target": None, "payload": {}},
            ],
            "change_result": {
                "schema_version": "existing-repo-change-result-v1",
                "status": "validated",
                "repo_path": "/tmp/calc",
                "files_changed": ["calculator.py", "tests/test_calculator_cli.py"],
                "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            },
            "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            "passed": True,
            "failure_observation": None,
            "repo_path": "/tmp/calc",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
