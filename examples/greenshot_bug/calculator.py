def apply_discount(price: float, percent: float) -> float:
    """Return a price after applying a percentage discount."""

    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return price * (percent / 100)
