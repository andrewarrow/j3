from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_auxiliary_gap_audit import (
    CLICK_DEFAULT_MAP_REPLAY_ID,
    COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION,
    REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
    build_issue_pr_auxiliary_gap_audit_rows,
    main,
    summarize_issue_pr_auxiliary_gap_audit_rows,
    write_issue_pr_auxiliary_gap_audit_jsonl,
    write_issue_pr_auxiliary_gap_audit_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"


def test_auxiliary_gap_audit_classifies_click_paths(tmp_path: Path) -> None:
    candidate_path = _candidate_artifact(tmp_path)

    rows = build_issue_pr_auxiliary_gap_audit_rows(
        manifest_path=MANIFEST_PATH,
        candidate_artifact_path=candidate_path,
    )

    assert [row["path"] for row in rows] == [
        "CHANGES.rst",
        "docs/commands.md",
        "docs/conf.py",
    ]
    by_path = {row["path"]: row for row in rows}
    assert by_path["CHANGES.rst"]["classification"] == (
        COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION
    )
    assert by_path["docs/conf.py"]["proposed_action_family"] == (
        "sphinx_conf_scalar_assignment_insert_v1"
    )
    assert by_path["docs/commands.md"]["classification"] == (
        REQUIRING_CONSTRAINED_LOCAL_GENERATOR
    )
    assert by_path["docs/commands.md"]["current_action_family"] == "none"
    assert by_path["docs/commands.md"]["validation_cost"] == {
        "tier": "moderate",
        "commands": ["git diff --check", "python -m sphinx -b html docs /tmp/j3-docs"],
        "notes": (
            "The insertion anchor is deterministic, but useful section text "
            "and examples require a constrained docs generator."
        ),
    }


def test_auxiliary_gap_audit_includes_manifest_and_data014_provenance(
    tmp_path: Path,
) -> None:
    rows = build_issue_pr_auxiliary_gap_audit_rows(
        manifest_path=MANIFEST_PATH,
        candidate_artifact_path=_candidate_artifact(tmp_path),
    )
    row = rows[0]

    manifest_provenance = row["manifest_provenance"]
    assert manifest_provenance["manifest_schema_version"] == "issue-pr-mini-replay-v0"
    assert manifest_provenance["accepted_change"]["changed_files"] == [
        "CHANGES.rst",
        "docs/commands.md",
        "docs/conf.py",
        "src/click/core.py",
        "tests/test_defaults.py",
    ]

    data014_provenance = row["data014_candidate_provenance"]
    assert data014_provenance["action_family"] == "click_default_map_multi_value_candidate"
    assert data014_provenance["materialized_files_changed"] == [
        "src/click/core.py",
        "tests/test_defaults.py",
    ]
    assert data014_provenance["materialization_gap_paths"] == [
        "CHANGES.rst",
        "docs/commands.md",
        "docs/conf.py",
    ]


def test_auxiliary_gap_audit_jsonl_report_and_cli(tmp_path: Path) -> None:
    candidate_path = _candidate_artifact(tmp_path)
    out_path = tmp_path / "audit.jsonl"
    report_path = tmp_path / "audit.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--candidate-artifact",
            str(candidate_path),
            "--out",
            str(out_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    loaded = [
        json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(loaded) == 3
    summary = summarize_issue_pr_auxiliary_gap_audit_rows(
        loaded,
        outcome_path=out_path,
        report_path=report_path,
    )
    assert summary["classification_counts"] == {
        COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION: 2,
        REQUIRING_CONSTRAINED_LOCAL_GENERATOR: 1,
    }
    rewritten = write_issue_pr_auxiliary_gap_audit_jsonl(
        loaded,
        tmp_path / "rewritten.jsonl",
    )
    report = write_issue_pr_auxiliary_gap_audit_report(
        loaded,
        tmp_path / "rewritten.md",
        summary=summary,
    )
    assert rewritten.exists()
    report_text = report.read_text(encoding="utf-8")
    assert "DATA-017 Click Auxiliary Materialization Gap Audit" in report_text
    assert "docs/commands.md" in report_text


def _candidate_artifact(tmp_path: Path) -> Path:
    path = tmp_path / "candidate.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-candidate-attempt-v1",
                "record_kind": "issue_pr_candidate_attempt",
                "candidate_id": (
                    "issue-pr-candidate/"
                    "pallets__click-issue-2745-pr-3364/test-fixture"
                ),
                "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
                "repo": "pallets/click",
                "status": "validated",
                "action_family": "click_default_map_multi_value_candidate",
                "residual_labels": [
                    "candidate_validation_passed",
                    "accepted_auxiliary_paths_not_materialized",
                ],
                "mutation_scope": {
                    "files_changed": [
                        "src/click/core.py",
                        "tests/test_defaults.py",
                    ],
                    "materialization_gap_paths": [
                        "CHANGES.rst",
                        "docs/commands.md",
                        "docs/conf.py",
                    ],
                },
                "structured_action_coverage": {
                    "accepted_edit_covered": False,
                    "behavior_edit_covered": True,
                    "materialization_gap": (
                        "accepted_auxiliary_changelog_docs_config_materialization_gap"
                    ),
                },
                "validation": {
                    "status": "passed",
                    "runtime_seconds": 1.106,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path
