"""Normalize transition scorer shadow advice with candidate outcomes."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from j3.transition_scorer_advice import TRANSITION_SCORER_ADVICE_VERSION


TRANSITION_SHADOW_OUTCOME_VERSION = "transition-shadow-outcome-v1"
TRANSITION_SHADOW_OUTCOME_SUMMARY_VERSION = "transition-shadow-outcome-summary-v1"

HOSTED_USAGE_FIELDS = (
    "hosted_llm_api_calls",
    "hosted_llm_prompt_tokens",
    "hosted_llm_completion_tokens",
    "hosted_api_tokens",
    "hosted_repo_context_bytes",
)


@dataclass(frozen=True, slots=True)
class TransitionShadowOutcomeSummary:
    """Summary of a normalized shadow outcome JSONL artifact."""

    advice_paths: list[Path]
    candidate_outcome_paths: list[Path]
    out_path: Path | None
    rows: int
    joined_rows: int
    unjoined_advice_rows: int
    unjoined_candidate_outcome_rows: int
    known_validation_rows: int
    labels: dict[str, int]
    usage: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRANSITION_SHADOW_OUTCOME_SUMMARY_VERSION,
            "advice_paths": [str(path) for path in self.advice_paths],
            "candidate_outcome_paths": [
                str(path) for path in self.candidate_outcome_paths
            ],
            "out_path": str(self.out_path) if self.out_path is not None else None,
            "rows": self.rows,
            "joined_rows": self.joined_rows,
            "unjoined_advice_rows": self.unjoined_advice_rows,
            "unjoined_candidate_outcome_rows": self.unjoined_candidate_outcome_rows,
            "known_validation_rows": self.known_validation_rows,
            "labels": dict(self.labels),
            "usage": dict(self.usage),
        }


@dataclass(frozen=True, slots=True)
class _AdviceItem:
    row: dict[str, object]
    path: Path
    line_number: int
    index: int


@dataclass(frozen=True, slots=True)
class _OutcomeItem:
    row: dict[str, object]
    path: Path
    line_number: int


@dataclass(frozen=True, slots=True)
class _OutcomeGroup:
    key: tuple[str, str, str]
    rows: list[dict[str, object]]
    path_lines: list[dict[str, object]]


def normalize_transition_shadow_outcomes(
    *,
    advice_paths: Sequence[Path],
    candidate_outcome_paths: Sequence[Path],
) -> list[dict[str, object]]:
    """Join shadow advice with candidate outcome groups into training rows."""

    advice_items = _read_advice_items(advice_paths)
    outcome_items = _read_outcome_items(candidate_outcome_paths)
    outcome_groups = _group_outcome_items(outcome_items)
    rows: list[dict[str, object]] = []
    joined_keys: set[tuple[str, str, str]] = set()

    for item in advice_items:
        key = _advice_key(item.row)
        group = outcome_groups.get(key)
        if group is not None and _key_is_joinable(key):
            join_status = "joined"
            unjoined_reason = None
            joined_keys.add(key)
            outcome_rows = group.rows
            outcome_path_lines = group.path_lines
        else:
            join_status = "unjoined_advice"
            unjoined_reason = (
                _missing_key_reason(key) or "no_candidate_outcome_group_for_key"
            )
            outcome_rows = []
            outcome_path_lines = []
        rows.append(
            _normalized_row(
                advice=item.row,
                outcome_rows=outcome_rows,
                key=key,
                join_status=join_status,
                unjoined_reason=unjoined_reason,
                source={
                    "advice": {
                        "path": str(item.path),
                        "line_number": item.line_number,
                        "row_index": item.index,
                    },
                    "candidate_outcomes": outcome_path_lines,
                },
            )
        )

    for key, group in sorted(outcome_groups.items()):
        if key in joined_keys:
            continue
        rows.append(
            _normalized_row(
                advice=None,
                outcome_rows=group.rows,
                key=key,
                join_status="unjoined_candidate_outcomes",
                unjoined_reason=(
                    _missing_key_reason(key) or "no_shadow_advice_for_key"
                ),
                source={
                    "advice": None,
                    "candidate_outcomes": group.path_lines,
                },
            )
        )

    for row in rows:
        validate_transition_shadow_outcome(row)
    return rows


def write_transition_shadow_outcomes_jsonl(
    path: Path,
    rows: Iterable[Mapping[str, object]],
) -> Path:
    """Write validated transition-shadow-outcome-v1 rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    materialized = [dict(row) for row in rows]
    for row in materialized:
        validate_transition_shadow_outcome(row)
    resolved.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in materialized),
        encoding="utf-8",
    )
    return resolved


