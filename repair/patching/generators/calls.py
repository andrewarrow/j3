"""Call-expression candidate generation."""

from __future__ import annotations

import ast

from actions import PatchActionKind

from ..types import CandidatePatch
from .common import _candidate


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
