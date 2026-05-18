from __future__ import annotations

import json
from pathlib import Path

from j3.real_repo_shadow_score import (
    format_real_repo_tests_only_shadow_score,
    run_real_repo_tests_only_shadow_score,
    write_real_repo_tests_only_shadow_report,
    write_real_repo_tests_only_shadow_score,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


def test_real_repo_tests_only_shadow_score_records_no_candidate_residuals() -> None:
    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
    )

    assert json.loads(json.dumps(score)) == score
    assert score["schema_version"] == "real-repo-tests-shadow-score-v1"
    assert score["record_kind"] == "real_repo_tests_only_shadow_score"
    assert score["zero_hosted_usage_confirmed"] is True

    metrics = score["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["tasks_scored"] == 4
    assert metrics["candidate_count"] == 0
    assert metrics["pass@1"] == "0/4"
    assert metrics["pass@3"] == "0/4"
    assert metrics["first_passing_ranks"] == [None, None, None, None]
    assert metrics["correct_test_location"] == "0/4"

    gate = score["gate_decision"]
    assert isinstance(gate, dict)
    assert gate["decision"] == "remain_shadow_only"
    assert gate["passed"] is False
    assert gate["guarded_opt_in_allowed"] is False

    rows = score["task_results"]
    assert isinstance(rows, list)
    assert {row["task_id"] for row in rows} == {
        "iniconfig-tests-parse-comments",
        "h11-tests-bytesify-memoryview",
        "humanize-tests-naturalsize-negative-strings",
        "boltons-tests-slugify-delimiter",
    }
    assert all(row["pass@1"] is False for row in rows)
    assert all(row["pass@3"] is False for row in rows)
    assert all(row["first_passing_rank"] is None for row in rows)
    assert all(row["hidden_like_agreement"] == "not_run" for row in rows)
    assert all(row["zero_hosted_usage_confirmed"] is True for row in rows)
    assert all(
        "unsupported_tests_only_action_slice" in row["residual_labels"]
        for row in rows
    )


def test_shadow_score_surfaces_slugify_overfit_location_mismatch() -> None:
    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
    )
    rows = score["task_results"]
    assert isinstance(rows, list)
    boltons = next(row for row in rows if row["repo_id"] == "boltons")

    mutation_scope = boltons["mutation_scope"]
    assert isinstance(mutation_scope, dict)
    assert mutation_scope["candidate_target_paths_considered"] == [
        "tests/test_slugify.py"
    ]
    assert mutation_scope["candidate_target_path_violations"] == [
        "tests/test_slugify.py"
    ]
    assert "wrong_test_location" in boltons["residual_labels"]
    assert "repo_state_planning_gap" in boltons["residual_labels"]


def test_shadow_score_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
    )

    score_path = write_real_repo_tests_only_shadow_score(
        score,
        tmp_path / "score.json",
    )
    report_path = write_real_repo_tests_only_shadow_report(
        score,
        tmp_path / "report.md",
    )

    assert json.loads(score_path.read_text(encoding="utf-8"))["metrics"]["pass@3"] == "0/4"
    report = report_path.read_text(encoding="utf-8")
    assert "REAL-003 Tests-Only Shadow Score" in report
    assert "pass@3: `0/4`" in report
    assert "remain_shadow_only" in report
    assert format_real_repo_tests_only_shadow_score(score) == report
