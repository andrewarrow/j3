"""Compact target context for candidate ranking records."""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from repo import PythonSource, iter_python_sources

from .types import CandidatePatch


MAX_UPSTREAM_DISTANCE = 3


@dataclass(frozen=True, slots=True)
class _RepoContext:
    function_qnames: dict[tuple[str, str], str]
    calls: dict[str, frozenset[str]]
    callers: dict[str, frozenset[str]]
    visible_signatures: dict[str, dict[str, tuple[str, ...]]]


def attach_target_context(repo: Path, candidates: list[CandidatePatch]) -> list[CandidatePatch]:
    """Attach compact repo-local target context to generated candidates."""

    if not candidates:
        return candidates
    context = _build_repo_context(repo)
    return [
        replace(candidate, target_context=_candidate_target_context(candidate, context))
        for candidate in candidates
    ]


def _build_repo_context(repo: Path) -> _RepoContext:
    parsed_sources: list[tuple[PythonSource, ast.Module]] = []
    for source in iter_python_sources(repo):
        path = PurePosixPath(source.relative_path)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(source.text)
        except SyntaxError:
            continue
        parsed_sources.append((source, tree))

    module_paths: dict[str, str] = {}
    module_functions: dict[str, set[str]] = {}
    function_qnames: dict[tuple[str, str], str] = {}
    for source, tree in parsed_sources:
        module = _module_name_from_path(PurePosixPath(source.relative_path))
        if not module:
            continue
        module_paths[module] = source.relative_path
        function_names = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        module_functions[module] = function_names
        for name in function_names:
            function_qnames[(source.relative_path, name)] = f"{module}.{name}"

    calls: dict[str, frozenset[str]] = {}
    caller_sets: defaultdict[str, set[str]] = defaultdict(set)
    for source, tree in parsed_sources:
        module = _module_name_from_path(PurePosixPath(source.relative_path))
        if not module:
            continue
        local_functions = module_functions.get(module, set())
        imports = _imported_function_qnames(
            tree,
            current_module=module,
            module_paths=module_paths,
            module_functions=module_functions,
        )
        for function in [node for node in tree.body if isinstance(node, ast.FunctionDef)]:
            qname = f"{module}.{function.name}"
            callees = _called_function_qnames(
                function,
                current_module=module,
                imports=imports,
                local_functions=local_functions,
            )
            calls[qname] = frozenset(callees)
            for callee in callees:
                caller_sets[callee].add(qname)

    callers = {
        qname: frozenset(caller_sets.get(qname, set()))
        for qname in set(calls) | set(caller_sets)
    }
    return _RepoContext(
        function_qnames=function_qnames,
        calls=calls,
        callers=callers,
        visible_signatures=_visible_signature_index(parsed_sources, module_functions),
    )


def _candidate_target_context(
    candidate: CandidatePatch,
    context: _RepoContext,
) -> dict[str, object]:
    symbol = candidate.action.target.symbol
    qname = context.function_qnames.get((candidate.file_path, symbol or ""))
    target: dict[str, object] = {
        "role": _target_role(candidate.file_path),
    }
    subscript_context = _subscript_returned_mapping_context(candidate)
    if subscript_context:
        target.update(subscript_context)
    dict_context = _dict_literal_key_context(candidate)
    if dict_context:
        target.update(dict_context)
    call_context = _swap_call_arg_context(candidate, context)
    if call_context:
        target.update(call_context)
    if qname is None:
        return target

    target["qualified_symbol"] = qname
    target["callee_count"] = len(context.calls.get(qname, frozenset()))
    target["caller_count"] = len(context.callers.get(qname, frozenset()))
    upstream = _upstream_callers(qname, context.callers, max_distance=MAX_UPSTREAM_DISTANCE)
    if upstream:
        target["upstream_callers"] = [
            {
                "symbol": caller.rsplit(".", maxsplit=1)[-1],
                "distance": distance,
            }
            for caller, distance in upstream
        ]
    return target


