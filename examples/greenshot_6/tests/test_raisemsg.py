from raisemsg import invalid_string_expected_exception_error


def test_expected_exception_type_error_message_uses_clear_sentence() -> None:
    assert (
        invalid_string_expected_exception_error()
        == "Expected a BaseException type, but got 'str'"
    )
