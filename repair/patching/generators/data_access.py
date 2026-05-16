"""Attribute and subscript candidate generation."""

from __future__ import annotations

import ast

from actions import PatchAction, PatchActionKind, PatchTarget
from synth import apply_edit

from ..ast_utils import _node_edit, _subscript_key_alternatives
from ..types import CandidatePatch
from .common import _candidate


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
