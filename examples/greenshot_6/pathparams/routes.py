from __future__ import annotations

import re


def path_param_pattern() -> str:
    return r":([A-Za-z_][A-Za-z0-9_]*)"


_PATH_PARAM_REGEX = re.compile(path_param_pattern())


def find_path_params(path: str) -> list[str]:
    return [match.group(1) for match in _PATH_PARAM_REGEX.finditer(path)]
