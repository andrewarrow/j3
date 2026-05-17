def default_project_metadata(project_name: str, version: str) -> dict[str, str]:
    return {
        "metadata_version": "2.2",
        "name": project_name,
        "version": version,
    }


def core_metadata_headers(project_name: str, version: str) -> dict[str, str]:
    metadata = default_project_metadata(project_name, version)
    return {
        "Metadata-Version": metadata["metadata_version"],
        "Name": metadata["name"],
        "Version": metadata["version"],
    }


def project_url_headers(homepage: str, repository: str) -> dict[str, str]:
    return {
        "Homepage": homepage,
        "Project_URL": repository,
    }


def readme_content_type(readme_format: str) -> str:
    content_types = {
        "markdown": "text/plain",
        "rst": "text/x-rst",
    }
    return content_types[readme_format]


def supports_python_version(version: tuple[int, int], minimum: tuple[int, int]) -> bool:
    return version > minimum


def license_classifier(license_id: str) -> str:
    classifiers = {
        "MIT": "License :: OSI Approved :: MIT License",
        "Apache-2.0": "License :: OSI Approved :: Apache License",
    }
    return classifiers[license_id]