def _subscript_returned_mapping_context(candidate: CandidatePatch) -> dict[str, object]:
    if candidate.action.kind.value != "change_subscript_key":
        return {}

    params = candidate.action.params
    original = params.get("from")
    replacement = params.get("to")
    if not isinstance(original, str) or not isinstance(replacement, str):
        return {}

    try:
        tree = ast.parse(candidate.original_source)
    except SyntaxError:
        return {}

    target_function = _find_target_function(
        tree,
        symbol=candidate.action.target.symbol,
        start_line=candidate.action.target.start_line,
    )
    if target_function is None:
        return {}

    subscript = _find_target_subscript(
        target_function,
        key=original,
        start_line=candidate.action.target.start_line,
        end_line=candidate.action.target.end_line,
    )
    if subscript is None or not isinstance(subscript.ctx, ast.Store):
        return {}
    if not isinstance(subscript.value, ast.Name):
        return {}

    mapping_name = subscript.value.id
    if not _function_returns_name(target_function, mapping_name):
        return {}

    keys = _assigned_dict_string_keys(target_function, mapping_name)
    if not keys:
        return {}

    result: dict[str, object] = {
        "subscript_write_to_returned_mapping": True,
        "returned_mapping_key_count": len(keys),
    }
    if original in keys:
        result["subscript_from_matches_returned_mapping_key"] = True
    if replacement in keys:
        result["subscript_to_matches_returned_mapping_key"] = True
    return result


def _swap_call_arg_context(
    candidate: CandidatePatch,
    context: _RepoContext,
) -> dict[str, object]:
    if candidate.action.kind.value != "swap_call_arg":
        return {}

    params = candidate.action.params
    left = params.get("left")
    right = params.get("right")
    if not isinstance(left, int) or not isinstance(right, int) or left < 0 or right < 0:
        return {}

    try:
        tree = ast.parse(candidate.original_source)
    except SyntaxError:
        return {}

    target_function = _find_target_function(
        tree,
        symbol=candidate.action.target.symbol,
        start_line=candidate.action.target.start_line,
    )
    if target_function is None:
        return {}

    call = _find_target_call(
        target_function,
        start_line=candidate.action.target.start_line,
        end_line=candidate.action.target.end_line,
        min_args=right + 1,
    )
    if call is None:
        return {}

    result: dict[str, object] = {}
    result.update(_mapping_get_swap_context(call, left=left, right=right))

    callee_name = call.func.id if isinstance(call.func, ast.Name) else None
    if callee_name is None:
        return result
    signature = context.visible_signatures.get(candidate.file_path, {}).get(callee_name)
    if signature is None or right >= len(signature):
        return result

    left_name = _arg_name(call.args[left])
    right_name = _arg_name(call.args[right])
    if left_name is None or right_name is None:
        return result

    left_param = signature[left]
    right_param = signature[right]
    before = _alignment_state(
        left_arg=left_name,
        right_arg=right_name,
        left_param=left_param,
        right_param=right_param,
    )
    after = _alignment_state(
        left_arg=right_name,
        right_arg=left_name,
        left_param=left_param,
        right_param=right_param,
    )
    result.update(
        {
            "swap_call_callee": callee_name,
            "swap_call_left_param": left_param,
            "swap_call_right_param": right_param,
            "swap_call_left_arg_name": left_name,
            "swap_call_right_arg_name": right_name,
            "swap_call_name_alignment_before": before,
            "swap_call_name_alignment_after": after,
        }
    )
    if before == "preserved" and after == "preserved":
        result["swap_call_preserves_name_alignment"] = True
    elif before == "preserved" and after != "preserved":
        result["swap_call_breaks_name_alignment"] = True
    elif before != "preserved" and after == "preserved":
        result["swap_call_repairs_name_alignment"] = True
    return result


def _find_target_call(
    function: ast.FunctionDef,
    *,
    start_line: int,
    end_line: int,
    min_args: int = 0,
) -> ast.Call | None:
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if node.lineno != start_line:
            continue
        if (node.end_lineno or node.lineno) != end_line:
            continue
        if len(node.args) < min_args:
            continue
        return node
    return None


