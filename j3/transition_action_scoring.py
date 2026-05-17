"""Evaluation-only scoring for transition action-choice groups."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

from j3.transition_action_choice import validate_transition_action_choice_group


TRANSITION_ACTION_SCORING_EVAL_VERSION = "transition-action-scoring-eval-v1"
TRANSITION_ACTION_SCORER_VERSION = "transition-action-future-scorer-v1"
TRANSITION_ACTION_SCORER_FEATURE_VERSION = "transition-action-local-features-v1"
TRANSITION_PRODUCT_READINESS_VERSION = "transition-product-readiness-v1"
DEFAULT_TOP_K = 3

GATE_NOT_READY_UNDERPERFORMS = "not_ready_underperforms_existing_rank_order"
GATE_READY_FOR_SHADOW_MODE = "ready_for_shadow_mode"
GATE_READY_FOR_GUARDED_OPT_IN = "ready_for_guarded_opt_in"
EXISTING_RANK_ORDER_BASELINE = "existing-rank-order"


def score_transition_action_candidate(
    candidate: Mapping[str, object],
    *,
    group: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Score one action candidate using only non-label local group features."""

    features = _candidate_score_features(candidate, group=group)
    score = (
        0.05 * features["bias"]
        + 0.10 * features["source_embedding_available"]
        + 0.35 * features["candidate_after_embedding_available"]
        + 0.10 * features["candidate_after_available"]
        + 0.15 * features["action_has_params"]
        + 0.06 * features["target_context_available"]
        + 0.50 * features["model_score"]
        + 1.50 * features["ranker_score"]
        + 1.00 * features["failure_hint_score"]
        + 0.04 * min(features["failure_hint_count"], 3.0)
        + 0.02 * min(features["failure_hint_assertion_count"], 5.0)
        + _action_prior(str(features["action_kind"]))
        + _param_prior(str(features["action_kind"]), features["param_signature"])
    )
    return {
        "scorer_version": TRANSITION_ACTION_SCORER_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_FEATURE_VERSION,
        "score": round(score, 12),
        "features": features,
        "tie_breaker": _candidate_order_key(candidate),
    }


def rank_transition_action_candidates(
    group: Mapping[str, object],
    *,
    strategy: str = TRANSITION_ACTION_SCORER_VERSION,
) -> tuple[dict[str, object], ...]:
    """Return candidates in deterministic evaluation order for one strategy."""

    validate_transition_action_choice_group(group)
    candidates = _candidate_list(group)
    if strategy == TRANSITION_ACTION_SCORER_VERSION:
        scored = [
            {
                **candidate,
                "evaluation_score": score_transition_action_candidate(
                    candidate,
                    group=group,
                ),
            }
            for candidate in candidates
        ]
        return tuple(
            sorted(
                scored,
                key=lambda item: (
                    -float(_mapping(item["evaluation_score"])["score"]),
                    _candidate_order_key(item),
                ),
            )
        )
    if strategy == EXISTING_RANK_ORDER_BASELINE:
        return tuple(sorted(candidates, key=lambda item: int(item["rank_index"])))
    if strategy == "stable-lexical-order":
        return tuple(sorted(candidates, key=_candidate_order_key))
    if strategy == "deterministic-random-order":
        group_id = str(group.get("id", ""))
        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    _stable_random_key(group_id, item),
                    _candidate_order_key(item),
                ),
            )
        )
    raise ValueError(f"unknown transition action scoring strategy: {strategy}")


