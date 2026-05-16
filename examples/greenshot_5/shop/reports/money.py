def format_receipt_total(total_cents: int) -> str:
    return f"${total_cents / 100:.2f}"