def load_transition_shadow_outcomes(paths: Sequence[Path]) -> list[dict[str, object]]:
    """Load and validate transition-shadow-outcome-v1 JSONL rows."""

    rows: list[dict[str, object]] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"shadow outcome file does not exist: {resolved}")
        if not resolved.is_file():
            raise IsADirectoryError(f"shadow outcome path is not a file: {resolved}")
        for line_number, line in enumerate(
            resolved.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{resolved}:{line_number}: expected JSON object")
            validate_transition_shadow_outcome(row)
            rows.append(row)
    return rows


def validate_transition_shadow_outcome(row: Mapping[str, object]) -> None:
    """Validate the stable parts of one normalized shadow outcome row."""

    if row.get("schema_version") != TRANSITION_SHADOW_OUTCOME_VERSION:
        raise ValueError(f"expected {TRANSITION_SHADOW_OUTCOME_VERSION}")
    join_status = row.get("join_status")
    if join_status not in {
        "joined",
        "unjoined_advice",
        "unjoined_candidate_outcomes",
    }:
        raise ValueError("shadow outcome join_status is invalid")
    if join_status == "joined" and row.get("unjoined_reason") is not None:
        raise ValueError("joined shadow outcome must not have unjoined_reason")
    if join_status != "joined" and not isinstance(row.get("unjoined_reason"), str):
        raise ValueError("unjoined shadow outcome requires unjoined_reason")
    key = _mapping(row.get("key"))
    if not isinstance(key.get("task"), str) or not isinstance(key.get("phase"), str):
        raise ValueError("shadow outcome key requires task and phase strings")
    if key.get("repair_plan_id") is not None and not isinstance(
        key.get("repair_plan_id"), str
    ):
        raise ValueError("shadow outcome key repair_plan_id must be string or null")
    if not isinstance(row.get("candidate_ranking"), list):
        raise ValueError("shadow outcome candidate_ranking must be a list")
    labels = _mapping(row.get("labels"))
    if labels.get("outcome_label") not in {"improved", "regressed", "same", "unknown"}:
        raise ValueError("shadow outcome label is invalid")
    usage = _mapping(row.get("usage"))
    for field in HOSTED_USAGE_FIELDS:
        value = usage.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"shadow outcome usage field {field} must be a nonnegative int")


def summarize_transition_shadow_outcomes(
    rows: Sequence[Mapping[str, object]],
    *,
    advice_paths: Sequence[Path] = (),
    candidate_outcome_paths: Sequence[Path] = (),
    out_path: Path | None = None,
) -> TransitionShadowOutcomeSummary:
    """Summarize normalized shadow outcome rows."""

    for row in rows:
        validate_transition_shadow_outcome(row)
    join_counts = Counter(_string(row.get("join_status"), "unknown") for row in rows)
    label_counts = Counter(
        _string(_mapping(row.get("labels")).get("outcome_label"), "unknown")
        for row in rows
    )
    usage = _usage_totals(rows)
    return TransitionShadowOutcomeSummary(
        advice_paths=[path.expanduser().resolve() for path in advice_paths],
        candidate_outcome_paths=[
            path.expanduser().resolve() for path in candidate_outcome_paths
        ],
        out_path=out_path.expanduser().resolve() if out_path is not None else None,
        rows=len(rows),
        joined_rows=join_counts["joined"],
        unjoined_advice_rows=join_counts["unjoined_advice"],
        unjoined_candidate_outcome_rows=join_counts["unjoined_candidate_outcomes"],
        known_validation_rows=sum(
            1
            for row in rows
            if _mapping(row.get("validation_outcome")).get("known") is True
        ),
        labels={
            label: label_counts[label]
            for label in ("improved", "regressed", "same", "unknown")
        },
        usage=usage,
    )


