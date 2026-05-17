from envwrite import format_env_value


def test_auto_quote_mode_leaves_alphanumeric_values_unquoted() -> None:
    assert format_env_value("TOKEN123", quote_mode="auto") == "TOKEN123"
    assert format_env_value("needs space", quote_mode="auto") == "'needs space'"
