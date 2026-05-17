"""Residual reporting for transition shadow and V3 scorer evidence."""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from j3.transition_action_choice import build_transition_action_choice_groups_jsonl
from j3.transition_action_scoring import (
    EXISTING_RANK_ORDER_BASELINE,
    TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
    TRANSITION_ACTION_SCORER_V3_VERSION,
    rank_transition_action_candidates,
)
from j3.transition_shadow_outcomes import (
    HOSTED_USAGE_FIELDS,
    load_transition_shadow_outcomes,
)


TRANSITION_RESIDUAL_REPORT_VERSION = "transition-residual-report-v1"
TRANSITION_RESIDUAL_MATRIX_REPORT_VERSION = "transition-residual-matrix-report-v1"


def report_transition_residuals(
    *,
    shadow_outcome_paths: Sequence[Path],
    shadow_scorer_report_path: Path,
    candidate_outcome_paths: Sequence[Path],
    embedding_dim: int = 256,
    example_limit: int = 20,
    out: Path | None = None,
) -> dict[str, object]:
    """Build a structured residual report from shadow outcomes and V3 evidence."""

    if example_limit < 0:
        raise ValueError("example_limit must be >= 0")
    started = time.perf_counter()
    shadow_rows = load_transition_shadow_outcomes(shadow_outcome_paths)
    shadow_scorer_report = _load_shadow_scorer_report(shadow_scorer_report_path)
    groups = [
        group
        for path in candidate_outcome_paths
        for group in build_transition_action_choice_groups_jsonl(
            path,
            embedding_dim=embedding_dim,
        )
    ]

    shadow_by_key = {
        _shadow_row_key(row): row
        for row in shadow_rows
        if row.get("join_status") == "joined" and all(_shadow_row_key(row))
    }
    failure_examples: list[dict[str, object]] = []
    failure_counts: Counter[str] = Counter()
    task_family_counts: Counter[str] = Counter()
    action_kind_counts: Counter[str] = Counter()
    source_file_counts: Counter[str] = Counter()
    top_comparison_counts: Counter[str] = Counter()
    missing_feature_counts: Counter[str] = Counter()
    gap_counts: Counter[str] = Counter()

    model = _mapping(shadow_scorer_report.get("model"))
    v3_available = (
        shadow_scorer_report.get("available") is True
        and model.get("name") == TRANSITION_ACTION_SCORER_V3_VERSION
    )

    matched_keys: set[tuple[str, str, str]] = set()
    for group in groups:
        key = _group_key(group)
        shadow = shadow_by_key.get(key)
        if shadow is not None:
            matched_keys.add(key)
        residual = _group_residual(
            group,
            shadow=shadow,
            v3_model=model if v3_available else None,
        )
        if residual is None:
            continue
        _record_failure(
            residual,
            failure_examples=failure_examples,
            failure_counts=failure_counts,
            task_family_counts=task_family_counts,
            action_kind_counts=action_kind_counts,
            source_file_counts=source_file_counts,
            top_comparison_counts=top_comparison_counts,
            missing_feature_counts=missing_feature_counts,
            gap_counts=gap_counts,
            example_limit=example_limit,
        )

    for row in shadow_rows:
        key = _shadow_row_key(row)
        if key in matched_keys:
            continue
        if row.get("join_status") == "joined":
            continue
        residual = _unjoined_shadow_residual(row)
        _record_failure(
            residual,
            failure_examples=failure_examples,
            failure_counts=failure_counts,
            task_family_counts=task_family_counts,
            action_kind_counts=action_kind_counts,
            source_file_counts=source_file_counts,
            top_comparison_counts=top_comparison_counts,
            missing_feature_counts=missing_feature_counts,
            gap_counts=gap_counts,
            example_limit=example_limit,
        )

    usage = _usage_totals(shadow_rows, shadow_scorer_report)
    report = {
        "schema_version": TRANSITION_RESIDUAL_REPORT_VERSION,
        "inputs": {
            "shadow_outcomes": [
                str(path.expanduser().resolve()) for path in shadow_outcome_paths
            ],
            "shadow_scorer_report": str(
                shadow_scorer_report_path.expanduser().resolve()
            ),
            "candidate_outcomes": [
                str(path.expanduser().resolve()) for path in candidate_outcome_paths
            ],
        },
        "shadow_scorer": {
            "schema_version": shadow_scorer_report.get("schema_version"),
            "available": shadow_scorer_report.get("available") is True,
            "scorer": shadow_scorer_report.get("scorer"),
            "gate_result": _mapping(
                _mapping(shadow_scorer_report.get("validation")).get(
                    "product_readiness"
                )
            ).get("gate_result"),
        },
        "summary": {
            "shadow_outcome_rows": len(shadow_rows),
            "candidate_action_choice_groups": len(groups),
            "failure_count": sum(failure_counts.values()),
            "failure_kinds": dict(sorted(failure_counts.items())),
            "gap_types": dict(sorted(gap_counts.items())),
        },
        "groups": {
            "task_family": _counter_records(task_family_counts),
            "action_kind": _counter_records(action_kind_counts),
            "source_file": _counter_records(source_file_counts),
            "scorer_top_vs_production": _counter_records(top_comparison_counts),
            "missing_feature_evidence": _counter_records(missing_feature_counts),
            "gap_type": _counter_records(gap_counts),
        },
        "examples": failure_examples,
        "runtime": {
            "local_runtime_ms": round((time.perf_counter() - started) * 1000, 3),
            **usage,
        },
        "usage": dict(usage),
    }
    if out is not None:
        resolved = out.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        report = {**report, "report": str(resolved)}
        resolved.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def report_transition_residual_matrix(
    *,
    matrix_dir: Path,
    embedding_dim: int = 256,
    example_limit: int = 20,
    out: Path | None = None,
) -> dict[str, object]:
    """Build a cross-suite residual report from a shadow matrix output."""

    if example_limit < 0:
        raise ValueError("example_limit must be >= 0")
    started = time.perf_counter()
    matrix = matrix_dir.expanduser().resolve()
    if not matrix.exists():
        raise FileNotFoundError(f"matrix output directory does not exist: {matrix}")
    if not matrix.is_dir():
        raise NotADirectoryError(f"matrix output path is not a directory: {matrix}")

    matrix_summary_path = matrix / "matrix-summary.json"
    matrix_summary = _load_json_object(
        matrix_summary_path,
        label="matrix summary",
    )
    suites = _list(matrix_summary.get("suites"))
    if not suites:
        raise ValueError("matrix summary does not contain suites")

    suite_reports: list[dict[str, object]] = []
    suite_examples: list[dict[str, object]] = []
    suite_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    task_family_counts: Counter[str] = Counter()
    action_kind_counts: Counter[str] = Counter()
    source_file_counts: Counter[str] = Counter()
    top_comparison_counts: Counter[str] = Counter()
    missing_feature_counts: Counter[str] = Counter()
    gap_counts: Counter[str] = Counter()

    for suite in suites:
        suite_record = _mapping(suite)
        suite_id = _string(suite_record.get("id"), "unknown")
        suite_manifest = _load_suite_manifest(matrix, suite_record)
        artifacts = _mapping(suite_manifest.get("artifacts"))
        suite_report = report_transition_residuals(
            shadow_outcome_paths=[
                _artifact_path(artifacts, "transition_shadow_outcomes", suite_id)
            ],
            shadow_scorer_report_path=_artifact_path(
                artifacts,
                "shadow_scorer_v3_report",
                suite_id,
            ),
            candidate_outcome_paths=[
                _artifact_path(artifacts, "candidate_outcomes", suite_id)
            ],
            embedding_dim=embedding_dim,
            example_limit=example_limit,
        )
        suite_summary = _mapping(suite_report.get("summary"))
        suite_scorer = _mapping(suite_report.get("shadow_scorer"))
        failure_count = _int(suite_summary.get("failure_count"))
        gate_result = _string(suite_scorer.get("gate_result"), "unknown")
        if failure_count:
            suite_counts[suite_id] += failure_count
            gate_counts[gate_result] += failure_count
        _merge_counter_records(task_family_counts, suite_report, "task_family")
        _merge_counter_records(action_kind_counts, suite_report, "action_kind")
        _merge_counter_records(source_file_counts, suite_report, "source_file")
        _merge_counter_records(
            top_comparison_counts,
            suite_report,
            "scorer_top_vs_production",
        )
        _merge_counter_records(
            missing_feature_counts,
            suite_report,
            "missing_feature_evidence",
        )
        _merge_counter_records(gap_counts, suite_report, "gap_type")
        for kind, count in _mapping(suite_summary.get("failure_kinds")).items():
            failure_counts[str(kind)] += _int(count)
        for example in _list(suite_report.get("examples")):
            if isinstance(example, Mapping):
                suite_examples.append(
                    {
                        **dict(example),
                        "suite_id": suite_id,
                        "gate_result": gate_result,
                    }
                )
        suite_reports.append(
            {
                "suite_id": suite_id,
                "task_count": suite_record.get("task_count"),
                "ranked_solved": suite_record.get("ranked_solved"),
                "gate_result": gate_result,
                "failure_count": failure_count,
                "gap_types": suite_summary.get("gap_types"),
                "examples_included": len(_list(suite_report.get("examples"))),
                "artifacts": {
                    "manifest": str(_suite_manifest_path(matrix, suite_record)),
                    "candidate_outcomes": artifacts.get("candidate_outcomes"),
                    "transition_shadow_outcomes": artifacts.get(
                        "transition_shadow_outcomes"
                    ),
                    "shadow_scorer_v3_report": artifacts.get(
                        "shadow_scorer_v3_report"
                    ),
                },
            }
        )

    matrix_usage = _mapping(matrix_summary.get("usage"))
    usage = {
        field: _int(matrix_usage.get(field))
        for field in HOSTED_USAGE_FIELDS
    }

    report = {
        "schema_version": TRANSITION_RESIDUAL_MATRIX_REPORT_VERSION,
        "matrix": {
            "out": str(matrix),
            "summary": str(matrix_summary_path),
            "schema_version": matrix_summary.get("schema_version"),
            "zero_hosted_usage": matrix_summary.get("zero_hosted_usage") is True,
            "totals": matrix_summary.get("totals"),
            "evidence": matrix_summary.get("evidence"),
        },
        "summary": {
            "suite_count": len(suite_reports),
            "failure_count": sum(failure_counts.values()),
            "failure_kinds": dict(sorted(failure_counts.items())),
            "gap_types": dict(sorted(gap_counts.items())),
        },
        "groups": {
            "suite_id": _counter_records(suite_counts),
            "task_family": _counter_records(task_family_counts),
            "action_kind": _counter_records(action_kind_counts),
            "source_file": _counter_records(source_file_counts),
            "gate_result": _counter_records(gate_counts),
            "scorer_top_vs_production": _counter_records(top_comparison_counts),
            "missing_feature_evidence": _counter_records(missing_feature_counts),
            "gap_type": _counter_records(gap_counts),
        },
        "suites": suite_reports,
        "examples": suite_examples,
        "runtime": {
            "local_runtime_ms": round((time.perf_counter() - started) * 1000, 3),
            **usage,
        },
        "usage": usage,
    }
    if out is not None:
        resolved = out.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        report = {**report, "report": str(resolved)}
        resolved.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def format_transition_residual_report(report: Mapping[str, object]) -> str:
    """Format a transition residual report for terminal output."""

    if report.get("schema_version") == TRANSITION_RESIDUAL_MATRIX_REPORT_VERSION:
        return _format_transition_residual_matrix_report(report)

    summary = _mapping(report.get("summary"))
    groups = _mapping(report.get("groups"))
    runtime = _mapping(report.get("runtime"))
    scorer = _mapping(report.get("shadow_scorer"))
    lines = [
        "j3 report-transition-residuals complete",
        f"shadow scorer: {scorer.get('scorer')} available={scorer.get('available')}",
        f"product gate: {scorer.get('gate_result')}",
        f"shadow rows: {summary.get('shadow_outcome_rows', 0)}",
        f"candidate groups: {summary.get('candidate_action_choice_groups', 0)}",
        f"failures: {summary.get('failure_count', 0)}",
        f"gap types: {_format_counter(_mapping(summary.get('gap_types')))}",
        f"task families: {_format_group_counts(groups.get('task_family'))}",
        f"action kinds: {_format_group_counts(groups.get('action_kind'))}",
        f"source files: {_format_group_counts(groups.get('source_file'))}",
        "missing feature evidence: "
        f"{_format_group_counts(groups.get('missing_feature_evidence'))}",
        f"local runtime ms: {runtime.get('local_runtime_ms', 0)}",
    ]
    for field in HOSTED_USAGE_FIELDS:
        lines.append(f"{field}: {runtime.get(field, 0)}")
    if report.get("report"):
        lines.append(f"report: {report['report']}")
    return "\n".join(lines)


