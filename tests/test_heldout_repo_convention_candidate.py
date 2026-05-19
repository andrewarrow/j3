from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from j3.heldout_repo_convention_candidate import (
    build_requests_clean_proxy_conftest_spec,
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


def _repo_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
