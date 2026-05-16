from __future__ import annotations

import shutil

import pytest

from cli import main


def test_help_menu_prints_project_summary(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "local-first JEPA coding agent" in output
    assert "patch" in output
    assert "train" in output
    assert "eval" in output


def test_actions_command_lists_structured_actions(capsys) -> None:
    assert main(["actions"]) == 0

    output = capsys.readouterr().out
    assert "change_operator" in output
    assert "modify_condition" in output


def test_patch_command_accepts_repo_and_test(capsys, tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    assert (
        main(
            [
                "patch",
                "--repo",
                str(repo),
                "--test",
                "python -m pytest tests/test_calculator.py",
                "--dry-run",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "j3 patch (dry run)" in output
    assert "pytest tests/test_calculator.py" in output
    assert "status: found passing patch" in output
