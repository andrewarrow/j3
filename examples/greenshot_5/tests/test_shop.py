from shop.accounts import Account
from shop.api import profile_heading, profile_label, quote_total, uploaded_extension, visible_balance


def test_quote_total_applies_discount_in_helper() -> None:
    assert quote_total(100, 20) == 80


def test_uploaded_extension_uses_pathlib_in_paths_module() -> None:
    assert uploaded_extension("archive.tar.gz") == ".gz"


def test_visible_balance_uses_balance_cents() -> None:
    account = Account(available_cents=900, balance_cents=1250, pending_cents=300)

    assert visible_balance(account) == 1250


def test_profile_label_accepts_username_keyword() -> None:
    assert profile_heading("ada") == "Ada"
    assert profile_label("grace") == "Grace"

