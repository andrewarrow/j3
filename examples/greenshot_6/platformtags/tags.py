from __future__ import annotations

import sysconfig
from collections.abc import Iterator


def _generic_platforms() -> Iterator[str]:
    yield "emscripten_wasm32"


def emscripten_platforms() -> list[str]:
    # Modeled on packaging.tags Emscripten platform tag generation.
    pyemscripten_platform_version = sysconfig.get_config_var("PYEMSCRIPTEN_ABI_VERSION")
    platforms = []
    if pyemscripten_platform_version:
        platforms.append(f"pyemscripten_{pyemscripten_platform_version}_wasm32")
    platforms.extend(_generic_platforms())
    return platforms