def _format_transition_residual_matrix_report(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    groups = _mapping(report.get("groups"))
    runtime = _mapping(report.get("runtime"))
    matrix = _mapping(report.get("matrix"))
    lines = [
        "j3 report-transition-residuals complete",
        f"matrix: {matrix.get('out')}",
        f"suites: {summary.get('suite_count', 0)}",
        f"failures: {summary.get('failure_count', 0)}",
        f"gap types: {_format_counter(_mapping(summary.get('gap_types')))}",
        f"gates: {_format_group_counts(groups.get('gate_result'))}",
        f"suite ids: {_format_group_counts(groups.get('suite_id'))}",
        f"task families: {_format_group_counts(groups.get('task_family'))}",
        f"action kinds: {_format_group_counts(groups.get('action_kind'))}",
        f"source files: {_format_group_counts(groups.get('source_file'))}",
        "missing feature evidence: "
        f"{_format_group_counts(groups.get('missing_feature_evidence'))}",
        f"local runtime ms: {runtime.get('local_runtime_ms', 0)}",
    ]
    for field in HOSTED_USAGE_FIELDS:
        lines.append(f"{field}: {runtime.get(field, 0)}")
    if report.get("report"):
        lines.append(f"report: {report['report']}")
    return "\n".join(lines)


def _group_residual(
    group: Mapping[str, object],
    *,
    shadow: Mapping[str, object] | None,
    v3_model: Mapping[str, object] | None,
) -> dict[str, object] | None:
    grouping = _mapping(group.get("grouping"))
    production_ranked = rank_transition_action_candidates(
        group,
        strategy=EXISTING_RANK_ORDER_BASELINE,
    )
    production_top = production_ranked[0] if production_ranked else None
    v3_top = None
    if v3_model is not None:
        v3_group = {**dict(group), "shadow_outcome": dict(shadow or {})}
        v3_ranked = rank_transition_action_candidates(
            v3_group,
            strategy=TRANSITION_ACTION_SCORER_V3_VERSION,
            scorer_model=v3_model,
        )
        v3_top = v3_ranked[0] if v3_ranked else None

    passing_ranks = {
        rank for rank in group.get("passing_candidate_ranks", []) if isinstance(rank, int)
    }
    shadow_scorer_top = _mapping(shadow.get("scorer_top_candidate") if shadow else None)
    shadow_label = _mapping(shadow.get("labels") if shadow else None).get(
        "outcome_label"
    )
    reasons: list[str] = []
    gap_type = "scorer_ranking_gap"
    selected_top = v3_top or _candidate_by_rank(group, shadow_scorer_top.get("rank_index"))
    if not passing_ranks:
        reasons.append("no_passing_candidate_generated")
        gap_type = "candidate_generation_gap"
    elif v3_top is not None and _rank(v3_top) not in passing_ranks:
        reasons.append("v3_top_candidate_failed")
    elif shadow_scorer_top and shadow_scorer_top.get("passed") is False:
        reasons.append("shadow_scorer_top_candidate_failed")
    elif shadow_label == "regressed":
        reasons.append("shadow_scorer_regressed_against_production")

    if shadow is None:
        reasons.append("missing_shadow_outcome")
    if not reasons:
        return None

    top_candidate = selected_top or production_top
    return {
        "failure_kind": reasons[0],
        "reasons": reasons,
        "gap_type": gap_type,
        "group_id": group.get("id"),
        "key": {
            "task": grouping.get("task"),
            "phase": grouping.get("phase"),
            "repair_plan_id": grouping.get("repair_plan_identity"),
        },
        "task_family": _string(grouping.get("task_family"), "unclassified"),
        "source_file": _candidate_file(top_candidate, production_top, shadow_scorer_top),
        "action_kind": _candidate_action_kind(top_candidate, shadow_scorer_top),
        "scorer_top_vs_production": _top_comparison(
            production_top=production_top,
            scorer_top=shadow_scorer_top,
            v3_top=v3_top,
        ),
        "missing_feature_evidence": _missing_feature_evidence(
            group,
            top_candidate=top_candidate,
            shadow=shadow,
            v3_model=v3_model,
        ),
        "production_candidate": _candidate_summary(production_top),
        "shadow_scorer_top_candidate": (
            dict(shadow_scorer_top) if shadow_scorer_top else None
        ),
        "v3_top_candidate": _candidate_summary(v3_top),
        "passing_candidate_ranks": sorted(passing_ranks),
        "exact_candidate_summaries": [
            _candidate_summary(candidate)
            for candidate in _candidate_list(group)
        ],
        "shadow_outcome": {
            "id": shadow.get("id") if shadow else None,
            "join_status": shadow.get("join_status") if shadow else None,
            "outcome_label": shadow_label,
        },
    }


def _unjoined_shadow_residual(row: Mapping[str, object]) -> dict[str, object]:
    task = _mapping(row.get("task"))
    top = _mapping(row.get("scorer_top_candidate")) or _mapping(
        row.get("production_selected_candidate")
    )
    return {
        "failure_kind": "shadow_outcome_unjoined",
        "reasons": [str(row.get("unjoined_reason") or "unjoined_shadow_outcome")],
        "gap_type": "evidence_gap",
        "group_id": row.get("id"),
        "key": dict(_mapping(row.get("key"))),
        "task_family": _string(task.get("family"), "unclassified"),
        "source_file": _string(top.get("file_path"), "unknown"),
        "action_kind": _string(top.get("action"), "unknown"),
        "scorer_top_vs_production": "unknown_missing_join",
        "missing_feature_evidence": [str(row.get("unjoined_reason"))],
        "production_candidate": row.get("production_selected_candidate"),
        "shadow_scorer_top_candidate": row.get("scorer_top_candidate"),
        "v3_top_candidate": None,
        "passing_candidate_ranks": [],
        "exact_candidate_summaries": [],
        "shadow_outcome": {
            "id": row.get("id"),
            "join_status": row.get("join_status"),
            "outcome_label": _mapping(row.get("labels")).get("outcome_label"),
        },
    }


def _record_failure(
    residual: Mapping[str, object],
    *,
    failure_examples: list[dict[str, object]],
    failure_counts: Counter[str],
    task_family_counts: Counter[str],
    action_kind_counts: Counter[str],
    source_file_counts: Counter[str],
    top_comparison_counts: Counter[str],
    missing_feature_counts: Counter[str],
    gap_counts: Counter[str],
    example_limit: int,
) -> None:
    failure_counts[_string(residual.get("failure_kind"), "unknown")] += 1
    task_family_counts[_string(residual.get("task_family"), "unclassified")] += 1
    action_kind_counts[_string(residual.get("action_kind"), "unknown")] += 1
    source_file_counts[_string(residual.get("source_file"), "unknown")] += 1
    top_comparison_counts[
        _string(residual.get("scorer_top_vs_production"), "unknown")
    ] += 1
    gap_counts[_string(residual.get("gap_type"), "unknown")] += 1
    evidence = residual.get("missing_feature_evidence")
    if isinstance(evidence, list) and evidence:
        for item in evidence:
            missing_feature_counts[_string(item, "unknown")] += 1
    else:
        missing_feature_counts["none_detected"] += 1
    if len(failure_examples) < example_limit:
        failure_examples.append(dict(residual))


def _load_shadow_scorer_report(path: Path) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"shadow scorer report does not exist: {resolved}")
    if not resolved.is_file():
        raise IsADirectoryError(f"shadow scorer report path is not a file: {resolved}")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("shadow scorer report must be a JSON object")
    if value.get("schema_version") != TRANSITION_ACTION_SCORER_V3_REPORT_VERSION:
        raise ValueError(f"expected {TRANSITION_ACTION_SCORER_V3_REPORT_VERSION}")
    return value


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {resolved}")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _load_suite_manifest(
    matrix: Path,
    suite_record: Mapping[str, object],
) -> dict[str, object]:
    return _load_json_object(
        _suite_manifest_path(matrix, suite_record),
        label=f"matrix suite {suite_record.get('id')} manifest",
    )


