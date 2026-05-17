"""Shadow transition-scorer advice for real repair plans."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
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


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}
