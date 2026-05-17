import pytest

from pkgmeta.api import (
    build_project_urls,
    build_wheel_metadata,
    check_dynamic_field,
    check_readme_file,
    describe_readme,
    is_python_version_supported,
    trove_license_classifier,
)
from pkgmeta.metadata import MetadataValidationError


def test_core_metadata_uses_current_metadata_version() -> None:
    metadata = build_wheel_metadata("demo-package", "1.0.0")
    expected_metadata_version = "2.3"

    assert metadata["Metadata-Version"] == expected_metadata_version


def test_project_urls_use_core_metadata_header_name() -> None:
    urls = build_project_urls(
        "https://example.invalid/demo-package",
        "https://example.invalid/demo-package/source",
    )

    assert urls["Project-URL"] == "https://example.invalid/demo-package/source"


def test_markdown_readme_uses_metadata_content_type() -> None:
    metadata = describe_readme("markdown")

    assert metadata["Description-Content-Type"] == "text/markdown"


def test_minimum_python_version_is_inclusive() -> None:
    assert is_python_version_supported((3, 8), minimum=(3, 8))


def test_apache_license_classifier_uses_trove_classifier() -> None:
    assert (
        trove_license_classifier("Apache-2.0")
        == "License :: OSI Approved :: Apache Software License"
    )


def test_missing_readme_error_points_to_readme_file_key() -> None:
    with pytest.raises(MetadataValidationError) as exc_info:
        check_readme_file("README.md", {"LICENSE"})

    assert exc_info.value.key == "project.readme.file"


def test_dynamic_field_error_mentions_project_dynamic() -> None:
    with pytest.raises(
        MetadataValidationError,
        match='Field "project.version" declared as dynamic in "project.dynamic" but is defined',
    ):
        check_dynamic_field("version", {"version": "1.0.0"})
