from __future__ import annotations

import json
import subprocess

from mining import mine_git_transitions


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
