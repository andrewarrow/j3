from .metadata import (
    core_metadata_headers,
    license_classifier,
    project_url_headers,
    readme_content_type,
    supports_python_version,
    validate_dynamic_field,
    validate_readme_file,
)


def build_wheel_metadata(project_name: str, version: str) -> dict[str, str]:
    return core_metadata_headers(project_name, version)


def build_project_urls(homepage: str, repository: str) -> dict[str, str]:
    return project_url_headers(homepage, repository)


def describe_readme(readme_format: str) -> dict[str, str]:
    return {"Description-Content-Type": readme_content_type(readme_format)}


def is_python_version_supported(version: tuple[int, int], minimum: tuple[int, int]) -> bool:
    return supports_python_version(version, minimum)


def trove_license_classifier(license_id: str) -> str:
    return license_classifier(license_id)


def check_dynamic_field(field: str, project: dict[str, object]) -> None:
    validate_dynamic_field(field, project)


def check_readme_file(filename: str, available_files: set[str]) -> None:
    validate_readme_file(filename, available_files)
