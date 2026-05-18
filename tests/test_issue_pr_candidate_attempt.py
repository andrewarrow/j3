from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_attempt import (
    CLICK_DEFAULT_MAP_REPLAY_ID,
    CLICK_SEMVER_REPLAY_ID,
    PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    REQUESTS_REPLAY_ID,
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    main,
    run_click_default_map_issue_pr_candidate_attempt,
    run_click_semver_issue_pr_candidate_attempt,
    run_pytest_strict_addopts_issue_pr_candidate_attempt,
    run_pytest_timedelta_approx_issue_pr_candidate_attempt,
    run_requests_issue_pr_candidate_attempt,
    run_scrapy_downloader_aware_issue_pr_candidate_attempt,
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


def test_click_default_map_candidate_attempt_materializes_behavior_with_gap(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_checkout(tmp_path / "click")

    attempt = run_click_default_map_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        readiness_records=[_click_ready_row()],
        prompt_spec_records=[_click_prompt_spec_row()],
        validation_records=[_click_validation_row()],
    )
    record = attempt.to_record()

    assert record["replay_id"] == CLICK_DEFAULT_MAP_REPLAY_ID
    assert record["status"] == "materialized"
    assert record["mutation_scope"]["allowed_write_path_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        "src/click/core.py",
        "tests/test_defaults.py",
    ]
    assert record["mutation_scope"]["materialization_gap_paths"] == [
        "CHANGES.rst",
        "docs/commands.md",
        "docs/conf.py",
    ]
    assert record["structured_action_coverage"]["behavior_edit_covered"] is True
    assert record["structured_action_coverage"]["accepted_edit_covered"] is False
    assert (
        record["structured_action_coverage"]["materialization_gap"]
        == "accepted_auxiliary_changelog_docs_config_materialization_gap"
    )
    assert "accepted_auxiliary_paths_not_materialized" in record["residual_labels"]
    assert "value = self.type.split_envvar_value(value)" in (
        repo / "src" / "click" / "core.py"
    ).read_text(encoding="utf-8")
    assert "test_default_map_nargs" in (
        repo / "tests" / "test_defaults.py"
    ).read_text(encoding="utf-8")
    assert "test_default_map_nargs" in record["test_materialization"]["diff"]


def test_click_default_map_candidate_attempt_validation_and_report(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_checkout(tmp_path / "click")

    attempt = run_click_default_map_issue_pr_candidate_attempt(
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
    assert record["residual_labels"] == [
        "candidate_validation_passed",
        "accepted_auxiliary_paths_not_materialized",
    ]
    report = write_issue_pr_candidate_attempt_report(attempt, tmp_path / "click.md")
    assert "DATA-014 Click default_map Issue/PR Candidate Attempt" in report.read_text(
        encoding="utf-8"
    )


def test_click_default_map_candidate_attempt_cli_writes_json_and_report(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_checkout(tmp_path / "click")
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "candidate.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            CLICK_DEFAULT_MAP_REPLAY_ID,
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
    assert record["replay_id"] == CLICK_DEFAULT_MAP_REPLAY_ID
    assert record["status"] == "validated"
    assert report_path.exists()


def test_click_semver_candidate_attempt_materializes_source_and_test(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_semver_checkout(tmp_path / "click")

    attempt = run_click_semver_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        readiness_records=[_click_semver_ready_row()],
        prompt_spec_records=[_click_semver_prompt_spec_row()],
        validation_records=[_click_semver_validation_row()],
        local_knowledge_records=[
            _click_semver_knowledge_row("click_non_string_default_handling"),
            _click_semver_knowledge_row("click_empty_string_check_semantics"),
        ],
    )
    record = attempt.to_record()

    assert record["replay_id"] == CLICK_SEMVER_REPLAY_ID
    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["allowed_write_path_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        "src/click/core.py",
        "tests/test_options.py",
    ]
    assert record["mutation_scope"]["materialization_gap_paths"] == []
    assert record["structured_action_coverage"]["accepted_edit_covered"] is True
    assert record["structured_action_coverage"]["behavior_edit_covered"] is True
    assert record["structured_action_coverage"]["materialization_gap"] is None
    assert len(record["evidence"]["local_knowledge"]) == 2
    assert 'elif isinstance(default_value, str) and default_value == "":' in (
        repo / "src" / "click" / "core.py"
    ).read_text(encoding="utf-8")
    assert "class _StrictEq" in (repo / "tests" / "test_options.py").read_text(
        encoding="utf-8"
    )
    assert "non-string-comparable-object" in record["test_materialization"]["diff"]


def test_click_semver_candidate_attempt_plan_only_records_planned_scope(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_semver_checkout(tmp_path / "click")

    attempt = run_click_semver_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=False,
        validate=False,
    )
    record = attempt.to_record()

    assert record["status"] == "planned"
    assert record["mutation_scope"]["files_changed"] == [
        "src/click/core.py",
        "tests/test_options.py",
    ]
    assert 'elif default_value == "":' in (
        repo / "src" / "click" / "core.py"
    ).read_text(encoding="utf-8")
    assert "class _StrictEq" not in (repo / "tests" / "test_options.py").read_text(
        encoding="utf-8"
    )


def test_click_semver_candidate_attempt_validation_and_report(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_semver_checkout(tmp_path / "click")

    attempt = run_click_semver_issue_pr_candidate_attempt(
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
    report = write_issue_pr_candidate_attempt_report(attempt, tmp_path / "semver.md")
    assert "DATA-016 Click semver Issue/PR Candidate Attempt" in report.read_text(
        encoding="utf-8"
    )


def test_click_semver_candidate_attempt_cli_writes_json_and_report(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_click_semver_checkout(tmp_path / "click")
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "candidate.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            CLICK_SEMVER_REPLAY_ID,
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
    assert record["replay_id"] == CLICK_SEMVER_REPLAY_ID
    assert record["status"] == "validated"
    assert report_path.exists()


def test_pytest_strict_addopts_candidate_materializes_source_test_only(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_pytest_checkout(tmp_path / "pytest")

    attempt = run_pytest_strict_addopts_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        readiness_records=[_pytest_strict_addopts_ready_row()],
        prompt_spec_records=[_pytest_strict_addopts_prompt_spec_row()],
        validation_records=[_pytest_strict_addopts_validation_row()],
        local_knowledge_records=[
            _pytest_strict_addopts_knowledge_row("repo_changed_file_context"),
            _pytest_strict_addopts_knowledge_row("pytest_repo_test_patterns"),
        ],
        materialization_audit_records=[
            _pytest_strict_addopts_audit_row("src/_pytest/config/__init__.py"),
            _pytest_strict_addopts_audit_row("testing/test_config.py"),
            _pytest_strict_addopts_audit_row("testing/test_mark.py"),
        ],
    )
    record = attempt.to_record()

    assert record["replay_id"] == PYTEST_STRICT_ADDOPTS_REPLAY_ID
    assert record["status"] == "materialized"
    assert record["mutation_scope"]["allowed_write_path_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        "src/_pytest/config/__init__.py",
        "testing/test_config.py",
        "testing/test_mark.py",
    ]
    assert record["mutation_scope"]["materialization_gap_paths"] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
    ]
    assert record["structured_action_coverage"]["behavior_edit_covered"] is True
    assert record["structured_action_coverage"]["accepted_edit_covered"] is False
    assert "accepted_auxiliary_paths_not_materialized" in record["residual_labels"]
    assert len(record["evidence"]["materialization_audit"]) == 3
    assert "from .findpaths import parse_override_ini" in (
        repo / "src" / "_pytest" / "config" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "addopts = --strict-config" in (
        repo / "testing" / "test_config.py"
    ).read_text(encoding="utf-8")
    assert "addopts = --strict-markers" in (
        repo / "testing" / "test_mark.py"
    ).read_text(encoding="utf-8")
    assert not (repo / "changelog" / "14442.bugfix.rst").exists()
    assert (repo / "AUTHORS").read_text(encoding="utf-8") == "Existing Author\n"


def test_pytest_strict_addopts_candidate_materializes_full_scope(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_pytest_checkout(tmp_path / "pytest")
    (repo / "AUTHORS").write_text(
        "\n".join(
            [
                "Holger Krekel",
                "",
                "Contributors include::",
                "",
                "Guoqiang Zhang",
                "Harald Armin Massa",
                "Prakhar Gurunani",
                "Prashant Anand",
                "Éloi Rivard",
                "",
            ]
        ),
        encoding="utf-8",
    )

    attempt = run_pytest_strict_addopts_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        include_auxiliary_paths=True,
        readiness_records=[_pytest_strict_addopts_ready_row()],
        prompt_spec_records=[_pytest_strict_addopts_prompt_spec_row()],
        validation_records=[_pytest_strict_addopts_validation_row()],
        local_knowledge_records=[
            _pytest_strict_addopts_knowledge_row("repo_changed_file_context"),
            _pytest_strict_addopts_knowledge_row(
                "pytest_changelog_fragment_convention"
            ),
            _pytest_strict_addopts_knowledge_row("pytest_authors_convention"),
        ],
        materialization_audit_records=[
            _pytest_strict_addopts_audit_row("AUTHORS"),
            _pytest_strict_addopts_audit_row("changelog/14442.bugfix.rst"),
            _pytest_strict_addopts_audit_row("src/_pytest/config/__init__.py"),
            _pytest_strict_addopts_audit_row("testing/test_config.py"),
            _pytest_strict_addopts_audit_row("testing/test_mark.py"),
        ],
    )
    record = attempt.to_record()

    assert record["action_family"] == "pytest_strict_addopts_full_scope_candidate"
    assert record["status"] == "materialized"
    assert set(record["mutation_scope"]["files_changed"]) == {
        "AUTHORS",
        "changelog/14442.bugfix.rst",
        "src/_pytest/config/__init__.py",
        "testing/test_config.py",
        "testing/test_mark.py",
    }
    assert record["mutation_scope"]["materialization_gap_paths"] == []
    assert record["mutation_scope"]["accepted_missing_paths"] == []
    assert record["mutation_scope"]["full_accepted_edit_coverage_expressible"] is True
    assert record["structured_action_coverage"]["behavior_edit_covered"] is True
    assert record["structured_action_coverage"]["auxiliary_edit_covered"] is True
    assert record["structured_action_coverage"]["accepted_edit_covered"] is True
    assert record["structured_action_coverage"]["materialization_gap"] is None
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert len(record["evidence"]["materialization_audit"]) == 5
    authors_lines = (repo / "AUTHORS").read_text(encoding="utf-8").splitlines()
    assert authors_lines.index("Guoqiang Zhang") < authors_lines.index("Hamza Mobeen")
    assert authors_lines.index("Hamza Mobeen") < authors_lines.index(
        "Harald Armin Massa"
    )
    assert authors_lines.index("Prakhar Gurunani") < authors_lines.index(
        "Praneeth Kodumagulla"
    )
    assert authors_lines.index("Praneeth Kodumagulla") < authors_lines.index(
        "Prashant Anand"
    )
    changelog = (repo / "changelog" / "14442.bugfix.rst").read_text(
        encoding="utf-8"
    )
    assert ":option:`--strict-markers`" in changelog
    assert ":confval:`addopts`" in changelog
    assert "changelog/14442.bugfix.rst" in record["auxiliary_materialization"][
        "targets"
    ][1]["diff"]


def test_pytest_strict_addopts_candidate_validation_report_and_cli(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_pytest_checkout(tmp_path / "pytest")
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "candidate.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            PYTEST_STRICT_ADDOPTS_REPLAY_ID,
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
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == [
        "candidate_validation_passed",
        "accepted_auxiliary_paths_not_materialized",
    ]
    assert "DATA-024 Pytest #14442" in report_path.read_text(encoding="utf-8")


def test_pytest_timedelta_approx_candidate_materializes_source_and_test(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_pytest_timedelta_approx_checkout(tmp_path / "pytest")

    attempt = run_pytest_timedelta_approx_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        readiness_records=[_pytest_timedelta_approx_ready_row()],
        prompt_spec_records=[_pytest_timedelta_approx_prompt_spec_row()],
        validation_records=[_pytest_timedelta_approx_validation_row()],
        local_knowledge_records=[
            _pytest_timedelta_approx_knowledge_row("repo_changed_file_context"),
            _pytest_timedelta_approx_knowledge_row(
                "pytest_approx_timedelta_tolerance_semantics"
            ),
            _pytest_timedelta_approx_knowledge_row(
                "pytest_datetime_timedelta_comparison_behavior"
            ),
        ],
        materialization_audit_records=[
            _pytest_timedelta_approx_audit_row("src/_pytest/python_api.py"),
            _pytest_timedelta_approx_audit_row("testing/python/approx.py"),
        ],
    )
    record = attempt.to_record()

    assert record["replay_id"] == PYTEST_TIMEDELTA_APPROX_REPLAY_ID
    assert record["action_family"] == "pytest_timedelta_approx_source_test_candidate"
    assert record["status"] == "materialized"
    assert record["mutation_scope"]["allowed_write_path_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        "src/_pytest/python_api.py",
        "testing/python/approx.py",
    ]
    assert record["mutation_scope"]["accepted_missing_paths"] == []
    assert record["mutation_scope"]["full_accepted_edit_coverage_expressible"] is True
    assert record["structured_action_coverage"]["accepted_edit_covered"] is True
    assert record["structured_action_coverage"]["materialization_gap"] is None
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert len(record["evidence"]["materialization_audit"]) == 2
    assert len(record["evidence"]["local_knowledge"]) == 3

    source = (repo / "src" / "_pytest" / "python_api.py").read_text(encoding="utf-8")
    assert "def _approx_scalar(self, x) -> ApproxBase:" in source
    assert "if isinstance(x, (datetime, timedelta)):" in source
    assert "relative tolerance for timedelta must be a" in source
    assert 'f"number, got {type(rel).__name__}"' in source
    assert "rel_tolerance = rel * builtins.abs(expected)" in source
    assert "datetime comparisons. Use abs=timedelta" in source
    assert "rel=rel, abs=tolerance" in source

    tests = (repo / "testing" / "python" / "approx.py").read_text(encoding="utf-8")
    assert "assert td1 == approx(td2, rel=0.01)" in tests
    assert "def test_timedelta_rel_must_be_number" in tests
    assert "def test_timedelta_rel_scales_with_expected" in tests
    assert "def test_timedelta_in_sequence" in tests
    assert "def test_datetime_in_mapping" in tests
    assert "assert td1 == approx(td2, rel=timedelta(seconds=1))" not in tests
    assert "assert td1 != approx(td2, rel=timedelta(seconds=1))" not in tests


def test_pytest_timedelta_approx_candidate_plan_only_records_scope(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_pytest_timedelta_approx_checkout(tmp_path / "pytest")

    attempt = run_pytest_timedelta_approx_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=False,
        validate=False,
    )
    record = attempt.to_record()

    assert record["status"] == "planned"
    assert record["mutation_scope"]["files_changed"] == [
        "src/_pytest/python_api.py",
        "testing/python/approx.py",
    ]
    source = (repo / "src" / "_pytest" / "python_api.py").read_text(encoding="utf-8")
    tests = (repo / "testing" / "python" / "approx.py").read_text(encoding="utf-8")
    assert "def _approx_scalar(self, x) -> ApproxScalar:" in source
    assert "assert td1 == approx(td2, rel=timedelta(seconds=1))" in tests


def test_pytest_timedelta_approx_candidate_validation_report_and_cli(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_pytest_timedelta_approx_checkout(tmp_path / "pytest")
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "candidate.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
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
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]
    assert "DATA-029 Pytest #14462" in report_path.read_text(encoding="utf-8")


def test_scrapy_downloader_aware_candidate_materializes_source_and_tests(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_scrapy_checkout(tmp_path / "scrapy")

    attempt = run_scrapy_downloader_aware_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=True,
        validate=False,
        readiness_records=[_scrapy_downloader_aware_ready_row()],
        prompt_spec_records=[_scrapy_downloader_aware_prompt_spec_row()],
        validation_records=[_scrapy_downloader_aware_validation_row()],
        local_knowledge_records=[
            _scrapy_downloader_aware_knowledge_row(
                "scrapy_downloader_aware_priority_queue"
            ),
            _scrapy_downloader_aware_knowledge_row(
                "scrapy_slot_active_download_accounting"
            ),
            _scrapy_downloader_aware_knowledge_row("scrapy_pqueue_test_patterns"),
        ],
        materialization_audit_records=[
            _scrapy_downloader_aware_audit_row("scrapy/pqueues.py"),
            _scrapy_downloader_aware_audit_row("tests/test_pqueues.py"),
        ],
    )
    record = attempt.to_record()

    assert record["replay_id"] == SCRAPY_DOWNLOADER_AWARE_REPLAY_ID
    assert record["action_family"] == (
        "scrapy_downloader_aware_slot_rotation_source_test_candidate"
    )
    assert record["status"] == "materialized"
    assert record["mutation_scope"]["allowed_write_path_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        "scrapy/pqueues.py",
        "tests/test_pqueues.py",
    ]
    assert record["mutation_scope"]["accepted_missing_paths"] == []
    assert record["mutation_scope"]["full_accepted_edit_coverage_expressible"] is True
    assert record["structured_action_coverage"]["accepted_edit_covered"] is True
    assert record["structured_action_coverage"]["materialization_gap"] is None
    assert record["validation"]["validation_command"] == (
        "python -m py_compile scrapy/pqueues.py && pytest tests/test_pqueues.py -q"
    )
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert len(record["evidence"]["local_knowledge"]) == 3
    assert len(record["evidence"]["materialization_audit"]) == 2

    source = (repo / "scrapy" / "pqueues.py").read_text(encoding="utf-8")
    assert "self._last_selected_slot: str | None = None" in source
    assert "def _next_slot(" in source
    assert "slot = self._next_slot(stats, update_state=True)" in source
    assert "slot = self._next_slot(stats, update_state=False)" in source

    tests = (repo / "tests" / "test_pqueues.py").read_text(encoding="utf-8")
    assert "from scrapy.core.downloader import Downloader" in tests
    assert "def test_tie_breaking_rotates_slots" in tests
    assert (
        "def test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted" in tests
    )
    assert 'assert slots == ["slot-a", "slot-b", "slot-a", "slot-b"]' in tests
    assert 'assert slots == ["slot-a", "slot-b", "slot-c", "slot-a"]' in tests


def test_scrapy_downloader_aware_candidate_plan_only_records_scope(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_scrapy_checkout(tmp_path / "scrapy")

    attempt = run_scrapy_downloader_aware_issue_pr_candidate_attempt(
        repo,
        manifest_path=MANIFEST_PATH,
        write=False,
        validate=False,
    )
    record = attempt.to_record()

    assert record["status"] == "planned"
    assert record["mutation_scope"]["files_changed"] == [
        "scrapy/pqueues.py",
        "tests/test_pqueues.py",
    ]
    source = (repo / "scrapy" / "pqueues.py").read_text(encoding="utf-8")
    tests = (repo / "tests" / "test_pqueues.py").read_text(encoding="utf-8")
    assert "self._last_selected_slot: str | None = None" not in source
    assert "from scrapy.core.downloader import Downloader" not in tests


def test_scrapy_downloader_aware_candidate_validation_report_and_cli(
    tmp_path: Path,
) -> None:
    repo = _write_synthetic_scrapy_checkout(tmp_path / "scrapy")
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "candidate.md"

    exit_code = main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--replay-id",
            SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
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
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]
    assert "DATA-035 Scrapy #7293" in report_path.read_text(encoding="utf-8")


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


def _write_synthetic_scrapy_checkout(repo: Path) -> Path:
    (repo / "scrapy").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "scrapy" / "pqueues.py").write_text(
        """from __future__ import annotations

from typing import Iterable, Self


class Crawler:
    settings = {}
    engine = None


class QueueProtocol:
    def push(self, request: Request) -> None:
        pass

    def pop(self) -> Request | None:
        return None

    def peek(self) -> Request | None:
        return None

    def close(self) -> list[int]:
        return []

    def __len__(self) -> int:
        return 0


class Request:
    def __init__(self, url: str):
        self.url = url
        self.meta = {}


class Downloader:
    def get_slot_key(self, request: Request) -> str:
        return str(request.meta.get("slot", "default"))


class ScrapyPriorityQueue:
    def __init__(
        self,
        crawler: Crawler,
        downstream_queue_cls: type[QueueProtocol],
        key: str,
        startprios: Iterable[int] = (),
        *,
        start_queue_cls: type[QueueProtocol] | None = None,
    ) -> None:
        self.key = key

    def push(self, request: Request) -> None:
        pass

    def pop(self) -> Request | None:
        return None

    def peek(self) -> Request | None:
        return None

    def close(self) -> list[int]:
        return []

    def __len__(self) -> int:
        return 0


def _path_safe(slot: str) -> str:
    return slot


class DownloaderInterface:
    def __init__(self, crawler: Crawler):
        assert crawler.engine
        self.downloader: Downloader = crawler.engine.downloader

    def stats(self, possible_slots: Iterable[str]) -> list[tuple[int, str]]:
        return [(self._active_downloads(slot), slot) for slot in possible_slots]

    def get_slot_key(self, request: Request) -> str:
        return self.downloader.get_slot_key(request)

    def _active_downloads(self, slot: str) -> int:
        return 0


class DownloaderAwarePriorityQueue:
    @classmethod
    def from_crawler(
        cls,
        crawler: Crawler,
        downstream_queue_cls: type[QueueProtocol],
        key: str,
        startprios: dict[str, Iterable[int]] | None = None,
        *,
        start_queue_cls: type[QueueProtocol] | None = None,
    ) -> Self:
        return cls(
            crawler,
            downstream_queue_cls,
            key,
            startprios,
            start_queue_cls=start_queue_cls,
        )

    def __init__(
        self,
        crawler: Crawler,
        downstream_queue_cls: type[QueueProtocol],
        key: str,
        slot_startprios: dict[str, Iterable[int]] | None = None,
        *,
        start_queue_cls: type[QueueProtocol] | None = None,
    ):
        self._downloader_interface: DownloaderInterface = DownloaderInterface(crawler)
        self.downstream_queue_cls: type[QueueProtocol] = downstream_queue_cls
        self._start_queue_cls: type[QueueProtocol] | None = start_queue_cls
        self.key: str = key
        self.crawler: Crawler = crawler

        self.pqueues: dict[str, ScrapyPriorityQueue] = {}  # slot -> priority queue
        if slot_startprios:
            for slot, startprios in slot_startprios.items():
                self.pqueues[slot] = self.pqfactory(slot, startprios)

    def pqfactory(
        self, slot: str, startprios: Iterable[int] = ()
    ) -> ScrapyPriorityQueue:
        return ScrapyPriorityQueue(
            self.crawler,
            self.downstream_queue_cls,
            self.key + "/" + _path_safe(slot),
            startprios,
            start_queue_cls=self._start_queue_cls,
        )

    def pop(self) -> Request | None:
        stats = self._downloader_interface.stats(self.pqueues)

        if not stats:
            return None

        slot = min(stats)[1]
        queue = self.pqueues[slot]
        request = queue.pop()
        if len(queue) == 0:
            del self.pqueues[slot]
        return request

    def push(self, request: Request) -> None:
        slot = self._downloader_interface.get_slot_key(request)
        if slot not in self.pqueues:
            self.pqueues[slot] = self.pqfactory(slot)
        queue = self.pqueues[slot]
        queue.push(request)

    def peek(self) -> Request | None:
        stats = self._downloader_interface.stats(self.pqueues)
        if not stats:
            return None
        slot = min(stats)[1]
        queue = self.pqueues[slot]
        return queue.peek()

    def close(self) -> dict[str, list[int]]:
        active = {slot: queue.close() for slot, queue in self.pqueues.items()}
        self.pqueues.clear()
        return active
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_pqueues.py").write_text(
        """import tempfile
from unittest.mock import Mock

import pytest
import queuelib

from scrapy.http.request import Request
from scrapy.pqueues import DownloaderAwarePriorityQueue, ScrapyPriorityQueue
from scrapy.spiders import Spider
from scrapy.squeues import FifoMemoryQueue
from scrapy.utils.misc import build_from_crawler, load_object
from scrapy.utils.test import get_crawler
from tests.test_scheduler import MockDownloader


class TestPriorityQueue:
    def setup_method(self):
        self.crawler = get_crawler(Spider)
        self.spider = self.crawler._create_spider("foo")


class TestDownloaderAwarePriorityQueue:
    def setup_method(self):
        crawler = get_crawler(Spider)
        crawler.engine = Mock(downloader=MockDownloader())
        self.queue = DownloaderAwarePriorityQueue.from_crawler(
            crawler=crawler,
            downstream_queue_cls=FifoMemoryQueue,
            key="foo/bar",
        )

    def teardown_method(self):
        self.queue.close()

    def test_push_pop(self):
        assert len(self.queue) == 0
        assert self.queue.pop() is None
        req1 = Request("http://www.example.com/1")
        req2 = Request("http://www.example.com/2")
        req3 = Request("http://www.example.com/3")
        self.queue.push(req1)
        self.queue.push(req2)
        self.queue.push(req3)
        assert len(self.queue) == 3
        assert self.queue.pop().url == req1.url
        assert len(self.queue) == 2
        assert self.queue.pop().url == req2.url
        assert len(self.queue) == 1
        assert self.queue.pop().url == req3.url
        assert len(self.queue) == 0
        assert self.queue.pop() is None

    def test_no_peek_raises(self):
        if hasattr(queuelib.queue.FifoMemoryQueue, "peek"):
            pytest.skip("queuelib.queue.FifoMemoryQueue.peek is defined")
        self.queue.push(Request("https://example.org"))
        with pytest.raises(
            NotImplementedError,
            match="The underlying queue class does not implement 'peek'",
        ):
            self.queue.peek()

    def test_peek(self):
        if not hasattr(queuelib.queue.FifoMemoryQueue, "peek"):
            pytest.skip("queuelib.queue.FifoMemoryQueue.peek is undefined")
        assert len(self.queue) == 0
        req1 = Request("https://example.org/1")
        req2 = Request("https://example.org/2")
        req3 = Request("https://example.org/3")
        self.queue.push(req1)
        self.queue.push(req2)
        self.queue.push(req3)
        assert len(self.queue) == 3
        assert self.queue.peek().url == req1.url
        assert self.queue.pop().url == req1.url
        assert len(self.queue) == 2
        assert self.queue.peek().url == req2.url
        assert self.queue.pop().url == req2.url
        assert len(self.queue) == 1
        assert self.queue.peek().url == req3.url
        assert self.queue.pop().url == req3.url
        assert self.queue.peek() is None


@pytest.mark.parametrize(
    ("input_", "output"),
    [
        ([{}, {}], [2, 1]),
    ],
)
def test_pop_order(input_, output):
    assert input_
    assert output
""",
        encoding="utf-8",
    )
    return repo


def _write_synthetic_pytest_checkout(repo: Path) -> Path:
    (repo / "src" / "_pytest" / "config").mkdir(parents=True)
    (repo / "testing").mkdir(parents=True)
    (repo / "changelog").mkdir()
    (repo / "AUTHORS").write_text("Existing Author\n", encoding="utf-8")
    (repo / "src" / "_pytest" / "config" / "__init__.py").write_text(
        """from __future__ import annotations

import copy
import os
import shlex

from .findpaths import determine_setup


class Config:
    def parse(self, args: list[str], addopts: bool = True) -> None:
        if addopts:
            env_addopts = os.environ.get("PYTEST_ADDOPTS", "")
            if len(env_addopts):
                args[:] = (
                    self._validate_args(shlex.split(env_addopts), "via PYTEST_ADDOPTS")
                    + args
                )

        ns = self._parser.parse_known_args(args, namespace=copy.copy(self.option))
        rootpath, inipath, inicfg, ignored_config_files = determine_setup(
            inifile=ns.inifilename,
            override_ini=ns.override_ini,
            args=ns.file_or_dir,
            rootdir_cmd_arg=ns.rootdir or None,
            invocation_dir=self.invocation_params.dir,
        )
        self._rootpath = rootpath
        self._inipath = inipath
        self._ignored_config_files = ignored_config_files
        self._inicfg = inicfg

        self._parser.addini("addopts", "Extra command line options", "args")

        if addopts:
            args[:] = (
                self._validate_args(self.getini("addopts"), "via addopts config") + args
            )

        self.known_args_namespace = self._parser.parse_known_args(
            args, namespace=copy.copy(self.option)
        )
        self._checkversion()
""",
        encoding="utf-8",
    )
    (repo / "testing" / "test_config.py").write_text(
        """import pytest


class TestParseIni:
    @pytest.mark.parametrize("option_name", ["strict_config", "strict"])
    def test_strict_config_ini_option(
        self, pytester: Pytester, option_name: str
    ) -> None:
        \"\"\"Test that strict_config and strict ini options enable strict config checking.\"\"\"
        pytester.makeini(
            f\"\"\"
            [pytest]
            unknown_option = 1
            {option_name} = True
            \"\"\"
        )
        result = pytester.runpytest()
        result.stderr.fnmatch_lines("ERROR: Unknown config option: unknown_option")
        assert result.ret == pytest.ExitCode.USAGE_ERROR
""",
        encoding="utf-8",
    )
    (repo / "testing" / "test_mark.py").write_text(
        """import pytest


@pytest.mark.parametrize(
    "option_name", ["--strict-markers", "--strict", "strict_markers", "strict"]
)
def test_strict_prohibits_unregistered_markers(
    pytester: Pytester, option_name: str
) -> None:
    pytester.makepyfile(
        \"\"\"
        import pytest
        @pytest.mark.unregisteredmark
        def test_hello():
            pass
    \"\"\"
    )
    if option_name in ("strict_markers", "strict"):
        pytester.makeini(
            f\"\"\"
            [pytest]
            {option_name} = true
            \"\"\"
        )
        result = pytester.runpytest()
    else:
        result = pytester.runpytest(option_name)
    assert result.ret != 0
    result.stdout.fnmatch_lines(
        ["'unregisteredmark' not found in `markers` configuration option"]
    )
""",
        encoding="utf-8",
    )
    return repo


def _write_synthetic_pytest_timedelta_approx_checkout(repo: Path) -> Path:
    (repo / "src" / "_pytest").mkdir(parents=True)
    (repo / "testing" / "python").mkdir(parents=True)
    (repo / "src" / "_pytest" / "python_api.py").write_text(
        """from __future__ import annotations

import builtins
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sized
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
import math
from typing import Any


class ApproxBase:
    def __init__(self, expected, rel=None, abs=None, nan_ok: bool = False) -> None:
        self.expected = expected
        self.abs = abs
        self.rel = rel
        self.nan_ok = nan_ok

    def _approx_scalar(self, x) -> ApproxScalar:
        if isinstance(x, Decimal):
            return ApproxDecimal(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)
        return ApproxScalar(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)


class ApproxScalar(ApproxBase):
    pass


class ApproxDecimal(ApproxScalar):
    pass


class ApproxTimedelta(ApproxBase):
    \"\"\"Perform approximate comparisons where the expected value is a
    datetime or timedelta.

    Requires an explicit tolerance as a timedelta.
    Relative tolerance is not supported for datetime comparisons.
    \"\"\"

    def __init__(self, expected, rel=None, abs=None, nan_ok: bool = False) -> None:
        if isinstance(expected, datetime) and rel is not None:
            raise TypeError(
                "pytest.approx() does not support relative tolerance for "
                "datetime comparisons. Use abs=timedelta(...) instead."
            )
        if nan_ok:
            raise TypeError(
                "pytest.approx() does not support nan_ok for "
                "datetime/timedelta comparisons."
            )
        if abs is None and rel is None:
            raise TypeError(
                "pytest.approx() requires an explicit tolerance for "
                "datetime/timedelta comparisons: "
                "e.g. approx(expected, abs=timedelta(seconds=1))"
            )
        if abs is not None and not isinstance(abs, timedelta):
            raise TypeError(
                f"absolute tolerance for datetime/timedelta must be a "
                f"timedelta, got {type(abs).__name__}"
            )
        if rel is not None and not isinstance(rel, timedelta):
            raise TypeError(
                f"relative tolerance for timedelta must be a "
                f"timedelta, got {type(rel).__name__}"
            )
        tolerance = max(t for t in (abs, rel) if t is not None)
        super().__init__(expected, rel=None, abs=tolerance, nan_ok=False)

    def __repr__(self) -> str:
        return f"{self.expected} ± {self.abs}"


def _is_sequence_like(expected: object) -> bool:
    return (
        hasattr(expected, "__getitem__")
        and isinstance(expected, Sized)
        and not isinstance(expected, str | bytes)
    )


def _is_numpy_array(obj: object) -> bool:
    return False


def _as_numpy_array(obj: object) -> object:
    return obj


def approx(
    expected: Any,
    rel: float | Decimal | timedelta | None = None,
    abs: float | Decimal | timedelta | None = None,
    nan_ok: bool = False,
) -> ApproxBase:
    \"\"\"Assert that two numbers are equal to each other within some tolerance.

    **datetime and timedelta**

    You can also use ``approx`` to compare :class:`~datetime.datetime` and
    :class:`~datetime.timedelta` objects by specifying an absolute tolerance
    as a :class:`~datetime.timedelta`::

        >>> from datetime import datetime, timedelta
        >>> dt1 = datetime(2024, 1, 1, 12, 0, 0)
        >>> dt2 = datetime(2024, 1, 1, 12, 0, 0, 500000)
        >>> dt1 == approx(dt2, abs=timedelta(seconds=1))
        True

    Note that ``rel`` is not supported for datetime comparisons,
    and ``abs`` or ``rel`` must be explicitly provided as a ``timedelta`` object.
    \"\"\"
    if isinstance(expected, Decimal):
        cls: type[ApproxBase] = ApproxDecimal
    elif isinstance(expected, Mapping):
        cls = ApproxBase
    elif _is_numpy_array(expected):
        expected = _as_numpy_array(expected)
        cls = ApproxBase
    elif _is_sequence_like(expected):
        cls = ApproxBase
    elif isinstance(expected, Collection) and not isinstance(expected, str | bytes):
        msg = f"pytest.approx() only supports ordered sequences, but got: {expected!r}"
        raise TypeError(msg)
    elif isinstance(expected, (datetime, timedelta)):
        cls = ApproxTimedelta
    else:
        cls = ApproxScalar
    return cls(expected, rel, abs, nan_ok)
""",
        encoding="utf-8",
    )
    (repo / "testing" / "python" / "approx.py").write_text(
        """import pytest
from pytest import approx


class TestApproxDatetime:
    \"\"\"Tests for datetime/timedelta support in approx (issue #8395).\"\"\"

    def test_timedelta_rel_within_tolerance(self):
        from datetime import timedelta

        td1 = timedelta(seconds=100)
        td2 = timedelta(seconds=100.5)
        assert td1 == approx(td2, rel=timedelta(seconds=1))

    def test_timedelta_rel_outside_tolerance(self):
        from datetime import timedelta

        td1 = timedelta(seconds=100)
        td2 = timedelta(seconds=102)
        assert td1 != approx(td2, rel=timedelta(seconds=1))

    def test_datetime_rejects_rel(self):
        from datetime import datetime
        from datetime import timedelta

        with pytest.raises(TypeError, match="does not support relative tolerance"):
            approx(datetime(2024, 1, 1), rel=0.1, abs=timedelta(seconds=1))

        with pytest.raises(TypeError, match="does not support relative tolerance"):
            approx(datetime(2024, 1, 1), rel=timedelta(seconds=1))

    def test_abs_must_be_timedelta(self):
        from datetime import datetime

        with pytest.raises(TypeError, match="must be a timedelta"):
            approx(datetime(2024, 1, 1), abs=1.0)

    def test_timedelta_rel_must_be_timedelta(self):
        from datetime import timedelta

        with pytest.raises(TypeError, match="must be a timedelta"):
            approx(timedelta(seconds=1), rel=0.1)

    def test_rejects_nan_ok(self):
        from datetime import datetime
        from datetime import timedelta

        with pytest.raises(TypeError, match="does not support nan_ok"):
            approx(datetime(2024, 1, 1), abs=timedelta(seconds=1), nan_ok=True)

    def test_repr_compare_with_incompatible_type(self):
        result = ["comparison failed", "Obtained: x", "Expected: y", "N/A"]
        assert "comparison failed" in result[0]
        assert "N/A" in result[3]


class MyVec3:
    pass
""",
        encoding="utf-8",
    )
    return repo


def _write_synthetic_click_checkout(repo: Path) -> Path:
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "CHANGES.rst").write_text("Version 8.3.0\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "commands.md").write_text("# Commands\n", encoding="utf-8")
    (repo / "docs" / "conf.py").write_text("nitpicky = True\n", encoding="utf-8")
    (repo / "src" / "click" / "core.py").write_text(
        """from __future__ import annotations

import typing as t


UNSET = object()


class ParameterSource:
    COMMANDLINE = "COMMANDLINE"
    DEFAULT = "DEFAULT"
    DEFAULT_MAP = "DEFAULT_MAP"
    ENVIRONMENT = "ENVIRONMENT"


class Parameter:
    nargs = 1

    def value_from_envvar(self, ctx):
        return None

    def get_default(self, ctx):
        return UNSET

    def consume_value(self, ctx, opts) -> t.Any:
        value = opts.get(self.name, UNSET)  # type: ignore
        source = (
            ParameterSource.COMMANDLINE
            if value is not UNSET
            else ParameterSource.DEFAULT
        )

        if value is UNSET:
            envvar_value = self.value_from_envvar(ctx)
            if envvar_value is not None:
                value = envvar_value
                source = ParameterSource.ENVIRONMENT

        if value is UNSET:
            default_map_value = ctx.lookup_default(self.name)  # type: ignore[arg-type]
            if default_map_value is not None or ctx._default_map_has(self.name):
                value = default_map_value
                source = ParameterSource.DEFAULT_MAP

        if value is UNSET:
            default_value = self.get_default(ctx)
            if default_value is not UNSET:
                value = default_value
                source = ParameterSource.DEFAULT

        return value, source
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_defaults.py").write_text(
        """import click
import pytest


def test_default_map_with_callable_flag_value(runner, default_map, args, expected):
    assert True


def test_unset_in_default_map(runner):
    assert True
""",
        encoding="utf-8",
    )
    return repo


def _write_synthetic_click_semver_checkout(repo: Path) -> Path:
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "click" / "core.py").write_text(
        """from __future__ import annotations

import inspect


UNSET = object()


class Option:
    is_bool_flag = False
    secondary_opts = []
    show_default = True
    default = ""

    def __init__(self, param_decls, default="", show_default=True):
        self.param_decls = param_decls
        self.default = default
        self.show_default = show_default

    def get_default(self, ctx, call=True):
        return self.default

    def get_help_record(self, ctx):
        extra = self.get_help_extra(ctx)
        return ("--limit", f"[default: {extra['default']}]")

    def get_help_extra(self, ctx):
        default_value = self.get_default(ctx, call=False)

        extra = {}
        show_default = bool(self.show_default)
        show_default_is_str = isinstance(self.show_default, str)
        if show_default_is_str or (show_default and default_value not in (None, UNSET)):
            if show_default_is_str:
                default_string = f"({self.show_default})"
            elif inspect.isfunction(default_value):
                default_string = "(dynamic)"
            elif self.is_bool_flag and not self.secondary_opts and not default_value:
                default_string = ""
            elif default_value == "":
                default_string = '""'
            else:
                default_string = str(default_value)
            extra["default"] = default_string

        return extra


class Command:
    def __init__(self, name):
        self.name = name


class Context:
    def __init__(self, command):
        self.command = command
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_options.py").write_text(
        """import click
import pytest


def test_show_default_string(runner):
    opt = click.Option(["--limit"], show_default="unlimited")
    ctx = click.Context(click.Command("cli"))
    message = opt.get_help_record(ctx)[1]
    assert "[default: (unlimited)]" in message


def test_show_default_with_empty_string(runner):
    \"\"\"When show_default is True and default is set to an empty string.\"\"\"
    opt = click.Option(["--limit"], default="", show_default=True)
    ctx = click.Context(click.Command("cli"))
    message = opt.get_help_record(ctx)[1]
    assert '[default: ""]' in message


def test_do_not_show_no_default(runner):
    assert True
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


def _click_ready_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
        "ready_for_candidate_attempt": True,
        "validation_command": "pytest tests/test_defaults.py -q",
    }


def _click_prompt_spec_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
        "status": "normalized",
        "prompt_spec_kind": "click_default_map_multi_value_parameter",
    }


def _click_validation_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
        "status": "passed",
        "validation_command": "pytest tests/test_defaults.py -q",
    }


def _click_semver_ready_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": CLICK_SEMVER_REPLAY_ID,
        "ready_for_candidate_attempt": True,
        "validation_command": "pytest tests/test_options.py -q",
    }


def _click_semver_prompt_spec_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": CLICK_SEMVER_REPLAY_ID,
        "status": "normalized",
        "prompt_spec_kind": "click_semver_non_string_default_help",
    }


def _click_semver_validation_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": CLICK_SEMVER_REPLAY_ID,
        "status": "passed",
        "validation_command": "pytest tests/test_options.py -q",
    }


def _click_semver_knowledge_row(category: str) -> dict[str, object]:
    return {
        "record_type": "library_idiom_record",
        "id": f"click:{category}",
        "links": {"task_ids": [CLICK_SEMVER_REPLAY_ID]},
        "data": {"knowledge_category": category},
    }


def _pytest_strict_addopts_ready_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID,
        "ready_for_candidate_attempt": True,
        "validation_command": "pytest testing/test_config.py testing/test_mark.py -q",
    }


