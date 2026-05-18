"""Shadow issue/PR candidate ranking decoy harness.

This module deliberately does not make a production ranking decision. It builds
real issue/PR candidate rows with hard decoys and reports whether the current
local candidate-record observations are enough to rank them honestly.
"""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from candidate_ranker.features import _candidate_record_features
from j3.candidate_observation import candidate_change_observation
from j3.issue_pr_decoy_validation import load_issue_pr_decoy_validation_bundle_index
from j3.issue_pr_candidate_after_snapshot import load_candidate_after_bundle_index


ISSUE_PR_CANDIDATE_RANKING_SCHEMA_VERSION = "issue-pr-candidate-ranking-v1"
DEFAULT_PYTEST_CANDIDATE_PATH = Path(
    "/tmp/j3-data-029-pytest-14462-source-test/candidate.json"
)
DEFAULT_SCRAPY_CANDIDATE_PATH = Path(
    "/tmp/j3-data-035-scrapy-7293-source-test-final/candidate.json"
)
DEFAULT_OUT_DIR = Path("/tmp/j3-data-037-issue-pr-ranking-decoys")


class IssuePrCandidateRankingError(ValueError):
    """Raised when the shadow ranking harness cannot be built."""


@dataclass(frozen=True, slots=True)
class ShadowCandidate:
    candidate_id: str
    candidate_kind: str
    expected_accepted: bool
    expected_validation_status: str
    targeted_mistakes: list[str]
    residual_labels: list[str]
    record: dict[str, object]
    score: float | None = None
    rank: int | None = None
    feature_inputs: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_kind": self.candidate_kind,
            "expected_accepted": self.expected_accepted,
            "expected_validation_status": self.expected_validation_status,
            "targeted_mistakes": list(self.targeted_mistakes),
            "residual_labels": list(self.residual_labels),
            "score": self.score,
            "rank": self.rank,
            "feature_inputs": _json_copy(self.feature_inputs),
            "record": _json_copy(self.record),
        }


@dataclass(frozen=True, slots=True)
class ShadowRankingRow:
    replay_id: str
    repo: str
    source_candidate_path: str
    candidates: list[ShadowCandidate]
    pass_at_1: float | None
    pass_at_k: float | None
    first_accepted_rank: int | None
    scorer_status: str
    scorer_blockers: list[dict[str, str]]
    residual_labels: list[str]

    def to_record(self) -> dict[str, object]:
        return {
            "replay_id": self.replay_id,
            "repo": self.repo,
            "source_candidate_path": self.source_candidate_path,
            "candidate_count": len(self.candidates),
            "accepted_candidate_count": sum(
                1 for candidate in self.candidates if candidate.expected_accepted
            ),
            "decoy_count": sum(
                1 for candidate in self.candidates if not candidate.expected_accepted
            ),
            "pass_at_1": self.pass_at_1,
            "pass_at_k": self.pass_at_k,
            "first_accepted_rank": self.first_accepted_rank,
            "scorer_status": self.scorer_status,
            "scorer_blockers": [dict(blocker) for blocker in self.scorer_blockers],
            "residual_labels": list(self.residual_labels),
            "candidates": [candidate.to_record() for candidate in self.candidates],
        }


