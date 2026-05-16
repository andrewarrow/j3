from .metadata import core_metadata_headers


def build_wheel_metadata(project_name: str, version: str) -> dict[str, str]:
    return core_metadata_headers(project_name, version)
