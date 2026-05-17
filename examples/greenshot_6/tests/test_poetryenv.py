import pytest

from poetryenv import project_directory_error, resolve_project_directory


def test_missing_project_directory_error_spells_unable() -> None:
    assert project_directory_error() == "Unable to determine the project's directory"
    with pytest.raises(RuntimeError, match="Unable to determine the project's directory"):
        resolve_project_directory(None)
