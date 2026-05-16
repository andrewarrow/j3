from pkgmeta.api import build_wheel_metadata


def test_core_metadata_uses_current_metadata_version() -> None:
    metadata = build_wheel_metadata("demo-package", "1.0.0")
    expected_metadata_version = "2.3"

    assert metadata["Metadata-Version"] == expected_metadata_version
