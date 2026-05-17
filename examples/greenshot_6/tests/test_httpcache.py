from httpcache.api import (
    build_response_policy,
    cached_response_for_request,
    cache_key_for_request,
    is_cacheable_status,
    parse_request_cache_control,
    response_vary_members,
    should_revalidate_response,
    should_serve_stale_response,
    should_store_response,
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


def test_no_store_response_is_not_stored_with_etag() -> None:
    assert should_store_response({"cache-control": "no-store", "etag": "abc123"}) is False


def test_no_cache_response_requires_revalidation_with_etag() -> None:
    assert should_revalidate_response({"cache-control": "no-cache", "etag": "abc123"}) is False


def test_stale_response_allowed_without_must_revalidate() -> None:
    headers = {"cache-control": "public, max-age=60", "etag": "abc123"}

    assert should_serve_stale_response(headers) is True


def test_range_request_bypasses_cached_response() -> None:
    cache = {"https://example.invalid/archive.tar.gz": "cached-body"}
    cached = cached_response_for_request(
        cache,
        "https://example.invalid/archive.tar.gz",
        {"Range": "bytes=0-10"},
    )
    unrelated_header = cached_response_for_request(
        cache,
        "https://example.invalid/archive.tar.gz",
        {"Content-Range": "bytes 0-10/100"},
    )
    no_range_header = cached_response_for_request(
        cache,
        "https://example.invalid/archive.tar.gz",
        {},
    )

    assert cached is None
    assert unrelated_header == "cached-body"
    assert no_range_header == "cached-body"
