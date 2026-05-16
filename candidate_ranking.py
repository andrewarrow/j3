"""Lightweight candidate ranker trained from eval diagnostics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol

from actions import PatchAction


RANKER_FORMAT = "j3.candidate-ranker.v1"
RANKER_FEATURE_VERSION = "candidate-diagnostics-v1"


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
    plans: int
    training_pairs: int
    features: int
    mistakes: int


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
    diagnostics_paths: list[Path],
    out_dir: Path,
    epochs: int = 8,
    learning_rate: float = 0.25,
    margin: float = 1.0,
    plan_name: str = "ranked",
) -> CandidateRankerTrainingResult:
    """Train a pairwise linear ranker from eval diagnostics JSON files."""

    if not diagnostics_paths:
        raise ValueError("at least one diagnostics path is required")
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be positive")
    if margin <= 0:
        raise ValueError("margin must be positive")

    resolved_paths = [path.expanduser().resolve() for path in diagnostics_paths]
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    plans = 0
    for path in resolved_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task in payload.get("tasks", []):
            plan = task.get(plan_name)
            if not isinstance(plan, dict):
                continue
            plan_pairs = _training_pairs_from_plan(plan)
            if plan_pairs:
                plans += 1
                pairs.extend(plan_pairs)

    if not pairs:
        raise ValueError("diagnostics did not contain solved plans with failed candidates")

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

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    ranker_path = output / "candidate-ranker.json"
    metrics_path = output / "candidate-ranker-metrics.json"
    model = {
        "format": RANKER_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": RANKER_FEATURE_VERSION,
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "plan": plan_name,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "margin": margin,
        "bias": 0.0,
        "weights": dict(sorted(weights.items())),
    }
    metrics = {
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "plan": plan_name,
        "plans": plans,
        "training_pairs": len(pairs),
        "features": len(weights),
        "mistakes": mistakes,
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
        plans=plans,
        training_pairs=len(pairs),
        features=len(weights),
        mistakes=mistakes,
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
        f"reason:{candidate.reason}": 1.0,
        "failure_hint_score": candidate.failure_hint_score / 100.0,
    }
    if candidate.model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = candidate.model_score
    if candidate.action.target.symbol:
        features[f"symbol:{candidate.action.target.symbol}"] = 1.0
    if candidate.action.target.node_kind:
        features[f"node_kind:{candidate.action.target.node_kind}"] = 1.0

    for key, value in sorted(params.items()):
        normalized = _normalize_value(value)
        features[f"param:{key}"] = 1.0
        features[f"param:{key}={normalized}"] = 1.0
        features[f"action_param:{action}:{key}={normalized}"] = 1.0

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
    for candidate in tested[:positive_index]:
        if isinstance(candidate, dict):
            pairs.append((positive_features, _candidate_record_features(candidate, hints)))
    return pairs


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
        f"reason:{candidate.get('reason', '')}": 1.0,
        "failure_hint_score": _float_value(candidate.get("failure_hint_score")) / 100.0,
    }
    model_score = candidate.get("model_score")
    if model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = _float_value(model_score)
    symbol = candidate.get("symbol")
    if symbol:
        features[f"symbol:{symbol}"] = 1.0
    for key, value in sorted(params.items()) if isinstance(params, dict) else []:
        normalized = _normalize_value(value)
        features[f"param:{key}"] = 1.0
        features[f"param:{key}={normalized}"] = 1.0
        features[f"action_param:{action}:{key}={normalized}"] = 1.0

    if isinstance(hints, list):
        for hint in hints:
            if isinstance(hint, dict):
                _merge_hint_record_features(features, candidate, action, hint)
    return features


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


def _update_weights(weights: dict[str, float], features: Mapping[str, float], scale: float) -> None:
    for name, value in features.items():
        weights[name] = weights.get(name, 0.0) + scale * value
        if abs(weights[name]) < 1e-12:
            del weights[name]


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
