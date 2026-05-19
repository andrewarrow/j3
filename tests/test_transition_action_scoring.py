from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.transition_action_choice import build_transition_action_choice_groups
from j3.transition_action_scoring import (
    GATE_NOT_READY_UNDERPERFORMS,
    GATE_READY_FOR_GUARDED_OPT_IN,
    GATE_READY_FOR_SHADOW_MODE,
    TRANSITION_ACTION_SCORER_VERSION,
    TRANSITION_ACTION_SCORER_V2_CALIBRATION_VERSION,
    TRANSITION_ACTION_SCORER_V2_VERSION,
    TRANSITION_ACTION_SCORER_V3_VERSION,
    TRANSITION_ACTION_SCORING_EVAL_VERSION,
    TRANSITION_PRODUCT_READINESS_VERSION,
    calibrate_transition_action_scorer_v2,
    evaluate_transition_product_readiness,
    evaluate_transition_action_choices,
    rank_transition_action_candidates,
    score_transition_action_candidate,
    score_transition_action_candidate_v3,
)


FIXTURES = Path(__file__).parent / "fixtures" / "transition_bench"


def test_future_scorer_evaluates_fixture_against_rank_order_baseline() -> None:
    groups = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )

    report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )

    assert report["schema_version"] == TRANSITION_ACTION_SCORING_EVAL_VERSION
    assert report["group_count"] == 1
    assert report["solved_group_count"] == 1
    assert report["candidate_count"] == 2
    assert report["runtime"]["hosted_llm_api_calls"] == 0
    assert report["runtime"]["hosted_llm_prompt_tokens"] == 0
    assert report["runtime"]["hosted_llm_completion_tokens"] == 0
    assert report["runtime"]["hosted_repo_context_bytes"] == 0

    scorer_metrics = report["metrics"][TRANSITION_ACTION_SCORER_VERSION]
    rank_order_metrics = report["metrics"]["existing-rank-order"]
    assert scorer_metrics["pass_at_1_count"] == 1
    assert scorer_metrics["pass_at_1_rate"] == 1.0
    assert scorer_metrics["pass_at_1_solved_rate"] == 1.0
    assert scorer_metrics["mean_reciprocal_rank"] == 1.0
    assert scorer_metrics["mean_reciprocal_rank_solved"] == 1.0
    assert scorer_metrics["average_first_passing_rank"] == 1.0
    assert scorer_metrics["average_candidates_validated_before_first_pass"] == 0.0
    assert scorer_metrics["average_candidates_saved_vs_existing_rank_order"] == 1.0
    assert scorer_metrics["residual_count"] == 0
    assert rank_order_metrics["pass_at_1_count"] == 0
    assert rank_order_metrics["mean_reciprocal_rank"] == 0.5
    assert report["residual_examples"] == []


def test_future_scorer_ranking_uses_local_non_label_features() -> None:
    group = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )[0]

    ranked = rank_transition_action_candidates(group)
    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]

    failed_score = score_transition_action_candidate(group["candidates"][0], group=group)
    passed_score = score_transition_action_candidate(group["candidates"][1], group=group)
    assert failed_score["features"]["ranker_score"] == pytest.approx(0.1)
    assert passed_score["features"]["ranker_score"] == pytest.approx(0.9)
    assert passed_score["features"]["candidate_after_embedding_available"] == 1.0
    assert passed_score["score"] > failed_score["score"]


def test_future_scorer_penalizes_unvalidated_add_keyword_decoy_without_hint() -> None:
    group = {"candidate_count": 2}
    decoy = _scoring_candidate(
        action="add_keyword_arg",
        params={"keyword": "timeout", "value": True, "callee": "fetch"},
        validated=False,
        model_score=1.0,
        ranker_score=1.0,
        failure_hint_score=1.0,
        failure_hints=[],
    )
    passing = _scoring_candidate(
        action="change_literal",
        params={"to": 30},
        validated=True,
        passed=True,
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
        failure_hints=[],
    )

    decoy_score = score_transition_action_candidate(decoy, group=group)
    passing_score = score_transition_action_candidate(passing, group=group)

    assert decoy_score["features"]["candidate_unvalidated"] == 1.0
    assert decoy_score["features"]["failure_hint_names_keyword_path"] == 0.0
    assert decoy_score["features"]["unvalidated_add_keyword_arg_without_hint"] == 1.0
    assert passing_score["score"] > decoy_score["score"]


def test_future_scorer_keeps_add_keyword_when_failure_hint_names_keyword() -> None:
    group = {"candidate_count": 2}
    candidate = _scoring_candidate(
        action="add_keyword_arg",
        params={"keyword": "timeout", "value": True, "callee": "fetch"},
        validated=False,
        model_score=1.0,
        ranker_score=1.0,
        failure_hint_score=1.0,
        failure_hints=[{"type_error_names": ["timeout"]}],
    )

    score = score_transition_action_candidate(candidate, group=group)

    assert score["features"]["candidate_unvalidated"] == 1.0
    assert score["features"]["failure_hint_names_keyword_path"] == 1.0
    assert score["features"]["unvalidated_add_keyword_arg_without_hint"] == 0.0


