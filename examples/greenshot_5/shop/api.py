from .accounts import Account, account_balance
from .orders import customer_display_name
from .paths import attachment_extension
from .policies import default_return_window_days, express_shipping_eligible
from .pricing import discounted_subtotal, total_after_store_credit
from .profiles import display_profile, render_profile, user_badge_label
from .reports.summary import receipt_total_label
from .rewards import parse_loyalty_points
from .shipping import shipping_service_label, shipping_timeout_label
from .widgets import checkout_widget_payload


def quote_total(subtotal: float, discount_percent: float) -> float:
    return discounted_subtotal(subtotal, discount_percent)


def balance_after_store_credit(total_cents: int, credit_cents: int) -> int:
    return total_after_store_credit(credit_cents, total_cents)


def uploaded_extension(filename: str) -> str:
    return attachment_extension(filename)


def visible_balance(account: Account) -> int:
    return account_balance(account)


def profile_heading(username: str) -> str:
    return display_profile(username)


def profile_label(username: str) -> str:
    return render_profile(username=username)


def profile_badge(username: str) -> str:
    return user_badge_label(username=username)


def order_customer_label(order: dict[str, str]) -> str:
    return customer_display_name(order)


def return_window_days() -> int:
    return default_return_window_days()


def express_shipping_label(subtotal_cents: int, minimum_cents: int = 5000) -> str:
    return "free" if express_shipping_eligible(subtotal_cents, minimum_cents) else "paid"


def receipt_label(total_cents: int) -> str:
    return receipt_total_label(total_cents)


def loyalty_points(raw_points: str) -> int:
    return parse_loyalty_points(raw_points)


def priority_shipping_service() -> str:
    return shipping_service_label("priorty")


def delivery_summary_service() -> str:
    return delivery_speed_label("expres")


def checkout_widget(label: str) -> dict[str, object]:
    return checkout_widget_payload(label)


def carrier_timeout_label(timeout_seconds: int = 30) -> str:
    return shipping_timeout_label()
