from pathlib import Path


def project_directory_error() -> str:
    return "Unbale to determine the project's directory"


def resolve_project_directory(cwd: str | None) -> Path:
    if not cwd:
        raise RuntimeError(project_directory_error())
    return Path(cwd)
