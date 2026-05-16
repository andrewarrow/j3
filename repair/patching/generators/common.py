"""Shared helpers for candidate generation."""

from __future__ import annotations

import ast
import builtins

from actions import PatchAction, PatchActionKind, PatchTarget
from synth import apply_edit

from ..ast_utils import _node_edit
from ..types import CandidatePatch


BUILTIN_NAMES = set(dir(builtins))


def _candidate(
    *,
    file_path: str,
    source: str,
    node: ast.AST,
    kind: PatchActionKind,
    replacement: str,
    reason: str,
    params: dict[str, object] | None = None,
    symbol: str | None = None,
) -> CandidatePatch:
    edit = _node_edit(node, replacement)
    patched = apply_edit(source, edit)
    action = PatchAction(
        kind=kind,
        target=PatchTarget(
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            symbol=symbol,
            node_kind=type(node).__name__,
        ),
        params=params or {"replacement": replacement},
    )
    return CandidatePatch(
        file_path=file_path,
        action=action,
        edit=edit,
        original_source=source,
        patched_source=patched,
        reason=reason,
    )
