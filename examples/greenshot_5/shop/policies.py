def default_return_window_days(days: int = 13) -> int:
    return days


def express_shipping_eligible(subtotal_cents: int, minimum_cents: int) -> bool:
    return subtotal_cents > minimum_cents
