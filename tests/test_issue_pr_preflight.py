from __future__ import annotations

import json
import subprocess
from pathlib import Path

from j3.issue_pr_preflight import (
    Command,
    classify_issue_pr_command_outcome,
    classify_issue_pr_evidence_acquisition_status,
    derive_issue_pr_blocker_details,
    derive_issue_pr_pre_edit_evidence_gaps,
    classify_pre_edit_residuals,
    first_failed_stage,
    load_issue_pr_preflight_jsonl,
    load_issue_pr_replay_manifest,
    run_issue_pr_validation_recipe_attempt,
    run_issue_pr_replay_preflight_batch,
    run_issue_pr_replay_preflight,
    select_issue_pr_replay_record,
    select_issue_pr_replay_records,
    summarize_issue_pr_validation_recipe_attempts,
    summarize_issue_pr_preflight_outcomes,
    summarize_issue_pr_preflight_records,
    write_issue_pr_validation_recipe_attempt_jsonl,
    write_issue_pr_validation_recipe_attempt_report,
    write_issue_pr_preflight_jsonl,
    write_issue_pr_preflight_records_jsonl,
    write_issue_pr_preflight_records_report,
    write_issue_pr_preflight_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"
REQUESTS_REPLAY_ID = "psf__requests-issue-7432-pr-7433"
CLICK_REPLAY_ID = "pallets__click-issue-2745-pr-3364"
PIP_REPLAY_ID = "pypa__pip-issue-12018-pr-13886"
SCRAPY_REPLAY_ID = "scrapy__scrapy-issue-7293-pr-7351"


def test_loads_manifest_and_selects_replay_row() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)

    assert record["repo"] == "psf/requests"
    assert record["repo_before_ref"]["sha"] == "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
    assert record["validation"]["command"] == "pytest tests/test_requests.py -q"


def test_selects_bounded_replay_batch_in_manifest_order() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    records = select_issue_pr_replay_records(manifest, limit=2)

    assert [record["id"] for record in records] == [
        REQUESTS_REPLAY_ID,
        CLICK_REPLAY_ID,
    ]


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
    assert row["runtime_seconds"] >= 0
    assert row["command_stages_reached"] == [
        "checkout_clone",
        "checkout_ref",
        "checkout_verify",
        "setup",
        "baseline_validation",
    ]
    assert row["first_failed_stage"] == "none"
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
    assert row["first_failed_stage"] == "baseline_validation"
    assert row["command_results"][-1]["name"] == "baseline_validation"
    assert row["command_results"][-1]["exit_code"] == 2
    assert row["blocker_details"][0]["failure_family"] == "validation_recipe_failure"


