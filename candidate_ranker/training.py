"""Training loop for the candidate ranker."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .constants import RANKER_FEATURE_VERSION, RANKER_FORMAT
from .metrics import (
    _RankerMetricsAccumulator,
    _accumulate_ranker_metrics,
    _ranker_calibration_record,
    _ranker_metrics_records,
)
from .model import score_features
from .outcomes import (
    _candidate_record_features,
    _outcome_task_family,
    _positive_outcome_row,
    _record_hints,
    _training_pairs_from_outcome_rows,
    _training_pairs_from_plan,
)
from .types import CandidateRankerTrainingResult


@dataclass(frozen=True, slots=True)
class _ValidationPlan:
    task: str
    family: str
    hints: list[dict[str, object]]
    rows: list[dict[str, object]]


def train_candidate_ranker(
    *,
    diagnostics_paths: list[Path] | None = None,
    candidate_outcome_paths: list[Path] | None = None,
    validation_diagnostics_paths: list[Path] | None = None,
    validation_candidate_outcome_paths: list[Path] | None = None,
    holdout_tasks: list[str] | set[str] | tuple[str, ...] | None = None,
    holdout_task_families: list[str] | set[str] | tuple[str, ...] | None = None,
    out_dir: Path,
    epochs: int = 8,
    learning_rate: float = 0.25,
    margin: float = 1.0,
    plan_name: str = "ranked",
) -> CandidateRankerTrainingResult:
    """Train a pairwise linear ranker from eval diagnostics or outcome rows."""

    diagnostics_paths = diagnostics_paths or []
    candidate_outcome_paths = candidate_outcome_paths or []
    validation_diagnostics_paths = validation_diagnostics_paths or []
    validation_candidate_outcome_paths = validation_candidate_outcome_paths or []
    holdout_task_names = _normalize_holdout_names(holdout_tasks)
    holdout_families = _normalize_holdout_names(holdout_task_families)
    if not diagnostics_paths and not candidate_outcome_paths:
        raise ValueError("at least one diagnostics or candidate outcome path is required")
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be positive")
    if margin <= 0:
        raise ValueError("margin must be positive")

    resolved_paths = [path.expanduser().resolve() for path in diagnostics_paths]
    resolved_outcome_paths = [path.expanduser().resolve() for path in candidate_outcome_paths]
    resolved_validation_paths = [
        path.expanduser().resolve() for path in validation_diagnostics_paths
    ]
    resolved_validation_outcome_paths = [
        path.expanduser().resolve() for path in validation_candidate_outcome_paths
    ]
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    plans = 0
    task_names: set[str] = set()
    action_metrics: dict[str, _RankerMetricsAccumulator] = {}
    family_metrics: dict[str, _RankerMetricsAccumulator] = {}
    calibration_rows: list[tuple[dict[str, float], bool]] = []
    rows = 0
    passing_rows = 0

    for path in resolved_paths:
        path_pairs, path_plans, path_rows, path_passing, path_tasks = _read_diagnostics_path(
            path=path,
            plan_name=plan_name,
            action_metrics=action_metrics,
            family_metrics=family_metrics,
            calibration_rows=calibration_rows,
            holdout_tasks=holdout_task_names,
            holdout_task_families=holdout_families,
        )
        pairs.extend(path_pairs)
        plans += path_plans
        rows += path_rows
        passing_rows += path_passing
        task_names.update(path_tasks)

    for path in resolved_outcome_paths:
        path_pairs, path_plans, path_rows, path_passing, path_tasks = _read_candidate_outcome_path(
            path=path,
            plan_name=plan_name,
            action_metrics=action_metrics,
            family_metrics=family_metrics,
            calibration_rows=calibration_rows,
            holdout_tasks=holdout_task_names,
            holdout_task_families=holdout_families,
        )
        pairs.extend(path_pairs)
        plans += path_plans
        rows += path_rows
        passing_rows += path_passing
        task_names.update(path_tasks)

    failing_rows = rows - passing_rows
    if not pairs:
        raise ValueError("training sources did not contain solved plans with failed candidates")

    weights, mistakes = _fit_pairwise_weights(
        pairs,
        epochs=epochs,
        learning_rate=learning_rate,
        margin=margin,
    )
    correct_pairs, margin_violations = _score_training_pairs(pairs, weights, margin=margin)
    training_accuracy = correct_pairs / len(pairs)

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    ranker_path = output / "candidate-ranker.json"
    metrics_path = output / "candidate-ranker-metrics.json"
    model = {
        "format": RANKER_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": RANKER_FEATURE_VERSION,
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "candidate_outcome_sources": [str(path) for path in resolved_outcome_paths],
        "holdout_tasks": sorted(holdout_task_names),
        "holdout_task_families": sorted(holdout_families),
        "plan": plan_name,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "margin": margin,
        "bias": 0.0,
        "weights": dict(sorted(weights.items())),
    }
    per_action = _ranker_metrics_records(action_metrics)
    per_task_family = _ranker_metrics_records(family_metrics)
    calibration = _ranker_calibration_record(calibration_rows, weights)
    validation = _ranker_validation_record(
        diagnostics_paths=resolved_validation_paths,
        candidate_outcome_paths=resolved_validation_outcome_paths,
        holdout_diagnostics_paths=resolved_paths,
        holdout_candidate_outcome_paths=resolved_outcome_paths,
        holdout_tasks=holdout_task_names,
        holdout_task_families=holdout_families,
        plan_name=plan_name,
        weights=weights,
    )
    metrics = {
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "candidate_outcome_sources": [str(path) for path in resolved_outcome_paths],
        "validation_diagnostics_sources": [
            str(path) for path in resolved_validation_paths
        ],
        "validation_candidate_outcome_sources": [
            str(path) for path in resolved_validation_outcome_paths
        ],
        "holdout_diagnostics_sources": [
            str(path) for path in resolved_paths if holdout_task_names or holdout_families
        ],
        "holdout_candidate_outcome_sources": [
            str(path) for path in resolved_outcome_paths if holdout_task_names or holdout_families
        ],
        "holdout_tasks": sorted(holdout_task_names),
        "holdout_task_families": sorted(holdout_families),
        "plan": plan_name,
        "rows": rows,
        "passing_rows": passing_rows,
        "failing_rows": failing_rows,
        "tasks": len(task_names),
        "plans": plans,
        "training_pairs": len(pairs),
        "features": len(weights),
        "mistakes": mistakes,
        "training_accuracy": training_accuracy,
        "margin_violations": margin_violations,
        "calibration": calibration,
        "validation": validation,
        "per_action": per_action,
        "per_task_family": per_task_family,
        "artifacts": {
            "ranker": ranker_path.name,
            "metrics": metrics_path.name,
        },
    }
    ranker_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return CandidateRankerTrainingResult(
        out_dir=output,
        ranker_path=ranker_path,
        metrics_path=metrics_path,
        diagnostics_paths=resolved_paths,
        candidate_outcome_paths=resolved_outcome_paths,
        validation_diagnostics_paths=resolved_validation_paths,
        validation_candidate_outcome_paths=resolved_validation_outcome_paths,
        holdout_tasks=sorted(holdout_task_names),
        holdout_task_families=sorted(holdout_families),
        rows=rows,
        passing_rows=passing_rows,
        failing_rows=failing_rows,
        tasks=len(task_names),
        plans=plans,
        training_pairs=len(pairs),
        features=len(weights),
        mistakes=mistakes,
        training_accuracy=training_accuracy,
        margin_violations=margin_violations,
        calibration=calibration,
        validation=validation,
        per_action=per_action,
        per_task_family=per_task_family,
    )


def _read_diagnostics_path(
    *,
    path: Path,
    plan_name: str,
    action_metrics: dict[str, _RankerMetricsAccumulator],
    family_metrics: dict[str, _RankerMetricsAccumulator],
    calibration_rows: list[tuple[dict[str, float], bool]],
    holdout_tasks: set[str],
    holdout_task_families: set[str],
) -> tuple[list[tuple[dict[str, float], dict[str, float]]], int, int, int, set[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    plans = 0
    rows = 0
    passing_rows = 0
    task_names: set[str] = set()

    for task in payload.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_name = str(task.get("name", ""))
        task_family = str(task.get("family", "unclassified"))
        if _matches_holdout(
            task=task_name,
            family=task_family,
            holdout_tasks=holdout_tasks,
            holdout_task_families=holdout_task_families,
        ):
            continue
        if task_name:
            task_names.add(task_name)
        plan = task.get(plan_name)
        if not isinstance(plan, dict):
            continue

        plan_pairs = _training_pairs_from_plan(plan)
        tested = plan.get("tested_candidates")
        if isinstance(tested, list):
            _append_plan_calibration_rows(
                plan=plan,
                candidates=[candidate for candidate in tested if isinstance(candidate, dict)],
                calibration_rows=calibration_rows,
            )
            _accumulate_ranker_metrics(
                action_metrics=action_metrics,
                family_metrics=family_metrics,
                task_family=task_family,
                rows=[candidate for candidate in tested if isinstance(candidate, dict)],
                training_pairs=len(plan_pairs),
            )
            rows += len(tested)
            passing_rows += sum(
                1 for candidate in tested if isinstance(candidate, dict) and candidate.get("passed") is True
            )
        if plan_pairs:
            plans += 1
            pairs.extend(plan_pairs)

    return pairs, plans, rows, passing_rows, task_names


def _read_candidate_outcome_path(
    *,
    path: Path,
    plan_name: str,
    action_metrics: dict[str, _RankerMetricsAccumulator],
    family_metrics: dict[str, _RankerMetricsAccumulator],
    calibration_rows: list[tuple[dict[str, float], bool]],
    holdout_tasks: set[str],
    holdout_task_families: set[str],
) -> tuple[list[tuple[dict[str, float], dict[str, float]]], int, int, int, set[str]]:
    grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = {}
    rows = 0
    passing_rows = 0
    task_names: set[str] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        task = str(row.get("task", ""))
        phase = str(row.get("phase", plan_name))
        grouped_rows.setdefault((task, phase), []).append(row)

    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    plans = 0
    for (_task, phase), task_rows in grouped_rows.items():
        if phase != plan_name:
            continue
        task_family = _outcome_task_family(task_rows)
        if _matches_holdout(
            task=_task,
            family=task_family,
            holdout_tasks=holdout_tasks,
            holdout_task_families=holdout_task_families,
        ):
            continue
        rows += len(task_rows)
        passing_rows += sum(1 for row in task_rows if row.get("passed") is True)
        if _task:
            task_names.add(_task)
        _append_outcome_calibration_rows(task_rows, calibration_rows)
        plan_pairs = _training_pairs_from_outcome_rows(task_rows)
        _accumulate_ranker_metrics(
            action_metrics=action_metrics,
            family_metrics=family_metrics,
            task_family=task_family,
            rows=task_rows,
            training_pairs=len(plan_pairs),
        )
        if plan_pairs:
            plans += 1
            pairs.extend(plan_pairs)

    return pairs, plans, rows, passing_rows, task_names


def _append_plan_calibration_rows(
    *,
    plan: dict[str, object],
    candidates: list[dict[str, object]],
    calibration_rows: list[tuple[dict[str, float], bool]],
) -> None:
    plan_hints = plan.get("failure_hints", [])
    for candidate in candidates:
        calibration_rows.append(
            (
                _candidate_record_features(candidate, _record_hints(candidate, plan_hints)),
                candidate.get("passed") is True,
            )
        )


def _append_outcome_calibration_rows(
    rows: list[dict[str, object]],
    calibration_rows: list[tuple[dict[str, float], bool]],
) -> None:
    for row in rows:
        calibration_rows.append(
            (
                _candidate_record_features(row, _record_hints(row, [])),
                row.get("passed") is True,
            )
        )


def _fit_pairwise_weights(
    pairs: list[tuple[dict[str, float], dict[str, float]]],
    *,
    epochs: int,
    learning_rate: float,
    margin: float,
) -> tuple[dict[str, float], int]:
    weights: dict[str, float] = {}
    mistakes = 0
    for _ in range(epochs):
        for positive, negative in pairs:
            pos_score = score_features(positive, weights)
            neg_score = score_features(negative, weights)
            if pos_score <= neg_score + margin:
                _update_weights(weights, positive, learning_rate)
                _update_weights(weights, negative, -learning_rate)
                mistakes += 1
    return weights, mistakes


def _update_weights(weights: dict[str, float], features: Mapping[str, float], scale: float) -> None:
    for name, value in features.items():
        weights[name] = weights.get(name, 0.0) + scale * value
        if abs(weights[name]) < 1e-12:
            del weights[name]


def _score_training_pairs(
    pairs: list[tuple[dict[str, float], dict[str, float]]],
    weights: Mapping[str, float],
    *,
    margin: float,
) -> tuple[int, int]:
    correct = 0
    margin_violations = 0
    for positive, negative in pairs:
        pos_score = score_features(positive, weights)
        neg_score = score_features(negative, weights)
        if pos_score > neg_score:
            correct += 1
        if pos_score <= neg_score + margin:
            margin_violations += 1
    return correct, margin_violations


def _ranker_validation_record(
    *,
    diagnostics_paths: list[Path],
    candidate_outcome_paths: list[Path],
    holdout_diagnostics_paths: list[Path],
    holdout_candidate_outcome_paths: list[Path],
    holdout_tasks: set[str],
    holdout_task_families: set[str],
    plan_name: str,
    weights: Mapping[str, float],
) -> dict[str, object]:
    plans = _read_validation_plans(
        diagnostics_paths=diagnostics_paths,
        candidate_outcome_paths=candidate_outcome_paths,
        plan_name=plan_name,
        include_tasks=set(),
        include_task_families=set(),
    )
    if holdout_tasks or holdout_task_families:
        plans.extend(
            _read_validation_plans(
                diagnostics_paths=holdout_diagnostics_paths,
                candidate_outcome_paths=holdout_candidate_outcome_paths,
                plan_name=plan_name,
                include_tasks=holdout_tasks,
                include_task_families=holdout_task_families,
            )
        )
    action_metrics: dict[str, _RankerMetricsAccumulator] = {}
    family_metrics: dict[str, _RankerMetricsAccumulator] = {}
    calibration_rows: list[tuple[dict[str, float], bool]] = []
    task_names: set[str] = set()
    rows = 0
    passing_rows = 0
    evaluated_plans = 0
    solved = 0
    pass_at_1 = 0
    positive_at_1 = 0
    first_passing_indices: list[int] = []
    positive_ranks: list[int] = []

    for plan in plans:
        if not plan.rows:
            continue
        evaluated_plans += 1
        if plan.task:
            task_names.add(plan.task)
        rows += len(plan.rows)
        plan_passing_rows = sum(1 for row in plan.rows if row.get("passed") is True)
        passing_rows += plan_passing_rows
        if plan_passing_rows:
            solved += 1

        scored_rows = _validation_scored_rows(plan, weights)
        for _score, _original_rank, row, features in scored_rows:
            calibration_rows.append((features, row.get("passed") is True))

        ranked_rows = [row for _score, _original_rank, row, _features in scored_rows]
        positive = _positive_outcome_row(plan.rows)
        first_passing_index = _first_ranked_passing_index(ranked_rows)
        positive_rank = _rank_of_row(ranked_rows, positive)
        if first_passing_index is not None:
            first_passing_indices.append(first_passing_index)
            if first_passing_index == 1:
                pass_at_1 += 1
        if positive_rank is not None:
            positive_ranks.append(positive_rank)
            if positive_rank == 1:
                positive_at_1 += 1

        _accumulate_validation_metrics(
            action_metrics=action_metrics,
            family_metrics=family_metrics,
            task_family=plan.family,
            rows=plan.rows,
            positive=positive,
            first_passing_index=first_passing_index,
            positive_rank=positive_rank,
        )

    failing_rows = rows - passing_rows
    return {
        "diagnostics_sources": [str(path) for path in diagnostics_paths],
        "candidate_outcome_sources": [str(path) for path in candidate_outcome_paths],
        "holdout_diagnostics_sources": [
            str(path) for path in holdout_diagnostics_paths if holdout_tasks or holdout_task_families
        ],
        "holdout_candidate_outcome_sources": [
            str(path)
            for path in holdout_candidate_outcome_paths
            if holdout_tasks or holdout_task_families
        ],
        "holdout_tasks": sorted(holdout_tasks),
        "holdout_task_families": sorted(holdout_task_families),
        "rows": rows,
        "passing_rows": passing_rows,
        "failing_rows": failing_rows,
        "tasks": len(task_names),
        "plans": evaluated_plans,
        "solved": solved,
        "pass_at_1": pass_at_1,
        "positive_at_1": positive_at_1,
        "avg_first_passing_index": (
            sum(first_passing_indices) / len(first_passing_indices)
            if first_passing_indices
            else None
        ),
        "avg_positive_rank": (
            sum(positive_ranks) / len(positive_ranks) if positive_ranks else None
        ),
        "calibration": _ranker_calibration_record(calibration_rows, weights),
        "per_action": _ranker_metrics_records(action_metrics),
        "per_task_family": _ranker_metrics_records(family_metrics),
    }


def _read_validation_plans(
    *,
    diagnostics_paths: list[Path],
    candidate_outcome_paths: list[Path],
    plan_name: str,
    include_tasks: set[str],
    include_task_families: set[str],
) -> list[_ValidationPlan]:
    plans: list[_ValidationPlan] = []
    for path in diagnostics_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task in payload.get("tasks", []):
            if not isinstance(task, dict):
                continue
            task_name = str(task.get("name", ""))
            task_family = str(task.get("family", "unclassified"))
            if not _included_by_holdout_filter(
                task=task_name,
                family=task_family,
                include_tasks=include_tasks,
                include_task_families=include_task_families,
            ):
                continue
            plan = task.get(plan_name)
            if not isinstance(plan, dict):
                continue
            tested = plan.get("tested_candidates")
            if not isinstance(tested, list):
                continue
            plans.append(
                _ValidationPlan(
                    task=task_name,
                    family=task_family,
                    hints=[
                        hint for hint in plan.get("failure_hints", []) if isinstance(hint, dict)
                    ]
                    if isinstance(plan.get("failure_hints"), list)
                    else [],
                    rows=[row for row in tested if isinstance(row, dict)],
                )
            )

    grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = {}
    for path in candidate_outcome_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            task = str(row.get("task", ""))
            phase = str(row.get("phase", plan_name))
            if phase != plan_name:
                continue
            grouped_rows.setdefault((task, phase), []).append(row)

    for (task, _phase), rows in grouped_rows.items():
        task_family = _outcome_task_family(rows)
        if not _included_by_holdout_filter(
            task=task,
            family=task_family,
            include_tasks=include_tasks,
            include_task_families=include_task_families,
        ):
            continue
        plans.append(
            _ValidationPlan(
                task=task,
                family=task_family,
                hints=[],
                rows=sorted(rows, key=lambda row: _validation_original_rank(row, 0)),
            )
        )
    return plans


def _normalize_holdout_names(values: list[str] | set[str] | tuple[str, ...] | None) -> set[str]:
    if values is None:
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def _matches_holdout(
    *,
    task: str,
    family: str,
    holdout_tasks: set[str],
    holdout_task_families: set[str],
) -> bool:
    return task in holdout_tasks or family in holdout_task_families


def _included_by_holdout_filter(
    *,
    task: str,
    family: str,
    include_tasks: set[str],
    include_task_families: set[str],
) -> bool:
    if not include_tasks and not include_task_families:
        return True
    return task in include_tasks or family in include_task_families


def _validation_scored_rows(
    plan: _ValidationPlan,
    weights: Mapping[str, float],
) -> list[tuple[float, int, dict[str, object], dict[str, float]]]:
    scored_rows: list[tuple[float, int, dict[str, object], dict[str, float]]] = []
    for index, row in enumerate(plan.rows, start=1):
        features = _candidate_record_features(row, _record_hints(row, plan.hints))
        scored_rows.append(
            (
                score_features(features, weights),
                _validation_original_rank(row, index),
                row,
                features,
            )
        )
    return sorted(scored_rows, key=lambda item: (-item[0], item[1]))


def _validation_original_rank(row: dict[str, object], default: int) -> int:
    rank = row.get("rank_index")
    return rank if isinstance(rank, int) and rank > 0 else default


def _first_ranked_passing_index(rows: list[dict[str, object]]) -> int | None:
    for index, row in enumerate(rows, start=1):
        if row.get("passed") is True:
            return index
    return None


def _rank_of_row(
    rows: list[dict[str, object]],
    target: dict[str, object] | None,
) -> int | None:
    if target is None:
        return None
    for index, row in enumerate(rows, start=1):
        if row is target:
            return index
    return None


def _accumulate_validation_metrics(
    *,
    action_metrics: dict[str, _RankerMetricsAccumulator],
    family_metrics: dict[str, _RankerMetricsAccumulator],
    task_family: str,
    rows: list[dict[str, object]],
    positive: dict[str, object] | None,
    first_passing_index: int | None,
    positive_rank: int | None,
) -> None:
    passing_rows = sum(1 for row in rows if row.get("passed") is True)
    action = str(positive.get("action", "unsolved")) if positive is not None else "unsolved"
    family = task_family or "unclassified"
    for metrics in (
        action_metrics.setdefault(action, _RankerMetricsAccumulator()),
        family_metrics.setdefault(family, _RankerMetricsAccumulator()),
    ):
        metrics.plans += 1
        metrics.rows += len(rows)
        metrics.passing_rows += passing_rows
        metrics.failing_rows += len(rows) - passing_rows
        if first_passing_index is not None:
            metrics.first_passing_indices.append(first_passing_index)
            if first_passing_index == 1:
                metrics.pass_at_1 += 1
        if positive_rank is not None:
            metrics.positive_ranks.append(positive_rank)
            if positive_rank == 1:
                metrics.positive_at_1 += 1
