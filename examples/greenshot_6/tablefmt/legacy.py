_DEPRECATED_FRAME = "FRAME"
_DEPRECATED_ALL = "ALL"


def resolve_legacy_symbol(name: str) -> str:
    value = globals().get(f"_DEPRECATED_{name}")
    if value is None:
        msg = "module 'tablefmt.legacy' has no attribute '{name}".format(name=name)
        raise AttributeError(msg)
    return value
