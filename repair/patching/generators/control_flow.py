"""Control-flow candidate generation."""

from __future__ import annotations

import ast

from actions import PatchAction, PatchActionKind, PatchTarget
from synth import SourceEdit, apply_edit

from ..ast_utils import _call_exception, _function_uses_len_of
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
