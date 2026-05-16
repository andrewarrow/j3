from calculator import apply_discount


def test_apply_discount_returns_discounted_price() -> None:
    assert apply_discount(200, 25) == 150


def test_apply_discount_rejects_invalid_percent() -> None:
    try:
        apply_discount(100, 101)
    except ValueError:
        return

    raise AssertionError("expected ValueError")
