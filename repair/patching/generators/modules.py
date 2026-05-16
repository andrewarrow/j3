"""Module-name helpers for local Python sources."""

from __future__ import annotations

import ast
from pathlib import Path


def _resolve_import_from_module(current_module: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    if not current_module:
        return node.module

    parts = current_module.split(".")
    if node.level > len(parts):
        return node.module
    base = parts[: len(parts) - node.level]
    if node.module:
        base.append(node.module)
    if not base:
        return None
    return ".".join(base)


def _module_name_from_path(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)
