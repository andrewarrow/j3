"""Call-expression candidate generation."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from actions import PatchActionKind
from repo import PythonSource

from ..types import CandidatePatch
from .common import _candidate
from .modules import _module_name_from_path, _resolve_import_from_module


@dataclass(frozen=True, slots=True)
class _FunctionSignature:
    name: str
    params: tuple[str, ...]


def _call_signature_index(
    parsed_sources: list[tuple[PythonSource, ast.Module]],
) -> dict[str, dict[str, _FunctionSignature]]:
    """Return callable signatures visible by simple local/imported names."""

    module_functions: dict[str, dict[str, _FunctionSignature]] = {}
    for source, tree in parsed_sources:
        module = _module_name_from_path(Path(source.relative_path))
        if not module:
            continue
        module_functions[module] = {
            node.name: _FunctionSignature(
                name=node.name,
                params=tuple(
                    arg.arg
                    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                    if arg.arg not in {"self", "cls"}
                ),
            )
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    index: dict[str, dict[str, _FunctionSignature]] = {}
    for source, tree in parsed_sources:
        current_module = _module_name_from_path(Path(source.relative_path))
        visible: dict[str, _FunctionSignature] = {}
        if current_module in module_functions:
            visible.update(module_functions[current_module])
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            module = _resolve_import_from_module(current_module, node)
            if module is None or module not in module_functions:
                continue
            for alias in node.names:
                signature = module_functions[module].get(alias.name)
                if signature is not None:
                    visible[alias.asname or alias.name] = signature
        index[source.relative_path] = visible
    return index


def _swap_call_arg_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Call,
) -> list[CandidatePatch]:
    if len(node.args) < 2:
        return []
    func = ast.get_source_segment(source, node.func)
    args = [ast.get_source_segment(source, arg) for arg in node.args]
    if not func or any(arg is None for arg in args):
        return []

    keyword_parts: list[str] = []
    for keyword in node.keywords:
        value = ast.get_source_segment(source, keyword.value)
        if value is None:
            return []
        if keyword.arg is None:
            keyword_parts.append(f"**{value}")
        else:
            keyword_parts.append(f"{keyword.arg}={value}")

    candidates: list[CandidatePatch] = []
    for left in range(len(args) - 1):
        right = left + 1
        swapped = list(args)
        swapped[left], swapped[right] = swapped[right], swapped[left]
        call_args = [arg for arg in swapped if arg is not None] + keyword_parts
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node,
                kind=PatchActionKind.SWAP_CALL_ARG,
                replacement=f"{func}({', '.join(call_args)})",
                reason=f"swap call arguments {left} and {right}",
                params={"left": left, "right": right},
                symbol=function.name,
            )
        )
    return candidates


def _add_keyword_arg_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Call,
    visible_signatures: Mapping[str, _FunctionSignature],
) -> list[CandidatePatch]:
    if not isinstance(node.func, ast.Name):
        return []
    signature = visible_signatures.get(node.func.id)
    if signature is None:
        return []
    if any(keyword.arg is None for keyword in node.keywords):
        return []

    outer_params = {
        arg.arg
        for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
        if arg.arg not in {"self", "cls"}
    }
    if not outer_params:
        return []

    supplied_keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
    supplied_by_position = set(signature.params[: len(node.args)])
    candidates: list[CandidatePatch] = []
    for param in signature.params:
        if param not in outer_params:
            continue
        if param in supplied_keywords or param in supplied_by_position:
            continue
        replacement = _render_call_with_added_keyword(source, node, param)
        if replacement is None:
            continue
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node,
                kind=PatchActionKind.ADD_KEYWORD_ARG,
                replacement=replacement,
                reason=f"pass through keyword argument {param}",
                params={"keyword": param, "value": param, "callee": signature.name},
                symbol=function.name,
            )
        )
    return candidates


def _render_call_with_added_keyword(source: str, node: ast.Call, keyword_name: str) -> str | None:
    func = ast.get_source_segment(source, node.func)
    if not func:
        return None

    parts: list[str] = []
    for arg in node.args:
        value = ast.get_source_segment(source, arg)
        if value is None:
            return None
        parts.append(value)
    for keyword in node.keywords:
        value = ast.get_source_segment(source, keyword.value)
        if value is None or keyword.arg is None:
            return None
        parts.append(f"{keyword.arg}={value}")
    parts.append(f"{keyword_name}={keyword_name}")
    return f"{func}({', '.join(parts)})"
