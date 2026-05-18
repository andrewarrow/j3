from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.issue_pr_candidate_ranking import (
    IssuePrCandidateRankingError,
    build_issue_pr_candidate_ranking_report,
    main,
    write_issue_pr_candidate_ranking_report,
)


def test_build_shadow_report_blocks_instead_of_forcing_issue_pr_ranking(tmp_path: Path) -> None:
    pytest_path = _write_candidate(tmp_path, "pytest")
    scrapy_path = _write_candidate(tmp_path, "scrapy")

    report = build_issue_pr_candidate_ranking_report(
        pytest_candidate_path=pytest_path,
        scrapy_candidate_path=scrapy_path,
    )

    assert report["mode"] == "shadow_only"
    assert report["production_ranking_gate_changed"] is False
    assert report["hosted_llm_usage"] == {
        "used": False,
        "zero_hosted_usage_confirmed": True,
    }
    assert report["summary"]["rows"] == 2
    assert report["summary"]["rankable_rows"] == 0
    assert report["summary"]["pass_at_1"] is None
    assert report["summary"]["pass_at_k"] is None
    assert report["summary"]["scorer_status"] == "blocked_current_inputs"

    for row in report["rows"]:
        assert row["candidate_count"] >= 4
        assert row["decoy_count"] >= 3
        assert row["pass_at_1"] is None
        assert row["pass_at_k"] is None
        assert row["first_accepted_rank"] is None
        assert row["scorer_status"] == "blocked_current_inputs"
        reasons = {blocker["reason"] for blocker in row["scorer_blockers"]}
        assert "no_guarded_issue_pr_ranker" in reasons
        assert "issue_specific_semantics_not_in_current_features" in reasons
        accepted = [candidate for candidate in row["candidates"] if candidate["expected_accepted"]]
        assert len(accepted) == 1


def test_decoys_cover_known_pytest_and_scrapy_hard_mistakes(tmp_path: Path) -> None:
    report = build_issue_pr_candidate_ranking_report(
        pytest_candidate_path=_write_candidate(tmp_path, "pytest"),
        scrapy_candidate_path=_write_candidate(tmp_path, "scrapy"),
    )
    rows = {row["replay_id"]: row for row in report["rows"]}

    pytest_mistakes = _mistakes(rows["pytest-dev__pytest-issue-14462-pr-14466"])
    assert "incomplete_timedelta_relative_tolerance_semantics" in pytest_mistakes
    assert "missing_test_coverage" in pytest_mistakes
    assert "incomplete_source_test_materialization" in pytest_mistakes

    scrapy_mistakes = _mistakes(rows["scrapy__scrapy-issue-7293-pr-7351"])
    assert "stale_min_stats_selection" in scrapy_mistakes
    assert "mutating_peek" in scrapy_mistakes
    assert "missing_last_selected_slot" in scrapy_mistakes
    assert "missing_tests" in scrapy_mistakes


def test_report_exposes_diff_ast_and_candidate_after_feature_availability(tmp_path: Path) -> None:
    report = build_issue_pr_candidate_ranking_report(
        pytest_candidate_path=_write_candidate(tmp_path, "pytest"),
        scrapy_candidate_path=_write_candidate(tmp_path, "scrapy"),
    )

    for row in report["rows"]:
        accepted = next(candidate for candidate in row["candidates"] if candidate["expected_accepted"])
        inputs = accepted["feature_inputs"]
        assert inputs["diff_summary_available"] is True
        assert inputs["ast_delta_available"] is True
        assert inputs["candidate_after_available"] is False
        assert inputs["validation_available"] is True
        assert inputs["feature_count"] > 0
        assert isinstance(inputs["feature_sample"], list)


def test_write_report_outputs_json_jsonl_and_markdown(tmp_path: Path) -> None:
    report = build_issue_pr_candidate_ranking_report(
        pytest_candidate_path=_write_candidate(tmp_path, "pytest"),
        scrapy_candidate_path=_write_candidate(tmp_path, "scrapy"),
    )

    artifacts = write_issue_pr_candidate_ranking_report(report, out_dir=tmp_path / "out")

    assert json.loads(artifacts["report_json"].read_text(encoding="utf-8"))["schema_version"]
    jsonl_lines = artifacts["candidates_jsonl"].read_text(encoding="utf-8").splitlines()
    assert len(jsonl_lines) == 10
    assert all(json.loads(line)["candidate_id"] for line in jsonl_lines)
    markdown = artifacts["report_md"].read_text(encoding="utf-8")
    assert "DATA-037 Issue/PR Ranking Decoy Harness" in markdown
    assert "blocked_current_inputs" in markdown


