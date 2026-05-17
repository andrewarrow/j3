from __future__ import annotations

import re


def forbidden_header_chars_pattern() -> str:
    # Modeled on Tornado's forbidden header-character validator.
    return r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"


def is_valid_header_value(value: str) -> bool:
    return re.search(forbidden_header_chars_pattern(), value) is None