def evaluate_transition_action_choices(
    groups: Sequence[Mapping[str, object]],
    *,
    top_k: int = DEFAULT_TOP_K,
    residual_limit: int = 10,
    include_random_baseline: bool = True,
) -> dict[str, object]:
    """Evaluate local action-choice scoring against simple baselines."""

    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if residual_limit < 0:
        raise ValueError("residual_limit must be >= 0")

    started = time.perf_counter()
    validated_groups = [dict(group) for group in groups]
    for group in validated_groups:
        validate_transition_action_choice_group(group)

    strategy_names = [
        TRANSITION_ACTION_SCORER_VERSION,
        EXISTING_RANK_ORDER_BASELINE,
        "stable-lexical-order",
    ]
    if include_random_baseline:
        strategy_names.append("deterministic-random-order")

    rank_records: dict[str, list[dict[str, object]]] = {
        strategy: [] for strategy in strategy_names
    }
    for group in validated_groups:
        baseline_record = _group_rank_record(
            group,
            rank_transition_action_candidates(
                group,
                strategy=EXISTING_RANK_ORDER_BASELINE,
            ),
            top_k=top_k,
        )
        for strategy in strategy_names:
            rank_records[strategy].append(
                _group_rank_record(
                    group,
                    rank_transition_action_candidates(group, strategy=strategy),
                    top_k=top_k,
                    baseline_first_pass_rank=baseline_record["first_pass_rank"],
                )
            )

    metrics = {
        strategy: _metrics_from_rank_records(records)
        for strategy, records in rank_records.items()
    }
    residuals = _residual_examples(
        rank_records[TRANSITION_ACTION_SCORER_VERSION],
        limit=residual_limit,
    )
    runtime_ms = round((time.perf_counter() - started) * 1000, 3)

    return {
        "schema_version": TRANSITION_ACTION_SCORING_EVAL_VERSION,
        "scorer": {
            "name": TRANSITION_ACTION_SCORER_VERSION,
            "feature_version": TRANSITION_ACTION_SCORER_FEATURE_VERSION,
        },
        "top_k": top_k,
        "group_count": len(validated_groups),
        "solved_group_count": sum(
            1 for group in validated_groups if _passing_rank_set(group)
        ),
        "candidate_count": sum(
            int(group.get("candidate_count", 0)) for group in validated_groups
        ),
        "metrics": metrics,
        "residual_examples": residuals,
        "runtime": {
            "local_runtime_ms": runtime_ms,
            "hosted_llm_api_calls": 0,
            "hosted_llm_prompt_tokens": 0,
            "hosted_llm_completion_tokens": 0,
            "hosted_api_tokens": 0,
            "hosted_repo_context_bytes": 0,
        },
    }


def evaluate_transition_product_readiness(
    scoring_report: Mapping[str, object],
    *,
    scorer_name: str = TRANSITION_ACTION_SCORER_VERSION,
    baseline_name: str = EXISTING_RANK_ORDER_BASELINE,
) -> dict[str, object]:
    """Compare the future scorer to the existing rank order for product gating."""

    metrics = _mapping(scoring_report.get("metrics"))
    scorer_metrics = _mapping(metrics.get(scorer_name))
    baseline_metrics = _mapping(metrics.get(baseline_name))
    solved_group_count = _int_metric(scoring_report.get("solved_group_count"))
    if solved_group_count == 0:
        solved_group_count = max(
            _int_metric(scorer_metrics.get("solved_group_count")),
            _int_metric(baseline_metrics.get("solved_group_count")),
        )

    pass_at_1 = _count_rate_comparison(
        scorer_metrics,
        baseline_metrics,
        count_key="pass_at_1_count",
        rate_key="pass_at_1_solved_rate",
    )
    top_k = _count_rate_comparison(
        scorer_metrics,
        baseline_metrics,
        count_key="top_k_pass_count",
        rate_key="top_k_pass_solved_rate",
    )
    mean_reciprocal_rank = _float_comparison(
        scorer_metrics,
        baseline_metrics,
        key="mean_reciprocal_rank_solved",
    )
    average_candidates_before_first_pass = _float_comparison(
        scorer_metrics,
        baseline_metrics,
        key="average_candidates_validated_before_first_pass",
    )
    scorer_residual_count = _int_metric(scorer_metrics.get("residual_count"))
    baseline_residual_count = _int_metric(baseline_metrics.get("residual_count"))
    reasons = _product_readiness_reasons(
        solved_group_count=solved_group_count,
        pass_at_1_delta=_float_or_none(pass_at_1.get("delta")),
        top_k_delta=_float_or_none(top_k.get("delta")),
        mrr_delta=_float_or_none(mean_reciprocal_rank.get("delta")),
        candidates_before_delta=_float_or_none(
            average_candidates_before_first_pass.get("delta")
        ),
    )
    gate_result = _product_readiness_gate_result(
        reasons=reasons,
        pass_at_1_delta=_float_or_none(pass_at_1.get("delta")),
        top_k_delta=_float_or_none(top_k.get("delta")),
        mrr_delta=_float_or_none(mean_reciprocal_rank.get("delta")),
        candidates_before_delta=_float_or_none(
            average_candidates_before_first_pass.get("delta")
        ),
        residual_count=scorer_residual_count,
    )

    return {
        "schema_version": TRANSITION_PRODUCT_READINESS_VERSION,
        "scorer": scorer_name,
        "baseline": baseline_name,
        "comparison_scope": "solved_action_choice_groups",
        "gate_result": gate_result,
        "eligible_for_shadow_mode": gate_result in {
            GATE_READY_FOR_SHADOW_MODE,
            GATE_READY_FOR_GUARDED_OPT_IN,
        },
        "eligible_for_guarded_opt_in": gate_result == GATE_READY_FOR_GUARDED_OPT_IN,
        "top_k": scoring_report.get("top_k"),
        "solved_group_count": solved_group_count,
        "candidate_count": scoring_report.get("candidate_count", 0),
        "residual_count": scorer_residual_count,
        "baseline_residual_count": baseline_residual_count,
        "reasons": reasons,
        "metrics": {
            "pass_at_1": pass_at_1,
            "top_k": top_k,
            "mean_reciprocal_rank": mean_reciprocal_rank,
            "average_candidates_validated_before_first_pass": {
                **average_candidates_before_first_pass,
                "lower_is_better": True,
            },
        },
        "guarded_opt_in_requirements": {
            "does_not_underperform_existing_rank_order": not reasons,
            "pass_at_1_delta_positive": _positive(
                _float_or_none(pass_at_1.get("delta"))
            ),
            "top_k_delta_non_negative": _non_negative(
                _float_or_none(top_k.get("delta"))
            ),
            "mrr_delta_positive": _positive(
                _float_or_none(mean_reciprocal_rank.get("delta"))
            ),
            "validates_no_more_candidates_before_first_pass": _non_positive(
                _float_or_none(average_candidates_before_first_pass.get("delta"))
            ),
            "residual_count_zero": scorer_residual_count == 0,
        },
    }


