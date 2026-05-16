def discounted_subtotal(subtotal: float, discount_percent: float) -> float:
    return subtotal * (discount_percent / 100)


def total_after_store_credit(total_cents: int, credit_cents: int) -> int:
    return total_cents - credit_cents
