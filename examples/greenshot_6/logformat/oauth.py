def oauth_state_log_template() -> str:
    return "Unable to validate oauth state: %1"


def format_oauth_state_error(error: object) -> str:
    return oauth_state_log_template() % error
