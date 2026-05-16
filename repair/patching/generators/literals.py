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
