from __future__ import annotations

import json

import pytest

from cli import main
from j3.transition_shadow_outcomes import (
    load_transition_shadow_outcomes,
    normalize_transition_shadow_outcomes,
    validate_transition_shadow_outcome,
    write_transition_shadow_outcomes_jsonl,
)


def test_normalize_transition_shadow_outcomes_joins_and_preserves_unjoined_rows(
    tmp_path,
) -> None:
    advice = tmp_path / "transition-advice.jsonl"
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    advice_rows = [
        _advice_row(
            task="boundary",
            repair_plan_id="plan-joined",
            selected_rank=2,
            scorer_top_rank=1,
            comparison={"known": True, "would_have": "regressed"},
        ),
        _advice_row(
            task="advice_only",
            repair_plan_id="plan-advice-only",
            selected_rank=1,
            scorer_top_rank=1,
            comparison={"known": False, "would_have": "unknown"},
        ),
    ]
    outcome_rows = [
        _outcome_row(
            task="boundary",
            repair_plan_id="plan-joined",
            rank_index=1,
            passed=False,
            is_first_pass=False,
        ),
        _outcome_row(
            task="boundary",
            repair_plan_id="plan-joined",
            rank_index=2,
            passed=True,
            is_first_pass=True,
        ),
        _outcome_row(
            task="outcomes_only",
            repair_plan_id="plan-outcomes-only",
            rank_index=1,
            passed=True,
            is_first_pass=True,
        ),
    ]
    _write_jsonl(advice, advice_rows)
    _write_jsonl(outcomes, outcome_rows)

    rows = normalize_transition_shadow_outcomes(
        advice_paths=[advice],
        candidate_outcome_paths=[outcomes],
    )

    assert [row["join_status"] for row in rows] == [
        "joined",
        "unjoined_advice",
        "unjoined_candidate_outcomes",
    ]
    joined = rows[0]
    assert joined["schema_version"] == "transition-shadow-outcome-v1"
    assert joined["key"] == {
        "task": "boundary",
        "phase": "ranked",
        "repair_plan_id": "plan-joined",
    }
    assert joined["task"]["family"] == "operator_boundary"
    assert joined["production_selected_candidate"]["rank_index"] == 2
    assert joined["production_selected_candidate"]["passed"] is True
    assert joined["scorer_top_candidate"]["rank_index"] == 1
    assert joined["candidate_ranking"][0]["rank_index"] == 1
    assert joined["candidate_ranking"][0]["scorer_rank_position"] == 1
    assert joined["candidate_ranking"][0]["validation"]["known"] is True
    assert joined["validation_outcome"]["production_first_passing_index"] == 2
    assert joined["validation_outcome"]["passing_candidate_count"] == 1
    assert joined["labels"]["outcome_label"] == "regressed"
    assert joined["labels"]["regression"] is True
    assert joined["usage"]["hosted_llm_api_calls"] == 0
    assert joined["runtime"]["hosted_repo_context_bytes"] == 0

    advice_only = rows[1]
    assert advice_only["unjoined_reason"] == "no_candidate_outcome_group_for_key"
    assert advice_only["production_selected_candidate"]["rank_index"] == 1
    assert advice_only["candidate_ranking"]

    outcomes_only = rows[2]
    assert outcomes_only["unjoined_reason"] == "no_shadow_advice_for_key"
    assert outcomes_only["scorer_top_candidate"] is None
    assert outcomes_only["production_selected_candidate"]["passed"] is True
    assert outcomes_only["validation_outcome"]["known"] is True


def test_transition_shadow_outcome_loader_and_validator_preserve_zero_usage(
    tmp_path,
) -> None:
    advice = tmp_path / "transition-advice.jsonl"
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    out = tmp_path / "shadow-outcomes.jsonl"
    _write_jsonl(
        advice,
        [
            _advice_row(
                task="boundary",
                repair_plan_id="plan-joined",
                selected_rank=1,
                scorer_top_rank=1,
                comparison={"known": True, "would_have": "same"},
            )
        ],
    )
    _write_jsonl(
        outcomes,
        [
            _outcome_row(
                task="boundary",
                repair_plan_id="plan-joined",
                rank_index=1,
                passed=True,
                is_first_pass=True,
            )
        ],
    )
    rows = normalize_transition_shadow_outcomes(
        advice_paths=[advice],
        candidate_outcome_paths=[outcomes],
    )

    written = write_transition_shadow_outcomes_jsonl(out, rows)
    loaded = load_transition_shadow_outcomes([written])

    assert loaded == rows
    assert loaded[0]["usage"] == {
        "hosted_llm_api_calls": 0,
        "hosted_llm_prompt_tokens": 0,
        "hosted_llm_completion_tokens": 0,
        "hosted_api_tokens": 0,
        "hosted_repo_context_bytes": 0,
    }

    bad = dict(loaded[0])
    bad["usage"] = {**bad["usage"], "hosted_api_tokens": None}
    with pytest.raises(ValueError, match="hosted_api_tokens"):
        validate_transition_shadow_outcome(bad)


