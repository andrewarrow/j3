"""Structured candidate generation for Python repairs."""

from __future__ import annotations

import ast
import builtins
import difflib
from dataclasses import dataclass
from pathlib import Path

from actions import PatchAction, PatchActionKind, PatchTarget
from repo import PythonSource, iter_python_sources
from synth import SourceEdit, apply_edit

from .ast_utils import (
    _apply_node_replacements,
    _call_exception,
    _class_fields,
    _defined_names,
    _full_source_edit,
    _function_arg_types,
    _function_uses_len_of,
    _import_insert_line,
    _import_module,
    _imported_names,
    _is_valid_python,
    _local_symbols,
    _module_symbols,
    _nearby_literals,
    _node_edit,
    _operator_alternatives,
    _operator_text,
    _rename_identifier_in_text,
    _render_call_with_keyword_rename,
    _string_literals,
    _subscript_key_alternatives,
)
from .types import CandidatePatch


COMMON_IMPORTS = {
    "Counter": "from collections import Counter",
    "defaultdict": "from collections import defaultdict",
    "datetime": "from datetime import datetime",
    "Path": "from pathlib import Path",
}
BUILTIN_NAMES = set(dir(builtins))


@dataclass(frozen=True, slots=True)
class _LocalImport:
    name: str
    module: str
    import_line: str
    source_path: str


def generate_candidate_patches(repo: Path) -> list[CandidatePatch]:
    """Generate structured candidate edits for source files in a repo."""

    parsed_sources = []
    repo_string_literals: set[str] = set()
    for source in iter_python_sources(repo):
        try:
            tree = ast.parse(source.text)
        except SyntaxError:
            continue
        parsed_sources.append((source, tree))
        repo_string_literals.update(_string_literals(tree))

    local_imports = _local_import_index(parsed_sources)
    candidates: list[CandidatePatch] = []
    for source, tree in parsed_sources:
        path = Path(source.relative_path)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue

        class_fields = _class_fields(tree)
        module_symbols = _module_symbols(tree)
        candidates.extend(
            _add_import_candidates(source.relative_path, source.text, tree, local_imports)
        )
        candidates.extend(_signature_propagation_candidates(source.relative_path, source.text, tree))
        for function in [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]:
            arg_names = {arg.arg for arg in function.args.args}
            arg_types = _function_arg_types(function)
            local_symbols = module_symbols | _local_symbols(function)
            candidates.extend(_guard_candidates(source.relative_path, source.text, function, arg_names))
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    candidates.extend(
                        _return_candidates(source.relative_path, source.text, function, node, arg_names)
                    )
                    candidates.extend(_wrap_try_except_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Compare):
                    candidates.extend(_compare_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Subscript):
                    candidates.extend(
                        _subscript_key_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                elif isinstance(node, ast.Constant):
                    candidates.extend(_literal_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.If):
                    candidates.extend(_modify_condition_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    candidates.extend(
                        _rename_symbol_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            local_symbols,
                        )
                    )
                elif isinstance(node, ast.Call):
                    candidates.extend(_swap_call_arg_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Attribute):
                    candidates.extend(
                        _attribute_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            arg_types,
                            class_fields,
                        )
                    )
    return candidates


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


def _module_name_from_path(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


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


def _guard_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    arg_names: set[str],
) -> list[CandidatePatch]:
    if not function.body:
        return []

    candidates: list[CandidatePatch] = []
    for arg_name in sorted(arg_names):
        if not _function_uses_len_of(function, arg_name):
            continue
        first_statement = function.body[0]
        indent = " " * first_statement.col_offset
        guard = f"if not {arg_name}:\n{indent}    return 0\n{indent}"
        edit = SourceEdit(
            start_line=first_statement.lineno,
            start_col=first_statement.col_offset,
            end_line=first_statement.lineno,
            end_col=first_statement.col_offset,
            replacement=guard,
        )
        patched = apply_edit(source, edit)
        action = PatchAction(
            kind=PatchActionKind.INSERT_GUARD,
            target=PatchTarget(
                file_path=file_path,
                start_line=first_statement.lineno,
                end_line=first_statement.lineno,
                symbol=function.name,
                node_kind=type(first_statement).__name__,
            ),
            params={"condition": f"not {arg_name}", "return": 0},
        )
        candidates.append(
            CandidatePatch(
                file_path=file_path,
                action=action,
                edit=edit,
                original_source=source,
                patched_source=patched,
                reason=f"insert empty-sequence guard for {arg_name}",
            )
        )
    return candidates


