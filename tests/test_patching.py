from __future__ import annotations

import shutil

from patching import plan_and_maybe_apply_patch


def test_patch_finds_discount_fix_without_modifying_in_dry_run(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.applied is False
    assert "price * (1 - percent / 100)" in result.selected.patched_source
    assert "return price * (percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_patch_applies_discount_fix(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=False,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.applied is True
    assert "return price * (1 - percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")
