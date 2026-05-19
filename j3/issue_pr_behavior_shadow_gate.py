"""Reusable VAL-004 shadow gate for behavior-negative-only issue/PR metrics."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_coverage_gap_policy import LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER


VAL_004_SHADOW_GATE_SCHEMA_VERSION = "issue-pr-behavior-shadow-gate-v1"
DEFAULT_POLICY_REPORT_PATH = Path(
    "/tmp/j3-val-003-coverage-gap-policy-probe/val-003-policy-report.json"
)
DEFAULT_OUT_DIR = Path("/tmp/j3-val-004-behavior-shadow-gate")


class IssuePrBehaviorShadowGateError(ValueError):
    """Raised when a behavior shadow gate input is malformed."""


def build_issue_pr_behavior_shadow_gate(
    policy_report: Mapping[str, object],
) -> dict[str, object]:
    """Build a reusable shadow gate from VAL-003-style policy rows.

    The returned record intentionally never promotes behavior-negative-only
    metrics to a production ranking gate. Those metrics are shadow evidence
    until strict issue/PR ranking can handle coverage-gap product blockers
    without label-dependent classification.
    """

    started = time.monotonic()
    rows = _list_of_mappings(policy_report.get("rows"))
    if not rows:
        raise IssuePrBehaviorShadowGateError("policy report must include rows")

    row_gates = [_row_gate(row) for row in rows]
    strict = _aggregate_readiness(row_gates, key="strict_ranking_readiness")
    behavior = _aggregate_readiness(
        row_gates,
        key="behavior_negative_only_ranking_readiness",
        shadow_only=True,
    )
    blocker_counts = _blocker_counts(row_gates)
    product_blocker_count = sum(
        _int_value(row.get("product_blocker_count")) for row in row_gates
    )
    behavior_negative_count = sum(
        _int_value(row.get("behavior_observable_negative_count")) for row in row_gates
    )
    label_dependent_count = sum(
        _int_value(row.get("label_dependent_product_blocker_count"))
        for row in row_gates
    )
    leakage = _leakage_risk(
        label_dependent_product_blocker_count=label_dependent_count,
        behavior_readiness=behavior,
    )
    production_gate_stance = _production_gate_stance(
        strict_readiness=strict,
        behavior_readiness=behavior,
        leakage_risk=leakage,
        blocker_counts=blocker_counts,
    )

    return {
        "schema_version": VAL_004_SHADOW_GATE_SCHEMA_VERSION,
        "record_kind": "issue_pr_behavior_negative_shadow_gate",
        "task_id": "VAL-004",
        "mode": "shadow_only_behavior_negative_issue_pr_gate",
        "source_task_id": str(policy_report.get("task_id") or "VAL-003"),
        "production_ranking_gate_changed": False,
        "summary": {
            "rows": len(row_gates),
            "candidate_count": sum(
                _int_value(row.get("candidate_count")) for row in row_gates
            ),
            "decoy_count": sum(_int_value(row.get("decoy_count")) for row in row_gates),
            "behavior_observable_negative_count": behavior_negative_count,
            "product_blocker_count": product_blocker_count,
            "label_dependent_product_blocker_count": label_dependent_count,
            "blocker_counts": blocker_counts,
            "strict_ranking_readiness": strict,
            "behavior_negative_only_ranking_readiness": behavior,
            "leakage_risk": leakage,
            "runtime_seconds": round(time.monotonic() - started, 3),
            "input_runtime_seconds": _input_runtime_seconds(policy_report),
            "production_gate_stance": production_gate_stance,
        },
        "production_gate_stance": production_gate_stance,
        "rows": row_gates,
    }


def load_issue_pr_behavior_shadow_gate_policy_report(path: Path) -> dict[str, object]:
    expanded = path.expanduser()
    if not expanded.is_file():
        raise IssuePrBehaviorShadowGateError(f"policy report missing: {expanded}")
    payload = json.loads(expanded.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrBehaviorShadowGateError(
            f"policy report must be a JSON object: {expanded}"
        )
    return payload


def write_issue_pr_behavior_shadow_gate(
    gate: Mapping[str, object],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write VAL-004 JSON, row JSONL, and markdown artifacts."""

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    gate_json = output / "val-004-shadow-gate.json"
    rows_jsonl = output / "val-004-shadow-gate-rows.jsonl"
    gate_md = output / "val-004-shadow-gate.md"

    gate_json.write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        json.dumps(row, sort_keys=True)
        for row in _list_of_mappings(gate.get("rows"))
    ]
    rows_jsonl.write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8",
    )
    gate_md.write_text(
        format_issue_pr_behavior_shadow_gate_markdown(gate),
        encoding="utf-8",
    )
    return {
        "gate_json": gate_json,
        "rows_jsonl": rows_jsonl,
        "gate_md": gate_md,
    }


