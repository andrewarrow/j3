from i18nmsgs import locale_directory_hint, missing_locale_path_error


def test_missing_locale_path_message_uses_plural_verb() -> None:
    assert locale_directory_hint() == "the 'locale' directory exists in an app"
    assert missing_locale_path_error("__init__.py") == (
        "Unable to find a locale path to store translations for file "
        "__init__.py. Make sure the 'locale' directory exists in an app "
        "or LOCALE_PATHS setting is set."
    )
