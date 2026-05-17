from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.transition_action_choice import build_transition_action_choice_groups
from j3.transition_action_scoring import (
    GATE_NOT_READY_UNDERPERFORMS,
    GATE_READY_FOR_GUARDED_OPT_IN,
    GATE_READY_FOR_SHADOW_MODE,
    TRANSITION_ACTION_SCORER_VERSION,
    TRANSITION_ACTION_SCORING_EVAL_VERSION,
    TRANSITION_PRODUCT_READINESS_VERSION,
    evaluate_transition_product_readiness,
    evaluate_transition_action_choices,
    rank_transition_action_candidates,
    score_transition_action_candidate,
)


FIXTURES = Path(__file__).parent / "fixtures" / "transition_bench"


def test_future_scorer_evaluates_fixture_against_rank_order_baseline() -> None:
    groups = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )

    report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )

    assert report["schema_version"] == TRANSITION_ACTION_SCORING_EVAL_VERSION
    assert report["group_count"] == 1
    assert report["solved_group_count"] == 1
    assert report["candidate_count"] == 2
    assert report["runtime"]["hosted_llm_api_calls"] == 0
    assert report["runtime"]["hosted_llm_prompt_tokens"] == 0
    assert report["runtime"]["hosted_llm_completion_tokens"] == 0
    assert report["runtime"]["hosted_repo_context_bytes"] == 0

    scorer_metrics = report["metrics"][TRANSITION_ACTION_SCORER_VERSION]
    rank_order_metrics = report["metrics"]["existing-rank-order"]
    assert scorer_metrics["pass_at_1_count"] == 1
    assert scorer_metrics["pass_at_1_rate"] == 1.0
    assert scorer_metrics["pass_at_1_solved_rate"] == 1.0
    assert scorer_metrics["mean_reciprocal_rank"] == 1.0
    assert scorer_metrics["mean_reciprocal_rank_solved"] == 1.0
    assert scorer_metrics["average_first_passing_rank"] == 1.0
    assert scorer_metrics["average_candidates_validated_before_first_pass"] == 0.0
    assert scorer_metrics["average_candidates_saved_vs_existing_rank_order"] == 1.0
    assert scorer_metrics["residual_count"] == 0
    assert rank_order_metrics["pass_at_1_count"] == 0
    assert rank_order_metrics["mean_reciprocal_rank"] == 0.5
    assert report["residual_examples"] == []


def test_future_scorer_ranking_uses_local_non_label_features() -> None:
    group = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )[0]

    ranked = rank_transition_action_candidates(group)
    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]

    failed_score = score_transition_action_candidate(group["candidates"][0], group=group)
    passed_score = score_transition_action_candidate(group["candidates"][1], group=group)
    assert failed_score["features"]["ranker_score"] == pytest.approx(0.1)
    assert passed_score["features"]["ranker_score"] == pytest.approx(0.9)
    assert passed_score["features"]["candidate_after_embedding_available"] == 1.0
    assert passed_score["score"] > failed_score["score"]


def test_baseline_orders_are_stable_and_distinct() -> None:
    group = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )[0]

    existing = rank_transition_action_candidates(group, strategy="existing-rank-order")
    lexical = rank_transition_action_candidates(group, strategy="stable-lexical-order")
    random_once = rank_transition_action_candidates(
        group,
        strategy="deterministic-random-order",
    )
    random_twice = rank_transition_action_candidates(
        group,
        strategy="deterministic-random-order",
    )

    assert [candidate["rank_index"] for candidate in existing] == [1, 2]
    assert [candidate["rank_index"] for candidate in lexical] == [2, 1]
    assert [candidate["rank_index"] for candidate in random_once] == [
        candidate["rank_index"] for candidate in random_twice
    ]


def test_residual_examples_capture_wrong_top_action_choice() -> None:
    groups = build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=False,
                repair_plan_id="plan-wrong-top",
                params={"to": "*"},
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=True,
                repair_plan_id="plan-wrong-top",
                params={"to": "+"},
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
        ],
        embedding_dim=8,
    )

    report = evaluate_transition_action_choices(groups, top_k=2, residual_limit=1)

    scorer_metrics = report["metrics"][TRANSITION_ACTION_SCORER_VERSION]
    assert scorer_metrics["pass_at_1_count"] == 0
    assert scorer_metrics["top_k_pass_count"] == 1
    assert scorer_metrics["mean_reciprocal_rank"] == 0.5
    assert scorer_metrics["average_candidates_saved_vs_existing_rank_order"] == 0.0
    residual = report["residual_examples"][0]
    assert residual["group_id"] == groups[0]["id"]
    assert residual["grouping"] == groups[0]["grouping"]
    assert residual["selected_top_candidate"]["rank_index"] == 1
    assert residual["selected_top_candidate"]["params"] == {"to": "*"}
    assert residual["selected_top_candidate"]["passed"] is False
    assert residual["passing_candidate_ranks"] == [2]
    assert residual["first_pass_rank"] == 2
    assert residual["ranked_candidate_ranks"] == [1, 2]


