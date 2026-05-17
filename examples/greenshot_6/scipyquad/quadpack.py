from __future__ import annotations


def _quad(a: float, b: float) -> str:
    if a == float("-inf") or b == float("inf"):
        raise RunTimeError("Infinity comparisons don't work for you.")
    return "finite"
