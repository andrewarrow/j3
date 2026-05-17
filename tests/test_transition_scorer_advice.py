from __future__ import annotations

import json

from j3.transition_scorer_advice import (
    format_transition_scorer_advice_summary,
    summarize_transition_scorer_advice,
)


def test_summarize_transition_scorer_advice_reports_shadow_metrics(tmp_path) -> None:
    advice = tmp_path / "transition-advice.jsonl"
    rows = [
        _advice_row(
            candidate_count=3,
            selected={"id": "candidate-2", "rank_index": 2, "validated": True, "passed": True},
            scorer_top={
                "id": "candidate-1",
                "rank_index": 1,
                "validated": True,
                "passed": False,
            },
            comparison={
                "known": True,
                "would_have": "regressed",
                "existing_first_passing_index": 2,
                "scorer_first_known_passing_position": 3,
            },
        ),
        _advice_row(
            candidate_count=2,
            selected={"id": "candidate-a", "rank_index": 1, "validated": True, "passed": True},
            scorer_top={
                "id": "candidate-a",
                "rank_index": 1,
                "validated": True,
                "passed": True,
            },
            comparison={
                "known": True,
                "would_have": "same",
                "existing_first_passing_index": 1,
                "scorer_first_known_passing_position": 1,
            },
        ),
        _advice_row(
            candidate_count=4,
            selected={"id": "candidate-z", "rank_index": 3, "validated": True, "passed": True},
            scorer_top={
                "id": "candidate-y",
                "rank_index": 2,
                "validated": True,
                "passed": True,
            },
            comparison={
                "known": True,
                "would_have": "improved",
                "existing_first_passing_index": 3,
                "scorer_first_known_passing_position": 1,
            },
        ),
    ]
    advice.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    summary = summarize_transition_scorer_advice([advice])
    record = summary.as_dict()

    assert record["schema_version"] == "transition-scorer-advice-summary-v1"
    assert record["advice_paths"] == [str(advice.resolve())]
    assert record["advice_row_count"] == 3
    assert record["candidate_count"] == 9
    assert record["scorer_production_agreement"] == {
        "count": 1,
        "total": 3,
        "rate": 0.333333,
    }
    assert record["known_validation"] == {
        "row_count": 3,
        "improved_count": 1,
        "regressed_count": 1,
        "no_change_count": 1,
        "production_pass_at_1_count": 3,
        "production_pass_at_1_rate": 1.0,
        "scorer_pass_at_1_count": 2,
        "scorer_pass_at_1_rate": 0.666667,
        "average_candidates_saved_or_lost": 0.333333,
    }
    assert record["runtime"]["hosted_llm_api_calls"] == 0
    assert record["usage"]["hosted_llm_prompt_tokens"] == 0
    assert record["usage"]["hosted_repo_context_bytes"] == 0

    output = format_transition_scorer_advice_summary(summary)
    assert "j3 summarize-transition-advice" in output
    assert "advice rows: 3" in output
    assert "candidates: 9" in output
    assert "scorer/production agreement: 1/3 (33.33%)" in output
    assert "known validation: improved=1 regressed=1 no_change=1" in output
    assert "production-selected pass@1: 3/3 (100.00%)" in output
    assert "scorer-top pass@1: 2/3 (66.67%)" in output
    assert "average candidates saved/lost: 0.33" in output
    assert "hosted_llm_api_calls: 0" in output
    assert "hosted_repo_context_bytes: 0" in output


def _advice_row(
    *,
    candidate_count: int,
    selected: dict[str, object],
    scorer_top: dict[str, object],
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
        "candidate_count": candidate_count,
        "existing_selected_candidate": selected,
        "scorer_top_candidate": scorer_top,
        "validation_comparison": comparison,
        "runtime": {"local_runtime_ms": 1.5, **usage},
        "usage": usage,
    }
