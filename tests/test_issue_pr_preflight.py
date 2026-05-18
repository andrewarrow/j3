from __future__ import annotations

import json
import subprocess
from pathlib import Path

from j3.issue_pr_preflight import (
    Command,
    classify_pre_edit_residuals,
    load_issue_pr_replay_manifest,
    run_issue_pr_replay_preflight,
    select_issue_pr_replay_record,
    write_issue_pr_preflight_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"
REQUESTS_REPLAY_ID = "psf__requests-issue-7432-pr-7433"
CLICK_REPLAY_ID = "pallets__click-issue-2745-pr-3364"


def test_loads_manifest_and_selects_replay_row() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)

    assert record["repo"] == "psf/requests"
    assert record["repo_before_ref"]["sha"] == "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
    assert record["validation"]["command"] == "pytest tests/test_requests.py -q"


def test_preflight_records_checkout_setup_validation_and_local_knowledge(
    tmp_path: Path,
) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]
    calls: list[tuple[str, Path | None, int]] = []

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        calls.append((command_text, cwd, timeout_seconds))
        stdout = f"{sha}\n" if command_text == "git rev-parse HEAD" else ""
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=REQUESTS_REPLAY_ID,
        workspace=tmp_path,
        timeout_seconds=7,
        runner=runner,
    )
    row = outcome.to_record()

    assert row["schema_version"] == "issue-pr-replay-preflight-v1"
    assert row["replay_id"] == REQUESTS_REPLAY_ID
    assert row["repo"] == "psf/requests"
    assert row["validation_command"] == "pytest tests/test_requests.py -q"
    assert row["status"] == "blocked"
    assert row["blocker_labels"] == ["local_knowledge_required"]
    assert row["residual_category"] == "local_knowledge"
    assert [result["name"] for result in row["command_results"]] == [
        "checkout_clone",
        "checkout_ref",
        "checkout_verify",
        "setup",
        "baseline_validation",
    ]
    assert calls[0][0].startswith(
        "git clone https://github.com/psf/requests.git "
    )
    assert calls[1][0] == f"git checkout {sha}"
    assert calls[3][0] == "python -m pip install -e ."
    assert calls[4][0] == "pytest tests/test_requests.py -q"
    assert all(timeout == 7 for _, _, timeout in calls)

    provenance = row["provenance"]
    assert provenance["prompt_source"]["issue_number"] == 7432
    assert provenance["provenance_license"]["license_spdx"] == "Apache-2.0"
    assert provenance["deferred_agent_residual_labels"] == ["ranking_gap"]


def test_setup_failure_is_environment_blocker_and_skips_validation(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, CLICK_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]
    calls: list[str] = []

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        calls.append(command_text)
        if command_text == "git rev-parse HEAD":
            return subprocess.CompletedProcess(command, returncode=0, stdout=f"{sha}\n", stderr="")
        if command_text == "python -m pip install -e .":
            return subprocess.CompletedProcess(
                command,
                returncode=1,
                stdout="",
                stderr="build backend missing",
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=CLICK_REPLAY_ID,
        workspace=tmp_path,
        runner=runner,
    )
    row = outcome.to_record()

    assert row["status"] == "blocked"
    assert row["residual_category"] == "environment"
    assert row["blocker_labels"] == ["environment_setup_failed"]
    assert [result["name"] for result in row["command_results"]] == [
        "checkout_clone",
        "checkout_ref",
        "checkout_verify",
        "setup",
    ]
    assert "pytest tests/test_defaults.py -q" not in calls


def test_validation_failure_is_validation_blocker(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, CLICK_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        if command_text == "git rev-parse HEAD":
            return subprocess.CompletedProcess(command, returncode=0, stdout=f"{sha}\n", stderr="")
        if command_text == "pytest tests/test_defaults.py -q":
            return subprocess.CompletedProcess(
                command,
                returncode=2,
                stdout="",
                stderr="pytest import error",
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=CLICK_REPLAY_ID,
        workspace=tmp_path,
        runner=runner,
    )
    row = outcome.to_record()

    assert row["status"] == "blocked"
    assert row["residual_category"] == "validation"
    assert row["blocker_labels"] == ["validation_baseline_failed"]
    assert row["command_results"][-1]["name"] == "baseline_validation"
    assert row["command_results"][-1]["exit_code"] == 2


def test_writes_preflight_outcomes_as_jsonl(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        stdout = f"{sha}\n" if command_text == "git rev-parse HEAD" else ""
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=REQUESTS_REPLAY_ID,
        workspace=tmp_path / "work",
        runner=runner,
    )
    path = write_issue_pr_preflight_jsonl([outcome], tmp_path / "outcomes.jsonl")

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["record_kind"] == "issue_pr_replay_preflight_outcome"
    assert rows[0]["replay_id"] == REQUESTS_REPLAY_ID


def test_classification_defers_agent_stage_labels() -> None:
    category, blockers = classify_pre_edit_residuals(
        ["materialization_gap", "ranking_gap"],
        validation_availability="available",
    )

    assert category == "none"
    assert blockers == []


def _command_text(command: Command) -> str:
    if isinstance(command, str):
        return command
    return " ".join(str(part) for part in command)
