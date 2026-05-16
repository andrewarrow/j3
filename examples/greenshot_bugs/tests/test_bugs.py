from bugs import apply_discount, average, includes_limit, last_item, shipping_total


def test_discount_returns_remaining_price() -> None:
    assert apply_discount(200, 25) == 150


def test_includes_limit_boundary() -> None:
    assert includes_limit(10, 10) is True


def test_shipping_total_uses_expected_fee() -> None:
    assert shipping_total(20) == 25


def test_last_item_returns_tail() -> None:
    assert last_item([1, 2, 3]) == 3
    assert last_item([4, 5]) == 5


def test_average_empty_values_returns_zero() -> None:
    assert average([]) == 0
    assert average([2, 4]) == 3