def _return_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Return,
    arg_names: set[str],
) -> list[CandidatePatch]:
    expr = ast.get_source_segment(source, node.value)
    if not expr:
        return []

    candidates: list[CandidatePatch] = []
    if {"price", "percent"}.issubset(arg_names) and "percent" in expr and "100" in expr:
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node.value,
                kind=PatchActionKind.REPLACE_EXPR,
                replacement="price * (1 - percent / 100)",
                reason="discount formula candidate",
                symbol=function.name,
            )
        )

    if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mult):
        left = ast.get_source_segment(source, node.value.left)
        right = ast.get_source_segment(source, node.value.right)
        if left and right:
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=node.value,
                    kind=PatchActionKind.REPLACE_EXPR,
                    replacement=f"{left} - ({left} * {right})",
                    reason="convert multiplier into subtraction from base value",
                    symbol=function.name,
                )
            )

    if isinstance(node.value, ast.Subscript):
        subscript_candidate = _last_item_candidate(file_path, source, function, node.value)
        if subscript_candidate is not None:
            candidates.append(subscript_candidate)

    return candidates


def _wrap_try_except_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Return,
) -> list[CandidatePatch]:
    value = ast.get_source_segment(source, node.value) if node.value is not None else None
    if value is None or not isinstance(node.value, ast.Call):
        return []

    exception = _call_exception(node.value)
    if exception is None:
        return []

    inner_indent = " " * (node.col_offset + 4)
    outer_indent = " " * node.col_offset
    replacement = f"try:\n{inner_indent}return {value}\n{outer_indent}except {exception}:\n{inner_indent}return 0"
    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.WRAP_TRY_EXCEPT,
            replacement=replacement,
            reason=f"wrap return in {exception} handler",
            params={"exception": exception, "return": 0},
            symbol=function.name,
        )
    ]


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


def _attribute_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Attribute,
    arg_types: dict[str, str],
    class_fields: dict[str, set[str]],
) -> list[CandidatePatch]:
    if not isinstance(node.value, ast.Name):
        return []

    class_name = arg_types.get(node.value.id)
    if class_name is None:
        return []

    fields = class_fields.get(class_name, set())
    alternatives = sorted(field for field in fields if field != node.attr)
    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.CHANGE_ATTRIBUTE,
            replacement=f"{node.value.id}.{field}",
            reason=f"try attribute {field}",
            params={"from": node.attr, "to": field},
            symbol=function.name,
        )
        for field in alternatives
    ]


def _last_item_candidate(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Subscript,
) -> CandidatePatch | None:
    if not isinstance(node.slice, ast.Constant) or node.slice.value != 0:
        return None

    collection = ast.get_source_segment(source, node.value)
    if not collection:
        return None
    return _candidate(
        file_path=file_path,
        source=source,
        node=node,
        kind=PatchActionKind.REPLACE_EXPR,
        replacement=f"{collection}[-1]",
        reason="replace first item access with last item access",
        symbol=function.name,
    )


def _subscript_key_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Subscript,
    repo_string_literals: set[str],
) -> list[CandidatePatch]:
    if not isinstance(node.slice, ast.Constant) or not isinstance(node.slice.value, str):
        return []

    original = node.slice.value
    alternatives = _subscript_key_alternatives(original, repo_string_literals)
    candidates: list[CandidatePatch] = []
    for replacement in alternatives:
        edit = _node_edit(node.slice, repr(replacement))
        patched = apply_edit(source, edit)
        action = PatchAction(
            kind=PatchActionKind.CHANGE_SUBSCRIPT_KEY,
            target=PatchTarget(
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno,
                symbol=function.name,
                node_kind="Subscript",
            ),
            params={"from": original, "to": replacement},
        )
        candidates.append(
            CandidatePatch(
                file_path=file_path,
                action=action,
                edit=edit,
                original_source=source,
                patched_source=patched,
                reason=f"try subscript key {replacement!r}",
            )
        )
    return candidates


