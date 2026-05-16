"""Failure-hint feature extraction for candidate ranking."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .constants import TOKEN_RE
from .types import CandidateLike


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
    _merge_name_set_features(
        features,
        action,
        dict(candidate.action.params),
        name_set=getattr(hint, "missing_names", set()),
        prefix="missing_name",
    )
    _merge_name_set_features(
        features,
        action,
        dict(candidate.action.params),
        name_set=getattr(hint, "missing_attributes", set()),
        prefix="missing_attribute",
    )
    _merge_name_set_features(
        features,
        action,
        dict(candidate.action.params),
        name_set=getattr(hint, "type_error_names", set()),
        prefix="type_error_name",
    )
    missing_keys = getattr(hint, "missing_keys", set())
    if missing_keys:
        features["hint_has_missing_key"] = 1.0
        for key in missing_keys:
            features[f"hint_missing_key:{key}"] = 1.0
            features[f"action_hint_missing_key:{action}:{key}"] = 1.0
        params = dict(candidate.action.params)
        original = params.get("from")
        replacement = params.get("to")
        key_param = params.get("key")
        if isinstance(original, str) and original in missing_keys:
            features["hint_missing_key_matches_from"] = 1.0
            features[f"action_hint_missing_key_matches_from:{action}"] = 1.0
        if isinstance(replacement, str) and any(key in replacement for key in missing_keys):
            features["hint_missing_key_in_to"] = 1.0
            features[f"action_hint_missing_key_in_to:{action}"] = 1.0
        if isinstance(key_param, str) and key_param in missing_keys:
            features["hint_missing_key_matches_key"] = 1.0
            features[f"action_hint_missing_key_matches_key:{action}"] = 1.0


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
    params = candidate.get("params", {})
    if isinstance(params, dict):
        _merge_name_set_features(
            features,
            action,
            params,
            name_set=set(hint.get("missing_names", [])),
            prefix="missing_name",
        )
        _merge_name_set_features(
            features,
            action,
            params,
            name_set=set(hint.get("missing_attributes", [])),
            prefix="missing_attribute",
        )
        _merge_name_set_features(
            features,
            action,
            params,
            name_set=set(hint.get("type_error_names", [])),
            prefix="type_error_name",
        )
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
            key_param = params.get("key")
            if isinstance(original, str) and original in missing_keys:
                features["hint_missing_key_matches_from"] = 1.0
                features[f"action_hint_missing_key_matches_from:{action}"] = 1.0
            if isinstance(replacement, str) and any(key in replacement for key in missing_keys):
                features["hint_missing_key_in_to"] = 1.0
                features[f"action_hint_missing_key_in_to:{action}"] = 1.0
            if isinstance(key_param, str) and key_param in missing_keys:
                features["hint_missing_key_matches_key"] = 1.0
                features[f"action_hint_missing_key_matches_key:{action}"] = 1.0


def _merge_name_set_features(
    features: dict[str, float],
    action: str,
    params: Mapping[str, object],
    *,
    name_set: set[str],
    prefix: str,
) -> None:
    if not name_set:
        return
    features[f"hint_has_{prefix}"] = 1.0
    original = params.get("from")
    replacement = params.get("to")
    name = params.get("name")
    module = params.get("module")
    if isinstance(original, str) and original in name_set:
        features[f"hint_{prefix}_matches_from"] = 1.0
        features[f"action_hint_{prefix}_matches_from:{action}"] = 1.0
    if isinstance(replacement, str) and replacement in name_set:
        features[f"hint_{prefix}_matches_to"] = 1.0
        features[f"action_hint_{prefix}_matches_to:{action}"] = 1.0
    if isinstance(name, str) and name in name_set:
        features[f"hint_{prefix}_matches_import_name"] = 1.0
        features[f"action_hint_{prefix}_matches_import_name:{action}"] = 1.0
    if isinstance(module, str) and any(module == item or module.endswith(f".{item}") for item in name_set):
        features[f"hint_{prefix}_matches_module"] = 1.0
        features[f"action_hint_{prefix}_matches_module:{action}"] = 1.0


def _add_hint_token_overlap_features(
    features: dict[str, float],
    *,
    action: str,
    candidate_tokens: set[str],
    params: Mapping[str, object],
    hint_tokens: set[str],
) -> None:
    if not candidate_tokens or not hint_tokens:
        return
    overlap = candidate_tokens & hint_tokens
    if overlap:
        value = min(len(overlap), 8) / 8.0
        features["hint_candidate_token_overlap"] = value
        features[f"action_hint_candidate_token_overlap:{action}"] = value

    for key in ("from", "to", "name", "module", "key"):
        value = params.get(key)
        if not isinstance(value, str):
            continue
        param_tokens = _tokens(value)
        param_overlap = param_tokens & hint_tokens
        if param_overlap:
            feature_value = min(len(param_overlap), 6) / 6.0
            features[f"hint_param_{key}_token_overlap"] = feature_value
            features[f"action_hint_param_{key}_token_overlap:{action}"] = feature_value


def _candidate_tokens(
    file_path: str,
    symbol: object,
    params: Mapping[str, object],
) -> set[str]:
    tokens = _tokens(file_path)
    if isinstance(symbol, str):
        tokens |= _tokens(symbol)
    for key in ("from", "to", "name", "module", "import", "replacement", "key"):
        value = params.get(key)
        if isinstance(value, str):
            tokens |= _tokens(value)
    return tokens


def _hint_tokens(hints: list[object] | tuple[object, ...]) -> set[str]:
    tokens: set[str] = set()
    for hint in hints:
        for attr in (
            "nodeid",
            "summary",
            "exception_type",
            "function_names",
            "missing_names",
            "missing_attributes",
            "missing_modules",
            "missing_keys",
            "type_error_names",
            "expected_strings",
            "assertion_diff_lines",
            "source_files",
        ):
            tokens |= _tokens_from_hint_value(getattr(hint, attr, None))
        for location in getattr(hint, "traceback_locations", []):
            tokens |= _tokens(getattr(location, "file_path", ""))
        for diagnostic in getattr(hint, "tool_diagnostics", []):
            tokens |= _tokens(getattr(diagnostic, "file_path", ""))
            tokens |= _tokens(getattr(diagnostic, "message", ""))
    return tokens


def _hint_record_tokens(hints: list[dict[str, object]]) -> set[str]:
    tokens: set[str] = set()
    for hint in hints:
        for key in (
            "nodeid",
            "summary",
            "exception_type",
            "function_names",
            "missing_names",
            "missing_attributes",
            "missing_modules",
            "missing_keys",
            "type_error_names",
            "expected_strings",
            "assertion_diff_lines",
            "source_files",
        ):
            tokens |= _tokens_from_hint_value(hint.get(key))
        for location in hint.get("traceback_locations", []):
            if isinstance(location, dict):
                tokens |= _tokens(location.get("file_path"))
        for diagnostic in hint.get("tool_diagnostics", []):
            if isinstance(diagnostic, dict):
                tokens |= _tokens(diagnostic.get("file_path"))
                tokens |= _tokens(diagnostic.get("message"))
    return tokens


def _hint_function_name_set(hints: list[object] | tuple[object, ...]) -> set[str]:
    names: set[str] = set()
    for hint in hints:
        if isinstance(hint, Mapping):
            raw_names = hint.get("function_names", [])
        else:
            raw_names = getattr(hint, "function_names", set())
        if isinstance(raw_names, str):
            names.add(raw_names)
        elif isinstance(raw_names, (set, list, tuple)):
            names.update(name for name in raw_names if isinstance(name, str))
    return names


def _tokens_from_hint_value(value: object) -> set[str]:
    if isinstance(value, str):
        return _tokens(value)
    if isinstance(value, (set, list, tuple)):
        tokens: set[str] = set()
        for item in value:
            tokens |= _tokens_from_hint_value(item)
        return tokens
    return set()


def _tokens(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    tokens: set[str] = set()
    for match in TOKEN_RE.finditer(value):
        token = match.group(0)
        for part in re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", token).replace("_", " ").split():
            normalized = part.lower()
            if len(normalized) >= 3:
                tokens.add(normalized)
    return tokens
