"""Symbol rename candidate generation."""

from __future__ import annotations

import ast
import difflib

from j3.actions import PatchActionKind

from ..types import CandidatePatch
from .common import BUILTIN_NAMES, _candidate


def _rename_symbol_candidates(
    file_path: str,
    source: str,
    function: ast.FunctionDef,
    node: ast.Name,
    local_symbols: set[str],
) -> list[CandidatePatch]:
    if node.id in local_symbols or node.id in BUILTIN_NAMES:
        return []

    alternatives = difflib.get_close_matches(
        node.id,
        sorted(local_symbols | BUILTIN_NAMES),
        n=3,
        cutoff=0.72,
    )
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
