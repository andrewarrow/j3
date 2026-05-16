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
