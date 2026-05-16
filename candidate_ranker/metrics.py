"""Training metric aggregation for the candidate ranker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .outcomes import _first_passing_rank, _positive_outcome_row, _row_rank


@dataclass(slots=True)
class _RankerMetricsAccumulator:
    plans: int = 0
    rows: int = 0
    passing_rows: int = 0
    failing_rows: int = 0
    pass_at_1: int = 0
    positive_at_1: int = 0
    training_pairs: int = 0
    first_passing_indices: list[int] = field(default_factory=list)
    positive_ranks: list[int] = field(default_factory=list)


def _accumulate_ranker_metrics(
    *,
    action_metrics: dict[str, _RankerMetricsAccumulator],
    family_metrics: dict[str, _RankerMetricsAccumulator],
    task_family: str,
    rows: list[dict[str, object]],
    training_pairs: int,
) -> None:
    if not rows:
        return

    positive = _positive_outcome_row(rows)
    action = str(positive.get("action", "unsolved")) if positive is not None else "unsolved"
    first_passing_index = _first_passing_rank(rows)
    positive_rank = _row_rank(positive, rows) if positive is not None else None
    passing_rows = sum(1 for row in rows if row.get("passed") is True)

    family = task_family or "unclassified"
    for metrics in (
        action_metrics.setdefault(action, _RankerMetricsAccumulator()),
        family_metrics.setdefault(family, _RankerMetricsAccumulator()),
    ):
        metrics.plans += 1
        metrics.rows += len(rows)
        metrics.passing_rows += passing_rows
        metrics.failing_rows += len(rows) - passing_rows
        metrics.training_pairs += training_pairs
        if first_passing_index is not None:
            metrics.first_passing_indices.append(first_passing_index)
            if first_passing_index == 1:
                metrics.pass_at_1 += 1
        if positive_rank is not None:
            metrics.positive_ranks.append(positive_rank)
            if positive_rank == 1:
                metrics.positive_at_1 += 1


def _ranker_metrics_records(
    metrics: Mapping[str, _RankerMetricsAccumulator],
) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for name, stats in sorted(metrics.items()):
        average_first_pass = (
            sum(stats.first_passing_indices) / len(stats.first_passing_indices)
            if stats.first_passing_indices
            else None
        )
        average_positive_rank = (
            sum(stats.positive_ranks) / len(stats.positive_ranks)
            if stats.positive_ranks
            else None
        )
        records[name] = {
            "plans": stats.plans,
            "rows": stats.rows,
            "passing_rows": stats.passing_rows,
            "failing_rows": stats.failing_rows,
            "pass_at_1": stats.pass_at_1,
            "positive_at_1": stats.positive_at_1,
            "avg_first_passing_index": average_first_pass,
            "avg_positive_rank": average_positive_rank,
            "training_pairs": stats.training_pairs,
        }
    return records
