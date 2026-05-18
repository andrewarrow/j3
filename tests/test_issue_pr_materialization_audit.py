from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_materialization_audit import (
    COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION,
    PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
    build_issue_pr_materialization_audit_rows,
    main,
    summarize_issue_pr_materialization_audit_rows,
    write_issue_pr_materialization_audit_jsonl,
    write_issue_pr_materialization_audit_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"


def test_materialization_audit_classifies_all_pytest_14442_paths() -> None:
    rows = build_issue_pr_materialization_audit_rows(manifest_path=MANIFEST_PATH)

    assert [row["path"] for row in rows] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
        "src/_pytest/config/__init__.py",
        "testing/test_config.py",
        "testing/test_mark.py",
    ]
    by_path = {row["path"]: row for row in rows}
    assert by_path["AUTHORS"]["classification"] == (
        COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION
    )
    assert by_path["AUTHORS"]["proposed_action_family"] == (
        "newline_delimited_sorted_unique_insert_v1"
    )
    assert by_path["AUTHORS"]["accepted_diff_summary"]["accepted_numstat"] == {
        "added": 2,
        "removed": 0,
    }
    assert by_path["changelog/14442.bugfix.rst"]["classification"] == (
        REQUIRING_CONSTRAINED_LOCAL_GENERATOR
    )
    assert by_path["src/_pytest/config/__init__.py"]["validation_cost"][
        "commands"
    ] == [
        "python -m py_compile src/_pytest/config/__init__.py",
        "pytest testing/test_config.py testing/test_mark.py -q",
    ]
    assert by_path["testing/test_config.py"]["proposed_action_family"] == (
        "pytest_parametrize_existing_test_refine_v1"
    )
    assert by_path["testing/test_mark.py"][
        "smallest_next_falsifiable_materializer_task"
    ]["task_id"] == "DATA-023-next-test-mark-parametrize-refine"


def test_materialization_audit_classifies_all_pytest_14462_paths() -> None:
    rows = build_issue_pr_materialization_audit_rows(
        manifest_path=MANIFEST_PATH,
        replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    )

    assert [row["path"] for row in rows] == [
        "src/_pytest/python_api.py",
        "testing/python/approx.py",
    ]
    by_path = {row["path"]: row for row in rows}
    source = by_path["src/_pytest/python_api.py"]
    assert source["audit_id"] == (
        "DATA-028/"
        "pytest-dev__pytest-issue-14462-pr-14466/"
        "src/_pytest/python_api.py"
    )
    assert source["audit_task_id"] == "DATA-028"
    assert source["classification"] == REQUIRING_CONSTRAINED_LOCAL_GENERATOR
    assert source["accepted_diff_summary"]["accepted_numstat"] == {
        "added": 31,
        "removed": 12,
    }
    assert source["validation_cost"]["commands"] == [
        "python -m py_compile src/_pytest/python_api.py",
        "pytest testing/python/approx.py -q",
    ]
    assert source["audit_provenance"] == ["DATA-018", "DATA-026", "DATA-028"]
    assert (
        source["smallest_next_falsifiable_materializer_task"]["task_id"]
        == "DATA-028-next-approx-timedelta-source-region"
    )

    tests = by_path["testing/python/approx.py"]
    assert tests["classification"] == REQUIRING_CONSTRAINED_LOCAL_GENERATOR
    assert tests["proposed_action_family"] == (
        "pytest_existing_class_method_refine_and_insert_v1"
    )
    assert tests["accepted_diff_summary"]["accepted_numstat"] == {
        "added": 95,
        "removed": 5,
    }
    assert (
        tests["smallest_next_falsifiable_materializer_task"]["task_id"]
        == "DATA-028-next-approx-test-class-refiner"
    )


