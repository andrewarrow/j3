from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_after_snapshot import (
    build_issue_pr_candidate_after_bundle,
    load_candidate_after_bundle_index,
    main,
    write_issue_pr_candidate_after_bundle,
)


def test_build_candidate_after_bundle_writes_full_file_snapshots(
    tmp_path: Path,
) -> None:
    candidate_path, after_root, replay_id, candidate_id = _write_candidate_and_after_root(
        tmp_path
    )

    bundle = build_issue_pr_candidate_after_bundle(
        candidate_paths=[candidate_path],
        out_dir=tmp_path / "out",
        after_roots={replay_id: [after_root]},
    )

    assert bundle["summary"]["candidate_count"] == 1
    assert bundle["summary"]["available_candidate_count"] == 1
    assert bundle["summary"]["snapshot_file_count"] == 2
    candidate = bundle["candidates"][0]
    assert candidate["status"] == "available"
    assert candidate["candidate_after"]["available"] is True
    assert candidate["candidate_after"]["file_count"] == 2
    snapshot_paths = [
        Path(snapshot["after_snapshot_path"]) for snapshot in candidate["snapshots"]
    ]
    assert {path.name for path in snapshot_paths} == {"mod.py", "test_mod.py"}
    assert all(path.is_file() for path in snapshot_paths)

    artifacts = write_issue_pr_candidate_after_bundle(bundle, out_dir=tmp_path / "out")
    assert json.loads(artifacts["bundle_json"].read_text(encoding="utf-8"))[
        "schema_version"
    ]
    assert "DATA-038 Issue/PR Candidate-After" in artifacts["report_md"].read_text(
        encoding="utf-8"
    )

    index = load_candidate_after_bundle_index(artifacts["bundle_json"])
    assert (replay_id, candidate_id) in index
    assert index[(replay_id, candidate_id)]["available"] is True


def test_candidate_after_bundle_blocks_when_no_after_root_matches(
    tmp_path: Path,
) -> None:
    candidate_path, _after_root, replay_id, _candidate_id = (
        _write_candidate_and_after_root(tmp_path)
    )

    bundle = build_issue_pr_candidate_after_bundle(
        candidate_paths=[candidate_path],
        out_dir=tmp_path / "out",
        after_roots={replay_id: [tmp_path / "missing-root"]},
    )

    assert bundle["summary"]["available_candidate_count"] == 0
    assert bundle["summary"]["blocker_reasons"] == ["matching_after_root_unavailable"]
    assert bundle["candidates"][0]["status"] == "blocked"


def test_candidate_after_snapshot_cli_writes_bundle(tmp_path: Path) -> None:
    candidate_path, after_root, replay_id, _candidate_id = (
        _write_candidate_and_after_root(tmp_path)
    )

    exit_code = main(
        [
            "--candidate",
            str(candidate_path),
            "--after-root",
            f"{replay_id}={after_root}",
            "--out-dir",
            str(tmp_path / "cli-out"),
        ]
    )

    assert exit_code == 0
    bundle = json.loads(
        (tmp_path / "cli-out" / "candidate-after-bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["summary"]["available_candidate_count"] == 1


def _write_candidate_and_after_root(
    tmp_path: Path,
) -> tuple[Path, Path, str, str]:
    replay_id = "pytest-dev__pytest-issue-14462-pr-14466"
    candidate_id = "candidate-1"
    before_source = "def f():\n    return 1\n"
    after_source = "def f():\n    return 2\n"
    before_test = "def test_f():\n    assert True\n"
    after_test = "def test_f():\n    assert 2 == 2\n"

    after_root = tmp_path / "after-root"
    (after_root / "pkg").mkdir(parents=True)
    (after_root / "tests").mkdir(parents=True)
    (after_root / "pkg" / "mod.py").write_text(after_source, encoding="utf-8")
    (after_root / "tests" / "test_mod.py").write_text(after_test, encoding="utf-8")

    candidate = {
        "schema_version": "issue-pr-candidate-attempt-v1",
        "record_kind": "issue_pr_candidate_attempt",
        "candidate_id": candidate_id,
        "replay_id": replay_id,
        "repo": "pytest-dev/pytest",
        "repo_before_ref": "abc123",
        "status": "validated",
        "action_family": "pytest_timedelta_approx_source_test_candidate",
        "candidate_diff": {
            "changed_files": ["pkg/mod.py", "tests/test_mod.py"],
            "diff_summary": {"added_line_count": 2, "removed_line_count": 2},
        },
        "source_materialization": {
            "target_source_file": "pkg/mod.py",
            "planned_changed_files": ["pkg/mod.py"],
            "sha256_before": _sha256_text(before_source),
            "sha256_after": _sha256_text(after_source),
            "diff_summary": {"added_line_count": 1, "removed_line_count": 1},
            "diff": "--- a/pkg/mod.py\n+++ b/pkg/mod.py\n",
            "ast_delta": {"ast_parse_ok": True},
        },
        "test_materialization": {
            "target_test_file": "tests/test_mod.py",
            "planned_changed_files": ["tests/test_mod.py"],
            "sha256_before": _sha256_text(before_test),
            "sha256_after": _sha256_text(after_test),
            "diff_summary": {"added_line_count": 1, "removed_line_count": 1},
            "diff": "--- a/tests/test_mod.py\n+++ b/tests/test_mod.py\n",
        },
        "validation": {"status": "passed"},
        "evidence": {},
        "zero_hosted_usage_confirmed": True,
    }
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(
        json.dumps(candidate, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return candidate_path, after_root, replay_id, candidate_id


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
