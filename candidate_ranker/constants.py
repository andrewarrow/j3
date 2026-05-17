"""Shared constants for candidate ranking."""

from __future__ import annotations

import re


RANKER_FORMAT = "j3.candidate-ranker.v1"
RANKER_FEATURE_VERSION = "candidate-diagnostics-v13"
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")

_SYMBOLIC_PARAM_VALUES = {
    "!=",
    "%",
    "*",
    "+",
    "-",
    "/",
    "//",
    "<",
    "<=",
    "==",
    ">",
    ">=",
    "and",
    "in",
    "is",
    "is not",
    "not in",
    "or",
}
