"""Latent patch ranking model."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from features import embed_python_source, vector_delta

from .types import CandidatePatch


@dataclass(frozen=True, slots=True)
class PatchRankingModel:
    """Prototype latent action model used to rank structured patch candidates."""

    path: Path
    embedding_dim: int
    action_delta_prototypes: dict[str, list[float]]
    action_delta_exemplars: dict[str, list[list[float]]]

    @classmethod
    def load(cls, path: Path) -> "PatchRankingModel":
        resolved = path.expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if payload.get("format") != "j3.prototype-jepa.v1":
            raise ValueError(f"unsupported model format in {resolved}")
        embedding_dim = int(payload["embedding_dim"])
        prototypes = {
            str(action): [float(value) for value in vector]
            for action, vector in payload.get("action_delta_prototypes", {}).items()
        }
        exemplars = {
            str(action): [
                [float(value) for value in vector]
                for vector in vectors
                if len(vector) == embedding_dim
            ]
            for action, vectors in payload.get("action_delta_exemplars", {}).items()
        }
        return cls(
            path=resolved,
            embedding_dim=embedding_dim,
            action_delta_prototypes=prototypes,
            action_delta_exemplars=exemplars,
        )

    def score(self, candidate: CandidatePatch) -> float:
        before = embed_python_source(candidate.original_source, dim=self.embedding_dim)
        after = embed_python_source(candidate.patched_source, dim=self.embedding_dim)
        delta = vector_delta(after, before)
        scores: list[tuple[float, float]] = []

        prototype = self.action_delta_prototypes.get(candidate.action.kind.value)
        if prototype is not None:
            scores.append((_cosine_similarity(delta, prototype), 0.50))

        action_exemplars = self.action_delta_exemplars.get(candidate.action.kind.value, [])
        action_score = _nearest_exemplar_similarity(delta, action_exemplars)
        if action_score is not None:
            scores.append((action_score, 0.30))

        git_score = _nearest_exemplar_similarity(delta, self.action_delta_exemplars.get("git_transition", []))
        if git_score is not None:
            scores.append((git_score, 0.20))

        if not scores:
            return -1.0

        total_weight = sum(weight for _, weight in scores)
        return sum(score * weight for score, weight in scores) / total_weight


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _nearest_exemplar_similarity(delta: list[float], exemplars: list[list[float]]) -> float | None:
    if not exemplars:
        return None
    return max(_cosine_similarity(delta, exemplar) for exemplar in exemplars)


