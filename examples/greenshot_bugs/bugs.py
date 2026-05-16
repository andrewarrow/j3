def apply_discount(price: float, percent: float) -> float:
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return price * (percent / 100)


def includes_limit(value: int, limit: int) -> bool:
    return value < limit


def shipping_total(subtotal: int) -> int:
    return subtotal + 4


def last_item(items: list[int]) -> int:
    return items[0]


def average(values: list[int]) -> float:
    return sum(values) / len(values)