def _mapping_get_swap_context(call: ast.Call, *, left: int, right: int) -> dict[str, object]:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "get":
        return {}
    if (left, right) != (0, 1):
        return {}
    if len(call.args) < 2:
        return {}
    return {
        "swap_call_method": "get",
        "swap_call_mapping_get_key_default_swapped": True,
        "swap_call_left_role": "mapping_key",
        "swap_call_right_role": "mapping_default",
        "swap_call_left_arg_kind": _arg_role_kind(call.args[left]),
        "swap_call_right_arg_kind": _arg_role_kind(call.args[right]),
    }


def _alignment_state(
    *,
    left_arg: str,
    right_arg: str,
    left_param: str,
    right_param: str,
) -> str:
    left_aligned = left_arg == left_param
    right_aligned = right_arg == right_param
    if left_aligned and right_aligned:
        return "preserved"
    if left_aligned or right_aligned:
        return "partial"
    return "broken"


def _arg_name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _arg_role_kind(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return "empty_string_literal" if node.value == "" else "string_literal"
        if node.value is None:
            return "none_literal"
        if isinstance(node.value, bool):
            return "bool_literal"
        if isinstance(node.value, int | float):
            return "number_literal"
    if isinstance(node, ast.Name):
        return "name"
    return type(node).__name__


def _dict_literal_key_context(candidate: CandidatePatch) -> dict[str, object]:
    if candidate.action.kind.value not in {"change_dict_key", "change_dict_value"}:
        return {}

    try:
        tree = ast.parse(candidate.original_source)
    except SyntaxError:
        return {}

    target_function = _find_target_function(
        tree,
        symbol=candidate.action.target.symbol,
        start_line=candidate.action.target.start_line,
    )
    if target_function is None:
        return {}

    target_dict = _find_target_dict_literal(
        target_function,
        action=candidate.action.kind.value,
        start_line=candidate.action.target.start_line,
        end_line=candidate.action.target.end_line,
    )
    if target_dict is None:
        return {}

    keys = _dict_literal_string_keys(target_dict)
    if not keys:
        return {}

    result: dict[str, object] = {
        "dict_literal_key_count": len(keys),
        "dict_literal_keys": sorted(keys),
    }
    params = candidate.action.params
    key = params.get("key")
    original = params.get("from")
    replacement = params.get("to")
    if candidate.action.kind.value == "change_dict_value" and isinstance(key, str):
        result["dict_value_key"] = key
        if key in keys:
            result["dict_value_key_in_same_mapping"] = True
    elif candidate.action.kind.value == "change_dict_key":
        if isinstance(original, str):
            result["dict_key_from"] = original
            if original in keys:
                result["dict_key_from_in_same_mapping"] = True
        if isinstance(replacement, str):
            result["dict_key_to"] = replacement
            if replacement in keys:
                result["dict_key_to_in_same_mapping"] = True
    return result


def _find_target_dict_literal(
    function: ast.FunctionDef,
    *,
    action: str,
    start_line: int,
    end_line: int,
) -> ast.Dict | None:
    for node in ast.walk(function):
        if not isinstance(node, ast.Dict):
            continue
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            target_node: ast.AST | None = key_node if action == "change_dict_key" else value_node
            if target_node is None:
                continue
            if target_node.lineno != start_line:
                continue
            if (target_node.end_lineno or target_node.lineno) != end_line:
                continue
            return node
    return None


def _dict_literal_string_keys(node: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for key_node in node.keys:
        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
            keys.add(key_node.value)
    return keys


def _find_target_function(
    tree: ast.Module,
    *,
    symbol: str | None,
    start_line: int,
) -> ast.FunctionDef | None:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and (symbol is None or node.name == symbol)
        and node.lineno <= start_line <= (node.end_lineno or node.lineno)
    ]
    if matches:
        return min(matches, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)
    return None


def _find_target_subscript(
    function: ast.FunctionDef,
    *,
    key: str,
    start_line: int,
    end_line: int,
) -> ast.Subscript | None:
    for node in ast.walk(function):
        if not isinstance(node, ast.Subscript):
            continue
        if node.lineno != start_line or (node.end_lineno or node.lineno) != end_line:
            continue
        if isinstance(node.slice, ast.Constant) and node.slice.value == key:
            return node
    return None


def _function_returns_name(function: ast.FunctionDef, name: str) -> bool:
    return any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Name)
        and node.value.id == name
        for node in ast.walk(function)
    )