def _suite_manifest_path(
    matrix: Path,
    suite_record: Mapping[str, object],
) -> Path:
    manifest = suite_record.get("manifest")
    if isinstance(manifest, str) and manifest:
        return Path(manifest)
    out = suite_record.get("out")
    if isinstance(out, str) and out:
        return Path(out) / "manifest.json"
    suite_id = _string(suite_record.get("id"), "")
    if suite_id:
        return matrix / "suite" / suite_id / "manifest.json"
    raise ValueError("matrix suite record is missing manifest, out, and id")


def _artifact_path(
    artifacts: Mapping[str, object],
    name: str,
    suite_id: str,
) -> Path:
    value = artifacts.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"suite {suite_id} manifest is missing artifact {name}")
    return Path(value)


def _merge_counter_records(
    counter: Counter[str],
    report: Mapping[str, object],
    group_name: str,
) -> None:
    groups = _mapping(report.get("groups"))
    for row in _list(groups.get(group_name)):
        if not isinstance(row, Mapping):
            continue
        counter[_string(row.get("value"), "unknown")] += _int(row.get("count"))


def _counter_records(counter: Counter[str]) -> list[dict[str, object]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _usage_totals(
    shadow_rows: Sequence[Mapping[str, object]],
    shadow_scorer_report: Mapping[str, object],
) -> dict[str, int]:
    totals = {field: 0 for field in HOSTED_USAGE_FIELDS}
    for row in shadow_rows:
        usage = _mapping(row.get("usage"))
        runtime = _mapping(row.get("runtime"))
        for field in HOSTED_USAGE_FIELDS:
            totals[field] += _int(usage.get(field, runtime.get(field)))
    report_runtime = _mapping(shadow_scorer_report.get("runtime"))
    for field in HOSTED_USAGE_FIELDS:
        totals[field] += _int(report_runtime.get(field))
    return totals


def _group_key(group: Mapping[str, object]) -> tuple[str, str, str]:
    grouping = _mapping(group.get("grouping"))
    return (
        _string(grouping.get("task"), ""),
        _string(grouping.get("phase"), ""),
        _string(grouping.get("repair_plan_identity"), ""),
    )


def _shadow_row_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    key = _mapping(row.get("key"))
    return (
        _string(key.get("task"), ""),
        _string(key.get("phase"), ""),
        _string(key.get("repair_plan_id"), ""),
    )


def _candidate_by_rank(
    group: Mapping[str, object],
    rank: object,
) -> Mapping[str, object] | None:
    expected = _rank({"rank_index": rank})
    if expected is None:
        return None
    for candidate in _candidate_list(group):
        if _rank(candidate) == expected:
            return candidate
    return None


def _candidate_list(group: Mapping[str, object]) -> list[Mapping[str, object]]:
    candidates = group.get("candidates")
    if not isinstance(candidates, list):
        return []
    return [_mapping(candidate) for candidate in candidates]


def _candidate_summary(candidate: Mapping[str, object] | None) -> dict[str, object] | None:
    if candidate is None:
        return None
    action = _mapping(candidate.get("action"))
    validation = _mapping(candidate.get("validation"))
    scores = _mapping(candidate.get("scores"))
    evaluation = _mapping(candidate.get("evaluation_score"))
    return {
        "rank_index": candidate.get("rank_index"),
        "action": action.get("kind"),
        "file_path": action.get("file_path"),
        "symbol": action.get("symbol"),
        "start_line": action.get("start_line"),
        "end_line": action.get("end_line"),
        "node_kind": action.get("node_kind"),
        "params": action.get("params"),
        "reason": action.get("reason"),
        "validated": validation.get("validated"),
        "passed": validation.get("passed"),
        "score": evaluation.get("score"),
        "scores": {
            "model_score": scores.get("model_score"),
            "failure_hint_score": scores.get("failure_hint_score"),
            "ranker_score": scores.get("ranker_score"),
        },
    }


def _missing_feature_evidence(
    group: Mapping[str, object],
    *,
    top_candidate: Mapping[str, object] | None,
    shadow: Mapping[str, object] | None,
    v3_model: Mapping[str, object] | None,
) -> list[str]:
    missing: list[str] = []
    if shadow is None:
        missing.append("no_shadow_outcome")
    else:
        validation = _mapping(shadow.get("validation_outcome"))
        if validation.get("known") is not True:
            missing.append("shadow_validation_unknown")
    if v3_model is None:
        missing.append("v3_model_unavailable")
    candidate = _mapping(top_candidate)
    source = _mapping(candidate.get("source_context"))
    after = _mapping(candidate.get("candidate_after"))
    target = _mapping(candidate.get("target_context"))
    validation = _mapping(candidate.get("validation"))
    if source and source.get("embedding_available") is not True:
        missing.append("source_embedding_unavailable")
    if after and after.get("available") is not True:
        missing.append("candidate_after_unavailable")
    if after and after.get("embedding_available") is not True:
        missing.append("candidate_after_embedding_unavailable")
    if not target:
        missing.append("target_context_unavailable")
    if not _list(validation.get("failure_hints")):
        missing.append("failure_hints_unavailable")
    if not _candidate_list(group):
        missing.append("candidate_group_empty")
    return missing


def _top_comparison(
    *,
    production_top: Mapping[str, object] | None,
    scorer_top: Mapping[str, object],
    v3_top: Mapping[str, object] | None,
) -> str:
    production_rank = _rank(production_top)
    scorer_rank = _rank(scorer_top)
    v3_rank = _rank(v3_top)
    if scorer_rank is None and v3_rank is None:
        return "missing_scorer_top"
    if scorer_rank == production_rank and v3_rank == production_rank:
        return "all_same_top"
    if scorer_rank == production_rank:
        return "shadow_same_v3_differs"
    if v3_rank == production_rank:
        return "v3_same_shadow_differs"
    if scorer_rank == v3_rank and scorer_rank is not None:
        return "scorers_agree_differs_from_production"
    return "scorers_and_production_disagree"


def _candidate_file(
    *candidates: Mapping[str, object] | None,
) -> str:
    for candidate in candidates:
        record = _mapping(candidate)
        action = _mapping(record.get("action"))
        for value in (action.get("file_path"), record.get("file_path")):
            if isinstance(value, str) and value:
                return value
    return "unknown"


def _candidate_action_kind(
    *candidates: Mapping[str, object] | None,
) -> str:
    for candidate in candidates:
        record = _mapping(candidate)
        action = _mapping(record.get("action"))
        for value in (action.get("kind"), record.get("action")):
            if isinstance(value, str) and value:
                return value
    return "unknown"


def _rank(candidate: Mapping[str, object] | None) -> int | None:
    value = _mapping(candidate).get("rank_index")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(value, 0)
    return 0


def _format_counter(value: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={count}" for key, count in sorted(value.items())) or "none"


def _format_group_counts(value: object) -> str:
    rows = value if isinstance(value, list) else []
    parts = []
    for row in rows[:6]:
        item = _mapping(row)
        parts.append(f"{item.get('value')}={item.get('count')}")
    return ", ".join(parts) or "none"
