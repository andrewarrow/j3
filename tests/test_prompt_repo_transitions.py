from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.prompt_jepa import (
    EXISTING_REPO_CHANGE_ATTEMPT_KIND,
    REQUEST_REPO_ATTEMPT_KIND,
)
from j3.prompt_repo_transitions import (
    EVALUATION_ONLY_DECISION,
    NEAREST_ACTION_DELTA_PREDICTOR_KIND,
    PROMPT_ONLY_RETRIEVAL_BASELINE_KIND,
    PROMPT_REPO_TRANSITION_EVAL_SCHEMA_VERSION,
    PROMPT_REPO_TRANSITION_PREDICTOR_SCHEMA_VERSION,
    PROMPT_REPO_TRANSITION_SCHEMA_VERSION,
    PromptRepoOutcomeState,
    build_prompt_repo_transition_rows,
    evaluate_prompt_repo_transition_predictions,
    fit_prompt_repo_transition_predictor_v0,
    load_prompt_repo_transition_predictor_json,
    predict_prompt_repo_transition_target_v0,
    write_prompt_repo_transition_predictor_json,
    write_prompt_repo_transitions_jsonl,
)
from j3.repo_state import encode_repo_state_record


def test_build_prompt_repo_transition_rows_for_source_change_and_blocked(
    tmp_path: Path,
) -> None:
    empty_repo = tmp_path / "empty"
    created_repo = tmp_path / "created"
    blocked_repo = tmp_path / "blocked"
    empty_repo.mkdir()
    created_repo.mkdir()
    blocked_repo.mkdir()
    (created_repo / "calculator.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )

    rows = build_prompt_repo_transition_rows(
        [
            _request_outcome_row(blocked=False),
            _request_outcome_row(blocked=True),
        ],
        [
            PromptRepoOutcomeState(
                repo_before=encode_repo_state_record(empty_repo, embedding_dim=16),
                repo_after=encode_repo_state_record(created_repo, embedding_dim=16),
            ),
            PromptRepoOutcomeState(
                repo_before=encode_repo_state_record(blocked_repo, embedding_dim=16),
                repo_after=encode_repo_state_record(blocked_repo, embedding_dim=16),
            ),
        ],
        embedding_dim=16,
    )

    assert json.loads(json.dumps(rows, sort_keys=True)) == list(rows)
    assert [row["schema_version"] for row in rows] == [
        PROMPT_REPO_TRANSITION_SCHEMA_VERSION,
        PROMPT_REPO_TRANSITION_SCHEMA_VERSION,
    ]
    assert rows[0]["structured_action"]["kind"] == "create_repo"  # type: ignore[index]
    assert rows[0]["outcome"]["kind"] == "source_changed"  # type: ignore[index]
    assert rows[0]["repo_before"]["state"]["included_python_file_paths"] == []  # type: ignore[index]
    assert rows[0]["repo_after"]["state"]["included_python_file_paths"] == [  # type: ignore[index]
        "calculator.py"
    ]
    assert rows[0]["prompt_context"]["embedding_dim"] == 16  # type: ignore[index]
    assert len(rows[0]["prompt_context"]["embedding"]) == 16  # type: ignore[index]
    assert len(rows[0]["prompt_context"]["embedding_checksum"]) == 64  # type: ignore[index]
    assert len(rows[0]["prompt_jepa_target"]["embedding_checksum"]) == 64  # type: ignore[index]
    assert rows[0]["prompt_jepa_target"]["summary"]["outcome_kind"] == (  # type: ignore[index]
        "source_changed"
    )
    assert rows[0]["cost"]["hosted_llm_api_tokens"] == 0  # type: ignore[index]
    assert rows[0]["cost"]["hosted_repo_context_bytes"] == 0  # type: ignore[index]
    assert rows[0]["validation"]["status"] == "passed"  # type: ignore[index]

    assert rows[1]["structured_action"]["kind"] == "ask_clarification"  # type: ignore[index]
    assert rows[1]["outcome"]["kind"] == "blocked_no_change"  # type: ignore[index]
    assert rows[1]["repo_after"]["kind"] == "blocked_no_change"  # type: ignore[index]
    assert rows[1]["repo_after"]["state_checksum"] == (  # type: ignore[index]
        rows[1]["repo_before"]["state_checksum"]  # type: ignore[index]
    )
    assert rows[1]["validation"]["status"] == "not_run"  # type: ignore[index]
    assert rows[1]["cost"]["validation_command_count"] == 0  # type: ignore[index]


def test_build_prompt_repo_transition_rows_supports_existing_repo_change(
    tmp_path: Path,
) -> None:
    before_repo = tmp_path / "before"
    after_repo = tmp_path / "after"
    before_repo.mkdir()
    after_repo.mkdir()
    (before_repo / "calculator.py").write_text(
        "def calculate(left, operator, right):\n    return left + right\n",
        encoding="utf-8",
    )
    (after_repo / "calculator.py").write_text(
        "def calculate(left, operator, right):\n"
        "    if operator == '**':\n"
        "        return left ** right\n"
        "    return left + right\n",
        encoding="utf-8",
    )

    rows = build_prompt_repo_transition_rows(
        [_change_outcome_row()],
        [
            PromptRepoOutcomeState(
                repo_before=encode_repo_state_record(before_repo, embedding_dim=16),
                repo_after=encode_repo_state_record(after_repo, embedding_dim=16),
            )
        ],
        embedding_dim=16,
    )

    assert rows[0]["structured_action"]["kind"] == "modify_repo"  # type: ignore[index]
    assert rows[0]["structured_action"]["features"] == ["power"]  # type: ignore[index]
    assert rows[0]["outcome"]["status"] == "validated"  # type: ignore[index]
    assert rows[0]["repo_after"]["kind"] == "source_changed"  # type: ignore[index]
    assert rows[0]["cost"]["validation_command_count"] == 1  # type: ignore[index]


def test_write_prompt_repo_transitions_jsonl_is_deterministic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = encode_repo_state_record(repo, embedding_dim=16)
    rows = build_prompt_repo_transition_rows(
        [_request_outcome_row(blocked=True)],
        [PromptRepoOutcomeState(repo_before=state, repo_after=state)],
        embedding_dim=16,
    )

    out = write_prompt_repo_transitions_jsonl(rows, tmp_path / "transitions.jsonl")

    loaded = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert loaded == list(rows)
    assert loaded[0]["schema_version"] == PROMPT_REPO_TRANSITION_SCHEMA_VERSION


def test_fit_transition_predictor_v0_returns_evaluation_only_metadata(
    tmp_path: Path,
) -> None:
    rows = _sample_transition_rows(tmp_path)

    predictor = fit_prompt_repo_transition_predictor_v0(rows)
    record = predictor.to_record()

    assert json.loads(json.dumps(record, sort_keys=True)) == record
    assert record["schema_version"] == PROMPT_REPO_TRANSITION_PREDICTOR_SCHEMA_VERSION
    assert record["predictor_kind"] == NEAREST_ACTION_DELTA_PREDICTOR_KIND
    assert record["decision"] == EVALUATION_ONLY_DECISION
    assert record["embedding_dim"] == 16
    assert record["train_row_ids"] == [row["id"] for row in rows]
    assert set(record["action_source_deltas"]) == {"create_repo", "modify_repo"}
    assert len(record["train_examples"]) == 3
    assert record["train_examples"][0]["target_kind"] == "repo_after_embedding"  # type: ignore[index]
    assert record["train_examples"][0]["repo_after_embedding"] == (  # type: ignore[index]
        rows[0]["repo_after"]["state"]["repo_embedding"]  # type: ignore[index]
    )
    assert record["train_examples"][1]["target_kind"] == "blocked_or_clarification"  # type: ignore[index]


def test_write_and_load_transition_predictor_v0_json(tmp_path: Path) -> None:
    rows = _sample_transition_rows(tmp_path)
    predictor = fit_prompt_repo_transition_predictor_v0(rows)

    out = write_prompt_repo_transition_predictor_json(
        predictor,
        tmp_path / "transition-model.json",
    )
    loaded = load_prompt_repo_transition_predictor_json(out)

    assert json.loads(out.read_text(encoding="utf-8")) == predictor.to_record()
    assert loaded.to_record() == predictor.to_record()


def test_predict_transition_target_v0_handles_source_and_blocked_targets(
    tmp_path: Path,
) -> None:
    rows = _sample_transition_rows(tmp_path)
    predictor = fit_prompt_repo_transition_predictor_v0(rows)

    source_prediction = predict_prompt_repo_transition_target_v0(predictor, rows[0])
    expected_after = rows[0]["repo_after"]["state"]["repo_embedding"]  # type: ignore[index]
    assert source_prediction["schema_version"] == "prompt-repo-transition-prediction-v0"
    assert source_prediction["decision"] == EVALUATION_ONLY_DECISION
    assert source_prediction["nearest_train_row_id"] == rows[0]["id"]
    assert source_prediction["target"]["kind"] == "repo_after_embedding"  # type: ignore[index]
    assert source_prediction["target"]["source_delta_kind"] == (  # type: ignore[index]
        "action_conditioned_average"
    )
    assert source_prediction["target"]["repo_after_embedding"] == expected_after  # type: ignore[index]
    assert source_prediction["input_features"]["prompt_context_embedding"] is True  # type: ignore[index]
    assert source_prediction["input_features"]["repo_before_embedding"] is True  # type: ignore[index]

    blocked_prediction = predict_prompt_repo_transition_target_v0(predictor, rows[1])
    assert blocked_prediction["nearest_train_row_id"] == rows[1]["id"]
    assert blocked_prediction["target"]["kind"] == "blocked_or_clarification"  # type: ignore[index]
    assert blocked_prediction["target"]["outcome_kind"] == "blocked_no_change"  # type: ignore[index]
    assert blocked_prediction["target"]["validation_status"] == "not_run"  # type: ignore[index]
    assert blocked_prediction["target"]["failure_kind"] == "blocking_clarification"  # type: ignore[index]
    assert blocked_prediction["target"]["clarification_fields"] == [  # type: ignore[index]
        "unsupported_requirement"
    ]
    assert blocked_prediction["target"]["repo_after_embedding"] is None  # type: ignore[index]


def test_evaluate_transition_predictions_reports_metrics_and_residuals(
    tmp_path: Path,
) -> None:
    rows = _sample_transition_rows(tmp_path)

    result = evaluate_prompt_repo_transition_predictions(
        rows,
        top_k=3,
        residual_limit=5,
    )

    assert json.loads(json.dumps(result, sort_keys=True)) == result
    assert result["schema_version"] == PROMPT_REPO_TRANSITION_EVAL_SCHEMA_VERSION
    assert result["decision"] == EVALUATION_ONLY_DECISION
    assert result["predictor_kind"] == NEAREST_ACTION_DELTA_PREDICTOR_KIND
    assert result["baseline_kind"] == PROMPT_ONLY_RETRIEVAL_BASELINE_KIND
    assert result["rows"] == 3
    assert result["embedding_dim"] == 16
    assert result["top_k"] == 3
    assert result["effective_top_k"] == 2
    assert result["source_split"] == {  # type: ignore[comparison-overlap]
        "source_change_or_no_change": 2,
        "blocked_or_clarification": 1,
    }

    v0 = result["v0_predictor"]
    prompt_only = result["prompt_only_baseline"]
    assert v0["outcome_kind"]["total"] == 3  # type: ignore[index]
    assert v0["outcome_kind"]["top_1_correct"] <= (  # type: ignore[index]
        v0["outcome_kind"]["top_k_correct"]  # type: ignore[index]
    )
    assert v0["validation_status"]["total"] == 3  # type: ignore[index]
    assert prompt_only["outcome_kind"]["total"] == 3  # type: ignore[index]
    assert prompt_only["validation_status"]["top_1_correct"] <= (  # type: ignore[index]
        prompt_only["validation_status"]["top_k_correct"]  # type: ignore[index]
    )
    distance = v0["repo_after_embedding_distance"]  # type: ignore[index]
    assert distance["total_applicable"] == 2
    assert distance["predicted_source_targets"] <= 2
    assert set(distance) == {
        "total_applicable",
        "predicted_source_targets",
        "missing_source_predictions",
        "mean",
        "min",
        "max",
    }
    residuals = result["residual_examples"]
    assert residuals
    first = residuals[0]
    assert {
        "prompt",
        "action",
        "expected",
        "predicted",
        "prompt_only",
        "distance",
    } <= set(first)


def test_source_changing_transition_requires_repo_after(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="requires repo_after"):
        build_prompt_repo_transition_rows(
            [_request_outcome_row(blocked=False)],
            [
                PromptRepoOutcomeState(
                    repo_before=encode_repo_state_record(repo, embedding_dim=16),
                    repo_after=None,
                )
            ],
            embedding_dim=16,
        )


def _sample_transition_rows(tmp_path: Path) -> tuple[dict[str, object], ...]:
    empty_repo = tmp_path / "empty"
    created_repo = tmp_path / "created"
    blocked_repo = tmp_path / "blocked"
    before_repo = tmp_path / "before"
    after_repo = tmp_path / "after"
    for repo in (empty_repo, created_repo, blocked_repo, before_repo, after_repo):
        repo.mkdir()
    (created_repo / "calculator.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    (before_repo / "calculator.py").write_text(
        "def calculate(left, operator, right):\n    return left + right\n",
        encoding="utf-8",
    )
    (after_repo / "calculator.py").write_text(
        "def calculate(left, operator, right):\n"
        "    if operator == '**':\n"
        "        return left ** right\n"
        "    return left + right\n",
        encoding="utf-8",
    )
    return build_prompt_repo_transition_rows(
        [
            _request_outcome_row(blocked=False),
            _request_outcome_row(blocked=True),
            _change_outcome_row(),
        ],
        [
            PromptRepoOutcomeState(
                repo_before=encode_repo_state_record(empty_repo, embedding_dim=16),
                repo_after=encode_repo_state_record(created_repo, embedding_dim=16),
            ),
            PromptRepoOutcomeState(
                repo_before=encode_repo_state_record(blocked_repo, embedding_dim=16),
                repo_after=encode_repo_state_record(blocked_repo, embedding_dim=16),
            ),
            PromptRepoOutcomeState(
                repo_before=encode_repo_state_record(before_repo, embedding_dim=16),
                repo_after=encode_repo_state_record(after_repo, embedding_dim=16),
            ),
        ],
        embedding_dim=16,
    )


def _request_outcome_row(*, blocked: bool) -> dict[str, object]:
    clarifications = (
        [{"field": "unsupported_requirement", "message": "authentication is out of scope"}]
        if blocked
        else []
    )
    actions = (
        [{"kind": "ask_clarification", "target": None, "payload": {}}]
        if blocked
        else [{"kind": "create_file", "target": "calculator.py", "payload": {}}]
    )
    return {
        "record_kind": REQUEST_REPO_ATTEMPT_KIND,
        "raw_prompt": "add auth" if blocked else "make me a simple cli calc",
        "normalized_request_spec": {
            "schema_version": "request-spec-v1",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "features": ["add"],
            "artifacts": ["calculator.py"],
            "interfaces": [{"kind": "cli"}],
            "clarifications_needed": clarifications,
        },
        "greenfield_actions": actions,
        "build_result": {
            "status": "blocked" if blocked else "built",
            "files_written": [] if blocked else ["calculator.py"],
        },
        "validation": {
            "status": "not_run" if blocked else "passed",
            "command": None if blocked else "python -m pytest tests -q",
            "exit_code": None if blocked else 0,
        },
        "passed": not blocked,
        "failure_observation": {
            "kind": "blocking_clarification",
            "clarifications_needed": clarifications,
        }
        if blocked
        else None,
    }


def _change_outcome_row() -> dict[str, object]:
    return {
        "record_kind": EXISTING_REPO_CHANGE_ATTEMPT_KIND,
        "raw_prompt": "add exponent support",
        "existing_repo_change_spec": {
            "schema_version": "existing-repo-change-spec-v1",
            "task_type": "modify_app",
            "repo_mode": "existing_repo",
            "domain": "calculator",
            "features_to_add": ["power"],
            "target_files": ["calculator.py"],
        },
        "existing_repo_actions": [
            {"kind": "inspect_repo", "target": None, "payload": {}},
            {"kind": "add_operator_dispatch", "target": "calculator.py", "payload": {}},
            {"kind": "validate", "target": None, "payload": {}},
        ],
        "change_result": {
            "status": "validated",
            "files_changed": ["calculator.py"],
        },
        "validation": {
            "status": "passed",
            "command": "python -m pytest tests/test_calculator_cli.py -q",
            "exit_code": 0,
        },
        "passed": True,
        "failure_observation": None,
    }