def format_transition_shadow_outcome_summary(
    summary: TransitionShadowOutcomeSummary,
) -> str:
    """Format a shadow outcome normalization summary for CLI output."""

    lines = ["j3 normalize-transition-shadow-outcomes"]
    lines.append("transition advice:")
    for path in summary.advice_paths:
        lines.append(f"  {path}")
    lines.append("candidate outcomes:")
    for path in summary.candidate_outcome_paths:
        lines.append(f"  {path}")
    if summary.out_path is not None:
        lines.append(f"out: {summary.out_path}")
    lines.append(f"rows: {summary.rows}")
    lines.append(f"joined rows: {summary.joined_rows}")
    lines.append(f"unjoined advice rows: {summary.unjoined_advice_rows}")
    lines.append(
        "unjoined candidate outcome rows: "
        f"{summary.unjoined_candidate_outcome_rows}"
    )
    lines.append(f"known validation rows: {summary.known_validation_rows}")
    lines.append(
        "labels: "
        f"improved={summary.labels['improved']} "
        f"regressed={summary.labels['regressed']} "
        f"same={summary.labels['same']} "
        f"unknown={summary.labels['unknown']}"
    )
    for field in HOSTED_USAGE_FIELDS:
        lines.append(f"{field}: {summary.usage[field]}")
    return "\n".join(lines)


def _normalized_row(
    *,
    advice: Mapping[str, object] | None,
    outcome_rows: Sequence[Mapping[str, object]],
    key: tuple[str, str, str],
    join_status: str,
    unjoined_reason: str | None,
    source: Mapping[str, object],
) -> dict[str, object]:
    task, phase, repair_plan_id = key
    advice_context = _mapping(advice.get("repair_context") if advice else None)
    repo_summary = _mapping(advice.get("repo_state_summary") if advice else None)
    selected = _production_selected_candidate(advice, outcome_rows)
    scorer_top = _scorer_top_candidate(advice)
    ranking = _candidate_ranking(advice, outcome_rows)
    comparison = _mapping(advice.get("validation_comparison") if advice else None)
    validation = _validation_outcome(
        comparison=comparison,
        selected=selected,
        scorer_top=scorer_top,
        outcome_rows=outcome_rows,
    )
    labels = _labels(advice=advice, selected=selected, scorer_top=scorer_top)
    usage = _usage_totals([advice] if advice is not None else [])
    row = {
        "schema_version": TRANSITION_SHADOW_OUTCOME_VERSION,
        "id": _row_id(
            key=key,
            join_status=join_status,
            source=source,
        ),
        "join_status": join_status,
        "unjoined_reason": unjoined_reason,
        "key": {
            "task": task,
            "phase": phase,
            "repair_plan_id": repair_plan_id or None,
        },
        "repo": {
            "path": repo_summary.get("repo"),
            "name": repo_summary.get("repo_name"),
            "python_file_count": repo_summary.get("python_file_count"),
            "language": _first_string(
                advice_context.get("language"),
                _first_outcome_value(outcome_rows, "language"),
                "python",
            ),
        },
        "task": {
            "name": _first_string(task, _first_outcome_value(outcome_rows, "task"), ""),
            "family": _first_string(
                advice_context.get("task_family"),
                _first_outcome_value(outcome_rows, "task_family"),
                "unclassified",
            ),
            "source_type": _first_string(
                advice_context.get("source_type"),
                _first_outcome_value(outcome_rows, "source_type"),
                "unknown",
            ),
            "split": _first_string(
                advice_context.get("split"),
                _first_outcome_value(outcome_rows, "split"),
                "unspecified",
            ),
            "phase": _first_string(phase, _first_outcome_value(outcome_rows, "phase"), ""),
            "test_command": advice_context.get("test_command"),
        },
        "production_selected_candidate": selected,
        "scorer_top_candidate": scorer_top,
        "candidate_ranking": ranking,
        "validation_outcome": validation,
        "labels": labels,
        "source": dict(source),
        "usage": usage,
        "runtime": {
            "local_runtime_ms": _float(
                _mapping(advice.get("runtime") if advice else None).get(
                    "local_runtime_ms"
                )
            ),
            **usage,
        },
    }
    validate_transition_shadow_outcome(row)
    return row