def build_issue_pr_candidate_ranking_report(
    *,
    pytest_candidate_path: Path = DEFAULT_PYTEST_CANDIDATE_PATH,
    scrapy_candidate_path: Path = DEFAULT_SCRAPY_CANDIDATE_PATH,
    candidate_after_bundle_path: Path | None = None,
    decoy_validation_bundle_path: Path | None = None,
) -> dict[str, object]:
    """Build a shadow-only ranking report for the DATA-037 real candidates."""

    candidate_after_index = (
        load_candidate_after_bundle_index(candidate_after_bundle_path)
        if candidate_after_bundle_path is not None
        else {}
    )
    decoy_validation_index = (
        load_issue_pr_decoy_validation_bundle_index(decoy_validation_bundle_path)
        if decoy_validation_bundle_path is not None
        else {}
    )
    rows = [
        _build_pytest_row(
            pytest_candidate_path.expanduser().resolve(),
            candidate_after_index=candidate_after_index,
            decoy_validation_index=decoy_validation_index,
        ),
        _build_scrapy_row(
            scrapy_candidate_path.expanduser().resolve(),
            candidate_after_index=candidate_after_index,
            decoy_validation_index=decoy_validation_index,
        ),
    ]
    rankable_rows = sum(1 for row in rows if row.scorer_status == "ranked")
    zero_hosted_usage_confirmed = all(
        _bool_value(candidate.record.get("zero_hosted_usage_confirmed"))
        for row in rows
        for candidate in row.candidates
    )
    pass_at_1_values = [row.pass_at_1 for row in rows if row.pass_at_1 is not None]
    pass_at_k_values = [row.pass_at_k for row in rows if row.pass_at_k is not None]
    report = {
        "schema_version": ISSUE_PR_CANDIDATE_RANKING_SCHEMA_VERSION,
        "record_kind": "issue_pr_candidate_ranking_decoy_report",
        "mode": "shadow_only",
        "production_ranking_gate_changed": False,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": zero_hosted_usage_confirmed,
        },
        "summary": {
            "rows": len(rows),
            "rankable_rows": rankable_rows,
            "blocked_rows": len(rows) - rankable_rows,
            "candidate_count": sum(len(row.candidates) for row in rows),
            "decoy_count": sum(
                sum(1 for candidate in row.candidates if not candidate.expected_accepted)
                for row in rows
            ),
            "pass_at_1": _mean_or_none(pass_at_1_values),
            "pass_at_k": _mean_or_none(pass_at_k_values),
            "first_accepted_ranks": [
                row.first_accepted_rank for row in rows if row.first_accepted_rank is not None
            ],
            "residual_labels": _sorted_unique(
                label for row in rows for label in row.residual_labels
            ),
            "scorer_status": (
                "ranked" if rankable_rows == len(rows) else "blocked_current_inputs"
            ),
        },
        "rows": [row.to_record() for row in rows],
    }
    return report