def test_future_scorer_prefers_dict_value_delta_over_same_mapping_key_decoy() -> None:
    groups = build_transition_action_choice_groups(
        [
            _mapping_candidate_row(
                rank_index=1,
                action="change_dict_key",
                params={"from": "secure", "to": "__Secure-"},
                passed=False,
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
            ),
            _mapping_candidate_row(
                rank_index=2,
                action="change_dict_value",
                params={"key": "secure", "from": True, "to": False},
                passed=True,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    key_score = score_transition_action_candidate(groups[0]["candidates"][0], group=groups[0])
    value_score = score_transition_action_candidate(groups[0]["candidates"][1], group=groups[0])

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]
    assert value_score["features"]["mapping_target_value_mutation"] == 1.0
    assert value_score["features"]["mapping_value_key_matches_asserted_key"] == 1.0
    assert value_score["features"]["mapping_value_matches_assertion_delta"] == 1.0
    assert value_score["features"]["mapping_same_mapping_competitor_count"] == 1.0
    assert key_score["features"]["mapping_target_key_mutation"] == 1.0
    assert (
        key_score["features"]["mapping_key_renames_asserted_key_with_value_assertion"]
        == 1.0
    )
    assert value_score["score"] > key_score["score"]


def test_future_scorer_prefers_add_dict_key_for_missing_same_mapping_key() -> None:
    groups = build_transition_action_choice_groups(
        [
            _mapping_candidate_row(
                rank_index=1,
                action="change_dict_value",
                params={"key": "retries", "from": 1, "to": 0},
                passed=False,
                failure_hints=[{"missing_keys": ["timeout"]}],
            ),
            _mapping_candidate_row(
                rank_index=2,
                action="add_dict_key",
                params={"key": "timeout", "value": 30},
                passed=True,
                failure_hints=[{"missing_keys": ["timeout"]}],
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    add_score = score_transition_action_candidate(groups[0]["candidates"][1], group=groups[0])

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]
    assert add_score["features"]["mapping_target_add_key"] == 1.0
    assert add_score["features"]["mapping_add_key_matches_missing_key"] == 1.0
    assert add_score["features"]["mapping_same_mapping_competes_with_key_and_value"] == 1.0


def test_future_scorer_prefers_existing_key_rename_over_placeholder_add() -> None:
    failure_hints = [
        {
            "exception_type": "KeyError",
            "missing_keys": ["Project-URL"],
            "asserted_mapping_keys": ["Project-URL"],
            "function_names": ["build_project_urls"],
        }
    ]
    groups = build_transition_action_choice_groups(
        [
            _mapping_candidate_row(
                rank_index=1,
                action="change_dict_key",
                params={"from": "Project_URL", "to": "Project-URL"},
                passed=True,
                failure_hint_score=1.0,
                failure_hints=failure_hints,
                target_context={
                    "qualified_symbol": "pkgmeta.metadata.project_url_headers",
                    "role": "helper",
                    "dict_key_from": "Project_URL",
                    "dict_key_from_in_same_mapping": True,
                    "dict_key_to": "Project-URL",
                    "dict_literal_key_count": 2,
                    "dict_literal_keys": ["Homepage", "Project_URL"],
                },
            ),
            _mapping_candidate_row(
                rank_index=2,
                action="add_dict_key",
                params={"key": "Project-URL", "value": None},
                passed=False,
                model_score=0.9137659547000444,
                failure_hint_score=0.9,
                failure_hints=failure_hints,
                target_context={
                    "qualified_symbol": "pkgmeta.metadata.project_url_headers",
                    "role": "helper",
                },
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    rename_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    add_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked[:2]] == [1, 2]
    assert (
        rename_score["features"]["mapping_existing_key_rename_to_missing_key"]
        == 1.0
    )
    assert (
        add_score["features"][
            "mapping_add_key_placeholder_competes_with_existing_key_rename"
        ]
        == 1.0
    )
    assert rename_score["features"]["mapping_same_mapping_competitor_count"] == 1.0
    assert add_score["features"]["mapping_same_mapping_competitor_count"] == 1.0
    assert rename_score["score"] > add_score["score"]


def test_future_scorer_uses_assertion_diff_lines_for_mapping_value_delta() -> None:
    groups = build_transition_action_choice_groups(
        _apache_license_mapping_candidate_rows(),
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    passing_score = score_transition_action_candidate(
        groups[0]["candidates"][2],
        group=groups[0],
    )
    mit_decoy_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked[:3]] == [5, 1, 2]
    assert (
        passing_score["features"]["mapping_value_matches_assertion_delta"]
        == 1.0
    )
    assert passing_score["features"]["mapping_value_key_matches_asserted_key"] == 1.0
    assert (
        mit_decoy_score["features"]["mapping_value_matches_assertion_delta"]
        == 0.0
    )
    assert passing_score["score"] > mit_decoy_score["score"]


def test_v3_scorer_can_use_mapping_value_diff_line_feature() -> None:
    groups = build_transition_action_choice_groups(
        _apache_license_mapping_candidate_rows(),
        embedding_dim=8,
    )
    model = {
        "weights": {
            "mapping_value_matches_assertion_delta": 4.0,
            "mapping_value_key_matches_asserted_key": 1.0,
        },
        "allow_production_rank_feature": False,
    }

    ranked = rank_transition_action_candidates(
        groups[0],
        strategy=TRANSITION_ACTION_SCORER_V3_VERSION,
        scorer_model=model,
    )
    passing_score = score_transition_action_candidate_v3(
        groups[0]["candidates"][2],
        group=groups[0],
        model=model,
    )

    assert ranked[0]["rank_index"] == 5
    assert {candidate["rank_index"] for candidate in ranked[1:3]} == {1, 2}
    assert (
        passing_score["features"]["mapping_value_matches_assertion_delta"]
        == 1.0
    )


def test_v3_scorer_replays_model_009_structural_residuals() -> None:
    model = {
        "weights": {
            "v3_action_kind:add_import": 0.5,
            "v3_action_kind:change_literal": -0.2,
            "v3_action_kind:change_module_constant": -0.2,
            "v3_action_kind:replace_expr": -0.2,
            "v3_action_kind:swap_call_arg": 0.5,
            "v3_action_kind:wrap_try_except": -0.5,
        },
        "allow_production_rank_feature": False,
    }
    cases = [
        {
            "task": "wrap_try_except",
            "passing_ranks": {1},
            "positive_rank": 1,
            "positive_feature": "v3_wrap_exception_matches_failure",
            "negative_rank": 2,
            "negative_feature": "v3_import_without_missing_name_hint",
            "rows": _model_009_wrap_try_except_rows(),
        },
        {
            "task": "express_shipping_boundary_preferred_helper",
            "passing_ranks": {2, 3},
            "positive_rank": 2,
            "positive_feature": "v3_boundary_literal_numeric_candidate",
            "negative_rank": 1,
            "negative_feature": "v3_swap_call_breaks_name_alignment",
            "rows": _model_009_express_boundary_rows(),
        },
        {
            "task": "free_shipping_threshold_module_constant",
            "passing_ranks": {1},
            "positive_rank": 1,
            "positive_feature": "v3_module_constant_named_assertion_delta",
            "negative_rank": 2,
            "negative_feature": "v3_literal_change_moves_expected_value_away",
            "rows": _model_009_module_constant_rows(),
        },
        {
            "task": "quote_total_helper_discount",
            "passing_ranks": {2},
            "positive_rank": 2,
            "positive_feature": "v3_helper_expression_reaches_failure_symbol",
            "negative_rank": 1,
            "negative_feature": "v3_swap_call_breaks_name_alignment",
            "rows": _model_009_quote_total_rows(),
        },
    ]

    for case in cases:
        group = build_transition_action_choice_groups(
            case["rows"],
            embedding_dim=8,
        )[0]

        ranked = rank_transition_action_candidates(
            group,
            strategy=TRANSITION_ACTION_SCORER_V3_VERSION,
            scorer_model=model,
        )
        positive = next(
            candidate
            for candidate in group["candidates"]
            if candidate["rank_index"] == case["positive_rank"]
        )
        negative = next(
            candidate
            for candidate in group["candidates"]
            if candidate["rank_index"] == case["negative_rank"]
        )
        positive_score = score_transition_action_candidate_v3(
            positive,
            group=group,
            model=model,
        )
        negative_score = score_transition_action_candidate_v3(
            negative,
            group=group,
            model=model,
        )

        assert int(ranked[0]["rank_index"]) in case["passing_ranks"], case["task"]
        assert positive_score["features"][case["positive_feature"]] == 1.0
        assert negative_score["features"][case["negative_feature"]] == 1.0
        assert positive_score["features"]["v3_local_evidence_prior"] > 0.0
        assert negative_score["features"]["v3_local_evidence_prior"] < 0.0


def test_future_scorer_prefers_returned_mapping_subscript_key_over_add_key_decoy() -> None:
    groups = build_transition_action_choice_groups(
        [
            _mapping_candidate_row(
                rank_index=1,
                action="add_dict_key",
                params={"key": "customer_name", "value": None},
                passed=False,
                failure_hints=[{"asserted_mapping_keys": ["customer_name"]}],
                target_context={
                    "mapping_name": "row",
                    "dict_literal_keys": ["id", "name"],
                },
            ),
            _mapping_candidate_row(
                rank_index=2,
                action="change_subscript_key",
                params={"from": "name", "to": "customer_name"},
                passed=True,
                failure_hints=[{"asserted_mapping_keys": ["customer_name"]}],
                target_context={
                    "mapping_name": "row",
                    "subscript_write_to_returned_mapping": True,
                    "subscript_to_matches_returned_mapping_key": True,
                },
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    subscript_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]
    assert subscript_score["features"]["mapping_target_subscript_key"] == 1.0
    assert subscript_score["features"]["mapping_subscript_to_matches_asserted_key"] == 1.0
    assert (
        subscript_score["features"][
            "mapping_subscript_to_matches_returned_mapping_key"
        ]
        == 1.0
    )
    assert subscript_score["features"]["mapping_same_mapping_competitor_count"] == 1.0


def test_future_scorer_exposes_distinct_mapping_target_roles_for_same_mapping() -> None:
    group = {
        "candidate_count": 4,
        "candidates": [
            _scoring_candidate(
                action="change_dict_key",
                params={"from": "secure", "to": "__Secure-"},
                validated=True,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                failure_hints=[],
                target_context={"mapping_name": "attrs"},
            ),
            _scoring_candidate(
                action="change_dict_value",
                params={"key": "secure", "from": True, "to": False},
                validated=True,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                failure_hints=[],
                target_context={"mapping_name": "attrs"},
            ),
            _scoring_candidate(
                action="add_dict_key",
                params={"key": "expires", "value": None},
                validated=True,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                failure_hints=[],
                target_context={"mapping_name": "attrs"},
            ),
            _scoring_candidate(
                action="change_subscript_key",
                params={"from": "name", "to": "customer_name"},
                validated=True,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                failure_hints=[],
                target_context={"mapping_name": "attrs"},
            ),
        ],
    }

    role_features = [
        score_transition_action_candidate(candidate, group=group)["features"]
        for candidate in group["candidates"]
    ]

    assert [features["mapping_target_key_mutation"] for features in role_features] == [
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    assert [features["mapping_target_value_mutation"] for features in role_features] == [
        0.0,
        1.0,
        0.0,
        0.0,
    ]
    assert [features["mapping_target_add_key"] for features in role_features] == [
        0.0,
        0.0,
        1.0,
        0.0,
    ]
    assert [features["mapping_target_subscript_key"] for features in role_features] == [
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    assert all(
        features["mapping_same_mapping_competes_with_key_and_value"] == 1.0
        for features in role_features
    )


def test_future_scorer_prefers_boundary_operator_with_hint_alignment() -> None:
    groups = build_transition_action_choice_groups(
        [
            _boundary_literal_candidate_row(
                rank_index=1,
                action="change_literal",
                params={"from": 10000, "to": 9999},
                passed=False,
                task="express_shipping_boundary_preferred_helper",
                task_family="operator_boundary",
                file_path="shop/shipping.py",
                symbol="is_express_eligible",
                node_kind="Constant",
                model_score=0.6,
                ranker_score=0.6,
                failure_hint_score=0.6,
            ),
            _boundary_literal_candidate_row(
                rank_index=2,
                action="change_operator",
                params={"from": ">", "to": ">="},
                passed=True,
                task="express_shipping_boundary_preferred_helper",
                task_family="operator_boundary",
                file_path="shop/shipping.py",
                symbol="is_express_eligible",
                node_kind="Compare",
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    operator_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]
    assert operator_score["features"]["failure_hint_file_match"] == 1.0
    assert operator_score["features"]["failure_hint_symbol_match"] == 1.0
    assert operator_score["features"]["action_family_boundary_operator_match"] == 1.0
    assert operator_score["features"]["same_file_symbol_competitor_count"] == 1.0


def test_future_scorer_prefers_module_constant_over_literal_neighbor() -> None:
    groups = build_transition_action_choice_groups(
        [
            _boundary_literal_candidate_row(
                rank_index=1,
                action="change_literal",
                params={"from": 4999, "to": 5000},
                passed=False,
                task="free_shipping_threshold_module_constant",
                task_family="module_constant",
                file_path="shop/shipping.py",
                symbol="shipping_total",
                node_kind="Constant",
                model_score=0.7,
                ranker_score=0.7,
                failure_hint_score=0.7,
            ),
            _boundary_literal_candidate_row(
                rank_index=2,
                action="change_module_constant",
                params={
                    "name": "FREE_SHIPPING_MINIMUM_CENTS",
                    "from": 4999,
                    "to": 5000,
                },
                passed=True,
                task="free_shipping_threshold_module_constant",
                task_family="module_constant",
                file_path="shop/shipping.py",
                symbol="FREE_SHIPPING_MINIMUM_CENTS",
                node_kind="Constant",
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    constant_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]
    assert constant_score["features"]["action_family_module_constant_match"] == 1.0
    assert constant_score["features"]["module_constant_name_matches_symbol"] == 1.0
    assert constant_score["features"]["module_constant_name_matches_name_hint"] == 1.0
    assert constant_score["features"]["literal_or_constant_matches_assertion_delta"] == 1.0


def test_future_scorer_prefers_literal_delta_in_hinted_file_and_symbol() -> None:
    groups = build_transition_action_choice_groups(
        [
            _boundary_literal_candidate_row(
                rank_index=1,
                action="change_return_value",
                params={"from": None, "to": "{name} {filename!r} is a directory."},
                passed=False,
                task="dynamic_field_error_message",
                task_family="string_literal_error_message",
                file_path="errors/fallback.py",
                symbol="fallback_directory_message",
                node_kind="Return",
                model_score=0.7,
                ranker_score=0.7,
                failure_hint_score=0.7,
            ),
            _boundary_literal_candidate_row(
                rank_index=2,
                action="change_literal",
                params={
                    "from": "{name} '{filename}' is a directory.",
                    "to": "{name} {filename!r} is a directory.",
                },
                passed=True,
                task="dynamic_field_error_message",
                task_family="string_literal_error_message",
                file_path="errors/messages.py",
                symbol="invalid_directory_message",
                node_kind="Constant",
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    decoy_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    literal_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1]
    assert decoy_score["features"]["failure_hint_file_mismatch"] == 1.0
    assert decoy_score["features"]["failure_hint_symbol_mismatch"] == 1.0
    assert literal_score["features"]["failure_hint_file_and_symbol_match"] == 1.0
    assert literal_score["features"]["action_family_literal_match"] == 1.0
    assert literal_score["features"]["literal_or_constant_matches_assertion_delta"] == 1.0


def test_future_scorer_replays_tail_index_literal_decoy_residuals() -> None:
    cases = [
        ("last_item", "last_item", "items[-1]", 1, 3),
        ("final_score_tail", "final_score", "scores[-1]", 4, 15),
        ("last_order_id_tail", "last_order_id", "order_ids[-1]", 101, 303),
        ("newest_event_tail", "newest_event", "events[-1]", "created", "sent"),
    ]

    for task, symbol, replacement, actual, expected in cases:
        groups = build_transition_action_choice_groups(
            [
                _tail_index_candidate_row(
                    task=task,
                    symbol=symbol,
                    rank_index=1,
                    action="replace_expr",
                    params={"replacement": replacement},
                    node_kind="Subscript",
                    passed=True,
                    model_score=0.3018494539923293,
                    failure_hint_score=45.0,
                    actual=actual,
                    expected=expected,
                ),
                _tail_index_candidate_row(
                    task=task,
                    symbol=symbol,
                    rank_index=2,
                    action="change_literal",
                    params={"from": 0, "to": -2},
                    node_kind="Constant",
                    passed=False,
                    model_score=0.10970811259610694,
                    failure_hint_score=40.0,
                    actual=actual,
                    expected=expected,
                ),
            ],
            embedding_dim=8,
        )

        ranked = rank_transition_action_candidates(groups[0])
        replace_score = score_transition_action_candidate(
            groups[0]["candidates"][0],
            group=groups[0],
        )
        literal_score = score_transition_action_candidate(
            groups[0]["candidates"][1],
            group=groups[0],
        )

        assert [candidate["rank_index"] for candidate in ranked] == [1, 2], task
        assert (
            replace_score["features"]["tail_index_replace_expr_matches_tail_intent"]
            == 1.0
        )
        assert (
            literal_score["features"][
                "tail_index_literal_decoy_competes_with_tail_expr"
            ]
            == 1.0
        )
        assert replace_score["score"] > literal_score["score"]


def test_future_scorer_does_not_reward_tail_access_without_tail_intent() -> None:
    groups = build_transition_action_choice_groups(
        [
            _tail_index_candidate_row(
                task="first_item",
                symbol="first_item",
                rank_index=1,
                action="replace_expr",
                params={"replacement": "items[-1]"},
                node_kind="Subscript",
                passed=False,
                model_score=0.3018494539923293,
                failure_hint_score=45.0,
                actual=3,
                expected=1,
                tail_intent_hint=False,
            ),
            _tail_index_candidate_row(
                task="first_item",
                symbol="first_item",
                rank_index=2,
                action="change_literal",
                params={"from": 0, "to": -2},
                node_kind="Constant",
                passed=False,
                model_score=0.10970811259610694,
                failure_hint_score=40.0,
                actual=3,
                expected=1,
                tail_intent_hint=False,
            ),
        ],
        embedding_dim=8,
    )

    replace_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    literal_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert replace_score["features"]["tail_index_intent_available"] == 0.0
    assert (
        replace_score["features"]["tail_index_replace_expr_matches_tail_intent"]
        == 0.0
    )
    assert (
        literal_score["features"]["tail_index_literal_decoy_competes_with_tail_expr"]
        == 0.0
    )


def test_future_scorer_prefers_guard_insert_over_unrelated_operator_decoy() -> None:
    groups = build_transition_action_choice_groups(
        [
            _guard_candidate_row(
                rank_index=1,
                action="insert_guard",
                symbol="average",
                params={"condition": "not values", "return": 0},
                node_kind="Return",
                passed=True,
                model_score=0.8811021258317153,
                failure_hint_score=92.0,
            ),
            _guard_candidate_row(
                rank_index=2,
                action="change_operator",
                symbol="apply_discount",
                params={"from": ">", "to": "<"},
                node_kind="Compare",
                passed=False,
                model_score=0.454596635082278,
                failure_hint_score=20.0,
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    guard_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    operator_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [1, 2]
    assert guard_score["features"]["guard_insert_condition_checks_empty_value"] == 1.0
    assert guard_score["features"]["guard_failure_context_mentions_empty_input"] == 1.0
    assert guard_score["features"]["guard_insert_file_and_symbol_match"] == 1.0
    assert guard_score["features"]["guard_insert_matches_empty_input_failure"] == 1.0
    assert (
        operator_score["features"][
            "guard_operator_decoy_competes_with_guarded_symbol"
        ]
        == 1.0
    )
    assert guard_score["score"] > operator_score["score"]


def test_future_scorer_does_not_reward_guard_without_empty_target_evidence() -> None:
    groups = build_transition_action_choice_groups(
        [
            _guard_candidate_row(
                rank_index=1,
                action="insert_guard",
                symbol="average",
                params={"condition": "values is not None", "return": 0},
                node_kind="Return",
                passed=False,
                model_score=0.9,
                failure_hint_score=90.0,
                hinted_symbol="apply_discount",
                nodeid="tests/test_bugs.py::test_apply_discount_threshold",
                exception_type="AssertionError",
            ),
            _guard_candidate_row(
                rank_index=2,
                action="change_operator",
                symbol="apply_discount",
                params={"from": ">", "to": ">="},
                node_kind="Compare",
                passed=True,
                model_score=0.1,
                failure_hint_score=10.0,
                hinted_symbol="apply_discount",
                nodeid="tests/test_bugs.py::test_apply_discount_threshold",
                exception_type="AssertionError",
            ),
        ],
        embedding_dim=8,
    )

    guard_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    operator_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert guard_score["features"]["guard_insert_condition_checks_empty_value"] == 0.0
    assert guard_score["features"]["guard_failure_context_mentions_empty_input"] == 0.0
    assert guard_score["features"]["guard_insert_file_and_symbol_match"] == 0.0
    assert guard_score["features"]["guard_insert_matches_empty_input_failure"] == 0.0
    assert (
        operator_score["features"][
            "guard_operator_decoy_competes_with_guarded_symbol"
        ]
        == 0.0
    )


def test_future_scorer_prefers_nested_package_missing_import() -> None:
    groups = build_transition_action_choice_groups(
        [
            _missing_import_candidate_row(
                rank_index=1,
                action="add_import",
                params={
                    "import": "from shop.money import format_receipt_total",
                    "module": "shop.money",
                    "name": "format_receipt_total",
                },
                file_path="shop/reports/summary.py",
                symbol="format_receipt_total",
                node_kind="Import",
                passed=False,
                model_score=0.8868007564616814,
                failure_hint_score=120.0,
            ),
            _missing_import_candidate_row(
                rank_index=2,
                action="add_import",
                params={
                    "import": (
                        "from shop.reports.money import format_receipt_total"
                    ),
                    "module": "shop.reports.money",
                    "name": "format_receipt_total",
                },
                file_path="shop/reports/summary.py",
                symbol="format_receipt_total",
                node_kind="Import",
                passed=True,
                model_score=0.8868007564616814,
                failure_hint_score=120.0,
            ),
            _missing_import_candidate_row(
                rank_index=3,
                action="change_literal",
                params={"from": 100, "to": 98},
                file_path="shop/reports/money.py",
                symbol="format_receipt_total",
                node_kind="Constant",
                passed=False,
                model_score=0.0,
                failure_hint_score=40.0,
                target_context={
                    "callee_count": 0,
                    "caller_count": 0,
                    "qualified_symbol": "shop.reports.money.format_receipt_total",
                    "role": "helper",
                },
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    top_level_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    nested_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )
    literal_score = score_transition_action_candidate(
        groups[0]["candidates"][2],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1, 3]
    assert nested_score["features"]["missing_import_name_matches_hint"] == 1.0
    assert (
        nested_score["features"][
            "missing_import_nested_module_matches_target_package"
        ]
        == 1.0
    )
    assert (
        nested_score["features"][
            "missing_import_nested_module_matches_local_symbol"
        ]
        == 1.0
    )
    assert (
        top_level_score["features"][
            "missing_import_top_level_decoy_competes_with_nested_module"
        ]
        == 1.0
    )
    assert (
        literal_score["features"][
            "missing_import_literal_decoy_competes_with_nested_import"
        ]
        == 1.0
    )
    assert nested_score["score"] > top_level_score["score"]
    assert nested_score["score"] > literal_score["score"]


def test_future_scorer_does_not_reward_deep_import_without_local_symbol() -> None:
    groups = build_transition_action_choice_groups(
        [
            _missing_import_candidate_row(
                rank_index=1,
                action="add_import",
                params={
                    "import": "from shop.reports.money import format_receipt_total",
                    "module": "shop.reports.money",
                    "name": "format_receipt_total",
                },
                file_path="shop/api.py",
                symbol="format_receipt_total",
                node_kind="Import",
                passed=False,
                model_score=0.8868007564616814,
                failure_hint_score=120.0,
            ),
            _missing_import_candidate_row(
                rank_index=2,
                action="change_literal",
                params={"from": 100, "to": 98},
                file_path="shop/money.py",
                symbol="format_receipt_total",
                node_kind="Constant",
                passed=True,
                model_score=0.0,
                failure_hint_score=40.0,
                first_passing_index=2,
            ),
        ],
        embedding_dim=8,
    )

    deep_import_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    literal_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )

    assert (
        deep_import_score["features"][
            "missing_import_nested_module_matches_target_package"
        ]
        == 0.0
    )
    assert (
        deep_import_score["features"][
            "missing_import_nested_module_matches_local_symbol"
        ]
        == 0.0
    )
    assert (
        literal_score["features"][
            "missing_import_literal_decoy_competes_with_nested_import"
        ]
        == 0.0
    )


def test_future_scorer_prefers_symbol_aligned_signature_propagation() -> None:
    groups = build_transition_action_choice_groups(
        [
            _signature_propagation_candidate_row(
                rank_index=1,
                action="rename_symbol",
                symbol="render_profile",
                params={"from": "username", "scope": "call_site", "to": "name"},
                passed=False,
                failure_hint_score=147.0,
                caller_symbols=[
                    "profile_label",
                    "display_profile",
                    "profile_heading",
                ],
            ),
            _signature_propagation_candidate_row(
                rank_index=2,
                action="propagate_signature",
                symbol="render_profile",
                params={"from": "name", "to": "username"},
                passed=True,
                failure_hint_score=110.0,
                caller_symbols=[
                    "profile_label",
                    "display_profile",
                    "profile_heading",
                ],
            ),
            _signature_propagation_candidate_row(
                rank_index=3,
                action="propagate_signature",
                symbol="user_badge_label",
                params={"from": "name", "to": "username"},
                passed=False,
                failure_hint_score=40.0,
                caller_symbols=["profile_badge"],
            ),
        ],
        embedding_dim=8,
    )

    ranked = rank_transition_action_candidates(groups[0])
    rename_score = score_transition_action_candidate(
        groups[0]["candidates"][0],
        group=groups[0],
    )
    propagation_score = score_transition_action_candidate(
        groups[0]["candidates"][1],
        group=groups[0],
    )
    unrelated_score = score_transition_action_candidate(
        groups[0]["candidates"][2],
        group=groups[0],
    )

    assert [candidate["rank_index"] for candidate in ranked] == [2, 1, 3]
    assert (
        propagation_score["features"][
            "signature_propagation_type_error_to_matches_keyword"
        ]
        == 1.0
    )
    assert (
        propagation_score["features"]["signature_propagation_file_and_symbol_match"]
        == 1.0
    )
    assert (
        rename_score["features"][
            "rename_symbol_call_site_decoy_competes_with_signature_propagation"
        ]
        == 1.0
    )
    assert unrelated_score["features"]["signature_propagation_file_match"] == 1.0
    assert unrelated_score["features"]["signature_propagation_symbol_match"] == 0.0
    assert (
        unrelated_score["features"]["signature_propagation_file_and_symbol_match"]
        == 0.0
    )
    assert propagation_score["score"] > rename_score["score"]
    assert propagation_score["score"] > unrelated_score["score"]


def test_baseline_orders_are_stable_and_distinct() -> None:
    group = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )[0]

    existing = rank_transition_action_candidates(group, strategy="existing-rank-order")
    lexical = rank_transition_action_candidates(group, strategy="stable-lexical-order")
    random_once = rank_transition_action_candidates(
        group,
        strategy="deterministic-random-order",
    )
    random_twice = rank_transition_action_candidates(
        group,
        strategy="deterministic-random-order",
    )

    assert [candidate["rank_index"] for candidate in existing] == [1, 2]
    assert [candidate["rank_index"] for candidate in lexical] == [2, 1]
    assert [candidate["rank_index"] for candidate in random_once] == [
        candidate["rank_index"] for candidate in random_twice
    ]


def test_v2_scorer_calibrates_from_action_choice_outcomes() -> None:
    rows: list[dict[str, object]] = []
    for index, family in enumerate(
        ("operator_fix", "operator_fix", "operator_holdout"),
        start=1,
    ):
        plan = f"plan-v2-{index}"
        rows.extend(
            [
                _candidate_row(
                    rank_index=1,
                    passed=False,
                    repair_plan_id=plan,
                    task=f"task_{index}",
                    task_family=family,
                    params={"to": "*"},
                    model_score=1.0,
                    ranker_score=1.0,
                    failure_hint_score=1.0,
                    patched_source="def add(left, right):\n    return left * right\n",
                ),
                _candidate_row(
                    rank_index=2,
                    passed=True,
                    repair_plan_id=plan,
                    task=f"task_{index}",
                    task_family=family,
                    params={"to": "+"},
                    model_score=0.0,
                    ranker_score=0.0,
                    failure_hint_score=0.0,
                    patched_source="def add(left, right):\n    return left + right\n",
                ),
            ]
        )
    groups = build_transition_action_choice_groups(rows, embedding_dim=8)

    report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
        v2_validation_fraction=0.5,
    )

    calibration = report["calibration"]
    assert calibration["schema_version"] == TRANSITION_ACTION_SCORER_V2_CALIBRATION_VERSION
    assert calibration["available"] is True
    assert calibration["split"]["split_by"] == "task_family"
    assert calibration["training"]["pair_count"] > 0
    assert calibration["validation"]["product_readiness"]["baseline"] == "existing-rank-order"
    v1_metrics = report["metrics"][TRANSITION_ACTION_SCORER_VERSION]
    v2_metrics = report["metrics"][TRANSITION_ACTION_SCORER_V2_VERSION]
    assert v2_metrics["pass_at_1_count"] > v1_metrics["pass_at_1_count"]
    assert v2_metrics["mean_reciprocal_rank"] > v1_metrics["mean_reciprocal_rank"]


def test_v2_calibration_supports_source_file_validation_split() -> None:
    groups = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        source_path=Path("first-candidate-outcomes.jsonl"),
        embedding_dim=8,
    ) + build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=False,
                repair_plan_id="second-plan",
                params={"to": "*"},
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=True,
                repair_plan_id="second-plan",
                params={"to": "+"},
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
        ],
        source_path=Path("second-candidate-outcomes.jsonl"),
        embedding_dim=8,
    )

    calibration = calibrate_transition_action_scorer_v2(
        groups,
        split_by="source_file",
        validation_fraction=0.5,
    )

    assert calibration["available"] is True
    assert calibration["split"]["split_by"] == "source_file"
    assert calibration["split"]["training_bucket_count"] == 1
    assert calibration["split"]["validation_bucket_count"] == 1
    assert set(calibration["validation"]["metrics"]) >= {
        TRANSITION_ACTION_SCORER_V2_VERSION,
        TRANSITION_ACTION_SCORER_VERSION,
        "existing-rank-order",
        "stable-lexical-order",
        "deterministic-random-order",
    }


def test_v3_scorer_features_include_candidate_change_context_deltas() -> None:
    row = _candidate_row(
        rank_index=1,
        passed=True,
        repair_plan_id="plan-change-context",
        params={"to": "+"},
        model_score=0.1,
        ranker_score=0.2,
        failure_hint_score=0.3,
        patched_source="def add(left, right):\n    return left + right\n",
    )
    row.update(
        {
            "diff_added_lines": 2,
            "diff_removed_lines": 1,
            "diff_changed_lines": 3,
            "edit_is_single_line": True,
            "edit_within_target_span": True,
            "edit_line_span": 1,
            "edit_replacement_lines": 1,
            "edit_target_line_distance": 0,
            "ast_parse_ok": True,
            "ast_delta_added_count": 4,
            "ast_delta_removed_count": 2,
            "ast_delta_net_count": 2,
            "ast_delta_added_features": {"node:BinOp": 1, "binop:Add": 1},
            "ast_delta_removed_features": {"binop:Sub": 1},
        }
    )
    groups = build_transition_action_choice_groups([row], embedding_dim=8)
    candidate = groups[0]["candidates"][0]

    assert candidate["change_context"]["available"] is True
    score = score_transition_action_candidate_v3(
        candidate,
        group=groups[0],
        model={"weights": {}, "allow_production_rank_feature": False},
    )
    features = score["features"]

    assert features["change_context_available"] == 1.0
    assert features["change:diff_changed_lines:scaled"] == pytest.approx(0.15)
    assert features["change:edit_is_single_line"] == 1.0
    assert features["change:ast_parse_ok"] == 1.0
    assert features["change_ast_added:node:BinOp"] == pytest.approx(0.2)
    assert features["change_ast_removed:binop:Sub"] == pytest.approx(0.2)


def test_v3_scorer_features_include_nested_candidate_after_for_wrapper_decoys() -> None:
    row = _candidate_row(
        rank_index=1,
        passed=True,
        repair_plan_id="plan-wrapper-decoy",
        task="held_out_wrapper_behavior",
        task_family="held_out_wrapper_decoy",
        params={"name": "Wrapper"},
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
        patched_source="def add(left, right):\n    return left + right\n",
    )
    row["candidate_after"] = {
        "available": True,
        "file_path": "api.py",
        "diff_summary": {"added_line_count": 8, "removed_line_count": 1},
        "ast_delta": {
            "ast_parse_ok": True,
            "ast_delta_added_count": 9,
            "ast_delta_removed_count": 1,
            "ast_delta_net_count": 8,
            "ast_delta_added_features": {
                "node:ClassDef": 1,
                "node:FunctionDef": 2,
                "call:isinstance": 1,
            },
            "ast_delta_removed_features": {"node:Pass": 1},
        },
    }
    groups = build_transition_action_choice_groups([row], embedding_dim=8)

    score = score_transition_action_candidate_v3(
        groups[0]["candidates"][0],
        group=groups[0],
        model={"weights": {}, "allow_production_rank_feature": False},
    )
    features = score["features"]

    assert features["candidate_after_available"] == 1.0
    assert features["change_context_available"] == 1.0
    assert features["change:diff_changed_lines:scaled"] == pytest.approx(0.45)
    assert features["change_ast_added:node:ClassDef"] == pytest.approx(0.2)
    assert features["change_ast_added:node:FunctionDef"] == pytest.approx(0.4)
    assert features["change_ast_added:call:isinstance"] == pytest.approx(0.2)


def test_residual_examples_capture_wrong_top_action_choice() -> None:
    groups = build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=False,
                repair_plan_id="plan-wrong-top",
                params={"to": "*"},
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=True,
                repair_plan_id="plan-wrong-top",
                params={"to": "+"},
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
        ],
        embedding_dim=8,
    )

    report = evaluate_transition_action_choices(groups, top_k=2, residual_limit=1)

    scorer_metrics = report["metrics"][TRANSITION_ACTION_SCORER_VERSION]
    assert scorer_metrics["pass_at_1_count"] == 0
    assert scorer_metrics["top_k_pass_count"] == 1
    assert scorer_metrics["mean_reciprocal_rank"] == 0.5
    assert scorer_metrics["average_candidates_saved_vs_existing_rank_order"] == 0.0
    residual = report["residual_examples"][0]
    assert residual["group_id"] == groups[0]["id"]
    assert residual["grouping"] == groups[0]["grouping"]
    assert residual["selected_top_candidate"]["rank_index"] == 1
    assert residual["selected_top_candidate"]["params"] == {"to": "*"}
    assert residual["selected_top_candidate"]["passed"] is False
    assert residual["passing_candidate_ranks"] == [2]
    assert residual["first_pass_rank"] == 2
    assert residual["ranked_candidate_ranks"] == [1, 2]


def test_product_readiness_gate_allows_guarded_opt_in_only_after_strict_gain() -> None:
    groups = build_transition_action_choice_groups(
        _fixture_candidate_rows(),
        embedding_dim=8,
    )

    scoring_report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )
    readiness = evaluate_transition_product_readiness(scoring_report)

    assert readiness["schema_version"] == TRANSITION_PRODUCT_READINESS_VERSION
    assert readiness["gate_result"] == GATE_READY_FOR_GUARDED_OPT_IN
    assert readiness["eligible_for_shadow_mode"] is True
    assert readiness["eligible_for_guarded_opt_in"] is True
    assert readiness["comparison_scope"] == "solved_action_choice_groups"
    assert readiness["residual_count"] == 0
    assert readiness["metrics"]["pass_at_1"]["delta"] == 1.0
    assert readiness["metrics"]["top_k"]["delta"] == 1.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == 0.5
    assert (
        readiness["metrics"]["average_candidates_validated_before_first_pass"]["delta"]
        == -1.0
    )


def test_product_readiness_gate_rejects_scorer_under_existing_rank_order() -> None:
    groups = build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=True,
                repair_plan_id="plan-regression",
                params={"to": "+"},
                first_passing_index=1,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=False,
                repair_plan_id="plan-regression",
                params={"to": "*"},
                first_passing_index=1,
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
        ],
        embedding_dim=8,
    )

    scoring_report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )
    readiness = evaluate_transition_product_readiness(scoring_report)

    assert readiness["gate_result"] == GATE_NOT_READY_UNDERPERFORMS
    assert readiness["eligible_for_shadow_mode"] is False
    assert readiness["eligible_for_guarded_opt_in"] is False
    assert readiness["residual_count"] == 1
    assert readiness["metrics"]["pass_at_1"]["delta"] == -1.0
    assert readiness["metrics"]["top_k"]["delta"] == -1.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == -0.5
    assert "pass_at_1_under_existing_rank_order" in readiness["reasons"]
    assert "mrr_under_existing_rank_order" in readiness["reasons"]


def test_product_readiness_gate_uses_shadow_mode_for_non_regressing_scorer() -> None:
    groups = build_transition_action_choice_groups(
        [
            _candidate_row(
                rank_index=1,
                passed=True,
                repair_plan_id="plan-equal",
                params={"to": "+"},
                first_passing_index=1,
                model_score=1.0,
                ranker_score=1.0,
                failure_hint_score=1.0,
                patched_source="def add(left, right):\n    return left + right\n",
            ),
            _candidate_row(
                rank_index=2,
                passed=False,
                repair_plan_id="plan-equal",
                params={"to": "*"},
                first_passing_index=1,
                model_score=0.0,
                ranker_score=0.0,
                failure_hint_score=0.0,
                patched_source="def add(left, right):\n    return left * right\n",
            ),
        ],
        embedding_dim=8,
    )

    scoring_report = evaluate_transition_action_choices(
        groups,
        top_k=1,
        include_random_baseline=False,
    )
    readiness = evaluate_transition_product_readiness(scoring_report)

    assert readiness["gate_result"] == GATE_READY_FOR_SHADOW_MODE
    assert readiness["eligible_for_shadow_mode"] is True
    assert readiness["eligible_for_guarded_opt_in"] is False
    assert readiness["residual_count"] == 0
    assert readiness["metrics"]["pass_at_1"]["delta"] == 0.0
    assert readiness["metrics"]["mean_reciprocal_rank"]["delta"] == 0.0
    assert readiness["reasons"] == []


def test_evaluator_rejects_invalid_arguments() -> None:
    groups = build_transition_action_choice_groups(_fixture_candidate_rows(), embedding_dim=8)

    with pytest.raises(ValueError, match="top_k must be >= 1"):
        evaluate_transition_action_choices(groups, top_k=0)
    with pytest.raises(ValueError, match="residual_limit must be >= 0"):
        evaluate_transition_action_choices(groups, residual_limit=-1)
    with pytest.raises(ValueError, match="unknown transition action scoring strategy"):
        rank_transition_action_candidates(groups[0], strategy="missing")


def _fixture_candidate_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in (FIXTURES / "candidate_outcomes.jsonl").read_text(encoding="utf-8").splitlines():
        if not row:
            continue
        # eval keeps source text local so source/after embedding features can be tested.
        parsed = json.loads(row)
        parsed["before_source"] = "def add(left, right):\n    return left - right\n"
        parsed["patched_source"] = (
            "def add(left, right):\n    return left + right\n"
            if parsed["passed"]
            else "def add(left, right):\n    return left - right\n"
        )
        rows.append(parsed)
    return rows


def _candidate_row(
    *,
    rank_index: int,
    passed: bool,
    repair_plan_id: str,
    params: dict[str, object],
    task: str = "calculator_add",
    task_family: str = "operator_fix",
    first_passing_index: int = 2,
    model_score: float,
    ranker_score: float,
    failure_hint_score: float,
    patched_source: str,
) -> dict[str, object]:
    return {
        "task": task,
        "task_family": task_family,
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": repair_plan_id,
        "file_path": "calculator.py",
        "action": "change_operator",
        "symbol": "add",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "BinOp",
        "params": params,
        "reason": "try operator",
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": ranker_score,
        "target_context": {"function_name": "add", "line_span": [2, 2]},
        "before_source": "def add(left, right):\n    return left - right\n",
        "patched_source": patched_source,
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": first_passing_index,
        "is_first_pass": passed and rank_index == first_passing_index,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "assertions": [{"actual": 1, "expected": 3, "operator": "=="}],
                "function_names": ["add"],
            }
        ],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _mapping_candidate_row(
    *,
    rank_index: int,
    action: str,
    params: dict[str, object],
    passed: bool,
    model_score: float = 0.0,
    ranker_score: float = 0.0,
    failure_hint_score: float = 0.0,
    failure_hints: list[dict[str, object]] | None = None,
    target_context: dict[str, object] | None = None,
) -> dict[str, object]:
    context = (
        dict(target_context)
        if target_context is not None
        else {
            "mapping_name": "attrs",
            "dict_literal_key_count": 3,
            "dict_literal_keys": ["http_only", "same_site", "secure"],
        }
    )
    hints = (
        failure_hints
        if failure_hints is not None
        else [
            {
                "asserted_mapping_keys": ["secure"],
                "assertions": [
                    {"actual": True, "operator": "is", "expected": False},
                ],
            }
        ]
    )
    return {
        "task": "mapping_target",
        "task_family": "mapping_key_value_target",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": "plan-mapping-target",
        "file_path": "policy.py",
        "action": action,
        "symbol": "default_cookie_attributes",
        "start_line": 3,
        "end_line": 3,
        "node_kind": "Dict" if action != "change_subscript_key" else "Subscript",
        "params": params,
        "reason": f"try {action}",
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": ranker_score,
        "target_context": context,
        "before_source": "def attrs():\n    return {'secure': True}\n",
        "patched_source": "def attrs():\n    return {'secure': False}\n",
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": 2,
        "is_first_pass": passed and rank_index == 2,
        "passing_candidates": 1,
        "failure_hints": hints,
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


APACHE_LICENSE_ACTUAL = "License :: OSI Approved :: Apache License"
APACHE_LICENSE_EXPECTED = "License :: OSI Approved :: Apache Software License"


def _apache_license_mapping_candidate_rows() -> list[dict[str, object]]:
    hints = [
        {
            "asserted_mapping_keys": ["Apache-2.0"],
            "assertions": [
                {
                    "actual": "License :: OSI Approved :: Apache...",
                    "operator": "==",
                    "expected": "License :: OSI Approved :: Apache Software...",
                }
            ],
            "assertion_diff_lines": [
                "Differing items:",
                (
                    "{'Apache-2.0': 'License :: OSI Approved :: Apache License'} "
                    "!= {'Apache-2.0': "
                    "'License :: OSI Approved :: Apache Software License'}"
                ),
                "Full diff:",
                (
                    "- {'Apache-2.0': "
                    "'License :: OSI Approved :: Apache Software License'}"
                ),
                "+ {'Apache-2.0': 'License :: OSI Approved :: Apache License'}",
            ],
        }
    ]
    return [
        _apache_license_mapping_candidate_row(
            rank_index=1,
            key="MIT",
            original="License :: OSI Approved :: MIT License",
            replacement=APACHE_LICENSE_ACTUAL,
            passed=False,
            hints=hints,
            score=0.6,
        ),
        _apache_license_mapping_candidate_row(
            rank_index=2,
            key="MIT",
            original="License :: OSI Approved :: MIT License",
            replacement=APACHE_LICENSE_EXPECTED,
            passed=False,
            hints=hints,
            score=0.35,
        ),
        _apache_license_mapping_candidate_row(
            rank_index=5,
            key="Apache-2.0",
            original=APACHE_LICENSE_ACTUAL,
            replacement=APACHE_LICENSE_EXPECTED,
            passed=True,
            hints=hints,
            score=0.0,
        ),
    ]


def _apache_license_mapping_candidate_row(
    *,
    rank_index: int,
    key: str,
    original: str,
    replacement: str,
    passed: bool,
    hints: list[dict[str, object]],
    score: float,
) -> dict[str, object]:
    return {
        "task": "apache_license_classifier_dict_value",
        "task_family": "mapping_key_value_target",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": "plan-apache-license-classifier",
        "file_path": "setup_metadata.py",
        "action": "change_dict_value",
        "symbol": "license_classifiers",
        "start_line": 4,
        "end_line": 8,
        "node_kind": "Dict",
        "params": {"key": key, "from": original, "to": replacement},
        "reason": f"try {key} classifier value",
        "model_score": score,
        "failure_hint_score": score,
        "ranker_score": score,
        "target_context": {
            "mapping_name": "classifiers",
            "dict_value_key": key,
            "dict_value_key_in_same_mapping": True,
            "dict_literal_key_count": 2,
            "dict_literal_keys": ["Apache-2.0", "MIT"],
        },
        "before_source": (
            "CLASSIFIERS = {\n"
            "    'MIT': 'License :: OSI Approved :: MIT License',\n"
            "    'Apache-2.0': 'License :: OSI Approved :: Apache License',\n"
            "}\n"
        ),
        "patched_source": (
            "CLASSIFIERS = {\n"
            "    'MIT': 'License :: OSI Approved :: MIT License',\n"
            "    'Apache-2.0': 'License :: OSI Approved :: Apache License',\n"
            f"    {key!r}: {replacement!r},\n"
            "}\n"
        ),
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": 5,
        "is_first_pass": passed and rank_index == 5,
        "passing_candidates": 1,
        "failure_hints": hints,
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _boundary_literal_candidate_row(
    *,
    rank_index: int,
    action: str,
    params: dict[str, object],
    passed: bool,
    task: str,
    task_family: str,
    file_path: str,
    symbol: str,
    node_kind: str,
    model_score: float = 0.0,
    ranker_score: float = 0.0,
    failure_hint_score: float = 0.0,
) -> dict[str, object]:
    expected = (
        "{name} {filename!r} is a directory."
        if task == "dynamic_field_error_message"
        else 5000
    )
    actual = (
        "{name} '{filename}' is a directory."
        if task == "dynamic_field_error_message"
        else 4999
    )
    function_name = (
        "invalid_directory_message"
        if task == "dynamic_field_error_message"
        else "shipping_total"
        if task == "free_shipping_threshold_module_constant"
        else symbol
    )
    source_file = (
        "errors/messages.py"
        if task == "dynamic_field_error_message"
        else file_path
    )
    missing_names = (
        ["FREE_SHIPPING_MINIMUM_CENTS"]
        if task == "free_shipping_threshold_module_constant"
        else []
    )
    return {
        "task": task,
        "task_family": task_family,
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": f"plan-{task}",
        "file_path": file_path,
        "action": action,
        "symbol": symbol,
        "start_line": 3,
        "end_line": 3,
        "node_kind": node_kind,
        "params": params,
        "reason": f"try {action}",
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": ranker_score,
        "target_context": {"function_name": symbol, "line_span": [3, 3]},
        "before_source": "def target():\n    return False\n",
        "patched_source": "def target():\n    return True\n",
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": 2,
        "is_first_pass": passed and rank_index == 2,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "source_files": [source_file],
                "function_names": [function_name],
                "missing_names": missing_names,
                "assertions": [
                    {"actual": actual, "operator": "==", "expected": expected},
                ],
            }
        ],
        "equivalent_candidate_ranks": [1, 2],
        "overlapping_candidate_ranks": [1, 2],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _tail_index_candidate_row(
    *,
    task: str,
    symbol: str,
    rank_index: int,
    action: str,
    params: dict[str, object],
    node_kind: str,
    passed: bool,
    model_score: float,
    failure_hint_score: float,
    actual: object,
    expected: object,
    tail_intent_hint: bool = True,
) -> dict[str, object]:
    return {
        "task": task,
        "task_family": "unclassified",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": f"plan-{task}",
        "file_path": "bugs.py",
        "action": action,
        "symbol": symbol,
        "start_line": 2,
        "end_line": 2,
        "node_kind": node_kind,
        "params": params,
        "reason": (
            "replace first item access with last item access"
            if action == "replace_expr" and tail_intent_hint
            else "replace indexed item access"
            if action == "replace_expr"
            else "try nearby literal -2"
        ),
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": None,
        "target_context": {
            "callee_count": 0,
            "caller_count": 0,
            "qualified_symbol": f"bugs.{symbol}",
            "role": "helper",
        },
        "before_source": "def target(items):\n    return items[0]\n",
        "patched_source": "def target(items):\n    return items[-1]\n",
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": 1,
        "is_first_pass": passed and rank_index == 1,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "assertions": [
                    {
                        "actual": actual,
                        "expected": expected,
                        "operator": "==",
                    }
                ],
                "exception_type": "AssertionError",
                "function_names": [symbol],
                "nodeid": (
                    f"tests/test_bugs.py::test_{symbol}_returns_tail"
                    if tail_intent_hint
                    else f"tests/test_bugs.py::test_{symbol}_returns_first"
                ),
                "summary": f"assert {actual!r} == {expected!r}",
            }
        ],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _guard_candidate_row(
    *,
    rank_index: int,
    action: str,
    symbol: str,
    params: dict[str, object],
    node_kind: str,
    passed: bool,
    model_score: float,
    failure_hint_score: float,
    hinted_symbol: str = "average",
    nodeid: str = "tests/test_bugs.py::test_average_empty_values_returns_zero",
    exception_type: str = "ZeroDivisionError",
) -> dict[str, object]:
    return {
        "task": "missing_guard",
        "task_family": "unclassified",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": "plan-missing-guard",
        "file_path": "bugs.py",
        "action": action,
        "symbol": symbol,
        "start_line": 20 if action == "insert_guard" else 2,
        "end_line": 20 if action == "insert_guard" else 2,
        "node_kind": node_kind,
        "params": params,
        "reason": (
            "insert empty-sequence guard for values"
            if action == "insert_guard"
            else "try comparison operator <"
        ),
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": None,
        "target_context": {
            "callee_count": 0,
            "caller_count": 0,
            "qualified_symbol": f"bugs.{symbol}",
            "role": "helper",
        },
        "before_source": (
            "def apply_discount(total, discount):\n"
            "    return total if discount > 100 else total - discount\n\n"
            "def average(values):\n"
            "    return sum(values) / len(values)\n"
        ),
        "patched_source": (
            "def apply_discount(total, discount):\n"
            "    return total if discount > 100 else total - discount\n\n"
            "def average(values):\n"
            "    if not values:\n"
            "        return 0\n"
            "    return sum(values) / len(values)\n"
        )
        if action == "insert_guard"
        else (
            "def apply_discount(total, discount):\n"
            "    return total if discount < 100 else total - discount\n\n"
            "def average(values):\n"
            "    return sum(values) / len(values)\n"
        ),
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": 1,
        "is_first_pass": passed and rank_index == 1,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "exception_type": exception_type,
                "function_names": [hinted_symbol],
                "nodeid": nodeid,
                "source_files": ["bugs.py"],
                "summary": (
                    "ZeroDivisionError: division by zero"
                    if exception_type == "ZeroDivisionError"
                    else "assert total == discounted"
                ),
                "traceback_locations": [
                    {"file_path": "tests/test_bugs.py", "line": 22},
                    {
                        "exception_type": exception_type,
                        "file_path": "bugs.py",
                        "line": 20,
                    },
                ],
            }
        ],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _missing_import_candidate_row(
    *,
    rank_index: int,
    action: str,
    params: dict[str, object],
    file_path: str,
    symbol: str,
    node_kind: str,
    passed: bool,
    model_score: float,
    failure_hint_score: float,
    first_passing_index: int = 2,
    target_context: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "task": "receipt_label_nested_module_import_decoy",
        "task_family": "missing_import",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": "plan-receipt-label-nested-import",
        "file_path": file_path,
        "action": action,
        "symbol": symbol,
        "start_line": 1 if action == "add_import" else 2,
        "end_line": 1 if action == "add_import" else 2,
        "node_kind": node_kind,
        "params": params,
        "reason": (
            f"add missing import for {symbol}"
            if action == "add_import"
            else "try nearby literal 98"
        ),
        "model_score": model_score,
        "failure_hint_score": failure_hint_score,
        "ranker_score": None,
        "target_context": (
            dict(target_context) if target_context is not None else {"role": "helper"}
        ),
        "before_source": "def receipt_label(total):\n    return format_receipt_total(total)\n",
        "patched_source": "def receipt_label(total):\n    return format_receipt_total(total)\n",
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": first_passing_index,
        "is_first_pass": passed and rank_index == first_passing_index,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "asserted_mapping_keys": [],
                "assertion_diff_lines": [],
                "assertions": [],
                "exception_type": "NameError",
                "expected_strings": [],
                "function_names": [
                    "format_receipt_total",
                    "receipt_label",
                    "receipt_total_label",
                ],
                "missing_attributes": [],
                "missing_keys": [],
                "missing_modules": [],
                "missing_names": ["format_receipt_total"],
                "nodeid": (
                    "tests/test_shop.py::"
                    "test_receipt_label_imports_nested_report_formatter"
                ),
                "source_files": ["shop/api.py", "shop/reports/summary.py"],
                "summary": None,
                "traceback_locations": [
                    {"exception_type": None, "file_path": "tests/test_shop.py", "line": 73},
                    {"exception_type": None, "file_path": "shop/api.py", "line": 67},
                    {
                        "exception_type": "NameError",
                        "file_path": "shop/reports/summary.py",
                        "line": 2,
                    },
                ],
                "type_error_names": [],
            }
        ],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _signature_propagation_candidate_row(
    *,
    rank_index: int,
    action: str,
    symbol: str,
    params: dict[str, object],
    passed: bool,
    failure_hint_score: float,
    caller_symbols: list[str],
) -> dict[str, object]:
    return {
        "task": "profile_signature_propagation",
        "task_family": "signature_propagation",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": "plan-profile-signature-propagation",
        "file_path": "shop/profiles.py",
        "action": action,
        "symbol": symbol,
        "start_line": 6,
        "end_line": 6,
        "node_kind": "FunctionDef" if action == "propagate_signature" else "Call",
        "params": params,
        "reason": f"try {action} for username TypeError",
        "model_score": 0.0,
        "failure_hint_score": failure_hint_score,
        "ranker_score": None,
        "target_context": {
            "callee_count": 0,
            "caller_count": len(caller_symbols),
            "qualified_symbol": f"shop.profiles.{symbol}",
            "role": "helper",
            "upstream_callers": [
                {"distance": 1 if index < 2 else 2, "symbol": caller}
                for index, caller in enumerate(caller_symbols)
            ],
        },
        "before_source": (
            "def render_profile(name):\n"
            "    return f'Profile: {name}'\n\n"
            "def user_badge_label(name):\n"
            "    return f'Badge: {name}'\n"
        ),
        "patched_source": (
            "def render_profile(username):\n"
            "    return f'Profile: {username}'\n\n"
            "def user_badge_label(name):\n"
            "    return f'Badge: {name}'\n"
        ),
        "passed": passed,
        "preferred": passed,
        "rank_index": rank_index,
        "first_passing_index": 2,
        "is_first_pass": passed and rank_index == 2,
        "passing_candidates": 1,
        "failure_hints": [
            {
                "asserted_mapping_keys": [],
                "assertion_diff_lines": [],
                "assertions": [],
                "exception_type": "TypeError",
                "expected_strings": [],
                "function_names": [
                    "display_profile",
                    "profile_heading",
                    "render_profile",
                ],
                "missing_attributes": [],
                "missing_keys": [],
                "missing_modules": [],
                "missing_names": [],
                "nodeid": (
                    "tests/test_shop.py::"
                    "test_profile_label_accepts_username_keyword"
                ),
                "source_files": ["shop/api.py", "shop/profiles.py"],
                "summary": "TypeError: unexpected keyword username",
                "traceback_locations": [
                    {
                        "exception_type": None,
                        "file_path": "tests/test_shop.py",
                        "line": 48,
                    },
                    {"exception_type": None, "file_path": "shop/api.py", "line": 39},
                    {
                        "exception_type": "TypeError",
                        "file_path": "shop/profiles.py",
                        "line": 6,
                    },
                ],
                "type_error_names": ["username"],
            }
        ],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _model_009_wrap_try_except_rows() -> list[dict[str, object]]:
    hints = [
        {
            "exception_type": "ValueError",
            "function_names": ["int", "parse_quantity"],
            "source_files": ["bugs.py"],
            "assertions": [],
            "missing_names": [],
            "missing_modules": [],
        }
    ]
    return [
        _model_009_candidate_row(
            task="wrap_try_except",
            task_family="unclassified",
            split="validation",
            rank_index=1,
            first_passing_index=1,
            action="wrap_try_except",
            params={"exception": "ValueError", "return": 0},
            passed=True,
            file_path="bugs.py",
            symbol="parse_quantity",
            node_kind="Return",
            target_context={
                "callee_count": 0,
                "caller_count": 0,
                "qualified_symbol": "bugs.parse_quantity",
                "role": "helper",
            },
            failure_hints=hints,
            diff_added_lines=4,
            diff_removed_lines=1,
            diff_changed_lines=5,
            edit_is_single_line=False,
            ast_delta_added_features={
                "name:ValueError": 1,
                "node:ExceptHandler": 1,
                "node:Try": 1,
            },
        ),
        _model_009_candidate_row(
            task="wrap_try_except",
            task_family="unclassified",
            split="validation",
            rank_index=2,
            first_passing_index=1,
            action="add_import",
            params={
                "import": "from pathlib import Path",
                "module": "pathlib",
                "name": "Path",
            },
            passed=False,
            file_path="bugs.py",
            symbol="Path",
            node_kind="Import",
            target_context={"role": "helper"},
            failure_hints=hints,
            diff_added_lines=1,
            diff_removed_lines=0,
            diff_changed_lines=1,
            ast_delta_added_features={"node:ImportFrom": 1, "node:alias": 1},
        ),
    ]


def _model_009_express_boundary_rows() -> list[dict[str, object]]:
    hints = [
        {
            "exception_type": "AssertionError",
            "function_names": ["express_shipping_label"],
            "assertion_diff_lines": ["- free", "+ paid"],
            "assertions": [
                {"actual": "paid", "operator": "==", "expected": "free"},
            ],
            "missing_names": [],
            "missing_modules": [],
        }
    ]
    return [
        _model_009_candidate_row(
            task="express_shipping_boundary_preferred_helper",
            task_family="operator_boundary",
            split="train",
            rank_index=1,
            first_passing_index=2,
            action="swap_call_arg",
            params={"left": 0, "right": 1},
            passed=False,
            file_path="shop/api.py",
            symbol="express_shipping_label",
            node_kind="Call",
            target_context={
                "callee_count": 1,
                "caller_count": 0,
                "qualified_symbol": "shop.api.express_shipping_label",
                "role": "public_api",
                "swap_call_breaks_name_alignment": True,
                "swap_call_callee": "express_shipping_eligible",
                "swap_call_left_arg_name": "subtotal_cents",
                "swap_call_left_param": "subtotal_cents",
                "swap_call_name_alignment_after": "broken",
                "swap_call_name_alignment_before": "preserved",
                "swap_call_right_arg_name": "minimum_cents",
                "swap_call_right_param": "minimum_cents",
            },
            failure_hints=hints,
        ),
        _model_009_candidate_row(
            task="express_shipping_boundary_preferred_helper",
            task_family="operator_boundary",
            split="train",
            rank_index=2,
            first_passing_index=2,
            action="change_literal",
            params={"from": 5000, "to": 4998},
            passed=True,
            file_path="shop/api.py",
            symbol="express_shipping_label",
            node_kind="Constant",
            target_context={
                "callee_count": 1,
                "caller_count": 0,
                "qualified_symbol": "shop.api.express_shipping_label",
                "role": "public_api",
            },
            failure_hints=hints,
            ast_delta_added_features={"literal:number:4998": 1},
            ast_delta_removed_features={"literal:number:5000": 1},
        ),
        _model_009_candidate_row(
            task="express_shipping_boundary_preferred_helper",
            task_family="operator_boundary",
            split="train",
            rank_index=3,
            first_passing_index=2,
            action="change_literal",
            params={"from": 5000, "to": 4999},
            passed=True,
            file_path="shop/api.py",
            symbol="express_shipping_label",
            node_kind="Constant",
            target_context={
                "callee_count": 1,
                "caller_count": 0,
                "qualified_symbol": "shop.api.express_shipping_label",
                "role": "public_api",
            },
            failure_hints=hints,
            ast_delta_added_features={"literal:number:4999": 1},
            ast_delta_removed_features={"literal:number:5000": 1},
        ),
    ]


def _model_009_module_constant_rows() -> list[dict[str, object]]:
    hints = [
        {
            "exception_type": "AssertionError",
            "function_names": ["free_shipping_threshold"],
            "assertions": [
                {
                    "actual": 4999,
                    "operator": "==",
                    "expected": 5000,
                    "numeric_delta": 1,
                }
            ],
            "missing_names": [],
            "missing_modules": [],
        }
    ]
    return [
        _model_009_candidate_row(
            task="free_shipping_threshold_module_constant",
            task_family="module_constant",
            split="train",
            rank_index=1,
            first_passing_index=1,
            action="change_module_constant",
            params={
                "from": 4999,
                "name": "FREE_SHIPPING_MINIMUM_CENTS",
                "to": 5000,
            },
            passed=True,
            file_path="shop/shipping.py",
            symbol="FREE_SHIPPING_MINIMUM_CENTS",
            node_kind="Constant",
            target_context={"role": "helper"},
            failure_hints=hints,
            ast_delta_added_features={"literal:number:5000": 1},
            ast_delta_removed_features={"literal:number:4999": 1},
        ),
        _model_009_candidate_row(
            task="free_shipping_threshold_module_constant",
            task_family="module_constant",
            split="train",
            rank_index=2,
            first_passing_index=1,
            action="change_literal",
            params={"from": 5000, "to": 5001},
            passed=False,
            file_path="shop/api.py",
            symbol="express_shipping_label",
            node_kind="Constant",
            target_context={
                "callee_count": 1,
                "caller_count": 0,
                "qualified_symbol": "shop.api.express_shipping_label",
                "role": "public_api",
            },
            failure_hints=hints,
            ast_delta_added_features={"literal:number:5001": 1},
            ast_delta_removed_features={"literal:number:5000": 1},
        ),
    ]


def _model_009_quote_total_rows() -> list[dict[str, object]]:
    hints = [
        {
            "exception_type": "AssertionError",
            "function_names": ["quote_total"],
            "assertions": [
                {
                    "actual": 20.0,
                    "operator": "==",
                    "expected": 80,
                    "numeric_delta": 60.0,
                }
            ],
            "missing_names": [],
            "missing_modules": [],
        }
    ]
    return [
        _model_009_candidate_row(
            task="quote_total_helper_discount",
            task_family="expression_helper",
            split="test",
            rank_index=1,
            first_passing_index=2,
            action="swap_call_arg",
            params={"left": 0, "right": 1},
            passed=False,
            file_path="shop/api.py",
            symbol="quote_total",
            node_kind="Call",
            target_context={
                "callee_count": 1,
                "caller_count": 0,
                "qualified_symbol": "shop.api.quote_total",
                "role": "public_api",
                "swap_call_breaks_name_alignment": True,
                "swap_call_callee": "discounted_subtotal",
                "swap_call_left_arg_name": "subtotal",
                "swap_call_left_param": "subtotal",
                "swap_call_name_alignment_after": "broken",
                "swap_call_name_alignment_before": "preserved",
                "swap_call_right_arg_name": "discount_percent",
                "swap_call_right_param": "discount_percent",
            },
            failure_hints=hints,
        ),
        _model_009_candidate_row(
            task="quote_total_helper_discount",
            task_family="expression_helper",
            split="test",
            rank_index=2,
            first_passing_index=2,
            action="replace_expr",
            params={
                "replacement": "subtotal - (subtotal * discount_percent / 100)"
            },
            passed=True,
            file_path="shop/pricing.py",
            symbol="discounted_subtotal",
            node_kind="BinOp",
            target_context={
                "callee_count": 0,
                "caller_count": 1,
                "qualified_symbol": "shop.pricing.discounted_subtotal",
                "role": "helper",
                "upstream_callers": [{"distance": 1, "symbol": "quote_total"}],
            },
            failure_hints=hints,
            ast_delta_added_count=6,
            ast_delta_net_count=6,
            ast_delta_added_features={
                "binop:Sub": 1,
                "name:subtotal": 1,
                "node:BinOp": 1,
                "node:Sub": 1,
            },
        ),
        _model_009_candidate_row(
            task="quote_total_helper_discount",
            task_family="expression_helper",
            split="test",
            rank_index=3,
            first_passing_index=2,
            action="change_literal",
            params={"from": 100, "to": 98},
            passed=False,
            file_path="shop/pricing.py",
            symbol="discounted_subtotal",
            node_kind="Constant",
            target_context={
                "callee_count": 0,
                "caller_count": 1,
                "qualified_symbol": "shop.pricing.discounted_subtotal",
                "role": "helper",
                "upstream_callers": [{"distance": 1, "symbol": "quote_total"}],
            },
            failure_hints=hints,
            ast_delta_added_features={"literal:number:98": 1},
            ast_delta_removed_features={"literal:number:100": 1},
        ),
    ]


def _model_009_candidate_row(
    *,
    task: str,
    task_family: str,
    split: str,
    rank_index: int,
    first_passing_index: int,
    action: str,
    params: dict[str, object],
    passed: bool,
    file_path: str,
    symbol: str,
    node_kind: str,
    target_context: dict[str, object],
    failure_hints: list[dict[str, object]],
    diff_added_lines: int = 1,
    diff_removed_lines: int = 1,
    diff_changed_lines: int = 2,
    edit_is_single_line: bool = True,
    ast_delta_added_count: int | None = None,
    ast_delta_removed_count: int | None = None,
    ast_delta_net_count: int | None = None,
    ast_delta_added_features: dict[str, int] | None = None,
    ast_delta_removed_features: dict[str, int] | None = None,
) -> dict[str, object]:
    added_features = ast_delta_added_features or {}
    removed_features = ast_delta_removed_features or {}
    added_count = (
        ast_delta_added_count
        if ast_delta_added_count is not None
        else sum(added_features.values())
    )
    removed_count = (
        ast_delta_removed_count
        if ast_delta_removed_count is not None
        else sum(removed_features.values())
    )
    net_count = (
        ast_delta_net_count
        if ast_delta_net_count is not None
        else added_count - removed_count
    )
    return {
        "task": task,
        "task_family": task_family,
        "source_type": "handcrafted",
        "split": split,
        "language": "python",
        "phase": "ranked",
        "repair_plan_id": f"patch-plan:model-009-{task}",
        "file_path": file_path,
        "action": action,
        "symbol": symbol,
        "start_line": 1,
        "end_line": 1,
        "node_kind": node_kind,
        "params": params,
        "reason": f"try {action}",
        "model_score": 0.0,
        "failure_hint_score": 0.0,
        "ranker_score": None,
        "target_context": target_context,
        "passed": passed,
        "preferred": False,
        "rank_index": rank_index,
        "first_passing_index": first_passing_index,
        "is_first_pass": passed and rank_index == first_passing_index,
        "passing_candidates": 1,
        "failure_hints": failure_hints,
        "diff_added_lines": diff_added_lines,
        "diff_removed_lines": diff_removed_lines,
        "diff_changed_lines": diff_changed_lines,
        "edit_line_span": 1,
        "edit_replacement_lines": diff_added_lines,
        "edit_line_delta": diff_added_lines - diff_removed_lines,
        "edit_target_line_distance": 0,
        "edit_is_single_line": edit_is_single_line,
        "edit_within_target_span": True,
        "ast_parse_ok": True,
        "ast_delta_added_count": added_count,
        "ast_delta_removed_count": removed_count,
        "ast_delta_net_count": net_count,
        "ast_delta_added_features": added_features,
        "ast_delta_removed_features": removed_features,
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }


def _scoring_candidate(
    *,
    action: str,
    params: dict[str, object],
    validated: bool,
    model_score: float,
    ranker_score: float,
    failure_hint_score: float,
    failure_hints: list[dict[str, object]],
    passed: bool | None = None,
    target_context: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "rank_index": 1,
        "action": {
            "kind": action,
            "file_path": "client.py",
            "symbol": "load",
            "start_line": 2,
            "end_line": 2,
            "node_kind": "Call",
            "params": params,
        },
        "target_context": (
            dict(target_context)
            if target_context is not None
            else {"function_name": "load", "line_span": [2, 2]}
        ),
        "source_context": {
            "available": True,
            "kind": "candidate_original_source",
            "embedding_available": False,
        },
        "candidate_after": {
            "available": True,
            "kind": "candidate_patched_source",
            "embedding_available": False,
        },
        "scores": {
            "model_score": model_score,
            "failure_hint_score": failure_hint_score,
            "ranker_score": ranker_score,
        },
        "validation": {
            "validated": validated,
            "passed": passed if validated else None,
            "status": "passed" if passed else ("failed" if validated else "not_validated"),
            "failure_hints": failure_hints,
        },
    }
