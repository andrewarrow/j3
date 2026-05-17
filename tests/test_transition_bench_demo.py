from __future__ import annotations

import json
from pathlib import Path

from j3.transition_action_scoring import (
    GATE_READY_FOR_GUARDED_OPT_IN,
    TRANSITION_ACTION_SCORER_VERSION,
)
from j3.transition_bench_demo import (
    TRANSITION_BENCH_DEMO_REPORT_VERSION,
    format_transition_bench_demo_report,
    run_transition_bench_demo,
)


FIXTURES = Path("examples/transition_bench")


def test_transition_bench_demo_runs_from_checked_in_fixtures(tmp_path: Path) -> None:
    out = tmp_path / "transition-bench-report.json"

    report = run_transition_bench_demo(
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
        top_k=1,
        embedding_dim=8,
        out=out,
    )

    assert report["schema_version"] == TRANSITION_BENCH_DEMO_REPORT_VERSION
    assert report["decision"] == "evaluation_only_not_wired_to_production"
    assert report["uses_checked_in_fixtures"] is True
    assert report["report"] == str(out.resolve())
    assert report["asset_inventory"]["totals"]["prompt_corpus_rows"] == 2
    assert report["transition_bench"]["row_count"] == 4
    assert report["transition_bench"]["source_counts"] == {
        "candidate_outcome": 2,
        "mined_git_transition": 1,
        "prompt_repo_transition": 1,
    }
    assert report["transition_bench"]["normalized_source_counts"] == {
        "candidate_outcome": 2,
        "mined_git_transition": 1,
        "prompt_repo_transition": 1,
    }
    assert report["transition_bench"]["skipped_row_count"] == 0
    assert report["transition_bench"]["skipped_source_counts"] == {}
    assert report["transition_bench"]["skipped_rows"] == []
    assert report["action_choices"]["group_count"] == 1
    assert report["action_choices"]["candidate_count"] == 2
    assert report["action_choices"]["solved_group_count"] == 1
    assert report["runtime"]["hosted_llm_api_calls"] == 0
    assert report["runtime"]["hosted_llm_prompt_tokens"] == 0
    assert report["runtime"]["hosted_llm_completion_tokens"] == 0
    assert report["runtime"]["hosted_repo_context_bytes"] == 0

    scoring = report["action_scoring"]
    assert scoring["group_count"] == 1
    assert scoring["candidate_count"] == 2
    assert scoring["runtime"]["hosted_repo_context_bytes"] == 0
    scorer_metrics = scoring["metrics"][TRANSITION_ACTION_SCORER_VERSION]
    baseline_metrics = scoring["metrics"]["existing-rank-order"]
    assert scorer_metrics["pass_at_1_rate"] == 1.0
    assert scorer_metrics["top_k_pass_rate"] == 1.0
    assert scorer_metrics["mean_reciprocal_rank"] == 1.0
    assert baseline_metrics["pass_at_1_rate"] == 0.0
    assert baseline_metrics["mean_reciprocal_rank"] == 0.5
    readiness = report["product_readiness"]
    assert readiness["gate_result"] == GATE_READY_FOR_GUARDED_OPT_IN
    assert readiness["comparison_scope"] == "solved_action_choice_groups"
    assert readiness["eligible_for_shadow_mode"] is True
    assert readiness["eligible_for_guarded_opt_in"] is True
    assert readiness["metrics"]["pass_at_1"]["delta"] == 1.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == 0.5
    assert readiness["residual_count"] == 0
    assert json.loads(out.read_text(encoding="utf-8")) == report


def test_transition_bench_demo_accepts_explicit_candidate_outcomes_only() -> None:
    report = run_transition_bench_demo(
        candidate_outcomes=[FIXTURES / "candidate_outcomes.jsonl"],
        include_fixtures=False,
        top_k=2,
        embedding_dim=8,
    )

    assert report["uses_checked_in_fixtures"] is False
    assert report["sources"]["prompt_repo_transition_files"] == []
    assert report["sources"]["mined_git_transition_files"] == []
    assert report["sources"]["candidate_outcome_files"][0]["rows"] == 2
    assert report["transition_bench"]["row_count"] == 2
    assert report["action_scoring"]["top_k"] == 2


def test_transition_bench_demo_reports_skipped_empty_mined_sources(
    tmp_path: Path,
) -> None:
    mined = tmp_path / "mined.jsonl"
    invalid_commit = "2222222222222222222222222222222222222222"
    mined.write_text(
        "\n".join(
            json.dumps(row, sort_keys=True)
            for row in [
                {
                    "kind": "git_transition",
                    "repo": "demo",
                    "commit": "1111111111111111111111111111111111111111",
                    "parent": "0000000000000000000000000000000000000000",
                    "file_path": "calculator.py",
                    "before_source": "def add(left, right):\n    return left - right\n",
                    "after_source": "def add(left, right):\n    return left + right\n",
                },
                {
                    "kind": "git_transition",
                    "repo": "demo",
                    "commit": invalid_commit,
                    "parent": "1111111111111111111111111111111111111111",
                    "file_path": "calculator.py",
                    "before_source": "def add(left, right):\n    return left - right\n",
                    "after_source": "",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_transition_bench_demo(
        repo_root=tmp_path,
        mined_transitions=[mined],
        candidate_outcomes=[FIXTURES / "candidate_outcomes.jsonl"],
        include_fixtures=False,
        top_k=1,
        embedding_dim=8,
    )

    assert report["transition_bench"]["row_count"] == 3
    assert report["transition_bench"]["input_source_counts"] == {
        "candidate_outcome": 2,
        "mined_git_transition": 2,
    }
    assert report["transition_bench"]["normalized_source_counts"] == {
        "candidate_outcome": 2,
        "mined_git_transition": 1,
    }
    assert report["transition_bench"]["skipped_row_count"] == 1
    assert report["transition_bench"]["skipped_source_counts"] == {
        "mined_git_transition": 1,
    }
    assert report["transition_bench"]["skipped_rows"] == [
        {
            "source_kind": "mined_git_transition",
            "source_path": str(mined.resolve()),
            "row_index": 2,
            "reason": "empty_after_source",
            "repo": "demo",
            "file_path": "calculator.py",
            "commit": invalid_commit,
        }
    ]


def test_transition_bench_demo_human_output_mentions_core_metrics() -> None:
    report = run_transition_bench_demo(top_k=1, embedding_dim=8)

    output = format_transition_bench_demo_report(report)

    assert "j3 demo-transition-bench complete" in output
    assert "skipped source rows: 0" in output
    assert "groups: 1" in output
    assert "candidates: 2" in output
    assert f"{TRANSITION_ACTION_SCORER_VERSION}: pass@1=1/1" in output
    assert "existing-rank-order: pass@1=0/1" in output
    assert "top-k=" in output
    assert "mrr=" in output
    assert f"product gate: {GATE_READY_FOR_GUARDED_OPT_IN} residuals=0" in output
    assert "local runtime ms:" in output
    assert "hosted_llm_prompt_tokens: 0" in output
    assert "hosted_repo_context_bytes: 0" in output
