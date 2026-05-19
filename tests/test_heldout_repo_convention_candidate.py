from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from j3.heldout_repo_convention_candidate import (
    build_pytest_argument_repr_parser_fixture_spec,
    build_requests_clean_proxy_conftest_spec,
    build_requests_leading_slash_adapter_spec,
    materialize_repo_convention_candidate,
)


def test_requests_clean_proxy_spec_uses_reusable_action_kind(tmp_path: Path) -> None:
    repo = _write_requests_conftest_fixture_repo(tmp_path / "requests")

    spec = build_requests_clean_proxy_conftest_spec(repo)

    assert spec.fixture_action.kind == "insert_pytest_fixture_after_anchor"
    assert "requests_7423" not in spec.fixture_action.kind
    assert spec.base_ref == "e8d2c015eecda8273612dd4562425e00cd164ba5"
    assert spec.accepted_head_ref == "da905d0eb1de1184d323d39dfc2ce2b423df7bee"
    assert spec.validation_command.startswith("HTTP_PROXY=http://127.0.0.1:1 ")
    assert "PYTHONPATH=src python -m pytest" in spec.validation_command
    assert spec.allowed_write_paths == ("tests/conftest.py",)


def test_materializes_requests_clean_proxy_conftest_with_reusable_action(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_conftest_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_repo_convention_candidate(
        accepted_repo,
        build_requests_clean_proxy_conftest_spec(
            accepted_repo,
            base_ref=_repo_head(accepted_repo),
        ),
        write=True,
        validate=False,
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        str(accepted_candidate.candidate_after["candidate_diff"]),
        encoding="utf-8",
    )

    repo = _write_requests_conftest_fixture_repo(tmp_path / "candidate")
    candidate = materialize_repo_convention_candidate(
        repo,
        build_requests_clean_proxy_conftest_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["accepted_head_ref"] == "da905d0eb1de1184d323d39dfc2ce2b423df7bee"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == ["tests/conftest.py"]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "tests/conftest.py"
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert (
        record["accepted_diff_comparison"]["scope_comparisons"]["repo_convention"][
            "normalized_diff_equal"
        ]
        is True
    )
    assert record["zero_hosted_llm_source_judgment"] is True
    assert [action["kind"] for action in record["action_records"]] == [
        "insert_pytest_fixture_after_anchor"
    ]
    fixture_after = record["candidate_after"]["fixture_file"]
    assert fixture_after["candidate_after"]["ast_parse_ok"] is True
    assert "clean_proxy_environ" in fixture_after["candidate_after"]["diff"]
    assert fixture_after["convention_evidence"]["imports_pytest"] is True
    assert fixture_after["convention_evidence"]["existing_fixture_names"] == ["httpbin"]
    assert fixture_after["convention_evidence"]["inserted_fixture"] == {
        "name": "clean_proxy_environ",
        "is_pytest_fixture": True,
        "autouse": True,
        "arguments": ["monkeypatch"],
    }


def test_blocks_when_local_pytest_fixture_convention_is_missing(
    tmp_path: Path,
) -> None:
    repo = _write_requests_conftest_fixture_repo(
        tmp_path / "requests",
        conftest_source=dedent(
            '''
            def prepare_url(value):
                return value
            '''
        ).lstrip(),
    )

    candidate = materialize_repo_convention_candidate(
        repo,
        build_requests_clean_proxy_conftest_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=tmp_path / "missing.diff",
    )
    record = candidate.to_record()

    assert record["status"] == "blocked"
    assert record["blockers"][0]["reason"] == "repo_convention_fixture_detection_blocked"
    assert record["mutation_scope"]["actual_changed_files"] == []


def test_requests_leading_slash_spec_uses_reusable_action_kinds(
    tmp_path: Path,
) -> None:
    repo = _write_requests_adapter_fixture_repo(tmp_path / "requests")

    spec = build_requests_leading_slash_adapter_spec(repo)

    assert [action.kind for action in spec.actions] == [
        "delete_exact_source_lines_after_anchor",
        "rename_pytest_function",
        "replace_pytest_assertion_expected_literal",
    ]
    assert all("7315" not in action.kind for action in spec.actions)
    assert spec.base_ref == "e8d2c015eecda8273612dd4562425e00cd164ba5"
    assert spec.accepted_head_ref == "fd628095d7b9ddbf3e987d8a4bf0e6062768916f"
    assert spec.validation_command.startswith("PYTHONPATH=src python -m pytest ")
    assert spec.allowed_write_paths == (
        "src/requests/adapters.py",
        "tests/test_adapters.py",
    )


def test_materializes_requests_leading_slash_adapter_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_adapter_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_repo_convention_candidate(
        accepted_repo,
        build_requests_leading_slash_adapter_spec(
            accepted_repo,
            base_ref=_repo_head(accepted_repo),
        ),
        write=True,
        validate=False,
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        str(accepted_candidate.candidate_after["candidate_diff"]),
        encoding="utf-8",
    )

    repo = _write_requests_adapter_fixture_repo(tmp_path / "candidate")
    candidate = materialize_repo_convention_candidate(
        repo,
        build_requests_leading_slash_adapter_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["accepted_head_ref"] == "fd628095d7b9ddbf3e987d8a4bf0e6062768916f"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["mode"] == (
        "heldout_repo_convention_bounded_source_test_update"
    )
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/adapters.py",
        "tests/test_adapters.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/requests/adapters.py",
        "tests/test_adapters.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert (
        record["accepted_diff_comparison"]["scope_comparisons"]["repo_convention"][
            "normalized_diff_equal"
        ]
        is True
    )
    assert [action["kind"] for action in record["action_records"]] == [
        "delete_exact_source_lines_after_anchor",
        "rename_pytest_function",
        "replace_pytest_assertion_expected_literal",
    ]
    assert record["zero_hosted_llm_source_judgment"] is True

    action_results = record["candidate_after"]["action_results"]
    assert [result["action_kind"] for result in action_results] == [
        "delete_exact_source_lines_after_anchor",
        "rename_pytest_function",
        "replace_pytest_assertion_expected_literal",
    ]
    source_result = action_results[0]
    assert source_result["candidate_after"]["ast_parse_ok"] is True
    assert source_result["convention_evidence"]["anchor_function_name"] == "request_url"
    assert source_result["convention_evidence"]["deleted_line_count"] == 2
    expectation_result = action_results[2]
    assert (
        expectation_result["convention_evidence"]["new_expected_literal"] == "//v:h"
    )
    assert (
        repo / "tests" / "test_adapters.py"
    ).read_text() == _requests_adapter_test_after_source()


def test_blocks_when_adapter_test_import_convention_is_missing(
    tmp_path: Path,
) -> None:
    repo = _write_requests_adapter_fixture_repo(
        tmp_path / "requests",
        adapter_test_source=dedent(
            '''
            def test_request_url_trims_leading_path_separators():
                pass
            '''
        ).lstrip(),
    )

    candidate = materialize_repo_convention_candidate(
        repo,
        build_requests_leading_slash_adapter_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=tmp_path / "missing.diff",
    )
    record = candidate.to_record()

    assert record["status"] == "blocked"
    assert record["blockers"][0]["reason"] == "repo_convention_test_expectation_blocked"
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/adapters.py"
    ]


def test_pytest_argument_repr_spec_uses_reusable_action_kinds(
    tmp_path: Path,
) -> None:
    repo = _write_pytest_parseopt_fixture_repo(tmp_path / "pytest")

    spec = build_pytest_argument_repr_parser_fixture_spec(repo)

    assert [action.kind for action in spec.actions] == [
        "replace_exact_source_lines_after_anchor",
        "insert_pytest_function_after_anchor",
    ]
    assert all("14429" not in action.kind for action in spec.actions)
    assert spec.base_ref == "8f81c76744daf72d4f77cfc8423f4bdc60733d78"
    assert spec.accepted_head_ref == "641a97b7695430f9fc4e9113b31d797447dc9654"
    assert "PYTHONPATH=src python -m pytest " in spec.validation_command
    assert "src/_pytest/_version.py" in spec.validation_command
    assert spec.allowed_write_paths == (
        "src/_pytest/config/argparsing.py",
        "testing/test_parseopt.py",
    )
    assert spec.source_test_scope_paths == spec.allowed_write_paths


def test_materializes_pytest_argument_repr_with_source_test_scoped_parity(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_pytest_parseopt_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_repo_convention_candidate(
        accepted_repo,
        build_pytest_argument_repr_parser_fixture_spec(
            accepted_repo,
            base_ref=_repo_head(accepted_repo),
        ),
        write=True,
        validate=False,
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _changelog_diff() + str(accepted_candidate.candidate_after["candidate_diff"]),
        encoding="utf-8",
    )

    repo = _write_pytest_parseopt_fixture_repo(tmp_path / "candidate")
    candidate = materialize_repo_convention_candidate(
        repo,
        build_pytest_argument_repr_parser_fixture_spec(
            repo,
            base_ref=_repo_head(repo),
        ),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["accepted_head_ref"] == "641a97b7695430f9fc4e9113b31d797447dc9654"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/_pytest/config/argparsing.py",
        "testing/test_parseopt.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "changelog/13817.bugfix.rst",
        "src/_pytest/config/argparsing.py",
        "testing/test_parseopt.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is False
    assert (
        record["accepted_diff_comparison"]["scope_comparisons"]["source_test"][
            "normalized_diff_equal"
        ]
        is True
    )
    assert (
        record["accepted_diff_comparison"]["scope_comparisons"]["repo_convention"][
            "normalized_diff_equal"
        ]
        is True
    )
    assert [action["kind"] for action in record["action_records"]] == [
        "replace_exact_source_lines_after_anchor",
        "insert_pytest_function_after_anchor",
    ]

    action_results = record["candidate_after"]["action_results"]
    assert [result["action_kind"] for result in action_results] == [
        "replace_exact_source_lines_after_anchor",
        "insert_pytest_function_after_anchor",
    ]
    source_result = action_results[0]
    assert source_result["candidate_after"]["ast_parse_ok"] is True
    assert source_result["convention_evidence"]["anchor_class_name"] == "Argument"
    assert source_result["convention_evidence"]["old_line_count"] == 4
    assert source_result["convention_evidence"]["new_line_count"] == 7
    test_result = action_results[1]
    assert test_result["candidate_after"]["ast_parse_ok"] is True
    assert test_result["convention_evidence"]["existing_fixture_names"] == ["parser"]
    assert test_result["convention_evidence"]["inserted_test_function_names"] == [
        "test_argument_repr_uninitialized",
        "test_argument_repr_initialized",
    ]
    assert (
        repo / "testing" / "test_parseopt.py"
    ).read_text() == _pytest_parseopt_test_after_source()


def test_blocks_when_pytest_parser_fixture_convention_is_missing(
    tmp_path: Path,
) -> None:
    repo = _write_pytest_parseopt_fixture_repo(
        tmp_path / "pytest",
        test_source=dedent(
            '''
            from _pytest.config import argparsing as parseopt


            def test_argcomplete() -> None:
                pass
            '''
        ).lstrip(),
    )

    candidate = materialize_repo_convention_candidate(
        repo,
        build_pytest_argument_repr_parser_fixture_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=tmp_path / "missing.diff",
    )
    record = candidate.to_record()

    assert record["status"] == "blocked"
    assert record["blockers"][0]["reason"] == "repo_convention_test_insertion_blocked"
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/_pytest/config/argparsing.py"
    ]


def _write_requests_conftest_fixture_repo(
    repo: Path,
    *,
    conftest_source: str | None = None,
) -> Path:
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "conftest.py").write_text(
        conftest_source
        or dedent(
            '''
            import pytest

            from requests.compat import urljoin


            def prepare_url(value):
                httpbin_url = value.url.rstrip("/") + "/"

                def inner(*suffix):
                    return urljoin(httpbin_url, "/".join(suffix))

                return inner


            @pytest.fixture
            def httpbin(httpbin):
                return prepare_url(httpbin)
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=j3-test",
            "-c",
            "user.email=j3-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "base",
        ],
        cwd=repo,
        check=True,
    )
    return repo


def _write_requests_adapter_fixture_repo(
    repo: Path,
    *,
    adapters_source: str | None = None,
    adapter_test_source: str | None = None,
) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "requests" / "adapters.py").write_text(
        adapters_source or _requests_adapter_before_source(),
        encoding="utf-8",
    )
    (repo / "tests" / "test_adapters.py").write_text(
        adapter_test_source or _requests_adapter_test_before_source(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=j3-test",
            "-c",
            "user.email=j3-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "base",
        ],
        cwd=repo,
        check=True,
    )
    return repo


def _write_pytest_parseopt_fixture_repo(
    repo: Path,
    *,
    source: str | None = None,
    test_source: str | None = None,
) -> Path:
    (repo / "src" / "_pytest" / "config").mkdir(parents=True)
    (repo / "testing").mkdir(parents=True)
    (repo / "src" / "_pytest" / "config" / "argparsing.py").write_text(
        source or _pytest_argparsing_before_source(),
        encoding="utf-8",
    )
    (repo / "testing" / "test_parseopt.py").write_text(
        test_source or _pytest_parseopt_test_before_source(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=j3-test",
            "-c",
            "user.email=j3-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "base",
        ],
        cwd=repo,
        check=True,
    )
    return repo


def _requests_adapter_before_source() -> str:
    return dedent(
        '''
        class HTTPAdapter:
            def request_url(self, request, proxies):
                proxy = None
                scheme = "http"

                is_proxied_http_request = proxy and scheme != "https"
                using_socks_proxy = False
                if proxy:
                    proxy_scheme = "http"
                    using_socks_proxy = proxy_scheme.startswith("socks")

                url = request.path_url
                if url.startswith("//"):  # Don't confuse urllib3
                    url = f"/{url.lstrip('/')}"

                if is_proxied_http_request and not using_socks_proxy:
                    url = request.url

                return url
        '''
    ).lstrip()


def _requests_adapter_test_before_source() -> str:
    return dedent(
        '''
        import requests.adapters


        def test_request_url_trims_leading_path_separators():
            """See also https://github.com/psf/requests/issues/6643."""
            a = requests.adapters.HTTPAdapter()
            p = requests.Request(method="GET", url="http://127.0.0.1:10000//v:h").prepare()
            assert "/v:h" == a.request_url(p, {})
        '''
    ).lstrip()


def _requests_adapter_test_after_source() -> str:
    return dedent(
        '''
        import requests.adapters


        def test_request_url_handles_leading_path_separators():
            """See also https://github.com/psf/requests/issues/6643."""
            a = requests.adapters.HTTPAdapter()
            p = requests.Request(method="GET", url="http://127.0.0.1:10000//v:h").prepare()
            assert "//v:h" == a.request_url(p, {})
        '''
    ).lstrip()


def _pytest_argparsing_before_source() -> str:
    return dedent(
        '''
        from typing import Any, Sequence


        class Argument:
            def __init__(self, action):
                self._action = action

            def names(self) -> Sequence[str]:
                return self._action.option_strings

            @property
            def dest(self) -> str:
                return self._action.dest

            @property
            def default(self) -> Any:
                return self._action.default

            @property
            def type(self) -> Any | None:
                return self._action.type

            def __repr__(self) -> str:
                args: list[str] = []
                args += ["opts: " + repr(self.names())]
                args += ["dest: " + repr(self.dest)]
                if self._action.type:
                    args += ["type: " + repr(self.type)]
                args += ["default: " + repr(self.default)]
                return "Argument({})".format(", ".join(args))
        '''
    ).lstrip()


def _pytest_parseopt_test_before_source() -> str:
    return dedent(
        '''
        from _pytest.config import argparsing as parseopt
        import pytest


        @pytest.fixture
        def parser() -> parseopt.Parser:
            return parseopt.Parser(_ispytest=True)


        def test_argcomplete(pytester, monkeypatch) -> None:
            monkeypatch.setenv("COMP_LINE", "pytest test_argc")
            result = pytester.run("bash", "pytest")
            result.stdout.fnmatch_lines(["test_argcomplete", "test_argcomplete.d/"])
        '''
    ).lstrip()


def _pytest_parseopt_test_after_source() -> str:
    return dedent(
        '''
        from _pytest.config import argparsing as parseopt
        import pytest


        @pytest.fixture
        def parser() -> parseopt.Parser:
            return parseopt.Parser(_ispytest=True)


        def test_argcomplete(pytester, monkeypatch) -> None:
            monkeypatch.setenv("COMP_LINE", "pytest test_argc")
            result = pytester.run("bash", "pytest")
            result.stdout.fnmatch_lines(["test_argcomplete", "test_argcomplete.d/"])


        def test_argument_repr_uninitialized() -> None:
            """Argument.__repr__ should not crash if _action is not set yet."""
            arg = parseopt.Argument.__new__(parseopt.Argument)
            assert repr(arg) == "Argument(<uninitialized>)"


        def test_argument_repr_initialized(parser: parseopt.Parser) -> None:
            """Argument.__repr__ with properly initialized options."""
            # Without type
            parser.addoption("--myflag", dest="myflag", help="test flag")
            option = parser._anonymous.options[-1]
            assert repr(option) == "Argument(opts: ['--myflag'], dest: 'myflag', default: None)"

            # With type
            parser.addoption("--count", type=int, dest="count", help="count")
            option = parser._anonymous.options[-1]
            assert (
                repr(option)
                == "Argument(opts: ['--count'], dest: 'count', type: <class 'int'>, default: None)"
            )
        '''
    ).lstrip()


def _changelog_diff() -> str:
    return dedent(
        '''
        diff --git a/changelog/13817.bugfix.rst b/changelog/13817.bugfix.rst
        new file mode 100644
        index 000000000..08c9a6a53
        --- /dev/null
        +++ b/changelog/13817.bugfix.rst
        @@ -0,0 +1 @@
        +Fixed a secondary `AttributeError` masking the original error when an option argument fails to initialize.
        '''
    ).lstrip()


def _repo_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
