"""Call-expression candidate generation."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from j3.actions import PatchActionKind
from j3.repo import PythonSource

from ..types import CandidatePatch
from .common import _candidate
from .modules import _module_name_from_path, _resolve_import_from_module


@dataclass(frozen=True, slots=True)
class _FunctionSignature:
    name: str
    params: tuple[str, ...]
    defaults: Mapping[str, object]


def _call_signature_index(
    parsed_sources: list[tuple[PythonSource, ast.Module]],
) -> dict[str, dict[str, _FunctionSignature]]:
    """Return callable signatures visible by simple local/imported names."""

    module_functions: dict[str, dict[str, _FunctionSignature]] = {}
    for source, tree in parsed_sources:
        module = _module_name_from_path(Path(source.relative_path))
        if not module:
            continue
        signatures: dict[str, _FunctionSignature] = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            params = tuple(
                arg.arg
                for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if arg.arg not in {"self", "cls"}
            )
            signatures[node.name] = _FunctionSignature(
                name=node.name,
                params=params,
                defaults=_function_literal_defaults(node),
            )
        module_functions[module] = signatures

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

    supplied_keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
    supplied_by_position = set(signature.params[: len(node.args)])
    candidates: list[CandidatePatch] = []
    for param in signature.params:
        if param in supplied_keywords or param in supplied_by_position:
            continue
        if param in outer_params:
            replacement = _render_call_with_added_keyword(source, node, param, param)
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
            continue

        default = signature.defaults.get(param)
        if not isinstance(default, bool):
            continue
        value = not default
        replacement = _render_call_with_added_keyword(source, node, param, str(value))
        if replacement is None:
            continue
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node,
                kind=PatchActionKind.ADD_KEYWORD_ARG,
                replacement=replacement,
                reason=f"set boolean keyword argument {param}",
                params={"keyword": param, "value": value, "callee": signature.name},
                symbol=function.name,
            )
        )
    return candidates


def _function_literal_defaults(function: ast.FunctionDef) -> dict[str, object]:
    defaults: dict[str, object] = {}
    positional_args = [*function.args.posonlyargs, *function.args.args]
    positional_defaults = function.args.defaults
    defaulted_args = positional_args[len(positional_args) - len(positional_defaults) :]
    for arg, default in zip(defaulted_args, positional_defaults, strict=True):
        if arg.arg in {"self", "cls"}:
            continue
        if isinstance(default, ast.Constant):
            defaults[arg.arg] = default.value

    for arg, default in zip(function.args.kwonlyargs, function.args.kw_defaults, strict=True):
        if arg.arg in {"self", "cls"} or default is None:
            continue
        if isinstance(default, ast.Constant):
            defaults[arg.arg] = default.value
    return defaults


def _render_call_with_added_keyword(
    source: str,
    node: ast.Call,
    keyword_name: str,
    keyword_value: str,
) -> str | None:
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
    parts.append(f"{keyword_name}={keyword_value}")
    return f"{func}({', '.join(parts)})"
