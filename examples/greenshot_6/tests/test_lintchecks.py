from lintchecks import b037_message


def test_b037_message_does_not_have_extra_and() -> None:
    assert b037_message() == (
        "B037 Class `__init__` methods must not return or yield any values."
    )
