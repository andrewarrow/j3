import pytest

from scipyquad import _quad


def test_quad_infinite_bounds_raise_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="Infinity comparisons"):
        _quad(0.0, float("inf"))
