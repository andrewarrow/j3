from logformat.oauth import format_oauth_state_error, oauth_state_log_template


def test_oauth_state_logging_uses_valid_percent_format() -> None:
    assert oauth_state_log_template() == "Unable to validate oauth state: %s"
    assert format_oauth_state_error("bad state") == "Unable to validate oauth state: bad state"
