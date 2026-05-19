"""Shadow transition-scorer advice for real repair plans."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from j3.failure_hints import PytestFailureHint
from j3.repo import DEFAULT_EXCLUDE_DIRS
from j3.transition_action_scoring import (
    TRANSITION_ACTION_SCORER_FEATURE_VERSION,
    TRANSITION_ACTION_SCORER_VERSION,
    score_transition_action_candidate,
)

if TYPE_CHECKING:
    from repair.patching.types import CandidatePatch


TRANSITION_SCORER_ADVICE_VERSION = "transition-scorer-advice-v1"
TRANSITION_SCORER_ADVICE_SUMMARY_VERSION = "transition-scorer-advice-summary-v1"


@dataclass(frozen=True, slots=True)
class TransitionScorerAdviceSummary:
    """Aggregate shadow advice metrics for one or more JSONL artifacts."""

    paths: list[Path]
    advice_row_count: int
    candidate_count: int
    scorer_production_agreement_count: int
    scorer_production_agreement_total: int
    known_improved_count: int
    known_regressed_count: int
    known_no_change_count: int
    production_pass_at_1_count: int
    scorer_pass_at_1_count: int
    known_validation_count: int
    average_candidates_saved_or_lost: float | None
    runtime: dict[str, object]
    usage: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        agreement_rate = _rate(
            self.scorer_production_agreement_count,
            self.scorer_production_agreement_total,
        )
        return {
            "schema_version": TRANSITION_SCORER_ADVICE_SUMMARY_VERSION,
            "advice_paths": [str(path) for path in self.paths],
            "advice_row_count": self.advice_row_count,
            "candidate_count": self.candidate_count,
            "scorer_production_agreement": {
                "count": self.scorer_production_agreement_count,
                "total": self.scorer_production_agreement_total,
                "rate": agreement_rate,
            },
            "known_validation": {
                "row_count": self.known_validation_count,
                "improved_count": self.known_improved_count,
                "regressed_count": self.known_regressed_count,
                "no_change_count": self.known_no_change_count,
                "production_pass_at_1_count": self.production_pass_at_1_count,
                "production_pass_at_1_rate": _rate(
                    self.production_pass_at_1_count,
                    self.known_validation_count,
                ),
                "scorer_pass_at_1_count": self.scorer_pass_at_1_count,
                "scorer_pass_at_1_rate": _rate(
                    self.scorer_pass_at_1_count,
                    self.known_validation_count,
                ),
                "average_candidates_saved_or_lost": (
                    round(self.average_candidates_saved_or_lost, 6)
                    if self.average_candidates_saved_or_lost is not None
                    else None
                ),
            },
            "runtime": dict(self.runtime),
            "usage": dict(self.usage),
        }


def build_transition_scorer_advice(
    *,
    repo: Path,
    test_command: str,
    baseline_exit_code: int,
    candidates: Sequence[CandidatePatch],
    selected: CandidatePatch | None,
    tested_candidates: Sequence[CandidatePatch],
    passing_candidates: Sequence[CandidatePatch],
    candidate_hints: Sequence[Sequence[PytestFailureHint]] = (),
    first_passing_index: int | None = None,
    model_path: Path | None = None,
    ranker_path: Path | None = None,
    context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Score repair candidates in shadow mode without affecting planner order."""

    started = time.perf_counter()
    candidate_records = [
        _candidate_record(
            candidate,
            rank_index=index,
            hints=_hints_for_rank(candidate_hints, index),
            validated=any(candidate == tested for tested in tested_candidates),
            passed=any(candidate == passing for passing in passing_candidates),
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    group = {
        "candidate_count": len(candidate_records),
        "grouping": {
            "language": "python",
            "phase": "real-patch-planning",
            **(dict(context) if context is not None else {}),
        },
        "candidates": candidate_records,
    }
    scored_records = [
        {
            **record,
            "evaluation_score": score_transition_action_candidate(record, group=group),
        }
        for record in candidate_records
    ]
    scorer_ranked = sorted(
        scored_records,
        key=lambda record: (
            -float(_mapping(record["evaluation_score"])["score"]),
            int(record["rank_index"]),
        ),
    )
    selected_rank = _candidate_rank(candidates, selected)
    selected_record = (
        _record_by_rank(scored_records, selected_rank)
        if selected_rank is not None
        else None
    )
    top_record = scorer_ranked[0] if scorer_ranked else None
    scorer_ranked_ranks = [int(record["rank_index"]) for record in scorer_ranked]
    existing_ranked_ranks = [int(record["rank_index"]) for record in candidate_records]
    comparison = _validation_comparison(
        scorer_ranked=scorer_ranked,
        selected_rank=selected_rank,
        first_passing_index=first_passing_index,
    )
    usage = {
        "hosted_llm_api_calls": 0,
        "hosted_llm_prompt_tokens": 0,
        "hosted_llm_completion_tokens": 0,
        "hosted_api_tokens": 0,
        "hosted_repo_context_bytes": 0,
    }

    return {
        "schema_version": TRANSITION_SCORER_ADVICE_VERSION,
        "mode": "shadow",
        "decision": "shadow_only_not_wired_to_routing",
        "scorer": {
            "name": TRANSITION_ACTION_SCORER_VERSION,
            "feature_version": TRANSITION_ACTION_SCORER_FEATURE_VERSION,
        },
        "repair_plan_id": _repair_plan_id(
            repo=repo,
            test_command=test_command,
            baseline_exit_code=baseline_exit_code,
            candidates=candidates,
        ),
        "repo_state_summary": _repo_state_summary(repo),
        "repair_context": {
            "test_command": test_command,
            "baseline_exit_code": baseline_exit_code,
            "model_path": str(model_path) if model_path is not None else None,
            "ranker_path": str(ranker_path) if ranker_path is not None else None,
            **(dict(context) if context is not None else {}),
        },
        "candidate_count": len(candidate_records),
        "validated_candidate_count": sum(
            1 for record in candidate_records if _mapping(record["validation"])["validated"]
        ),
        "existing_ranked_candidate_ranks": existing_ranked_ranks,
        "scorer_ranked_candidate_ranks": scorer_ranked_ranks,
        "existing_selected_candidate": (
            _candidate_summary(selected_record) if selected_record is not None else None
        ),
        "scorer_top_candidate": _candidate_summary(top_record) if top_record else None,
        "scorer_agreed_with_existing_rank_order": (
            scorer_ranked_ranks == existing_ranked_ranks
        ),
        "scorer_agreed_with_existing_top_candidate": (
            bool(scorer_ranked_ranks)
            and bool(existing_ranked_ranks)
            and scorer_ranked_ranks[0] == existing_ranked_ranks[0]
        ),
        "validation_comparison": comparison,
        "runtime": {
            "local_runtime_ms": round((time.perf_counter() - started) * 1000, 3),
            **usage,
        },
        "usage": usage,
    }


def transition_scorer_ranked_candidates(
    candidates: Sequence[CandidatePatch],
    *,
    candidate_hints: Sequence[Sequence[PytestFailureHint]] = (),
    context: Mapping[str, object] | None = None,
) -> tuple[CandidatePatch, ...]:
    """Rank real repair candidates with the transition action scorer."""

    candidate_records = [
        _candidate_record(
            candidate,
            rank_index=index,
            hints=_hints_for_rank(candidate_hints, index),
            validated=False,
            passed=False,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    group = {
        "candidate_count": len(candidate_records),
        "grouping": {
            "language": "python",
            "phase": "real-patch-planning",
            **(dict(context) if context is not None else {}),
        },
        "candidates": candidate_records,
    }
    ranked_records = sorted(
        (
            {
                "index": index,
                "score": score_transition_action_candidate(record, group=group),
            }
            for index, record in enumerate(candidate_records)
        ),
        key=lambda item: (
            -float(_mapping(item["score"])["score"]),
            int(candidate_records[int(item["index"])]["rank_index"]),
        ),
    )
    return tuple(candidates[int(record["index"])] for record in ranked_records)


def append_transition_scorer_advice_jsonl(path: Path, row: Mapping[str, object]) -> Path:
    """Append one transition scorer advice row to a JSONL file."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def summarize_transition_scorer_advice(
    paths: Sequence[Path],
) -> TransitionScorerAdviceSummary:
    """Summarize one or more transition-scorer-advice-v1 JSONL files."""

    resolved_paths = [path.expanduser().resolve() for path in paths]
    rows = _read_transition_scorer_advice_rows(resolved_paths)
    candidate_count = sum(_int(row.get("candidate_count")) for row in rows)
    agreement_total = 0
    agreement_count = 0
    known_improved_count = 0
    known_regressed_count = 0
    known_no_change_count = 0
    production_pass_at_1_count = 0
    scorer_pass_at_1_count = 0
    known_validation_count = 0
    saved_or_lost: list[int] = []

    for row in rows:
        selected = _mapping(row.get("existing_selected_candidate"))
        scorer_top = _mapping(row.get("scorer_top_candidate"))
        if selected and scorer_top:
            agreement_total += 1
            if _candidate_summaries_match(selected, scorer_top):
                agreement_count += 1

        comparison = _mapping(row.get("validation_comparison"))
        if comparison.get("known") is not True:
            continue
        known_validation_count += 1
        would_have = comparison.get("would_have")
        if would_have == "improved":
            known_improved_count += 1
        elif would_have == "regressed":
            known_regressed_count += 1
        elif would_have == "same":
            known_no_change_count += 1
        if selected.get("passed") is True:
            production_pass_at_1_count += 1
        if scorer_top.get("validated") is True and scorer_top.get("passed") is True:
            scorer_pass_at_1_count += 1
        existing_position = _int_or_none(comparison.get("existing_first_passing_index"))
        scorer_position = _int_or_none(
            comparison.get("scorer_first_known_passing_position")
        )
        if existing_position is not None and scorer_position is not None:
            saved_or_lost.append(existing_position - scorer_position)

    usage = _usage_totals(rows)
    runtime = {
        "local_runtime_ms": round(
            sum(
                _float(_mapping(row.get("runtime")).get("local_runtime_ms"))
                for row in rows
            ),
            3,
        ),
        **usage,
    }
    return TransitionScorerAdviceSummary(
        paths=resolved_paths,
        advice_row_count=len(rows),
        candidate_count=candidate_count,
        scorer_production_agreement_count=agreement_count,
        scorer_production_agreement_total=agreement_total,
        known_improved_count=known_improved_count,
        known_regressed_count=known_regressed_count,
        known_no_change_count=known_no_change_count,
        production_pass_at_1_count=production_pass_at_1_count,
        scorer_pass_at_1_count=scorer_pass_at_1_count,
        known_validation_count=known_validation_count,
        average_candidates_saved_or_lost=_average(saved_or_lost),
        runtime=runtime,
        usage=usage,
    )


def format_transition_scorer_advice_summary(
    summary: TransitionScorerAdviceSummary,
) -> str:
    """Format shadow advice summary metrics for CLI output."""

    record = summary.as_dict()
    agreement = _mapping(record["scorer_production_agreement"])
    known = _mapping(record["known_validation"])
    lines = ["j3 summarize-transition-advice"]
    lines.append("transition advice:")
    for path in summary.paths:
        lines.append(f"  {path}")
    lines.append(f"advice rows: {summary.advice_row_count}")
    lines.append(f"candidates: {summary.candidate_count}")
    lines.append(
        "scorer/production agreement: "
        f"{agreement['count']}/{agreement['total']} "
        f"({_format_rate(agreement.get('rate'))})"
    )
    lines.append(
        "known validation: "
        f"improved={known['improved_count']} "
        f"regressed={known['regressed_count']} "
        f"no_change={known['no_change_count']}"
    )
    lines.append(
        "production-selected pass@1: "
        f"{known['production_pass_at_1_count']}/{known['row_count']} "
        f"({_format_rate(known.get('production_pass_at_1_rate'))})"
    )
    lines.append(
        "scorer-top pass@1: "
        f"{known['scorer_pass_at_1_count']}/{known['row_count']} "
        f"({_format_rate(known.get('scorer_pass_at_1_rate'))})"
    )
    average = known.get("average_candidates_saved_or_lost")
    average_text = f"{average:.2f}" if isinstance(average, float) else "-"
    lines.append(f"average candidates saved/lost: {average_text}")
    lines.append(f"local runtime ms: {summary.runtime['local_runtime_ms']}")
    lines.append(f"hosted_llm_api_calls: {summary.usage['hosted_llm_api_calls']}")
    lines.append(f"hosted_llm_prompt_tokens: {summary.usage['hosted_llm_prompt_tokens']}")
    lines.append(
        f"hosted_llm_completion_tokens: {summary.usage['hosted_llm_completion_tokens']}"
    )
    lines.append(f"hosted_api_tokens: {summary.usage['hosted_api_tokens']}")
    lines.append(
        f"hosted_repo_context_bytes: {summary.usage['hosted_repo_context_bytes']}"
    )
    return "\n".join(lines)


def _candidate_record(
    candidate: CandidatePatch,
    *,
    rank_index: int,
    hints: Sequence[PytestFailureHint],
    validated: bool,
    passed: bool,
) -> dict[str, object]:
    action = candidate.action.to_record()
    return {
        "id": _candidate_id(candidate, rank_index=rank_index),
        "rank_index": rank_index,
        "action": {
            "kind": action["kind"],
            "file_path": candidate.file_path,
            "symbol": candidate.action.target.symbol,
            "start_line": candidate.action.target.start_line,
            "end_line": candidate.action.target.end_line,
            "node_kind": candidate.action.target.node_kind,
            "params": dict(candidate.action.params),
        },
        "target_context": dict(candidate.target_context),
        "source_context": {
            "available": True,
            "kind": "candidate_original_source",
            "embedding_available": False,
        },
        "candidate_after": {
            "available": True,
            "kind": "candidate_patched_source",
            "embedding_available": False,
        },
        "scores": {
            "model_score": candidate.model_score,
            "failure_hint_score": candidate.failure_hint_score,
            "ranker_score": candidate.ranker_score,
        },
        "validation": {
            "validated": validated,
            "passed": passed if validated else None,
            "status": "passed" if passed else ("failed" if validated else "not_validated"),
            "failure_hints": [_failure_hint_record(hint) for hint in hints],
        },
        "reason": candidate.reason,
    }


def _candidate_summary(record: Mapping[str, object] | None) -> dict[str, object] | None:
    if record is None:
        return None
    action = _mapping(record.get("action"))
    validation = _mapping(record.get("validation"))
    score = _mapping(record.get("evaluation_score"))
    return {
        "id": record.get("id"),
        "rank_index": record.get("rank_index"),
        "file_path": action.get("file_path"),
        "action": action.get("kind"),
        "symbol": action.get("symbol"),
        "start_line": action.get("start_line"),
        "end_line": action.get("end_line"),
        "node_kind": action.get("node_kind"),
        "params": action.get("params"),
        "validated": validation.get("validated"),
        "passed": validation.get("passed"),
        "score": score.get("score"),
        "reason": record.get("reason"),
    }


def _validation_comparison(
    *,
    scorer_ranked: Sequence[Mapping[str, object]],
    selected_rank: int | None,
    first_passing_index: int | None,
) -> dict[str, object]:
    if selected_rank is None or first_passing_index is None:
        return {
            "known": False,
            "would_have": "unknown",
            "reason": "existing planner did not select a passing candidate",
        }

    blocked_by_unvalidated = False
    for scorer_position, record in enumerate(scorer_ranked, start=1):
        validation = _mapping(record.get("validation"))
        if validation.get("validated") is not True:
            blocked_by_unvalidated = True
            break
        if validation.get("passed") is True:
            if scorer_position < first_passing_index:
                outcome = "improved"
            elif scorer_position > first_passing_index:
                outcome = "regressed"
            else:
                outcome = "same"
            return {
                "known": True,
                "would_have": outcome,
                "existing_first_passing_index": first_passing_index,
                "scorer_first_known_passing_position": scorer_position,
                "scorer_first_known_passing_rank_index": record.get("rank_index"),
            }

    return {
        "known": False,
        "would_have": "unknown",
        "reason": (
            "scorer ranking has unvalidated candidates before the first known pass"
            if blocked_by_unvalidated
            else "no validated scorer-ranked candidate is known to pass"
        ),
        "existing_first_passing_index": first_passing_index,
    }


def _repo_state_summary(repo: Path) -> dict[str, object]:
    python_files = [
        path
        for path in repo.rglob("*.py")
        if not any(part in DEFAULT_EXCLUDE_DIRS for part in path.relative_to(repo).parts)
    ]
    return {
        "repo": str(repo),
        "repo_name": repo.name,
        "python_file_count": len(python_files),
    }


def _repair_plan_id(
    *,
    repo: Path,
    test_command: str,
    baseline_exit_code: int,
    candidates: Sequence[CandidatePatch],
) -> str:
    payload = {
        "repo": str(repo),
        "test_command": test_command,
        "baseline_exit_code": baseline_exit_code,
        "candidates": [
            {
                "file_path": candidate.file_path,
                "action": candidate.action.to_record(),
                "reason": candidate.reason,
            }
            for candidate in candidates
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"patch-plan:{digest[:16]}"


def _candidate_id(candidate: CandidatePatch, *, rank_index: int) -> str:
    payload = {
        "rank_index": rank_index,
        "file_path": candidate.file_path,
        "action": candidate.action.to_record(),
        "reason": candidate.reason,
        "diff": candidate.diff(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _candidate_rank(
    candidates: Sequence[CandidatePatch],
    selected: CandidatePatch | None,
) -> int | None:
    if selected is None:
        return None
    for index, candidate in enumerate(candidates, start=1):
        if candidate == selected:
            return index
    return None


def _record_by_rank(
    records: Sequence[Mapping[str, object]],
    rank_index: int,
) -> Mapping[str, object] | None:
    for record in records:
        if record.get("rank_index") == rank_index:
            return record
    return None


def _hints_for_rank(
    candidate_hints: Sequence[Sequence[PytestFailureHint]],
    rank_index: int,
) -> Sequence[PytestFailureHint]:
    offset = rank_index - 1
    if offset < len(candidate_hints):
        return candidate_hints[offset]
    return ()


def _failure_hint_record(hint: PytestFailureHint) -> dict[str, object]:
    return {
        "nodeid": hint.nodeid,
        "exception_type": hint.exception_type,
        "source_files": sorted(hint.source_files),
        "function_names": sorted(hint.function_names),
        "missing_names": sorted(hint.missing_names),
        "missing_keys": sorted(hint.missing_keys),
        "asserted_mapping_keys": sorted(hint.asserted_mapping_keys),
        "type_error_names": sorted(hint.type_error_names),
        "assertions": [
            {
                "operator": assertion.operator,
                "actual": assertion.actual,
                "expected": assertion.expected,
                "numeric_delta": assertion.numeric_delta,
            }
            for assertion in hint.assertions
        ],
    }


def _read_transition_scorer_advice_rows(paths: Sequence[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"transition advice file does not exist: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"transition advice path is not a file: {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            if row.get("schema_version") != TRANSITION_SCORER_ADVICE_VERSION:
                raise ValueError(
                    f"{path}:{line_number}: expected {TRANSITION_SCORER_ADVICE_VERSION}"
                )
            rows.append(row)
    return rows


def _candidate_summaries_match(
    left: Mapping[str, object],
    right: Mapping[str, object],
) -> bool:
    left_id = left.get("id")
    right_id = right.get("id")
    if isinstance(left_id, str) and isinstance(right_id, str):
        return left_id == right_id
    return left.get("rank_index") == right.get("rank_index")


def _usage_totals(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    fields = (
        "hosted_llm_api_calls",
        "hosted_llm_prompt_tokens",
        "hosted_llm_completion_tokens",
        "hosted_api_tokens",
        "hosted_repo_context_bytes",
    )
    totals = dict.fromkeys(fields, 0)
    for row in rows:
        usage = _mapping(row.get("usage"))
        runtime = _mapping(row.get("runtime"))
        for field in fields:
            totals[field] += _int(usage.get(field, runtime.get(field)))
    return totals


def _average(values: Sequence[int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _rate(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total, 6)


def _format_rate(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    return f"{float(value):.2%}"


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}
