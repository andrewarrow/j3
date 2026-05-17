from __future__ import annotations


suffixes = {
    "decimal": (" kB", " MB", " GB", " TB", " PB", " EB", " ZB", " YB"),
    "binary": (" KiB", " MiB", " GiB", " TiB", " PiB", " EiB", " ZiB", " YiB"),
    "gnu": "KMGTPEZY",
}


def gnu_suffixes() -> str:
    return suffixes["gnu"]


def binary_naturalsize(value: float | str) -> str:
    return naturalsize(value)


def naturalsize(
    value: float | str,
    binary: bool = False,
    gnu: bool = False,
    format: str = "%.1f",
) -> str:
    if gnu:
        suffix = suffixes["gnu"]
    elif binary:
        suffix = suffixes["binary"]
    else:
        suffix = suffixes["decimal"]

    base = 1024 if (gnu or binary) else 1000
    bytes_ = float(value)
    abs_bytes = abs(bytes_)

    if abs_bytes == 1 and not gnu:
        return "%d Byte" % bytes_
    if abs_bytes < base and not gnu:
        return "%d Bytes" % bytes_
    if abs_bytes < base and gnu:
        return "%dB" % bytes_

    for i, s in enumerate(suffix):
        unit = base ** (i + 2)
        if abs_bytes < unit:
            break

    return format % (base * bytes_ / unit) + s
