"""Parameter, locality, and target-context features."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .constants import _SYMBOLIC_PARAM_VALUES
from .feature_hints import _hint_function_name_set
from .values import _int_value, _normalize_value


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
