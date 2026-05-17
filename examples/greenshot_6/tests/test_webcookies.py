from webcookies.api import (
    cookie_prefix,
    cookie_scope_key,
    default_cookie_attributes,
    default_partitioned_cookie_attributes,
    is_expired_cookie,
    legacy_cookie_prefix,
    render_cookie_pair,
)


def test_default_secure_attribute_can_be_disabled() -> None:
    attributes = default_cookie_attributes()

    assert attributes["secure"] is False


def test_partitioned_cookie_attribute_is_enabled_by_default() -> None:
    attributes = default_partitioned_cookie_attributes()

    assert attributes["partitioned"] is True


def test_host_cookie_prefix_has_trailing_dash() -> None:
    assert cookie_prefix("host") == "__Host-"


def test_legacy_secure_cookie_prefix_has_no_trailing_dash() -> None:
    assert legacy_cookie_prefix("secure") == "__Secure"


def test_zero_max_age_cookie_is_expired() -> None:
    assert is_expired_cookie(0)


def test_render_cookie_pair_preserves_name_before_value() -> None:
    assert render_cookie_pair("session", "abc123") == "session=abc123"


def test_cookie_scope_key_includes_path_when_requested() -> None:
    assert cookie_scope_key("example.invalid", "/account") == "example.invalid/account"
