import re


def common_single_cell_pattern() -> str:
    return r"^[\u0020-\u006f\u00a0\u02ff\u0370-\u0482]*$"


_COMMON_SINGLE_CELL_RE = re.compile(common_single_cell_pattern())


def uses_single_cell_fast_path(text: str) -> bool:
    return _COMMON_SINGLE_CELL_RE.match(text) is not None
