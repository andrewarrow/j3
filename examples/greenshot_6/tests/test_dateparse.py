from datetime import timezone

from dateparse.isoparse import accepted_utc_zone_names, parse_timezone_suffix


def test_lowercase_z_is_accepted_as_utc_suffix() -> None:
    assert accepted_utc_zone_names() == "UTC GMT Z z"
    assert parse_timezone_suffix("Z") is timezone.utc
    assert parse_timezone_suffix("z") is timezone.utc
