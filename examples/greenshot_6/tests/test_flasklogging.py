from flasklogging import create_logger_description


def test_create_logger_description_uses_singular_possessive_app() -> None:
    assert create_logger_description() == (
        "Get the Flask app's logger and configure it if needed."
    )
