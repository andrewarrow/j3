import pytest

from shop.accounts import Account
from shop.api import (
    balance_after_store_credit,
    cache_status_label,
    checkout_step,
    carrier_timeout_label,
    checkout_widget,
    checkout_startup_events,
    delivery_summary_service,
    express_shipping_label,
    free_shipping_threshold,
    loyalty_points,
    order_customer_label,
    profile_badge,
    profile_heading,
    profile_label,
    priority_shipping_service,
    quote_total,
    receipt_label,
    return_window_days,
    training_data_config,
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


def test_free_shipping_threshold_uses_module_constant() -> None:
    assert free_shipping_threshold() == 5000


def test_receipt_label_imports_nested_report_formatter() -> None:
    assert receipt_label(1250) == "$12.50"


def test_loyalty_points_wrapper_handles_pending_value() -> None:
    assert loyalty_points("pending") == 0


def test_priority_shipping_mode_literal_is_fixed_in_caller() -> None:
    assert priority_shipping_service() == "air"


def test_multi_step_delivery_summary_reveals_literal_after_import() -> None:
    assert delivery_summary_service() == "air"


def test_checkout_widget_payload_includes_disabled_key() -> None:
    payload = checkout_widget("Pay now")

    assert payload["label"] == "Pay now"
    assert payload["disabled"] is False


def test_checkout_step_metadata_uses_metadata_icon_key() -> None:
    metadata = checkout_step("card")

    assert metadata["metadata_icon"] == "card"


def test_carrier_timeout_label_passes_timeout_keyword() -> None:
    assert carrier_timeout_label(timeout_seconds=30) == "extended"


def test_training_data_file_defaults_validation_fraction_with_warning(tmp_path) -> None:
    data_file = tmp_path / "train.json"
    data_file.write_text("[]", encoding="utf-8")

    with pytest.warns(UserWarning, match="Defaulting to `validation_fraction=0.05`"):
        config = training_data_config(data_file)

    assert config.validation_fraction == 0.05


def test_checkout_startup_hooks_are_idempotent() -> None:
    assert checkout_startup_events() == ["cart_loaded", "payment_ready"]


def test_cache_backend_import_falls_back_to_legacy_path() -> None:
    assert cache_status_label() == "sqlite:ready"
