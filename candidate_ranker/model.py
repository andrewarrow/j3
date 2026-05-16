"""Model loading and scoring for the candidate ranker."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .constants import RANKER_FORMAT
from .features import candidate_features
from .types import CandidateLike


@dataclass(frozen=True, slots=True)
class CandidateRankerModel:
    """Small linear ranker over candidate diagnostics features."""

    path: Path
    weights: dict[str, float]
    bias: float = 0.0

    @classmethod
    def load(cls, path: Path) -> "CandidateRankerModel":
        resolved = path.expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if payload.get("format") != RANKER_FORMAT:
            raise ValueError(f"unsupported candidate ranker format in {resolved}")
        return cls(
            path=resolved,
            weights={str(name): float(value) for name, value in payload.get("weights", {}).items()},
            bias=float(payload.get("bias", 0.0)),
        )

    def score(self, candidate: CandidateLike, hints: list[object] | tuple[object, ...] = ()) -> float:
        return score_features(candidate_features(candidate, hints=hints), self.weights, self.bias)


def score_features(features: Mapping[str, float], weights: Mapping[str, float], bias: float = 0.0) -> float:
    return bias + sum(weights.get(name, 0.0) * value for name, value in features.items())
