import pytest

from tablefmt.legacy import resolve_legacy_symbol


def test_unknown_legacy_symbol_error_closes_attribute_quote() -> None:
    expected_template = "module 'tablefmt.legacy' has no attribute '{name}'"

    with pytest.raises(AttributeError) as exc_info:
        resolve_legacy_symbol("MISSING")

    assert str(exc_info.value) == expected_template.format(name="MISSING")
