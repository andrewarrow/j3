from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from j3.heldout_source_region_candidate import (
    _accepted_diff_comparison,
    build_click_write_usage_spec,
    _mark_expression_scanner_source_replacement,
    build_pytest_mark_expression_scanner_spec,
    build_requests_no_proxy_domain_boundary_spec,
    build_requests_redirect_history_spec,
    build_requests_stream_wrapper_spec,
    materialize_heldout_source_region_candidate,
)
from j3.source_region_materializer import SourceRegionActionKind


def test_requests_no_proxy_spec_uses_reusable_action_kinds(tmp_path: Path) -> None:
    repo = _write_requests_fixture_repo(tmp_path / "requests")

    spec = build_requests_no_proxy_domain_boundary_spec(repo)

    assert spec.source_action.kind == SourceRegionActionKind.REPLACE_FUNCTION_REGION
    assert spec.test_action.kind == "insert_pytest_function_after_anchor"
    assert "requests_7427" not in spec.source_action.kind.value
    assert "requests_7427" not in spec.test_action.kind
    assert spec.allowed_write_paths == (
        "src/requests/utils.py",
        "tests/test_utils.py",
    )


def test_materializes_requests_no_proxy_candidate_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_heldout_source_region_candidate(
        accepted_repo,
        build_requests_no_proxy_domain_boundary_spec(
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

    repo = _write_requests_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_source_region_candidate(
        repo,
        build_requests_no_proxy_domain_boundary_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/utils.py",
        "tests/test_utils.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert record["zero_hosted_llm_source_judgment"] is True
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert action_kinds == [
        "replace_function_region",
        "insert_pytest_function_after_anchor",
    ]
    source_after = record["candidate_after"]["source_file"]["candidate_after"]
    assert source_after["ast_parse_ok"] is True
    assert source_after["signature_preserved"] is True
    assert 'host = host.lstrip(".")' in source_after["diff"]
    test_after = record["candidate_after"]["test_file"]["candidate_after"]
    assert test_after["ast_parse_ok"] is True
    assert "test_should_bypass_proxies_no_proxy_domain_boundary" in test_after["diff"]


def test_accepted_diff_comparison_ignores_hunk_context_labels(tmp_path: Path) -> None:
    accepted = tmp_path / "accepted.diff"
    accepted.write_text(
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1,2 +1,2 @@ def old_context():\n"
        "-a\n"
        "+b\n",
        encoding="utf-8",
    )
    candidate = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -1,2 +1,2 @@ def new_context():\n"
        "-a\n"
        "+b\n"
    )

    comparison = _accepted_diff_comparison(candidate, accepted_diff_path=accepted)

    assert comparison["normalized_diff_equal"] is True


def test_pytest_scanner_spec_uses_reusable_action_kinds(tmp_path: Path) -> None:
    repo = _write_pytest_fixture_repo(tmp_path / "pytest")

    spec = build_pytest_mark_expression_scanner_spec(repo)

    assert spec.source_action.kind == SourceRegionActionKind.REPLACE_FUNCTION_REGION
    assert spec.test_action.kind == "insert_pytest_function_after_anchor"
    assert "pytest_14475" not in spec.source_action.kind.value
    assert "pytest_14475" not in spec.test_action.kind
    assert spec.allowed_write_paths == (
        "src/_pytest/mark/expression.py",
        "testing/test_mark_expression.py",
    )


def test_materializes_pytest_scanner_candidate_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_pytest_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_heldout_source_region_candidate(
        accepted_repo,
        build_pytest_mark_expression_scanner_spec(
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

    repo = _write_pytest_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_source_region_candidate(
        repo,
        build_pytest_mark_expression_scanner_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/_pytest/mark/expression.py",
        "testing/test_mark_expression.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "changelog/14474.bugfix.rst",
        "src/_pytest/mark/expression.py",
        "testing/test_mark_expression.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is False
    assert record["accepted_diff_comparison"]["scoped_normalized_diff_equal"] is True
    assert record["zero_hosted_llm_source_judgment"] is True
    assert (
        'r\'escaping with "\\" not supported in marker expression\''
        in _mark_expression_scanner_source_replacement()
    )
    assert (
        'r\'escaping with "\\\\" not supported in marker expression\''
        not in _mark_expression_scanner_source_replacement()
    )
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert action_kinds == [
        "replace_function_region",
        "insert_pytest_function_after_anchor",
    ]
    source_after = record["candidate_after"]["source_file"]["candidate_after"]
    assert source_after["ast_parse_ok"] is True
    assert source_after["signature_preserved"] is True
    assert 'value.find("\\\\")' in source_after["diff"]
    assert "pos + backslash_pos + 1" in source_after["diff"]
    test_after = record["candidate_after"]["test_file"]["candidate_after"]
    assert test_after["ast_parse_ok"] is True
    assert "test_backslash_in_identifier_with_string_literal" in test_after["diff"]


def test_requests_stream_wrapper_spec_uses_reusable_action_kinds(
    tmp_path: Path,
) -> None:
    repo = _write_requests_stream_wrapper_fixture_repo(tmp_path / "requests")

    spec = build_requests_stream_wrapper_spec(repo)

    assert spec.source_action.kind == SourceRegionActionKind.REPLACE_FUNCTION_REGION
    assert spec.test_action.kind == "insert_pytest_function_after_anchor"
    assert "requests_7433" not in spec.source_action.kind.value
    assert "requests_7433" not in spec.test_action.kind
    assert spec.base_ref == "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
    assert spec.accepted_head_ref == "ea1c36c1b1a8364e234b6ad49ea05e3261636f8a"
    assert spec.allowed_write_paths == (
        "src/requests/models.py",
        "tests/test_requests.py",
    )


def test_materializes_requests_stream_wrapper_candidate_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_stream_wrapper_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_heldout_source_region_candidate(
        accepted_repo,
        build_requests_stream_wrapper_spec(
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

    repo = _write_requests_stream_wrapper_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_source_region_candidate(
        repo,
        build_requests_stream_wrapper_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["accepted_head_ref"] == "ea1c36c1b1a8364e234b6ad49ea05e3261636f8a"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/models.py",
        "tests/test_requests.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/requests/models.py",
        "tests/test_requests.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert record["accepted_diff_comparison"]["scoped_normalized_diff_equal"] is True
    assert record["zero_hosted_llm_source_judgment"] is True
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert action_kinds == [
        "replace_function_region",
        "insert_pytest_function_after_anchor",
    ]
    source_after = record["candidate_after"]["source_file"]["candidate_after"]
    assert source_after["ast_parse_ok"] is True
    assert source_after["signature_preserved"] is True
    assert 'hasattr(data, "__iter__")' in source_after["diff"]
    assert "is_iterable and not isinstance" in source_after["diff"]
    test_after = record["candidate_after"]["test_file"]["candidate_after"]
    assert test_after["ast_parse_ok"] is True
    assert "test_getattr_proxy_stream_follows_redirect" in test_after["diff"]


def test_requests_redirect_history_spec_uses_reusable_action_kinds(
    tmp_path: Path,
) -> None:
    repo = _write_requests_redirect_history_fixture_repo(tmp_path / "requests")

    spec = build_requests_redirect_history_spec(repo)

    assert spec.source_action.kind == SourceRegionActionKind.REPLACE_FUNCTION_REGION
    assert spec.test_action.kind == "insert_pytest_function_after_anchor"
    assert "requests_7328" not in spec.source_action.kind.value
    assert "requests_7328" not in spec.test_action.kind
    assert spec.base_ref == "cbce031327be4f1b4b5fd041ff4dcaa8efa2ce53"
    assert spec.accepted_head_ref == "3ee28b806f8bc414b29f7b4561e53c161924fe66"
    assert spec.validation_command.startswith("PYTHONPATH=src ")
    assert spec.allowed_write_paths == (
        "src/requests/sessions.py",
        "tests/test_requests.py",
    )


def test_materializes_requests_redirect_history_candidate_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_redirect_history_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_heldout_source_region_candidate(
        accepted_repo,
        build_requests_redirect_history_spec(
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

    repo = _write_requests_redirect_history_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_source_region_candidate(
        repo,
        build_requests_redirect_history_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["accepted_head_ref"] == "3ee28b806f8bc414b29f7b4561e53c161924fe66"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/sessions.py",
        "tests/test_requests.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/requests/sessions.py",
        "tests/test_requests.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert record["accepted_diff_comparison"]["scoped_normalized_diff_equal"] is True
    assert record["zero_hosted_llm_source_judgment"] is True
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert action_kinds == [
        "replace_function_region",
        "insert_pytest_function_after_anchor",
    ]
    source_after = record["candidate_after"]["source_file"]["candidate_after"]
    assert source_after["ast_parse_ok"] is True
    assert source_after["signature_preserved"] is True
    assert "resp.history = hist[:]" in source_after["diff"]
    assert "resp.history = hist[1:]" in source_after["diff"]
    test_after = record["candidate_after"]["test_file"]["candidate_after"]
    assert test_after["ast_parse_ok"] is True
    assert "test_redirect_history_no_self_reference" in test_after["diff"]


def test_click_write_usage_spec_uses_reusable_action_kinds(tmp_path: Path) -> None:
    repo = _write_click_write_usage_fixture_repo(tmp_path / "click")

    spec = build_click_write_usage_spec(repo)

    assert spec.source_action.kind == SourceRegionActionKind.REPLACE_FUNCTION_REGION
    assert spec.test_action.kind == "insert_pytest_function_after_anchor"
    assert "click_3434" not in spec.source_action.kind.value
    assert "click_3434" not in spec.test_action.kind
    assert spec.base_ref == "7c99ebe23b931f27562d926814423cce85fd9766"
    assert spec.accepted_head_ref == "0551bf53588ae87f462d336f24f853a156fefe3a"
    assert spec.validation_command.startswith("PYTHONPATH=src ")
    assert spec.allowed_write_paths == (
        "src/click/formatting.py",
        "tests/test_formatting.py",
    )


def test_materializes_click_write_usage_candidate_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_click_write_usage_fixture_repo(tmp_path / "accepted")
    accepted_candidate = materialize_heldout_source_region_candidate(
        accepted_repo,
        build_click_write_usage_spec(
            accepted_repo,
            base_ref=_repo_head(accepted_repo),
        ),
        write=True,
        validate=False,
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _click_changelog_diff() + str(accepted_candidate.candidate_after["candidate_diff"]),
        encoding="utf-8",
    )

    repo = _write_click_write_usage_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_source_region_candidate(
        repo,
        build_click_write_usage_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["accepted_head_ref"] == "0551bf53588ae87f462d336f24f853a156fefe3a"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/click/formatting.py",
        "tests/test_formatting.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "CHANGES.rst",
        "src/click/formatting.py",
        "tests/test_formatting.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is False
    assert record["accepted_diff_comparison"]["scoped_normalized_diff_equal"] is True
    assert record["zero_hosted_llm_source_judgment"] is True
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert action_kinds == [
        "replace_function_region",
        "insert_pytest_function_after_anchor",
    ]
    source_after = record["candidate_after"]["source_file"]["candidate_after"]
    assert source_after["ast_parse_ok"] is True
    assert source_after["signature_preserved"] is True
    assert "if not args:" in source_after["diff"]
    assert 'usage_prefix.rstrip(" ")' in source_after["diff"]
    test_after = record["candidate_after"]["test_file"]["candidate_after"]
    assert test_after["ast_parse_ok"] is True
    assert "test_help_formatter_write_usage" in test_after["diff"]
    assert "test_command_write_usage_no_args" in test_after["diff"]


def _write_requests_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "requests" / "utils.py").write_text(
        dedent(
            '''
            from urllib.parse import urlparse


            def should_bypass_proxies(url: str, no_proxy: str | None) -> bool:
                parsed = urlparse(url)
                no_proxy_hosts = [host for host in no_proxy.split(",") if host]
                if parsed.hostname is None:
                    return False
                hostname = parsed.hostname
                if no_proxy:
                    if False:
                        return False
                    else:
                        host_with_port = hostname
                        if parsed.port:
                            host_with_port += f":{parsed.port}"

                        for host in no_proxy_hosts:
                            if hostname.endswith(host) or host_with_port.endswith(host):
                                # The URL does match something in no_proxy, so we don't want
                                # to apply the proxies on this URL.
                                return True
                return False
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    (repo / "tests" / "test_utils.py").write_text(
        dedent(
            '''
            import pytest

            from requests.utils import should_bypass_proxies


            @pytest.mark.parametrize(
                "url, expected",
                (
                    ("http://localhost/", True),
                    ("http://prelocalhost/", True),
                ),
            )
            def test_should_bypass_proxies_no_proxy(url, expected, monkeypatch):
                no_proxy = "localhost"
                assert should_bypass_proxies(url, no_proxy=no_proxy) == expected
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


def _write_click_write_usage_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "click" / "formatting.py").write_text(
        dedent(
            '''
            from gettext import gettext as _


            def term_len(x):
                return len(x)


            def wrap_text(text, width, initial_indent="", subsequent_indent=""):
                if not text:
                    return ""
                return initial_indent + text


            class HelpFormatter:
                indent_increment = 2

                def __init__(self, width=None, max_width=None):
                    self.width = width or 80
                    self.current_indent: int = 0
                    self.buffer: list[str] = []

                def write(self, string: str) -> None:
                    """Writes a unicode string into the internal buffer."""
                    self.buffer.append(string)

                def write_usage(self, prog: str, args: str = "", prefix: str | None = None) -> None:
                    """Writes a usage line into the buffer.

                    :param prog: the program name.
                    :param args: whitespace separated list of arguments.
                    :param prefix: The prefix for the first line. Defaults to
                        ``"Usage: "``.
                    """
                    if prefix is None:
                        prefix = "{usage} ".format(usage=_("Usage:"))

                    usage_prefix = f"{prefix:>{self.current_indent}}{prog} "
                    text_width = self.width - self.current_indent

                    if text_width >= (term_len(usage_prefix) + 20):
                        # The arguments will fit to the right of the prefix.
                        indent = " " * term_len(usage_prefix)
                        self.write(
                            wrap_text(
                                args,
                                text_width,
                                initial_indent=usage_prefix,
                                subsequent_indent=indent,
                            )
                        )
                    else:
                        # The prefix is too long, put the arguments on the next line.
                        self.write(usage_prefix)
                        self.write("\\n")
                        indent = " " * (max(self.current_indent, term_len(prefix)) + 4)
                        self.write(
                            wrap_text(
                                args, text_width, initial_indent=indent, subsequent_indent=indent
                            )
                        )

                    self.write("\\n")
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    (repo / "tests" / "test_formatting.py").write_text(
        dedent(
            '''
            import pytest

            import click
            from click._compat import strip_ansi


            def test_write_usage_styled_prefix_keeps_options_on_one_line():
                """End-to-end: a downstream-styled ``Usage:`` prefix should not split
                ``[OPTIONS]`` across two lines.
                """
                styled_prefix = "\\x1b[38;2;38;139;210m\\x1b[1mUsage:\\x1b[0m "

                formatter = click.HelpFormatter(width=40)
                formatter.write_usage("cli", "[OPTIONS]", prefix=styled_prefix)
                rendered = formatter.getvalue()

                visible = strip_ansi(rendered)
                assert visible == "Usage: cli [OPTIONS]\\n"
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


def _write_requests_redirect_history_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "requests" / "sessions.py").write_text(
        dedent(
            '''
            from urllib.parse import urlparse


            class SessionRedirectMixin:
                max_redirects = 30

                def get_redirect_target(self, resp):
                    return None

                def resolve_redirects(
                    self,
                    resp,
                    req,
                    stream=False,
                    timeout=None,
                    verify=True,
                    cert=None,
                    proxies=None,
                    yield_requests=False,
                    **adapter_kwargs,
                ):
                    """Receives a Response. Returns a generator of Responses or Requests."""

                    hist = []  # keep track of history

                    url = self.get_redirect_target(resp)
                    previous_fragment = urlparse(req.url).fragment
                    while url:
                        prepared_request = req.copy()

                        # Update history and keep track of redirects.
                        # resp.history must ignore the original request in this loop
                        hist.append(resp)
                        resp.history = hist[1:]

                        if len(resp.history) >= self.max_redirects:
                            raise RuntimeError("too many redirects")

                        yield prepared_request
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    (repo / "tests" / "test_requests.py").write_text(
        dedent(
            '''
            """Tests for Requests."""

            import requests


            class TestRequests:
                def test_HTTP_302_ALLOW_REDIRECT_GET(self, httpbin):
                    r = requests.get(httpbin("redirect", "1"))
                    assert r.status_code == 200
                    assert r.history[0].status_code == 302
                    assert r.history[0].is_redirect

                def test_HTTP_307_ALLOW_REDIRECT_POST(self, httpbin):
                    r = requests.post(
                        httpbin("redirect-to"),
                        data="test",
                        params={"url": "post", "status_code": 307},
                    )
                    assert r.status_code == 200
                    assert r.history[0].status_code == 307
                    assert r.history[0].is_redirect
                    assert r.json()["data"] == "test"
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


def _write_requests_stream_wrapper_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "requests" / "models.py").write_text(
        dedent(
            '''
            from collections.abc import Iterable, Mapping
            from io import UnsupportedOperation


            class PreparedRequest:
                def prepare_body(self, data, files, json=None):
                    body = None

                    if isinstance(data, Iterable) and not isinstance(
                        data, (str, bytes, list, tuple, Mapping)
                    ):
                        try:
                            length = super_len(data)
                        except (TypeError, AttributeError, UnsupportedOperation):
                            length = None

                        body = data

                    return body
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    (repo / "tests" / "test_requests.py").write_text(
        dedent(
            '''
            """Tests for Requests."""

            import io

            import requests


            class TestRequests:
                def test_rewind_body_failed_tell(self):
                    class BadFileObj:
                        def tell(self):
                            raise OSError()

                        def __iter__(self):
                            return

                    assert BadFileObj()

                def _patch_adapter_gzipped_redirect(self, session, url):
                    adapter = session.get_adapter(url=url)
                    assert adapter
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


def _write_pytest_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "_pytest" / "mark").mkdir(parents=True)
    (repo / "testing").mkdir(parents=True)
    (repo / "src" / "_pytest" / "mark" / "expression.py").write_text(
        dedent(
            r'''
            from __future__ import annotations

            import re
            from collections.abc import Iterator
            from dataclasses import dataclass
            from enum import Enum

            FILE_NAME = "<pytest match expression>"


            class TokenType(Enum):
                STRING = "string"


            @dataclass
            class Token:
                type: TokenType
                value: str
                pos: int


            class Scanner:
                __slots__ = ("current", "input", "tokens")

                def __init__(self, input: str) -> None:
                    self.input = input
                    self.tokens = self.lex(input)
                    self.current = next(self.tokens)

                def lex(self, input: str) -> Iterator[Token]:
                    pos = 0
                    while pos < len(input):
                        if (quote_char := input[pos]) in ("'", '"'):
                            end_quote_pos = input.find(quote_char, pos + 1)
                            if end_quote_pos == -1:
                                raise SyntaxError(
                                    f'closing quote "{quote_char}" is missing',
                                    (FILE_NAME, 1, pos + 1, input),
                                )
                            value = input[pos : end_quote_pos + 1]
                            if (backslash_pos := input.find("\\")) != -1:
                                raise SyntaxError(
                                    r'escaping with "\" not supported in marker expression',
                                    (FILE_NAME, 1, backslash_pos + 1, input),
                                )
                            yield Token(TokenType.STRING, value, pos)
                            pos += len(value)
                        else:
                            match = re.match(r"(:?\w|:|\+|-|\.|\[|\]|\\|/)+", input[pos:])
                            if match:
                                pos += len(match.group(0))
                            else:
                                pos += 1
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    (repo / "testing" / "test_mark_expression.py").write_text(
        dedent(
            r'''
            from __future__ import annotations

            import pytest


            def evaluate(input: str, matcher):
                return True


            def test_backslash_not_treated_specially() -> None:
                r"""Backslashes in identifiers are regular identifier characters."""

                def matcher(name: str, /, **kwargs: str | int | bool | None) -> bool:
                    return {r"\nfoo\n"}.__contains__(name)

                assert evaluate(r"\nfoo\n", matcher)
                assert not evaluate(r"foo", matcher)
                with pytest.raises(SyntaxError):
                    evaluate("\nfoo\n", matcher)


            @pytest.mark.parametrize(
                ("expr", "column", "message"),
                (("(", 2, "expected"),),
            )
            def test_syntax_errors(expr: str, column: int, message: str) -> None:
                assert column
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


def _changelog_diff() -> str:
    return (
        "diff --git a/changelog/14474.bugfix.rst "
        "b/changelog/14474.bugfix.rst\n"
        "new file mode 100644\n"
        "index 00000000000..333d4d34d9a\n"
        "--- /dev/null\n"
        "+++ b/changelog/14474.bugfix.rst\n"
        "@@ -0,0 +1 @@\n"
        "+Fixed a scanner regression.\n"
    )


def _click_changelog_diff() -> str:
    return (
        "diff --git a/CHANGES.rst b/CHANGES.rst\n"
        "index 2c0dc4f00f..f8c2df43e7 100644\n"
        "--- a/CHANGES.rst\n"
        "+++ b/CHANGES.rst\n"
        "@@ -59,6 +59,11 @@ Unreleased\n"
        "+-   Fix HelpFormatter.write_usage empty args.\n"
    )


def _repo_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