def test_product_readiness_gate_allows_guarded_opt_in_only_after_strict_gain() -> None:
    groups = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )

    scoring_report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )
    readiness = evaluate_transition_product_readiness(scoring_report)

    assert readiness["schema_version"] == TRANSITION_PRODUCT_READINESS_VERSION
    assert readiness["gate_result"] == GATE_READY_FOR_GUARDED_OPT_IN
    assert readiness["eligible_for_shadow_mode"] is True
    assert readiness["eligible_for_guarded_opt_in"] is True
    assert readiness["comparison_scope"] == "solved_action_choice_groups"
    assert readiness["residual_count"] == 0
    assert readiness["metrics"]["pass_at_1"]["delta"] == 1.0
    assert readiness["metrics"]["top_k"]["delta"] == 1.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == 0.5
    assert (
        readiness["metrics"]["average_candidates_validated_before_first_pass"]["delta"]
        == -1.0
    )


def test_product_readiness_gate_rejects_scorer_under_existing_rank_order() -> None:
    groups = build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=True,
                repair_plan_id="plan-regression",
                params={"to": "+"},
                first_passing_index=1,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=False,
                repair_plan_id="plan-regression",
                params={"to": "*"},
                first_passing_index=1,
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
        ],
        embedding_dim=8,
    )

    scoring_report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )
    readiness = evaluate_transition_product_readiness(scoring_report)

    assert readiness["gate_result"] == GATE_NOT_READY_UNDERPERFORMS
    assert readiness["eligible_for_shadow_mode"] is False
    assert readiness["eligible_for_guarded_opt_in"] is False
    assert readiness["residual_count"] == 1
    assert readiness["metrics"]["pass_at_1"]["delta"] == -1.0
    assert readiness["metrics"]["top_k"]["delta"] == -1.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == -0.5
    assert "pass_at_1_under_existing_rank_order" in readiness["reasons"]
    assert "mrr_under_existing_rank_order" in readiness["reasons"]


def test_product_readiness_gate_uses_shadow_mode_for_non_regressing_scorer() -> None:
    groups = build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=True,
                repair_plan_id="plan-equal",
                params={"to": "+"},
                first_passing_index=1,
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=False,
                repair_plan_id="plan-equal",
                params={"to": "*"},
                first_passing_index=1,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
        ],
        embedding_dim=8,
    )

    scoring_report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )
    readiness = evaluate_transition_product_readiness(scoring_report)

    assert readiness["gate_result"] == GATE_READY_FOR_SHADOW_MODE
    assert readiness["eligible_for_shadow_mode"] is True
    assert readiness["eligible_for_guarded_opt_in"] is False
    assert readiness["residual_count"] == 0
    assert readiness["metrics"]["pass_at_1"]["delta"] == 0.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == 0.0
    assert readiness["reasons"] == []


def test_evaluator_rejects_invalid_arguments() -> None:
    groups = build_transition_action_choice_groups(_fixture_candidate_rows(), embedding_dim=8)

    with pytest.raises(ValueError, match="top_k must be >= 1"):
        evaluate_transition_action_choices(groups, top_k=0)
    with pytest.raises(ValueError, match="residual_limit must be >= 0"):
        evaluate_transition_action_choices(groups, residual_limit=-1)
    with pytest.raises(ValueError, match="unknown transition action scoring strategy"):
        rank_transition_action_candidates(groups[0], strategy="missing")


def _fixture_candidate_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in (FIXTURES / "candidate_outcomes.jsonl").read_text(encoding="utf-8").splitlines():
        if not row:
            continue
        # eval keeps source text local so source/after embedding features can be tested.
        parsed = json.loads(row)
        parsed["before_source"] = "def add(left, right):\n    return left - right\n"
        parsed["patched_source"] = (
            "def add(left, right):\n    return left + right\n"
            if parsed["passed"]
            else "def add(left, right):\n    return left - right\n"
        )
        rows.append(parsed)
    return rows


def _candidate_row(
    *,
    rank_index: int,
    passed: bool,
    repair_plan_id: str,
    params: dict[str, object],
    first_passing_index: int = 2,
    model_score: float,
    ranker_score: float,
    failure_hint_score: float,
    patched_source: str,
) -> dict[str, object]:
    return {
        "task": "calculator_add",
        "task_family": "operator_fix",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": repair_plan_id,
        "file_path": "calculator.py",
        "action": "change_operator",
        "symbol": "add",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "BinOp",
        "params": params,
        "reason": "try operator",
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": ranker_score,
        "target_context": {"function_name": "add", "line_span": [2, 2]},
        "before_source": "def add(left, right):\n    return left - right\n",
        "patched_source": patched_source,
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
