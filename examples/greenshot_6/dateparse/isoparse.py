from __future__ import annotations

from datetime import timezone, tzinfo


UTC_ZONE_NAMES = "UTC GMT Z"


def accepted_utc_zone_names() -> str:
    return UTC_ZONE_NAMES


def parse_timezone_suffix(suffix: str) -> tzinfo:
    if suffix in UTC_ZONE_NAMES.split():
        return timezone.utc
    raise ValueError(f"Unsupported ISO-8601 timezone suffix: {suffix!r}")

