from .accounts import Account, account_balance
from .orders import customer_display_name
from .paths import attachment_extension
from .policies import default_return_window_days
from .pricing import discounted_subtotal
from .profiles import display_profile, render_profile
from .reports.summary import receipt_total_label


def quote_total(subtotal: float, discount_percent: float) -> float:
    return discounted_subtotal(subtotal, discount_percent)


def uploaded_extension(filename: str) -> str:
    return attachment_extension(filename)


def visible_balance(account: Account) -> int:
    return account_balance(account)


def profile_heading(username: str) -> str:
    return display_profile(username)


def profile_label(username: str) -> str:
    return render_profile(username=username)


def order_customer_label(order: dict[str, str]) -> str:
    return customer_display_name(order)


def return_window_days() -> int:
    return default_return_window_days()


def receipt_label(total_cents: int) -> str:
    return receipt_total_label(total_cents)
