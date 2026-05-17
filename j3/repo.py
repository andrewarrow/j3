"""Repository discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "venv",
    }
)


@dataclass(frozen=True, slots=True)
class PythonSource:
    """One Python source file loaded from a repository."""

    path: Path
    relative_path: str
    text: str


def iter_python_sources(repo_root: Path) -> list[PythonSource]:
    """Return Python files under a repo, excluding common generated directories."""

    root = repo_root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repo is not a directory: {root}")

    sources: list[PythonSource] = []
    for path in sorted(root.rglob("*.py")):
        if _is_excluded(path, root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        sources.append(
            PythonSource(
                path=path,
                relative_path=path.relative_to(root).as_posix(),
                text=text,
            )
        )
    return sources


def _is_excluded(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in DEFAULT_EXCLUDE_DIRS for part in relative_parts)