def test_normalize_transition_shadow_outcomes_cli_writes_jsonl_and_summary(
    capsys,
    tmp_path,
) -> None:
    advice = tmp_path / "transition-advice.jsonl"
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    out = tmp_path / "shadow-outcomes.jsonl"
    _write_jsonl(
        advice,
        [
            _advice_row(
                task="boundary",
                repair_plan_id="plan-joined",
                selected_rank=1,
                scorer_top_rank=1,
                comparison={"known": True, "would_have": "same"},
            )
        ],
    )
    _write_jsonl(
        outcomes,
        [
            _outcome_row(
                task="boundary",
                repair_plan_id="plan-joined",
                rank_index=1,
                passed=True,
                is_first_pass=True,
            )
        ],
    )

    assert (
        main(
            [
                "normalize-transition-shadow-outcomes",
                "--advice",
                str(advice),
                "--candidate-outcomes",
                str(outcomes),
                "--out",
                str(out),
                "--json",
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    written_rows = [
        json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()
    ]
    assert summary["schema_version"] == "transition-shadow-outcome-summary-v1"
    assert summary["rows"] == 1
    assert summary["joined_rows"] == 1
    assert summary["labels"]["same"] == 1
    assert summary["usage"]["hosted_repo_context_bytes"] == 0
    assert written_rows[0]["schema_version"] == "transition-shadow-outcome-v1"


def _advice_row(
    *,
    task: str,
    repair_plan_id: str,
    selected_rank: int,
    scorer_top_rank: int,
    comparison: dict[str, object],
) -> dict[str, object]:
    usage = {
        "hosted_llm_api_calls": 0,
        "hosted_llm_prompt_tokens": 0,
        "hosted_llm_completion_tokens": 0,
        "hosted_api_tokens": 0,
        "hosted_repo_context_bytes": 0,
    }
    return {
        "schema_version": "transition-scorer-advice-v1",
        "mode": "shadow",
        "decision": "shadow_only_not_wired_to_routing",
        "repair_plan_id": repair_plan_id,
        "repo_state_summary": {
            "repo": "/tmp/example-repo",
            "repo_name": "example-repo",
            "python_file_count": 1,
        },
        "repair_context": {
            "task": task,
            "task_family": "operator_boundary",
            "source_type": "handcrafted",
            "split": "validation",
            "phase": "ranked",
            "test_command": "python -m pytest",
        },
        "candidate_count": 2,
        "existing_ranked_candidate_ranks": [1, 2],
        "scorer_ranked_candidate_ranks": [scorer_top_rank, 2 if scorer_top_rank == 1 else 1],
        "existing_selected_candidate": {
            "id": f"candidate-{selected_rank}",
            "rank_index": selected_rank,
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "params": {"to": ">="},
            "validated": True,
            "passed": True,
            "reason": f"candidate {selected_rank}",
        },
        "scorer_top_candidate": {
            "id": f"candidate-{scorer_top_rank}",
            "rank_index": scorer_top_rank,
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "params": {"to": ">="},
            "validated": True,
            "passed": scorer_top_rank == selected_rank,
            "score": 0.9,
            "reason": f"candidate {scorer_top_rank}",
        },
        "scorer_agreed_with_existing_rank_order": scorer_top_rank == 1,
        "scorer_agreed_with_existing_top_candidate": scorer_top_rank == selected_rank,
        "validation_comparison": comparison,
        "runtime": {"local_runtime_ms": 1.0, **usage},
        "usage": usage,
    }


def _outcome_row(
    *,
    task: str,
    repair_plan_id: str,
    rank_index: int,
    passed: bool,
    is_first_pass: bool,
) -> dict[str, object]:
    return {
        "task": task,
        "task_family": "operator_boundary",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": repair_plan_id,
        "file_path": "bugs.py",
        "action": "change_operator",
        "symbol": "meets_minimum",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "Compare",
        "params": {"to": ">="},
        "reason": f"candidate {rank_index}",
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": rank_index if is_first_pass else 2,
        "is_first_pass": is_first_pass,
    }


def _write_jsonl(path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
