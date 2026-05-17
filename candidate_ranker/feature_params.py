"""Parameter, locality, and target-context features."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .constants import _SYMBOLIC_PARAM_VALUES
from .feature_hints import _hint_function_name_set
from .values import _int_value, _normalize_value


_MISSING = object()


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


def _add_dict_value_assertion_delta_features(
    features: dict[str, float],
    *,
    action: str,
    params: Mapping[str, object],
    hints: list[object] | tuple[object, ...],
) -> None:
    if action != "change_dict_value":
        return

    match = _scalar_assertion_value_delta_match(params, hints)
    if match == "actual_to_expected":
        features["dict_value_scalar_assertion_delta_matches"] = 1.0
        features[f"action_dict_value_scalar_assertion_delta_matches:{action}"] = 1.0
    elif match == "actual_only":
        features["dict_value_scalar_assertion_delta_from_matches_actual_only"] = 1.0
        features[
            f"action_dict_value_scalar_assertion_delta_from_matches_actual_only:{action}"
        ] = 1.0
    elif match == "expected_only":
        features["dict_value_scalar_assertion_delta_to_matches_expected_only"] = 1.0
        features[
            f"action_dict_value_scalar_assertion_delta_to_matches_expected_only:{action}"
        ] = 1.0


def _add_import_locality_features(
    features: dict[str, float],
    action: str,
    file_path: str,
    params: Mapping[str, object],
) -> None:
    if action != "add_import":
        return
    module = params.get("module")
    if not isinstance(module, str) or not module:
        return

    file_module_parts = _module_parts_from_file_path(file_path)
    import_parts = tuple(part for part in module.split(".") if part)
    if not file_module_parts or not import_parts:
        return

    target_package = file_module_parts[:-1]
    import_package = import_parts[:-1]
    if not target_package:
        return

    prefix = _common_prefix_len(target_package, import_package)
    if prefix:
        features["import_module_target_package_overlap"] = prefix / len(target_package)
        features["action_import_module_target_package_overlap:add_import"] = features[
            "import_module_target_package_overlap"
        ]
    if target_package == import_package:
        features["import_module_same_target_package"] = 1.0
        features["action_import_module_same_target_package:add_import"] = 1.0
    elif prefix:
        features["import_module_shares_target_package_prefix"] = 1.0
        features["action_import_module_shares_target_package_prefix:add_import"] = 1.0


def _add_edit_metadata_features(
    features: dict[str, float],
    action: str,
    *,
    diff_changed_lines: int,
    edit_line_span: int,
    edit_replacement_lines: int,
    edit_line_delta: int,
    edit_target_line_distance: int,
    edit_within_target_span: bool | None,
    edit_is_single_line: bool | None,
) -> None:
    if diff_changed_lines > 0:
        bucket = _line_count_bucket(diff_changed_lines)
        features[f"diff_changed_lines:{bucket}"] = 1.0
        features[f"action_diff_changed_lines:{action}:{bucket}"] = 1.0
        features["diff_changed_lines_scaled"] = min(diff_changed_lines, 20) / 20.0
        features[f"action_diff_changed_lines_scaled:{action}"] = features[
            "diff_changed_lines_scaled"
        ]

    if edit_line_span > 0:
        bucket = _line_count_bucket(edit_line_span)
        features[f"edit_line_span:{bucket}"] = 1.0
        features[f"action_edit_line_span:{action}:{bucket}"] = 1.0

    if edit_replacement_lines >= 0:
        bucket = _line_count_bucket(edit_replacement_lines)
        features[f"edit_replacement_lines:{bucket}"] = 1.0
        features[f"action_edit_replacement_lines:{action}:{bucket}"] = 1.0

    if edit_line_delta > 0:
        features["edit_line_delta:increase"] = 1.0
        features[f"action_edit_line_delta:{action}:increase"] = 1.0
    elif edit_line_delta < 0:
        features["edit_line_delta:decrease"] = 1.0
        features[f"action_edit_line_delta:{action}:decrease"] = 1.0
    else:
        features["edit_line_delta:same"] = 1.0
        features[f"action_edit_line_delta:{action}:same"] = 1.0

    if edit_target_line_distance >= 0:
        bucket = _distance_bucket(edit_target_line_distance)
        features[f"edit_target_line_distance:{bucket}"] = 1.0
        features[f"action_edit_target_line_distance:{action}:{bucket}"] = 1.0

    if edit_within_target_span is True:
        features["edit_within_target_span"] = 1.0
        features[f"action_edit_within_target_span:{action}"] = 1.0
    elif edit_within_target_span is False:
        features["edit_outside_target_span"] = 1.0
        features[f"action_edit_outside_target_span:{action}"] = 1.0

    if edit_is_single_line is True:
        features["edit_is_single_line"] = 1.0
        features[f"action_edit_is_single_line:{action}"] = 1.0
    elif edit_is_single_line is False:
        features["edit_is_multi_line"] = 1.0
        features[f"action_edit_is_multi_line:{action}"] = 1.0


def _add_target_context_features(
    features: dict[str, float],
    *,
    action: str,
    params: Mapping[str, object],
    target_context: object,
    hints: list[object] | tuple[object, ...],
    symbol: object,
) -> None:
    if not isinstance(target_context, Mapping):
        return

    role = target_context.get("role")
    if isinstance(role, str) and role:
        features[f"target_role:{role}"] = 1.0
        features[f"action_target_role:{action}:{role}"] = 1.0

    caller_count = _int_value(target_context.get("caller_count"), default=0)
    if caller_count > 0:
        bucket = _count_bucket(caller_count)
        features[f"target_caller_count:{bucket}"] = 1.0
        features[f"action_target_caller_count:{action}:{bucket}"] = 1.0

    callee_count = _int_value(target_context.get("callee_count"), default=0)
    if callee_count > 0:
        bucket = _count_bucket(callee_count)
        features[f"target_callee_count:{bucket}"] = 1.0
        features[f"action_target_callee_count:{action}:{bucket}"] = 1.0

    if target_context.get("subscript_write_to_returned_mapping") is True:
        features["subscript_write_to_returned_mapping"] = 1.0
        features[f"action_subscript_write_to_returned_mapping:{action}"] = 1.0

    returned_mapping_key_count = _int_value(
        target_context.get("returned_mapping_key_count"),
        default=0,
    )
    if returned_mapping_key_count > 0:
        bucket = _count_bucket(returned_mapping_key_count)
        features[f"returned_mapping_key_count:{bucket}"] = 1.0
        features[f"action_returned_mapping_key_count:{action}:{bucket}"] = 1.0

    if target_context.get("subscript_from_matches_returned_mapping_key") is True:
        features["subscript_from_matches_returned_mapping_key"] = 1.0
        features[f"action_subscript_from_matches_returned_mapping_key:{action}"] = 1.0

    if target_context.get("subscript_to_matches_returned_mapping_key") is True:
        features["subscript_to_matches_returned_mapping_key"] = 1.0
        features[f"action_subscript_to_matches_returned_mapping_key:{action}"] = 1.0

    _add_same_mapping_asserted_key_features(
        features,
        action=action,
        params=params,
        target_context=target_context,
        hints=hints,
    )
    _add_swap_call_role_features(
        features,
        action=action,
        target_context=target_context,
    )
    _add_membership_predicate_features(
        features,
        action=action,
        target_context=target_context,
    )

    hint_names = _hint_function_name_set(hints)
    distance = _hint_target_distance(
        symbol=symbol,
        target_context=target_context,
        hint_names=hint_names,
    )
    if distance is None:
        return

    bucket = _distance_bucket(distance)
    features["hint_call_graph_reaches_target"] = 1.0
    features[f"hint_call_graph_distance:{bucket}"] = 1.0
    features[f"action_hint_call_graph_distance:{action}:{bucket}"] = 1.0
    features["hint_call_graph_closeness"] = 1.0 / (1.0 + distance)
    features[f"action_hint_call_graph_closeness:{action}"] = features[
        "hint_call_graph_closeness"
    ]
    if distance == 0:
        features["target_is_hinted_symbol"] = 1.0
        features[f"action_target_is_hinted_symbol:{action}"] = 1.0
    else:
        features["target_is_downstream_of_hint"] = 1.0
        features[f"action_target_is_downstream_of_hint:{action}"] = 1.0


def _hint_target_distance(
    *,
    symbol: object,
    target_context: Mapping[str, object],
    hint_names: set[str],
) -> int | None:
    if not hint_names:
        return None

    distances: list[int] = []
    if isinstance(symbol, str) and symbol in hint_names:
        distances.append(0)

    qualified = target_context.get("qualified_symbol")
    if isinstance(qualified, str) and qualified.rsplit(".", maxsplit=1)[-1] in hint_names:
        distances.append(0)

    upstream_callers = target_context.get("upstream_callers", [])
    if isinstance(upstream_callers, list):
        for caller in upstream_callers:
            if not isinstance(caller, Mapping):
                continue
            caller_symbol = caller.get("symbol")
            distance = _int_value(caller.get("distance"), default=0)
            if isinstance(caller_symbol, str) and caller_symbol in hint_names and distance > 0:
                distances.append(distance)

    if not distances:
        return None
    return min(distances)


def _add_same_mapping_asserted_key_features(
    features: dict[str, float],
    *,
    action: str,
    params: Mapping[str, object],
    target_context: Mapping[str, object],
    hints: list[object] | tuple[object, ...],
) -> None:
    asserted_keys = _asserted_mapping_key_set(hints)
    if not asserted_keys:
        return
    mapping_keys = _string_set(target_context.get("dict_literal_keys"))
    if not mapping_keys:
        return

    matched_keys = asserted_keys & mapping_keys
    if not matched_keys:
        return

    features["same_mapping_has_asserted_key"] = 1.0
    features[f"action_same_mapping_has_asserted_key:{action}"] = 1.0

    value_key = target_context.get("dict_value_key")
    if (
        action == "change_dict_value"
        and isinstance(value_key, str)
        and value_key in matched_keys
        and target_context.get("dict_value_key_in_same_mapping") is True
    ):
        features["same_mapping_asserted_key_value_changed"] = 1.0
        features[f"action_same_mapping_asserted_key_value_changed:{action}"] = 1.0
        if _matches_assertion_value_delta(params, hints):
            features["same_mapping_asserted_key_value_matches_assertion_delta"] = 1.0
            features[
                f"action_same_mapping_asserted_key_value_matches_assertion_delta:{action}"
            ] = 1.0
        return

    original_key = target_context.get("dict_key_from")
    replacement_key = target_context.get("dict_key_to")
    if (
        action == "change_dict_key"
        and isinstance(original_key, str)
        and original_key in matched_keys
        and target_context.get("dict_key_from_in_same_mapping") is True
        and replacement_key != original_key
    ):
        features["same_mapping_asserted_key_renamed_or_removed"] = 1.0
        features[f"action_same_mapping_asserted_key_renamed_or_removed:{action}"] = 1.0
        return

    if (
        action == "change_dict_key"
        and isinstance(replacement_key, str)
        and replacement_key in asserted_keys
        and replacement_key not in mapping_keys
    ):
        features["same_mapping_asserted_key_created"] = 1.0
        features[f"action_same_mapping_asserted_key_created:{action}"] = 1.0


def _add_swap_call_role_features(
    features: dict[str, float],
    *,
    action: str,
    target_context: Mapping[str, object],
) -> None:
    before = target_context.get("swap_call_name_alignment_before")
    after = target_context.get("swap_call_name_alignment_after")
    if isinstance(before, str) and before:
        features[f"swap_call_name_alignment_before:{before}"] = 1.0
        features[f"action_swap_call_name_alignment_before:{action}:{before}"] = 1.0
    if isinstance(after, str) and after:
        features[f"swap_call_name_alignment_after:{after}"] = 1.0
        features[f"action_swap_call_name_alignment_after:{action}:{after}"] = 1.0

    if target_context.get("swap_call_preserves_name_alignment") is True:
        features["swap_call_preserves_name_alignment"] = 1.0
        features[f"action_swap_call_preserves_name_alignment:{action}"] = 1.0
    if target_context.get("swap_call_breaks_name_alignment") is True:
        features["swap_call_breaks_name_alignment"] = 1.0
        features[f"action_swap_call_breaks_name_alignment:{action}"] = 1.0
    if target_context.get("swap_call_repairs_name_alignment") is True:
        features["swap_call_repairs_name_alignment"] = 1.0
        features[f"action_swap_call_repairs_name_alignment:{action}"] = 1.0

    if target_context.get("swap_call_mapping_get_key_default_swapped") is True:
        features["swap_call_mapping_get_key_default_swapped"] = 1.0
        features[f"action_swap_call_mapping_get_key_default_swapped:{action}"] = 1.0

    method = target_context.get("swap_call_method")
    if isinstance(method, str) and method == "get":
        features["swap_call_method:get"] = 1.0
        features[f"action_swap_call_method:{action}:get"] = 1.0

    left_role = target_context.get("swap_call_left_role")
    right_role = target_context.get("swap_call_right_role")
    if isinstance(left_role, str) and isinstance(right_role, str):
        features[f"swap_call_role_pair:{left_role}->{right_role}"] = 1.0
        features[f"action_swap_call_role_pair:{action}:{left_role}->{right_role}"] = 1.0

    left_kind = target_context.get("swap_call_left_arg_kind")
    right_kind = target_context.get("swap_call_right_arg_kind")
    if isinstance(left_kind, str):
        features[f"swap_call_left_arg_kind:{left_kind}"] = 1.0
    if isinstance(right_kind, str):
        features[f"swap_call_right_arg_kind:{right_kind}"] = 1.0


def _add_membership_predicate_features(
    features: dict[str, float],
    *,
    action: str,
    target_context: Mapping[str, object],
) -> None:
    if target_context.get("membership_predicate") is not True:
        return

    features["membership_predicate"] = 1.0
    features[f"action_membership_predicate:{action}"] = 1.0

    operator = target_context.get("membership_predicate_operator")
    if isinstance(operator, str) and operator:
        features[f"membership_predicate_operator:{operator}"] = 1.0
        features[f"action_membership_predicate_operator:{action}:{operator}"] = 1.0

    needle_kind = target_context.get("membership_predicate_needle_kind")
    if isinstance(needle_kind, str) and needle_kind:
        features[f"membership_predicate_needle_kind:{needle_kind}"] = 1.0
        features[f"action_membership_predicate_needle_kind:{action}:{needle_kind}"] = 1.0

    container_kind = target_context.get("membership_predicate_container_kind")
    if isinstance(container_kind, str) and container_kind:
        features[f"membership_predicate_container_kind:{container_kind}"] = 1.0
        features[
            f"action_membership_predicate_container_kind:{action}:{container_kind}"
        ] = 1.0

    literal_role = target_context.get("membership_predicate_literal_role")
    if isinstance(literal_role, str) and literal_role:
        features[f"membership_predicate_literal_role:{literal_role}"] = 1.0
        features[f"action_membership_predicate_literal_role:{action}:{literal_role}"] = 1.0

    if target_context.get("membership_predicate_in_branch_test") is True:
        features["membership_predicate_in_branch_test"] = 1.0
        features[f"action_membership_predicate_in_branch_test:{action}"] = 1.0
    if target_context.get("membership_predicate_operator_changed") is True:
        features["membership_predicate_operator_changed"] = 1.0
        features[f"action_membership_predicate_operator_changed:{action}"] = 1.0
    if target_context.get("membership_predicate_operator_flipped") is True:
        features["membership_predicate_operator_flipped"] = 1.0
        features[f"action_membership_predicate_operator_flipped:{action}"] = 1.0
    if target_context.get("membership_predicate_literal_changed") is True:
        features["membership_predicate_literal_changed"] = 1.0
        features[f"action_membership_predicate_literal_changed:{action}"] = 1.0
    if target_context.get("membership_predicate_needle_changed") is True:
        features["membership_predicate_needle_changed"] = 1.0
        features[f"action_membership_predicate_needle_changed:{action}"] = 1.0


def _asserted_mapping_key_set(hints: list[object] | tuple[object, ...]) -> set[str]:
    keys: set[str] = set()
    for hint in hints:
        if isinstance(hint, Mapping):
            raw_keys = hint.get("asserted_mapping_keys", [])
        else:
            raw_keys = getattr(hint, "asserted_mapping_keys", set())
        keys.update(_string_set(raw_keys))
    return keys


def _matches_assertion_value_delta(
    params: Mapping[str, object],
    hints: list[object] | tuple[object, ...],
) -> bool:
    original = params.get("from", _MISSING)
    replacement = params.get("to", _MISSING)
    if original is _MISSING or replacement is _MISSING:
        return False
    for hint in hints:
        assertions = (
            hint.get("assertions", [])
            if isinstance(hint, Mapping)
            else getattr(hint, "assertions", [])
        )
        if not isinstance(assertions, list):
            continue
        for assertion in assertions:
            if _assertion_operator(assertion) not in {"==", "is"}:
                continue
            actual = _assertion_value(assertion, "actual")
            expected = _assertion_value(assertion, "expected")
            if actual is _MISSING or expected is _MISSING:
                continue
            if (
                _exact_value_equal(original, actual)
                and _exact_value_equal(replacement, expected)
            ):
                return True
    return False


def _scalar_assertion_value_delta_match(
    params: Mapping[str, object],
    hints: list[object] | tuple[object, ...],
) -> str | None:
    original = params.get("from", _MISSING)
    replacement = params.get("to", _MISSING)
    if original is _MISSING or replacement is _MISSING:
        return None

    found_actual_only = False
    found_expected_only = False
    for hint in hints:
        assertions = (
            hint.get("assertions", [])
            if isinstance(hint, Mapping)
            else getattr(hint, "assertions", [])
        )
        if not isinstance(assertions, list):
            continue
        for assertion in assertions:
            if _assertion_operator(assertion) not in {"==", "is"}:
                continue
            actual = _assertion_value(assertion, "actual")
            expected = _assertion_value(assertion, "expected")
            if (
                actual is _MISSING
                or expected is _MISSING
                or not _is_scalar_assertion_value(actual)
                or not _is_scalar_assertion_value(expected)
            ):
                continue
            actual_matches = _exact_value_equal(original, actual)
            expected_matches = _exact_value_equal(replacement, expected)
            if actual_matches and expected_matches:
                return "actual_to_expected"
            found_actual_only = found_actual_only or actual_matches
            found_expected_only = found_expected_only or expected_matches

    if found_actual_only:
        return "actual_only"
    if found_expected_only:
        return "expected_only"
    return None


def _assertion_operator(assertion: object) -> object:
    if isinstance(assertion, Mapping):
        return assertion.get("operator")
    return getattr(assertion, "operator", None)


def _assertion_value(assertion: object, key: str) -> object:
    if isinstance(assertion, Mapping):
        return assertion.get(key, _MISSING)
    return getattr(assertion, key, _MISSING)


def _exact_value_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


def _is_scalar_assertion_value(value: object) -> bool:
    return value is None or isinstance(value, (str, bool, int, float))


def _string_set(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, (set, list, tuple)):
        return {item for item in value if isinstance(item, str)}
    return set()


def _count_bucket(count: int) -> str:
    if count <= 1:
        return "1"
    if count <= 3:
        return "2_3"
    return "4_plus"


def _line_count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    return _count_bucket(count)


def _distance_bucket(distance: int) -> str:
    if distance <= 0:
        return "0"
    if distance == 1:
        return "1"
    if distance == 2:
        return "2"
    return "3_plus"


def _module_parts_from_file_path(file_path: str) -> tuple[str, ...]:
    path = Path(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return tuple(parts)


def _common_prefix_len(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    count = 0
    for left_part, right_part in zip(left, right, strict=False):
        if left_part != right_part:
            break
        count += 1
    return count


def _is_plain_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