def format_issue_pr_behavior_shadow_gate_markdown(
    gate: Mapping[str, object],
) -> str:
    summary = _mapping(gate.get("summary"))
    strict = _mapping(summary.get("strict_ranking_readiness"))
    behavior = _mapping(summary.get("behavior_negative_only_ranking_readiness"))
    leakage = _mapping(summary.get("leakage_risk"))
    stance = _mapping(gate.get("production_gate_stance"))
    lines = [
        "# VAL-004 Behavior-Negative Issue/PR Shadow Gate",
        "",
        "- Mode: shadow-only behavior-negative issue/PR gate",
        "- Production ranking gate changed: false",
        f"- Production decision: {stance.get('decision')}",
        f"- Strict readiness: {strict.get('status')}",
        f"- Strict pass@1: {_metric_text(strict.get('pass_at_1'))}",
        f"- Strict pass@k: {_metric_text(strict.get('pass_at_k'))}",
        f"- Behavior-negative-only readiness: {behavior.get('status')}",
        f"- Behavior-negative-only pass@1: {_metric_text(behavior.get('pass_at_1'))}",
        f"- Behavior-negative-only pass@k: {_metric_text(behavior.get('pass_at_k'))}",
        f"- Product blockers: {summary.get('product_blocker_count')}",
        f"- Behavior-observable negatives: {summary.get('behavior_observable_negative_count')}",
        f"- Leakage risk: {leakage.get('overall')}",
        f"- Runtime seconds: {summary.get('runtime_seconds')}",
        f"- Input runtime seconds: {summary.get('input_runtime_seconds')}",
        "",
        "## Production Stance",
        "",
        f"- Strict issue/PR ranking: {stance.get('strict_issue_pr_ranking')}",
        f"- Behavior-negative-only ranking: {stance.get('behavior_negative_only_ranking')}",
        f"- Production ranking allowed: {_yes_no(stance.get('production_ranking_allowed'))}",
        f"- Shadow metrics allowed: {_yes_no(stance.get('shadow_metrics_allowed'))}",
        f"- Reason: {stance.get('reason')}",
        "",
        "## Row Gates",
        "",
        (
            "| Replay | Strict status | Behavior-only status | Behavior pass@1 | "
            "Behavior pass@k | Product blockers | Label-dependent blockers |"
        ),
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in _list_of_mappings(gate.get("rows")):
        row_strict = _mapping(row.get("strict_ranking_readiness"))
        row_behavior = _mapping(row.get("behavior_negative_only_ranking_readiness"))
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("replay_id", "")),
                    str(row_strict.get("status", "")),
                    str(row_behavior.get("status", "")),
                    _metric_text(row_behavior.get("pass_at_1")),
                    _metric_text(row_behavior.get("pass_at_k")),
                    str(row.get("product_blocker_count", 0)),
                    str(row.get("label_dependent_product_blocker_count", 0)),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _row_gate(row: Mapping[str, object]) -> dict[str, object]:
    strict = _readiness_copy(_mapping(row.get("strict_ranking_readiness")))
    behavior = _readiness_copy(
        _mapping(row.get("behavior_negative_only_ranking_readiness"))
    )
    strict_blocker_reasons = _readiness_blocker_reasons(strict)
    label_dependent_count = _int_value(row.get("label_dependent_product_blocker_count"))
    if (
        label_dependent_count
        and LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER not in strict_blocker_reasons
    ):
        strict.setdefault("blockers", []).append(
            {
                "field": "leakage",
                "reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
                "count": label_dependent_count,
            }
        )
        strict["status"] = "blocked"
        strict["rankable"] = False
        strict["pass_at_1"] = None
        strict["pass_at_k"] = None

    return {
        "replay_id": str(row.get("replay_id", "")),
        "repo": str(row.get("repo", "")),
        "candidate_count": _int_value(row.get("candidate_count")),
        "decoy_count": _int_value(row.get("decoy_count")),
        "behavior_observable_negative_count": _int_value(
            row.get("behavior_observable_negative_count")
        ),
        "product_blocker_count": _int_value(row.get("product_blocker_count")),
        "label_dependent_product_blocker_count": label_dependent_count,
        "strict_ranking_readiness": strict,
        "behavior_negative_only_ranking_readiness": behavior,
        "production_gate_stance": {
            "strict_issue_pr_ranking": "blocked"
            if strict.get("status") != "ranked_shadow_only"
            else "shadow_ranked_not_production",
            "behavior_negative_only_ranking": "shadow_only"
            if behavior.get("status") == "ranked_shadow_only"
            else "blocked",
            "production_ranking_allowed": False,
        },
    }


