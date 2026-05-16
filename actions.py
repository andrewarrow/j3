"""Structured patch actions for j3.

The first j3 models should not emit free-form source text. They should choose a
typed action, a target, and small parameters that a deterministic patch engine
can later turn into a diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Mapping


PatchValue = str | int | float | bool | None


class PatchActionKind(str, Enum):
    """Supported structured edit types for the first repair model."""

    REPLACE_EXPR = "replace_expr"
    INSERT_GUARD = "insert_guard"
    CHANGE_LITERAL = "change_literal"
    CHANGE_OPERATOR = "change_operator"
    CHANGE_SUBSCRIPT_KEY = "change_subscript_key"
    ADD_DICT_KEY = "add_dict_key"
    SWAP_CALL_ARG = "swap_call_arg"
    ADD_KEYWORD_ARG = "add_keyword_arg"
    ADD_IMPORT = "add_import"
    CHANGE_ATTRIBUTE = "change_attribute"
    WRAP_TRY_EXCEPT = "wrap_try_except"
    CHANGE_RETURN_VALUE = "change_return_value"
    RENAME_SYMBOL = "rename_symbol"
    MODIFY_CONDITION = "modify_condition"
    PROPAGATE_SIGNATURE = "propagate_signature"


@dataclass(frozen=True, slots=True)
class PatchTarget:
    """A stable location for an edit inside one source file."""

    file_path: str
    start_line: int
    end_line: int
    symbol: str | None = None
    node_kind: str | None = None

    def __post_init__(self) -> None:
        if PurePosixPath(self.file_path).is_absolute():
            raise ValueError("file_path must be relative to the repository root")
        if self.start_line < 1:
            raise ValueError("start_line must be >= 1")
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")


@dataclass(frozen=True, slots=True)
class PatchAction:
    """A model-selected edit before it is materialized as a diff."""

    kind: PatchActionKind
    target: PatchTarget
    params: Mapping[str, PatchValue] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        """Return a JSON-serializable record for training logs and datasets."""

        return {
            "kind": self.kind.value,
            "target": {
                "file_path": self.target.file_path,
                "start_line": self.target.start_line,
                "end_line": self.target.end_line,
                "symbol": self.target.symbol,
                "node_kind": self.target.node_kind,
            },
            "params": dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class PatchAttempt:
    """One proposed action plus the model score that produced it."""

    action: PatchAction
    score: float
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
