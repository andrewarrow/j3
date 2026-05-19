from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.issue_pr_coverage_gap_policy import (
    COVERAGE_GAP_LABEL_LEAKAGE_BLOCKER,
    LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
    IssuePrCoverageGapPolicyError,
    build_coverage_gap_policy_report,
    main,
    write_coverage_gap_policy_report,
)


PYTEST_REPLAY_ID = "pytest-dev__pytest-issue-14462-pr-14466"
SCRAPY_REPLAY_ID = "scrapy__scrapy-issue-7293-pr-7351"


def test_val003_blocks_strict_but_ranks_behavior_negative_denominator(
    tmp_path: Path,
) -> None:
    inputs = _write_policy_inputs(tmp_path)

    report = build_coverage_gap_policy_report(**inputs)

    summary = report["summary"]
    assert report["mode"] == "shadow_only_coverage_gap_policy_probe"
    assert report["production_ranking_gate_changed"] is False
    assert summary["behavior_observable_negative_count"] == 6
    assert summary["product_blocker_count"] == 2
    assert summary["strict_ranking_readiness"] == {
        "status": "blocked",
        "rankable_rows": 0,
        "blocked_rows": 2,
        "pass_at_1": None,
        "pass_at_k": None,
    }
    assert summary["behavior_negative_only_ranking_readiness"] == {
        "status": "ranked_shadow_only",
        "rankable_rows": 2,
        "blocked_rows": 0,
        "pass_at_1": 1.0,
        "pass_at_k": 1.0,
    }

    rows = {row["replay_id"]: row for row in report["rows"]}
    for row in rows.values():
        behavior = row["behavior_negative_only_ranking_readiness"]
        assert behavior["first_accepted_rank"] == 1
        assert behavior["pass_at_1"] == 1.0
        assert behavior["pass_at_k"] == 1.0
        assert all(
            "expected_accepted" not in candidate["score_inputs"]
            for candidate in behavior["ranked_candidates"]
        )

    scrapy_decoys = {
        decoy["decoy_id"]: decoy
        for decoy in rows[SCRAPY_REPLAY_ID]["decoy_policy_records"]
    }
    assert (
        scrapy_decoys["scrapy_mutating_peek"]["policy_class"]
        == "behavior_observable_hard_negative"
    )
    assert scrapy_decoys["scrapy_mutating_peek"]["observable_evidence"] == [
        "val_002_label_safe_behavior_probe_failed"
    ]


def test_val003_records_label_dependency_for_coverage_gap_claims(
    tmp_path: Path,
) -> None:
    inputs = _write_policy_inputs(tmp_path)

    report = build_coverage_gap_policy_report(**inputs)

    summary = report["summary"]
    assert summary["leakage_risk"] == {
        "behavior_negative_denominator": "low",
        "coverage_gap_classification": "blocked_high",
        "overall": "blocked_high",
        "separation_depends_on_decoy_labels": True,
        "blocker_reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
        "label_dependent_product_blocker_count": 2,
    }
    assert (
        summary["blocker_counts"][LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER] == 2
    )

    coverage_gap_decoys = [
        decoy
        for row in report["rows"]
        for decoy in row["decoy_policy_records"]
        if decoy["policy_class"] == "coverage_gap_product_blocker"
    ]
    assert {decoy["decoy_id"] for decoy in coverage_gap_decoys} == {
        "scrapy_missing_tests",
        "pytest_missing_invalid_tolerance_tests",
    }
    assert all(
        decoy["coverage_gap_claim_depends_on_decoy_labels"] is True
        for decoy in coverage_gap_decoys
    )
    assert all(
        decoy["blocker_reason"] == LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER
        for decoy in coverage_gap_decoys
    )


def test_val003_unprobed_passing_decoy_blocks_behavior_negative_metrics(
    tmp_path: Path,
) -> None:
    inputs = _write_policy_inputs(tmp_path, include_pytest_strength=False)

    report = build_coverage_gap_policy_report(**inputs)

    summary = report["summary"]
    assert summary["behavior_negative_only_ranking_readiness"]["status"] == "blocked"
    assert summary["behavior_negative_only_ranking_readiness"]["rankable_rows"] == 1
    assert (
        summary["blocker_counts"]["behavior_negative_denominator_contains_unresolved_decoys"]
        == 1
    )
    rows = {row["replay_id"]: row for row in report["rows"]}
    pytest_row = rows[PYTEST_REPLAY_ID]
    assert pytest_row["behavior_negative_only_ranking_readiness"]["status"] == "blocked"
    unresolved = [
        decoy
        for decoy in pytest_row["decoy_policy_records"]
        if decoy["policy_class"] == "unresolved_non_negative_decoy"
    ]
    assert [decoy["decoy_id"] for decoy in unresolved] == [
        "pytest_missing_invalid_tolerance_tests"
    ]