def _readiness_copy(readiness: Mapping[str, object]) -> dict[str, object]:
    if not readiness:
        return {
            "status": "blocked",
            "rankable": False,
            "rankable_candidate_count": None,
            "first_accepted_rank": None,
            "pass_at_1": None,
            "pass_at_k": None,
            "k": None,
            "blockers": [
                {
                    "field": "policy_row",
                    "reason": "readiness_record_missing",
                    "count": 1,
                }
            ],
        }
    copied = json.loads(json.dumps(readiness, sort_keys=True))
    if not isinstance(copied, dict):
        raise IssuePrBehaviorShadowGateError("readiness record must be an object")
    copied.setdefault("blockers", [])
    return copied


def _aggregate_readiness(
    rows: Sequence[Mapping[str, object]],
    *,
    key: str,
    shadow_only: bool = False,
) -> dict[str, object]:
    rankable = [
        _mapping(row.get(key))
        for row in rows
        if _mapping(row.get(key)).get("rankable") is True
    ]
    all_ranked = len(rankable) == len(rows)
    status = "ranked_shadow_only" if all_ranked else "blocked"
    pass_at_1 = _mean_metric(rankable, "pass_at_1") if all_ranked else None
    pass_at_k = _mean_metric(rankable, "pass_at_k") if all_ranked else None
    result: dict[str, object] = {
        "status": status,
        "rankable_rows": len(rankable),
        "blocked_rows": len(rows) - len(rankable),
        "pass_at_1": pass_at_1,
        "pass_at_k": pass_at_k,
        "production_eligible": False,
    }
    if shadow_only and status == "ranked_shadow_only":
        result["shadow_only_reason"] = (
            "behavior-negative-only metrics exclude coverage-gap product "
            "blockers and cannot change production ranking"
        )
    return result


