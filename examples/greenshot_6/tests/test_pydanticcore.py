from pydanticcore import pydantic_use_default_docstring


def test_use_default_docstring_separates_see_the() -> None:
    assert pydantic_use_default_docstring() == (
        "For an additional example, see the partial JSON parsing section."
    )
