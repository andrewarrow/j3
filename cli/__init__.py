"""Public CLI API."""

from __future__ import annotations

from cli.handlers import (
    handle_actions,
    handle_build_prompt_jepa_index,
    handle_change,
    handle_compare_diagnostics,
    handle_eval,
    handle_fix,
    handle_greenshot_7,
    handle_implement,
    handle_mine,
    handle_patch,
    handle_query_prompt_jepa_index,
    handle_train,
    handle_train_prompt_intents,
    handle_train_ranker,
)
from cli.main import main
from cli.parser import build_parser

__all__ = [
    "build_parser",
    "handle_actions",
    "handle_build_prompt_jepa_index",
    "handle_change",
    "handle_compare_diagnostics",
    "handle_eval",
    "handle_fix",
    "handle_greenshot_7",
    "handle_implement",
    "handle_mine",
    "handle_patch",
    "handle_query_prompt_jepa_index",
    "handle_train",
    "handle_train_prompt_intents",
    "handle_train_ranker",
    "main",
]