def _production_gate_stance(
    *,
    strict_readiness: Mapping[str, object],
    behavior_readiness: Mapping[str, object],
    leakage_risk: Mapping[str, object],
    blocker_counts: Mapping[str, int],
) -> dict[str, object]:
    strict_ranked = strict_readiness.get("status") == "ranked_shadow_only"
    behavior_ranked = behavior_readiness.get("status") == "ranked_shadow_only"
    label_dependent = (
        leakage_risk.get("separation_depends_on_decoy_labels") is True
        or LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER in blocker_counts
    )
    if label_dependent:
        decision = "remain_shadow_only"
        strict_stance = "blocked"
        reason = LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER
    elif not strict_ranked:
        decision = "remain_shadow_only"
        strict_stance = "blocked"
        reason = "strict_issue_pr_ranking_blocked"
    else:
        decision = "remain_shadow_only"
        strict_stance = "shadow_ranked_not_production"
        reason = "no_production_issue_pr_ranker_approval"

    blockers = [
        {"reason": reason, "count": _int_value(blocker_counts.get(reason), 1)}
    ]
    if label_dependent and reason != LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER:
        blockers.append(
            {
                "reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
                "count": _int_value(
                    blocker_counts.get(LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER),
                    1,
                ),
            }
        )
    return {
        "decision": decision,
        "strict_issue_pr_ranking": strict_stance,
        "behavior_negative_only_ranking": "shadow_only" if behavior_ranked else "blocked",
        "production_ranking_allowed": False,
        "behavior_negative_only_production_allowed": False,
        "shadow_metrics_allowed": behavior_ranked,
        "production_ranking_gate_changed": False,
        "reason": reason,
        "blockers": blockers,
    }


def _leakage_risk(
    *,
    label_dependent_product_blocker_count: int,
    behavior_readiness: Mapping[str, object],
) -> dict[str, object]:
    return {
        "behavior_negative_denominator": "low"
        if behavior_readiness.get("status") == "ranked_shadow_only"
        else "unknown",
        "coverage_gap_classification": "blocked_high"
        if label_dependent_product_blocker_count
        else "low",
        "overall": "blocked_high" if label_dependent_product_blocker_count else "low",
        "separation_depends_on_decoy_labels": bool(label_dependent_product_blocker_count),
        "blocker_reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER
        if label_dependent_product_blocker_count
        else None,
        "label_dependent_product_blocker_count": label_dependent_product_blocker_count,
    }


def _blocker_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for key in (
            "strict_ranking_readiness",
            "behavior_negative_only_ranking_readiness",
        ):
            readiness = _mapping(row.get(key))
            for blocker in _list_of_mappings(readiness.get("blockers")):
                reason = str(blocker.get("reason", "unknown"))
                counts[reason] = counts.get(reason, 0) + _int_value(
                    blocker.get("count"),
                    1,
                )
    return dict(sorted(counts.items()))


def _readiness_blocker_reasons(readiness: Mapping[str, object]) -> set[str]:
    return {
        str(blocker.get("reason", "unknown"))
        for blocker in _list_of_mappings(readiness.get("blockers"))
    }


def _input_runtime_seconds(policy_report: Mapping[str, object]) -> float | None:
    summary = _mapping(policy_report.get("summary"))
    runtime = summary.get("runtime_seconds")
    input_runtime = summary.get("input_validation_runtime_seconds")
    values = [
        _float_value(value)
        for value in (runtime, input_runtime)
        if value is not None
    ]
    if not values:
        return None
    return round(sum(values), 3)


def _mean_metric(rows: Sequence[Mapping[str, object]], key: str) -> float | None:
    values = [
        _float_value(row.get(key))
        for row in rows
        if row.get(key) is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _metric_text(value: object) -> str:
    if value is None:
        return "blocked"
    return str(value)


def _yes_no(value: object) -> str:
    return "yes" if value is True else "no"


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy-report",
        type=Path,
        default=DEFAULT_POLICY_REPORT_PATH,
        help="Path to a VAL-003-style policy report JSON artifact.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for VAL-004 gate artifacts.",
    )
    args = parser.parse_args(argv)

    policy_report = load_issue_pr_behavior_shadow_gate_policy_report(args.policy_report)
    gate = build_issue_pr_behavior_shadow_gate(policy_report)
    artifacts = write_issue_pr_behavior_shadow_gate(gate, out_dir=args.out_dir)
    print(json.dumps({name: str(path) for name, path in artifacts.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
