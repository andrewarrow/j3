from __future__ import annotations

import json

from cli import main
from j3.transition_action_choice import build_transition_action_choice_groups_jsonl
from j3.transition_action_scoring import (
    GATE_NOT_READY_UNDERPERFORMS,
    GATE_READY_FOR_GUARDED_OPT_IN,
    TRANSITION_ACTION_SCORER_V2_VERSION,
    TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
    TRANSITION_ACTION_SCORER_V3_VERSION,
    evaluate_transition_shadow_scorer_v3,
)
from j3.transition_shadow_outcomes import (
    normalize_transition_shadow_outcomes,
    write_transition_shadow_outcomes_jsonl,
)


def test_v3_shadow_scorer_reports_held_out_gate_and_zero_hosted_usage(tmp_path) -> None:
    candidate_outcomes = tmp_path / "candidate-outcomes.jsonl"
    advice = tmp_path / "advice.jsonl"
    shadow_outcomes = tmp_path / "shadow-outcomes.jsonl"
    rows = [
        *_candidate_pair(task="a_train", plan="plan-a", passing_rank=2),
        *_candidate_pair(task="b_train", plan="plan-b", passing_rank=2),
        *_candidate_pair(task="z_validation", plan="plan-z", passing_rank=2),
    ]
    _write_jsonl(candidate_outcomes, rows)
    _write_jsonl(
        advice,
        [
            _advice_row(task="a_train", plan="plan-a", scorer_top_rank=2),
            _advice_row(task="b_train", plan="plan-b", scorer_top_rank=2),
            _advice_row(task="z_validation", plan="plan-z", scorer_top_rank=2),
        ],
    )
    shadow_rows = normalize_transition_shadow_outcomes(
        advice_paths=[advice],
        candidate_outcome_paths=[candidate_outcomes],
    )
    write_transition_shadow_outcomes_jsonl(shadow_outcomes, shadow_rows)
    groups = build_transition_action_choice_groups_jsonl(candidate_outcomes, embedding_dim=8)

    report = evaluate_transition_shadow_scorer_v3(
        groups,
        shadow_rows,
        split_by="order",
        validation_fraction=0.34,
        top_k=1,
        epochs=6,
    )

    assert report["schema_version"] == TRANSITION_ACTION_SCORER_V3_REPORT_VERSION
    assert report["decision"] == "evaluation_only_not_wired_to_production"
    assert report["available"] is True
    assert report["split"]["held_out"] is True
    assert report["shadow_outcomes"]["matched_action_choice_groups"] == 3
    assert report["model"]["allow_production_rank_feature"] is False
    validation = report["validation"]
    assert validation["metrics"][TRANSITION_ACTION_SCORER_V3_VERSION]["pass_at_1_count"] == 1
    assert validation["metrics"]["existing-rank-order"]["pass_at_1_count"] == 0
    assert TRANSITION_ACTION_SCORER_V2_VERSION in validation["metrics"]
    assert (
        validation["product_readiness"]["gate_result"]
        == GATE_READY_FOR_GUARDED_OPT_IN
    )
    assert validation["product_readiness"]["eligible_for_guarded_opt_in"] is True
    assert report["runtime"]["hosted_llm_api_calls"] == 0
    assert report["runtime"]["hosted_llm_prompt_tokens"] == 0
    assert report["runtime"]["hosted_llm_completion_tokens"] == 0
    assert report["runtime"]["hosted_repo_context_bytes"] == 0


