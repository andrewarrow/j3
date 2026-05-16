"""Comparison helpers for j3 eval diagnostics files."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

DiagnosticsPhase = Literal["baseline", "ranked"]


@dataclass(frozen=True, slots=True)
class TaskRankMovement:
    name: str
    old_first_passing_index: int | None
    new_first_passing_index: int | None
    old_failure_mode: str
    new_failure_mode: str

    @property
    def old_pass_at_1(self) -> bool:
        return self.old_first_passing_index == 1

    @property
    def new_pass_at_1(self) -> bool:
        return self.new_first_passing_index == 1

    @property
    def rank_delta(self) -> int | None:
        if self.old_first_passing_index is None or self.new_first_passing_index is None:
            return None
        return self.old_first_passing_index - self.new_first_passing_index


@dataclass(frozen=True, slots=True)
class DiagnosticsComparison:
    old_path: Path
    new_path: Path
    phase: DiagnosticsPhase
    old_tasks: int
    new_tasks: int
    shared_tasks: int
    old_pass_at_1: int
    new_pass_at_1: int
    old_bad_ranking: int
    new_bad_ranking: int
    task_movements: list[TaskRankMovement]
    old_failed_reasons: list[tuple[str, int]]
    new_failed_reasons: list[tuple[str, int]]

    @property
    def pass_at_1_delta(self) -> int:
        return self.new_pass_at_1 - self.old_pass_at_1

    @property
    def bad_ranking_delta(self) -> int:
        return self.new_bad_ranking - self.old_bad_ranking


def compare_diagnostics(
    *,
    old_path: Path,
    new_path: Path,
    phase: DiagnosticsPhase = "ranked",
    top_reasons: int = 5,
) -> DiagnosticsComparison:
    """Compare rank movement and failure modes across two diagnostics files."""

    if phase not in {"baseline", "ranked"}:
        raise ValueError(f"unsupported diagnostics phase: {phase}")
    old_resolved = old_path.expanduser().resolve()
    new_resolved = new_path.expanduser().resolve()
    old_payload = json.loads(old_resolved.read_text(encoding="utf-8"))
    new_payload = json.loads(new_resolved.read_text(encoding="utf-8"))
    old_tasks = _task_plans(old_payload, phase=phase)
    new_tasks = _task_plans(new_payload, phase=phase)
    shared_names = sorted(set(old_tasks) & set(new_tasks))

    movements = [
        TaskRankMovement(
            name=name,
            old_first_passing_index=_first_passing_index(old_tasks[name]),
            new_first_passing_index=_first_passing_index(new_tasks[name]),
            old_failure_mode=_failure_mode(old_tasks[name]),
            new_failure_mode=_failure_mode(new_tasks[name]),
        )
        for name in shared_names
    ]
    movements.sort(key=_movement_sort_key)

    return DiagnosticsComparison(
        old_path=old_resolved,
        new_path=new_resolved,
        phase=phase,
        old_tasks=len(old_tasks),
        new_tasks=len(new_tasks),
        shared_tasks=len(shared_names),
        old_pass_at_1=sum(1 for plan in old_tasks.values() if _first_passing_index(plan) == 1),
        new_pass_at_1=sum(1 for plan in new_tasks.values() if _first_passing_index(plan) == 1),
        old_bad_ranking=sum(1 for plan in old_tasks.values() if _failure_mode(plan) == "bad_ranking"),
        new_bad_ranking=sum(1 for plan in new_tasks.values() if _failure_mode(plan) == "bad_ranking"),
        task_movements=movements,
        old_failed_reasons=_failed_reasons(old_tasks.values(), limit=top_reasons),
        new_failed_reasons=_failed_reasons(new_tasks.values(), limit=top_reasons),
    )


def format_diagnostics_comparison(comparison: DiagnosticsComparison) -> str:
    """Render a compact CLI report for a diagnostics comparison."""

    lines = [
        "j3 compare-diagnostics",
        f"old: {comparison.old_path}",
        f"new: {comparison.new_path}",
        f"phase: {comparison.phase}",
        (
            "tasks: "
            f"old={comparison.old_tasks} "
            f"new={comparison.new_tasks} "
            f"shared={comparison.shared_tasks}"
        ),
        (
            "pass@1: "
            f"{comparison.old_pass_at_1}/{comparison.old_tasks} -> "
            f"{comparison.new_pass_at_1}/{comparison.new_tasks} "
            f"({_signed(comparison.pass_at_1_delta)})"
        ),
        (
            "bad-ranking: "
            f"{comparison.old_bad_ranking} -> "
            f"{comparison.new_bad_ranking} "
            f"({_signed(comparison.bad_ranking_delta)})"
        ),
        "tasks:",
    ]
    if comparison.task_movements:
        for movement in comparison.task_movements:
            lines.append(f"  {movement.name}: {_movement_line(movement)}")
    else:
        lines.append("  no shared tasks")

    lines.extend(
        [
            "top failed candidate reasons:",
            "  old:",
        ]
    )
    lines.extend(_reason_lines(comparison.old_failed_reasons))
    lines.append("  new:")
    lines.extend(_reason_lines(comparison.new_failed_reasons))
    return "\n".join(lines)


def _task_plans(payload: object, *, phase: DiagnosticsPhase) -> dict[str, dict[str, object]]:
    if not isinstance(payload, dict):
        return {}
    plans: dict[str, dict[str, object]] = {}
    for task in payload.get("tasks", []):
        if not isinstance(task, dict) or not task.get("name"):
            continue
        plan = task.get(phase)
        if isinstance(plan, dict) and plan.get("skipped") is not True:
            plans[str(task["name"])] = plan
    return plans


def _first_passing_index(plan: dict[str, object]) -> int | None:
    value = plan.get("first_passing_index")
    if isinstance(value, int):
        return value
    tested = plan.get("tested_candidates")
    if isinstance(tested, list):
        for index, candidate in enumerate(tested, start=1):
            if isinstance(candidate, dict) and candidate.get("passed") is True:
                return index
    return None


def _failure_mode(plan: dict[str, object]) -> str:
    summary = plan.get("summary")
    if isinstance(summary, dict) and summary.get("failure_mode"):
        return str(summary["failure_mode"])
    if _first_passing_index(plan) == 1:
        return "pass_at_1"
    if _first_passing_index(plan) is not None:
        return "bad_ranking"
    if _int_value(plan.get("candidates_tested")) >= _int_value(plan.get("candidates_generated")):
        return "missing_action"
    return "search_budget_or_bad_ranking"


def _failed_reasons(
    plans: Iterable[object],
    *,
    limit: int,
) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        summary = plan.get("summary")
        if isinstance(summary, dict):
            used_summary = False
            for item in summary.get("top_failed_candidate_reasons", []):
                if isinstance(item, dict) and item.get("reason"):
                    counter[str(item["reason"])] += _int_value(item.get("count"), default=1)
                    used_summary = True
            if used_summary:
                continue
        tested = plan.get("tested_candidates")
        if isinstance(tested, list):
            for candidate in tested:
                if (
                    isinstance(candidate, dict)
                    and candidate.get("passed") is not True
                    and candidate.get("reason")
                ):
                    counter[str(candidate["reason"])] += 1
    return counter.most_common(max(0, limit))


def _movement_line(movement: TaskRankMovement) -> str:
    status = _status_change(movement)
    return (
        f"first_pass={_rank_label(movement.old_first_passing_index)}"
        f"->{_rank_label(movement.new_first_passing_index)} "
        f"movement={_movement_label(movement)} "
        f"mode={movement.old_failure_mode}->{movement.new_failure_mode} "
        f"{status}"
    )


def _status_change(movement: TaskRankMovement) -> str:
    if movement.old_pass_at_1 and not movement.new_pass_at_1:
        return "pass@1 lost"
    if not movement.old_pass_at_1 and movement.new_pass_at_1:
        return "pass@1 gained"
    if movement.old_pass_at_1 and movement.new_pass_at_1:
        return "pass@1 kept"
    return "pass@1 missed"


def _movement_label(movement: TaskRankMovement) -> str:
    if movement.old_first_passing_index is None and movement.new_first_passing_index is None:
        return "unchanged"
    if movement.old_first_passing_index is None:
        return "found"
    if movement.new_first_passing_index is None:
        return "lost"
    delta = movement.rank_delta or 0
    if delta == 0:
        return "0"
    return _signed(delta)


def _movement_sort_key(movement: TaskRankMovement) -> tuple[int, str]:
    priority = 2
    if movement.old_pass_at_1 != movement.new_pass_at_1:
        priority = 0
    elif movement.old_failure_mode != movement.new_failure_mode:
        priority = 1
    return (priority, movement.name)


def _reason_lines(reasons: list[tuple[str, int]]) -> list[str]:
    if not reasons:
        return ["    none"]
    return [f"    {reason}: {count}" for reason, count in reasons]


def _rank_label(value: int | None) -> str:
    return str(value) if value is not None else "-"


def _signed(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _int_value(value: object, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default
