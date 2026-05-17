def locale_directory_hint() -> str:
    return "the 'locale' directory exist in an app"


def missing_locale_path_error(file_path: str) -> str:
    return (
        "Unable to find a locale path to store translations for file "
        f"{file_path}. Make sure {locale_directory_hint()} or LOCALE_PATHS "
        "setting is set."
    )
