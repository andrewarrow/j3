from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from j3.heldout_source_region_candidate import (
    _accepted_diff_comparison,
    build_requests_no_proxy_domain_boundary_spec,
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


def _repo_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