def _candidate_ranking(
    advice: Mapping[str, object] | None,
    outcome_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    outcome_by_rank = {
        rank: row
        for row in outcome_rows
        if (rank := _positive_int_or_none(row.get("rank_index"))) is not None
    }
    production_order = _rank_order(
        _mapping(advice).get("existing_ranked_candidate_ranks")
    )
    if not production_order:
        production_order = sorted(outcome_by_rank)
    scorer_order = _rank_order(_mapping(advice).get("scorer_ranked_candidate_ranks"))
    ranks = sorted(set(production_order) | set(scorer_order) | set(outcome_by_rank))
    selected = _mapping(_mapping(advice).get("existing_selected_candidate"))
    scorer_top = _mapping(_mapping(advice).get("scorer_top_candidate"))

    records: list[dict[str, object]] = []
    for rank in ranks:
        outcome = outcome_by_rank.get(rank)
        summary = _candidate_summary_from_outcome(outcome) if outcome else {}
        if selected.get("rank_index") == rank:
            summary = {**_compact_candidate_summary(selected), **summary}
        if scorer_top.get("rank_index") == rank:
            summary = {**_compact_candidate_summary(scorer_top), **summary}
        records.append(
            {
                "rank_index": rank,
                "production_rank_position": _rank_position(production_order, rank),
                "scorer_rank_position": _rank_position(scorer_order, rank),
                "candidate": {"rank_index": rank, **summary},
                "validation": {
                    "known": outcome is not None,
                    "passed": outcome.get("passed") if outcome is not None else None,
                    "is_first_pass": (
                        outcome.get("is_first_pass") if outcome is not None else None
                    ),
                },
            }
        )
    return records


def _production_selected_candidate(
    advice: Mapping[str, object] | None,
    outcome_rows: Sequence[Mapping[str, object]],
) -> dict[str, object] | None:
    if advice is not None:
        selected = _mapping(advice.get("existing_selected_candidate"))
        if selected:
            outcome = _outcome_by_rank(outcome_rows, selected.get("rank_index"))
            summary = _compact_candidate_summary(selected)
            if outcome is not None:
                summary = {**summary, **_candidate_summary_from_outcome(outcome)}
            return summary
    selected_outcome = _selected_outcome_row(outcome_rows)
    if selected_outcome is None:
        return None
    return _candidate_summary_from_outcome(selected_outcome)


def _scorer_top_candidate(advice: Mapping[str, object] | None) -> dict[str, object] | None:
    if advice is None:
        return None
    scorer_top = _mapping(advice.get("scorer_top_candidate"))
    if not scorer_top:
        return None
    return _compact_candidate_summary(scorer_top)


def _validation_outcome(
    *,
    comparison: Mapping[str, object],
    selected: Mapping[str, object] | None,
    scorer_top: Mapping[str, object] | None,
    outcome_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    first_passing_index = _first_passing_index(outcome_rows)
    label = _comparison_label(comparison)
    known = comparison.get("known") is True or bool(outcome_rows)
    scorer_top_passed = None
    if scorer_top is not None:
        scorer_top_outcome = _outcome_by_rank(outcome_rows, scorer_top.get("rank_index"))
        scorer_top_passed = (
            scorer_top_outcome.get("passed")
            if scorer_top_outcome is not None
            else scorer_top.get("passed")
        )
    return {
        "known": known,
        "outcome_label": label,
        "production_selected_passed": (
            selected.get("passed") if selected is not None else None
        ),
        "production_first_passing_index": first_passing_index
        or _positive_int_or_none(comparison.get("existing_first_passing_index")),
        "production_pass_at_1": (
            first_passing_index == 1 if first_passing_index is not None else None
        ),
        "scorer_top_passed": scorer_top_passed,
        "scorer_first_known_passing_position": _positive_int_or_none(
            comparison.get("scorer_first_known_passing_position")
        ),
        "scorer_first_known_passing_rank_index": _positive_int_or_none(
            comparison.get("scorer_first_known_passing_rank_index")
        ),
        "candidate_outcome_row_count": len(outcome_rows),
        "passing_candidate_count": sum(1 for row in outcome_rows if row.get("passed") is True),
        "comparison": dict(comparison),
    }


def _labels(
    *,
    advice: Mapping[str, object] | None,
    selected: Mapping[str, object] | None,
    scorer_top: Mapping[str, object] | None,
) -> dict[str, object]:
    comparison = _mapping(advice.get("validation_comparison") if advice else None)
    label = _comparison_label(comparison)
    top_agreement = None
    rank_order_agreement = None
    if advice is not None:
        top_value = advice.get("scorer_agreed_with_existing_top_candidate")
        order_value = advice.get("scorer_agreed_with_existing_rank_order")
        top_agreement = top_value if isinstance(top_value, bool) else None
        rank_order_agreement = order_value if isinstance(order_value, bool) else None
        if top_agreement is None and selected is not None and scorer_top is not None:
            top_agreement = _candidate_identity(selected) == _candidate_identity(scorer_top)
    return {
        "validation_known": comparison.get("known") is True,
        "outcome_label": label,
        "agreement": top_agreement,
        "rank_order_agreement": rank_order_agreement,
        "improvement": label == "improved" if label != "unknown" else None,
        "regression": label == "regressed" if label != "unknown" else None,
    }


def _read_advice_items(paths: Sequence[Path]) -> list[_AdviceItem]:
    items: list[_AdviceItem] = []
    index = 0
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"transition advice file does not exist: {resolved}")
        if not resolved.is_file():
            raise IsADirectoryError(f"transition advice path is not a file: {resolved}")
        for line_number, line in enumerate(
            resolved.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{resolved}:{line_number}: expected JSON object")
            if row.get("schema_version") != TRANSITION_SCORER_ADVICE_VERSION:
                raise ValueError(
                    f"{resolved}:{line_number}: expected {TRANSITION_SCORER_ADVICE_VERSION}"
                )
            index += 1
            items.append(
                _AdviceItem(row=row, path=resolved, line_number=line_number, index=index)
            )
    return items


def _read_outcome_items(paths: Sequence[Path]) -> list[_OutcomeItem]:
    items: list[_OutcomeItem] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"candidate outcome file does not exist: {resolved}")
        if not resolved.is_file():
            raise IsADirectoryError(f"candidate outcome path is not a file: {resolved}")
        for line_number, line in enumerate(
            resolved.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{resolved}:{line_number}: expected JSON object")
            items.append(_OutcomeItem(row=row, path=resolved, line_number=line_number))
    return items


def _group_outcome_items(items: Sequence[_OutcomeItem]) -> dict[tuple[str, str, str], _OutcomeGroup]:
    groups: dict[tuple[str, str, str], _OutcomeGroup] = {}
    for item in items:
        key = _outcome_key(item.row)
        group = groups.setdefault(key, _OutcomeGroup(key=key, rows=[], path_lines=[]))
        group.rows.append(item.row)
        group.path_lines.append({"path": str(item.path), "line_number": item.line_number})
    for group in groups.values():
        group.rows.sort(key=lambda row: _positive_int_or_none(row.get("rank_index")) or 0)
    return groups


def _advice_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    context = _mapping(row.get("repair_context"))
    return (
        _string(context.get("task"), ""),
        _string(context.get("phase"), ""),
        _string(row.get("repair_plan_id"), ""),
    )


def _outcome_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        _string(row.get("task"), ""),
        _string(row.get("phase"), ""),
        _string(row.get("repair_plan_id"), ""),
    )


def _key_is_joinable(key: tuple[str, str, str]) -> bool:
    return all(key)


def _missing_key_reason(key: tuple[str, str, str]) -> str | None:
    missing = [
        name
        for name, value in zip(("task", "phase", "repair_plan_id"), key, strict=True)
        if not value
    ]
    if missing:
        return "missing_" + "_".join(missing)
    return None


def _selected_outcome_row(
    rows: Sequence[Mapping[str, object]],
) -> Mapping[str, object] | None:
    for row in rows:
        if row.get("is_first_pass") is True:
            return row
    for row in rows:
        if row.get("passed") is True:
            return row
    return None


def _outcome_by_rank(
    rows: Sequence[Mapping[str, object]],
    rank: object,
) -> Mapping[str, object] | None:
    expected = _positive_int_or_none(rank)
    if expected is None:
        return None
    for row in rows:
        if _positive_int_or_none(row.get("rank_index")) == expected:
            return row
    return None


def _candidate_summary_from_outcome(row: Mapping[str, object] | None) -> dict[str, object]:
    if row is None:
        return {}
    return {
        "rank_index": row.get("rank_index"),
        "file_path": row.get("file_path"),
        "action": row.get("action"),
        "symbol": row.get("symbol"),
        "start_line": row.get("start_line"),
        "end_line": row.get("end_line"),
        "node_kind": row.get("node_kind"),
        "params": row.get("params"),
        "reason": row.get("reason"),
        "validated": True,
        "passed": row.get("passed"),
        "preferred": row.get("preferred"),
        "is_first_pass": row.get("is_first_pass"),
    }


def _compact_candidate_summary(row: Mapping[str, object]) -> dict[str, object]:
    fields = (
        "id",
        "rank_index",
        "file_path",
        "action",
        "symbol",
        "start_line",
        "end_line",
        "node_kind",
        "params",
        "validated",
        "passed",
        "score",
        "reason",
    )
    return {field: row.get(field) for field in fields if field in row}


def _rank_order(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    ranks: list[int] = []
    for item in value:
        rank = _positive_int_or_none(item)
        if rank is not None:
            ranks.append(rank)
    return ranks


def _rank_position(order: Sequence[int], rank: int) -> int | None:
    for index, item in enumerate(order, start=1):
        if item == rank:
            return index
    return None


def _first_passing_index(rows: Sequence[Mapping[str, object]]) -> int | None:
    for row in rows:
        if row.get("is_first_pass") is True:
            rank = _positive_int_or_none(row.get("rank_index"))
            if rank is not None:
                return rank
    for row in rows:
        if row.get("passed") is True:
            return _positive_int_or_none(row.get("rank_index"))
    return None


def _comparison_label(comparison: Mapping[str, object]) -> str:
    label = comparison.get("would_have")
    if label in {"improved", "regressed", "same"}:
        return str(label)
    return "unknown"


def _candidate_identity(row: Mapping[str, object]) -> tuple[object, object, object]:
    return (row.get("id"), row.get("rank_index"), row.get("reason"))


def _first_outcome_value(
    rows: Sequence[Mapping[str, object]],
    key: str,
) -> object:
    for row in rows:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _first_string(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""


def _usage_totals(rows: Sequence[Mapping[str, object] | None]) -> dict[str, int]:
    totals = {field: 0 for field in HOSTED_USAGE_FIELDS}
    for row in rows:
        if row is None:
            continue
        usage = _mapping(row.get("usage"))
        runtime = _mapping(row.get("runtime"))
        for field in HOSTED_USAGE_FIELDS:
            totals[field] += _int(usage.get(field, runtime.get(field)))
    return totals


def _row_id(
    *,
    key: tuple[str, str, str],
    join_status: str,
    source: Mapping[str, object],
) -> str:
    payload = {"key": key, "join_status": join_status, "source": source}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"shadow-outcome:{digest[:16]}"


def _positive_int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _string(value: object, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}
