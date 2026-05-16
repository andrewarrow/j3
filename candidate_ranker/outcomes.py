"""Outcome-row parsing for ranker training."""

from __future__ import annotations

from .features import _candidate_record_features
from .values import _int_value


def _training_pairs_from_plan(plan: dict[str, object]) -> list[tuple[dict[str, float], dict[str, float]]]:
    tested = plan.get("tested_candidates")
    selected = plan.get("selected")
    if not isinstance(tested, list) or not isinstance(selected, dict):
        return []

    plan_hints = plan.get("failure_hints", [])
    positive_index = _first_passing_index(tested)
    if positive_index is None:
        return []
    positive = tested[positive_index]
    if not isinstance(positive, dict):
        return []

    positive_hints = _record_hints(positive, plan_hints)
    positive_features = _candidate_record_features(positive, positive_hints)
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    for index, candidate in enumerate(tested):
        if index == positive_index:
            continue
        if isinstance(candidate, dict) and candidate.get("passed") is not True:
            candidate_hints = _record_hints(candidate, plan_hints)
            pairs.append(
                (positive_features, _candidate_record_features(candidate, candidate_hints))
            )
    return pairs


def _training_pairs_from_outcome_rows(
    rows: list[dict[str, object]],
) -> list[tuple[dict[str, float], dict[str, float]]]:
    ordered_rows = sorted(rows, key=lambda row: _int_value(row.get("rank_index"), default=0))
    positive = _positive_outcome_row(ordered_rows)
    if positive is None:
        return []

    positive_features = _candidate_record_features(positive, _record_hints(positive, []))
    preferred_positive = positive.get("preferred") is True
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    for candidate in ordered_rows:
        if candidate is positive:
            continue
        if candidate.get("passed") is not True or (
            preferred_positive and candidate.get("preferred") is not True
        ):
            pairs.append(
                (
                    positive_features,
                    _candidate_record_features(candidate, _record_hints(candidate, [])),
                )
            )
    return pairs


def _first_passing_rank(rows: list[dict[str, object]]) -> int | None:
    for row in rows:
        if row.get("is_first_pass") is True:
            value = row.get("rank_index")
            if isinstance(value, int):
                return value
    for index, row in enumerate(
        sorted(rows, key=lambda candidate: _int_value(candidate.get("rank_index"), default=0)),
        start=1,
    ):
        if row.get("passed") is True:
            value = row.get("rank_index")
            return value if isinstance(value, int) and value > 0 else index
    return None


def _row_rank(row: dict[str, object], rows: list[dict[str, object]]) -> int | None:
    rank = row.get("rank_index")
    if isinstance(rank, int) and rank > 0:
        return rank
    for index, candidate in enumerate(rows, start=1):
        if candidate is row:
            return index
    return None


def _outcome_task_family(rows: list[dict[str, object]]) -> str:
    for row in rows:
        family = row.get("task_family")
        if isinstance(family, str) and family:
            return family
    return "unclassified"


def _positive_outcome_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    for candidate in rows:
        if candidate.get("passed") is True and candidate.get("preferred") is True:
            return candidate
    for candidate in rows:
        if candidate.get("is_first_pass") is True:
            return candidate
    for candidate in rows:
        if candidate.get("passed") is True:
            return candidate
    return None


def _first_passing_index(candidates: list[object]) -> int | None:
    for index, candidate in enumerate(candidates):
        if isinstance(candidate, dict) and candidate.get("passed") is True:
            return index
    return None


def _record_hints(
    record: dict[str, object],
    fallback: object,
) -> list[dict[str, object]]:
    hints = record.get("failure_hints")
    if isinstance(hints, list):
        return [hint for hint in hints if isinstance(hint, dict)]
    if isinstance(fallback, list):
        return [hint for hint in fallback if isinstance(hint, dict)]
    return []