def test_val003_writes_json_jsonl_and_markdown(tmp_path: Path) -> None:
    report = build_coverage_gap_policy_report(**_write_policy_inputs(tmp_path))

    artifacts = write_coverage_gap_policy_report(report, out_dir=tmp_path / "out")

    assert json.loads(artifacts["report_json"].read_text(encoding="utf-8"))[
        "task_id"
    ] == "VAL-003"
    decoy_lines = artifacts["decoys_jsonl"].read_text(encoding="utf-8").splitlines()
    assert len(decoy_lines) == 8
    markdown = artifacts["report_md"].read_text(encoding="utf-8")
    assert "VAL-003 Coverage-Gap Decoy Policy Probe" in markdown
    assert "Behavior-negative-only pass@1: 1.0" in markdown
    assert LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER in markdown


def test_val003_cli_smoke_writes_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = _write_policy_inputs(tmp_path)

    result = main(
        [
            "--pytest-candidate",
            str(inputs["pytest_candidate_path"]),
            "--scrapy-candidate",
            str(inputs["scrapy_candidate_path"]),
            "--candidate-after-bundle",
            str(inputs["candidate_after_bundle_path"]),
            "--validation-strength-report",
            str(inputs["validation_strength_report_path"]),
            "--decoy-validation-bundle",
            str(inputs["decoy_validation_bundle_paths"][0]),
            "--decoy-validation-bundle",
            str(inputs["decoy_validation_bundle_paths"][1]),
            "--out-dir",
            str(tmp_path / "cli-out"),
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert Path(output["report_json"]).is_file()
    assert Path(output["decoys_jsonl"]).is_file()
    assert Path(output["report_md"]).is_file()


def test_val003_missing_strength_artifact_is_reported(tmp_path: Path) -> None:
    inputs = _write_policy_inputs(tmp_path)
    inputs["validation_strength_report_path"] = tmp_path / "missing-val-002.json"

    with pytest.raises(IssuePrCoverageGapPolicyError, match="input artifact missing"):
        build_coverage_gap_policy_report(**inputs)


def _write_policy_inputs(
    tmp_path: Path,
    *,
    include_pytest_strength: bool = True,
) -> dict[str, object]:
    pytest_candidate_path = _write_candidate(tmp_path, "pytest")
    scrapy_candidate_path = _write_candidate(tmp_path, "scrapy")
    candidate_after_bundle_path = _write_candidate_after_bundle(tmp_path)
    scrapy_bundle_path = _write_decoy_bundle(
        tmp_path / "scrapy-decoys.json",
        [
            _scrapy_decoy("scrapy_stale_min_stats_selection", "failed"),
            _scrapy_decoy("scrapy_mutating_peek", "passed"),
            _scrapy_decoy("scrapy_missing_last_selected_slot", "failed"),
            _scrapy_decoy("scrapy_missing_tests", "passed"),
        ],
    )
    pytest_bundle_path = _write_decoy_bundle(
        tmp_path / "pytest-decoys.json",
        [
            _pytest_decoy("pytest_rel_timedelta_object_semantics", "failed"),
            _pytest_decoy("pytest_missing_container_dispatch", "failed"),
            _pytest_decoy("pytest_missing_invalid_tolerance_tests", "passed"),
            _pytest_decoy("pytest_partial_source_test_materialization", "failed"),
        ],
    )
    validation_strength_report_path = _write_validation_strength_report(
        tmp_path / "val-002.json",
        include_pytest_strength=include_pytest_strength,
    )
    return {
        "pytest_candidate_path": pytest_candidate_path,
        "scrapy_candidate_path": scrapy_candidate_path,
        "candidate_after_bundle_path": candidate_after_bundle_path,
        "decoy_validation_bundle_paths": (scrapy_bundle_path, pytest_bundle_path),
        "validation_strength_report_path": validation_strength_report_path,
    }


def _write_candidate(tmp_path: Path, kind: str) -> Path:
    record = _candidate_record(kind)
    path = tmp_path / f"{kind}-candidate.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _candidate_record(kind: str) -> dict[str, object]:
    if kind == "pytest":
        replay_id = PYTEST_REPLAY_ID
        repo = "pytest-dev/pytest"
        candidate_id = "pytest-timedelta-approx-source-test"
        action_family = "pytest_timedelta_approx_source_test_candidate"
        source_path = "src/_pytest/python_api.py"
        test_path = "testing/python/approx.py"
    elif kind == "scrapy":
        replay_id = SCRAPY_REPLAY_ID
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
        "status": "candidate_validation_passed",
        "action_family": action_family,
        "allowed_write_paths": [source_path, test_path],
        "candidate_diff": {
            "changed_files": [source_path, test_path],
            "diff_summary": {
                "added_line_count": 10,
                "removed_line_count": 1,
                "changed_line_count": 11,
            },
        },
        "source_materialization": {
            "target_source_file": source_path,
            "diff_summary": {"added_line_count": 6, "removed_line_count": 1},
            "ast_delta": {"ast_parse_ok": True, "ast_delta_added_count": 3},
        },
        "test_materialization": {
            "target_test_file": test_path,
            "diff_summary": {"added_line_count": 4, "removed_line_count": 0},
        },
        "validation": {"status": "passed", "runtime_seconds": 0.1},
        "residual_labels": ["candidate_validation_passed"],
        "zero_hosted_usage_confirmed": True,
    }


def _write_candidate_after_bundle(tmp_path: Path) -> Path:
    path = tmp_path / "candidate-after-bundle.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-candidate-after-snapshot-v1",
                "record_kind": "issue_pr_candidate_after_snapshot_bundle",
                "candidates": [
                    _candidate_after("pytest-timedelta-approx-source-test", PYTEST_REPLAY_ID),
                    _candidate_after("scrapy-downloader-aware-source-test", SCRAPY_REPLAY_ID),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _candidate_after(candidate_id: str, replay_id: str) -> dict[str, object]:
    touched = "src/example.py"
    return {
        "status": "available",
        "candidate_id": candidate_id,
        "replay_id": replay_id,
        "candidate_after": {
            "available": True,
            "candidate_id": candidate_id,
            "replay_id": replay_id,
            "touched_file_paths": [touched],
            "file_count": 1,
            "files": {
                touched: {
                    "path": touched,
                    "sha256_before": "0" * 64,
                    "sha256_after": "1" * 64,
                    "diff_summary": {"added_line_count": 1},
                    "ast_delta": {"ast_parse_ok": True, "ast_delta_added_count": 1},
                }
            },
            "embedding_available": False,
            "embedding": None,
        },
    }


def _write_decoy_bundle(path: Path, candidates: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-decoy-validation-v1",
                "record_kind": "issue_pr_decoy_validation_bundle",
                "candidates": candidates,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _scrapy_decoy(decoy_id: str, status: str) -> dict[str, object]:
    labels = {
        "scrapy_stale_min_stats_selection": ["semantic_decoy", "slot_rotation_gap"],
        "scrapy_mutating_peek": ["semantic_decoy", "peek_side_effect_gap"],
        "scrapy_missing_last_selected_slot": ["state_decoy", "source_state_gap"],
        "scrapy_missing_tests": ["coverage_gap", "test_decoy"],
    }[decoy_id]
    return _decoy(
        replay_id=SCRAPY_REPLAY_ID,
        repo="scrapy/scrapy",
        decoy_id=decoy_id,
        status=status,
        residual_labels=[f"decoy_validation_{status}", *labels],
        touched_file_paths=["scrapy/pqueues.py"],
        targeted_mistakes=[decoy_id],
    )


def _pytest_decoy(decoy_id: str, status: str) -> dict[str, object]:
    labels = {
        "pytest_rel_timedelta_object_semantics": [
            "semantic_decoy",
            "pytest_timedelta_rel_semantics_gap",
        ],
        "pytest_missing_container_dispatch": [
            "source_decoy",
            "candidate_after_observation_gap",
        ],
        "pytest_missing_invalid_tolerance_tests": ["coverage_gap", "test_decoy"],
        "pytest_partial_source_test_materialization": [
            "materialization_decoy",
            "source_semantics_gap",
        ],
    }[decoy_id]
    return _decoy(
        replay_id=PYTEST_REPLAY_ID,
        repo="pytest-dev/pytest",
        decoy_id=decoy_id,
        status=status,
        residual_labels=[f"decoy_validation_{status}", *labels],
        touched_file_paths=["src/_pytest/python_api.py", "testing/python/approx.py"],
        targeted_mistakes=[decoy_id],
    )


def _decoy(
    *,
    replay_id: str,
    repo: str,
    decoy_id: str,
    status: str,
    residual_labels: list[str],
    touched_file_paths: list[str],
    targeted_mistakes: list[str],
) -> dict[str, object]:
    candidate_id = f"{replay_id}:{decoy_id}"
    source_path = touched_file_paths[0]
    test_path = touched_file_paths[-1]
    return {
        "schema_version": "issue-pr-decoy-validation-v1",
        "record_kind": "issue_pr_decoy_validation_candidate",
        "candidate_id": candidate_id,
        "candidate_kind": "realistic_decoy",
        "decoy_id": decoy_id,
        "replay_id": replay_id,
        "repo": repo,
        "status": "validated",
        "action_family": "issue_pr_source_test_candidate",
        "allowed_write_paths": list(touched_file_paths),
        "touched_file_paths": list(touched_file_paths),
        "candidate_diff": {
            "changed_files": list(touched_file_paths),
            "diff_summary": {"added_line_count": 1, "removed_line_count": 1},
        },
        "source_materialization": {
            "target_source_file": source_path,
            "planned_changed_files": [source_path],
            "diff_summary": {"added_line_count": 1, "removed_line_count": 1},
            "ast_delta": {"ast_parse_ok": True, "ast_delta_added_count": 1},
        },
        "test_materialization": {
            "target_test_file": test_path,
            "planned_changed_files": [test_path],
            "diff_summary": {"added_line_count": 1, "removed_line_count": 1},
        },
        "validation": {
            "status": status,
            "validation_command": "pytest focused -q",
            "runtime_seconds": 0.2,
        },
        "candidate_after": {
            "available": True,
            "candidate_id": candidate_id,
            "replay_id": replay_id,
            "touched_file_paths": list(touched_file_paths),
            "file_count": len(touched_file_paths),
            "files": {
                file_path: {
                    "path": file_path,
                    "sha256_before": "0" * 64,
                    "sha256_after": "2" * 64,
                    "diff_summary": {"added_line_count": 1},
                    "ast_delta": {"ast_parse_ok": True, "ast_delta_added_count": 1},
                }
                for file_path in touched_file_paths
            },
            "embedding_available": False,
            "embedding": None,
        },
        "decoy_evidence": {
            "description": f"{decoy_id} fixture",
            "targeted_mistakes": list(targeted_mistakes),
        },
        "residual_labels": residual_labels,
        "zero_hosted_usage_confirmed": True,
    }


def _write_validation_strength_report(
    path: Path,
    *,
    include_pytest_strength: bool = True,
) -> Path:
    results = [
        _strength_result(
            replay_id=SCRAPY_REPLAY_ID,
            decoy_id="scrapy_mutating_peek",
            decoy_status="failed",
            converted=True,
            blocker=None,
        ),
        _strength_result(
            replay_id=SCRAPY_REPLAY_ID,
            decoy_id="scrapy_missing_tests",
            decoy_status="passed",
            converted=False,
            blocker=COVERAGE_GAP_LABEL_LEAKAGE_BLOCKER,
        ),
    ]
    if include_pytest_strength:
        results.append(
            _strength_result(
                replay_id=PYTEST_REPLAY_ID,
                decoy_id="pytest_missing_invalid_tolerance_tests",
                decoy_status="passed",
                converted=False,
                blocker=COVERAGE_GAP_LABEL_LEAKAGE_BLOCKER,
            )
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-validation-strength-probe-v1",
                "record_kind": "issue_pr_validation_strength_probe_report",
                "task_id": "VAL-002",
                "summary": {"runtime_seconds": 1.25},
                "results": results,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _strength_result(
    *,
    replay_id: str,
    decoy_id: str,
    decoy_status: str,
    converted: bool,
    blocker: str | None,
) -> dict[str, object]:
    return {
        "candidate_id": f"{replay_id}:{decoy_id}",
        "decoy_id": decoy_id,
        "replay_id": replay_id,
        "accepted_status": "passed",
        "decoy_status": decoy_status,
        "accepted_preserved": True,
        "passing_decoy_converted_to_failure": converted,
        "product_gate_blocker": blocker,
        "leakage_risk": "low",
        "live_runs": [],
    }
