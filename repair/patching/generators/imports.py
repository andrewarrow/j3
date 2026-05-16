"""Import-related candidate generation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from actions import PatchAction, PatchActionKind, PatchTarget
from repo import PythonSource
from synth import SourceEdit, apply_edit

from ..ast_utils import _defined_names, _import_insert_line, _import_module, _imported_names
from ..types import CandidatePatch
from .common import BUILTIN_NAMES
from .modules import _module_name_from_path


COMMON_IMPORTS = {
    "Counter": "from collections import Counter",
    "defaultdict": "from collections import defaultdict",
    "datetime": "from datetime import datetime",
    "Path": "from pathlib import Path",
}


@dataclass(frozen=True, slots=True)
class _LocalImport:
    name: str
    module: str
    import_line: str
    source_path: str


def _local_import_index(
    parsed_sources: list[tuple[PythonSource, ast.Module]],
) -> dict[str, list[_LocalImport]]:
    imports: dict[str, list[_LocalImport]] = {}
    for source, tree in parsed_sources:
        relative_path = source.relative_path
        path = Path(relative_path)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        module = _module_name_from_path(path)
        if not module:
            continue
        for name in sorted(_defined_names(tree)):
            import_line = f"from {module} import {name}"
            imports.setdefault(name, []).append(
                _LocalImport(
                    name=name,
                    module=module,
                    import_line=import_line,
                    source_path=relative_path,
                )
            )
    for matches in imports.values():
        matches.sort(key=lambda item: (item.module, item.name))
    return imports


def _add_import_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
    local_imports: dict[str, list[_LocalImport]],
) -> list[CandidatePatch]:
    imported_names = _imported_names(tree)
    defined_names = _defined_names(tree)
    used_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    candidates: list[CandidatePatch] = []
    missing_names = used_names - imported_names - defined_names - BUILTIN_NAMES
    for name in sorted(missing_names):
        if name in COMMON_IMPORTS:
            candidates.append(
                _add_import_candidate(file_path, source, tree, name, COMMON_IMPORTS[name])
            )
        for local_import in local_imports.get(name, []):
            if local_import.source_path == file_path:
                continue
            candidates.append(
                _add_import_candidate(
                    file_path,
                    source,
                    tree,
                    name,
                    local_import.import_line,
                )
            )
    candidates.extend(_import_fallback_candidates(file_path, source, tree, local_imports))
    return candidates


def _import_fallback_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
    local_imports: dict[str, list[_LocalImport]],
) -> list[CandidatePatch]:
    candidates: list[CandidatePatch] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module is None or len(node.names) != 1:
            continue
        alias = node.names[0]
        if alias.asname is not None or alias.name == "*":
            continue
        primary_module = _absolute_import_module(file_path, node)
        if primary_module is None:
            continue
        original_import = ast.get_source_segment(source, node)
        if original_import is None:
            continue
        for local_import in local_imports.get(alias.name, []):
            if local_import.source_path == file_path or local_import.module == primary_module:
                continue
            candidates.append(
                _import_fallback_candidate(
                    file_path=file_path,
                    source=source,
                    node=node,
                    name=alias.name,
                    primary_module=primary_module,
                    primary_import=original_import,
                    fallback_import=local_import.import_line,
                    fallback_module=local_import.module,
                )
            )
    return candidates


def _absolute_import_module(file_path: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    package_parts = list(Path(file_path).with_suffix("").parts[:-1])
    if node.level > len(package_parts) + 1:
        return None
    prefix = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        prefix.extend(node.module.split("."))
    return ".".join(part for part in prefix if part)


def _import_fallback_candidate(
    *,
    file_path: str,
    source: str,
    node: ast.ImportFrom,
    name: str,
    primary_module: str,
    primary_import: str,
    fallback_import: str,
    fallback_module: str,
) -> CandidatePatch:
    base_indent = " " * node.col_offset
    nested_indent = base_indent + "    "
    replacement = "\n".join(
        [
            "try:",
            f"{nested_indent}{primary_import}",
            f"{base_indent}except ImportError:",
            f"{nested_indent}{fallback_import}",
        ]
    )
    edit = SourceEdit(
        start_line=node.lineno,
        start_col=node.col_offset,
        end_line=node.end_lineno,
        end_col=node.end_col_offset,
        replacement=replacement,
    )
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.ADD_IMPORT_FALLBACK,
        target=PatchTarget(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            symbol=name,
            node_kind="ImportFrom",
        ),
        params={
            "name": name,
            "primary_module": primary_module,
            "fallback_module": fallback_module,
            "primary_import": primary_import,
            "fallback_import": fallback_import,
        },
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=f"fallback import for {name}",
    )


def _add_import_candidate(
    file_path: str,
    source: str,
    tree: ast.Module,
    name: str,
    import_line: str,
) -> CandidatePatch:
    insert_line = _import_insert_line(tree)
    edit = SourceEdit(
        start_line=insert_line,
        start_col=0,
        end_line=insert_line,
        end_col=0,
        replacement=f"{import_line}\n",
    )
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.ADD_IMPORT,
        target=PatchTarget(
            file_path=file_path,
            start_line=insert_line,
            end_line=insert_line,
            symbol=name,
            node_kind="Import",
        ),
        params={
            "name": name,
            "module": _import_module(import_line),
            "import": import_line,
        },
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=f"add missing import for {name}",
    )
