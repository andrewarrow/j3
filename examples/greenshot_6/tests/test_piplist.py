import pytest

from piplist.listing import CommandError, validate_list_options


def test_outdated_freeze_format_error_matches_pip_message() -> None:
    with pytest.raises(CommandError) as exc_info:
        validate_list_options(outdated=True, list_format="freeze")

    assert (
        str(exc_info.value)
        == "List format 'freeze' cannot be used together with the --outdated option."
    )

    validate_list_options(outdated=False, list_format="freeze")
    validate_list_options(outdated=True, list_format="columns")
