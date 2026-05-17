"""Literal and operator candidate generation."""

from __future__ import annotations

import ast
import difflib

from actions import PatchAction, PatchActionKind, PatchTarget
from synth import SourceEdit, apply_edit

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


def _fstring_fragment_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.JoinedStr,
    repo_string_literals: set[str],
) -> list[CandidatePatch]:
    candidates: list[CandidatePatch] = []
    values = list(node.values)
    for index, value_node in enumerate(values):
        if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
            continue
        if value_node.lineno != value_node.end_lineno:
            continue
        original = value_node.value
        for concrete in sorted(repo_string_literals):
            replacement = _concrete_fstring_fragment_replacement(values, index, concrete)
            if replacement is None:
                continue
            candidate = _fstring_fragment_candidate(
                file_path=file_path,
                source=source,
                function=function,
                node=value_node,
                original=original,
                replacement=replacement,
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _concrete_fstring_fragment_replacement(
    values: list[ast.expr],
    index: int,
    concrete: str,
) -> str | None:
    original_node = values[index]
    if not isinstance(original_node, ast.Constant) or not isinstance(original_node.value, str):
        return None
    original = original_node.value
    if not original:
        return None

    prefix_ends = _fstring_prefix_end_positions(values[:index], concrete)
    replacements = [
        concrete[prefix_end:]
        for prefix_end in prefix_ends
        if prefix_end <= len(concrete)
    ]
    replacements = [
        replacement
        for replacement in replacements
        if replacement != original and _fstring_fragments_look_related(original, replacement)
    ]
    if not replacements:
        return None
    return max(replacements, key=lambda value: (difflib.SequenceMatcher(None, original, value).ratio(), len(value)))


def _fstring_prefix_end_positions(values: list[ast.expr], concrete: str) -> set[int]:
    positions: set[int] = {0}
    for value in values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            positions = {
                position + len(value.value)
                for position in positions
                if concrete.startswith(value.value, position)
            }
        elif isinstance(value, ast.FormattedValue):
            positions = {
                end
                for position in positions
                for end in range(position, len(concrete) + 1)
            }
        else:
            positions = set()
        if not positions:
            return set()
    return positions


def _fstring_fragments_look_related(original: str, replacement: str) -> bool:
    if not replacement:
        return False
    if original[0] != replacement[0]:
        return False
    ratio = difflib.SequenceMatcher(None, original, replacement).ratio()
    return ratio >= 0.70 and len(replacement) >= len(original)


def _fstring_fragment_candidate(
    *,
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Constant,
    original: str,
    replacement: str,
) -> CandidatePatch | None:
    edit_offset = _shared_fstring_fragment_prefix_offset(original, replacement)
    param_from = original[edit_offset:]
    param_to = replacement[edit_offset:]
    if not param_from or param_from == param_to:
        return None
    lines = source.splitlines()
    if node.lineno < 1 or node.lineno > len(lines):
        return None
    line = lines[node.lineno - 1]
    start_col = line.find(param_from, node.col_offset)
    if start_col < 0:
        start_col = line.find(param_from)
    if start_col < 0:
        return None
    edit = SourceEdit(
        start_line=node.lineno,
        start_col=start_col,
        end_line=node.end_lineno,
        end_col=start_col + len(param_from),
        replacement=param_to,
    )
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.CHANGE_LITERAL,
        target=PatchTarget(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            symbol=function.name,
            node_kind=type(node).__name__,
        ),
        params={"from": param_from, "to": param_to},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=f"repair f-string fragment {param_from!r}",
    )


def _shared_fstring_fragment_prefix_offset(original: str, replacement: str) -> int:
    if original[:1] == replacement[:1] and original[:1] in {'"', "'"}:
        return 1
    return 0


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
