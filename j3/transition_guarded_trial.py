"""Decide guarded transition-scorer trial eligibility from matrix evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from j3.transition_action_scoring import GATE_READY_FOR_GUARDED_OPT_IN
from j3.transition_shadow_matrix import MATRIX_SUMMARY, TRANSITION_SHADOW_MATRIX_VERSION
from j3.transition_shadow_suite import HOSTED_USAGE_FIELDS


TRANSITION_GUARDED_TRIAL_DECISION_VERSION = "transition-guarded-trial-decision-v1"
DECISION_REMAIN_SHADOW_ONLY = "remain_shadow_only"
DECISION_GUARDED_OPT_IN_TRIAL = "guarded_opt_in_trial"


def decide_transition_guarded_trial(*, matrix_dir: Path) -> dict[str, object]:
    """Return a conservative guarded-trial decision for a matrix output."""

    matrix = matrix_dir.expanduser().resolve()
    summary = _load_matrix_summary(matrix)
    suites = _list(summary.get("suites"))
    totals = _mapping(summary.get("totals"))
    usage = _mapping(summary.get("usage"))

    checks = _decision_checks(summary=summary, suites=suites, totals=totals, usage=usage)
    blockers = [check["reason"] for check in checks if check["passed"] is not True]
    eligible = not blockers
    decision = (
        DECISION_GUARDED_OPT_IN_TRIAL if eligible else DECISION_REMAIN_SHADOW_ONLY
    )

    return {
        "schema_version": TRANSITION_GUARDED_TRIAL_DECISION_VERSION,
        "matrix": str(matrix),
        "matrix_summary": str(matrix / MATRIX_SUMMARY),
        "decision": decision,
        "eligible_for_guarded_opt_in_trial": eligible,
        "trial_scope": (
            "narrow_opt_in_transition_ranking" if eligible else "shadow_only"
        ),
        "summary": {
            "suite_count": totals.get("suite_count", len(suites)),
            "task_count": totals.get("task_count", 0),
            "held_out_group_count": totals.get("held_out_group_count", 0),
            "residual_count": totals.get("residual_count", 0),
            "baseline_residual_count": totals.get("baseline_residual_count", 0),
            "zero_hosted_usage": summary.get("zero_hosted_usage") is True,
        },
        "checks": checks,
        "blockers": blockers,
        "suites": [_suite_decision_record(suite) for suite in suites],
        "usage": {field: _int(usage.get(field)) for field in HOSTED_USAGE_FIELDS},
    }


def format_transition_guarded_trial_decision(decision: Mapping[str, object]) -> str:
    """Format a guarded-trial decision for CLI output."""

    summary = _mapping(decision.get("summary"))
    lines = [
        "j3 decide-transition-guarded-trial complete",
        f"matrix: {decision.get('matrix')}",
        f"decision: {decision.get('decision')}",
        "eligible for guarded opt-in trial: "
        f"{str(decision.get('eligible_for_guarded_opt_in_trial') is True).lower()}",
        f"trial scope: {decision.get('trial_scope')}",
        f"suites: {summary.get('suite_count', 0)}",
        f"held-out groups: {summary.get('held_out_group_count', 0)}",
        f"residuals: {summary.get('residual_count', 0)}",
        f"zero hosted usage: {str(summary.get('zero_hosted_usage') is True).lower()}",
    ]
    blockers = [str(blocker) for blocker in _list(decision.get("blockers"))]
    if blockers:
        lines.append("blockers:")
        for blocker in blockers:
            lines.append(f"  - {blocker}")
    return "\n".join(lines)


def _decision_checks(
    *,
    summary: Mapping[str, object],
    suites: list[Any],
    totals: Mapping[str, object],
    usage: Mapping[str, object],
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    checks.append(
        _check(
            "matrix_schema",
            summary.get("schema_version") == TRANSITION_SHADOW_MATRIX_VERSION,
            "matrix summary is not a transition shadow matrix run",
        )
    )
    checks.append(
        _check(
            "has_suite_evidence",
            len(suites) > 0 and _int(totals.get("suite_count")) == len(suites),
            "matrix summary must contain at least one suite with matching totals",
        )
    )
    checks.append(
        _check(
            "has_held_out_groups",
            _int(totals.get("held_out_group_count")) > 0
            and all(_int(_mapping(suite).get("held_out_group_count")) > 0 for suite in suites),
            "every suite must include held-out validation groups",
        )
    )
    checks.append(
        _check(
            "zero_hosted_usage",
            summary.get("zero_hosted_usage") is True
            and all(_int(usage.get(field)) == 0 for field in HOSTED_USAGE_FIELDS),
            "matrix evidence must assert zero hosted API/context usage",
        )
    )
    checks.append(
        _check(
            "all_suite_gates_ready_for_guarded_opt_in",
            all(
                _mapping(suite).get("v3_gate") == GATE_READY_FOR_GUARDED_OPT_IN
                and _mapping(suite).get("eligible_for_guarded_opt_in") is True
                for suite in suites
            ),
            "all suite V3 gates must be ready_for_guarded_opt_in",
        )
    )
    checks.append(
        _check(
            "no_matrix_residuals",
            _int(totals.get("residual_count")) == 0
            and all(_int(_mapping(suite).get("residual_count")) == 0 for suite in suites),
            "matrix and per-suite residual counts must be zero",
        )
    )
    return checks


def _suite_decision_record(suite: object) -> dict[str, object]:
    record = _mapping(suite)
    return {
        "id": record.get("id"),
        "v3_gate": record.get("v3_gate"),
        "eligible_for_guarded_opt_in": record.get("eligible_for_guarded_opt_in"),
        "held_out_group_count": record.get("held_out_group_count", 0),
        "residual_count": record.get("residual_count", 0),
        "baseline_residual_count": record.get("baseline_residual_count", 0),
        "zero_hosted_usage": record.get("zero_hosted_usage") is True,
    }


def _load_matrix_summary(matrix: Path) -> dict[str, object]:
    if not matrix.exists():
        raise FileNotFoundError(f"matrix output directory does not exist: {matrix}")
    if not matrix.is_dir():
        raise NotADirectoryError(f"matrix output path is not a directory: {matrix}")
    summary_path = matrix / MATRIX_SUMMARY
    if not summary_path.exists():
        raise FileNotFoundError(f"matrix summary does not exist: {summary_path}")
    if not summary_path.is_file():
        raise IsADirectoryError(f"matrix summary path is not a file: {summary_path}")
    loaded = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"matrix summary must be a JSON object: {summary_path}")
    return loaded


def _check(name: str, passed: bool, reason: str) -> dict[str, object]:
    return {"name": name, "passed": passed, "reason": None if passed else reason}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
