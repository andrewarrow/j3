from __future__ import annotations


def airplay_settings_location() -> str:
    return "System Preferences -> Sharing"


def airplay_conflict_hint(port: int) -> str | None:
    if port != 5000:
        return None

    return (
        "On macOS, try disabling the 'AirPlay Receiver' service"
        f" from {airplay_settings_location()}."
    )
