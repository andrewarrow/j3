"""Candidate-relation features for persisted outcome rows."""

from __future__ import annotations

from collections.abc import Mapping

from .values import _int_value


def _add_candidate_relation_features(
    features: dict[str, float],
    action: str,
    candidate: Mapping[str, object],
) -> None:
    rank = _positive_int(candidate.get("rank_index"))
    for relation in ("equivalent", "overlapping"):
        ranks = _rank_list(candidate.get(f"{relation}_candidate_ranks"))
        count = _relation_count(candidate.get(f"{relation}_candidate_count"), ranks)
        if count <= 0:
            continue

        features[f"has_{relation}_candidate"] = 1.0
        features[f"action_has_{relation}_candidate:{action}"] = 1.0
        bucket = _count_bucket(count)
        features[f"{relation}_candidate_count:{bucket}"] = 1.0
        features[f"action_{relation}_candidate_count:{action}:{bucket}"] = 1.0
        features[f"{relation}_candidate_count_scaled"] = min(count, 8) / 8.0

        if rank is None or not ranks:
            continue
        before = sum(1 for other_rank in ranks if other_rank < rank)
        after = sum(1 for other_rank in ranks if other_rank > rank)
        if before:
            features[f"{relation}_candidate_before"] = 1.0
            features[f"action_{relation}_candidate_before:{action}"] = 1.0
        if after:
            features[f"{relation}_candidate_after"] = 1.0
            features[f"action_{relation}_candidate_after:{action}"] = 1.0
        closest = min(abs(other_rank - rank) for other_rank in ranks)
        distance_bucket = _rank_distance_bucket(closest)
        features[f"{relation}_candidate_rank_distance:{distance_bucket}"] = 1.0
        features[
            f"action_{relation}_candidate_rank_distance:{action}:{distance_bucket}"
        ] = 1.0


def _relation_count(value: object, ranks: list[int]) -> int:
    count = _int_value(value, default=-1)
    if count >= 0:
        return count
    return len(ranks)


def _rank_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    ranks: list[int] = []
    for item in value:
        rank = _positive_int(item)
        if rank is not None:
            ranks.append(rank)
    return ranks


def _positive_int(value: object) -> int | None:
    rank = _int_value(value, default=0)
    return rank if rank > 0 else None


def _count_bucket(count: int) -> str:
    if count <= 1:
        return "1"
    if count <= 3:
        return "2_3"
    return "4_plus"


def _rank_distance_bucket(distance: int) -> str:
    if distance <= 1:
        return "1"
    if distance <= 3:
        return "2_3"
    return "4_plus"
