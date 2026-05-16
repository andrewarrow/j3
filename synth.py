"""Synthetic break/fix transition generation for Python repositories."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable

from actions import PatchAction, PatchActionKind, PatchTarget


MAX_EXAMPLES_PER_FILE = 20


@dataclass(frozen=True, slots=True)
class SyntheticTransition:
    """One generated broken source state and the action that repairs it."""

    file_path: str
    clean_source: str
    broken_source: str
    repair_action: PatchAction
    mutation: str

    def to_record(self) -> dict[str, object]:
        return {
            "file_path": self.file_path,
            "mutation": self.mutation,
            "repair_action": self.repair_action.to_record(),
        }


@dataclass(frozen=True, slots=True)
class SourceEdit:
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    replacement: str


def generate_transitions(
    *,
    file_path: str,
    source: str,
    max_examples: int = MAX_EXAMPLES_PER_FILE,
) -> list[SyntheticTransition]:
    """Generate local synthetic repair examples from one passing source file."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    transitions: list[SyntheticTransition] = []
    for node in ast.walk(tree):
        for transition in _transitions_for_node(file_path, source, node):
            transitions.append(transition)
            if len(transitions) >= max_examples:
                return transitions
    return transitions


def _transitions_for_node(
    file_path: str,
    source: str,
    node: ast.AST,
) -> Iterable[SyntheticTransition]:
    if isinstance(node, ast.Compare) and node.ops:
        yield from _comparison_transition(file_path, source, node)
    elif isinstance(node, ast.Constant):
        yield from _literal_transition(file_path, source, node)
    elif isinstance(node, ast.Return) and node.value is not None:
        yield from _return_transition(file_path, source, node)
    elif isinstance(node, ast.If):
        yield from _condition_transition(file_path, source, node)


def _comparison_transition(
    file_path: str,
    source: str,
    node: ast.Compare,
) -> Iterable[SyntheticTransition]:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return

    original = _operator_text(node.ops[0])
    broken = _broken_operator(original)
    if original is None or broken is None:
        return

    left = ast.get_source_segment(source, node.left)
    right = ast.get_source_segment(source, node.comparators[0])
    if not left or not right:
        return

    original_expr = ast.get_source_segment(source, node)
    if not original_expr:
        return

    broken_expr = f"{left} {broken} {right}"
    edit = _node_edit(node, broken_expr)
    broken_source = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.CHANGE_OPERATOR,
        target=_target(file_path, node, "Compare"),
        params={"from": broken, "to": original},
    )
    yield SyntheticTransition(file_path, source, broken_source, action, "comparison_operator")


def _literal_transition(
    file_path: str,
    source: str,
    node: ast.Constant,
) -> Iterable[SyntheticTransition]:
    original = node.value
    if isinstance(original, bool):
        broken_value = not original
        replacement = repr(broken_value)
    elif isinstance(original, int) and not isinstance(original, bool):
        broken_value = original + 1
        replacement = repr(broken_value)
    elif isinstance(original, str) and original:
        broken_value = original[:-1]
        replacement = repr(broken_value)
    else:
        return

    edit = _node_edit(node, replacement)
    broken_source = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.CHANGE_LITERAL,
        target=_target(file_path, node, "Constant"),
        params={"from": broken_value, "to": original},
    )
    yield SyntheticTransition(file_path, source, broken_source, action, "literal_value")


def _return_transition(
    file_path: str,
    source: str,
    node: ast.Return,
) -> Iterable[SyntheticTransition]:
    yield from _return_value_transition(file_path, source, node)
    yield from _replace_expr_transition(file_path, source, node)


def _return_value_transition(
    file_path: str,
    source: str,
    node: ast.Return,
) -> Iterable[SyntheticTransition]:
    if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, bool):
        return
    original = node.value.value
    broken_value = not original
    edit = _node_edit(node.value, repr(broken_value))
    broken_source = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.CHANGE_RETURN_VALUE,
        target=_target(file_path, node, "Return"),
        params={"from": broken_value, "to": original},
    )
    yield SyntheticTransition(file_path, source, broken_source, action, "return_value")


def _replace_expr_transition(
    file_path: str,
    source: str,
    node: ast.Return,
) -> Iterable[SyntheticTransition]:
    if node.value is None:
        return

    replacement = _simpler_expression(source, node.value)
    original = ast.get_source_segment(source, node.value)
    if not replacement or not original or replacement == original:
        return

    edit = _node_edit(node.value, replacement)
    broken_source = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.REPLACE_EXPR,
        target=_target(file_path, node.value, type(node.value).__name__),
        params={"from": replacement, "to": original},
    )
    yield SyntheticTransition(file_path, source, broken_source, action, "replace_expr")


def _condition_transition(
    file_path: str,
    source: str,
    node: ast.If,
) -> Iterable[SyntheticTransition]:
    original_test = ast.get_source_segment(source, node.test)
    if not original_test:
        return

    edit = _node_edit(node.test, f"not ({original_test})")
    broken_source = apply_edit(source, edit)
    action = PatchAction(
        kind=PatchActionKind.MODIFY_CONDITION,
        target=_target(file_path, node.test, type(node.test).__name__),
        params={"operation": "remove_not"},
    )
    yield SyntheticTransition(file_path, source, broken_source, action, "condition_negation")


def _simpler_expression(source: str, node: ast.AST) -> str | None:
    if isinstance(node, ast.BinOp):
        left = ast.get_source_segment(source, node.left)
        right = ast.get_source_segment(source, node.right)
        return left or right
    if isinstance(node, ast.BoolOp) and node.values:
        return ast.get_source_segment(source, node.values[0])
    if isinstance(node, ast.IfExp):
        return ast.get_source_segment(source, node.body)
    if isinstance(node, ast.Call):
        return "None"
    if isinstance(node, ast.Compare):
        return "False"
    return None


def apply_edit(source: str, edit: SourceEdit) -> str:
    lines = source.splitlines(keepends=True)
    start = _offset(lines, edit.start_line, edit.start_col)
    end = _offset(lines, edit.end_line, edit.end_col)
    return source[:start] + edit.replacement + source[end:]


def _node_edit(node: ast.AST, replacement: str) -> SourceEdit:
    if (
        not hasattr(node, "lineno")
        or not hasattr(node, "col_offset")
        or not hasattr(node, "end_lineno")
        or not hasattr(node, "end_col_offset")
    ):
        raise ValueError("node does not have source location metadata")
    return SourceEdit(
        start_line=node.lineno,
        start_col=node.col_offset,
        end_line=node.end_lineno,
        end_col=node.end_col_offset,
        replacement=replacement,
    )


def _target(file_path: str, node: ast.AST, node_kind: str) -> PatchTarget:
    return PatchTarget(
        file_path=file_path,
        start_line=node.lineno,
        end_line=node.end_lineno,
        node_kind=node_kind,
    )


def _offset(lines: list[str], line: int, col: int) -> int:
    return sum(len(value) for value in lines[: line - 1]) + col


def _operator_text(op: ast.cmpop) -> str | None:
    table = {
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Is: "is",
        ast.IsNot: "is not",
        ast.In: "in",
        ast.NotIn: "not in",
    }
    return table.get(type(op))


def _broken_operator(operator: str | None) -> str | None:
    table = {
        "==": "!=",
        "!=": "==",
        "<": "<=",
        "<=": "<",
        ">": ">=",
        ">=": ">",
        "is": "is not",
        "is not": "is",
        "in": "not in",
        "not in": "in",
    }
    if operator is None:
        return None
    return table.get(operator)
