from cliformat.types import invalid_directory_message


def test_invalid_directory_message_escapes_newline_in_filename() -> None:
    expected_template = "{name} {filename!r} is a directory."

    assert invalid_directory_message("path", "my\ndir") == expected_template.format(
        name="Path",
        filename="my\ndir",
    )
