checkout_start_events: list[str] = []
_checkout_hooks_started = False


def start_checkout_hooks() -> list[str]:
    checkout_start_events.append("cart_loaded")
    checkout_start_events.append("payment_ready")
    return checkout_start_events
