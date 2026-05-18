from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_attempt import (
    CLICK_DEFAULT_MAP_REPLAY_ID,
    CLICK_SEMVER_REPLAY_ID,
    PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    REQUESTS_REPLAY_ID,
    main,
    run_click_default_map_issue_pr_candidate_attempt,
    run_click_semver_issue_pr_candidate_attempt,
    run_pytest_strict_addopts_issue_pr_candidate_attempt,
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
