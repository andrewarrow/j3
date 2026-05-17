from headers.validation import forbidden_header_chars_pattern, is_valid_header_value


def test_newline_is_rejected_in_header_value() -> None:
    assert forbidden_header_chars_pattern() == r"[\x00-\x08\x0A-\x1F\x7F]"
    assert is_valid_header_value("safe value") is True
    assert is_valid_header_value("bad\nvalue") is False
