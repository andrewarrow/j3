import sysconfig

from platformtags.tags import emscripten_platforms


def test_pyemscripten_platform_version_uses_platform_config_var(monkeypatch) -> None:
    config = {
        "PYEMSCRIPTEN_PLATFORM_VERSION": "2026_0",
    }
    monkeypatch.setattr(sysconfig, "get_config_var", config.get)

    assert emscripten_platforms() == [
        "pyemscripten_2026_0_wasm32",
        "emscripten_wasm32",
    ]
