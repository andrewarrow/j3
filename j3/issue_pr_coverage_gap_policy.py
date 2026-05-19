"""VAL-003 shadow policy for issue/PR coverage-gap decoys.

The policy report is deliberately shadow-only. It answers two separate
questions:

* Can the ranker denominator use only behavior-observable hard negatives?
* Do remaining coverage-gap claims depend on decoy labels rather than
  observable validation evidence?
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_candidate_ranking import (
    DEFAULT_PYTEST_CANDIDATE_PATH,
    DEFAULT_SCRAPY_CANDIDATE_PATH,
    build_issue_pr_candidate_ranking_report,
)


VAL_003_POLICY_SCHEMA_VERSION = "issue-pr-coverage-gap-policy-v1"
DEFAULT_OUT_DIR = Path("/tmp/j3-val-003-coverage-gap-policy-probe")
DEFAULT_CANDIDATE_AFTER_BUNDLE_PATH = Path(
    "/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-bundle.json"
)
DEFAULT_DECOY_VALIDATION_BUNDLE_PATHS = (
    Path("/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-bundle.json"),
    Path("/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-bundle.json"),
)
DEFAULT_VALIDATION_STRENGTH_REPORT_PATH = Path(
    "/tmp/j3-val-002-validation-strength-probe/validation-strength-report.json"
)

COVERAGE_GAP_LABEL_LEAKAGE_BLOCKER = (
    "coverage_gap_decoy_indistinguishable_without_accepted_label_leakage"
)
LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER = (
    "coverage_gap_product_blocker_classification_depends_on_decoy_labels"
)


class IssuePrCoverageGapPolicyError(ValueError):
    """Raised when VAL-003 policy inputs are malformed."""


def build_coverage_gap_policy_report(
    *,
    pytest_candidate_path: Path = DEFAULT_PYTEST_CANDIDATE_PATH,
    scrapy_candidate_path: Path = DEFAULT_SCRAPY_CANDIDATE_PATH,
    decoy_validation_bundle_paths: Sequence[Path] = DEFAULT_DECOY_VALIDATION_BUNDLE_PATHS,
    validation_strength_report_path: Path = DEFAULT_VALIDATION_STRENGTH_REPORT_PATH,
    candidate_after_bundle_path: Path | None = DEFAULT_CANDIDATE_AFTER_BUNDLE_PATH,
) -> dict[str, object]:
    """Build the VAL-003 shadow-only ranking-denominator policy report."""

    started = time.monotonic()
    expanded_decoy_paths = tuple(path.expanduser() for path in decoy_validation_bundle_paths)
    expanded_strength_path = validation_strength_report_path.expanduser()
    candidate_after_path = _existing_candidate_after_path(candidate_after_bundle_path)

    ranking_report = build_issue_pr_candidate_ranking_report(
        pytest_candidate_path=pytest_candidate_path,
        scrapy_candidate_path=scrapy_candidate_path,
        candidate_after_bundle_path=candidate_after_path,
        decoy_validation_bundle_paths=expanded_decoy_paths,
    )
    strength_report = _load_json_object(expanded_strength_path)
    strength_index = _validation_strength_index(strength_report)

    rows = [
        _policy_row(row, strength_index=strength_index)
        for row in _list_of_mappings(ranking_report.get("rows"))
    ]
    input_runtime = _input_validation_runtime_seconds(expanded_decoy_paths, strength_report)
    summary = _summary(rows, input_runtime_seconds=input_runtime)
    summary["runtime_seconds"] = round(time.monotonic() - started, 3)

    return {
        "schema_version": VAL_003_POLICY_SCHEMA_VERSION,
        "record_kind": "issue_pr_coverage_gap_policy_report",
        "task_id": "VAL-003",
        "mode": "shadow_only_coverage_gap_policy_probe",
        "production_ranking_gate_changed": False,
        "inputs": {
            "pytest_candidate_path": str(pytest_candidate_path.expanduser().resolve()),
            "scrapy_candidate_path": str(scrapy_candidate_path.expanduser().resolve()),
            "candidate_after_bundle_path": str(candidate_after_path.resolve())
            if candidate_after_path is not None
            else None,
            "decoy_validation_bundle_paths": [
                str(path.resolve()) for path in expanded_decoy_paths
            ],
            "validation_strength_report_path": str(expanded_strength_path.resolve()),
        },
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": True,
        },
        "policy": {
            "strict_denominator": (
                "All accepted and decoy candidates remain in the ranking "
                "denominator. Passing decoys block pass@1/pass@k claims because "
                "observable validation does not distinguish them from accepted "
                "passing candidates."
            ),
            "behavior_negative_only_denominator": (
                "Only candidates that fail focused validation or a label-safe "
                "behavior probe are used as hard negatives. Pass-pass candidates "
                "are excluded from ranker metrics and retained as product "
                "blockers."
            ),
            "ranking_signal": (
                "Observable validation status and VAL-002 behavior-probe status "
                "only; accepted labels, residual labels, targeted mistakes, and "
                "accepted diff/test names are not scoring inputs."
            ),
        },
        "summary": summary,
        "rows": rows,
    }


def write_coverage_gap_policy_report(
    report: Mapping[str, object],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write VAL-003 JSON, JSONL, and markdown artifacts."""

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_json = output / "val-003-policy-report.json"
    decoys_jsonl = output / "val-003-decoy-policy-records.jsonl"
    report_md = output / "val-003-policy-report.md"

    report_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    decoy_lines: list[str] = []
    for row in _list_of_mappings(report.get("rows")):
        for decoy in _list_of_mappings(row.get("decoy_policy_records")):
            decoy_lines.append(json.dumps(decoy, sort_keys=True))
    decoys_jsonl.write_text(
        "\n".join(decoy_lines) + ("\n" if decoy_lines else ""),
        encoding="utf-8",
    )
    report_md.write_text(format_coverage_gap_policy_markdown(report), encoding="utf-8")
    return {
        "report_json": report_json,
        "decoys_jsonl": decoys_jsonl,
        "report_md": report_md,
    }


