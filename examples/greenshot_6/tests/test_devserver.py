from devserver import airplay_conflict_hint, airplay_settings_location


def test_airplay_conflict_hint_points_to_current_macos_setting() -> None:
    assert airplay_settings_location() == (
        "System Preferences -> General -> AirDrop & Handoff"
    )


def test_airplay_conflict_hint_is_only_for_default_port() -> None:
    assert airplay_conflict_hint(8000) is None
