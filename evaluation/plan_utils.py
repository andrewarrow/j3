"""Shared helpers for interpreting patch plan results."""

from __future__ import annotations

from j3.patching import CandidatePatch, PatchPlanResult


def _average(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _first_passing_index(plan: PatchPlanResult) -> int | None:
    if plan.first_passing_index is not None:
        return plan.first_passing_index
    if plan.selected is None:
        return None
    for index, candidate in enumerate(plan.tested_candidates, start=1):
        if candidate == plan.selected:
            return index
    return plan.candidates_tested if plan.candidates_tested > 0 else None


def _passing_candidates(plan: PatchPlanResult) -> tuple[CandidatePatch, ...]:
    if plan.passing_candidates:
        return plan.passing_candidates
    if plan.selected is None:
        return ()
    return (plan.selected,)


def _candidate_passed(candidate: CandidatePatch, plan: PatchPlanResult) -> bool:
    return any(candidate == passing for passing in _passing_candidates(plan))


def _candidates_tested_before_pass(plan: PatchPlanResult) -> int | None:
    first_passing_index = _first_passing_index(plan)
    if first_passing_index is None:
        return None
    return first_passing_index - 1


def _candidates_tested_after_pass(plan: PatchPlanResult) -> int:
    first_passing_index = _first_passing_index(plan)
    if first_passing_index is None:
        return 0
    return max(0, plan.candidates_tested - first_passing_index)
