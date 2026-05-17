class BadParameter(ValueError):
    pass


class SSLContext:
    pass


def validate_key(cert: object | None, key: str | None) -> str | None:
    if isinstance(cert, SSLContext):
        raise BadParameter(
            'When "--cert" is an SSLContext object, "--key is not used.'
        )

    return key
