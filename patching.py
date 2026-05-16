"""Compatibility exports for patch planning and materialization.

The implementation lives under ``repair.patching`` so the patching pipeline can
be maintained as focused modules while existing imports from ``patching`` keep
working.
"""

from repair.patching import (
    CandidatePatch,
    DEFAULT_PATCH_TIMEOUT_SECONDS,
    PatchPlanResult,
    PatchRankingModel,
    generate_candidate_patches,
    plan_and_maybe_apply_patch,
    prioritize_candidate_patches,
    rank_candidate_patches,
    rank_with_candidate_ranker,
)

__all__ = [
    "CandidatePatch",
    "DEFAULT_PATCH_TIMEOUT_SECONDS",
    "PatchPlanResult",
    "PatchRankingModel",
    "generate_candidate_patches",
    "plan_and_maybe_apply_patch",
    "prioritize_candidate_patches",
    "rank_candidate_patches",
    "rank_with_candidate_ranker",
]
