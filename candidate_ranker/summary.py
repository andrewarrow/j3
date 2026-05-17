"""Candidate outcome dataset summary utilities."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class OutcomeDatasetSummary:
    paths: list[Path]
    phase: str | None
    rows: int
    tasks: int
    plans: int
    passing_rows: int
    preferred_positive_rows: int
    avg_candidates_per_task: float | None
    task_families: dict[str, dict[str, object]]
    source_types: dict[str, dict[str, object]]
    actions: dict[str, dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return {
            "paths": [str(path) for path in self.paths],
            "phase": self.phase,
            "rows": self.rows,
            "tasks": self.tasks,
            "plans": self.plans,
            "passing_rows": self.passing_rows,
            "preferred_positive_rows": self.preferred_positive_rows,
            "avg_candidates_per_task": self.avg_candidates_per_task,
            "task_families": self.task_families,
            "source_types": self.source_types,
            "actions": self.actions,
        }


@dataclass(slots=True)
class _PlanAccumulator:
    plans: int = 0
    rows: int = 0
    passing_rows: int = 0
    preferred_positive_rows: int = 0
    solved: int = 0
    pass_at_1: int = 0
    candidate_counts: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _OutcomePlan:
    task: str
    phase: str
    family: str
    source_type: str
    rows: list[dict[str, object]]


def summarize_candidate_outcomes(
    paths: Iterable[Path],
    *,
    phase: str | None = "ranked",
) -> OutcomeDatasetSummary:
    """Summarize one or more j3 candidate outcome JSONL files."""

    resolved_paths = [path.expanduser().resolve() for path in paths]
    plans = _read_outcome_plans(resolved_paths, phase=phase)
    rows = [row for plan in plans for row in plan.rows]
    task_names = {plan.task for plan in plans if plan.task}
    family_stats: defaultdict[str, _PlanAccumulator] = defaultdict(_PlanAccumulator)
    source_type_stats: defaultdict[str, _PlanAccumulator] = defaultdict(_PlanAccumulator)
    action_counts: Counter[str] = Counter()
    action_passing: Counter[str] = Counter()

    for row in rows:
        action = _label(row.get("action"), "unknown")
        action_counts[action] += 1
        if row.get("passed") is True:
            action_passing[action] += 1

    for plan in plans:
        _accumulate_plan(family_stats[plan.family], plan.rows)
        _accumulate_plan(source_type_stats[plan.source_type], plan.rows)

    return OutcomeDatasetSummary(
        paths=resolved_paths,
        phase=phase,
        rows=len(rows),
        tasks=len(task_names),
        plans=len(plans),
        passing_rows=sum(1 for row in rows if row.get("passed") is True),
        preferred_positive_rows=sum(
            1
            for row in rows
            if row.get("passed") is True and row.get("preferred") is True
        ),
        avg_candidates_per_task=_average([len(plan.rows) for plan in plans]),
        task_families=_accumulator_records(family_stats),
        source_types=_accumulator_records(source_type_stats),
        actions={
            action: {
                "rows": action_counts[action],
                "passing_rows": action_passing[action],
            }
            for action in sorted(action_counts)
        },
    )


def format_outcome_dataset_summary(summary: OutcomeDatasetSummary) -> str:
    """Format an outcome dataset summary for CLI output."""

    lines = ["j3 outcome-summary"]
    lines.append("candidate outcomes:")
    for path in summary.paths:
        lines.append(f"  {path}")
    lines.append(f"phase: {summary.phase or 'all'}")
    lines.append(f"rows: {summary.rows}")
    lines.append(f"tasks: {summary.tasks}")
    lines.append(f"plans: {summary.plans}")
    lines.append(f"passing rows: {summary.passing_rows}")
    lines.append(f"preferred-positive rows: {summary.preferred_positive_rows}")
    lines.append(
        "average candidates per task: "
        f"{summary.avg_candidates_per_task:.2f}"
        if summary.avg_candidates_per_task is not None
        else "average candidates per task: -"
    )
    lines.extend(_format_record_section("task families", summary.task_families))
    lines.extend(_format_record_section("source types", summary.source_types))
    lines.append("actions:")
    if summary.actions:
        for action, record in summary.actions.items():
            lines.append(
                f"  {action}: rows={record['rows']} passing={record['passing_rows']}"
            )
    else:
        lines.append("  -")
    return "\n".join(lines)


def _read_outcome_plans(paths: list[Path], *, phase: str | None) -> list[_OutcomePlan]:
    grouped_rows: dict[tuple[int, str, str], list[dict[str, object]]] = {}
    for path_index, path in enumerate(paths):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            row_phase = _label(row.get("phase"), "ranked")
            if phase is not None and row_phase != phase:
                continue
            task = _label(row.get("task"), "")
            grouped_rows.setdefault((path_index, task, row_phase), []).append(row)

    plans: list[_OutcomePlan] = []
    for (_path_index, task, row_phase), rows in sorted(grouped_rows.items()):
        ordered_rows = sorted(rows, key=_row_rank)
        plans.append(
            _OutcomePlan(
                task=task,
                phase=row_phase,
                family=_first_label(ordered_rows, "task_family", "unclassified"),
                source_type=_first_label(ordered_rows, "source_type", "unknown"),
                rows=ordered_rows,
            )
        )
    return plans


def _accumulate_plan(stats: _PlanAccumulator, rows: list[dict[str, object]]) -> None:
    stats.plans += 1
    stats.rows += len(rows)
    stats.candidate_counts.append(len(rows))
    passing_rows = sum(1 for row in rows if row.get("passed") is True)
    preferred_positive_rows = sum(
        1 for row in rows if row.get("passed") is True and row.get("preferred") is True
    )
    stats.passing_rows += passing_rows
    stats.preferred_positive_rows += preferred_positive_rows
    if passing_rows:
        stats.solved += 1
    if _first_passing_rank(rows) == 1:
        stats.pass_at_1 += 1


def _accumulator_records(
    stats_by_name: dict[str, _PlanAccumulator],
) -> dict[str, dict[str, object]]:
    return {
        name: {
            "plans": stats.plans,
            "rows": stats.rows,
            "passing_rows": stats.passing_rows,
            "preferred_positive_rows": stats.preferred_positive_rows,
            "solved": stats.solved,
            "pass_at_1": stats.pass_at_1,
            "avg_candidates": _average(stats.candidate_counts),
        }
        for name, stats in sorted(stats_by_name.items())
    }


def _format_record_section(
    title: str,
    records: dict[str, dict[str, object]],
) -> list[str]:
    lines = [f"{title}:"]
    if not records:
        lines.append("  -")
        return lines
    for name, record in records.items():
        lines.append(
            f"  {name}: "
            f"plans={record['plans']} "
            f"rows={record['rows']} "
            f"solved={record['solved']}/{record['plans']} "
            f"pass@1={record['pass_at_1']}/{record['plans']} "
            f"avg_candidates={record['avg_candidates']:.2f}"
        )
    return lines


def _first_passing_rank(rows: list[dict[str, object]]) -> int | None:
    for row in rows:
        if row.get("is_first_pass") is True:
            rank = row.get("rank_index")
            return rank if isinstance(rank, int) and rank > 0 else _row_rank(row)
    for row in rows:
        if row.get("passed") is True:
            rank = row.get("rank_index")
            return rank if isinstance(rank, int) and rank > 0 else _row_rank(row)
    return None


def _row_rank(row: dict[str, object]) -> int:
    rank = row.get("rank_index")
    return rank if isinstance(rank, int) and rank > 0 else 0


def _first_label(
    rows: list[dict[str, object]],
    key: str,
    default: str,
) -> str:
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def _label(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
