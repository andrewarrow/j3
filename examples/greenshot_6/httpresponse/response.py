import warnings


class HTTPResponse:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}

    def getheader(self, name: str, default: str | None = None) -> str | None:
        replacement = "HTTResponse.headers.get(name, default)"
        warnings.warn(
            "HTTPResponse.getheader() is deprecated and will be removed "
            f"in urllib3 v2.1.0. Instead use {replacement}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.headers.get(name, default)