def _literal_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Constant,
) -> list[CandidatePatch]:
    if isinstance(node.value, bool) or not isinstance(node.value, int | float):
        return []

    candidates: list[CandidatePatch] = []
    for replacement in _nearby_literals(node.value):
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node,
                kind=PatchActionKind.CHANGE_LITERAL,
                replacement=repr(replacement),
                reason=f"try nearby literal {replacement!r}",
                params={"from": node.value, "to": replacement},
                symbol=function.name,
            )
        )
    return candidates


def _compare_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Compare,
) -> list[CandidatePatch]:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return []

    original = _operator_text(node.ops[0])
    alternatives = _operator_alternatives(original)
    if not alternatives:
        return []

    left = ast.get_source_segment(source, node.left)
    right = ast.get_source_segment(source, node.comparators[0])
    if not left or not right:
        return []

    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.CHANGE_OPERATOR,
            replacement=f"{left} {operator} {right}",
            reason=f"try comparison operator {operator}",
            params={"from": original, "to": operator},
            symbol=function.name,
        )
        for operator in alternatives
    ]


def _modify_condition_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.If,
) -> list[CandidatePatch]:
    condition = ast.get_source_segment(source, node.test)
    if not condition:
        return []

    candidates: list[CandidatePatch] = []
    if isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not):
        operand = ast.get_source_segment(source, node.test.operand)
        if operand:
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=node.test,
                    kind=PatchActionKind.MODIFY_CONDITION,
                    replacement=operand,
                    reason="remove condition negation",
                    params={"operation": "remove_not", "from": condition, "to": operand},
                    symbol=function.name,
                )
            )
    else:
        candidates.append(
            _candidate(
                file_path=file_path,
                source=source,
                node=node.test,
                kind=PatchActionKind.MODIFY_CONDITION,
                replacement=f"not ({condition})",
                reason="negate condition",
                params={"operation": "add_not", "from": condition, "to": f"not ({condition})"},
                symbol=function.name,
            )
        )

    if isinstance(node.test, ast.BoolOp):
        for index, value in enumerate(node.test.values):
            replacement = ast.get_source_segment(source, value)
            if not replacement or replacement == condition:
                continue
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=node.test,
                    kind=PatchActionKind.MODIFY_CONDITION,
                    replacement=replacement,
                    reason=f"simplify condition to branch {index}",
                    params={"operation": "simplify_boolop", "branch": index, "from": condition, "to": replacement},
                    symbol=function.name,
                )
            )

    return candidates


def _rename_symbol_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Name,
    local_symbols: set[str],
) -> list[CandidatePatch]:
    if node.id in local_symbols or node.id in BUILTIN_NAMES:
        return []

    alternatives = difflib.get_close_matches(node.id, sorted(local_symbols), n=3, cutoff=0.72)
    return [
        _candidate(
            file_path=file_path,
            source=source,
            node=node,
            kind=PatchActionKind.RENAME_SYMBOL,
            replacement=alternative,
            reason=f"rename unknown symbol {node.id} to {alternative}",
            params={"from": node.id, "to": alternative},
            symbol=function.name,
        )
        for alternative in alternatives
    ]


def _signature_propagation_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
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
                    candidates.append(candidate)

    return candidates


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


def _candidate(
    *,
    file_path: str,
    source: str,
    node: ast.AST,
    kind: PatchActionKind,
    replacement: str,
    reason: str,
    params: dict[str, object] | None = None,
    symbol: str | None = None,
) -> CandidatePatch:
    edit = _node_edit(node, replacement)
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=kind,
        target=PatchTarget(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            symbol=symbol,
            node_kind=type(node).__name__,
        ),
        params=params or {"replacement": replacement},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=reason,
    )
