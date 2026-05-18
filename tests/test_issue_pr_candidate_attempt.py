from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_attempt import (
    REQUESTS_REPLAY_ID,
    main,
    run_requests_issue_pr_candidate_attempt,
    write_issue_pr_candidate_attempt_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"


def test_requests_candidate_attempt_materializes_source_and_test(tmp_path: Path) -> None:
    repo = _write_synthetic_requests_checkout(tmp_path / "requests")

    attempt = run_requests_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        readiness_records=[_ready_row()],
        validation_records=[_validation_row()],
        local_knowledge_records=[_knowledge_row("focused_validation_recipe")],
    )
    record = attempt.to_record()

    assert record["replay_id"] == REQUESTS_REPLAY_ID
    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["allowed_write_path_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        "src/requests/models.py",
        "tests/test_requests.py",
    ]
    assert record["structured_action_coverage"]["accepted_edit_covered"] is True
    assert record["validation"]["validation_command"] == (
        ".venv/bin/python -m pytest tests/test_requests.py -q "
        "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
    )
    assert 'hasattr(data, "__iter__")' in (
        repo / "src" / "requests" / "models.py"
    ).read_text(encoding="utf-8")
    assert "test_getattr_proxy_stream_follows_redirect" in (
        repo / "tests" / "test_requests.py"
    ).read_text(encoding="utf-8")
    assert "is_iterable = isinstance(data, Iterable)" in record[
        "source_materialization"
    ]["candidate_after"]["diff"]
    assert "AttrProxy" in record["test_materialization"]["diff"]


def test_requests_candidate_attempt_plan_only_records_planned_scope(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_requests_checkout(tmp_path / "requests")

    attempt = run_requests_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=False,
        validate=False,
    )
    record = attempt.to_record()

    assert record["status"] == "planned"
    assert record["mutation_scope"]["files_changed"] == [
        "src/requests/models.py",
        "tests/test_requests.py",
    ]
    assert 'hasattr(data, "__iter__")' not in (
        repo / "src" / "requests" / "models.py"
    ).read_text(encoding="utf-8")


def test_requests_candidate_attempt_validation_command_and_report(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_requests_checkout(tmp_path / "requests")

    attempt = run_requests_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        setup_command="python -c 'print(\"setup ok\")'",
        validation_command="python -c 'print(\"validation ok\")'",
        write=True,
        validate=True,
    )
    record = attempt.to_record()

    assert record["status"] == "validated"
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]
    report = write_issue_pr_candidate_attempt_report(attempt, tmp_path / "report.md")
    report_text = report.read_text(encoding="utf-8")
    assert "DATA-012 Requests Issue/PR Candidate Attempt" in report_text
    assert "Accepted edit covered" in report_text


def test_requests_candidate_attempt_cli_writes_json_and_report(tmp_path: Path) -> None:
    repo = _write_synthetic_requests_checkout(tmp_path / "requests")
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "candidate.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--repo-path",
            str(repo),
            "--setup-command",
            "python -c 'print(\"setup ok\")'",
            "--validation-command",
            "python -c 'print(\"validation ok\")'",
            "--validate",
            "--out",
            str(out_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    record = json.loads(out_path.read_text(encoding="utf-8"))
    assert record["status"] == "validated"
    assert report_path.exists()


def test_requests_candidate_attempt_rejects_wrong_replay(tmp_path: Path) -> None:
    repo = _write_synthetic_requests_checkout(tmp_path / "requests")

    try:
        run_requests_issue_pr_candidate_attempt(
            repo,
            manifest_path=MANIFEST_PATH,
            replay_id="pallets__click-issue-2745-pr-3364",
        )
    except Exception as error:
        assert "unsupported replay id" in str(error)
    else:
        raise AssertionError("wrong replay id should be rejected")


def _write_synthetic_requests_checkout(repo: Path) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "requests" / "models.py").write_text(
        """from collections.abc import Iterable, Mapping


class PreparedRequest:
    def prepare_body(
        self, data, files, json=None
    ) -> None:
        \"\"\"Prepares the given HTTP body data.\"\"\"

        body = None
        content_type = None

        if not data and json is not None:
            content_type = "application/json"

        if isinstance(data, Iterable) and not isinstance(
            data, (str, bytes, list, tuple, Mapping)
        ):
            body = data

            if getattr(body, "tell", None) is not None:
                self._body_position = body.tell()
        else:
            body = data
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_requests.py").write_text(
        """import io

import requests


class TestRequests:
    def test_rewind_body_failed_tell(self):
        assert True

    def _patch_adapter_gzipped_redirect(self, session, url):
        return None
""",
        encoding="utf-8",
    )
    return repo


def _ready_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": REQUESTS_REPLAY_ID,
        "ready_for_candidate_attempt": True,
        "validation_command": (
            ".venv/bin/python -m pytest tests/test_requests.py -q "
            "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
        ),
    }


def _validation_row() -> dict[str, object]:
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


def _knowledge_row(category: str) -> dict[str, object]:
    return {
        "record_type": "validation_recipe_record",
        "id": f"requests:{category}",
        "links": {"task_ids": [REQUESTS_REPLAY_ID]},
        "data": {"knowledge_category": category},
    }
