from __future__ import annotations

import shutil

from j3.fixing import parse_pytest_failures, run_fix_workflow


def test_parse_pytest_failures() -> None:
    output = """
FAILED tests/test_bugs.py::test_discount_returns_remaining_price - assert 50 == 150
FAILED tests/test_bugs.py::test_last_item_returns_tail - assert 1 == 3
"""

    assert parse_pytest_failures(output) == [
        "tests/test_bugs.py::test_discount_returns_remaining_price",
        "tests/test_bugs.py::test_last_item_returns_tail",
    ]


def test_fix_workflow_dry_run_plans_without_applying(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = run_fix_workflow(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        model_path=None,
        yes=False,
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.failing_targets == ["tests/test_calculator.py::test_apply_discount_returns_discounted_price"]
    assert result.solved == 1
    assert result.applied == 0
    assert result.attempts[0].plan.transition_ranking is None
    assert "return price * (percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_fix_workflow_applies_with_yes(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = run_fix_workflow(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        model_path=None,
        yes=True,
        dry_run=False,
        timeout_seconds=10,
    )

    assert result.solved == 1
    assert result.applied == 1
    assert "return price * (1 - percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")