def test_validation_drilldown_classifies_recursive_fixture_setup(
    tmp_path: Path,
) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        if command_text == "git rev-parse HEAD":
            return subprocess.CompletedProcess(command, returncode=0, stdout=f"{sha}\n", stderr="")
        if command_text == "pytest tests/test_requests.py -q":
            return subprocess.CompletedProcess(
                command,
                returncode=1,
                stdout=(
                    "file tests/test_requests.py, line 124\n"
                    "file tests/conftest.py, line 34\n"
                    "E recursive dependency involving fixture 'httpbin' detected\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=REQUESTS_REPLAY_ID,
        workspace=tmp_path,
        runner=runner,
    )
    row = outcome.to_record()
    detail = row["blocker_details"][0]

    assert detail["blocker_label"] == "validation_baseline_failed"
    assert detail["failure_family"] == "dependency_fixture_setup_failure"
    assert detail["evidence_stage"] == "baseline_validation"
    assert "httpbin" in detail["evidence"]["summary"]
    assert "hermetic" in detail["required_next_actions"][0]


def test_validation_recipe_attempt_records_passing_recipe(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]
    calls: list[str] = []

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        calls.append(command_text)
        stdout = f"{sha}\n" if command_text == "git rev-parse HEAD" else ""
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    attempt = run_issue_pr_validation_recipe_attempt(
        manifest_path=MANIFEST_PATH,
        replay_id=REQUESTS_REPLAY_ID,
        workspace=tmp_path / "work",
        recipe_name="requests-focused-prepare-body",
        setup_command="python -m pip install -r requirements-dev.txt",
        validation_command=(
            "python -m pytest tests/test_requests.py -q "
            "-k 'prepare_body or rewind_body'"
        ),
        timeout_seconds=9,
        runner=runner,
    )
    row = attempt.to_record()

    assert row["schema_version"] == "issue-pr-validation-recipe-attempt-v1"
    assert row["record_kind"] == "issue_pr_validation_recipe_attempt"
    assert row["status"] == "passed"
    assert row["first_failed_stage"] == "none"
    assert row["failure_family"] == "none"
    assert row["recommendation"] == "use_validation_recipe"
    assert row["candidate_code_edits_attempted"] is False
    assert row["command_stages_reached"] == [
        "checkout_clone",
        "checkout_ref",
        "checkout_verify",
        "setup",
        "validation",
    ]
    assert calls[3] == "python -m pip install -r requirements-dev.txt"
    assert calls[4].startswith("python -m pytest tests/test_requests.py")


def test_validation_recipe_attempt_records_fixture_blocker(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        if command_text == "git rev-parse HEAD":
            return subprocess.CompletedProcess(command, returncode=0, stdout=f"{sha}\n", stderr="")
        if command_text.startswith("python -m pytest"):
            return subprocess.CompletedProcess(
                command,
                returncode=1,
                stdout="E recursive dependency involving fixture 'httpbin' detected",
                stderr="",
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    attempt = run_issue_pr_validation_recipe_attempt(
        manifest_path=MANIFEST_PATH,
        replay_id=REQUESTS_REPLAY_ID,
        workspace=tmp_path / "work",
        recipe_name="requests-original-manifest",
        setup_command="python -m pip install -e . pytest",
        validation_command="python -m pytest tests/test_requests.py -q",
        runner=runner,
    )
    row = attempt.to_record()

    assert row["status"] == "blocked"
    assert row["first_failed_stage"] == "validation"
    assert row["failure_family"] == "dependency_fixture_setup_failure"
    assert row["command_classification"] == "dependency_fixture_setup_failure"
    assert row["evidence_acquisition_status"] == "blocked_on_validation_recipe"
    assert "httpbin" in row["fixture_dependency_evidence"]["summary"]
    assert row["recommendation"] == "keep_blocked_until_fixture_setup_is_hermetic"


def test_pip_validation_recipe_records_added_dependency_and_next_missing_module(
    tmp_path: Path,
) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, PIP_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        if command_text == "git rev-parse HEAD":
            return subprocess.CompletedProcess(command, returncode=0, stdout=f"{sha}\n", stderr="")
        if command_text == "pytest tests/functional/test_install_reqs.py -q":
            return subprocess.CompletedProcess(
                command,
                returncode=4,
                stdout="",
                stderr=(
                    "ImportError while loading conftest '/tmp/pip/tests/conftest.py'.\n"
                    "tests/conftest.py:41: in <module>\n"
                    "    from tests.lib import TestFileEnvironment\n"
                    "tests/lib/__init__.py:25: in <module>\n"
                    "    from scripttest import TestFileEnvironment\n"
                    "E   ModuleNotFoundError: No module named 'scripttest'\n"
                ),
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    attempt = run_issue_pr_validation_recipe_attempt(
        manifest_path=MANIFEST_PATH,
        replay_id=PIP_REPLAY_ID,
        workspace=tmp_path / "work",
        recipe_name="pip-functional-install-reqs-installer",
        setup_command="python -m pip install -e . installer",
        validation_command="pytest tests/functional/test_install_reqs.py -q",
        dependencies_added=["installer"],
        runner=runner,
    )
    row = attempt.to_record()

    assert row["dependencies_added"] == ["installer"]
    assert row["status"] == "blocked"
    assert row["first_failed_stage"] == "validation"
    assert row["failure_family"] == "dependency_fixture_setup_failure"
    assert row["command_classification"] == "dependency_fixture_setup_failure"
    assert row["evidence_acquisition_status"] == "blocked_on_validation_recipe"
    assert row["fixture_dependency_evidence"]["missing_module_names"] == ["scripttest"]
    assert "scripttest" in row["fixture_dependency_evidence"]["summary"]


def test_validation_recipe_jsonl_summary_and_report(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, REQUESTS_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        stdout = f"{sha}\n" if command_text == "git rev-parse HEAD" else ""
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    attempt = run_issue_pr_validation_recipe_attempt(
        manifest_path=MANIFEST_PATH,
        replay_id=REQUESTS_REPLAY_ID,
        workspace=tmp_path / "work",
        recipe_name="requests-focused",
        setup_command="python -m pip install -r requirements-dev.txt",
        validation_command="python -m pytest tests/test_requests.py -q -k prepare_body",
        dependencies_added=["requirements-dev.txt"],
        runner=runner,
    )
    outcome_path = write_issue_pr_validation_recipe_attempt_jsonl(
        [attempt],
        tmp_path / "attempts.jsonl",
    )
    summary = summarize_issue_pr_validation_recipe_attempts(
        [attempt],
        outcome_path=outcome_path,
        report_path=tmp_path / "report.md",
        batch_runtime_seconds=1.5,
    )
    report_path = write_issue_pr_validation_recipe_attempt_report(
        [attempt],
        tmp_path / "report.md",
        summary=summary,
    )

    written = [
        json.loads(line) for line in outcome_path.read_text(encoding="utf-8").splitlines()
    ]
    assert written[0]["recipe_name"] == "requests-focused"
    assert summary["status_counts"] == {"passed": 1}
    assert summary["failure_family_counts"] == {"none": 1}
    assert summary["command_classification_counts"] == {"commands_passed": 1}
    assert summary["evidence_acquisition_status_counts"] == {
        "ready_for_prompt_spec_and_local_knowledge": 1
    }
    assert summary["dependencies_added_counts"] == {"requirements-dev.txt": 1}
    assert summary["runtime_seconds"] == 1.5
    report = report_path.read_text(encoding="utf-8")
    assert "DATA-008 Issue/PR Validation Recipe Attempts" in report
    assert "requests-focused" in report
    assert "requirements-dev.txt" in report


def test_timeout_drilldown_classifies_timeout() -> None:
    row = {
        "replay_id": "example",
        "repo": "owner/repo",
        "validation_command": "pytest tests -q",
        "first_failed_stage": "baseline_validation",
        "blocker_labels": ["validation_baseline_failed"],
        "residual_category": "validation",
        "command_results": [
            {
                "name": "baseline_validation",
                "command": "pytest tests -q",
                "passed": False,
                "exit_code": None,
                "timed_out": True,
                "stdout": "",
                "stderr": "",
            }
        ],
        "provenance": {"prompt_source": {}},
    }

    details = derive_issue_pr_blocker_details(row)

    assert details[0]["failure_family"] == "timeout"
    assert details[0]["timed_out"] is True


def test_prompt_spec_drilldown_emits_missing_fields(tmp_path: Path) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, CLICK_REPLAY_ID)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        stdout = f"{sha}\n" if command_text == "git rev-parse HEAD" else ""
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=CLICK_REPLAY_ID,
        workspace=tmp_path,
        runner=runner,
    )
    row = outcome.to_record()
    detail = row["blocker_details"][0]

    assert detail["blocker_type"] == "prompt_spec"
    assert detail["failure_family"] == "prompt_spec_incomplete"
    assert "minimal_reproduction" in detail["missing_prompt_fields"]
    assert "default_map_mutation_timing" in detail["missing_prompt_fields"]
    assert detail["prompt_source"]["issue_number"] == 2745


def test_local_knowledge_drilldown_emits_required_categories(tmp_path: Path) -> None:
    replay_id = "pallets__click-issue-3298-pr-3299"
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    record = select_issue_pr_replay_record(manifest, replay_id)
    sha = record["repo_before_ref"]["sha"]

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        stdout = f"{sha}\n" if command_text == "git rev-parse HEAD" else ""
        return subprocess.CompletedProcess(command, returncode=0, stdout=stdout, stderr="")

    outcome = run_issue_pr_replay_preflight(
        manifest_path=MANIFEST_PATH,
        replay_id=replay_id,
        workspace=tmp_path,
        runner=runner,
    )
    detail = outcome.to_record()["blocker_details"][0]

    assert detail["blocker_type"] == "local_knowledge"
    assert detail["failure_family"] == "local_knowledge_missing"
    assert "click_parameter_default_handling" in detail["required_knowledge_categories"]
    assert "third_party_semver_version_reproduction" in detail["required_knowledge_categories"]
    assert "src/click/core.py" in detail["required_next_actions"][0]


def test_batch_summary_and_report_include_counts_and_deferred_labels(
    tmp_path: Path,
) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    records = select_issue_pr_replay_records(manifest, limit=2)
    sha_by_prefix = {
        record["repo_before_ref"]["sha"][:12]: record["repo_before_ref"]["sha"]
        for record in records
    }

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        if command_text == "git rev-parse HEAD":
            cwd_text = str(cwd)
            sha = next(
                full_sha
                for prefix, full_sha in sha_by_prefix.items()
                if prefix in cwd_text
            )
            return subprocess.CompletedProcess(command, returncode=0, stdout=f"{sha}\n", stderr="")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    outcomes = run_issue_pr_replay_preflight_batch(
        manifest_path=MANIFEST_PATH,
        workspace=tmp_path / "work",
        limit=2,
        runner=runner,
    )
    outcome_path = write_issue_pr_preflight_jsonl(
        outcomes,
        tmp_path / "outcomes.jsonl",
    )
    summary = summarize_issue_pr_preflight_outcomes(
        outcomes,
        outcome_path=outcome_path,
        report_path=tmp_path / "report.md",
        batch_runtime_seconds=1.25,
    )
    report_path = write_issue_pr_preflight_report(
        outcomes,
        tmp_path / "report.md",
        summary=summary,
    )

    assert len(outcomes) == 2
    assert summary["row_count"] == 2
    assert summary["status_counts"] == {"blocked": 2}
    assert summary["blocker_label_counts"] == {
        "local_knowledge_required": 1,
        "prompt_spec_ambiguous_or_incomplete": 1,
    }
    assert summary["residual_category_counts"] == {
        "local_knowledge": 1,
        "prompt_spec": 1,
    }
    assert summary["runtime_seconds"] == 1.25
    assert summary["command_stage_counts"]["baseline_validation"] == 2
    assert summary["first_failed_stage_counts"] == {"none": 2}
    assert summary["deferred_agent_residual_label_counts"] == {
        "materialization_gap": 1,
        "ranking_gap": 2,
    }
    assert summary["missing_prompt_field_counts"]["minimal_reproduction"] == 2
    report = report_path.read_text(encoding="utf-8")
    assert "Pre-edit replay preflight only" in report
    assert "Blocker Drilldown" in report
    assert REQUESTS_REPLAY_ID in report
    assert CLICK_REPLAY_ID in report


def test_validation_split_preflight_records_gap_status_and_next_row(
    tmp_path: Path,
) -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    records = [
        select_issue_pr_replay_record(manifest, PIP_REPLAY_ID),
        select_issue_pr_replay_record(manifest, SCRAPY_REPLAY_ID),
    ]
    sha_by_prefix = {
        record["repo_before_ref"]["sha"][:12]: record["repo_before_ref"]["sha"]
        for record in records
    }

    def runner(command: Command, cwd: Path | None, timeout_seconds: int):
        command_text = _command_text(command)
        if command_text == "git rev-parse HEAD":
            cwd_text = str(cwd)
            sha = next(
                full_sha
                for prefix, full_sha in sha_by_prefix.items()
                if prefix in cwd_text
            )
            return subprocess.CompletedProcess(
                command,
                returncode=0,
                stdout=f"{sha}\n",
                stderr="",
            )
        if command_text == "pytest tests/functional/test_install_reqs.py -q":
            return subprocess.CompletedProcess(
                command,
                returncode=4,
                stdout="",
                stderr="E   ModuleNotFoundError: No module named 'installer'",
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    outcomes = run_issue_pr_replay_preflight_batch(
        manifest_path=MANIFEST_PATH,
        workspace=tmp_path / "work",
        replay_ids=[PIP_REPLAY_ID, SCRAPY_REPLAY_ID],
        runner=runner,
    )
    rows = [outcome.to_record() for outcome in outcomes]
    summary = summarize_issue_pr_preflight_records(rows)

    pip_row, scrapy_row = rows
    assert classify_issue_pr_command_outcome(pip_row) == "dependency_fixture_setup_failure"
    assert pip_row["evidence_acquisition_status"] == "blocked_on_validation_recipe"
    pip_gaps = derive_issue_pr_pre_edit_evidence_gaps(pip_row)
    assert {gap["kind"] for gap in pip_gaps} == {
        "local_knowledge",
        "validation",
        "materialization",
        "ranking",
    }
    assert "pip_install_functional_test_fixtures" in pip_gaps[0][
        "required_knowledge_categories"
    ]

    assert classify_issue_pr_evidence_acquisition_status(scrapy_row) == (
        "ready_for_prompt_spec_and_local_knowledge"
    )
    assert scrapy_row["command_classification"] == "commands_passed"
    scrapy_gaps = derive_issue_pr_pre_edit_evidence_gaps(scrapy_row)
    assert {gap["kind"] for gap in scrapy_gaps} == {
        "prompt_spec",
        "local_knowledge",
        "ranking",
    }
    prompt_gap = next(gap for gap in scrapy_gaps if gap["kind"] == "prompt_spec")
    assert "downloader_slot_tie_breaking" in prompt_gap["missing_prompt_fields"]
    knowledge_gap = next(gap for gap in scrapy_gaps if gap["kind"] == "local_knowledge")
    assert "scrapy_downloader_aware_priority_queue" in knowledge_gap[
        "required_knowledge_categories"
    ]
    assert (
        summary["next_validation_split_row_ready_for_evidence_acquisition"]
        == SCRAPY_REPLAY_ID
    )
    assert summary["command_classification_counts"] == {
        "commands_passed": 1,
        "dependency_fixture_setup_failure": 1,
    }


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
    assert rows[0]["blocker_details"][0]["blocker_type"] == "local_knowledge"


def test_loads_existing_jsonl_and_writes_drilldown_records(tmp_path: Path) -> None:
    row = {
        "schema_version": "issue-pr-replay-preflight-v1",
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": CLICK_REPLAY_ID,
        "repo": "pallets/click",
        "validation_command": "pytest tests/test_defaults.py -q",
        "status": "blocked",
        "runtime_seconds": 0.1,
        "command_stages_reached": ["baseline_validation"],
        "first_failed_stage": "none",
        "command_results": [],
        "blocker_labels": ["prompt_spec_ambiguous_or_incomplete"],
        "residual_category": "prompt_spec",
        "provenance": {
            "prompt_text": "Fix default_map multi-value behavior",
            "prompt_source": {"issue_number": 2745, "pull_request_number": 3364},
            "accepted_change": {"changed_files": ["src/click/core.py"]},
            "deferred_agent_residual_labels": ["ranking_gap"],
        },
    }
    source_path = tmp_path / "source.jsonl"
    source_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    rows = load_issue_pr_preflight_jsonl(source_path)
    out_path = write_issue_pr_preflight_records_jsonl(rows, tmp_path / "out.jsonl")
    summary = summarize_issue_pr_preflight_records(rows, outcome_path=out_path)
    report_path = write_issue_pr_preflight_records_report(
        rows,
        tmp_path / "report.md",
        summary=summary,
    )

    written = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert written[0]["blocker_details"][0]["failure_family"] == "prompt_spec_incomplete"
    assert summary["missing_prompt_field_counts"]["minimal_reproduction"] == 1
    assert "DATA-007 Issue/PR Replay Blocker Drilldown" in report_path.read_text(
        encoding="utf-8"
    )


def test_classification_defers_agent_stage_labels() -> None:
    category, blockers = classify_pre_edit_residuals(
        ["materialization_gap", "ranking_gap"],
        validation_availability="available",
    )

    assert category == "none"
    assert blockers == []


def test_first_failed_stage_returns_none_when_commands_pass() -> None:
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
        workspace=Path("/tmp/j3-test-issue-pr-preflight"),
        runner=runner,
    )

    assert first_failed_stage(outcome.command_results) == "none"


def _command_text(command: Command) -> str:
    if isinstance(command, str):
        return command
    return " ".join(str(part) for part in command)
