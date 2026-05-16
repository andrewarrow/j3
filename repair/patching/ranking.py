"""Candidate ranking and failure-hint prioritization."""

from __future__ import annotations

from dataclasses import replace

from actions import PatchActionKind
from candidate_ranking import CandidateRankerModel
from failure_hints import PytestFailureHint

from .model import PatchRankingModel
from .types import CandidatePatch


def rank_candidate_patches(
    candidates: list[CandidatePatch],
    model: PatchRankingModel,
) -> list[CandidatePatch]:
    """Sort candidates by learned latent delta similarity."""

    scored = [
        CandidatePatch(
            file_path=candidate.file_path,
            action=candidate.action,
            edit=candidate.edit,
            original_source=candidate.original_source,
            patched_source=candidate.patched_source,
            reason=candidate.reason,
            model_score=model.score(candidate),
            failure_hint_score=candidate.failure_hint_score,
            ranker_score=candidate.ranker_score,
            target_context=candidate.target_context,
        )
        for candidate in candidates
    ]
    return sorted(scored, key=lambda candidate: candidate.model_score or -1.0, reverse=True)


def prioritize_candidate_patches(
    candidates: list[CandidatePatch],
    hints: list[PytestFailureHint],
    ranker: CandidateRankerModel | None = None,
) -> list[CandidatePatch]:
    """Sort candidates by structured evidence from the failing test output."""

    scored: list[CandidatePatch] = []
    for candidate in candidates:
        hint_scored = replace(
            candidate,
            failure_hint_score=_failure_hint_score(candidate, hints),
            ranker_score=candidate.ranker_score,
        )
        if ranker is not None:
            hint_scored = replace(
                hint_scored,
                ranker_score=ranker.score(hint_scored, hints),
            )
        scored.append(hint_scored)

    if ranker is not None:
        return sorted(
            scored,
            key=lambda candidate: (
                candidate.ranker_score if candidate.ranker_score is not None else 0.0,
                candidate.failure_hint_score,
                candidate.model_score if candidate.model_score is not None else 0.0,
            ),
            reverse=True,
        )

    return sorted(
        scored,
        key=lambda candidate: (
            candidate.failure_hint_score,
            candidate.model_score if candidate.model_score is not None else 0.0,
        ),
        reverse=True,
    )


def rank_with_candidate_ranker(
    candidates: list[CandidatePatch],
    ranker: CandidateRankerModel,
    *,
    hints: list[PytestFailureHint],
) -> list[CandidatePatch]:
    scored = [
        CandidatePatch(
            file_path=candidate.file_path,
            action=candidate.action,
            edit=candidate.edit,
            original_source=candidate.original_source,
            patched_source=candidate.patched_source,
            reason=candidate.reason,
            model_score=candidate.model_score,
            failure_hint_score=candidate.failure_hint_score,
            ranker_score=ranker.score(candidate, hints),
            target_context=candidate.target_context,
        )
        for candidate in candidates
    ]
    return sorted(
        scored,
        key=lambda candidate: (
            candidate.ranker_score if candidate.ranker_score is not None else 0.0,
            candidate.failure_hint_score,
            candidate.model_score if candidate.model_score is not None else 0.0,
        ),
        reverse=True,
    )


def _failure_hint_score(candidate: CandidatePatch, hints: list[PytestFailureHint]) -> float:
    if not hints:
        return 0.0
    return max(_score_against_hint(candidate, hint) for hint in hints)


def _score_against_hint(candidate: CandidatePatch, hint: PytestFailureHint) -> float:
    score = 0.0
    symbol = candidate.action.target.symbol
    if symbol and symbol in hint.function_names:
        score += 40.0

    if candidate.file_path in hint.source_files:
        score += 20.0

    for location in hint.traceback_locations:
        if candidate.file_path == location.file_path and candidate.action.target.start_line == location.line:
            score += 12.0
            break

    for diagnostic in hint.tool_diagnostics:
        if candidate.file_path == diagnostic.file_path and candidate.action.target.start_line == diagnostic.line:
            score += 12.0
            break

    if hint.exception_type == "ZeroDivisionError" and candidate.action.kind == PatchActionKind.INSERT_GUARD:
        score += 20.0

    if candidate.action.kind == PatchActionKind.ADD_IMPORT:
        imported = str(candidate.action.params.get("name", ""))
        module = str(candidate.action.params.get("module", ""))
        if imported in hint.missing_names or module in hint.missing_modules:
            score += 60.0

    if candidate.action.kind == PatchActionKind.CHANGE_ATTRIBUTE:
        original = str(candidate.action.params.get("from", ""))
        if original in hint.missing_attributes:
            score += 50.0

    if candidate.action.kind == PatchActionKind.CHANGE_SUBSCRIPT_KEY:
        original = str(candidate.action.params.get("from", ""))
        replacement = str(candidate.action.params.get("to", ""))
        if original in hint.missing_keys:
            score += 60.0
        if any(key in replacement for key in hint.missing_keys):
            score += 10.0
        if hint.assertions:
            score += 10.0

    if candidate.action.kind == PatchActionKind.WRAP_TRY_EXCEPT:
        exception = str(candidate.action.params.get("exception", ""))
        if exception and exception == hint.exception_type:
            score += 35.0

    if candidate.action.kind == PatchActionKind.SWAP_CALL_ARG and hint.assertions:
        score += 10.0

    if candidate.action.kind in {PatchActionKind.RENAME_SYMBOL, PatchActionKind.PROPAGATE_SIGNATURE}:
        original = str(candidate.action.params.get("from", ""))
        replacement = str(candidate.action.params.get("to", ""))
        if original in hint.missing_names or original in hint.type_error_names:
            score += 45.0
        if replacement in hint.type_error_names:
            score += 20.0

    if any(isinstance(assertion.expected, bool) for assertion in hint.assertions):
        if candidate.action.kind in {PatchActionKind.CHANGE_OPERATOR, PatchActionKind.MODIFY_CONDITION}:
            score += 10.0

    literal_delta_score = _literal_hint_score(candidate, hint)
    if literal_delta_score:
        score += literal_delta_score

    if candidate.action.kind == PatchActionKind.REPLACE_EXPR and hint.assertions:
        score += 5.0

    return score


def _literal_hint_score(candidate: CandidatePatch, hint: PytestFailureHint) -> float:
    if candidate.action.kind != PatchActionKind.CHANGE_LITERAL:
        return 0.0
    original = candidate.action.params.get("from")
    replacement = candidate.action.params.get("to")
    if isinstance(original, str) and isinstance(replacement, str):
        score = 0.0
        if original in hint.missing_keys:
            score += 35.0
        if any(key in replacement for key in hint.missing_keys):
            score += 8.0
        return score

    if not isinstance(original, (int, float)) or isinstance(original, bool):
        return 0.0
    if not isinstance(replacement, (int, float)) or isinstance(replacement, bool):
        return 0.0

    score = 0.0
    for assertion in hint.assertions:
        delta = assertion.numeric_delta
        if original != 0 and delta is not None and replacement == original + delta:
            score += 40.0
        if replacement == assertion.expected:
            score += 10.0
    return score
