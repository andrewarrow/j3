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
TRANSITION_ACTION_SCORER_V2_VERSION = "transition-action-future-scorer-v2"
TRANSITION_ACTION_SCORER_V3_VERSION = "transition-action-future-scorer-v3"
TRANSITION_ACTION_SCORER_FEATURE_VERSION = "transition-action-local-features-v1"
TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION = "transition-action-local-features-v2"
TRANSITION_ACTION_SCORER_V3_FEATURE_VERSION = "transition-action-shadow-features-v3"
TRANSITION_ACTION_SCORER_V2_CALIBRATION_VERSION = (
    "transition-action-future-scorer-v2-calibration-v1"
)
TRANSITION_ACTION_SCORER_V3_REPORT_VERSION = (
    "transition-action-future-scorer-v3-report-v1"
)
TRANSITION_PRODUCT_READINESS_VERSION = "transition-product-readiness-v1"
DEFAULT_TOP_K = 3
DEFAULT_V2_VALIDATION_FRACTION = 0.25
DEFAULT_V2_EPOCHS = 30
DEFAULT_V2_LEARNING_RATE = 0.1
DEFAULT_V2_MARGIN = 1.0
DEFAULT_V3_VALIDATION_FRACTION = 0.25

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


def score_transition_action_candidate_v2(
    candidate: Mapping[str, object],
    *,
    group: Mapping[str, object],
    model: Mapping[str, object],
) -> dict[str, object]:
    """Score one candidate with an evaluation-only fitted V2 model."""

    weights = _float_mapping(_mapping(model.get("weights")))
    bias = _float_or_default(model.get("bias"), 0.0)
    features = _candidate_v2_features(candidate, group=group)
    score = bias + sum(weights.get(name, 0.0) * value for name, value in features.items())
    return {
        "scorer_version": TRANSITION_ACTION_SCORER_V2_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION,
        "score": round(score, 12),
        "features": features,
        "tie_breaker": _candidate_order_key(candidate),
    }


def score_transition_action_candidate_v3(
    candidate: Mapping[str, object],
    *,
    group: Mapping[str, object],
    model: Mapping[str, object],
) -> dict[str, object]:
    """Score one candidate with an evaluation-only fitted V3 shadow model."""

    weights = _float_mapping(_mapping(model.get("weights")))
    bias = _float_or_default(model.get("bias"), 0.0)
    features = _candidate_v3_features(
        candidate,
        group=group,
        model=model,
    )
    score = bias + sum(weights.get(name, 0.0) * value for name, value in features.items())
    return {
        "scorer_version": TRANSITION_ACTION_SCORER_V3_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V3_FEATURE_VERSION,
        "score": round(score, 12),
        "features": features,
        "tie_breaker": _candidate_order_key(candidate),
    }


