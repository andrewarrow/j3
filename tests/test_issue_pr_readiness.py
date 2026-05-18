from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_readiness import (
    CLICK_DEFAULT_MAP_REPLAY_ID,
    CLICK_SEMVER_REPLAY_ID,
    PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    REQUESTS_REPLAY_ID,
    build_issue_pr_readiness_rows,
    main,
    summarize_issue_pr_readiness_rows,
    write_issue_pr_readiness_jsonl,
    write_issue_pr_readiness_report,
)
from j3.issue_pr_prompt_spec import (
    build_issue_pr_prompt_spec,
    load_issue_pr_replay_manifest,
)
from j3.local_knowledge import (
    CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES,
    REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"


def test_first_batch_readiness_separates_ready_and_blocked_rows() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    rows = build_issue_pr_readiness_rows(
        manifest_path=MANIFEST_PATH,
        limit=3,
        preflight_records=[
            _passed_preflight(CLICK_DEFAULT_MAP_REPLAY_ID, "pytest tests/test_defaults.py -q"),
            _passed_preflight(CLICK_SEMVER_REPLAY_ID, "pytest tests/test_options.py -q"),
        ],
        validation_records=[_passed_requests_validation_attempt()],
        prompt_specs=[
            build_issue_pr_prompt_spec(manifest, REQUESTS_REPLAY_ID),
            build_issue_pr_prompt_spec(manifest, CLICK_DEFAULT_MAP_REPLAY_ID),
            build_issue_pr_prompt_spec(manifest, CLICK_SEMVER_REPLAY_ID),
        ],
        local_knowledge_records=[
            *_knowledge_records(REQUESTS_REPLAY_ID, REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES),
            *_knowledge_records(CLICK_SEMVER_REPLAY_ID, CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES),
        ],
    )
    by_id = {row["replay_id"]: row for row in rows}

    assert by_id[CLICK_DEFAULT_MAP_REPLAY_ID]["ready_for_candidate_attempt"] is True
    assert by_id[CLICK_DEFAULT_MAP_REPLAY_ID]["missing_evidence_labels"] == []
    assert by_id[CLICK_DEFAULT_MAP_REPLAY_ID]["next_stage_challenge_labels"] == [
        "materialization_gap",
        "ranking_gap",
    ]
    assert by_id[CLICK_DEFAULT_MAP_REPLAY_ID]["validation_command"] == (
        "pytest tests/test_defaults.py -q"
    )

    assert by_id[REQUESTS_REPLAY_ID]["ready_for_candidate_attempt"] is True
    assert by_id[REQUESTS_REPLAY_ID]["missing_evidence_labels"] == []
    assert by_id[REQUESTS_REPLAY_ID]["validation_command"] == (
        ".venv/bin/python -m pytest tests/test_requests.py -q "
        "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
    )

    assert by_id[CLICK_SEMVER_REPLAY_ID]["ready_for_candidate_attempt"] is True
    assert by_id[CLICK_SEMVER_REPLAY_ID]["missing_evidence_labels"] == []
    assert by_id[CLICK_SEMVER_REPLAY_ID]["validation_command"] == (
        "pytest tests/test_options.py -q"
    )


def test_ready_row_keeps_materialization_and_ranking_as_next_stage() -> None:
    rows = build_issue_pr_readiness_rows(
        manifest_path=MANIFEST_PATH,
        replay_ids=[REQUESTS_REPLAY_ID],
        validation_records=[_passed_requests_validation_attempt()],
        prompt_specs=[_normalized_prompt_spec(REQUESTS_REPLAY_ID)],
        local_knowledge_records=_knowledge_records(
            REQUESTS_REPLAY_ID,
            REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
        ),
    )

    row = rows[0]
    assert row["ready_for_candidate_attempt"] is True
    assert row["blocker_recommendation"] == (
        "ready_for_candidate_attempt; "
        "next_stage_challenge=materialization_gap,ranking_gap"
    )
    assert row["missing_evidence_labels"] == []
    assert "prompt_spec_parsing_gap" not in row["residual_labels"]
    assert "local_knowledge_gap" not in row["residual_labels"]
    assert "validation_gap" not in row["residual_labels"]
    assert row["residual_labels"] == ["materialization_gap", "ranking_gap"]


def test_missing_local_knowledge_uses_exact_category_labels() -> None:
    rows = build_issue_pr_readiness_rows(
        manifest_path=MANIFEST_PATH,
        replay_ids=[CLICK_SEMVER_REPLAY_ID],
        preflight_records=[
            _passed_preflight(CLICK_SEMVER_REPLAY_ID, "pytest tests/test_options.py -q")
        ],
        prompt_specs=[_normalized_prompt_spec(CLICK_SEMVER_REPLAY_ID)],
        local_knowledge_records=_knowledge_records(
            CLICK_SEMVER_REPLAY_ID,
            CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES[:-1],
        ),
    )

    row = rows[0]
    assert row["ready_for_candidate_attempt"] is False
    assert row["missing_evidence_labels"] == [
        "missing_local_knowledge:third_party_semver_version_reproduction"
    ]
    assert row["blocker_recommendation"] == (
        "blocked_until_evidence:"
        "missing_local_knowledge:third_party_semver_version_reproduction"
    )


def test_pytest_strict_addopts_readiness_records_full_scope_note() -> None:
    rows = build_issue_pr_readiness_rows(
        manifest_path=MANIFEST_PATH,
        replay_ids=[PYTEST_STRICT_ADDOPTS_REPLAY_ID],
        preflight_records=[
            _passed_preflight(
                PYTEST_STRICT_ADDOPTS_REPLAY_ID,
                "pytest testing/test_config.py testing/test_mark.py -q",
                required_knowledge_categories=(
                    "repo_changed_file_context",
                    "repo_test_pattern",
                    "focused_validation_recipe",
                ),
            )
        ],
        prompt_specs=[_normalized_prompt_spec(PYTEST_STRICT_ADDOPTS_REPLAY_ID)],
        local_knowledge_records=_knowledge_records(
            PYTEST_STRICT_ADDOPTS_REPLAY_ID,
            PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES,
        ),
    )

    row = rows[0]

    assert row["ready_for_candidate_attempt"] is True
    assert row["missing_evidence_labels"] == []
    assert row["validation_command"] == (
        "pytest testing/test_config.py testing/test_mark.py -q"
    )
    assert row["required_local_knowledge_categories"] == list(
        PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES
    )
    assert row["local_knowledge_categories_present"] == sorted(
        PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES
    )
    assert row["allowed_write_scope"]["python_source_paths"] == [
        "src/_pytest/config/__init__.py"
    ]
    assert row["allowed_write_scope"]["test_paths"] == [
        "testing/test_config.py",
        "testing/test_mark.py",
    ]
    assert row["allowed_write_scope"]["auxiliary_paths"] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
    ]
    assert "source/test candidate scope" in row["accepted_edit_scope_note"].lower()
    assert "auxiliary materializers" in row["accepted_edit_scope_note"]
    assert row["residual_labels"] == ["materialization_gap", "ranking_gap"]
    assert row["next_stage_challenge_labels"] == [
        "materialization_gap",
        "ranking_gap",
    ]
    materialization_challenge = row["next_stage_challenges"][0]
    assert materialization_challenge["label"] == "materialization_gap"
    assert materialization_challenge["source_test_paths"] == [
        "src/_pytest/config/__init__.py",
        "testing/test_config.py",
        "testing/test_mark.py",
    ]
    assert materialization_challenge["auxiliary_paths"] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
    ]
    knowledge_evidence = [
        evidence
        for evidence in row["evidence_sources"]
        if evidence["evidence_type"] == "local_knowledge"
    ]
    assert {
        evidence["knowledge_category"] for evidence in knowledge_evidence
    } == set(PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES)


