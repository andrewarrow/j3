from securityforms import client_secret_docstring, oauth2_password_request_form_docs


def test_oauth2_client_secret_docstring_uses_secret_name() -> None:
    assert client_secret_docstring() == "client_secret"


def test_oauth2_form_docs_include_client_secret_field() -> None:
    docs = oauth2_password_request_form_docs()

    assert docs["client_secret"].startswith("If there's a `client_secret`")
