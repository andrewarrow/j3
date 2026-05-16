"""Training loop for the candidate ranker."""

from __future__ import annotations

import json
from collections.abc import Mapping
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
    _record_hints,
    _training_pairs_from_outcome_rows,
    _training_pairs_from_plan,
)
from .types import CandidateRankerTrainingResult


def train_candidate_ranker(
    *,
    diagnostics_paths: list[Path] | None = None,
    candidate_outcome_paths: list[Path] | None = None,
    out_dir: Path,
    epochs: int = 8,
    learning_rate: float = 0.25,
    margin: float = 1.0,
    plan_name: str = "ranked",
) -> CandidateRankerTrainingResult:
    """Train a pairwise linear ranker from eval diagnostics or outcome rows."""

    diagnostics_paths = diagnostics_paths or []
    candidate_outcome_paths = candidate_outcome_paths or []
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
    metrics = {
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "candidate_outcome_sources": [str(path) for path in resolved_outcome_paths],
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
        if task.get("name"):
            task_names.add(str(task["name"]))
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
                task_family=str(task.get("family", "unclassified")),
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
        rows += 1
        task = str(row.get("task", ""))
        phase = str(row.get("phase", plan_name))
        if task:
            task_names.add(task)
        if row.get("passed") is True:
            passing_rows += 1
        grouped_rows.setdefault((task, phase), []).append(row)

    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    plans = 0
    for (_task, phase), task_rows in grouped_rows.items():
        if phase != plan_name:
            continue
        _append_outcome_calibration_rows(task_rows, calibration_rows)
        plan_pairs = _training_pairs_from_outcome_rows(task_rows)
        _accumulate_ranker_metrics(
            action_metrics=action_metrics,
            family_metrics=family_metrics,
            task_family=_outcome_task_family(task_rows),
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
