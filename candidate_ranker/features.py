"""Feature extraction for live candidates and persisted outcome records."""

from __future__ import annotations

from j3.ast_delta import ast_delta_feature_map, python_ast_delta_metadata
from j3.candidate_observation import candidate_change_observation

from .feature_hints import (
    _add_hint_token_overlap_features,
    _candidate_tokens,
    _hint_record_tokens,
    _hint_tokens,
    _merge_hint_features,
    _merge_hint_record_features,
)
from .feature_params import (
    _add_dict_value_assertion_delta_features,
    _add_edit_metadata_features,
    _add_import_locality_features,
    _add_literal_dict_key_assertion_delta_features,
    _add_param_features,
    _add_target_context_features,
)
from .feature_relations import _add_candidate_relation_features
from .types import CandidateLike
from .values import _float_value, _int_value


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
    edit_metadata = _live_candidate_edit_metadata(candidate)
    if edit_metadata is not None:
        _add_edit_metadata_features(features, action, **edit_metadata)
    ast_metadata = python_ast_delta_metadata(candidate.original_source, candidate.patched_source)
    features.update(ast_delta_feature_map(ast_metadata))

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
    _add_dict_value_assertion_delta_features(
        features,
        action=action,
        params=params,
        hints=hints,
    )
    _add_literal_dict_key_assertion_delta_features(
        features,
        action=action,
        params=params,
        hints=hints,
        ast_metadata=ast_metadata,
    )
    _add_target_context_features(
        features,
        action=action,
        params=params,
        target_context=getattr(candidate, "target_context", {}),
        hints=hints,
        symbol=candidate.action.target.symbol,
    )

    return features


def _candidate_record_features(candidate: dict[str, object], hints: object) -> dict[str, float]:
    action = str(candidate.get("action", ""))
    params = candidate.get("params", {})
    observation = candidate_change_observation(candidate)
    features: dict[str, float] = {
        "bias": 1.0,
        f"action:{action}": 1.0,
        "failure_hint_score": _float_value(candidate.get("failure_hint_score")) / 100.0,
    }
    if observation.get("candidate_after_available") is True:
        features["candidate_after_available"] = 1.0
        features[f"action_candidate_after_available:{action}"] = 1.0
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
    edit_metadata = _record_edit_metadata(candidate, observation=observation)
    if edit_metadata is not None:
        _add_edit_metadata_features(features, action, **edit_metadata)
    _add_candidate_relation_features(features, action, candidate)
    features.update(ast_delta_feature_map({**candidate, **observation}))

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
            _add_dict_value_assertion_delta_features(
                features,
                action=action,
                params=params,
                hints=hints,
            )
            _add_literal_dict_key_assertion_delta_features(
                features,
                action=action,
                params=params,
                hints=hints,
                ast_metadata=candidate,
            )
    _add_target_context_features(
        features,
        action=action,
        params=params if isinstance(params, dict) else {},
        target_context=candidate.get("target_context", {}),
        hints=hints if isinstance(hints, list) else [],
        symbol=candidate.get("symbol"),
    )
    return features


def _live_candidate_edit_metadata(candidate: CandidateLike) -> dict[str, object] | None:
    edit = getattr(candidate, "edit", None)
    action = getattr(candidate, "action", None)
    target = getattr(action, "target", None)
    if edit is None or target is None:
        return None

    replacement = getattr(edit, "replacement", "")
    replacement_lines = _replacement_line_count(replacement if isinstance(replacement, str) else "")
    edit_line_span = max(
        1,
        _int_value(getattr(edit, "end_line", 0), default=0)
        - _int_value(getattr(edit, "start_line", 0), default=0)
        + 1,
    )
    diff_changed_lines = 0
    diff = getattr(candidate, "diff", None)
    if callable(diff):
        added, removed = _diff_line_counts(str(diff()))
        diff_changed_lines = added + removed

    return {
        "diff_changed_lines": diff_changed_lines,
        "edit_line_span": edit_line_span,
        "edit_replacement_lines": replacement_lines,
        "edit_line_delta": replacement_lines - edit_line_span,
        "edit_target_line_distance": min(
            abs(
                _int_value(getattr(edit, "start_line", 0), default=0)
                - _int_value(getattr(target, "start_line", 0), default=0)
            ),
            abs(
                _int_value(getattr(edit, "end_line", 0), default=0)
                - _int_value(getattr(target, "end_line", 0), default=0)
            ),
        ),
        "edit_within_target_span": (
            _int_value(getattr(target, "start_line", 0), default=0)
            <= _int_value(getattr(edit, "start_line", 0), default=0)
            and _int_value(getattr(edit, "end_line", 0), default=0)
            <= _int_value(getattr(target, "end_line", 0), default=0)
        ),
        "edit_is_single_line": (
            _int_value(getattr(edit, "start_line", 0), default=0)
            == _int_value(getattr(edit, "end_line", 0), default=0)
            and replacement_lines <= 1
        ),
    }


def _record_edit_metadata(
    candidate: dict[str, object],
    *,
    observation: dict[str, object],
) -> dict[str, object] | None:
    has_diff = "diff_changed_lines" in candidate or "diff_changed_lines" in observation
    has_edit = "edit_line_span" in candidate
    if not has_diff and not has_edit:
        return None
    return {
        "diff_changed_lines": _int_value(
            observation.get("diff_changed_lines", candidate.get("diff_changed_lines")),
            default=0,
        ),
        "edit_line_span": _optional_int_value(candidate.get("edit_line_span")),
        "edit_replacement_lines": _int_value(
            candidate.get("edit_replacement_lines"),
            default=-1,
        ),
        "edit_line_delta": _optional_int_value(candidate.get("edit_line_delta")),
        "edit_target_line_distance": _optional_int_value(candidate.get("edit_target_line_distance")),
        "edit_within_target_span": _bool_value(candidate.get("edit_within_target_span")),
        "edit_is_single_line": _bool_value(candidate.get("edit_is_single_line")),
    }


def _optional_int_value(value: object) -> int | None:
    if value is None:
        return None
    return _int_value(value, default=0)


def _diff_line_counts(diff_text: str) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _replacement_line_count(replacement: str) -> int:
    if not replacement:
        return 0
    return max(1, len(replacement.splitlines()))


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None
