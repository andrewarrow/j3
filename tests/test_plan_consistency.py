from __future__ import annotations

from pathlib import Path

from j3.plan_consistency import (
    validate_plan_consistency,
    validate_plan_consistency_text,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _backlog(status: str = "active") -> str:
    return f"""# Backlog

## Task Status Values

- `ready`: bounded enough for a worker
- `active`: assigned or in progress
- `blocked`: waiting on evidence, design, or dependency
- `done`: completed and recorded
- `parked`: intentionally deferred

## Workstream A

### OPS-001: Completed setup

- Status: done

### OPS-002: Add a lightweight plan consistency check

- Status: {status}

### GS7-002: Add non-calculator fixtures

- Status: ready

### DATA-004: Normalize transition examples

- Status: blocked
"""


def _active(status: str = "active", task_id: str = "OPS-002") -> str:
    return f"""# Active Board

## Active Tasks

### `{task_id}`: Add a lightweight plan consistency check

- Status: {status}

## Ready Queue

1. `GS7-002`: add five non-calculator fixtures.

## Paused Or Blocked

- `DATA-004`: blocked until issue/PR mining exists.

## Recently Completed

- `OPS-001`: migrated planning files.
"""


def _issue_names(report: dict[str, object]) -> set[str]:
    return {
        issue["issue"]
        for issue in report["issues"]  # type: ignore[index,union-attr]
    }


def test_current_plan_files_are_consistent() -> None:
    report = validate_plan_consistency(
        active_path=REPO_ROOT / "plans/active.md",
        backlog_path=REPO_ROOT / "plans/backlog.md",
    )

    assert report["valid"] is True, report["issues"]


def test_plan_consistency_accepts_matching_active_and_backlog() -> None:
    report = validate_plan_consistency_text(_active(), _backlog())

    assert report["valid"] is True
    assert report["error_count"] == 0


def test_plan_consistency_catches_missing_task_ids() -> None:
    active = _active().replace(
        "### `OPS-002`: Add a lightweight plan consistency check",
        "### Add a lightweight plan consistency check",
    )

    report = validate_plan_consistency_text(active, _backlog())

    assert report["valid"] is False
    assert "missing_task_id" in _issue_names(report)


def test_plan_consistency_catches_invalid_status_values() -> None:
    report = validate_plan_consistency_text(_active(status="working"), _backlog())

    assert report["valid"] is False
    assert "invalid_status" in _issue_names(report)


def test_plan_consistency_catches_active_tasks_missing_from_backlog() -> None:
    report = validate_plan_consistency_text(_active(task_id="OPS-999"), _backlog())

    assert report["valid"] is False
    assert "active_task_missing_from_backlog" in _issue_names(report)


def test_plan_consistency_catches_active_done_status_drift() -> None:
    report = validate_plan_consistency_text(_active(), _backlog(status="done"))

    assert report["valid"] is False
    assert "task_status_drift" in _issue_names(report)