def test_cli_smoke_writes_shadow_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = main(
        [
            "--pytest-candidate",
            str(_write_candidate(tmp_path, "pytest")),
            "--scrapy-candidate",
            str(_write_candidate(tmp_path, "scrapy")),
            "--out-dir",
            str(tmp_path / "cli-out"),
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["report_json"]).is_file()
    assert Path(output["candidates_jsonl"]).is_file()
    assert Path(output["report_md"]).is_file()


def test_missing_candidate_artifact_is_reported(tmp_path: Path) -> None:
    with pytest.raises(IssuePrCandidateRankingError, match="candidate artifact missing"):
        build_issue_pr_candidate_ranking_report(
            pytest_candidate_path=tmp_path / "missing-pytest.json",
            scrapy_candidate_path=_write_candidate(tmp_path, "scrapy"),
        )


def _mistakes(row: dict[str, object]) -> set[str]:
    mistakes: set[str] = set()
    for candidate in row["candidates"]:
        mistakes.update(candidate["targeted_mistakes"])
    return mistakes


def _write_candidate(tmp_path: Path, kind: str) -> Path:
    record = _candidate_record(kind)
    path = tmp_path / f"{kind}-candidate.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _candidate_record(kind: str) -> dict[str, object]:
    if kind == "pytest":
        replay_id = "pytest-dev__pytest-issue-14462-pr-14466"
        repo = "pytest-dev/pytest"
        candidate_id = "pytest-timedelta-approx-source-test"
        action_family = "pytest_timedelta_approx_source_test_candidate"
        source_path = "src/_pytest/python_api.py"
        test_path = "testing/python/approx.py"
    elif kind == "scrapy":
        replay_id = "scrapy__scrapy-issue-7293-pr-7351"
        repo = "scrapy/scrapy"
        candidate_id = "scrapy-downloader-aware-source-test"
        action_family = "scrapy_downloader_aware_slot_rotation_source_test_candidate"
        source_path = "scrapy/pqueues.py"
        test_path = "tests/test_pqueues.py"
    else:
        raise AssertionError(kind)

    return {
        "schema_version": "issue-pr-candidate-attempt-v1",
        "record_kind": "issue_pr_candidate_attempt",
        "candidate_id": candidate_id,
        "replay_id": replay_id,
        "repo": repo,
        "repo_before_ref": "abc123",
        "prompt": "real issue prompt",
        "status": "candidate_validation_passed",
        "action_family": action_family,
        "allowed_write_paths": [source_path, test_path],
        "candidate_diff": {
            "changed_files": [source_path, test_path],
            "diff_summary": {
                "added_line_count": 10,
                "removed_line_count": 2,
                "changed_line_count": 12,
                "hunk_count": 2,
            },
        },
        "source_materialization": {
            "status": "materialized",
            "target_source_file": source_path,
            "diff_summary": {
                "added_line_count": 6,
                "removed_line_count": 2,
                "changed_line_count": 8,
                "hunk_count": 1,
            },
            "ast_delta": {
                "ast_parse_ok": True,
                "ast_delta_added_count": 4,
                "ast_delta_removed_count": 1,
                "ast_delta_net_count": 3,
                "ast_delta_added_features": {"node:If": 1, "node:Call": 1},
                "ast_delta_removed_features": {"call:min": 1},
            },
        },
        "test_materialization": {
            "status": "materialized",
            "target_test_file": test_path,
            "diff_summary": {
                "added_line_count": 4,
                "removed_line_count": 0,
                "changed_line_count": 4,
                "hunk_count": 1,
            },
            "metadata": {"target_class": "ExampleTests"},
        },
        "validation": {
            "status": "passed",
            "validation_command": "pytest focused -q",
        },
        "residual_labels": ["candidate_validation_passed"],
        "zero_hosted_usage_confirmed": True,
    }
