from shop.accounts import Account
from shop.api import (
    balance_after_store_credit,
    express_shipping_label,
    loyalty_points,
    order_customer_label,
    profile_badge,
    profile_heading,
    profile_label,
    quote_total,
    receipt_label,
    return_window_days,
    uploaded_extension,
    visible_balance,
)


def test_quote_total_applies_discount_in_helper() -> None:
    assert quote_total(100, 20) == 80


def test_balance_after_store_credit_passes_arguments_to_helper() -> None:
    assert balance_after_store_credit(1000, 150) == 850


def test_uploaded_extension_uses_pathlib_in_paths_module() -> None:
    assert uploaded_extension("archive.tar.gz") == ".gz"


def test_visible_balance_uses_balance_cents() -> None:
    account = Account(available_cents=900, balance_cents=1250, pending_cents=300)

    assert visible_balance(account) == 1250


def test_profile_label_accepts_username_keyword() -> None:
    assert profile_heading("ada") == "Ada"
    assert profile_label("grace") == "Grace"


def test_profile_badge_propagates_public_api_username() -> None:
    assert profile_badge("Ada") == "@ada"


def test_order_customer_label_uses_customer_name_key() -> None:
    assert order_customer_label({"customer_name": "ada", "status": "paid"}) == "Ada"


def test_return_window_uses_policy_default() -> None:
    assert return_window_days() == 14


def test_express_shipping_boundary_prefers_helper_condition() -> None:
    assert express_shipping_label(5000) == "free"


def test_receipt_label_imports_nested_report_formatter() -> None:
    assert receipt_label(1250) == "$12.50"


def test_loyalty_points_wrapper_handles_pending_value() -> None:
    assert loyalty_points("pending") == 0
