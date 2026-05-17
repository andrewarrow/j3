from __future__ import annotations


def client_secret_docstring() -> str:
    return "client_password"


def oauth2_password_request_form_docs() -> dict[str, str]:
    return {
        "client_id": "Optional OAuth2 client identifier.",
        "client_secret": (
            f"If there's a `{client_secret_docstring()}` (and a `client_id`), "
            "they can be sent as part of the form fields."
        ),
    }
