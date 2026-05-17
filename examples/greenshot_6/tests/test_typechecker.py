from typechecker import overload_implementation_compatibility_note


def test_overload_docs_do_not_repeat_also() -> None:
    assert overload_implementation_compatibility_note() == (
        "The variants must also be compatible with the implementation"
    )