def test_materialization_audit_includes_manifest_and_evidence_provenance(
    tmp_path: Path,
) -> None:
    preflight_path = tmp_path / "preflight.jsonl"
    prompt_spec_path = tmp_path / "spec.jsonl"
    knowledge_path = tmp_path / "knowledge.jsonl"
    preflight_path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-replay-preflight-v1",
                "record_kind": "issue_pr_replay_preflight_outcome",
                "replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID,
                "status": "blocked",
                "validation_command": "pytest testing/test_config.py testing/test_mark.py -q",
                "first_failed_stage": "none",
                "command_results": [
                    {"name": "baseline_validation", "passed": True, "runtime_seconds": 3.715}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prompt_spec_path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-prompt-spec-v1",
                "record_kind": "issue_pr_prompt_spec",
                "replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    knowledge_path.write_text(
        json.dumps(
            {
                "schema_version": "local-knowledge-record-v1",
                "record_type": "pytest_pattern_record",
                "data": {"replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID},
                "id": "knowledge-row",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = build_issue_pr_materialization_audit_rows(
        manifest_path=MANIFEST_PATH,
        preflight_outcome_path=preflight_path,
        prompt_spec_evidence_path=prompt_spec_path,
        local_knowledge_evidence_path=knowledge_path,
    )
    row = rows[0]

    manifest_provenance = row["manifest_provenance"]
    assert manifest_provenance["manifest_schema_version"] == "issue-pr-mini-replay-v0"
    assert manifest_provenance["accepted_change"]["changed_files"] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
        "src/_pytest/config/__init__.py",
        "testing/test_config.py",
        "testing/test_mark.py",
    ]
    evidence = row["evidence_provenance"]
    assert evidence["preflight_outcome"]["first_failed_stage"] == "none"
    assert evidence["prompt_spec_evidence"]["record_kinds"] == [
        "issue_pr_prompt_spec"
    ]
    assert evidence["local_knowledge_evidence"]["ids"] == ["knowledge-row"]


def test_materialization_audit_includes_pytest_14462_data_026_provenance(
    tmp_path: Path,
) -> None:
    preflight_path = tmp_path / "preflight.jsonl"
    prompt_spec_path = tmp_path / "spec.jsonl"
    knowledge_path = tmp_path / "knowledge.jsonl"
    preflight_path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-replay-preflight-v1",
                "record_kind": "issue_pr_replay_preflight_outcome",
                "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
                "validation_command": "pytest testing/python/approx.py -q",
                "first_failed_stage": "none",
                "command_results": [
                    {
                        "name": "baseline_validation",
                        "passed": True,
                        "runtime_seconds": 0.438,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prompt_spec_path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-prompt-spec-v1",
                "record_kind": "issue_pr_prompt_spec",
                "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    knowledge_path.write_text(
        json.dumps(
            {
                "schema_version": "local-knowledge-record-v1",
                "record_type": "library_idiom_record",
                "data": {"replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID},
                "id": "data-026-knowledge-row",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = build_issue_pr_materialization_audit_rows(
        manifest_path=MANIFEST_PATH,
        replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        preflight_outcome_path=preflight_path,
        prompt_spec_evidence_path=prompt_spec_path,
        local_knowledge_evidence_path=knowledge_path,
    )
    row = rows[0]

    assert row["manifest_provenance"]["accepted_change"]["changed_files"] == [
        "src/_pytest/python_api.py",
        "testing/python/approx.py",
    ]
    evidence = row["evidence_provenance"]
    assert evidence["preflight_outcome"]["validation_command"] == (
        "pytest testing/python/approx.py -q"
    )
    assert evidence["prompt_spec_evidence"]["record_kinds"] == [
        "issue_pr_prompt_spec"
    ]
    assert evidence["local_knowledge_evidence"]["ids"] == [
        "data-026-knowledge-row"
    ]


def test_materialization_audit_jsonl_report_and_cli(tmp_path: Path) -> None:
    out_path = tmp_path / "audit.jsonl"
    report_path = tmp_path / "audit.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
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
    assert len(loaded) == 5
    summary = summarize_issue_pr_materialization_audit_rows(
        loaded,
        outcome_path=out_path,
        report_path=report_path,
    )
    assert summary["classification_counts"] == {
        COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION: 1,
        REQUIRING_CONSTRAINED_LOCAL_GENERATOR: 4,
    }
    rewritten = write_issue_pr_materialization_audit_jsonl(
        loaded,
        tmp_path / "rewritten.jsonl",
    )
    report = write_issue_pr_materialization_audit_report(
        loaded,
        tmp_path / "rewritten.md",
        summary=summary,
    )
    assert rewritten.exists()
    report_text = report.read_text(encoding="utf-8")
    assert "DATA-023 Pytest #14442 Materialization Coverage Audit" in report_text
    assert "src/_pytest/config/__init__.py" in report_text


def test_materialization_audit_pytest_14462_cli_report(tmp_path: Path) -> None:
    out_path = tmp_path / "audit.jsonl"
    report_path = tmp_path / "audit.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
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
    assert len(loaded) == 2
    summary = summarize_issue_pr_materialization_audit_rows(loaded)
    assert summary["classification_counts"] == {
        REQUIRING_CONSTRAINED_LOCAL_GENERATOR: 2,
    }
    assert summary["accepted_paths_fully_expressible_now"] is False
    report_text = report_path.read_text(encoding="utf-8")
    assert "DATA-028 Pytest #14462 Materialization Coverage Audit" in report_text
    assert "testing/python/approx.py" in report_text
