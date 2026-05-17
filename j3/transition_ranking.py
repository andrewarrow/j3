"""Guarded transition-scorer ranking for real repair planning."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from j3.failure_hints import PytestFailureHint
from j3.transition_action_scoring import GATE_READY_FOR_GUARDED_OPT_IN
from j3.transition_scorer_advice import transition_scorer_ranked_candidates

if TYPE_CHECKING:
    from repair.patching.types import CandidatePatch


EXPERIMENTAL_GATE_RESULT = "experimental_allowed_without_product_gate"
TRANSITION_RANKING_DECISION_VERSION = "transition-ranking-decision-v1"


class TransitionRankingGateError(ValueError):
    """Raised when transition-scorer ranking is not allowed."""


def transition_ranking_gate_decision(
    *,
    scorer_report_path: Path | None,
    allow_experimental_ranking: bool = False,
) -> dict[str, object]:
    """Return a guarded opt-in decision or raise when ranking is not allowed."""

    if scorer_report_path is None:
        if not allow_experimental_ranking:
            raise TransitionRankingGateError(
                "--transition-scorer-rank requires --transition-scorer-report "
                "or --allow-experimental-ranking"
            )
        return {
            "schema_version": TRANSITION_RANKING_DECISION_VERSION,
            "mode": "experimental",
            "source": "allow_experimental_ranking",
            "scorer_report": None,
            "gate_result": EXPERIMENTAL_GATE_RESULT,
            "eligible_for_guarded_opt_in": False,
            "allowed": True,
            "reason": "explicit experimental ranking override; no product gate artifact",
        }

    report_path = scorer_report_path.expanduser().resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    readiness_records = _product_readiness_records(report)
    failing_readiness = next(
        (
            readiness
            for readiness in readiness_records
            if not _allows_guarded_opt_in(readiness)
        ),
        None,
    )
    if failing_readiness is not None:
        gate_result = str(failing_readiness.get("gate_result", "unknown"))
        raise TransitionRankingGateError(
            "transition scorer ranking refused: "
            f"product gate {gate_result} is not ready for guarded opt-in"
        )
    readiness = readiness_records[0]
    gate_result = str(readiness.get("gate_result", "unknown"))

    return {
        "schema_version": TRANSITION_RANKING_DECISION_VERSION,
        "mode": "guarded_opt_in",
        "source": "scorer_report",
        "scorer_report": str(report_path),
        "gate_result": gate_result,
        "eligible_for_guarded_opt_in": True,
        "allowed": True,
        "reason": "scorer report passed the guarded opt-in product gate",
        "product_readiness": dict(readiness),
    }


def rank_candidate_patches_with_transition_scorer(
    candidates: Sequence[CandidatePatch],
    *,
    candidate_hints: Sequence[Sequence[PytestFailureHint]] = (),
    context: Mapping[str, object] | None = None,
) -> tuple[CandidatePatch, ...]:
    """Return patch candidates ordered by the transition action scorer."""

    return transition_scorer_ranked_candidates(
        candidates,
        candidate_hints=candidate_hints,
        context=context,
    )


def _product_readiness_records(report: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(report, Mapping):
        raise TransitionRankingGateError("scorer report must be a JSON object")
    records = tuple(_find_product_readiness(report))
    if not records:
        raise TransitionRankingGateError(
            "scorer report is missing a product_readiness object"
        )
    return records


def _find_product_readiness(value: object) -> list[Mapping[str, object]]:
    if isinstance(value, Mapping):
        records: list[Mapping[str, object]] = []
        readiness = value.get("product_readiness")
        if isinstance(readiness, Mapping):
            records.append(readiness)
        for item in value.values():
            records.extend(_find_product_readiness(item))
        return records
    if isinstance(value, list):
        records = []
        for item in value:
            records.extend(_find_product_readiness(item))
        return records
    return []


def _allows_guarded_opt_in(readiness: Mapping[str, object]) -> bool:
    return (
        readiness.get("gate_result") == GATE_READY_FOR_GUARDED_OPT_IN
        and readiness.get("eligible_for_guarded_opt_in") is True
    )
