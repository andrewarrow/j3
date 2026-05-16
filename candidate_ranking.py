"""Compatibility exports for candidate ranking.

The implementation lives under ``candidate_ranker`` so training, model loading,
and feature extraction can evolve as focused modules while existing imports from
``candidate_ranking`` keep working.
"""

from candidate_ranker import (
    CandidateLike,
    CandidateRankerModel,
    CandidateRankerTrainingResult,
    candidate_features,
    score_features,
    train_candidate_ranker,
)

__all__ = [
    "CandidateLike",
    "CandidateRankerModel",
    "CandidateRankerTrainingResult",
    "candidate_features",
    "score_features",
    "train_candidate_ranker",
]