def test_v3_shadow_scorer_gate_blocks_held_out_regression(tmp_path) -> None:
    candidate_outcomes = tmp_path / "candidate-outcomes.jsonl"
    advice = tmp_path / "advice.jsonl"
    rows = [
        *_candidate_pair(task="a_train", plan="plan-a", passing_rank=2),
        *_candidate_pair(task="b_train", plan="plan-b", passing_rank=2),
        *_candidate_pair(task="z_validation", plan="plan-z", passing_rank=1),
    ]
    _write_jsonl(candidate_outcomes, rows)
    _write_jsonl(
        advice,
        [
            _advice_row(task="a_train", plan="plan-a", scorer_top_rank=2),
            _advice_row(task="b_train", plan="plan-b", scorer_top_rank=2),
            _advice_row(task="z_validation", plan="plan-z", scorer_top_rank=2),
        ],
    )
    shadow_rows = normalize_transition_shadow_outcomes(
        advice_paths=[advice],
        candidate_outcome_paths=[candidate_outcomes],
    )
    groups = build_transition_action_choice_groups_jsonl(candidate_outcomes, embedding_dim=8)

    report = evaluate_transition_shadow_scorer_v3(
        groups,
        shadow_rows,
        split_by="order",
        validation_fraction=0.34,
        top_k=1,
        epochs=6,
    )

    readiness = report["validation"]["product_readiness"]
    assert readiness["gate_result"] == GATE_NOT_READY_UNDERPERFORMS
    assert readiness["eligible_for_guarded_opt_in"] is False
    assert "pass_at_1_under_existing_rank_order" in readiness["reasons"]
    assert report["validation"]["metrics"][TRANSITION_ACTION_SCORER_V3_VERSION][
        "pass_at_1_count"
    ] == 0
    assert report["validation"]["metrics"]["existing-rank-order"]["pass_at_1_count"] == 1


