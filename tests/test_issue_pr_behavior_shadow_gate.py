from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.issue_pr_behavior_shadow_gate import (
    IssuePrBehaviorShadowGateError,
    build_issue_pr_behavior_shadow_gate,
    load_issue_pr_behavior_shadow_gate_policy_report,
    main,
    write_issue_pr_behavior_shadow_gate,
)
from j3.issue_pr_coverage_gap_policy import LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER


def test_val004_gate_blocks_strict_and_keeps_behavior_metrics_shadow_only() -> None:
    gate = build_issue_pr_behavior_shadow_gate(_policy_report())

    summary = gate["summary"]
    strict = summary["strict_ranking_readiness"]
    behavior = summary["behavior_negative_only_ranking_readiness"]
    stance = gate["production_gate_stance"]
    assert gate["record_kind"] == "issue_pr_behavior_negative_shadow_gate"
    assert gate["production_ranking_gate_changed"] is False
    assert strict == {
        "status": "blocked",
        "rankable_rows": 0,
        "blocked_rows": 2,
        "pass_at_1": None,
        "pass_at_k": None,
        "production_eligible": False,
    }
    assert behavior["status"] == "ranked_shadow_only"
    assert behavior["pass_at_1"] == 1.0
    assert behavior["pass_at_k"] == 1.0
    assert behavior["production_eligible"] is False
    assert "cannot change production ranking" in behavior["shadow_only_reason"]
    assert stance["decision"] == "remain_shadow_only"
    assert stance["strict_issue_pr_ranking"] == "blocked"
    assert stance["behavior_negative_only_ranking"] == "shadow_only"
    assert stance["production_ranking_allowed"] is False
    assert stance["behavior_negative_only_production_allowed"] is False
    assert stance["shadow_metrics_allowed"] is True


def test_val004_records_blocker_counts_leakage_and_runtime() -> None:
    gate = build_issue_pr_behavior_shadow_gate(_policy_report())

    summary = gate["summary"]
    assert summary["behavior_observable_negative_count"] == 6
    assert summary["product_blocker_count"] == 2
    assert summary["blocker_counts"] == {
        LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER: 2,
        "strict_denominator_contains_non_behavior_observable_decoys": 2,
    }
    assert summary["leakage_risk"] == {
        "behavior_negative_denominator": "low",
        "coverage_gap_classification": "blocked_high",
        "overall": "blocked_high",
        "separation_depends_on_decoy_labels": True,
        "blocker_reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
        "label_dependent_product_blocker_count": 2,
    }
    assert summary["input_runtime_seconds"] == 3.5
    assert isinstance(summary["runtime_seconds"], float)
    assert summary["production_gate_stance"]["reason"] == LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER


def test_val004_adds_label_dependent_blocker_when_row_summary_requires_it() -> None:
    report = _policy_report(include_label_blockers=False)

    gate = build_issue_pr_behavior_shadow_gate(report)

    summary = gate["summary"]
    assert (
        summary["blocker_counts"][LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER] == 2
    )
    assert summary["strict_ranking_readiness"]["status"] == "blocked"


def test_val004_writes_json_jsonl_and_markdown(tmp_path: Path) -> None:
    gate = build_issue_pr_behavior_shadow_gate(_policy_report())

    artifacts = write_issue_pr_behavior_shadow_gate(gate, out_dir=tmp_path / "out")

    assert json.loads(artifacts["gate_json"].read_text(encoding="utf-8"))[
        "task_id"
    ] == "VAL-004"
    row_lines = artifacts["rows_jsonl"].read_text(encoding="utf-8").splitlines()
    assert len(row_lines) == 2
    markdown = artifacts["gate_md"].read_text(encoding="utf-8")
    assert "VAL-004 Behavior-Negative Issue/PR Shadow Gate" in markdown
    assert "Production decision: remain_shadow_only" in markdown
    assert "Behavior-negative-only pass@1: 1.0" in markdown


def test_val004_cli_smoke_writes_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path = tmp_path / "val-003-policy-report.json"
    policy_path.write_text(
        json.dumps(_policy_report(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    result = main(
        [
            "--policy-report",
            str(policy_path),
            "--out-dir",
            str(tmp_path / "cli-out"),
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["gate_json"]).is_file()
    assert Path(output["rows_jsonl"]).is_file()
    assert Path(output["gate_md"]).is_file()


def test_val004_missing_policy_report_is_reported(tmp_path: Path) -> None:
    with pytest.raises(IssuePrBehaviorShadowGateError, match="policy report missing"):
        load_issue_pr_behavior_shadow_gate_policy_report(tmp_path / "missing.json")


def _policy_report(*, include_label_blockers: bool = True) -> dict[str, object]:
    return {
        "schema_version": "issue-pr-coverage-gap-policy-v1",
        "record_kind": "issue_pr_coverage_gap_policy_report",
        "task_id": "VAL-003",
        "summary": {
            "runtime_seconds": 1.0,
            "input_validation_runtime_seconds": 2.5,
        },
        "rows": [
            _policy_row(
                "scrapy__scrapy-issue-7293-pr-7351",
                behavior_negative_count=3,
                product_blocker_count=1,
                include_label_blockers=include_label_blockers,
            ),
            _policy_row(
                "pytest-dev__pytest-issue-14462-pr-14466",
                behavior_negative_count=3,
                product_blocker_count=1,
                include_label_blockers=include_label_blockers,
            ),
        ],
    }


def _policy_row(
    replay_id: str,
    *,
    behavior_negative_count: int,
    product_blocker_count: int,
    include_label_blockers: bool,
) -> dict[str, object]:
    blockers = [
        {
            "field": "strict_denominator",
            "reason": "strict_denominator_contains_non_behavior_observable_decoys",
            "count": product_blocker_count,
        }
    ]
    if include_label_blockers:
        blockers.append(
            {
                "field": "leakage",
                "reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
                "count": product_blocker_count,
            }
        )
    return {
        "replay_id": replay_id,
        "repo": replay_id.split("__", 1)[0].replace("__", "/"),
        "candidate_count": 5,
        "decoy_count": 4,
        "behavior_observable_negative_count": behavior_negative_count,
        "product_blocker_count": product_blocker_count,
        "label_dependent_product_blocker_count": product_blocker_count,
        "strict_ranking_readiness": {
            "status": "blocked",
            "rankable": False,
            "rankable_candidate_count": None,
            "first_accepted_rank": None,
            "pass_at_1": None,
            "pass_at_k": None,
            "k": None,
            "blockers": blockers,
        },
        "behavior_negative_only_ranking_readiness": {
            "status": "ranked_shadow_only",
            "rankable": True,
            "scope": "behavior_negative_only",
            "rankable_candidate_count": 4,
            "first_accepted_rank": 1,
            "pass_at_1": 1.0,
            "pass_at_k": 1.0,
            "k": 4,
            "blockers": [],
        },
    }