def _pytest_strict_addopts_prompt_spec_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID,
        "status": "normalized",
        "prompt_spec_kind": "pytest_strict_addopts_config",
    }


def _pytest_strict_addopts_validation_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID,
        "status": "passed",
        "validation_command": "pytest testing/test_config.py testing/test_mark.py -q",
    }


def _pytest_strict_addopts_knowledge_row(category: str) -> dict[str, object]:
    return {
        "record_type": "pytest_pattern_record",
        "id": f"pytest:{category}",
        "links": {"task_ids": [PYTEST_STRICT_ADDOPTS_REPLAY_ID]},
        "data": {"knowledge_category": category},
    }


def _pytest_strict_addopts_audit_row(path: str) -> dict[str, object]:
    return {
        "record_kind": "issue_pr_materialization_audit",
        "audit_id": f"DATA-023/{PYTEST_STRICT_ADDOPTS_REPLAY_ID}/{path}",
        "replay_id": PYTEST_STRICT_ADDOPTS_REPLAY_ID,
        "path": path,
        "classification": "requiring_constrained_local_generator_or_source_region_action",
    }


def _pytest_timedelta_approx_ready_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        "ready_for_candidate_attempt": True,
        "validation_command": "pytest testing/python/approx.py -q",
    }


def _pytest_timedelta_approx_prompt_spec_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        "status": "normalized",
        "prompt_spec_kind": "pytest_timedelta_approx_relative_tolerance",
    }


