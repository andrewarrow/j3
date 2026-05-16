"""Lightweight candidate ranker trained from eval diagnostics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol

from actions import PatchAction


RANKER_FORMAT = "j3.candidate-ranker.v1"
RANKER_FEATURE_VERSION = "candidate-diagnostics-v2"

_SYMBOLIC_PARAM_VALUES = {
    "!=",
    "%",
    "*",
    "+",
    "-",
    "/",
    "//",
    "<",
    "<=",
    "==",
    ">",
    ">=",
    "and",
    "in",
    "is",
    "is not",
    "not in",
    "or",
}


class CandidateLike(Protocol):
    file_path: str
    action: PatchAction
    reason: str
    model_score: float | None
    failure_hint_score: float


@dataclass(frozen=True, slots=True)
class CandidateRankerTrainingResult:
    out_dir: Path
    ranker_path: Path
    metrics_path: Path
    diagnostics_paths: list[Path]
    candidate_outcome_paths: list[Path]
    rows: int
    passing_rows: int
    failing_rows: int
    tasks: int
    plans: int
    training_pairs: int
    features: int
    mistakes: int
    training_accuracy: float
    margin_violations: int


@dataclass(frozen=True, slots=True)
class CandidateRankerModel:
    """Small linear ranker over candidate diagnostics features."""

    path: Path
    weights: dict[str, float]
    bias: float = 0.0

    @classmethod
    def load(cls, path: Path) -> "CandidateRankerModel":
        resolved = path.expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if payload.get("format") != RANKER_FORMAT:
            raise ValueError(f"unsupported candidate ranker format in {resolved}")
        return cls(
            path=resolved,
            weights={str(name): float(value) for name, value in payload.get("weights", {}).items()},
            bias=float(payload.get("bias", 0.0)),
        )

    def score(self, candidate: CandidateLike, hints: list[object] | tuple[object, ...] = ()) -> float:
        return score_features(candidate_features(candidate, hints=hints), self.weights, self.bias)


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
    if not diagnostics_paths:
        if not candidate_outcome_paths:
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
    rows = 0
    passing_rows = 0
    failing_rows = 0
    for path in resolved_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task in payload.get("tasks", []):
            if not isinstance(task, dict):
                continue
            if task.get("name"):
                task_names.add(str(task["name"]))
            plan = task.get(plan_name)
            if not isinstance(plan, dict):
                continue
            plan_pairs = _training_pairs_from_plan(plan)
            if plan_pairs:
                plans += 1
                pairs.extend(plan_pairs)
            tested = plan.get("tested_candidates")
            if isinstance(tested, list):
                rows += len(tested)
                passing_rows += sum(
                    1 for candidate in tested if isinstance(candidate, dict) and candidate.get("passed") is True
                )

    for path in resolved_outcome_paths:
        grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = {}
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

        for (_task, phase), task_rows in grouped_rows.items():
            if phase != plan_name:
                continue
            plan_pairs = _training_pairs_from_outcome_rows(task_rows)
            if plan_pairs:
                plans += 1
                pairs.extend(plan_pairs)

    failing_rows = rows - passing_rows

    if not pairs:
        raise ValueError("training sources did not contain solved plans with failed candidates")

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
    )


def score_features(features: Mapping[str, float], weights: Mapping[str, float], bias: float = 0.0) -> float:
    return bias + sum(weights.get(name, 0.0) * value for name, value in features.items())


def candidate_features(
    candidate: CandidateLike,
    hints: list[object] | tuple[object, ...] = (),
) -> dict[str, float]:
    action = candidate.action.kind.value
    params = dict(candidate.action.params)
    features: dict[str, float] = {
        "bias": 1.0,
        f"action:{action}": 1.0,
        "failure_hint_score": candidate.failure_hint_score / 100.0,
    }
    if candidate.model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = candidate.model_score
    if candidate.action.target.symbol:
        features["has_target_symbol"] = 1.0
    if candidate.action.target.node_kind:
        features[f"node_kind:{candidate.action.target.node_kind}"] = 1.0

    _add_param_features(features, action, params)

    for hint in hints:
        _merge_hint_features(features, candidate, action, hint)

    return features


def _training_pairs_from_plan(plan: dict[str, object]) -> list[tuple[dict[str, float], dict[str, float]]]:
    tested = plan.get("tested_candidates")
    selected = plan.get("selected")
    if not isinstance(tested, list) or not isinstance(selected, dict):
        return []

    hints = plan.get("failure_hints", [])
    positive_index = _first_passing_index(tested)
    if positive_index is None:
        return []
    positive = tested[positive_index]
    if not isinstance(positive, dict):
        return []

    positive_features = _candidate_record_features(positive, hints)
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    for index, candidate in enumerate(tested):
        if index == positive_index:
            continue
        if isinstance(candidate, dict) and candidate.get("passed") is not True:
            pairs.append((positive_features, _candidate_record_features(candidate, hints)))
    return pairs


def _training_pairs_from_outcome_rows(
    rows: list[dict[str, object]],
) -> list[tuple[dict[str, float], dict[str, float]]]:
    ordered_rows = sorted(rows, key=lambda row: _int_value(row.get("rank_index"), default=0))
    positive = _first_passing_outcome_row(ordered_rows)
    if positive is None:
        return []

    positive_features = _candidate_record_features(positive, [])
    return [
        (positive_features, _candidate_record_features(candidate, []))
        for candidate in ordered_rows
        if candidate is not positive and candidate.get("passed") is not True
    ]


def _first_passing_outcome_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
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


def _candidate_record_features(candidate: dict[str, object], hints: object) -> dict[str, float]:
    action = str(candidate.get("action", ""))
    params = candidate.get("params", {})
    features: dict[str, float] = {
        "bias": 1.0,
        f"action:{action}": 1.0,
        "failure_hint_score": _float_value(candidate.get("failure_hint_score")) / 100.0,
    }
    model_score = candidate.get("model_score")
    if model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = _float_value(model_score)
    symbol = candidate.get("symbol")
    if symbol:
        features["has_target_symbol"] = 1.0
    node_kind = candidate.get("node_kind")
    if node_kind:
        features[f"node_kind:{node_kind}"] = 1.0
    if isinstance(params, dict):
        _add_param_features(features, action, params)

    if isinstance(hints, list):
        for hint in hints:
            if isinstance(hint, dict):
                _merge_hint_record_features(features, candidate, action, hint)
    return features


def _add_param_features(features: dict[str, float], action: str, params: Mapping[str, object]) -> None:
    for key, value in sorted(params.items()):
        normalized = _normalize_value(value)
        features[f"param:{key}"] = 1.0
        features[f"action_param:{action}:{key}"] = 1.0
        features[f"param_type:{key}:{type(value).__name__}"] = 1.0
        if normalized in _SYMBOLIC_PARAM_VALUES:
            features[f"param_symbol:{key}={normalized}"] = 1.0
            features[f"action_param_symbol:{action}:{key}={normalized}"] = 1.0

    original = params.get("from")
    replacement = params.get("to")
    if _is_plain_number(original) and _is_plain_number(replacement):
        delta = float(replacement) - float(original)
        if delta > 0:
            features["numeric_param_delta:increase"] = 1.0
        elif delta < 0:
            features["numeric_param_delta:decrease"] = 1.0
        else:
            features["numeric_param_delta:same"] = 1.0
        features[f"action_numeric_param_delta:{action}"] = 1.0


def _is_plain_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _merge_hint_features(
    features: dict[str, float],
    candidate: CandidateLike,
    action: str,
    hint: object,
) -> None:
    exception_type = getattr(hint, "exception_type", None)
    if exception_type:
        features[f"hint_exception:{exception_type}"] = 1.0
        features[f"action_hint_exception:{action}:{exception_type}"] = 1.0
    assertions = getattr(hint, "assertions", [])
    if assertions:
        features["hint_has_assertion"] = 1.0
        for assertion in assertions:
            operator = getattr(assertion, "operator", None)
            if operator:
                features[f"hint_assert_operator:{operator}"] = 1.0
    if candidate.action.target.symbol and candidate.action.target.symbol in getattr(hint, "function_names", set()):
        features["hint_symbol_match"] = 1.0
        features[f"action_hint_symbol_match:{action}"] = 1.0
    if candidate.file_path in getattr(hint, "source_files", set()):
        features["hint_file_match"] = 1.0
        features[f"action_hint_file_match:{action}"] = 1.0
    missing_keys = getattr(hint, "missing_keys", set())
    if missing_keys:
        features["hint_has_missing_key"] = 1.0
        for key in missing_keys:
            features[f"hint_missing_key:{key}"] = 1.0
            features[f"action_hint_missing_key:{action}:{key}"] = 1.0
        params = dict(candidate.action.params)
        original = params.get("from")
        replacement = params.get("to")
        if isinstance(original, str) and original in missing_keys:
            features["hint_missing_key_matches_from"] = 1.0
            features[f"action_hint_missing_key_matches_from:{action}"] = 1.0
        if isinstance(replacement, str) and any(key in replacement for key in missing_keys):
            features["hint_missing_key_in_to"] = 1.0
            features[f"action_hint_missing_key_in_to:{action}"] = 1.0


def _merge_hint_record_features(
    features: dict[str, float],
    candidate: dict[str, object],
    action: str,
    hint: dict[str, object],
) -> None:
    exception_type = hint.get("exception_type")
    if exception_type:
        features[f"hint_exception:{exception_type}"] = 1.0
        features[f"action_hint_exception:{action}:{exception_type}"] = 1.0
    assertions = hint.get("assertions", [])
    if assertions:
        features["hint_has_assertion"] = 1.0
        for assertion in assertions:
            if isinstance(assertion, dict) and assertion.get("operator"):
                features[f"hint_assert_operator:{assertion['operator']}"] = 1.0
    symbol = candidate.get("symbol")
    if symbol and symbol in set(hint.get("function_names", [])):
        features["hint_symbol_match"] = 1.0
        features[f"action_hint_symbol_match:{action}"] = 1.0
    if candidate.get("file_path") in set(hint.get("source_files", [])):
        features["hint_file_match"] = 1.0
        features[f"action_hint_file_match:{action}"] = 1.0
    missing_keys = set(hint.get("missing_keys", []))
    if missing_keys:
        features["hint_has_missing_key"] = 1.0
        for key in missing_keys:
            features[f"hint_missing_key:{key}"] = 1.0
            features[f"action_hint_missing_key:{action}:{key}"] = 1.0
        params = candidate.get("params", {})
        if isinstance(params, dict):
            original = params.get("from")
            replacement = params.get("to")
            if isinstance(original, str) and original in missing_keys:
                features["hint_missing_key_matches_from"] = 1.0
                features[f"action_hint_missing_key_matches_from:{action}"] = 1.0
            if isinstance(replacement, str) and any(key in replacement for key in missing_keys):
                features["hint_missing_key_in_to"] = 1.0
                features[f"action_hint_missing_key_in_to:{action}"] = 1.0


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


def _normalize_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return default
