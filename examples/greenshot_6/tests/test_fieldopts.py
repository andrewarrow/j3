import pytest

from fieldopts.fields import FieldOptionError, validate_field_options


def test_regex_keyword_error_points_to_pattern_parameter() -> None:
    with pytest.raises(FieldOptionError) as exc_info:
        validate_field_options(regex=r"^ok$")

    assert str(exc_info.value) == "`regex` is removed. use `pattern` instead"