def format_coverage_gap_policy_markdown(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    strict = _mapping(summary.get("strict_ranking_readiness"))
    behavior = _mapping(summary.get("behavior_negative_only_ranking_readiness"))
    leakage = _mapping(summary.get("leakage_risk"))
    lines = [
        "# VAL-003 Coverage-Gap Decoy Policy Probe",
        "",
        "- Mode: shadow-only coverage-gap policy probe",
        "- Production ranking gate changed: false",
        f"- Strict readiness: {strict.get('status')}",
        f"- Strict pass@1: {_metric_text(strict.get('pass_at_1'))}",
        f"- Strict pass@k: {_metric_text(strict.get('pass_at_k'))}",
        f"- Behavior-negative-only readiness: {behavior.get('status')}",
        f"- Behavior-negative-only pass@1: {_metric_text(behavior.get('pass_at_1'))}",
        f"- Behavior-negative-only pass@k: {_metric_text(behavior.get('pass_at_k'))}",
        f"- Behavior-observable negatives: {summary.get('behavior_observable_negative_count')}",
        f"- Product blockers: {summary.get('product_blocker_count')}",
        f"- Runtime seconds: {summary.get('runtime_seconds')}",
        f"- Input validation runtime seconds: {summary.get('input_validation_runtime_seconds')}",
        f"- Overall leakage risk: {leakage.get('overall')}",
        f"- Separation depends on decoy labels: {_yes_no(leakage.get('separation_depends_on_decoy_labels'))}",
        "",
        "## Row Readiness",
        "",
        (
            "| Replay | Strict status | Strict blockers | Behavior-only status | "
            "Behavior pass@1 | Product blockers | Label-dependent blockers |"
        ),
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in _list_of_mappings(report.get("rows")):
        row_strict = _mapping(row.get("strict_ranking_readiness"))
        row_behavior = _mapping(row.get("behavior_negative_only_ranking_readiness"))
        strict_blockers = [
            str(blocker.get("reason", "unknown"))
            for blocker in _list_of_mappings(row_strict.get("blockers"))
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("replay_id", "")),
                    str(row_strict.get("status", "")),
                    ", ".join(strict_blockers),
                    str(row_behavior.get("status", "")),
                    _metric_text(row_behavior.get("pass_at_1")),
                    str(row.get("product_blocker_count", 0)),
                    str(row.get("label_dependent_product_blocker_count", 0)),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Decoy Classification",
            "",
            (
                "| Replay | Decoy | Validation | VAL-002 result | Policy class | "
                "Denominator action | Leakage risk | Blocker |"
            ),
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in _list_of_mappings(report.get("rows")):
        for decoy in _list_of_mappings(row.get("decoy_policy_records")):
            strength = _mapping(decoy.get("validation_strength_probe"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("replay_id", "")),
                        str(decoy.get("decoy_id", "")),
                        str(decoy.get("validation_status", "")),
                        str(strength.get("status", "")),
                        str(decoy.get("policy_class", "")),
                        str(decoy.get("denominator_action", "")),
                        str(decoy.get("leakage_risk", "")),
                        str(decoy.get("blocker_reason") or ""),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Conclusion", "", _conclusion(report), ""])
    return "\n".join(lines)


def _policy_row(
    row: Mapping[str, object],
    *,
    strength_index: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    candidates = _list_of_mappings(row.get("candidates"))
    accepted = [candidate for candidate in candidates if candidate.get("expected_accepted") is True]
    decoys = [candidate for candidate in candidates if candidate.get("expected_accepted") is not True]
    decoy_records = [
        _classify_decoy(decoy, strength_result=strength_index.get(str(decoy.get("candidate_id", ""))))
        for decoy in decoys
    ]
    behavior_negatives = [
        decoy
        for decoy in decoy_records
        if decoy.get("policy_class") == "behavior_observable_hard_negative"
    ]
    product_blockers = [
        decoy
        for decoy in decoy_records
        if decoy.get("policy_class") == "coverage_gap_product_blocker"
    ]
    unresolved = [
        decoy
        for decoy in decoy_records
        if decoy.get("policy_class") == "unresolved_non_negative_decoy"
    ]

    strict = _strict_readiness(
        accepted=accepted,
        decoy_records=decoy_records,
        product_blockers=product_blockers,
        unresolved=unresolved,
    )
    behavior = _behavior_negative_only_readiness(
        accepted=accepted,
        behavior_negatives=behavior_negatives,
        unresolved=unresolved,
    )
    label_dependent_count = sum(
        1
        for decoy in product_blockers
        if decoy.get("coverage_gap_claim_depends_on_decoy_labels") is True
    )
    return {
        "replay_id": str(row.get("replay_id", "")),
        "repo": str(row.get("repo", "")),
        "candidate_count": int(row.get("candidate_count", len(candidates))),
        "accepted_candidate_count": len(accepted),
        "decoy_count": len(decoys),
        "behavior_observable_negative_count": len(behavior_negatives),
        "product_blocker_count": len(product_blockers),
        "unresolved_non_negative_count": len(unresolved),
        "label_dependent_product_blocker_count": label_dependent_count,
        "strict_ranking_readiness": strict,
        "behavior_negative_only_ranking_readiness": behavior,
        "decoy_policy_records": decoy_records,
    }


def _classify_decoy(
    decoy: Mapping[str, object],
    *,
    strength_result: Mapping[str, object] | None,
) -> dict[str, object]:
    candidate_id = str(decoy.get("candidate_id", ""))
    validation_status = str(decoy.get("expected_validation_status") or "")
    if not validation_status:
        validation_status = str(_mapping(decoy.get("feature_inputs")).get("validation_status", ""))
    strength = _strength_summary(strength_result)

    if validation_status == "failed":
        return {
            **_decoy_base(decoy, validation_status, strength),
            "policy_class": "behavior_observable_hard_negative",
            "denominator_action": "include_as_ranker_hard_negative",
            "observable_evidence": ["focused_validation_failed"],
            "uses_decoy_labels_for_behavior_negative": False,
            "coverage_gap_claim_depends_on_decoy_labels": False,
            "leakage_risk": "low",
            "blocker_reason": None,
        }

    if _converted_by_label_safe_behavior_probe(strength_result):
        return {
            **_decoy_base(decoy, validation_status, strength),
            "policy_class": "behavior_observable_hard_negative",
            "denominator_action": "include_as_ranker_hard_negative",
            "observable_evidence": ["val_002_label_safe_behavior_probe_failed"],
            "uses_decoy_labels_for_behavior_negative": False,
            "coverage_gap_claim_depends_on_decoy_labels": False,
            "leakage_risk": _strength_leakage_risk(strength_result),
            "blocker_reason": None,
        }

    if _coverage_gap_product_blocker(strength_result):
        return {
            **_decoy_base(decoy, validation_status, strength),
            "policy_class": "coverage_gap_product_blocker",
            "denominator_action": "exclude_from_behavior_negative_denominator",
            "observable_evidence": [
                "focused_validation_passed",
                "val_002_label_safe_behavior_probe_passed",
            ],
            "uses_decoy_labels_for_behavior_negative": False,
            "coverage_gap_claim_depends_on_decoy_labels": True,
            "leakage_risk": "blocked_high",
            "blocker_reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
            "blocker_message": (
                "The candidate is not a behavior-observable hard negative. "
                "Calling it a coverage-gap decoy depends on residual/decoy labels "
                "or accepted-test structure rather than observable validation "
                "failure evidence."
            ),
        }

    blocker = "passing_decoy_without_label_safe_behavior_probe"
    if validation_status == "timeout":
        blocker = "timed_out_decoy_without_behavior_negative_evidence"
    elif validation_status not in {"passed", "failed", "timeout"}:
        blocker = "decoy_validation_status_not_observable"
    return {
        **_decoy_base(decoy, validation_status, strength),
        "policy_class": "unresolved_non_negative_decoy",
        "denominator_action": "block_behavior_negative_denominator",
        "observable_evidence": [],
        "uses_decoy_labels_for_behavior_negative": False,
        "coverage_gap_claim_depends_on_decoy_labels": False,
        "leakage_risk": "unknown",
        "blocker_reason": blocker,
    }


def _strict_readiness(
    *,
    accepted: Sequence[Mapping[str, object]],
    decoy_records: Sequence[Mapping[str, object]],
    product_blockers: Sequence[Mapping[str, object]],
    unresolved: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    blockers: list[dict[str, object]] = []
    if not accepted:
        blockers.append(_blocker("accepted_candidate", "accepted_candidate_missing"))
    if product_blockers:
        blockers.append(
            _blocker(
                "strict_denominator",
                "strict_denominator_contains_non_behavior_observable_decoys",
                count=len(product_blockers),
            )
        )
    label_dependent = [
        decoy
        for decoy in product_blockers
        if decoy.get("coverage_gap_claim_depends_on_decoy_labels") is True
    ]
    if label_dependent:
        blockers.append(
            _blocker(
                "leakage",
                LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER,
                count=len(label_dependent),
            )
        )
    if unresolved:
        blockers.append(
            _blocker(
                "validation",
                "strict_denominator_contains_unresolved_non_negative_decoys",
                count=len(unresolved),
            )
        )
    status = "blocked" if blockers else "ranked_shadow_only"
    if blockers:
        return {
            "status": status,
            "rankable": False,
            "rankable_candidate_count": None,
            "first_accepted_rank": None,
            "pass_at_1": None,
            "pass_at_k": None,
            "k": None,
            "blockers": blockers,
        }
    ranked = _rank_candidates(
        accepted=accepted,
        negative_records=decoy_records,
        scope="strict",
    )
    return {
        "status": status,
        "rankable": True,
        **ranked,
        "blockers": [],
    }


def _behavior_negative_only_readiness(
    *,
    accepted: Sequence[Mapping[str, object]],
    behavior_negatives: Sequence[Mapping[str, object]],
    unresolved: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    blockers: list[dict[str, object]] = []
    if not accepted:
        blockers.append(_blocker("accepted_candidate", "accepted_candidate_missing"))
    if not behavior_negatives:
        blockers.append(_blocker("behavior_negative_denominator", "no_behavior_observable_negatives"))
    if unresolved:
        blockers.append(
            _blocker(
                "validation",
                "behavior_negative_denominator_contains_unresolved_decoys",
                count=len(unresolved),
            )
        )
    if blockers:
        return {
            "status": "blocked",
            "rankable": False,
            "rankable_candidate_count": None,
            "first_accepted_rank": None,
            "pass_at_1": None,
            "pass_at_k": None,
            "k": None,
            "blockers": blockers,
        }
    ranked = _rank_candidates(
        accepted=accepted,
        negative_records=behavior_negatives,
        scope="behavior_negative_only",
    )
    return {
        "status": "ranked_shadow_only",
        "rankable": True,
        **ranked,
        "blockers": [],
    }


def _rank_candidates(
    *,
    accepted: Sequence[Mapping[str, object]],
    negative_records: Sequence[Mapping[str, object]],
    scope: str,
) -> dict[str, object]:
    ranked: list[dict[str, object]] = []
    for candidate in accepted:
        status = str(candidate.get("expected_validation_status") or "")
        score = 1.0 if status == "passed" else 0.0
        ranked.append(
            {
                "candidate_id": str(candidate.get("candidate_id", "")),
                "candidate_kind": str(candidate.get("candidate_kind", "")),
                "expected_accepted": True,
                "observable_validation_class": status or "unknown",
                "score": score,
                "score_inputs": ["validation_status"],
            }
        )
    for decoy in negative_records:
        evidence = _string_list(decoy.get("observable_evidence"))
        ranked.append(
            {
                "candidate_id": str(decoy.get("candidate_id", "")),
                "candidate_kind": "realistic_decoy",
                "expected_accepted": False,
                "observable_validation_class": "behavior_negative",
                "score": 0.0,
                "score_inputs": evidence,
            }
        )
    ranked.sort(key=lambda item: (-_float_value(item.get("score")), str(item.get("candidate_id"))))
    for index, candidate in enumerate(ranked, start=1):
        candidate["rank"] = index
    first_accepted_rank = next(
        (
            int(candidate["rank"])
            for candidate in ranked
            if candidate.get("expected_accepted") is True
        ),
        None,
    )
    k = len(ranked)
    return {
        "scope": scope,
        "rankable_candidate_count": k,
        "first_accepted_rank": first_accepted_rank,
        "pass_at_1": 1.0 if first_accepted_rank == 1 else 0.0,
        "pass_at_k": 1.0 if first_accepted_rank is not None and first_accepted_rank <= k else 0.0,
        "k": k,
        "ranked_candidates": ranked,
    }


def _summary(
    rows: Sequence[Mapping[str, object]],
    *,
    input_runtime_seconds: float,
) -> dict[str, object]:
    strict_rankable = [
        row
        for row in rows
        if _mapping(row.get("strict_ranking_readiness")).get("rankable") is True
    ]
    behavior_rankable = [
        row
        for row in rows
        if _mapping(row.get("behavior_negative_only_ranking_readiness")).get("rankable")
        is True
    ]
    label_dependent_count = sum(
        _int_value(row.get("label_dependent_product_blocker_count")) for row in rows
    )
    product_blocker_count = sum(_int_value(row.get("product_blocker_count")) for row in rows)
    blocker_counts = _blocker_counts(rows)
    return {
        "rows": len(rows),
        "candidate_count": sum(_int_value(row.get("candidate_count")) for row in rows),
        "decoy_count": sum(_int_value(row.get("decoy_count")) for row in rows),
        "behavior_observable_negative_count": sum(
            _int_value(row.get("behavior_observable_negative_count")) for row in rows
        ),
        "product_blocker_count": product_blocker_count,
        "unresolved_non_negative_count": sum(
            _int_value(row.get("unresolved_non_negative_count")) for row in rows
        ),
        "blocker_counts": blocker_counts,
        "strict_ranking_readiness": {
            "status": "ranked_shadow_only"
            if len(strict_rankable) == len(rows)
            else "blocked",
            "rankable_rows": len(strict_rankable),
            "blocked_rows": len(rows) - len(strict_rankable),
            "pass_at_1": _mean_readiness_metric(strict_rankable, "strict_ranking_readiness", "pass_at_1")
            if len(strict_rankable) == len(rows)
            else None,
            "pass_at_k": _mean_readiness_metric(strict_rankable, "strict_ranking_readiness", "pass_at_k")
            if len(strict_rankable) == len(rows)
            else None,
        },
        "behavior_negative_only_ranking_readiness": {
            "status": "ranked_shadow_only"
            if len(behavior_rankable) == len(rows)
            else "blocked",
            "rankable_rows": len(behavior_rankable),
            "blocked_rows": len(rows) - len(behavior_rankable),
            "pass_at_1": _mean_readiness_metric(
                behavior_rankable,
                "behavior_negative_only_ranking_readiness",
                "pass_at_1",
            )
            if len(behavior_rankable) == len(rows)
            else None,
            "pass_at_k": _mean_readiness_metric(
                behavior_rankable,
                "behavior_negative_only_ranking_readiness",
                "pass_at_k",
            )
            if len(behavior_rankable) == len(rows)
            else None,
        },
        "input_validation_runtime_seconds": round(input_runtime_seconds, 3),
        "leakage_risk": {
            "behavior_negative_denominator": "low",
            "coverage_gap_classification": "blocked_high"
            if label_dependent_count
            else "low",
            "overall": "blocked_high" if label_dependent_count else "low",
            "separation_depends_on_decoy_labels": bool(label_dependent_count),
            "blocker_reason": LABEL_DEPENDENT_COVERAGE_GAP_BLOCKER
            if label_dependent_count
            else None,
            "label_dependent_product_blocker_count": label_dependent_count,
        },
    }


def _blocker_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for readiness_key in (
            "strict_ranking_readiness",
            "behavior_negative_only_ranking_readiness",
        ):
            readiness = _mapping(row.get(readiness_key))
            for blocker in _list_of_mappings(readiness.get("blockers")):
                reason = str(blocker.get("reason", "unknown"))
                counts[reason] = counts.get(reason, 0) + _int_value(blocker.get("count"), 1)
    return dict(sorted(counts.items()))


def _decoy_base(
    decoy: Mapping[str, object],
    validation_status: str,
    strength: Mapping[str, object],
) -> dict[str, object]:
    return {
        "candidate_id": str(decoy.get("candidate_id", "")),
        "decoy_id": _decoy_id(decoy),
        "validation_status": validation_status or "unknown",
        "targeted_mistakes_present": bool(_string_list(decoy.get("targeted_mistakes"))),
        "residual_labels_present": bool(_string_list(decoy.get("residual_labels"))),
        "validation_strength_probe": dict(strength),
    }


def _strength_summary(strength_result: Mapping[str, object] | None) -> dict[str, object]:
    if strength_result is None:
        return {"status": "not_available"}
    if _converted_by_label_safe_behavior_probe(strength_result):
        status = "converted_to_behavior_failure"
    elif _coverage_gap_product_blocker(strength_result):
        status = "passed_behavior_probe_product_blocker"
    else:
        status = "available_inconclusive"
    return {
        "status": status,
        "accepted_status": str(strength_result.get("accepted_status", "")),
        "decoy_status": str(strength_result.get("decoy_status", "")),
        "accepted_preserved": strength_result.get("accepted_preserved"),
        "passing_decoy_converted_to_failure": strength_result.get(
            "passing_decoy_converted_to_failure"
        ),
        "product_gate_blocker": strength_result.get("product_gate_blocker"),
        "leakage_risk": strength_result.get("leakage_risk"),
    }


def _converted_by_label_safe_behavior_probe(
    strength_result: Mapping[str, object] | None,
) -> bool:
    if strength_result is None:
        return False
    return (
        strength_result.get("accepted_preserved") is True
        and strength_result.get("passing_decoy_converted_to_failure") is True
        and strength_result.get("decoy_status") == "failed"
    )


def _coverage_gap_product_blocker(strength_result: Mapping[str, object] | None) -> bool:
    if strength_result is None:
        return False
    return strength_result.get("product_gate_blocker") == COVERAGE_GAP_LABEL_LEAKAGE_BLOCKER


def _strength_leakage_risk(strength_result: Mapping[str, object] | None) -> str:
    risk = str(_mapping(strength_result).get("leakage_risk", ""))
    return risk or "unknown"


def _validation_strength_index(report: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    results = _list_of_mappings(report.get("results"))
    return {
        str(result.get("candidate_id", "")): result
        for result in results
        if str(result.get("candidate_id", ""))
    }


def _input_validation_runtime_seconds(
    decoy_bundle_paths: Sequence[Path],
    strength_report: Mapping[str, object],
) -> float:
    total = _float_value(_mapping(strength_report.get("summary")).get("runtime_seconds"))
    for path in decoy_bundle_paths:
        bundle = _load_json_object(path)
        for candidate in _list_of_mappings(bundle.get("candidates")):
            total += _float_value(_mapping(candidate.get("validation")).get("runtime_seconds"))
    return total


def _existing_candidate_after_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    expanded = path.expanduser()
    if not expanded.is_file():
        raise IssuePrCoverageGapPolicyError(
            f"candidate-after bundle missing: {expanded}"
        )
    return expanded


def _load_json_object(path: Path) -> dict[str, object]:
    expanded = path.expanduser()
    if not expanded.is_file():
        raise IssuePrCoverageGapPolicyError(f"VAL-003 input artifact missing: {expanded}")
    payload = json.loads(expanded.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrCoverageGapPolicyError(f"VAL-003 input must be a JSON object: {expanded}")
    return payload


def _blocker(field: str, reason: str, *, count: int = 1) -> dict[str, object]:
    return {"field": field, "reason": reason, "count": count}


def _mean_readiness_metric(
    rows: Sequence[Mapping[str, object]],
    readiness_key: str,
    metric_key: str,
) -> float | None:
    values = [
        _float_value(_mapping(row.get(readiness_key)).get(metric_key))
        for row in rows
        if _mapping(row.get(readiness_key)).get(metric_key) is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _decoy_id(decoy: Mapping[str, object]) -> str:
    candidate_id = str(decoy.get("candidate_id", ""))
    if ":" in candidate_id:
        return candidate_id.rsplit(":", 1)[1]
    return candidate_id


def _conclusion(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    behavior = _mapping(summary.get("behavior_negative_only_ranking_readiness"))
    leakage = _mapping(summary.get("leakage_risk"))
    if (
        behavior.get("status") == "ranked_shadow_only"
        and leakage.get("separation_depends_on_decoy_labels") is True
    ):
        return (
            "Behavior-observable hard negatives can support shadow-only "
            "pass@1/pass@k metrics, but strict issue/PR ranking is still blocked. "
            "The remaining pass-pass product blockers cannot be honestly named "
            "coverage-gap decoys from validation evidence alone; that claim "
            "depends on decoy labels or accepted-test structure."
        )
    if behavior.get("status") == "ranked_shadow_only":
        return (
            "Behavior-observable hard negatives can support shadow-only "
            "pass@1/pass@k metrics, and no label-dependent coverage-gap blocker "
            "was observed in this artifact set."
        )
    return (
        "The artifact set does not yet provide a label-safe behavior-negative "
        "denominator for issue/PR ranking metrics."
    )


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


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
        "--pytest-candidate",
        type=Path,
        default=DEFAULT_PYTEST_CANDIDATE_PATH,
        help="Path to the accepted pytest issue/PR candidate.json artifact.",
    )
    parser.add_argument(
        "--scrapy-candidate",
        type=Path,
        default=DEFAULT_SCRAPY_CANDIDATE_PATH,
        help="Path to the accepted Scrapy issue/PR candidate.json artifact.",
    )
    parser.add_argument(
        "--decoy-validation-bundle",
        type=Path,
        action="append",
        default=[],
        help="DATA-039/DATA-040 decoy validation bundle. May be repeated.",
    )
    parser.add_argument(
        "--validation-strength-report",
        type=Path,
        default=DEFAULT_VALIDATION_STRENGTH_REPORT_PATH,
        help="VAL-002 validation-strength report JSON.",
    )
    parser.add_argument(
        "--candidate-after-bundle",
        type=Path,
        default=DEFAULT_CANDIDATE_AFTER_BUNDLE_PATH,
        help="DATA-038 candidate-after bundle JSON.",
    )
    parser.add_argument(
        "--no-candidate-after-bundle",
        action="store_true",
        help="Do not load a candidate-after bundle.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for VAL-003 report artifacts.",
    )
    args = parser.parse_args(argv)

    candidate_after_bundle_path = (
        None if args.no_candidate_after_bundle else args.candidate_after_bundle
    )
    report = build_coverage_gap_policy_report(
        pytest_candidate_path=args.pytest_candidate,
        scrapy_candidate_path=args.scrapy_candidate,
        decoy_validation_bundle_paths=tuple(args.decoy_validation_bundle)
        if args.decoy_validation_bundle
        else DEFAULT_DECOY_VALIDATION_BUNDLE_PATHS,
        validation_strength_report_path=args.validation_strength_report,
        candidate_after_bundle_path=candidate_after_bundle_path,
    )
    artifacts = write_coverage_gap_policy_report(report, out_dir=args.out_dir)
    print(json.dumps({key: str(path) for key, path in artifacts.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
