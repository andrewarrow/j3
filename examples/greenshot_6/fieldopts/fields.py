class FieldOptionError(ValueError):
    pass


def validate_field_options(**options: object) -> dict[str, object]:
    if "regex" in options:
        raise FieldOptionError("`regex` is removed. use `Pattern` instead")
    return options