def _metrics_from_rank_records(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    group_count = len(records)
    solved_records = [
        record for record in records if record.get("has_passing_candidate") is True
    ]
    solved_group_count = len(solved_records)
    pass_at_1_count = sum(1 for record in records if record.get("pass_at_1") is True)
    top_k_pass_count = sum(1 for record in records if record.get("top_k_pass") is True)
    reciprocal_ranks = [float(record.get("reciprocal_rank", 0.0)) for record in records]
    solved_reciprocal_ranks = [
        float(record.get("reciprocal_rank", 0.0)) for record in solved_records
    ]
    first_pass_ranks = [
        int(record["first_pass_rank"])
        for record in solved_records
        if isinstance(record.get("first_pass_rank"), int)
    ]
    candidates_saved = [
        float(record["candidates_saved_vs_existing_rank_order"])
        for record in solved_records
        if isinstance(record.get("candidates_saved_vs_existing_rank_order"), (int, float))
    ]
    return {
        "group_count": group_count,
        "solved_group_count": solved_group_count,
        "pass_at_1_count": pass_at_1_count,
        "pass_at_1_rate": _rate(pass_at_1_count, group_count),
        "pass_at_1_solved_rate": _rate(pass_at_1_count, solved_group_count),
        "top_k_pass_count": top_k_pass_count,
        "top_k_pass_rate": _rate(top_k_pass_count, group_count),
        "top_k_pass_solved_rate": _rate(top_k_pass_count, solved_group_count),
        "mean_reciprocal_rank": _mean(reciprocal_ranks),
        "mean_reciprocal_rank_solved": _mean(solved_reciprocal_ranks),
        "average_first_passing_rank": _mean(first_pass_ranks),
        "average_candidates_validated_to_first_pass": _mean(first_pass_ranks),
        "average_candidates_validated_before_first_pass": _mean(
            [rank - 1 for rank in first_pass_ranks]
        ),
        "average_candidates_saved_vs_existing_rank_order": _mean(candidates_saved),
        "residual_count": solved_group_count - pass_at_1_count,
    }


def _group_rank_record(
    group: Mapping[str, object],
    ranked_candidates: Sequence[Mapping[str, object]],
    *,
    top_k: int,
    baseline_first_pass_rank: object | None = None,
) -> dict[str, object]:
    passing_ranks = _passing_rank_set(group)
    first_pass_position: int | None = None
    for position, candidate in enumerate(ranked_candidates, start=1):
        if int(candidate["rank_index"]) in passing_ranks:
            first_pass_position = position
            break

    top_candidate = ranked_candidates[0] if ranked_candidates else None
    top_passed = (
        top_candidate is not None
        and int(top_candidate["rank_index"]) in passing_ranks
    )
    top_k_window = ranked_candidates[: min(top_k, len(ranked_candidates))]
    top_k_pass = any(int(candidate["rank_index"]) in passing_ranks for candidate in top_k_window)
    baseline_rank = (
        baseline_first_pass_rank
        if baseline_first_pass_rank is not None
        else group.get("first_passing_index")
    )
    candidates_saved = None
    if isinstance(baseline_rank, int) and isinstance(first_pass_position, int):
        candidates_saved = baseline_rank - first_pass_position

    return {
        "group_id": group.get("id"),
        "grouping": group.get("grouping"),
        "candidate_count": len(ranked_candidates),
        "passing_candidate_ranks": sorted(passing_ranks),
        "has_passing_candidate": bool(passing_ranks),
        "ranked_candidate_ranks": [
            int(candidate["rank_index"]) for candidate in ranked_candidates
        ],
        "top_candidate": _candidate_summary(top_candidate) if top_candidate else None,
        "first_pass_rank": first_pass_position,
        "pass_at_1": top_passed,
        "top_k_pass": top_k_pass,
        "reciprocal_rank": (
            round(1.0 / first_pass_position, 12)
            if isinstance(first_pass_position, int)
            else 0.0
        ),
        "candidates_saved_vs_existing_rank_order": candidates_saved,
    }


def _residual_examples(
    records: Sequence[Mapping[str, object]],
    *,
    limit: int,
) -> list[dict[str, object]]:
    residuals: list[dict[str, object]] = []
    for record in records:
        if record.get("has_passing_candidate") is not True:
            continue
        if record.get("pass_at_1") is True:
            continue
        residuals.append(
            {
                "group_id": record.get("group_id"),
                "grouping": record.get("grouping"),
                "selected_top_candidate": record.get("top_candidate"),
                "passing_candidate_ranks": record.get("passing_candidate_ranks"),
                "first_pass_rank": record.get("first_pass_rank"),
                "ranked_candidate_ranks": record.get("ranked_candidate_ranks"),
            }
        )
        if len(residuals) >= limit:
            break
    return residuals


def _candidate_score_features(
    candidate: Mapping[str, object],
    *,
    group: Mapping[str, object] | None,
) -> dict[str, Any]:
    action = _mapping(candidate.get("action"))
    scores = _mapping(candidate.get("scores"))
    validation = _mapping(candidate.get("validation"))
    source_context = _mapping(candidate.get("source_context"))
    candidate_after = _mapping(candidate.get("candidate_after"))
    target_context = _mapping(candidate.get("target_context"))
    params = _mapping(action.get("params"))
    failure_hints = _list(validation.get("failure_hints"))

    action_kind = str(action.get("kind", ""))
    ranker_score = _score_value(scores.get("ranker_score"))
    model_score = _score_value(scores.get("model_score"))
    failure_hint_score = _score_value(scores.get("failure_hint_score"))

    return {
        "bias": 1.0,
        "group_candidate_count": float(group.get("candidate_count", 0)) if group else 0.0,
        "rank_index": float(candidate.get("rank_index", 0)),
        "action_kind": action_kind,
        "action_has_params": 1.0 if params else 0.0,
        "param_signature": _json_signature(params),
        "source_embedding_available": _bool_float(
            source_context.get("embedding_available")
        ),
        "candidate_after_available": _bool_float(candidate_after.get("available")),
        "candidate_after_embedding_available": _bool_float(
            candidate_after.get("embedding_available")
        ),
        "target_context_available": 1.0 if target_context else 0.0,
        "ranker_score": ranker_score,
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "failure_hint_count": float(len(failure_hints)),
        "failure_hint_assertion_count": float(
            sum(len(_list(_mapping(hint).get("assertions"))) for hint in failure_hints)
        ),
    }


def _candidate_summary(candidate: Mapping[str, object] | None) -> dict[str, object] | None:
    if candidate is None:
        return None
    action = _mapping(candidate.get("action"))
    evaluation_score = _mapping(candidate.get("evaluation_score"))
    validation = _mapping(candidate.get("validation"))
    return {
        "rank_index": candidate.get("rank_index"),
        "action_kind": action.get("kind"),
        "params": action.get("params"),
        "symbol": action.get("symbol"),
        "score": evaluation_score.get("score"),
        "passed": validation.get("passed"),
    }


def _candidate_list(group: Mapping[str, object]) -> list[dict[str, object]]:
    candidates = group.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("group.candidates must be a list")
    return [dict(_mapping(candidate)) for candidate in candidates]


def _passing_rank_set(group: Mapping[str, object]) -> set[int]:
    ranks = group.get("passing_candidate_ranks")
    if not isinstance(ranks, list):
        return set()
    return {int(rank) for rank in ranks if isinstance(rank, int) and not isinstance(rank, bool)}


def _candidate_order_key(candidate: Mapping[str, object]) -> tuple[str, int]:
    action = _mapping(candidate.get("action"))
    signature = {
        "action": action.get("kind"),
        "file_path": action.get("file_path"),
        "symbol": action.get("symbol"),
        "node_kind": action.get("node_kind"),
        "params": action.get("params"),
        "reason": action.get("reason"),
    }
    return _json_signature(signature), int(candidate.get("rank_index", 0))


def _stable_random_key(group_id: str, candidate: Mapping[str, object]) -> str:
    digest_input = f"{group_id}\0{_candidate_order_key(candidate)[0]}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def _action_prior(action_kind: str) -> float:
    priors = {
        "change_operator": 0.10,
        "change_literal": 0.08,
        "change_dict_key": 0.08,
        "change_dict_value": 0.08,
        "change_subscript_key": 0.08,
        "rename_symbol": 0.06,
        "add_keyword_arg": 0.05,
        "add_import": 0.04,
        "add_import_fallback": 0.04,
        "propagate_signature": 0.04,
    }
    return priors.get(action_kind, 0.0)


def _param_prior(action_kind: str, param_signature: object) -> float:
    signature = str(param_signature)
    if action_kind == "change_operator" and '"to":"+"' in signature:
        return 0.12
    if "None" in signature or "null" in signature:
        return -0.04
    return 0.0


def _score_value(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 0.0
    numeric = float(value)
    if numeric > 1.0:
        return numeric / 100.0
    if numeric < -1.0:
        return numeric / 100.0
    return numeric


def _bool_float(value: object) -> float:
    return 1.0 if value is True else 0.0


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _json_signature(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 12)


def _mean(values: Sequence[float | int]) -> float | None:
    if not values:
        return None
    return round(sum(float(value) for value in values) / len(values), 12)


def _count_rate_comparison(
    scorer_metrics: Mapping[str, object],
    baseline_metrics: Mapping[str, object],
    *,
    count_key: str,
    rate_key: str,
) -> dict[str, object]:
    scorer_rate = _float_or_none(scorer_metrics.get(rate_key))
    baseline_rate = _float_or_none(baseline_metrics.get(rate_key))
    return {
        "scorer_count": _int_metric(scorer_metrics.get(count_key)),
        "baseline_count": _int_metric(baseline_metrics.get(count_key)),
        "scorer_rate": scorer_rate,
        "baseline_rate": baseline_rate,
        "delta": _delta(scorer_rate, baseline_rate),
    }


def _float_comparison(
    scorer_metrics: Mapping[str, object],
    baseline_metrics: Mapping[str, object],
    *,
    key: str,
) -> dict[str, object]:
    scorer_value = _float_or_none(scorer_metrics.get(key))
    baseline_value = _float_or_none(baseline_metrics.get(key))
    return {
        "scorer": scorer_value,
        "baseline": baseline_value,
        "delta": _delta(scorer_value, baseline_value),
    }


def _product_readiness_reasons(
    *,
    solved_group_count: int,
    pass_at_1_delta: float | None,
    top_k_delta: float | None,
    mrr_delta: float | None,
    candidates_before_delta: float | None,
) -> list[str]:
    reasons: list[str] = []
    if solved_group_count <= 0:
        reasons.append("no_solved_action_choice_groups")
    if _negative(pass_at_1_delta):
        reasons.append("pass_at_1_under_existing_rank_order")
    if _negative(top_k_delta):
        reasons.append("top_k_under_existing_rank_order")
    if _negative(mrr_delta):
        reasons.append("mrr_under_existing_rank_order")
    if _positive(candidates_before_delta):
        reasons.append("validates_more_candidates_before_first_pass")
    return reasons


def _product_readiness_gate_result(
    *,
    reasons: Sequence[str],
    pass_at_1_delta: float | None,
    top_k_delta: float | None,
    mrr_delta: float | None,
    candidates_before_delta: float | None,
    residual_count: int,
) -> str:
    if reasons:
        return GATE_NOT_READY_UNDERPERFORMS
    if (
        _positive(pass_at_1_delta)
        and _non_negative(top_k_delta)
        and _positive(mrr_delta)
        and _non_positive(candidates_before_delta)
        and residual_count == 0
    ):
        return GATE_READY_FOR_GUARDED_OPT_IN
    return GATE_READY_FOR_SHADOW_MODE


def _delta(scorer_value: float | None, baseline_value: float | None) -> float | None:
    if scorer_value is None or baseline_value is None:
        return None
    return round(scorer_value - baseline_value, 12)


def _int_metric(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _negative(value: float | None) -> bool:
    return value is not None and value < -1e-12


def _positive(value: float | None) -> bool:
    return value is not None and value > 1e-12


def _non_negative(value: float | None) -> bool:
    return value is not None and value >= -1e-12


def _non_positive(value: float | None) -> bool:
    return value is not None and value <= 1e-12
