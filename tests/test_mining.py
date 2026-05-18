from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cli import main
from j3.mining import build_issue_pr_transition_manifest, mine_git_transitions


ISSUE_PR_FIXTURE = (
    Path(__file__).parent / "fixtures" / "mining" / "apache_airflow_issue_pr_fixture.json"
)


def test_mine_git_transitions_writes_jsonl(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "j3@example.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "j3"], cwd=repo, check=True)

    source = repo / "example.py"
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "example.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    source.write_text("def value():\n    return 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "example.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "change value"], cwd=repo, check=True, capture_output=True)

    out = tmp_path / "transitions.jsonl"
    result = mine_git_transitions(repo=repo, out_path=out, max_commits=5)

    assert result.transitions_written == 1
    record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert record["file_path"] == "example.py"
    assert "return 1" in record["before_source"]
    assert "return 2" in record["after_source"]


def test_build_issue_pr_transition_manifest_from_fixture() -> None:
    manifest = build_issue_pr_transition_manifest(source_path=ISSUE_PR_FIXTURE)

    assert manifest["schema_version"] == "issue-pr-transition-manifest-v0"
    assert manifest["repository"]["full_name"] == "apache/airflow"  # type: ignore[index]
    assert manifest["totals"]["candidate_records"] == 1  # type: ignore[index]
    assert manifest["license_and_terms"]["repo_license_spdx"] == "Apache-2.0"  # type: ignore[index]

    record = manifest["records"][0]  # type: ignore[index]
    assert record["schema_version"] == "issue-pr-transition-record-v0"
    assert record["repo"] == "apache/airflow"
    assert record["issue"]["number"] == 41001  # type: ignore[index]
    assert record["pull_request"]["number"] == 41002  # type: ignore[index]
    assert record["repo_before_ref"]["sha"] == "a" * 40  # type: ignore[index]
    assert record["repo_after_ref"]["sha"] == "b" * 40  # type: ignore[index]
    assert record["links"]["compare"].endswith(f"{'a' * 40}...{'b' * 40}")  # type: ignore[index]
    assert record["provenance"]["manual_review_required"] is True  # type: ignore[index]
    assert record["provenance"]["source_kind"] == "github_fixture"  # type: ignore[index]
    assert record["split"] in {"train", "validation", "test"}
    assert record["stable_split"]["method"] == "sha256(id) % 100"  # type: ignore[index]


def test_mine_issue_pr_manifest_cli_writes_manifest(tmp_path) -> None:
    out = tmp_path / "issue-pr-manifest.json"

    exit_code = main(
        [
            "mine-issue-pr-manifest",
            "--source",
            str(ISSUE_PR_FIXTURE),
            "--out",
            str(out),
        ]
    )

    assert exit_code == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["totals"]["candidate_records"] == 1
    assert manifest["records"][0]["provenance"]["review_status"] == (
        "unreviewed_candidate"
    )
