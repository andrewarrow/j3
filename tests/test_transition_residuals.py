from __future__ import annotations

import json

from cli import main
from j3.transition_action_choice import build_transition_action_choice_groups_jsonl
from j3.transition_action_scoring import evaluate_transition_shadow_scorer_v3
from j3.transition_residuals import (
    TRANSITION_RESIDUAL_REPORT_VERSION,
    report_transition_residuals,
)
from j3.transition_shadow_outcomes import (
    normalize_transition_shadow_outcomes,
    write_transition_shadow_outcomes_jsonl,
)


def test_transition_residual_report_groups_ranking_and_generation_gaps(tmp_path) -> None:
    candidate_outcomes, shadow_outcomes, v3_report = _write_residual_inputs(tmp_path)

    report = report_transition_residuals(
        shadow_outcome_paths=[shadow_outcomes],
        shadow_scorer_report_path=v3_report,
        candidate_outcome_paths=[candidate_outcomes],
        embedding_dim=8,
        example_limit=3,
    )

    assert report["schema_version"] == TRANSITION_RESIDUAL_REPORT_VERSION
    assert report["summary"]["failure_count"] >= 2
    assert report["summary"]["gap_types"]["candidate_generation_gap"] == 1
    assert report["summary"]["gap_types"]["scorer_ranking_gap"] >= 1
    assert {"value": "operator_fix", "count": report["summary"]["failure_count"]} in report[
        "groups"
    ]["task_family"]
    assert {"value": "change_operator", "count": report["summary"]["failure_count"]} in report[
        "groups"
    ]["action_kind"]
    assert any(
        item["value"] == "calculator.py"
        for item in report["groups"]["source_file"]
    )
    assert any(
        item["value"] == "candidate_after_embedding_unavailable"
        for item in report["groups"]["missing_feature_evidence"]
    )
    examples = report["examples"]
    assert examples
    assert examples[0]["exact_candidate_summaries"][0]["params"] == {"to": "*"}
    assert examples[0]["production_candidate"]["rank_index"] == 1
    assert report["usage"]["hosted_llm_api_calls"] == 0
    assert report["runtime"]["hosted_repo_context_bytes"] == 0


def test_report_transition_residuals_cli_prints_json(capsys, tmp_path) -> None:
    candidate_outcomes, shadow_outcomes, v3_report = _write_residual_inputs(tmp_path)

    assert (
        main(
            [
                "report-transition-residuals",
                "--shadow-outcomes",
                str(shadow_outcomes),
                "--shadow-scorer-report",
                str(v3_report),
                "--candidate-outcomes",
                str(candidate_outcomes),
                "--embedding-dim",
                "8",
                "--example-limit",
                "2",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == TRANSITION_RESIDUAL_REPORT_VERSION
    assert output["summary"]["failure_count"] >= 2
    assert output["shadow_scorer"]["available"] is True
    assert output["runtime"]["hosted_api_tokens"] == 0


def _write_residual_inputs(tmp_path):
    candidate_outcomes = tmp_path / "candidate-outcomes.jsonl"
    advice = tmp_path / "advice.jsonl"
    shadow_outcomes = tmp_path / "shadow-outcomes.jsonl"
    v3_report = tmp_path / "v3-report.json"
    rows = [
        *_candidate_pair(task="a_train", plan="plan-a", passing_rank=1),
        *_candidate_pair(task="b_train", plan="plan-b", passing_rank=1),
        *_candidate_pair(task="z_validation", plan="plan-z", passing_rank=2),
        *_candidate_pair(task="zz_generation", plan="plan-g", passing_rank=None),
    ]
    _write_jsonl(candidate_outcomes, rows)
    _write_jsonl(
        advice,
        [
            _advice_row(task="a_train", plan="plan-a", scorer_top_rank=1),
            _advice_row(task="b_train", plan="plan-b", scorer_top_rank=1),
            _advice_row(task="z_validation", plan="plan-z", scorer_top_rank=1),
            _advice_row(task="zz_generation", plan="plan-g", scorer_top_rank=1),
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
        validation_fraction=0.5,
        top_k=1,
        epochs=6,
    )
    v3_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return candidate_outcomes, shadow_outcomes, v3_report


def _candidate_pair(
    *,
    task: str,
    plan: str,
    passing_rank: int | None,
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
    first_passing_index: int | None,
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
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": first_passing_index,
        "is_first_pass": passed and rank_index == first_passing_index,
        "passing_candidates": 1 if first_passing_index is not None else 0,
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
            "would_have": "same" if scorer_top_rank == 1 else "improved",
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