def write_issue_pr_candidate_ranking_report(
    report: Mapping[str, object],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write JSON, JSONL, and markdown artifacts for a shadow ranking report."""

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_json = output / "ranking-report.json"
    candidates_jsonl = output / "decoy-candidates.jsonl"
    report_md = output / "ranking-report.md"
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = report.get("rows", [])
    lines: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            candidates = row.get("candidates", [])
            if not isinstance(candidates, list):
                continue
            for candidate in candidates:
                if isinstance(candidate, Mapping):
                    lines.append(json.dumps(candidate, sort_keys=True))
    candidates_jsonl.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    report_md.write_text(format_issue_pr_candidate_ranking_markdown(report), encoding="utf-8")
    return {
        "report_json": report_json,
        "candidates_jsonl": candidates_jsonl,
        "report_md": report_md,
    }


def format_issue_pr_candidate_ranking_markdown(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    hosted = _mapping(report.get("hosted_llm_usage"))
    lines = [
        "# DATA-037 Issue/PR Ranking Decoy Harness",
        "",
        "- Mode: shadow-only",
        f"- Hosted LLM usage: {str(hosted.get('used') is True).lower()}",
        f"- Zero hosted usage confirmed: {str(hosted.get('zero_hosted_usage_confirmed') is True).lower()}",
        f"- Rows: {summary.get('rows')}",
        f"- Rankable rows: {summary.get('rankable_rows')}",
        f"- Blocked rows: {summary.get('blocked_rows')}",
        f"- Decoys: {summary.get('decoy_count')}",
        f"- pass@1: {_metric_text(summary.get('pass_at_1'))}",
        f"- pass@k: {_metric_text(summary.get('pass_at_k'))}",
        "",
        "| Replay | Candidates | Decoys | pass@1 | pass@k | First accepted rank | Status | Blockers |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    rows = report.get("rows", [])
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            blockers = row.get("scorer_blockers", [])
            blocker_reasons = []
            if isinstance(blockers, list):
                for blocker in blockers:
                    if isinstance(blocker, Mapping):
                        blocker_reasons.append(str(blocker.get("reason", "unknown")))
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.get("replay_id", "")),
                        str(row.get("candidate_count", "")),
                        str(row.get("decoy_count", "")),
                        _metric_text(row.get("pass_at_1")),
                        _metric_text(row.get("pass_at_k")),
                        _metric_text(row.get("first_accepted_rank")),
                        str(row.get("scorer_status", "")),
                        ", ".join(blocker_reasons),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Candidate Feature Availability",
            "",
            "| Replay | Candidate | Kind | Diff | AST | Candidate-after | Validation | Targeted mistakes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            for candidate in _candidate_mappings(row):
                feature_inputs = _mapping(candidate.get("feature_inputs"))
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(row.get("replay_id", "")),
                            str(candidate.get("candidate_id", "")),
                            str(candidate.get("candidate_kind", "")),
                            _yes_no(feature_inputs.get("diff_summary_available")),
                            _yes_no(feature_inputs.get("ast_delta_available")),
                            _yes_no(feature_inputs.get("candidate_after_available")),
                            str(candidate.get("expected_validation_status", "")),
                            ", ".join(
                                str(item)
                                for item in _string_list(candidate.get("targeted_mistakes"))
                            ),
                        ]
                    )
                    + " |"
                )
    lines.append("")
    return "\n".join(lines)


def _build_pytest_row(
    candidate_path: Path,
    *,
    candidate_after_index: Mapping[tuple[str, str], Mapping[str, object]],
    decoy_validation_index: Mapping[str, Mapping[str, object]],
) -> ShadowRankingRow:
    record = _load_candidate_record(candidate_path)
    candidates = [
        _accepted_candidate(record, candidate_after_index=candidate_after_index),
        _decoy_candidate(
            record,
            decoy_id="pytest_rel_timedelta_object_semantics",
            targeted_mistakes=[
                "incomplete_timedelta_relative_tolerance_semantics",
                "keeps_rel_as_timedelta_instead_of_numeric_fraction",
            ],
            residual_labels=["semantic_decoy", "pytest_timedelta_rel_semantics_gap"],
            description=(
                "Implements timedelta support but preserves stale rel=timedelta "
                "semantics instead of numeric rel * abs(expected)."
            ),
            decoy_validation_index=decoy_validation_index,
        ),
        _decoy_candidate(
            record,
            decoy_id="pytest_missing_container_dispatch",
            targeted_mistakes=[
                "incomplete_source_materialization",
                "missing_sequence_mapping_approx_timedelta_dispatch",
            ],
            residual_labels=["source_decoy", "candidate_after_observation_gap"],
            description=(
                "Updates ApproxTimedelta.__init__ but omits _approx_scalar dispatch "
                "needed for timedelta values inside sequences and mappings."
            ),
            omit_source_metadata_keys=("ast_delta",),
            decoy_validation_index=decoy_validation_index,
        ),
        _decoy_candidate(
            record,
            decoy_id="pytest_missing_invalid_tolerance_tests",
            targeted_mistakes=[
                "missing_test_coverage",
                "missing_negative_and_nan_tolerance_tests",
            ],
            residual_labels=["test_decoy", "coverage_gap"],
            description=(
                "Keeps source-looking changes but drops tests for negative rel, "
                "NaN rel, negative abs, and rel/abs max behavior."
            ),
            omit_test_materialization=True,
            decoy_validation_index=decoy_validation_index,
        ),
        _decoy_candidate(
            record,
            decoy_id="pytest_partial_source_test_materialization",
            targeted_mistakes=[
                "incomplete_source_test_materialization",
                "docs_and_tests_without_full_source_semantics",
            ],
            residual_labels=["materialization_decoy", "source_semantics_gap"],
            description=(
                "Adds docs and some tests but leaves incomplete source behavior for "
                "relative tolerance scaling."
            ),
            omit_source_materialization=True,
            decoy_validation_index=decoy_validation_index,
        ),
    ]
    return _blocked_row(record, candidate_path, candidates)


def _build_scrapy_row(
    candidate_path: Path,
    *,
    candidate_after_index: Mapping[tuple[str, str], Mapping[str, object]],
    decoy_validation_index: Mapping[str, Mapping[str, object]],
) -> ShadowRankingRow:
    record = _load_candidate_record(candidate_path)
    candidates = [
        _accepted_candidate(record, candidate_after_index=candidate_after_index),
        _decoy_candidate(
            record,
            decoy_id="scrapy_stale_min_stats_selection",
            targeted_mistakes=[
                "stale_min_stats_selection",
                "keeps_lexicographic_slot_tie_breaking",
            ],
            residual_labels=["semantic_decoy", "slot_rotation_gap"],
            description=(
                "Keeps min(stats)[1] style selection so equal active-download "
                "slots still starve later slots."
            ),
            omit_source_metadata_keys=("ast_delta",),
            decoy_validation_index=decoy_validation_index,
        ),
        _decoy_candidate(
            record,
            decoy_id="scrapy_mutating_peek",
            targeted_mistakes=[
                "mutating_peek",
                "updates_last_selected_slot_during_peek",
            ],
            residual_labels=["semantic_decoy", "peek_side_effect_gap"],
            description=(
                "Calls the slot selector from peek with state updates, so observing "
                "the queue changes later pop behavior."
            ),
            decoy_validation_index=decoy_validation_index,
        ),
        _decoy_candidate(
            record,
            decoy_id="scrapy_missing_last_selected_slot",
            targeted_mistakes=[
                "missing_last_selected_slot",
                "stateless_rotation_helper",
            ],
            residual_labels=["state_decoy", "source_state_gap"],
            description=(
                "Adds a helper but omits the persistent _last_selected_slot state "
                "needed to continue rotation after a slot is deleted."
            ),
            decoy_validation_index=decoy_validation_index,
        ),
        _decoy_candidate(
            record,
            decoy_id="scrapy_missing_tests",
            targeted_mistakes=["missing_tests", "source_only_candidate"],
            residual_labels=["test_decoy", "coverage_gap"],
            description=(
                "Changes the source candidate but omits the DownloaderAwarePriorityQueue "
                "tie-breaking regression tests."
            ),
            omit_test_materialization=True,
            decoy_validation_index=decoy_validation_index,
        ),
    ]
    return _blocked_row(record, candidate_path, candidates)


def _accepted_candidate(
    record: Mapping[str, object],
    *,
    candidate_after_index: Mapping[tuple[str, str], Mapping[str, object]],
) -> ShadowCandidate:
    normalized = _scorer_record(record)
    replay_id = str(record.get("replay_id", ""))
    candidate_id = str(record.get("candidate_id") or "accepted")
    candidate_after = candidate_after_index.get((replay_id, candidate_id))
    if candidate_after is not None:
        normalized["candidate_after"] = _json_copy(candidate_after)
    residual_labels = _string_list(record.get("residual_labels")) or [
        "candidate_validation_passed"
    ]
    return _candidate_from_record(
        candidate_id=candidate_id,
        candidate_kind="accepted_validated_candidate",
        expected_accepted=True,
        expected_validation_status=str(_mapping(record.get("validation")).get("status", "passed")),
        targeted_mistakes=[],
        residual_labels=residual_labels,
        record=normalized,
    )


def _decoy_candidate(
    record: Mapping[str, object],
    *,
    decoy_id: str,
    targeted_mistakes: list[str],
    residual_labels: list[str],
    description: str,
    decoy_validation_index: Mapping[str, Mapping[str, object]],
    omit_source_materialization: bool = False,
    omit_test_materialization: bool = False,
    omit_source_metadata_keys: Sequence[str] = (),
) -> ShadowCandidate:
    decoy = _scorer_record(record)
    replay_id = str(record.get("replay_id", "unknown"))
    candidate_id = f"{replay_id}:{decoy_id}"
    decoy["candidate_id"] = candidate_id
    decoy["status"] = "decoy_unvalidated"
    decoy["validation"] = {
        "status": "not_run",
        "reason": "shadow_decoy_evidence_only",
    }
    decoy["residual_labels"] = list(residual_labels)
    decoy["decoy_evidence"] = {
        "description": description,
        "targeted_mistakes": list(targeted_mistakes),
        "harness_only": True,
    }
    if omit_source_materialization:
        decoy.pop("source_materialization", None)
    if omit_test_materialization:
        decoy.pop("test_materialization", None)
        _drop_test_paths(decoy)
    if omit_source_metadata_keys and isinstance(decoy.get("source_materialization"), dict):
        source = dict(decoy["source_materialization"])  # type: ignore[index]
        for key in omit_source_metadata_keys:
            source.pop(key, None)
        decoy["source_materialization"] = source
    validation_status = "not_run"
    outcome = decoy_validation_index.get(candidate_id)
    if outcome is not None:
        decoy.update(_scorer_record(outcome))
        decoy["candidate_id"] = candidate_id
        decoy["status"] = "decoy_live_validated"
        validation_status = str(_mapping(outcome.get("validation")).get("status", ""))
        if not validation_status:
            validation_status = "not_run"
        residual_labels = _string_list(outcome.get("residual_labels")) or residual_labels
        targeted_mistakes = _string_list(
            _mapping(outcome.get("decoy_evidence")).get("targeted_mistakes")
        ) or targeted_mistakes
    return _candidate_from_record(
        candidate_id=candidate_id,
        candidate_kind="realistic_decoy",
        expected_accepted=False,
        expected_validation_status=validation_status,
        targeted_mistakes=targeted_mistakes,
        residual_labels=residual_labels,
        record=decoy,
    )


def _candidate_from_record(
    *,
    candidate_id: str,
    candidate_kind: str,
    expected_accepted: bool,
    expected_validation_status: str,
    targeted_mistakes: list[str],
    residual_labels: list[str],
    record: dict[str, object],
) -> ShadowCandidate:
    features = _candidate_record_features(record, hints=[])
    observation = candidate_change_observation(record)
    feature_inputs = {
        "candidate_after_available": observation.get("candidate_after_available") is True,
        "diff_summary_available": any(
            key in observation
            for key in ("diff_added_lines", "diff_removed_lines", "diff_changed_lines")
        ),
        "ast_delta_available": any(
            key in observation
            for key in ("ast_parse_ok", "ast_delta_added_count", "ast_delta_removed_count")
        ),
        "validation_available": expected_validation_status not in {"", "not_run"},
        "validation_status": expected_validation_status,
        "changed_files_available": bool(record.get("allowed_write_paths"))
        or bool(_mapping(record.get("candidate_diff")).get("changed_files")),
        "feature_count": len(features),
        "feature_sample": sorted(features)[:16],
    }
    return ShadowCandidate(
        candidate_id=candidate_id,
        candidate_kind=candidate_kind,
        expected_accepted=expected_accepted,
        expected_validation_status=expected_validation_status,
        targeted_mistakes=list(targeted_mistakes),
        residual_labels=list(residual_labels),
        record=record,
        feature_inputs=feature_inputs,
    )


def _blocked_row(
    record: Mapping[str, object],
    candidate_path: Path,
    candidates: list[ShadowCandidate],
) -> ShadowRankingRow:
    replay_id = str(record.get("replay_id", ""))
    repo = str(record.get("repo", ""))
    blockers = [
        {
            "field": "ranker_model",
            "reason": "no_guarded_issue_pr_ranker",
            "message": (
                "No production or guarded issue/PR ranker is available for these "
                "real source/test candidate action families."
            ),
        },
        {
            "field": "semantic_features",
            "reason": "issue_specific_semantics_not_in_current_features",
            "message": (
                "Current candidate-record features expose generic diff/AST signals "
                "but not enough issue-specific semantics to distinguish stale "
                "min(stats), mutating peek, missing _last_selected_slot, or "
                "incomplete timedelta relative tolerance behavior without leaking "
                "harness labels."
            ),
        },
    ]
    decoys = [candidate for candidate in candidates if not candidate.expected_accepted]
    decoys_live_validated = bool(decoys) and all(
        candidate.expected_validation_status in {"passed", "failed", "timeout"}
        for candidate in decoys
    )
    if not decoys_live_validated:
        blockers.append(
            {
                "field": "decoy_validation",
                "reason": "decoys_not_live_validated",
                "message": (
                    "The decoys are realistic hard negatives for shadow evidence, but "
                    "they have no complete live validation outcomes and should not be "
                    "scored as known failing candidates by a production ranker."
                ),
            }
        )
    elif any(candidate.expected_validation_status == "passed" for candidate in decoys):
        blockers.append(
            {
                "field": "decoy_validation",
                "reason": "decoy_validation_outcomes_include_passing_candidates",
                "message": (
                    "The decoys are live-validated, but at least one passes the "
                    "focused command. The row is evidence for a coverage gap, not "
                    "a clean accepted-versus-failing-decoys ranking set."
                ),
            }
        )
    accepted_after_available = all(
        candidate.feature_inputs.get("candidate_after_available") is True
        for candidate in candidates
        if candidate.expected_accepted
    )
    decoy_after_available = bool(decoys) and all(
        candidate.feature_inputs.get("candidate_after_available") is True
        for candidate in decoys
    )
    if accepted_after_available and not decoy_after_available:
        blockers.append(
            {
                "field": "candidate_after",
                "reason": "decoy_candidate_after_unavailable",
                "message": (
                    "DATA-038 provides complete candidate-after snapshots for "
                    "the accepted validated candidates, but the realistic decoys "
                    "still have no materialized after-file snapshots."
                ),
            }
        )
    elif not accepted_after_available:
        blockers.append(
            {
                "field": "candidate_after",
                "reason": "full_candidate_after_unavailable",
                "message": (
                    "The DATA-029/DATA-035 artifacts expose diffs and AST summaries, "
                    "but not complete candidate-after file snapshots for the "
                    "accepted candidate and decoys."
                ),
            }
        )
    return ShadowRankingRow(
        replay_id=replay_id,
        repo=repo,
        source_candidate_path=str(candidate_path),
        candidates=candidates,
        pass_at_1=None,
        pass_at_k=None,
        first_accepted_rank=None,
        scorer_status="blocked_current_inputs",
        scorer_blockers=blockers,
        residual_labels=_sorted_unique(
            label for candidate in candidates for label in candidate.residual_labels
        ),
    )


def _scorer_record(record: Mapping[str, object]) -> dict[str, object]:
    copied = copy.deepcopy(dict(record))
    copied["action"] = str(
        copied.get("action") or copied.get("action_family") or "issue_pr_source_test_candidate"
    )
    copied["params"] = {
        "action_family": copied.get("action_family", ""),
        "changed_file_count": len(_string_list(copied.get("allowed_write_paths"))),
    }
    return copied


def _drop_test_paths(record: dict[str, object]) -> None:
    test_path = str(_mapping(record.get("test_materialization")).get("target_test_file", ""))
    changed_files = _string_list(_mapping(record.get("candidate_diff")).get("changed_files"))
    if test_path and changed_files:
        candidate_diff = dict(_mapping(record.get("candidate_diff")))
        candidate_diff["changed_files"] = [path for path in changed_files if path != test_path]
        summary = dict(_mapping(candidate_diff.get("diff_summary")))
        test_summary = _mapping(_mapping(record.get("test_materialization")).get("diff_summary"))
        if test_summary:
            for key in ("added_line_count", "removed_line_count", "changed_line_count"):
                summary[key] = max(
                    0,
                    _int_value(summary.get(key)) - _int_value(test_summary.get(key)),
                )
            candidate_diff["diff_summary"] = summary
        record["candidate_diff"] = candidate_diff


def _load_candidate_record(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise IssuePrCandidateRankingError(f"candidate artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrCandidateRankingError(f"candidate artifact must be a JSON object: {path}")
    required = ["candidate_id", "replay_id", "repo", "candidate_diff", "validation"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise IssuePrCandidateRankingError(
            f"candidate artifact {path} is missing required keys: {', '.join(missing)}"
        )
    return payload


def _candidate_mappings(row: Mapping[str, object]) -> list[Mapping[str, object]]:
    candidates = row.get("candidates", [])
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, Mapping)]


def _mean_or_none(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _metric_text(value: object) -> str:
    if value is None:
        return "blocked"
    return str(value)


def _yes_no(value: object) -> str:
    return "yes" if value is True else "no"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


def _sorted_unique(values: object) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _bool_value(value: object) -> bool:
    return value is True


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pytest-candidate",
        type=Path,
        default=DEFAULT_PYTEST_CANDIDATE_PATH,
        help="Path to the DATA-029 pytest #14462 candidate.json artifact.",
    )
    parser.add_argument(
        "--scrapy-candidate",
        type=Path,
        default=DEFAULT_SCRAPY_CANDIDATE_PATH,
        help="Path to the DATA-035 Scrapy #7293 candidate.json artifact.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for ranking-report.json, decoy-candidates.jsonl, and markdown.",
    )
    parser.add_argument(
        "--candidate-after-bundle",
        type=Path,
        default=None,
        help="Optional DATA-038 candidate-after bundle JSON for accepted candidates.",
    )
    parser.add_argument(
        "--decoy-validation-bundle",
        type=Path,
        default=None,
        help="Optional DATA-039 decoy validation bundle JSON for materialized decoys.",
    )
    args = parser.parse_args(argv)

    report = build_issue_pr_candidate_ranking_report(
        pytest_candidate_path=args.pytest_candidate,
        scrapy_candidate_path=args.scrapy_candidate,
        candidate_after_bundle_path=args.candidate_after_bundle,
        decoy_validation_bundle_path=args.decoy_validation_bundle,
    )
    artifacts = write_issue_pr_candidate_ranking_report(report, out_dir=args.out_dir)
    print(json.dumps({name: str(path) for name, path in artifacts.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