def test_readiness_jsonl_summary_report_and_cli(tmp_path: Path) -> None:
    preflight_path = tmp_path / "preflight.jsonl"
    prompt_path = tmp_path / "prompt.jsonl"
    knowledge_path = tmp_path / "knowledge.jsonl"
    out_path = tmp_path / "readiness.jsonl"
    report_path = tmp_path / "readiness.md"

    preflight_path.write_text(
        json.dumps(
            _passed_preflight(CLICK_DEFAULT_MAP_REPLAY_ID, "pytest tests/test_defaults.py -q")
        )
        + "\n",
        encoding="utf-8",
    )
    prompt_path.write_text(
        json.dumps(_normalized_prompt_spec(CLICK_DEFAULT_MAP_REPLAY_ID)) + "\n",
        encoding="utf-8",
    )
    knowledge_path.write_text("", encoding="utf-8")

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            CLICK_DEFAULT_MAP_REPLAY_ID,
            "--preflight-evidence",
            str(preflight_path),
            "--prompt-spec-evidence",
            str(prompt_path),
            "--local-knowledge-evidence",
            str(knowledge_path),
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
    assert loaded[0]["ready_for_candidate_attempt"] is True
    summary = summarize_issue_pr_readiness_rows(loaded, outcome_path=out_path)
    assert summary["status_counts"] == {"ready": 1}
    rewritten = write_issue_pr_readiness_jsonl(loaded, tmp_path / "rewritten.jsonl")
    report = write_issue_pr_readiness_report(
        loaded,
        tmp_path / "rewritten.md",
        summary=summary,
    )
    assert rewritten.exists()
    assert "Issue/PR Candidate Readiness Gate" in report.read_text(
        encoding="utf-8"
    )


def _passed_preflight(
    replay_id: str,
    validation_command: str,
    *,
    required_knowledge_categories: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": replay_id,
        "status": "blocked",
        "validation_command": validation_command,
        "command_stages_reached": [
            "checkout_clone",
            "checkout_ref",
            "checkout_verify",
            "setup",
            "baseline_validation",
        ],
        "first_failed_stage": "none",
        "command_results": [
            {"name": "baseline_validation", "passed": True, "command": validation_command}
        ],
        "blocker_details": [
            {"required_knowledge_categories": list(required_knowledge_categories)}
        ]
        if required_knowledge_categories
        else [],
    }


def _passed_requests_validation_attempt() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_validation_recipe_attempt",
        "replay_id": REQUESTS_REPLAY_ID,
        "recipe_name": "requests-focused-prepare-body-httpbin",
        "status": "passed",
        "validation_command": (
            ".venv/bin/python -m pytest tests/test_requests.py -q "
            "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
        ),
    }


def _normalized_prompt_spec(replay_id: str) -> dict[str, object]:
    return {
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": replay_id,
        "prompt_spec_kind": "test-normalized",
        "status": "normalized",
        "required_prompt_fields_complete": True,
        "missing_prompt_fields": [],
    }


def _knowledge_records(
    replay_id: str,
    categories: tuple[str, ...],
) -> list[dict[str, object]]:
    rows = []
    for category in categories:
        rows.append(
            {
                "record_type": (
                    "validation_recipe_record"
                    if category == "focused_validation_recipe"
                    else "library_idiom_record"
                ),
                "id": f"{replay_id}:{category}",
                "links": {"task_ids": [replay_id], "outcome_ids": [], "residual_labels": []},
                "source": {"repo": "fixture/repo", "path": f"task:{replay_id}"},
                "data": {
                    "knowledge_category": category,
                    "focused_commands": ["python -m pytest focused.py -q"],
                },
            }
        )
    return rows
