"""Control-flow candidate generation."""

from __future__ import annotations

import ast

from actions import PatchAction, PatchActionKind, PatchTarget
from synth import SourceEdit, apply_edit

from ..ast_utils import (
    _call_exception,
    _full_source_edit,
    _function_uses_len_of,
    _import_insert_line,
    _is_valid_python,
)
from ..types import CandidatePatch
from .common import _candidate
from .data_access import _last_item_candidate


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


def _state_flag_guard_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
    function: ast.FunctionDef,
) -> list[CandidatePatch]:
    side_effect_lists = _module_list_appends(function, _module_list_names(tree))
    if not side_effect_lists:
        return []

    return_expr = _last_return_expr(source, function)
    candidates: list[CandidatePatch] = []
    for flag_name in _module_false_flags(tree):
        if _function_references_name(function, flag_name):
            continue
        related_lists = [
            name
            for name in side_effect_lists
            if _names_look_related(flag_name, name, function.name)
        ]
        if not related_lists:
            continue
        return_value = return_expr or related_lists[0]
        candidate = _state_flag_guard_candidate(
            file_path=file_path,
            source=source,
            function=function,
            flag_name=flag_name,
            return_value=return_value,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _state_flag_guard_candidate(
    *,
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    flag_name: str,
    return_value: str,
) -> CandidatePatch | None:
    insertion = _guard_insertion_statement(function)
    if insertion is None:
        return None

    indent = " " * insertion.col_offset
    guard = (
        f"global {flag_name}\n"
        f"{indent}if {flag_name}:\n"
        f"{indent}    return {return_value}\n"
        f"{indent}{flag_name} = True\n"
        f"{indent}"
    )
    edit = SourceEdit(
        start_line=insertion.lineno,
        start_col=insertion.col_offset,
        end_line=insertion.lineno,
        end_col=insertion.col_offset,
        replacement=guard,
    )
    patched = apply_edit(source, edit)
    if patched == source or not _is_valid_python(patched):
        return None

    action = PatchAction(
        kind=PatchActionKind.INSERT_GUARD,
        target=PatchTarget(
            file_path=file_path,
            start_line=insertion.lineno,
            end_line=insertion.lineno,
            symbol=function.name,
            node_kind=type(insertion).__name__,
        ),
        params={
            "condition": flag_name,
            "state_flag": flag_name,
            "return": return_value,
        },
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=f"insert idempotence guard for {flag_name}",
    )


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


def _fallback_warning_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
    function: ast.FunctionDef,
    node: ast.If,
) -> list[CandidatePatch]:
    """Replace a hard missing-setting error with a default plus warning."""

    if len(node.body) != 1 or not isinstance(node.body[0], ast.Raise):
        return []
    if not _raises_value_error(node.body[0]):
        return []

    missing_attribute = _none_checked_self_attribute(node.test)
    if missing_attribute is None:
        return []

    candidates: list[CandidatePatch] = []
    for fallback in (0.05, 0.1, 0):
        candidate = _fallback_warning_candidate(
            file_path=file_path,
            source=source,
            tree=tree,
            function=function,
            raise_node=node.body[0],
            attribute=missing_attribute,
            fallback=fallback,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _fallback_warning_candidate(
    *,
    file_path: str,
    source: str,
    tree: ast.Module,
    function: ast.FunctionDef,
    raise_node: ast.Raise,
    attribute: str,
    fallback: float | int,
) -> CandidatePatch | None:
    indent = " " * raise_node.col_offset
    fallback_text = repr(fallback)
    replacement = (
        f"{indent}self.{attribute} = {fallback_text}\n"
        f"{indent}warnings.warn(\n"
        f"{indent}    \"Defaulting to `{attribute}={fallback_text}`.\",\n"
        f"{indent}    UserWarning,\n"
        f"{indent}    stacklevel=2,\n"
        f"{indent})"
    )
    edit = SourceEdit(
        start_line=raise_node.lineno,
        start_col=0,
        end_line=raise_node.end_lineno,
        end_col=raise_node.end_col_offset,
        replacement=replacement,
    )
    patched = apply_edit(source, edit)
    if not _has_warnings_import(tree):
        insert_line = _import_insert_line(tree)
        lines = patched.splitlines(keepends=True)
        insertion = "import warnings\n"
        offset = sum(len(line) for line in lines[: insert_line - 1])
        patched = patched[:offset] + insertion + patched[offset:]

    if patched == source or not _is_valid_python(patched):
        return None

    action = PatchAction(
        kind=PatchActionKind.ADD_FALLBACK_WARNING,
        target=PatchTarget(
            file_path=file_path,
            start_line=raise_node.lineno,
            end_line=raise_node.end_lineno,
            symbol=function.name,
            node_kind="Raise",
        ),
        params={"attribute": attribute, "value": fallback, "exception": "ValueError"},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=_full_source_edit(source),
        original_source=source,
        patched_source=patched,
        reason=f"default missing {attribute} to {fallback_text} with warning",
    )


def _raises_value_error(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "ValueError"


def _none_checked_self_attribute(node: ast.AST) -> str | None:
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            attribute = _none_checked_self_attribute(value)
            if attribute is not None:
                return attribute
        return None

    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return None
    if not isinstance(node.ops[0], ast.Is):
        return None
    if not isinstance(node.comparators[0], ast.Constant) or node.comparators[0].value is not None:
        return None

    left = node.left
    if not isinstance(left, ast.Attribute):
        return None
    if not isinstance(left.value, ast.Name) or left.value.id != "self":
        return None
    return left.attr


def _has_warnings_import(tree: ast.Module) -> bool:
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            if any(alias.name == "warnings" for alias in statement.names):
                return True
        elif isinstance(statement, ast.ImportFrom) and statement.module == "warnings":
            return True
    return False


def _module_false_flags(tree: ast.Module) -> list[str]:
    flags: list[str] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if not isinstance(statement.value, ast.Constant) or statement.value.value is not False:
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    flags.append(target.id)
        elif isinstance(statement, ast.AnnAssign):
            if (
                isinstance(statement.target, ast.Name)
                and isinstance(statement.value, ast.Constant)
                and statement.value.value is False
            ):
                flags.append(statement.target.id)
    return flags


def _module_list_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if not _is_empty_list_expr(statement.value):
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and _is_empty_list_expr(statement.value):
                names.add(statement.target.id)
    return names


def _is_empty_list_expr(node: ast.AST | None) -> bool:
    if isinstance(node, ast.List) and not node.elts:
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "list" and not node.args


def _module_list_appends(function: ast.FunctionDef, module_lists: set[str]) -> set[str]:
    appended: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr not in {"append", "extend"}:
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id in module_lists:
            appended.add(node.func.value.id)
    return appended


def _last_return_expr(source: str, function: ast.FunctionDef) -> str | None:
    if not function.body:
        return None
    last_statement = function.body[-1]
    if not isinstance(last_statement, ast.Return) or last_statement.value is None:
        return None
    return ast.get_source_segment(source, last_statement.value)


def _guard_insertion_statement(function: ast.FunctionDef) -> ast.stmt | None:
    body = list(function.body)
    if not body:
        return None
    if (
        isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body[0] if body else None


def _function_references_name(function: ast.FunctionDef, name: str) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Global) and name in node.names:
            return True
    return False


def _names_look_related(flag_name: str, list_name: str, function_name: str) -> bool:
    flag_tokens = _name_tokens(flag_name)
    list_tokens = _name_tokens(list_name)
    function_tokens = _name_tokens(function_name)
    return bool(flag_tokens & list_tokens) or bool(flag_tokens & function_tokens)


def _name_tokens(name: str) -> set[str]:
    return {
        token
        for token in name.strip("_").casefold().split("_")
        if token and token not in {"is", "has", "was", "did", "started", "initialized", "registered"}
    }
