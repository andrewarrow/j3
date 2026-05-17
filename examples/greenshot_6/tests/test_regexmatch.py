from regexmatch import regex_match_failure_message


def test_regex_match_failure_message_names_expected_regex() -> None:
    expected_label = "Expected regex"

    assert regex_match_failure_message("[123]+", "division by zero") == (
        "Regex pattern did not match.\n"
        f"  {expected_label}: '[123]+'\n"
        "  Actual message: 'division by zero'"
    )
