"""Feature extraction for live candidates and persisted outcome records."""

from __future__ import annotations

from .feature_hints import (
    _add_hint_token_overlap_features,
    _candidate_tokens,
    _hint_record_tokens,
    _hint_tokens,
    _merge_hint_features,
    _merge_hint_record_features,
)
from .feature_params import (
    _add_import_locality_features,
    _add_param_features,
    _add_target_context_features,
)
from .types import CandidateLike
from .values import _float_value


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
    if candidate.failure_hint_score > 0:
        features["has_failure_hint_score"] = 1.0
        features[f"action_has_failure_hint_score:{action}"] = 1.0
    if candidate.model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = candidate.model_score
    if candidate.action.target.symbol:
        features["has_target_symbol"] = 1.0
    if candidate.action.target.node_kind:
        features[f"node_kind:{candidate.action.target.node_kind}"] = 1.0

    _add_param_features(features, action, params)
    _add_import_locality_features(features, action, candidate.file_path, params)

    for hint in hints:
        _merge_hint_features(features, candidate, action, hint)
    if hints:
        _add_hint_token_overlap_features(
            features,
            action=action,
            candidate_tokens=_candidate_tokens(
                candidate.file_path,
                candidate.action.target.symbol,
                params,
            ),
            params=params,
            hint_tokens=_hint_tokens(hints),
        )
    _add_target_context_features(
        features,
        action=action,
        target_context=getattr(candidate, "target_context", {}),
        hints=hints,
        symbol=candidate.action.target.symbol,
    )

    return features


def _candidate_record_features(candidate: dict[str, object], hints: object) -> dict[str, float]:
    action = str(candidate.get("action", ""))
    params = candidate.get("params", {})
    features: dict[str, float] = {
        "bias": 1.0,
        f"action:{action}": 1.0,
        "failure_hint_score": _float_value(candidate.get("failure_hint_score")) / 100.0,
    }
    if _float_value(candidate.get("failure_hint_score")) > 0:
        features["has_failure_hint_score"] = 1.0
        features[f"action_has_failure_hint_score:{action}"] = 1.0
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
        _add_import_locality_features(
            features,
            action,
            str(candidate.get("file_path", "")),
            params,
        )

    if isinstance(hints, list):
        for hint in hints:
            if isinstance(hint, dict):
                _merge_hint_record_features(features, candidate, action, hint)
        if hints and isinstance(params, dict):
            _add_hint_token_overlap_features(
                features,
                action=action,
                candidate_tokens=_candidate_tokens(
                    str(candidate.get("file_path", "")),
                    candidate.get("symbol"),
                    params,
                ),
                params=params,
                hint_tokens=_hint_record_tokens(hints),
            )
    _add_target_context_features(
        features,
        action=action,
        target_context=candidate.get("target_context", {}),
        hints=hints if isinstance(hints, list) else [],
        symbol=candidate.get("symbol"),
    )
    return features
