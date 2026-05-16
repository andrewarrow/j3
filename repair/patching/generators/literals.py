"""Literal and operator candidate generation."""

from __future__ import annotations

import ast

from actions import PatchActionKind

from ..ast_utils import (
    _nearby_literals,
    _operator_alternatives,
    _operator_text,
    _string_literal_alternatives,
)
from ..types import CandidatePatch
from .common import _candidate


def _literal_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Constant,
    repo_string_literals: set[str],
) -> list[CandidatePatch]:
    if isinstance(node.value, bool):
        return []

    candidates: list[CandidatePatch] = []
    if isinstance(node.value, int | float):
        replacements: list[object] = list(_nearby_literals(node.value))
    elif isinstance(node.value, str):
        replacements = list(_string_literal_alternatives(node.value, repo_string_literals))
    else:
        return []

    for replacement in replacements:
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


def _module_constant_candidates(
    file_path: str,
    source: str,
    tree: ast.Module,
    repo_string_literals: set[str],
) -> list[CandidatePatch]:
    candidates: list[CandidatePatch] = []
    for statement in tree.body:
        constant = _module_constant_assignment(statement)
        if constant is None:
            continue
        name, value = constant
        replacements = _module_constant_replacements(value, repo_string_literals)
        for replacement in replacements:
            candidates.append(
                _candidate(
                    file_path=file_path,
                    source=source,
                    node=value,
                    kind=PatchActionKind.CHANGE_MODULE_CONSTANT,
                    replacement=repr(replacement),
                    reason=f"try module constant {name}={replacement!r}",
                    params={"name": name, "from": value.value, "to": replacement},
                    symbol=name,
                )
            )
    return candidates


def _module_constant_assignment(statement: ast.stmt) -> tuple[str, ast.Constant] | None:
    target: ast.expr | None
    value: ast.expr | None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        value = statement.value
    elif isinstance(statement, ast.AnnAssign):
        target = statement.target
        value = statement.value
    else:
        return None

    if (
        not isinstance(target, ast.Name)
        or not _looks_like_config_constant(target.id)
        or not isinstance(value, ast.Constant)
    ):
        return None
    return target.id, value


def _looks_like_config_constant(name: str) -> bool:
    return name.isupper() and not name.startswith("__")


def _module_constant_replacements(
    node: ast.Constant,
    repo_string_literals: set[str],
) -> list[object]:
    value = node.value
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return list(_nearby_literals(value))
    if isinstance(value, str):
        return list(_string_literal_alternatives(value, repo_string_literals))
    return []


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
