"""Attribute and subscript candidate generation."""

from __future__ import annotations

import ast

from actions import PatchAction, PatchActionKind, PatchTarget
from synth import apply_edit

from ..ast_utils import (
    _key_similarity,
    _keys_look_related,
    _node_edit,
    _subscript_key_alternatives,
)
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


def _add_dict_key_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Dict,
    repo_string_literals: set[str],
) -> list[CandidatePatch]:
    existing_keys = _dict_string_keys(node)
    if not existing_keys:
        return []

    alternatives = _dict_key_alternatives(existing_keys, repo_string_literals)
    candidates: list[CandidatePatch] = []
    for key in alternatives:
        value = _default_value_for_key(key)
        replacement = _render_dict_with_added_key(source, node, key, value)
        if replacement is None:
            continue
        edit = _node_edit(node, replacement)
        patched = apply_edit(source, edit)
        action = PatchAction(
            kind=PatchActionKind.ADD_DICT_KEY,
            target=PatchTarget(
                file_path=file_path,
                start_line=node.lineno,
                end_line=node.end_lineno,
                symbol=function.name,
                node_kind="Dict",
            ),
            params={"key": key, "value": value},
        )
        candidates.append(
            CandidatePatch(
                file_path=file_path,
                action=action,
                edit=edit,
                original_source=source,
                patched_source=patched,
                reason=f"add dictionary key {key!r}",
            )
        )
    return candidates


def _dict_string_keys(node: ast.Dict) -> set[str]:
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def _dict_key_alternatives(existing_keys: set[str], repo_string_literals: set[str]) -> list[str]:
    alternatives = [
        value
        for value in repo_string_literals
        if value not in existing_keys
        and any(_keys_look_related(existing, value) for existing in existing_keys)
    ]
    return sorted(
        alternatives,
        key=lambda value: (
            -max(_key_similarity(existing, value) for existing in existing_keys),
            value,
        ),
    )[:5]


def _default_value_for_key(key: str) -> bool | int | None:
    normalized = key.casefold()
    if "disabled" in normalized:
        return False
    if "enabled" in normalized:
        return True
    if normalized.startswith(("is_", "has_", "can_", "should_")):
        return False
    if normalized.endswith(("_count", "_cents", "_total")):
        return 0
    return None


def _render_dict_with_added_key(
    source: str,
    node: ast.Dict,
    key: str,
    value: bool | int | None,
) -> str | None:
    segment = ast.get_source_segment(source, node)
    if not segment or not segment.rstrip().endswith("}"):
        return None

    rendered_entry = f"{_render_dict_key(source, node, key)}: {value!r}"
    if "\n" not in segment:
        prefix = segment.rstrip()[:-1].rstrip()
        separator = "" if prefix.endswith("{") else ", "
        return f"{prefix}{separator}{rendered_entry}}}"

    lines = segment.splitlines()
    closing = lines[-1]
    entry_indent = _dict_entry_indent(lines)
    body = _ensure_previous_dict_entry_comma(lines[:-1])
    comma = "," if _dict_body_has_entries(lines) else ""
    return "\n".join([*body, f"{entry_indent}{rendered_entry}{comma}", closing])


def _dict_entry_indent(lines: list[str]) -> str:
    for line in lines[1:-1]:
        if line.strip():
            return line[: len(line) - len(line.lstrip())]
    closing_indent = lines[-1][: len(lines[-1]) - len(lines[-1].lstrip())]
    return f"{closing_indent}    "


def _dict_body_has_entries(lines: list[str]) -> bool:
    return any(line.strip() for line in lines[1:-1])


def _render_dict_key(source: str, node: ast.Dict, key: str) -> str:
    for existing in node.keys:
        if not isinstance(existing, ast.Constant) or not isinstance(existing.value, str):
            continue
        segment = ast.get_source_segment(source, existing)
        if segment and segment.startswith('"'):
            return '"' + key.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if segment and segment.startswith("'"):
            return repr(key)
    return repr(key)


def _ensure_previous_dict_entry_comma(lines: list[str]) -> list[str]:
    updated = list(lines)
    for index in range(len(updated) - 1, 0, -1):
        stripped = updated[index].strip()
        if not stripped:
            continue
        if not stripped.endswith((",", "{")):
            updated[index] = f"{updated[index]},"
        break
    return updated
