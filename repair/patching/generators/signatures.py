"""Signature propagation candidate generation."""

from __future__ import annotations

import ast
import difflib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from actions import PatchAction, PatchActionKind, PatchTarget
from repo import PythonSource

from ..ast_utils import (
    _apply_node_replacements,
    _full_source_edit,
    _is_valid_python,
    _rename_identifier_in_text,
    _render_call_with_keyword_rename,
)
from ..types import CandidatePatch
from .common import _candidate
from .modules import _module_name_from_path, _resolve_import_from_module


@dataclass(frozen=True, slots=True)
class _FunctionOrigin:
    file_path: str
    name: str


def _external_signature_keyword_index(
    parsed_sources: list[tuple[PythonSource, ast.Module]],
) -> dict[str, dict[str, set[str]]]:
    module_paths: dict[str, str] = {}
    module_functions: dict[str, set[str]] = {}
    for source, tree in parsed_sources:
        module = _module_name_from_path(Path(source.relative_path))
        if not module:
            continue
        module_paths[module] = source.relative_path
        module_functions[module] = {
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    index: dict[str, dict[str, set[str]]] = {}
    for source, tree in parsed_sources:
        current_module = _module_name_from_path(Path(source.relative_path))
        imported_functions = _imported_function_origins(
            tree,
            current_module=current_module,
            module_paths=module_paths,
            module_functions=module_functions,
        )
        if not imported_functions:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            origin = imported_functions.get(node.func.id)
            if origin is None or origin.file_path == source.relative_path:
                continue
            keyword_names = [keyword.arg for keyword in node.keywords if keyword.arg]
            if not keyword_names:
                continue
            function_keywords = index.setdefault(origin.file_path, {}).setdefault(origin.name, set())
            function_keywords.update(keyword_names)
    return index


def _imported_function_origins(
    tree: ast.Module,
    *,
    current_module: str,
    module_paths: Mapping[str, str],
    module_functions: Mapping[str, set[str]],
) -> dict[str, _FunctionOrigin]:
    origins: dict[str, _FunctionOrigin] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolve_import_from_module(current_module, node)
        if module is None or module not in module_functions:
            continue
        file_path = module_paths.get(module)
        if file_path is None:
            continue
        for alias in node.names:
            if alias.name not in module_functions[module]:
                continue
            origins[alias.asname or alias.name] = _FunctionOrigin(
                file_path=file_path,
                name=alias.name,
            )
    return origins


def _signature_propagation_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
    *,
    external_keywords: Mapping[str, set[str]] | None = None,
) -> list[CandidatePatch]:
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    if not functions:
        return []

    calls_by_name: dict[str, list[ast.Call]] = {name: [] for name in functions}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions:
            calls_by_name[node.func.id].append(node)

    candidates: list[CandidatePatch] = []
    seen: set[tuple[str, str, str, str]] = set()
    for function_name, function in functions.items():
        params = [arg.arg for arg in function.args.args]
        if not params:
            continue

        calls = calls_by_name[function_name]
        for call in calls:
            for keyword in [keyword for keyword in call.keywords if keyword.arg]:
                if keyword.arg in params:
                    continue

                close_params = difflib.get_close_matches(keyword.arg, params, n=2, cutoff=0.65)
                for parameter in close_params:
                    replacement = _render_call_with_keyword_rename(source, call, keyword.arg, parameter)
                    if replacement:
                        candidates.append(
                            _candidate(
                                file_path=file_path,
                                source=source,
                                node=call,
                                kind=PatchActionKind.RENAME_SYMBOL,
                                replacement=replacement,
                                reason=f"rename call keyword {keyword.arg} to {parameter}",
                                params={"from": keyword.arg, "to": parameter, "scope": "call_site"},
                                symbol=function_name,
                            )
                        )

                candidate = _signature_candidate_from_keyword(
                    file_path=file_path,
                    source=source,
                    function=function,
                    calls=calls,
                    keyword_name=keyword.arg,
                    params=params,
                )
                if candidate is not None:
                    key = _signature_candidate_key(candidate)
                    if key not in seen:
                        seen.add(key)
                        candidates.append(candidate)

        for keyword_name in sorted((external_keywords or {}).get(function_name, set())):
            if keyword_name in params:
                continue
            candidate = _signature_candidate_from_keyword(
                file_path=file_path,
                source=source,
                function=function,
                calls=calls,
                keyword_name=keyword_name,
                params=params,
            )
            if candidate is not None:
                key = _signature_candidate_key(candidate)
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)

    return candidates


def _signature_candidate_key(candidate: CandidatePatch) -> tuple[str, str, str, str]:
    return (
        candidate.file_path,
        candidate.action.target.symbol or "",
        str(candidate.action.params.get("from", "")),
        str(candidate.action.params.get("to", "")),
    )


def _signature_candidate_from_keyword(
    *,
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    calls: list[ast.Call],
    keyword_name: str,
    params: list[str],
) -> CandidatePatch | None:
    keyword_names = {
        keyword.arg
        for call in calls
        for keyword in call.keywords
        if keyword.arg
    }
    rename_from = [param for param in params if param not in keyword_names]
    if len(rename_from) != 1 or keyword_name in params:
        return None

    old_name = rename_from[0]
    function_segment = ast.get_source_segment(source, function)
    if function_segment is None:
        return None

    replacements: list[tuple[ast.AST, str]] = [
        (function, _rename_identifier_in_text(function_segment, old_name, keyword_name))
    ]
    for call in calls:
        replacement = _render_call_with_keyword_rename(source, call, old_name, keyword_name)
        if replacement is not None:
            replacements.append((call, replacement))

    patched = _apply_node_replacements(source, replacements)
    if patched == source or not _is_valid_python(patched):
        return None

    edit = _full_source_edit(source)
    action = PatchAction(
        kind=PatchActionKind.PROPAGATE_SIGNATURE,
        target=PatchTarget(
            file_path=file_path,
            start_line=function.lineno,
            end_line=function.end_lineno,
            symbol=function.name,
            node_kind="FunctionDef",
        ),
        params={"from": old_name, "to": keyword_name},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=f"propagate signature name {old_name} to {keyword_name}",
    )