def _pytest_timedelta_approx_validation_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        "status": "passed",
        "validation_command": "pytest testing/python/approx.py -q",
    }


def _pytest_timedelta_approx_knowledge_row(category: str) -> dict[str, object]:
    return {
        "record_type": "pytest_pattern_record",
        "id": f"pytest-14462:{category}",
        "links": {"task_ids": [PYTEST_TIMEDELTA_APPROX_REPLAY_ID]},
        "data": {"knowledge_category": category},
    }


def _pytest_timedelta_approx_audit_row(path: str) -> dict[str, object]:
    return {
        "record_kind": "issue_pr_materialization_audit",
        "audit_id": f"DATA-028/{PYTEST_TIMEDELTA_APPROX_REPLAY_ID}/{path}",
        "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        "path": path,
        "classification": "requiring_constrained_local_generator_or_source_region_action",
    }


def _scrapy_downloader_aware_ready_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        "ready_for_candidate_attempt": True,
        "validation_command": "pytest tests/test_pqueues.py -q",
    }


def _scrapy_downloader_aware_prompt_spec_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        "status": "normalized",
        "prompt_spec_kind": "scrapy_downloader_aware_priority_queue_tie_breaking",
    }


def _scrapy_downloader_aware_validation_row() -> dict[str, object]:
    return {
        "record_kind": "issue_pr_replay_preflight_outcome",
        "replay_id": SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        "status": "passed",
        "validation_command": "pytest tests/test_pqueues.py -q",
    }


def _scrapy_downloader_aware_knowledge_row(category: str) -> dict[str, object]:
    return {
        "record_type": "library_idiom_record",
        "id": f"scrapy-7293:{category}",
        "links": {"task_ids": [SCRAPY_DOWNLOADER_AWARE_REPLAY_ID]},
        "data": {"knowledge_category": category},
    }


def _scrapy_downloader_aware_audit_row(path: str) -> dict[str, object]:
    return {
        "record_kind": "issue_pr_materialization_audit",
        "audit_id": f"DATA-034/{SCRAPY_DOWNLOADER_AWARE_REPLAY_ID}/{path}",
        "replay_id": SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        "path": path,
        "classification": "requiring_constrained_local_generator_or_source_region_action",
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