def rank_transition_action_candidates(
    group: Mapping[str, object],
    *,
    strategy: str = TRANSITION_ACTION_SCORER_VERSION,
    scorer_model: Mapping[str, object] | None = None,
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
    if strategy == TRANSITION_ACTION_SCORER_V2_VERSION:
        if scorer_model is None:
            raise ValueError("transition-action-future-scorer-v2 requires scorer_model")
        scored = [
            {
                **candidate,
                "evaluation_score": score_transition_action_candidate_v2(
                    candidate,
                    group=group,
                    model=scorer_model,
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
    if strategy == TRANSITION_ACTION_SCORER_V3_VERSION:
        if scorer_model is None:
            raise ValueError("transition-action-future-scorer-v3 requires scorer_model")
        scored = [
            {
                **candidate,
                "evaluation_score": score_transition_action_candidate_v3(
                    candidate,
                    group=group,
                    model=scorer_model,
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
    include_v2: bool = True,
    v2_split_by: str = "task_family",
    v2_validation_fraction: float = DEFAULT_V2_VALIDATION_FRACTION,
    v2_epochs: int = DEFAULT_V2_EPOCHS,
    v2_learning_rate: float = DEFAULT_V2_LEARNING_RATE,
    v2_margin: float = DEFAULT_V2_MARGIN,
) -> dict[str, object]:
    """Evaluate local action-choice scoring against simple baselines."""

    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if residual_limit < 0:
        raise ValueError("residual_limit must be >= 0")
    if include_v2 and not 0.0 < v2_validation_fraction < 1.0:
        raise ValueError("v2_validation_fraction must be > 0 and < 1")

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

    v2_calibration: dict[str, object] | None = None
    if include_v2:
        v2_calibration = calibrate_transition_action_scorer_v2(
            validated_groups,
            top_k=top_k,
            split_by=v2_split_by,
            validation_fraction=v2_validation_fraction,
            epochs=v2_epochs,
            learning_rate=v2_learning_rate,
            margin=v2_margin,
        )
        if v2_calibration.get("available") is True:
            model = _mapping(v2_calibration.get("model"))
            strategy_names.append(TRANSITION_ACTION_SCORER_V2_VERSION)
            rank_records[TRANSITION_ACTION_SCORER_V2_VERSION] = []
            for group in validated_groups:
                baseline_record = _group_rank_record(
                    group,
                    rank_transition_action_candidates(
                        group,
                        strategy=EXISTING_RANK_ORDER_BASELINE,
                    ),
                    top_k=top_k,
                )
                rank_records[TRANSITION_ACTION_SCORER_V2_VERSION].append(
                    _group_rank_record(
                        group,
                        rank_transition_action_candidates(
                            group,
                            strategy=TRANSITION_ACTION_SCORER_V2_VERSION,
                            scorer_model=model,
                        ),
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
        "scorers": [
            {
                "name": TRANSITION_ACTION_SCORER_VERSION,
                "feature_version": TRANSITION_ACTION_SCORER_FEATURE_VERSION,
            },
            *(
                [
                    {
                        "name": TRANSITION_ACTION_SCORER_V2_VERSION,
                        "feature_version": TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION,
                        "calibration_version": (
                            TRANSITION_ACTION_SCORER_V2_CALIBRATION_VERSION
                        ),
                    }
                ]
                if v2_calibration and v2_calibration.get("available") is True
                else []
            ),
        ],
        "top_k": top_k,
        "group_count": len(validated_groups),
        "solved_group_count": sum(
            1 for group in validated_groups if _passing_rank_set(group)
        ),
        "candidate_count": sum(
            int(group.get("candidate_count", 0)) for group in validated_groups
        ),
        "metrics": metrics,
        "calibration": v2_calibration,
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


def calibrate_transition_action_scorer_v2(
    groups: Sequence[Mapping[str, object]],
    *,
    top_k: int = DEFAULT_TOP_K,
    split_by: str = "task_family",
    validation_fraction: float = DEFAULT_V2_VALIDATION_FRACTION,
    epochs: int = DEFAULT_V2_EPOCHS,
    learning_rate: float = DEFAULT_V2_LEARNING_RATE,
    margin: float = DEFAULT_V2_MARGIN,
) -> dict[str, object]:
    """Fit and validate an evaluation-only V2 scorer from candidate outcomes."""

    if split_by not in {"task_family", "source_file"}:
        raise ValueError("split_by must be task_family or source_file")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be > 0 and < 1")
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    if learning_rate <= 0.0:
        raise ValueError("learning_rate must be positive")
    if margin <= 0.0:
        raise ValueError("margin must be positive")

    validated_groups = [dict(group) for group in groups]
    for group in validated_groups:
        validate_transition_action_choice_group(group)

    train_groups, validation_groups, split = _split_groups_for_v2(
        validated_groups,
        split_by=split_by,
        validation_fraction=validation_fraction,
    )
    pairs = _v2_training_pairs(train_groups)
    if not pairs:
        return {
            "schema_version": TRANSITION_ACTION_SCORER_V2_CALIBRATION_VERSION,
            "available": False,
            "scorer": TRANSITION_ACTION_SCORER_V2_VERSION,
            "feature_version": TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION,
            "reason": "training split had no solved groups with failed candidates",
            "split": split,
            "training": {
                "group_count": len(train_groups),
                "pair_count": 0,
            },
        }

    weights, mistakes = _fit_v2_pairwise_weights(
        pairs,
        epochs=epochs,
        learning_rate=learning_rate,
        margin=margin,
    )
    model = {
        "schema_version": "transition-action-future-scorer-v2-model-v1",
        "name": TRANSITION_ACTION_SCORER_V2_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION,
        "bias": 0.0,
        "weights": dict(sorted(weights.items())),
    }
    validation_metrics = _evaluate_v2_validation(
        validation_groups,
        model=model,
        top_k=top_k,
    )
    readiness_report = {
        "metrics": validation_metrics,
        "solved_group_count": sum(
            1 for group in validation_groups if _passing_rank_set(group)
        ),
        "candidate_count": sum(
            int(group.get("candidate_count", 0)) for group in validation_groups
        ),
        "top_k": top_k,
    }
    validation_readiness = evaluate_transition_product_readiness(
        readiness_report,
        scorer_name=TRANSITION_ACTION_SCORER_V2_VERSION,
        baseline_name=EXISTING_RANK_ORDER_BASELINE,
    )
    if split.get("held_out") is not True:
        validation_readiness = {
            **validation_readiness,
            "eligible_for_guarded_opt_in": False,
            "guarded_opt_in_blocked_reason": "validation split is not held out",
        }

    return {
        "schema_version": TRANSITION_ACTION_SCORER_V2_CALIBRATION_VERSION,
        "available": True,
        "scorer": TRANSITION_ACTION_SCORER_V2_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION,
        "split": split,
        "parameters": {
            "top_k": top_k,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "margin": margin,
        },
        "training": {
            "group_count": len(train_groups),
            "candidate_count": sum(
                int(group.get("candidate_count", 0)) for group in train_groups
            ),
            "pair_count": len(pairs),
            "features": len(weights),
            "mistakes": mistakes,
        },
        "validation": {
            "group_count": len(validation_groups),
            "candidate_count": sum(
                int(group.get("candidate_count", 0)) for group in validation_groups
            ),
            "metrics": validation_metrics,
            "product_readiness": validation_readiness,
        },
        "model": model,
    }


def evaluate_transition_shadow_scorer_v3(
    groups: Sequence[Mapping[str, object]],
    shadow_outcomes: Sequence[Mapping[str, object]],
    *,
    top_k: int = DEFAULT_TOP_K,
    split_by: str = "task_family",
    validation_fraction: float = DEFAULT_V3_VALIDATION_FRACTION,
    epochs: int = DEFAULT_V2_EPOCHS,
    learning_rate: float = DEFAULT_V2_LEARNING_RATE,
    margin: float = DEFAULT_V2_MARGIN,
    allow_production_rank_feature: bool = False,
    residual_limit: int = 10,
) -> dict[str, object]:
    """Train and evaluate the held-out V3 scorer from shadow outcome rows."""

    if split_by not in {"task_family", "source_file", "repo", "order"}:
        raise ValueError("split_by must be task_family, source_file, repo, or order")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be > 0 and < 1")
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    if learning_rate <= 0.0:
        raise ValueError("learning_rate must be positive")
    if margin <= 0.0:
        raise ValueError("margin must be positive")
    if residual_limit < 0:
        raise ValueError("residual_limit must be >= 0")

    started = time.perf_counter()
    validated_groups = [dict(group) for group in groups]
    for group in validated_groups:
        validate_transition_action_choice_group(group)

    shadow_by_key = _shadow_outcomes_by_group_key(shadow_outcomes)
    matched_groups = [
        _group_with_shadow_outcome(group, shadow_by_key[_group_shadow_key(group)])
        for group in validated_groups
        if _group_shadow_key(group) in shadow_by_key
    ]
    train_groups, validation_groups, split = _split_groups_for_v3(
        matched_groups,
        split_by=split_by,
        validation_fraction=validation_fraction,
    )
    pairs = _v3_training_pairs(
        train_groups,
        allow_production_rank_feature=allow_production_rank_feature,
    )

    usage = _shadow_usage_totals(shadow_outcomes)
    common: dict[str, object] = {
        "schema_version": TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
        "decision": "evaluation_only_not_wired_to_production",
        "scorer": TRANSITION_ACTION_SCORER_V3_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V3_FEATURE_VERSION,
        "available": False,
        "parameters": {
            "top_k": top_k,
            "split_by": split_by,
            "validation_fraction": validation_fraction,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "margin": margin,
            "allow_production_rank_feature": allow_production_rank_feature,
        },
        "shadow_outcomes": _shadow_outcome_summary_for_v3(
            shadow_outcomes,
            matched_group_count=len(matched_groups),
        ),
        "runtime": {
            "local_runtime_ms": 0.0,
            **usage,
        },
    }
    if not pairs:
        runtime_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            **common,
            "reason": "training split had no solved shadow groups with failed candidates",
            "split": split,
            "training": {
                "group_count": len(train_groups),
                "pair_count": 0,
            },
            "runtime": {
                "local_runtime_ms": runtime_ms,
                **usage,
            },
        }

    weights, mistakes = _fit_v2_pairwise_weights(
        pairs,
        epochs=epochs,
        learning_rate=learning_rate,
        margin=margin,
    )
    model = {
        "schema_version": "transition-action-future-scorer-v3-model-v1",
        "name": TRANSITION_ACTION_SCORER_V3_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V3_FEATURE_VERSION,
        "bias": 0.0,
        "weights": dict(sorted(weights.items())),
        "allow_production_rank_feature": allow_production_rank_feature,
    }

    v2_model = _fit_v2_model_for_groups(
        train_groups,
        epochs=epochs,
        learning_rate=learning_rate,
        margin=margin,
    )
    validation_metrics = _evaluate_v3_validation(
        validation_groups,
        v3_model=model,
        v2_model=v2_model,
        top_k=top_k,
    )
    readiness_report = {
        "metrics": validation_metrics,
        "solved_group_count": sum(
            1 for group in validation_groups if _passing_rank_set(group)
        ),
        "candidate_count": sum(
            int(group.get("candidate_count", 0)) for group in validation_groups
        ),
        "top_k": top_k,
    }
    validation_readiness = evaluate_transition_product_readiness(
        readiness_report,
        scorer_name=TRANSITION_ACTION_SCORER_V3_VERSION,
        baseline_name=EXISTING_RANK_ORDER_BASELINE,
    )
    if split.get("held_out") is not True:
        validation_readiness = {
            **validation_readiness,
            "eligible_for_guarded_opt_in": False,
            "guarded_opt_in_blocked_reason": "validation split is not held out",
        }

    runtime_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        **common,
        "available": True,
        "split": split,
        "training": {
            "group_count": len(train_groups),
            "candidate_count": sum(
                int(group.get("candidate_count", 0)) for group in train_groups
            ),
            "pair_count": len(pairs),
            "features": len(weights),
            "mistakes": mistakes,
        },
        "validation": {
            "group_count": len(validation_groups),
            "candidate_count": sum(
                int(group.get("candidate_count", 0)) for group in validation_groups
            ),
            "metrics": validation_metrics,
            "product_readiness": validation_readiness,
            "residual_examples": _residual_examples(
                _rank_records_for_strategy(
                    validation_groups,
                    strategy=TRANSITION_ACTION_SCORER_V3_VERSION,
                    scorer_model=model,
                    top_k=top_k,
                ),
                limit=residual_limit,
            ),
        },
        "model": model,
        "runtime": {
            "local_runtime_ms": runtime_ms,
            **usage,
        },
    }


def format_transition_shadow_scorer_v3_report(report: Mapping[str, object]) -> str:
    """Format a V3 held-out shadow scorer report for CLI output."""

    split = _mapping(report.get("split"))
    shadow = _mapping(report.get("shadow_outcomes"))
    training = _mapping(report.get("training"))
    validation = _mapping(report.get("validation"))
    metrics = _mapping(validation.get("metrics"))
    readiness = _mapping(validation.get("product_readiness"))
    runtime = _mapping(report.get("runtime"))
    lines = [
        "j3 evaluate-transition-shadow-scorer complete",
        "mode: evaluation-only",
        f"scorer: {report.get('scorer')}",
        f"available: {report.get('available')}",
        f"split: {split.get('split_by')} held_out={split.get('held_out')}",
        f"shadow rows: {shadow.get('row_count', 0)}",
        f"joined known rows: {shadow.get('joined_known_validation_rows', 0)}",
        f"matched groups: {shadow.get('matched_action_choice_groups', 0)}",
        f"training groups: {training.get('group_count', 0)}",
        f"training pairs: {training.get('pair_count', 0)}",
        f"validation groups: {validation.get('group_count', 0)}",
        "metrics:",
    ]
    for name in (
        TRANSITION_ACTION_SCORER_V3_VERSION,
        TRANSITION_ACTION_SCORER_V2_VERSION,
        TRANSITION_ACTION_SCORER_VERSION,
        EXISTING_RANK_ORDER_BASELINE,
        "stable-lexical-order",
        "deterministic-random-order",
    ):
        section = _mapping(metrics.get(name))
        if not section:
            continue
        lines.append(
            "  "
            f"{name}: "
            f"pass@1={section.get('pass_at_1_count')}/"
            f"{section.get('group_count')} "
            f"top-k={section.get('top_k_pass_count')}/"
            f"{section.get('group_count')} "
            f"mrr={_format_optional_float(section.get('mean_reciprocal_rank'))} "
            "avg_before_first_pass="
            f"{_format_optional_float(section.get('average_candidates_validated_before_first_pass'))}"
        )
    if readiness:
        lines.append(
            "product gate: "
            f"{readiness.get('gate_result')} "
            f"residuals={readiness.get('residual_count')}"
        )
        blocked_reason = readiness.get("guarded_opt_in_blocked_reason")
        if blocked_reason:
            lines.append(f"guarded opt-in blocked: {blocked_reason}")
    lines.extend(
        [
            f"local runtime ms: {_format_optional_float(runtime.get('local_runtime_ms'))}",
            f"hosted_llm_api_calls: {runtime.get('hosted_llm_api_calls', 0)}",
            f"hosted_llm_prompt_tokens: {runtime.get('hosted_llm_prompt_tokens', 0)}",
            "hosted_llm_completion_tokens: "
            f"{runtime.get('hosted_llm_completion_tokens', 0)}",
            f"hosted_api_tokens: {runtime.get('hosted_api_tokens', 0)}",
            f"hosted_repo_context_bytes: {runtime.get('hosted_repo_context_bytes', 0)}",
        ]
    )
    if report.get("report"):
        lines.append(f"report: {report['report']}")
    return "\n".join(lines)


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


def _candidate_v2_features(
    candidate: Mapping[str, object],
    *,
    group: Mapping[str, object],
) -> dict[str, float]:
    base = _candidate_score_features(candidate, group=group)
    action = _mapping(candidate.get("action"))
    params = _mapping(action.get("params"))
    target_context = _mapping(candidate.get("target_context"))
    action_kind = str(base.get("action_kind", ""))
    rank_index = max(float(base.get("rank_index", 0.0)), 1.0)
    v1_score = score_transition_action_candidate(candidate, group=group)["score"]

    features: dict[str, float] = {
        "bias": 1.0,
        "v1_score": float(v1_score),
        "source_embedding_available": float(base["source_embedding_available"]),
        "candidate_after_embedding_available": float(
            base["candidate_after_embedding_available"]
        ),
        "candidate_after_available": float(base["candidate_after_available"]),
        "action_has_params": float(base["action_has_params"]),
        "target_context_available": float(base["target_context_available"]),
        "model_score": float(base["model_score"]),
        "ranker_score": float(base["ranker_score"]),
        "failure_hint_score": float(base["failure_hint_score"]),
        "failure_hint_count": min(float(base["failure_hint_count"]), 5.0),
        "failure_hint_assertion_count": min(
            float(base["failure_hint_assertion_count"]),
            8.0,
        ),
        "group_candidate_count_scaled": float(base["group_candidate_count"]) / 10.0,
        "rank_index_inverse": 1.0 / rank_index,
        "rank_index_negative_scaled": -rank_index / 10.0,
        "rank_index_first": 1.0 if rank_index == 1.0 else 0.0,
        "rank_index_second": 1.0 if rank_index == 2.0 else 0.0,
    }
    _add_feature(features, f"action:{action_kind}", 1.0)

    for field in ("file_path", "symbol", "node_kind", "source_type"):
        value = action.get(field)
        if _simple_feature_value(value):
            _add_feature(features, f"action_{field}:{value}", 1.0)

    for key, value in sorted(params.items()):
        _add_feature(features, f"param_key:{action_kind}:{key}", 1.0)
        if _simple_feature_value(value):
            _add_feature(features, f"param_value:{action_kind}:{key}:{value}", 1.0)

    for key, value in sorted(target_context.items()):
        if _simple_feature_value(value):
            _add_feature(features, f"target:{key}:{value}", 1.0)

    grouping = _mapping(group.get("grouping"))
    for key in ("task_family", "source_type", "language", "phase"):
        value = grouping.get(key)
        if _simple_feature_value(value):
            _add_feature(features, f"group_{key}:{value}", 1.0)

    return features


def _candidate_v3_features(
    candidate: Mapping[str, object],
    *,
    group: Mapping[str, object],
    model: Mapping[str, object],
) -> dict[str, float]:
    allow_production_rank = model.get("allow_production_rank_feature") is True
    base = _candidate_v2_features(candidate, group=group)
    features = {
        name: value
        for name, value in base.items()
        if allow_production_rank
        or name
        not in {
            "rank_index_inverse",
            "rank_index_negative_scaled",
            "rank_index_first",
            "rank_index_second",
        }
    }
    action = _mapping(candidate.get("action"))
    params = _mapping(action.get("params"))
    validation = _mapping(candidate.get("validation"))
    failure_hints = [_mapping(item) for item in _list(validation.get("failure_hints"))]
    target_context = _mapping(candidate.get("target_context"))
    source_context = _mapping(candidate.get("source_context"))
    candidate_after = _mapping(candidate.get("candidate_after"))
    shadow = _mapping(group.get("shadow_outcome"))
    shadow_candidate = _shadow_candidate_for_rank(
        shadow,
        rank=_positive_int_or_zero(candidate.get("rank_index")),
    )
    shadow_validation = _mapping(shadow_candidate.get("validation"))
    action_kind = str(action.get("kind", ""))

    _add_feature(features, f"v3_action_kind:{action_kind}", 1.0)
    _add_feature(features, f"v3_param_signature:{action_kind}:{_json_signature(params)}", 1.0)
    for key in sorted(params):
        _add_feature(features, f"v3_param_key:{action_kind}:{key}", 1.0)

    symbol = action.get("symbol")
    function_names = {
        str(name)
        for hint in failure_hints
        for name in _list(hint.get("function_names"))
        if isinstance(name, str) and name
    }
    if isinstance(symbol, str) and symbol and symbol in function_names:
        _add_feature(features, "failure_hint_symbol_match", 1.0)
    assertion_count = sum(len(_list(hint.get("assertions"))) for hint in failure_hints)
    _add_feature(features, "failure_hint_assertion_count_v3", min(float(assertion_count), 8.0))
    for key in sorted(target_context):
        value = target_context.get(key)
        if _simple_feature_value(value):
            _add_feature(features, f"v3_target:{key}:{value}", 1.0)

    grouping = _mapping(group.get("grouping"))
    for key in ("task_family", "source_type", "split", "language", "phase"):
        value = grouping.get(key)
        if _simple_feature_value(value):
            _add_feature(features, f"v3_group_{key}:{value}", 1.0)

    source_embedding = _float_list_or_empty(source_context.get("embedding"))
    after_embedding = _float_list_or_empty(candidate_after.get("embedding"))
    if source_embedding and after_embedding and len(source_embedding) == len(after_embedding):
        deltas = [abs(after - source) for source, after in zip(source_embedding, after_embedding, strict=True)]
        _add_feature(features, "embedding_delta_l1_scaled", min(sum(deltas), 50.0) / 50.0)
        _add_feature(features, "embedding_delta_mean_abs", sum(deltas) / len(deltas))
        _add_feature(features, "embedding_cosine_similarity", _cosine_similarity(source_embedding, after_embedding))

    scorer_position = _positive_int_or_none(shadow_candidate.get("scorer_rank_position"))
    if scorer_position is not None:
        _add_feature(features, "shadow_scorer_rank_inverse", 1.0 / float(scorer_position))
        if scorer_position == 1:
            _add_feature(features, "shadow_scorer_rank_first", 1.0)
    if shadow_validation.get("known") is True:
        _add_feature(features, "shadow_validation_known", 1.0)
    if allow_production_rank:
        production_position = _positive_int_or_none(
            shadow_candidate.get("production_rank_position")
        )
        if production_position is not None:
            _add_feature(features, "ablation_production_rank_inverse", 1.0 / float(production_position))
            if production_position == 1:
                _add_feature(features, "ablation_production_rank_first", 1.0)
    return features


def _v2_training_pairs(
    groups: Sequence[Mapping[str, object]],
) -> list[tuple[dict[str, float], dict[str, float]]]:
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    for group in sorted(groups, key=lambda item: str(item.get("id", ""))):
        passing_ranks = _passing_rank_set(group)
        if not passing_ranks:
            continue
        candidates = _candidate_list(group)
        positive = [
            candidate
            for candidate in candidates
            if int(candidate["rank_index"]) in passing_ranks
        ]
        negative = [
            candidate
            for candidate in candidates
            if int(candidate["rank_index"]) not in passing_ranks
        ]
        for passed in positive:
            passed_features = _candidate_v2_features(passed, group=group)
            for failed in negative:
                pairs.append(
                    (
                        passed_features,
                        _candidate_v2_features(failed, group=group),
                    )
                )
    return pairs


def _v3_training_pairs(
    groups: Sequence[Mapping[str, object]],
    *,
    allow_production_rank_feature: bool,
) -> list[tuple[dict[str, float], dict[str, float]]]:
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    model = {"allow_production_rank_feature": allow_production_rank_feature}
    for group in sorted(groups, key=lambda item: str(item.get("id", ""))):
        passing_ranks = _passing_rank_set(group)
        if not passing_ranks:
            continue
        candidates = _candidate_list(group)
        positive = [
            candidate
            for candidate in candidates
            if int(candidate["rank_index"]) in passing_ranks
        ]
        negative = [
            candidate
            for candidate in candidates
            if int(candidate["rank_index"]) not in passing_ranks
        ]
        for passed in positive:
            passed_features = _candidate_v3_features(
                passed,
                group=group,
                model=model,
            )
            for failed in negative:
                pairs.append(
                    (
                        passed_features,
                        _candidate_v3_features(
                            failed,
                            group=group,
                            model=model,
                        ),
                    )
                )
    return pairs


def _fit_v2_pairwise_weights(
    pairs: Sequence[tuple[Mapping[str, float], Mapping[str, float]]],
    *,
    epochs: int,
    learning_rate: float,
    margin: float,
) -> tuple[dict[str, float], int]:
    weights: dict[str, float] = {}
    mistakes = 0
    for _epoch in range(epochs):
        for positive, negative in pairs:
            positive_score = _linear_score(positive, weights)
            negative_score = _linear_score(negative, weights)
            if positive_score <= negative_score + margin:
                mistakes += 1
                for name in sorted(set(positive) | set(negative)):
                    delta = positive.get(name, 0.0) - negative.get(name, 0.0)
                    if delta:
                        weights[name] = weights.get(name, 0.0) + learning_rate * delta
    return (
        {
            name: round(value, 12)
            for name, value in weights.items()
            if abs(value) > 1e-12
        },
        mistakes,
    )


def _fit_v2_model_for_groups(
    groups: Sequence[Mapping[str, object]],
    *,
    epochs: int,
    learning_rate: float,
    margin: float,
) -> dict[str, object] | None:
    pairs = _v2_training_pairs(groups)
    if not pairs:
        return None
    weights, _mistakes = _fit_v2_pairwise_weights(
        pairs,
        epochs=epochs,
        learning_rate=learning_rate,
        margin=margin,
    )
    return {
        "schema_version": "transition-action-future-scorer-v2-model-v1",
        "name": TRANSITION_ACTION_SCORER_V2_VERSION,
        "feature_version": TRANSITION_ACTION_SCORER_V2_FEATURE_VERSION,
        "bias": 0.0,
        "weights": dict(sorted(weights.items())),
    }


def _evaluate_v2_validation(
    groups: Sequence[Mapping[str, object]],
    *,
    model: Mapping[str, object],
    top_k: int,
) -> dict[str, object]:
    strategy_models: dict[str, Mapping[str, object] | None] = {
        TRANSITION_ACTION_SCORER_V2_VERSION: model,
        TRANSITION_ACTION_SCORER_VERSION: None,
        EXISTING_RANK_ORDER_BASELINE: None,
        "stable-lexical-order": None,
        "deterministic-random-order": None,
    }
    records: dict[str, list[dict[str, object]]] = {
        strategy: [] for strategy in strategy_models
    }
    for group in groups:
        baseline_record = _group_rank_record(
            group,
            rank_transition_action_candidates(
                group,
                strategy=EXISTING_RANK_ORDER_BASELINE,
            ),
            top_k=top_k,
        )
        for strategy, scorer_model in strategy_models.items():
            records[strategy].append(
                _group_rank_record(
                    group,
                    rank_transition_action_candidates(
                        group,
                        strategy=strategy,
                        scorer_model=scorer_model,
                    ),
                    top_k=top_k,
                    baseline_first_pass_rank=baseline_record["first_pass_rank"],
                )
            )
    return {
        strategy: _metrics_from_rank_records(strategy_records)
        for strategy, strategy_records in records.items()
    }


def _evaluate_v3_validation(
    groups: Sequence[Mapping[str, object]],
    *,
    v3_model: Mapping[str, object],
    v2_model: Mapping[str, object] | None,
    top_k: int,
) -> dict[str, object]:
    strategy_models: dict[str, Mapping[str, object] | None] = {
        TRANSITION_ACTION_SCORER_V3_VERSION: v3_model,
        TRANSITION_ACTION_SCORER_VERSION: None,
        EXISTING_RANK_ORDER_BASELINE: None,
        "stable-lexical-order": None,
        "deterministic-random-order": None,
    }
    if v2_model is not None:
        strategy_models = {
            TRANSITION_ACTION_SCORER_V3_VERSION: v3_model,
            TRANSITION_ACTION_SCORER_V2_VERSION: v2_model,
            TRANSITION_ACTION_SCORER_VERSION: None,
            EXISTING_RANK_ORDER_BASELINE: None,
            "stable-lexical-order": None,
            "deterministic-random-order": None,
        }
    records: dict[str, list[dict[str, object]]] = {
        strategy: _rank_records_for_strategy(
            groups,
            strategy=strategy,
            scorer_model=scorer_model,
            top_k=top_k,
        )
        for strategy, scorer_model in strategy_models.items()
    }
    return {
        strategy: _metrics_from_rank_records(strategy_records)
        for strategy, strategy_records in records.items()
    }


def _rank_records_for_strategy(
    groups: Sequence[Mapping[str, object]],
    *,
    strategy: str,
    scorer_model: Mapping[str, object] | None,
    top_k: int,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for group in groups:
        baseline_record = _group_rank_record(
            group,
            rank_transition_action_candidates(
                group,
                strategy=EXISTING_RANK_ORDER_BASELINE,
            ),
            top_k=top_k,
        )
        records.append(
            _group_rank_record(
                group,
                rank_transition_action_candidates(
                    group,
                    strategy=strategy,
                    scorer_model=scorer_model,
                ),
                top_k=top_k,
                baseline_first_pass_rank=baseline_record["first_pass_rank"],
            )
        )
    return records


def _split_groups_for_v2(
    groups: Sequence[Mapping[str, object]],
    *,
    split_by: str,
    validation_fraction: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    buckets: dict[str, list[dict[str, object]]] = {}
    for group in groups:
        key = _v2_split_key(group, split_by=split_by)
        buckets.setdefault(key, []).append(dict(group))

    train_keys: list[str] = []
    validation_keys: list[str] = []
    for key in sorted(buckets):
        fraction = _stable_fraction(f"{split_by}:{key}")
        if fraction < validation_fraction:
            validation_keys.append(key)
        else:
            train_keys.append(key)

    held_out = True
    if not validation_keys and train_keys:
        validation_keys.append(train_keys.pop(0))
    if not train_keys and validation_keys:
        if len(validation_keys) == 1:
            train_keys = list(validation_keys)
            held_out = False
        else:
            train_keys.append(validation_keys.pop())

    train_groups = [group for key in train_keys for group in buckets[key]]
    validation_groups = [group for key in validation_keys for group in buckets[key]]
    return train_groups, validation_groups, {
        "split_by": split_by,
        "validation_fraction": validation_fraction,
        "bucket_count": len(buckets),
        "training_bucket_count": len(set(train_keys)),
        "validation_bucket_count": len(set(validation_keys)),
        "training_group_count": len(train_groups),
        "validation_group_count": len(validation_groups),
        "held_out": held_out and bool(train_keys) and bool(validation_keys),
        "validation_keys": sorted(set(validation_keys)),
    }


def _split_groups_for_v3(
    groups: Sequence[Mapping[str, object]],
    *,
    split_by: str,
    validation_fraction: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    if split_by == "order":
        ordered = [dict(group) for group in sorted(groups, key=lambda item: str(item.get("id", "")))]
        validation_count = max(1, int(round(len(ordered) * validation_fraction))) if ordered else 0
        if validation_count >= len(ordered) and len(ordered) > 1:
            validation_count = len(ordered) - 1
        train_groups = ordered[: max(len(ordered) - validation_count, 0)]
        validation_groups = ordered[max(len(ordered) - validation_count, 0) :]
        held_out = bool(train_groups) and bool(validation_groups)
        return train_groups, validation_groups, {
            "split_by": split_by,
            "validation_fraction": validation_fraction,
            "bucket_count": len(ordered),
            "training_bucket_count": len(train_groups),
            "validation_bucket_count": len(validation_groups),
            "training_group_count": len(train_groups),
            "validation_group_count": len(validation_groups),
            "held_out": held_out,
            "validation_keys": [str(group.get("id", "")) for group in validation_groups],
        }

    buckets: dict[str, list[dict[str, object]]] = {}
    for group in groups:
        key = _v3_split_key(group, split_by=split_by)
        buckets.setdefault(key, []).append(dict(group))

    train_keys: list[str] = []
    validation_keys: list[str] = []
    for key in sorted(buckets):
        fraction = _stable_fraction(f"v3:{split_by}:{key}")
        if fraction < validation_fraction:
            validation_keys.append(key)
        else:
            train_keys.append(key)

    held_out = True
    if not validation_keys and train_keys:
        validation_keys.append(train_keys.pop(0))
    if not train_keys and validation_keys:
        if len(validation_keys) == 1:
            train_keys = list(validation_keys)
            held_out = False
        else:
            train_keys.append(validation_keys.pop())

    train_groups = [group for key in train_keys for group in buckets[key]]
    validation_groups = [group for key in validation_keys for group in buckets[key]]
    return train_groups, validation_groups, {
        "split_by": split_by,
        "validation_fraction": validation_fraction,
        "bucket_count": len(buckets),
        "training_bucket_count": len(set(train_keys)),
        "validation_bucket_count": len(set(validation_keys)),
        "training_group_count": len(train_groups),
        "validation_group_count": len(validation_groups),
        "held_out": held_out and bool(train_keys) and bool(validation_keys),
        "validation_keys": sorted(set(validation_keys)),
    }


def _v2_split_key(group: Mapping[str, object], *, split_by: str) -> str:
    if split_by == "source_file":
        source = _mapping(group.get("source"))
        value = source.get("path")
        if isinstance(value, str) and value:
            return value
    grouping = _mapping(group.get("grouping"))
    value = grouping.get("task_family")
    if isinstance(value, str) and value:
        return value
    return str(group.get("id", "unknown"))


def _v3_split_key(group: Mapping[str, object], *, split_by: str) -> str:
    if split_by == "source_file":
        source = _mapping(group.get("source"))
        value = source.get("path")
        if isinstance(value, str) and value:
            return value
    if split_by == "repo":
        shadow = _mapping(group.get("shadow_outcome"))
        repo = _mapping(shadow.get("repo"))
        for value in (repo.get("path"), repo.get("name")):
            if isinstance(value, str) and value:
                return value
    grouping = _mapping(group.get("grouping"))
    value = grouping.get("task_family")
    if isinstance(value, str) and value:
        return value
    return str(group.get("id", "unknown"))


def _shadow_outcomes_by_group_key(
    rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str, str], dict[str, object]]:
    result: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        if row.get("join_status") != "joined":
            continue
        validation = _mapping(row.get("validation_outcome"))
        if validation.get("known") is not True:
            continue
        key = _shadow_row_key(row)
        if all(key):
            result.setdefault(key, dict(row))
    return result


def _shadow_row_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    key = _mapping(row.get("key"))
    return (
        _string_or_empty(key.get("task")),
        _string_or_empty(key.get("phase")),
        _string_or_empty(key.get("repair_plan_id")),
    )


def _group_shadow_key(group: Mapping[str, object]) -> tuple[str, str, str]:
    grouping = _mapping(group.get("grouping"))
    return (
        _string_or_empty(grouping.get("task")),
        _string_or_empty(grouping.get("phase")),
        _string_or_empty(grouping.get("repair_plan_identity")),
    )


def _group_with_shadow_outcome(
    group: Mapping[str, object],
    shadow_outcome: Mapping[str, object],
) -> dict[str, object]:
    return {**dict(group), "shadow_outcome": dict(shadow_outcome)}


def _shadow_candidate_for_rank(
    shadow_outcome: Mapping[str, object],
    *,
    rank: int,
) -> Mapping[str, object]:
    ranking = shadow_outcome.get("candidate_ranking")
    if not isinstance(ranking, list):
        return {}
    for item in ranking:
        candidate = _mapping(item)
        if _positive_int_or_none(candidate.get("rank_index")) == rank:
            return candidate
    return {}


def _shadow_outcome_summary_for_v3(
    rows: Sequence[Mapping[str, object]],
    *,
    matched_group_count: int,
) -> dict[str, object]:
    joined_known = 0
    joined_rows = 0
    labels = {"improved": 0, "regressed": 0, "same": 0, "unknown": 0}
    for row in rows:
        if row.get("join_status") == "joined":
            joined_rows += 1
        validation = _mapping(row.get("validation_outcome"))
        if row.get("join_status") == "joined" and validation.get("known") is True:
            joined_known += 1
        label = _mapping(row.get("labels")).get("outcome_label")
        if label in labels:
            labels[str(label)] += 1
    return {
        "schema_version": "transition-shadow-outcome-v1",
        "row_count": len(rows),
        "joined_rows": joined_rows,
        "joined_known_validation_rows": joined_known,
        "matched_action_choice_groups": matched_group_count,
        "labels": labels,
    }


def _shadow_usage_totals(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    fields = (
        "hosted_llm_api_calls",
        "hosted_llm_prompt_tokens",
        "hosted_llm_completion_tokens",
        "hosted_api_tokens",
        "hosted_repo_context_bytes",
    )
    totals = {field: 0 for field in fields}
    for row in rows:
        usage = _mapping(row.get("usage"))
        runtime = _mapping(row.get("runtime"))
        for field in fields:
            totals[field] += _int_or_zero(usage.get(field, runtime.get(field)))
    return totals


def _linear_score(
    features: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    return sum(weights.get(name, 0.0) * value for name, value in features.items())


def _add_feature(features: dict[str, float], name: str, value: float) -> None:
    features[name] = features.get(name, 0.0) + value


def _simple_feature_value(value: object) -> bool:
    return (
        isinstance(value, (str, int, float, bool))
        and not (isinstance(value, str) and not value)
    ) or value is None


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


def _stable_fraction(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(0xFFFFFFFFFFFFFFFF)


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


def _float_list_or_empty(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return []
        result.append(float(item))
    return result


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return 0.0
    return round(dot / (left_norm * right_norm), 12)


def _bool_float(value: object) -> float:
    return 1.0 if value is True else 0.0


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _float_mapping(value: Mapping[str, object]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, item in value.items():
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            result[str(key)] = float(item)
    return result


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


def _float_or_default(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _positive_int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def _positive_int_or_zero(value: object) -> int:
    parsed = _positive_int_or_none(value)
    return parsed if parsed is not None else 0


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _string_or_empty(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _format_optional_float(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "none"
    return f"{float(value):.6f}"


def _negative(value: float | None) -> bool:
    return value is not None and value < -1e-12


def _positive(value: float | None) -> bool:
    return value is not None and value > 1e-12


def _non_negative(value: float | None) -> bool:
    return value is not None and value >= -1e-12


def _non_positive(value: float | None) -> bool:
    return value is not None and value <= 1e-12
