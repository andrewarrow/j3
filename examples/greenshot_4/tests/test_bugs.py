from bugs import (
    Account,
    FeatureFlag,
    Package,
    account_balance,
    apply_discount,
    average_age,
    bonus_points,
    count_statuses,
    display_name,
    display_range,
    error_rate,
    feature_enabled,
    file_extension,
    final_score,
    group_values,
    includes_threshold,
    is_below_limit,
    last_order_id,
    mean_score,
    meets_minimum,
    net_after_fee,
    newest_event,
    parse_count,
    parse_port,
    parse_ratio,
    product_slug,
    retry_limit,
    sale_total,
    shipping_total,
    shipping_weight,
)


def test_discount_returns_remaining_price() -> None:
    assert apply_discount(200, 25) == 150


def test_sale_total_returns_remaining_price() -> None:
    assert sale_total(100, 20) == 80


def test_net_after_fee_subtracts_fee() -> None:
    assert net_after_fee(100, 0.15) == 85


def test_includes_threshold_boundary() -> None:
    assert includes_threshold(10, 10) is True


def test_meets_minimum_boundary() -> None:
    assert meets_minimum(5, 5) is True


def test_below_limit_excludes_boundary() -> None:
    assert is_below_limit(7, 7) is False


def test_shipping_total_uses_expected_fee() -> None:
    assert shipping_total(20) == 25


def test_retry_limit_uses_expected_count() -> None:
    assert retry_limit() == 3


def test_bonus_points_uses_expected_increment() -> None:
    assert bonus_points(2) == 12


def test_last_order_id_returns_tail() -> None:
    assert last_order_id([101, 202, 303]) == 303


def test_newest_event_returns_tail() -> None:
    assert newest_event(["created", "queued", "sent"]) == "sent"


def test_final_score_returns_tail() -> None:
    assert final_score([4, 8, 15]) == 15


def test_mean_score_empty_returns_zero() -> None:
    assert mean_score([]) == 0
    assert mean_score([2, 4]) == 3


def test_average_age_empty_returns_zero() -> None:
    assert average_age([]) == 0
    assert average_age([20, 40]) == 30


def test_error_rate_empty_returns_zero() -> None:
    assert error_rate([]) == 0
    assert error_rate([1, 0, 1, 0]) == 0.5


def test_display_name_keeps_first_then_last() -> None:
    assert display_name("Ada", "Lovelace") == "Ada Lovelace"


def test_product_slug_keeps_category_then_name() -> None:
    assert product_slug("books", "python") == "books/python"


def test_display_range_keeps_start_then_end() -> None:
    assert display_range(3, 9) == "3-9"


def test_file_extension_uses_pathlib() -> None:
    assert file_extension("archive.tar.gz") == ".gz"


def test_count_statuses_uses_counter() -> None:
    assert count_statuses(["ready", "blocked", "ready"]) == 2


def test_group_values_uses_defaultdict() -> None:
    assert group_values([("a", 1), ("a", 2), ("b", 3)]) == {"a": [1, 2], "b": [3]}


def test_account_balance_uses_existing_attribute() -> None:
    assert account_balance(Account(balance_cents=1250)) == 1250


def test_shipping_weight_uses_existing_attribute() -> None:
    assert shipping_weight(Package(weight_grams=250)) == 250


def test_feature_enabled_uses_existing_attribute() -> None:
    assert feature_enabled(FeatureFlag(enabled=True)) is True


def test_parse_count_returns_zero_for_invalid_input() -> None:
    assert parse_count("12") == 12
    assert parse_count("n/a") == 0


def test_parse_ratio_returns_zero_for_invalid_input() -> None:
    assert parse_ratio("0.25") == 0.25
    assert parse_ratio("n/a") == 0


def test_parse_port_returns_zero_for_invalid_input() -> None:
    assert parse_port("443") == 443
    assert parse_port("https") == 0