def test_evaluate_transition_shadow_scorer_cli_writes_json_report(
    capsys,
    tmp_path,
) -> None:
    candidate_outcomes = tmp_path / "candidate-outcomes.jsonl"
    advice = tmp_path / "advice.jsonl"
    shadow_outcomes = tmp_path / "shadow-outcomes.jsonl"
    report_path = tmp_path / "v3-report.json"
    rows = [
        *_candidate_pair(task="a_train", plan="plan-a", passing_rank=2),
        *_candidate_pair(task="b_train", plan="plan-b", passing_rank=2),
        *_candidate_pair(task="z_validation", plan="plan-z", passing_rank=2),
    ]
    _write_jsonl(candidate_outcomes, rows)
    _write_jsonl(
        advice,
        [
            _advice_row(task="a_train", plan="plan-a", scorer_top_rank=2),
            _advice_row(task="b_train", plan="plan-b", scorer_top_rank=2),
            _advice_row(task="z_validation", plan="plan-z", scorer_top_rank=2),
        ],
    )
    shadow_rows = normalize_transition_shadow_outcomes(
        advice_paths=[advice],
        candidate_outcome_paths=[candidate_outcomes],
    )
    write_transition_shadow_outcomes_jsonl(shadow_outcomes, shadow_rows)

    assert (
        main(
            [
                "evaluate-transition-shadow-scorer",
                "--shadow-outcomes",
                str(shadow_outcomes),
                "--candidate-outcomes",
                str(candidate_outcomes),
                "--split-by",
                "order",
                "--validation-fraction",
                "0.34",
                "--top-k",
                "1",
                "--embedding-dim",
                "8",
                "--epochs",
                "6",
                "--out",
                str(report_path),
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert output["schema_version"] == TRANSITION_ACTION_SCORER_V3_REPORT_VERSION
    assert written == output
    assert output["validation"]["product_readiness"]["baseline"] == "existing-rank-order"
    assert output["runtime"]["hosted_api_tokens"] == 0


def test_v3_production_rank_feature_is_explicit_ablation(tmp_path) -> None:
    candidate_outcomes = tmp_path / "candidate-outcomes.jsonl"
    advice = tmp_path / "advice.jsonl"
    rows = [
        *_candidate_pair(task="a_train", plan="plan-a", passing_rank=2),
        *_candidate_pair(task="b_train", plan="plan-b", passing_rank=2),
        *_candidate_pair(task="z_validation", plan="plan-z", passing_rank=2),
    ]
    _write_jsonl(candidate_outcomes, rows)
    _write_jsonl(
        advice,
        [
            _advice_row(task="a_train", plan="plan-a", scorer_top_rank=2),
            _advice_row(task="b_train", plan="plan-b", scorer_top_rank=2),
            _advice_row(task="z_validation", plan="plan-z", scorer_top_rank=2),
        ],
    )
    shadow_rows = normalize_transition_shadow_outcomes(
        advice_paths=[advice],
        candidate_outcome_paths=[candidate_outcomes],
    )
    groups = build_transition_action_choice_groups_jsonl(candidate_outcomes, embedding_dim=8)

    default_report = evaluate_transition_shadow_scorer_v3(
        groups,
        shadow_rows,
        split_by="order",
        validation_fraction=0.34,
        top_k=1,
        epochs=6,
    )
    ablation_report = evaluate_transition_shadow_scorer_v3(
        groups,
        shadow_rows,
        split_by="order",
        validation_fraction=0.34,
        top_k=1,
        epochs=6,
        allow_production_rank_feature=True,
    )

    assert default_report["parameters"]["allow_production_rank_feature"] is False
    assert default_report["model"]["allow_production_rank_feature"] is False
    assert ablation_report["parameters"]["allow_production_rank_feature"] is True
    assert ablation_report["model"]["allow_production_rank_feature"] is True


def _candidate_pair(
    *,
    task: str,
    plan: str,
    passing_rank: int,
) -> list[dict[str, object]]:
    return [
        _candidate_row(
            task=task,
            plan=plan,
            rank_index=1,
            operator="*",
            passed=passing_rank == 1,
            first_passing_index=passing_rank,
        ),
        _candidate_row(
            task=task,
            plan=plan,
            rank_index=2,
            operator="+",
            passed=passing_rank == 2,
            first_passing_index=passing_rank,
        ),
    ]


def _candidate_row(
    *,
    task: str,
    plan: str,
    rank_index: int,
    operator: str,
    passed: bool,
    first_passing_index: int,
) -> dict[str, object]:
    return {
        "task": task,
        "task_family": "operator_fix",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": plan,
        "file_path": "calculator.py",
        "action": "change_operator",
        "symbol": "add",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "BinOp",
        "params": {"to": operator},
        "reason": f"try {operator}",
        "model_score": 0.9 if rank_index == 1 else 0.1,
        "failure_hint_score": 0.9 if rank_index == 1 else 0.1,
        "ranker_score": 0.9 if rank_index == 1 else 0.1,
        "target_context": {"function_name": "add", "line_span": [2, 2]},
        "before_source": "def add(left, right):\n    return left - right\n",
        "patched_source": f"def add(left, right):\n    return left {operator} right\n",
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": first_passing_index,
        "is_first_pass": passed and rank_index == first_passing_index,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "assertions": [{"actual": 1, "expected": 3, "operator": "=="}],
                "function_names": ["add"],
            }
        ],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _advice_row(
    *,
    task: str,
    plan: str,
    scorer_top_rank: int,
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
        "repair_plan_id": plan,
        "repo_state_summary": {
            "repo": "/tmp/example-repo",
            "repo_name": "example-repo",
            "python_file_count": 1,
        },
        "repair_context": {
            "task": task,
            "task_family": "operator_fix",
            "source_type": "handcrafted",
            "split": "validation",
            "phase": "ranked",
            "test_command": "python -m pytest",
        },
        "candidate_count": 2,
        "existing_ranked_candidate_ranks": [1, 2],
        "scorer_ranked_candidate_ranks": [
            scorer_top_rank,
            2 if scorer_top_rank == 1 else 1,
        ],
        "existing_selected_candidate": _advice_candidate(rank=1, operator="*"),
        "scorer_top_candidate": _advice_candidate(
            rank=scorer_top_rank,
            operator="+" if scorer_top_rank == 2 else "*",
        ),
        "scorer_agreed_with_existing_rank_order": scorer_top_rank == 1,
        "scorer_agreed_with_existing_top_candidate": scorer_top_rank == 1,
        "validation_comparison": {
            "known": True,
            "would_have": "improved" if scorer_top_rank == 2 else "same",
        },
        "runtime": {"local_runtime_ms": 1.0, **usage},
        "usage": usage,
    }


def _advice_candidate(*, rank: int, operator: str) -> dict[str, object]:
    return {
        "id": f"candidate-{rank}",
        "rank_index": rank,
        "file_path": "calculator.py",
        "action": "change_operator",
        "symbol": "add",
        "params": {"to": operator},
        "validated": True,
        "passed": None,
        "reason": f"try {operator}",
    }


def _write_jsonl(path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
