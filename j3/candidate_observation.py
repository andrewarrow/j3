"""Normalize candidate-after and AST-delta observations for shadow scoring."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping


def candidate_change_observation(record: Mapping[str, object]) -> dict[str, object]:
    """Return flat change signals from candidate outcome or attempt records."""

    diff_summaries = list(_iter_diff_summaries(record))
    ast_deltas = list(_iter_ast_deltas(record))
    added_features: Counter[str] = Counter()
    removed_features: Counter[str] = Counter()
    added_count = 0
    removed_count = 0
    net_count = 0
    parse_values: list[bool] = []

    for delta in ast_deltas:
        parse_ok = delta.get("ast_parse_ok")
        if isinstance(parse_ok, bool):
            parse_values.append(parse_ok)
        added_count += _int_value(delta.get("ast_delta_added_count"), default=0)
        removed_count += _int_value(delta.get("ast_delta_removed_count"), default=0)
        net_count += _int_value(delta.get("ast_delta_net_count"), default=0)
        added_features.update(_numeric_counter(delta.get("ast_delta_added_features")))
        removed_features.update(_numeric_counter(delta.get("ast_delta_removed_features")))

    observation: dict[str, object] = {
        "candidate_after_available": _candidate_after_available(record),
    }
    if diff_summaries:
        added = sum(_int_value(summary.get("added_line_count"), default=0) for summary in diff_summaries)
        removed = sum(_int_value(summary.get("removed_line_count"), default=0) for summary in diff_summaries)
        changed = sum(
            _int_value(
                summary.get("changed_line_count"),
                default=_int_value(summary.get("changed"), default=0),
            )
            for summary in diff_summaries
        )
        if changed <= 0:
            changed = added + removed
        observation.update(
            {
                "diff_added_lines": added,
                "diff_removed_lines": removed,
                "diff_changed_lines": changed,
            }
        )
    if ast_deltas:
        observation.update(
            {
                "ast_parse_ok": all(parse_values) if parse_values else True,
                "ast_delta_added_count": added_count,
                "ast_delta_removed_count": removed_count,
                "ast_delta_net_count": net_count,
                "ast_delta_added_features": dict(sorted(added_features.items())),
                "ast_delta_removed_features": dict(sorted(removed_features.items())),
            }
        )
    return observation


def _candidate_after_available(record: Mapping[str, object]) -> bool:
    direct = record.get("candidate_after")
    if isinstance(direct, Mapping):
        if direct.get("available") is True:
            return True
        if any(key in direct for key in ("diff", "diff_summary", "ast_delta")):
            return True
        for value in direct.values():
            if isinstance(value, Mapping) and _candidate_after_available(value):
                return True
    for key in ("source_materialization", "test_materialization"):
        value = record.get(key)
        if isinstance(value, Mapping) and _candidate_after_available(value):
            return True
    return False


def _iter_diff_summaries(record: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    candidate_diff = record.get("candidate_diff")
    if isinstance(candidate_diff, Mapping):
        summary = candidate_diff.get("diff_summary")
        if isinstance(summary, Mapping):
            return (summary,)
    summaries: list[Mapping[str, object]] = []
    _collect_diff_summaries(record, summaries)
    return tuple(summaries)


def _collect_diff_summaries(value: object, summaries: list[Mapping[str, object]]) -> None:
    if not isinstance(value, Mapping):
        return
    summary = value.get("diff_summary")
    if isinstance(summary, Mapping):
        summaries.append(summary)
    candidate_diff = value.get("candidate_diff")
    if isinstance(candidate_diff, Mapping):
        _collect_diff_summaries(candidate_diff, summaries)
    candidate_after = value.get("candidate_after")
    if isinstance(candidate_after, Mapping):
        _collect_diff_summaries(candidate_after, summaries)
    for key in ("source_materialization", "test_materialization", "source_file", "test_file"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            _collect_diff_summaries(nested, summaries)


def _iter_ast_deltas(record: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    deltas: list[Mapping[str, object]] = []
    _collect_ast_deltas(record, deltas)
    return tuple(deltas)


def _collect_ast_deltas(value: object, deltas: list[Mapping[str, object]]) -> None:
    if not isinstance(value, Mapping):
        return
    ast_delta = value.get("ast_delta")
    if isinstance(ast_delta, Mapping):
        deltas.append(ast_delta)
    if "ast_parse_ok" in value and (
        "ast_delta_added_features" in value or "ast_delta_removed_features" in value
    ):
        deltas.append(value)
    candidate_after = value.get("candidate_after")
    if isinstance(candidate_after, Mapping):
        _collect_ast_deltas(candidate_after, deltas)
    for key in ("source_materialization", "test_materialization", "source_file", "test_file"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            _collect_ast_deltas(nested, deltas)


def _numeric_counter(value: object) -> Counter[str]:
    counter: Counter[str] = Counter()
    if not isinstance(value, Mapping):
        return counter
    for key, count in value.items():
        numeric = _int_value(count, default=0)
        if numeric > 0:
            counter[str(key)] += numeric
    return counter


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
