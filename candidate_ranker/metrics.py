"""Training metric aggregation for the candidate ranker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import exp

from .model import score_features
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


@dataclass(slots=True)
class _CalibrationBucket:
    label: str
    rows: int = 0
    passing_rows: int = 0
    probability_sum: float = 0.0


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


def _ranker_calibration_record(
    rows: list[tuple[dict[str, float], bool]],
    weights: Mapping[str, float],
) -> dict[str, object]:
    buckets = [
        _CalibrationBucket("0.0-0.2"),
        _CalibrationBucket("0.2-0.4"),
        _CalibrationBucket("0.4-0.6"),
        _CalibrationBucket("0.6-0.8"),
        _CalibrationBucket("0.8-1.0"),
    ]
    if not rows:
        return {
            "score_transform": "sigmoid",
            "rows": 0,
            "passing_rows": 0,
            "failing_rows": 0,
            "avg_probability": None,
            "avg_passing_probability": None,
            "avg_failing_probability": None,
            "brier_score": None,
            "expected_calibration_error": None,
            "buckets": [_calibration_bucket_record(bucket) for bucket in buckets],
        }

    probability_sum = 0.0
    passing_probability_sum = 0.0
    failing_probability_sum = 0.0
    brier_sum = 0.0
    passing_rows = 0

    for features, passed in rows:
        probability = _sigmoid(score_features(features, weights))
        label = 1.0 if passed else 0.0
        probability_sum += probability
        brier_sum += (probability - label) ** 2
        if passed:
            passing_rows += 1
            passing_probability_sum += probability
        else:
            failing_probability_sum += probability

        bucket = buckets[_calibration_bucket_index(probability)]
        bucket.rows += 1
        bucket.probability_sum += probability
        if passed:
            bucket.passing_rows += 1

    total_rows = len(rows)
    failing_rows = total_rows - passing_rows
    ece = 0.0
    for bucket in buckets:
        if bucket.rows == 0:
            continue
        pass_rate = bucket.passing_rows / bucket.rows
        avg_probability = bucket.probability_sum / bucket.rows
        ece += (bucket.rows / total_rows) * abs(pass_rate - avg_probability)

    return {
        "score_transform": "sigmoid",
        "rows": total_rows,
        "passing_rows": passing_rows,
        "failing_rows": failing_rows,
        "avg_probability": probability_sum / total_rows,
        "avg_passing_probability": (
            passing_probability_sum / passing_rows if passing_rows else None
        ),
        "avg_failing_probability": (
            failing_probability_sum / failing_rows if failing_rows else None
        ),
        "brier_score": brier_sum / total_rows,
        "expected_calibration_error": ece,
        "buckets": [_calibration_bucket_record(bucket) for bucket in buckets],
    }


def _calibration_bucket_record(bucket: _CalibrationBucket) -> dict[str, object]:
    return {
        "bucket": bucket.label,
        "rows": bucket.rows,
        "passing_rows": bucket.passing_rows,
        "pass_rate": bucket.passing_rows / bucket.rows if bucket.rows else None,
        "avg_probability": (
            bucket.probability_sum / bucket.rows if bucket.rows else None
        ),
    }


def _calibration_bucket_index(probability: float) -> int:
    if probability >= 1.0:
        return 4
    return min(4, max(0, int(probability * 5)))


def _sigmoid(score: float) -> float:
    if score >= 0:
        z = exp(-score)
        return 1.0 / (1.0 + z)
    z = exp(score)
    return z / (1.0 + z)
