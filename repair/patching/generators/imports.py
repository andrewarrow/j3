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
    return candidates


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
