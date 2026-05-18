from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_attempt import PYTEST_TIMEDELTA_APPROX_REPLAY_ID
from j3.issue_pr_validation_strength_probe import (
    build_validation_strength_probe_report,
    identify_passing_decoys,
    main,
)


def test_identifies_passing_decoys_across_bundles(tmp_path: Path) -> None:
    scrapy_bundle = _write_bundle(
        tmp_path / "scrapy.json",
        [
            _decoy("scrapy_mutating_peek", "passed", replay_id="scrapy-row"),
            _decoy("scrapy_missing_last_selected_slot", "failed", replay_id="scrapy-row"),
        ],
    )
    pytest_bundle = _write_bundle(
        tmp_path / "pytest.json",
        [
            _decoy(
                "pytest_missing_invalid_tolerance_tests",
                "passed",
                replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
            ),
        ],
    )

    passing = identify_passing_decoys([scrapy_bundle, pytest_bundle])

    assert [candidate["decoy_id"] for candidate in passing] == [
        "scrapy_mutating_peek",
        "pytest_missing_invalid_tolerance_tests",
    ]
    assert all(candidate["source_bundle_path"] for candidate in passing)


def test_behavior_probe_records_coverage_gap_blocker(tmp_path: Path) -> None:
    accepted = _write_fake_pytest_checkout(tmp_path / "accepted", raises_invalid=True)
    decoy = _write_fake_pytest_checkout(tmp_path / "decoy", raises_invalid=True)
    bundle = _write_bundle(
        tmp_path / "pytest.json",
        [
            _decoy(
                "pytest_missing_invalid_tolerance_tests",
                "passed",
                replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
                checkout_path=decoy,
                residual_labels=["coverage_gap", "decoy_validation_passed", "test_decoy"],
            ),
        ],
    )

    report = build_validation_strength_probe_report(
        decoy_bundle_paths=[bundle],
        accepted_checkouts={PYTEST_TIMEDELTA_APPROX_REPLAY_ID: accepted},
        timeout_seconds=10,
    )

    result = report["results"][0]
    assert result["accepted_status"] == "passed"
    assert result["decoy_status"] == "passed"
    assert result["passing_decoy_converted_to_failure"] is False
    assert result["product_gate_blocker"] == (
        "coverage_gap_decoy_indistinguishable_without_accepted_label_leakage"
    )
    assert report["summary"]["coverage_gap_blocker_count"] == 1


def test_behavior_probe_can_convert_passing_decoy_to_failure(tmp_path: Path) -> None:
    accepted = _write_fake_pytest_checkout(tmp_path / "accepted", raises_invalid=True)
    decoy = _write_fake_pytest_checkout(tmp_path / "decoy", raises_invalid=False)
    bundle = _write_bundle(
        tmp_path / "pytest.json",
        [
            _decoy(
                "pytest_rel_timedelta_object_semantics",
                "passed",
                replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
                checkout_path=decoy,
                residual_labels=[
                    "decoy_validation_passed",
                    "pytest_timedelta_rel_semantics_gap",
                    "semantic_decoy",
                ],
            ),
        ],
    )

    report = build_validation_strength_probe_report(
        decoy_bundle_paths=[bundle],
        accepted_checkouts={PYTEST_TIMEDELTA_APPROX_REPLAY_ID: accepted},
        timeout_seconds=10,
    )

    result = report["results"][0]
    assert result["accepted_status"] == "passed"
    assert result["decoy_status"] == "failed"
    assert result["accepted_preserved"] is True
    assert result["passing_decoy_converted_to_failure"] is True
    assert result["product_gate_blocker"] is None
    assert report["summary"]["converted_passing_decoy_count"] == 1
    assert None not in report["summary"]["product_gate_blockers"]
    assert "None" not in report["summary"]["product_gate_blockers"]


def test_cli_writes_report(tmp_path: Path) -> None:
    bundle = _write_bundle(
        tmp_path / "pytest.json",
        [
            _decoy(
                "pytest_missing_invalid_tolerance_tests",
                "passed",
                replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
            ),
        ],
    )

    exit_code = main(
        [
            "--decoy-validation-bundle",
            str(bundle),
            "--no-live",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 0
    report = json.loads(
        (tmp_path / "out" / "validation-strength-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["task_id"] == "VAL-002"
    assert report["summary"]["passing_decoy_count"] == 1
    assert "VAL-002 Validation Strength Probe" in (
        tmp_path / "out" / "validation-strength-report.md"
    ).read_text(encoding="utf-8")


def _write_bundle(path: Path, candidates: list[dict[str, object]]) -> Path:
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


def _decoy(
    decoy_id: str,
    status: str,
    *,
    replay_id: str,
    checkout_path: Path | None = None,
    residual_labels: list[str] | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": f"{replay_id}:{decoy_id}",
        "candidate_kind": "realistic_decoy",
        "checkout_path": str(checkout_path or ""),
        "decoy_evidence": {
            "targeted_mistakes": [decoy_id],
        },
        "decoy_id": decoy_id,
        "expected_accepted": False,
        "replay_id": replay_id,
        "repo": "example/repo",
        "residual_labels": residual_labels or ["decoy_validation_passed"],
        "touched_file_paths": ["src/example.py"],
        "validation": {"status": status},
    }


def _write_fake_pytest_checkout(repo: Path, *, raises_invalid: bool) -> Path:
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "pytest.py").write_text(
        f"""from __future__ import annotations

from datetime import timedelta
from math import isnan


class _Approx:
    def __init__(self, expected, *, rel=None, abs=None):
        self.expected = expected
        self.rel = rel
        self.abs = abs

    def __eq__(self, actual):
        if {str(raises_invalid)}:
            if self.rel is not None and (self.rel < 0 or isnan(self.rel)):
                raise ValueError("invalid rel")
            if isinstance(self.abs, timedelta) and self.abs < timedelta(0):
                raise ValueError("invalid abs")
        tolerance = timedelta(0)
        if isinstance(self.abs, timedelta):
            tolerance = max(tolerance, self.abs)
        if self.rel is not None:
            tolerance = max(tolerance, abs(self.expected) * self.rel)
        return abs(actual - self.expected) <= tolerance


def approx(expected, *, rel=None, abs=None):
    return _Approx(expected, rel=rel, abs=abs)
""",
        encoding="utf-8",
    )
    return repo
