"""Lightweight consistency checks for persistent planning files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


TASK_ID_PATTERN = r"[A-Z][A-Z0-9]*-\d+"
TASK_HEADING_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.MULTILINE)
TASK_ID_AT_START_RE = re.compile(rf"^`?(?P<task_id>{TASK_ID_PATTERN})`?\s*:")
STATUS_RE = re.compile(r"^- Status:\s*(?P<status>[A-Za-z0-9_-]+)\s*$", re.MULTILINE)
STATUS_VALUE_RE = re.compile(r"^- `(?P<status>[a-z_]+)`:", re.MULTILINE)
LEADING_TASK_REF_RE = re.compile(
    rf"^\s*(?:[-*]|\d+\.)\s+`(?P<task_id>{TASK_ID_PATTERN})`",
    re.MULTILINE,
)


@dataclass(frozen=True)
class TaskEntry:
    task_id: str
    status: str | None
    line: int
    status_line: int | None
    heading: str


@dataclass(frozen=True)
class MarkdownSection:
    text: str
    start_line: int


def validate_plan_consistency(
    *,
    active_path: Path | str = Path("plans/active.md"),
    backlog_path: Path | str = Path("plans/backlog.md"),
) -> dict[str, object]:
    """Validate active/backlog planning files and return a small report."""

    active = Path(active_path)
    backlog = Path(backlog_path)
    return validate_plan_consistency_text(
        active.read_text(encoding="utf-8"),
        backlog.read_text(encoding="utf-8"),
        active_name=str(active),
        backlog_name=str(backlog),
    )


def validate_plan_consistency_text(
    active_text: str,
    backlog_text: str,
    *,
    active_name: str = "plans/active.md",
    backlog_name: str = "plans/backlog.md",
) -> dict[str, object]:
    """Validate the current Markdown planning contract.

    The parser intentionally targets the stable task-heading/status structure
    used by ``plans/active.md`` and ``plans/backlog.md``. It is not a general
    Markdown parser.
    """

    issues: list[dict[str, object]] = []
    valid_statuses = _valid_statuses_from_backlog(backlog_text)
    backlog_tasks = _parse_backlog_tasks(
        backlog_text,
        file_name=backlog_name,
        valid_statuses=valid_statuses,
        issues=issues,
    )
    active_tasks = _parse_active_task_entries(
        active_text,
        file_name=active_name,
        valid_statuses=valid_statuses,
        issues=issues,
    )

    for task in active_tasks:
        if task.task_id not in backlog_tasks:
            issues.append(
                _issue(
                    file=active_name,
                    line=task.line,
                    issue="active_task_missing_from_backlog",
                    message=(
                        f"active task {task.task_id} is not present in "
                        f"{backlog_name}"
                    ),
                    task_id=task.task_id,
                    section="Active Tasks",
                )
            )
            continue
        backlog_task = backlog_tasks[task.task_id]
        if task.status is None or backlog_task.status is None:
            continue
        if task.status != backlog_task.status:
            issues.append(
                _issue(
                    file=active_name,
                    line=task.status_line or task.line,
                    issue="task_status_drift",
                    message=(
                        f"{task.task_id} is {task.status!r} in {active_name} "
                        f"but {backlog_task.status!r} in {backlog_name}"
                    ),
                    task_id=task.task_id,
                    section="Active Tasks",
                )
            )

    for section_name, expected_statuses in (
        ("Ready Queue", {"ready"}),
        ("Paused Or Blocked", {"blocked", "parked"}),
        ("Recently Completed", None),
    ):
        section = _extract_section(active_text, section_name)
        if section is None:
            issues.append(
                _issue(
                    file=active_name,
                    line=1,
                    issue="missing_section",
                    message=f"{active_name} is missing ## {section_name}",
                    section=section_name,
                )
            )
            continue
        _validate_referenced_tasks(
            section,
            section_name=section_name,
            expected_statuses=expected_statuses,
            backlog_tasks=backlog_tasks,
            active_name=active_name,
            backlog_name=backlog_name,
            issues=issues,
        )

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    return {
        "schema_version": "plan-consistency-report-v1",
        "valid": error_count == 0,
        "error_count": error_count,
        "issue_count": len(issues),
        "issues": issues,
    }


def _parse_backlog_tasks(
    text: str,
    *,
    file_name: str,
    valid_statuses: frozenset[str],
    issues: list[dict[str, object]],
) -> dict[str, TaskEntry]:
    tasks: dict[str, TaskEntry] = {}
    for task in _parse_task_headings(
        text,
        file_name=file_name,
        valid_statuses=valid_statuses,
        issues=issues,
    ):
        if task.task_id in tasks:
            issues.append(
                _issue(
                    file=file_name,
                    line=task.line,
                    issue="duplicate_task_id",
                    message=f"duplicate backlog task id {task.task_id}",
                    task_id=task.task_id,
                )
            )
            continue
        tasks[task.task_id] = task
    return tasks


def _parse_active_task_entries(
    text: str,
    *,
    file_name: str,
    valid_statuses: frozenset[str],
    issues: list[dict[str, object]],
) -> list[TaskEntry]:
    section = _extract_section(text, "Active Tasks")
    if section is None:
        issues.append(
            _issue(
                file=file_name,
                line=1,
                issue="missing_section",
                message=f"{file_name} is missing ## Active Tasks",
                section="Active Tasks",
            )
        )
        return []

    tasks = _parse_task_headings(
        section.text,
        file_name=file_name,
        valid_statuses=valid_statuses,
        issues=issues,
        line_offset=section.start_line - 1,
        section="Active Tasks",
    )
    for task in tasks:
        if task.status is not None and task.status != "active":
            issues.append(
                _issue(
                    file=file_name,
                    line=task.status_line or task.line,
                    issue="active_task_status_not_active",
                    message=(
                        f"task {task.task_id} is listed under Active Tasks "
                        f"with status {task.status!r}"
                    ),
                    task_id=task.task_id,
                    section="Active Tasks",
                )
            )
    return tasks


def _parse_task_headings(
    text: str,
    *,
    file_name: str,
    valid_statuses: frozenset[str],
    issues: list[dict[str, object]],
    line_offset: int = 0,
    section: str | None = None,
) -> list[TaskEntry]:
    matches = list(TASK_HEADING_RE.finditer(text))
    tasks: list[TaskEntry] = []
    for index, match in enumerate(matches):
        heading = match.group("title").strip()
        line = line_offset + _line_number(text, match.start())
        task_id_match = TASK_ID_AT_START_RE.match(heading)
        if task_id_match is None:
            issues.append(
                _issue(
                    file=file_name,
                    line=line,
                    issue="missing_task_id",
                    message=f"task heading is missing a TASK-123 id: {heading}",
                    section=section,
                )
            )
            continue

        task_id = task_id_match.group("task_id")
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : block_end]
        status_match = STATUS_RE.search(block)
        if status_match is None:
            issues.append(
                _issue(
                    file=file_name,
                    line=line,
                    issue="missing_status",
                    message=f"task {task_id} is missing a - Status: line",
                    task_id=task_id,
                    section=section,
                )
            )
            tasks.append(TaskEntry(task_id, None, line, None, heading))
            continue

        status = status_match.group("status")
        status_line = line_offset + _line_number(text, match.end() + status_match.start())
        if status not in valid_statuses:
            issues.append(
                _issue(
                    file=file_name,
                    line=status_line,
                    issue="invalid_status",
                    message=(
                        f"task {task_id} has invalid status {status!r}; "
                        f"expected one of {', '.join(sorted(valid_statuses))}"
                    ),
                    task_id=task_id,
                    section=section,
                )
            )
        tasks.append(TaskEntry(task_id, status, line, status_line, heading))
    return tasks


def _validate_referenced_tasks(
    section: MarkdownSection,
    *,
    section_name: str,
    expected_statuses: set[str] | None,
    backlog_tasks: dict[str, TaskEntry],
    active_name: str,
    backlog_name: str,
    issues: list[dict[str, object]],
) -> None:
    seen: set[str] = set()
    for match in LEADING_TASK_REF_RE.finditer(section.text):
        task_id = match.group("task_id")
        if task_id in seen:
            continue
        seen.add(task_id)
        line = section.start_line + _line_number(section.text, match.start()) - 1
        backlog_task = backlog_tasks.get(task_id)
        if backlog_task is None:
            issues.append(
                _issue(
                    file=active_name,
                    line=line,
                    issue="task_reference_missing_from_backlog",
                    message=(
                        f"{section_name} references {task_id}, which is not "
                        f"present in {backlog_name}"
                    ),
                    task_id=task_id,
                    section=section_name,
                )
            )
            continue
        if expected_statuses is not None and backlog_task.status not in expected_statuses:
            issues.append(
                _issue(
                    file=active_name,
                    line=line,
                    issue="task_reference_status_drift",
                    message=(
                        f"{section_name} references {task_id}, but its backlog "
                        f"status is {backlog_task.status!r}; expected one of "
                        f"{', '.join(sorted(expected_statuses))}"
                    ),
                    task_id=task_id,
                    section=section_name,
                )
            )


def _extract_section(text: str, heading: str) -> MarkdownSection | None:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if match is None:
        return None
    body_start = match.end()
    next_match = re.search(r"^##\s+", text[body_start:], re.MULTILINE)
    body_end = (
        body_start + next_match.start() if next_match is not None else len(text)
    )
    return MarkdownSection(
        text=text[body_start:body_end],
        start_line=_line_number(text, body_start),
    )


def _valid_statuses_from_backlog(text: str) -> frozenset[str]:
    statuses = frozenset(match.group("status") for match in STATUS_VALUE_RE.finditer(text))
    return statuses or frozenset({"active", "blocked", "done", "parked", "ready"})


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _issue(
    *,
    file: str,
    line: int,
    issue: str,
    message: str,
    task_id: str | None = None,
    section: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "severity": "error",
        "file": file,
        "line": line,
        "issue": issue,
        "message": message,
    }
    if task_id is not None:
        record["task_id"] = task_id
    if section is not None:
        record["section"] = section
    return record