def _assigned_dict_string_keys(function: ast.FunctionDef, name: str) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        if not _assigns_to_name(node, name):
            continue
        for key_node in value.keys:
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                keys.add(key_node.value)
    return keys


def _assigns_to_name(node: ast.AnnAssign | ast.Assign, name: str) -> bool:
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == name
    return any(isinstance(target, ast.Name) and target.id == name for target in node.targets)


def _target_role(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if "tests" in path.parts or path.name.startswith("test_"):
        return "test"
    if path.stem in {"api", "__init__"}:
        return "public_api"
    return "helper"


def _upstream_callers(
    qname: str,
    callers: dict[str, frozenset[str]],
    *,
    max_distance: int,
) -> list[tuple[str, int]]:
    distances: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((caller, 1) for caller in sorted(callers.get(qname, ())))
    while queue:
        caller, distance = queue.popleft()
        if caller in distances or distance > max_distance:
            continue
        distances[caller] = distance
        for next_caller in sorted(callers.get(caller, ())):
            queue.append((next_caller, distance + 1))
    return sorted(distances.items(), key=lambda item: (item[1], item[0]))


def _called_function_qnames(
    function: ast.FunctionDef,
    *,
    current_module: str,
    imports: dict[str, str],
    local_functions: set[str],
) -> set[str]:
    callees: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in imports:
                callees.add(imports[name])
            elif name in local_functions:
                callees.add(f"{current_module}.{name}")
    return callees


def _imported_function_qnames(
    tree: ast.Module,
    *,
    current_module: str,
    module_paths: dict[str, str],
    module_functions: dict[str, set[str]],
) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolve_import_from_module(current_module, node)
        if module is None or module not in module_functions or module not in module_paths:
            continue
        for alias in node.names:
            if alias.name not in module_functions[module]:
                continue
            imports[alias.asname or alias.name] = f"{module}.{alias.name}"
    return imports


def _visible_signature_index(
    parsed_sources: list[tuple[PythonSource, ast.Module]],
    module_functions: dict[str, set[str]],
) -> dict[str, dict[str, tuple[str, ...]]]:
    module_signatures: dict[str, dict[str, tuple[str, ...]]] = {}
    module_paths: dict[str, str] = {}
    for source, tree in parsed_sources:
        module = _module_name_from_path(PurePosixPath(source.relative_path))
        if not module:
            continue
        module_paths[module] = source.relative_path
        module_signatures[module] = {
            node.name: tuple(
                arg.arg
                for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                if arg.arg not in {"self", "cls"}
            )
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    index: dict[str, dict[str, tuple[str, ...]]] = {}
    for source, tree in parsed_sources:
        current_module = _module_name_from_path(PurePosixPath(source.relative_path))
        visible: dict[str, tuple[str, ...]] = {}
        if current_module in module_signatures:
            visible.update(module_signatures[current_module])
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            module = _resolve_import_from_module(current_module, node)
            if module is None or module not in module_signatures or module not in module_paths:
                continue
            for alias in node.names:
                if alias.name not in module_functions.get(module, set()):
                    continue
                signature = module_signatures[module].get(alias.name)
                if signature is not None:
                    visible[alias.asname or alias.name] = signature
        index[source.relative_path] = visible
    return index


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


def _module_name_from_path(path: PurePosixPath) -> str:
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)
