class CommandError(ValueError):
    pass


def validate_list_options(*, outdated: bool, list_format: str) -> None:
    if outdated and list_format == "freeze":
        raise CommandError(
            "List format 'freeze' can not be used with the --outdated option."
        )

