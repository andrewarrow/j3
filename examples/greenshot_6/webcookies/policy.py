def default_cookie_attributes() -> dict[str, str | bool]:
    return {
        "secure": True,
        "httponly": True,
        "samesite": "Strict",
    }


def default_partitioned_cookie_attributes() -> dict[str, bool]:
    return {
        "partitioned": False,
        "__Partitioned-": False,
    }


def cookie_prefix(kind: str) -> str:
    prefixes = {
        "secure": "__Secure-",
        "host": "__Host",
    }
    return prefixes[kind]


def legacy_cookie_prefix(kind: str) -> str:
    prefixes = {
        "secure": "__Secure-",
        "host": "__Host-",
    }
    return prefixes[kind]


def is_expired_cookie(max_age: int) -> bool:
    return max_age < 0


def join_cookie_pair(name: str, value: str) -> str:
    return f"{name}={value}"


def render_cookie_pair(name: str, value: str) -> str:
    return join_cookie_pair(value, name)


def normalize_scope(host: str, path: str, include_path: bool = False) -> str:
    if include_path:
        return f"{host}{path}"
    return host


def cookie_scope_key(host: str, path: str) -> str:
    return normalize_scope(host, path)
