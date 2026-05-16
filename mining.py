"""Mine real Python file transitions from git history."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MineResult:
    repo: Path
    out_path: Path
    commits_scanned: int
    transitions_written: int


def mine_git_transitions(
    *,
    repo: Path,
    out_path: Path,
    max_commits: int = 50,
    max_files_per_commit: int = 20,
) -> MineResult:
    """Write JSONL records for Python files changed across recent commits."""

    root = repo.expanduser().resolve()
    if not (root / ".git").exists():
        raise ValueError(f"not a git repository: {root}")
    if max_commits < 1:
        raise ValueError("max_commits must be >= 1")
    if max_files_per_commit < 1:
        raise ValueError("max_files_per_commit must be >= 1")

    commits = _git_lines(root, ["log", "--format=%H", f"--max-count={max_commits}", "--", "*.py"])
    output = out_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output.open("w", encoding="utf-8") as handle:
        for commit in commits:
            parent = _first_parent(root, commit)
            if parent is None:
                continue

            changed_files = _changed_python_files(root, parent, commit)[:max_files_per_commit]
            for file_path in changed_files:
                before = _show_text(root, f"{parent}:{file_path}")
                after = _show_text(root, f"{commit}:{file_path}")
                if before is None or after is None or before == after:
                    continue

                diff = _git_text(root, ["diff", "--unified=3", parent, commit, "--", file_path])
                record = {
                    "kind": "git_transition",
                    "repo": root.name,
                    "repo_path": str(root),
                    "commit": commit,
                    "parent": parent,
                    "file_path": file_path,
                    "before_source": before,
                    "after_source": after,
                    "diff": diff,
                    "mined_at": datetime.now(timezone.utc).isoformat(),
                }
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                written += 1

    return MineResult(
        repo=root,
        out_path=output,
        commits_scanned=len(commits),
        transitions_written=written,
    )


def _first_parent(repo: Path, commit: str) -> str | None:
    parents = _git_lines(repo, ["rev-list", "--parents", "-n", "1", commit])
    if not parents:
        return None
    parts = parents[0].split()
    if len(parts) < 2:
        return None
    return parts[1]


def _changed_python_files(repo: Path, parent: str, commit: str) -> list[str]:
    files = _git_lines(
        repo,
        ["diff", "--name-only", "--diff-filter=AM", parent, commit, "--", "*.py"],
    )
    return [file for file in files if file.endswith(".py")]


def _show_text(repo: Path, spec: str) -> str | None:
    result = subprocess.run(
        ["git", "show", spec],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    text = _git_text(repo, args)
    return [line for line in text.splitlines() if line]


def _git_text(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout
