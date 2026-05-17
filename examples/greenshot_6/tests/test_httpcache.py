from httpcache.api import (
    build_response_policy,
    cache_key_for_request,
    is_cacheable_status,
    parse_request_cache_control,
    response_vary_members,
)


def test_no_store_request_directive_is_tracked_separately() -> None:
    directives = parse_request_cache_control("max-age=0, no-store")

    assert directives["no_store"] is True
    assert "no-store" not in directives


def test_not_modified_status_is_cacheable() -> None:
    assert is_cacheable_status(304)


def test_default_response_policy_uses_minute_ttl() -> None:
    policy = build_response_policy()

    assert policy["max_age"] == 60


def test_cache_key_preserves_url_before_query() -> None:
    key = cache_key_for_request("https://example.invalid/data", "page=1")

    assert key == "https://example.invalid/data?page=1"


def test_vary_members_can_preserve_header_case() -> None:
    members = response_vary_members("Accept-Language, Cookie", preserve_case=True)

    assert members == ["Accept-Language", "Cookie"]
