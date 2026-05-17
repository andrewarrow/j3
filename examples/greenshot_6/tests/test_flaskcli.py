import pytest

from flaskcli import BadParameter, SSLContext, validate_key


def test_ssl_context_key_error_message_quotes_key_option() -> None:
    with pytest.raises(BadParameter) as exc_info:
        validate_key(SSLContext(), "server.key")

    assert str(exc_info.value) == (
        'When "--cert" is an SSLContext object, "--key" is not used.'
    )
