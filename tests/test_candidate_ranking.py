from __future__ import annotations

import json

from actions import PatchAction, PatchActionKind, PatchTarget
from candidate_ranking import CandidateRankerModel, candidate_features, train_candidate_ranker
from candidate_ranker.features import _candidate_record_features
from failure_hints import AssertionComparison, PytestFailureHint
from patching import CandidatePatch, prioritize_candidate_patches, rank_with_candidate_ranker
from repair.patching.context import attach_target_context
from synth import SourceEdit


def test_train_candidate_ranker_from_diagnostics_and_rerank(tmp_path) -> None:
    diagnostics = tmp_path / "diagnostics.json"
    diagnostics.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "boundary",
                        "family": "operator_boundary",
                        "ranked": {
                            "selected": {"passed": True},
                            "failure_hints": [
                                {
                                    "function_names": ["meets_minimum"],
                                    "source_files": ["bugs.py"],
                                    "assertions": [{"operator": "is", "actual": False, "expected": True}],
                                }
                            ],
                            "tested_candidates": [
                                _candidate_record(to="<", passed=False),
                                _candidate_record(to=">=", passed=True),
                            ],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = train_candidate_ranker(diagnostics_paths=[diagnostics], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    ranked = rank_with_candidate_ranker(
        [
            _candidate(to="<", failure_hint_score=50.0),
            _candidate(to=">=", failure_hint_score=50.0),
        ],
        ranker,
        hints=[],
    )

    assert result.training_pairs == 1
    assert result.training_accuracy == 1.0
    assert result.margin_violations == 0
    assert result.per_action["change_operator"]["pass_at_1"] == 0
    assert result.per_task_family["operator_boundary"]["training_pairs"] == 1
    assert ranked[0].action.params["to"] == ">="
    assert ranked[0].ranker_score is not None


def test_train_candidate_ranker_uses_post_pass_exploration_failures(tmp_path) -> None:
    diagnostics = tmp_path / "diagnostics.json"
    diagnostics.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "dict_key",
                        "ranked": {
                            "selected": {"passed": True},
                            "failure_hints": [{"missing_keys": ["name"]}],
                            "tested_candidates": [
                                _subscript_key_candidate_record(passed=True),
                                _candidate_record(to="<", passed=False),
                            ],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = train_candidate_ranker(diagnostics_paths=[diagnostics], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    ranked = rank_with_candidate_ranker(
        [_candidate(to="<", failure_hint_score=0.0), _subscript_key_candidate()],
        ranker,
        hints=[PytestFailureHint(missing_keys={"name"})],
    )

    assert result.training_pairs == 1
    assert ranked[0].action.kind == PatchActionKind.CHANGE_SUBSCRIPT_KEY


def test_train_candidate_ranker_from_candidate_outcomes_jsonl(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to="<", passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to=">=", passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
        {
            "task": "boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to="!=", passed=False),
            "rank_index": 3,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(candidate_outcome_paths=[outcomes], out_dir=tmp_path / "run")

    assert result.rows == 3
    assert result.passing_rows == 1
    assert result.failing_rows == 2
    assert result.tasks == 1
    assert result.plans == 1
    assert result.training_pairs == 2
    assert result.per_action["change_operator"]["rows"] == 3
    assert result.per_action["change_operator"]["avg_first_passing_index"] == 2.0
    assert result.per_action["change_operator"]["avg_positive_rank"] == 2.0
    assert result.per_task_family["operator_boundary"]["pass_at_1"] == 0

    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert metrics["per_action"]["change_operator"]["training_pairs"] == 2
    assert metrics["per_task_family"]["operator_boundary"]["passing_rows"] == 1
    assert metrics["calibration"]["rows"] == 3
    assert metrics["calibration"]["passing_rows"] == 1
    assert metrics["calibration"]["brier_score"] is not None
    assert metrics["calibration"]["expected_calibration_error"] is not None
    assert sum(bucket["rows"] for bucket in metrics["calibration"]["buckets"]) == 3
    assert result.calibration["rows"] == 3


def test_train_candidate_ranker_reports_held_out_validation_metrics(tmp_path) -> None:
    train_outcomes = tmp_path / "train-candidate-outcomes.jsonl"
    validation_outcomes = tmp_path / "validation-candidate-outcomes.jsonl"
    train_rows = [
        {
            "task": "train_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to="<", passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "train_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to=">=", passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
    ]
    validation_rows = [
        {
            "task": "held_out_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to="<", passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "held_out_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to=">=", passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
    ]
    train_outcomes.write_text(
        "\n".join(json.dumps(row) for row in train_rows) + "\n",
        encoding="utf-8",
    )
    validation_outcomes.write_text(
        "\n".join(json.dumps(row) for row in validation_rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(
        candidate_outcome_paths=[train_outcomes],
        validation_candidate_outcome_paths=[validation_outcomes],
        out_dir=tmp_path / "run",
    )

    assert result.validation["plans"] == 1
    assert result.validation["rows"] == 2
    assert result.validation["solved"] == 1
    assert result.validation["pass_at_1"] == 1
    assert result.validation["positive_at_1"] == 1
    assert result.validation["avg_first_passing_index"] == 1.0
    assert result.validation["per_task_family"]["operator_boundary"]["pass_at_1"] == 1

    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert metrics["validation"]["calibration"]["rows"] == 2
    assert metrics["validation_candidate_outcome_sources"] == [str(validation_outcomes.resolve())]


def test_train_candidate_ranker_can_hold_out_task_family_from_same_outcomes(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "held_out_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to="<", passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "held_out_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            **_candidate_record(to=">=", passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
        {
            "task": "train_mapping_key",
            "task_family": "mapping_key",
            "phase": "ranked",
            **_subscript_key_candidate_record(passed=False),
            "params": {"from": "name", "to": "display_name"},
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "train_mapping_key",
            "task_family": "mapping_key",
            "phase": "ranked",
            **_subscript_key_candidate_record(passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(
        candidate_outcome_paths=[outcomes],
        holdout_task_families=["operator_boundary"],
        out_dir=tmp_path / "run",
    )

    assert result.rows == 2
    assert result.tasks == 1
    assert result.holdout_task_families == ["operator_boundary"]
    assert result.per_task_family.keys() == {"mapping_key"}
    assert result.validation["plans"] == 1
    assert result.validation["rows"] == 2
    assert result.validation["per_task_family"].keys() == {"operator_boundary"}
    assert result.validation["holdout_candidate_outcome_sources"] == [str(outcomes.resolve())]

    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert metrics["holdout_task_families"] == ["operator_boundary"]
    assert metrics["validation"]["holdout_task_families"] == ["operator_boundary"]


def test_train_candidate_ranker_prefers_marked_passing_outcome(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "boundary",
            "phase": "ranked",
            **_candidate_record(to="<", passed=True),
            "rank_index": 1,
            "first_passing_index": 1,
            "is_first_pass": True,
            "preferred": False,
        },
        {
            "task": "boundary",
            "phase": "ranked",
            **_candidate_record(to=">=", passed=True),
            "rank_index": 2,
            "first_passing_index": 1,
            "is_first_pass": False,
            "preferred": True,
        },
        {
            "task": "boundary",
            "phase": "ranked",
            **_candidate_record(to="!=", passed=False),
            "rank_index": 3,
            "first_passing_index": 1,
            "is_first_pass": False,
            "preferred": False,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(candidate_outcome_paths=[outcomes], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    ranked = rank_with_candidate_ranker(
        [
            _candidate(to="<", failure_hint_score=50.0),
            _candidate(to=">=", failure_hint_score=50.0),
        ],
        ranker,
        hints=[],
    )

    assert result.training_pairs == 2
    assert ranked[0].action.params["to"] == ">="


def test_train_candidate_ranker_from_outcomes_uses_failure_hint_context(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "visible_balance",
            "phase": "ranked",
            **_attribute_candidate_record(to="available_cents", passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
            "failure_hints": [
                {
                    "nodeid": "tests/test_shop.py::test_visible_balance_uses_balance_cents",
                    "function_names": ["visible_balance", "account_balance"],
                    "missing_attributes": ["amount_cents"],
                    "source_files": ["shop/accounts.py"],
                }
            ],
        },
        {
            "task": "visible_balance",
            "phase": "ranked",
            **_attribute_candidate_record(to="balance_cents", passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
            "failure_hints": [
                {
                    "nodeid": "tests/test_shop.py::test_visible_balance_uses_balance_cents",
                    "function_names": ["visible_balance", "account_balance"],
                    "missing_attributes": ["amount_cents"],
                    "source_files": ["shop/accounts.py"],
                }
            ],
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(candidate_outcome_paths=[outcomes], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    hint = PytestFailureHint(
        nodeid="tests/test_shop.py::test_visible_balance_uses_balance_cents",
        function_names={"visible_balance", "account_balance"},
        missing_attributes={"amount_cents"},
    )
    ranked = rank_with_candidate_ranker(
        [
            _attribute_candidate(to="available_cents"),
            _attribute_candidate(to="balance_cents"),
        ],
        ranker,
        hints=[hint],
    )

    assert result.training_pairs == 1
    assert ranked[0].action.params["to"] == "balance_cents"


def test_ranker_overrides_higher_failure_hint_score(tmp_path) -> None:
    ranker = CandidateRankerModel(
        path=tmp_path / "ranker.json",
        weights={"failure_hint_score": -100.0},
    )
    ranked = prioritize_candidate_patches(
        [
            _candidate(to="<", failure_hint_score=0.0, symbol="meets_minimum"),
            _candidate(to=">=", failure_hint_score=0.0, symbol="other_minimum"),
        ],
        hints=[PytestFailureHint(function_names={"meets_minimum"})],
        ranker=ranker,
    )

    assert ranked[0].action.params["to"] == ">="
    assert ranked[1].failure_hint_score > ranked[0].failure_hint_score
    assert ranked[0].ranker_score is not None
    assert ranked[0].ranker_score > (ranked[1].ranker_score or 0.0)


def test_hint_first_ordering_is_preserved_without_ranker() -> None:
    ranked = prioritize_candidate_patches(
        [
            _candidate(to="<", failure_hint_score=0.0, symbol="meets_minimum"),
            _candidate(to=">=", failure_hint_score=0.0, symbol="other_minimum", ranker_score=100.0),
        ],
        hints=[PytestFailureHint(function_names={"meets_minimum"})],
    )

    assert ranked[0].action.params["to"] == "<"
    assert ranked[0].failure_hint_score > ranked[1].failure_hint_score


def test_candidate_features_include_missing_key_hint_matches() -> None:
    candidate = _subscript_key_candidate()

    features = candidate_features(candidate, hints=[PytestFailureHint(missing_keys={"name"})])

    assert features["hint_has_missing_key"] == 1.0
    assert features["hint_missing_key:name"] == 1.0
    assert features["hint_missing_key_matches_from"] == 1.0
    assert features["hint_missing_key_in_to"] == 1.0
    assert features["action_hint_missing_key_matches_from:change_subscript_key"] == 1.0


def test_candidate_features_include_asserted_mapping_key_matches() -> None:
    candidate = _subscript_key_candidate()

    features = candidate_features(
        candidate,
        hints=[PytestFailureHint(asserted_mapping_keys={"customer_name"})],
    )

    assert features["hint_has_asserted_mapping_key"] == 1.0
    assert features["hint_asserted_mapping_key_matches_to"] == 1.0
    assert features["action_hint_asserted_mapping_key_matches_to:change_subscript_key"] == 1.0


def test_candidate_features_avoid_exact_task_specific_identity() -> None:
    candidate = _candidate(to=">=", failure_hint_score=50.0, symbol="meets_minimum")

    features = candidate_features(candidate)

    assert "reason:try comparison operator >=" not in features
    assert "symbol:meets_minimum" not in features
    assert "param:to=>=" not in features
    assert features["has_failure_hint_score"] == 1.0
    assert features["action_has_failure_hint_score:change_operator"] == 1.0
    assert features["param_symbol:to=>="] == 1.0


def test_candidate_features_include_type_error_name_matches() -> None:
    candidate = CandidatePatch(
        file_path="shop/profiles.py",
        action=PatchAction(
            kind=PatchActionKind.PROPAGATE_SIGNATURE,
            target=PatchTarget(
                file_path="shop/profiles.py",
                start_line=1,
                end_line=2,
                symbol="render_profile",
                node_kind="FunctionDef",
            ),
            params={"from": "name", "to": "username"},
        ),
        edit=SourceEdit(start_line=1, start_col=0, end_line=1, end_col=0, replacement=""),
        original_source="",
        patched_source="",
        reason="propagate signature name name to username",
    )

    features = candidate_features(candidate, hints=[PytestFailureHint(type_error_names={"username"})])

    assert features["hint_has_type_error_name"] == 1.0
    assert features["hint_type_error_name_matches_to"] == 1.0
    assert features["action_hint_type_error_name_matches_to:propagate_signature"] == 1.0


def test_candidate_features_include_hint_token_overlap_without_exact_identity() -> None:
    candidate = _attribute_candidate(to="balance_cents")

    features = candidate_features(
        candidate,
        hints=[
            PytestFailureHint(
                nodeid="tests/test_shop.py::test_visible_balance_uses_balance_cents",
                function_names={"visible_balance", "account_balance"},
            )
        ],
    )

    assert "param:to=balance_cents" not in features
    assert features["hint_param_to_token_overlap"] > 0.0
    assert features["action_hint_param_to_token_overlap:change_attribute"] > 0.0


def test_candidate_features_include_import_locality() -> None:
    source = "def receipt_total_label(cents):\n    return format_receipt_total(cents)\n"
    candidate = CandidatePatch(
        file_path="shop/reports/summary.py",
        action=PatchAction(
            kind=PatchActionKind.ADD_IMPORT,
            target=PatchTarget(
                file_path="shop/reports/summary.py",
                start_line=1,
                end_line=1,
                symbol="format_receipt_total",
                node_kind="Import",
            ),
            params={
                "name": "format_receipt_total",
                "module": "shop.reports.money",
                "import": "from shop.reports.money import format_receipt_total",
            },
        ),
        edit=SourceEdit(
            start_line=1,
            start_col=0,
            end_line=1,
            end_col=0,
            replacement="from shop.reports.money import format_receipt_total\n",
        ),
        original_source=source,
        patched_source="from shop.reports.money import format_receipt_total\n" + source,
        reason="add missing import for format_receipt_total",
    )

    features = candidate_features(candidate)

    assert features["import_module_same_target_package"] == 1.0
    assert features["action_import_module_same_target_package:add_import"] == 1.0


def test_candidate_features_include_edit_size_and_locality() -> None:
    features = candidate_features(_candidate(to=">=", failure_hint_score=50.0))

    assert features["diff_changed_lines:2_3"] == 1.0
    assert features["action_diff_changed_lines:change_operator:2_3"] == 1.0
    assert features["edit_line_span:1"] == 1.0
    assert features["edit_replacement_lines:1"] == 1.0
    assert features["edit_line_delta:same"] == 1.0
    assert features["edit_target_line_distance:0"] == 1.0
    assert features["edit_within_target_span"] == 1.0
    assert features["edit_is_single_line"] == 1.0


def test_candidate_features_include_ast_delta() -> None:
    features = candidate_features(_candidate(to=">=", failure_hint_score=50.0))

    assert features["ast_parse_ok"] == 1.0
    assert features["ast_delta_added:cmpop:GtE"] == 1.0
    assert features["ast_delta_removed:cmpop:Gt"] == 1.0
    assert features["ast_delta_net_count:same"] == 1.0


def test_candidate_record_features_include_edit_size_and_locality() -> None:
    record = {
        **_candidate_record(to=">=", passed=True),
        "diff_changed_lines": 2,
        "edit_line_span": 1,
        "edit_replacement_lines": 1,
        "edit_line_delta": 0,
        "edit_target_line_distance": 0,
        "edit_within_target_span": True,
        "edit_is_single_line": True,
    }

    features = _candidate_record_features(record, [])

    assert features["diff_changed_lines:2_3"] == 1.0
    assert features["action_diff_changed_lines:change_operator:2_3"] == 1.0
    assert features["edit_line_span:1"] == 1.0
    assert features["edit_replacement_lines:1"] == 1.0
    assert features["edit_line_delta:same"] == 1.0
    assert features["edit_target_line_distance:0"] == 1.0
    assert features["edit_within_target_span"] == 1.0
    assert features["edit_is_single_line"] == 1.0


def test_candidate_record_features_include_ast_delta() -> None:
    record = {
        **_candidate_record(to=">=", passed=True),
        "ast_parse_ok": True,
        "ast_delta_added_features": {"cmpop:GtE": 1},
        "ast_delta_removed_features": {"cmpop:Gt": 1},
        "ast_delta_added_count": 1,
        "ast_delta_removed_count": 1,
        "ast_delta_net_count": 0,
    }

    features = _candidate_record_features(record, [])

    assert features["ast_parse_ok"] == 1.0
    assert features["ast_delta_added:cmpop:GtE"] == 1.0
    assert features["ast_delta_removed:cmpop:Gt"] == 1.0
    assert features["ast_delta_net_count:same"] == 1.0


def test_candidate_record_features_include_relation_metadata_without_pass_leakage() -> None:
    record = {
        **_candidate_record(to=">=", passed=True),
        "rank_index": 3,
        "equivalent_candidate_ranks": [5],
        "equivalent_candidate_count": 1,
        "overlapping_candidate_ranks": [1, 4, 7],
        "overlapping_candidate_count": 3,
        "equivalent_passing_candidate_ranks": [5],
        "overlapping_passing_candidate_ranks": [4],
        "has_equivalent_passing_candidate": True,
        "has_overlapping_passing_candidate": True,
    }

    features = _candidate_record_features(record, [])

    assert features["has_equivalent_candidate"] == 1.0
    assert features["action_has_equivalent_candidate:change_operator"] == 1.0
    assert features["equivalent_candidate_count:1"] == 1.0
    assert features["equivalent_candidate_after"] == 1.0
    assert features["overlapping_candidate_count:2_3"] == 1.0
    assert features["overlapping_candidate_before"] == 1.0
    assert features["overlapping_candidate_after"] == 1.0
    assert features["overlapping_candidate_rank_distance:1"] == 1.0
    assert "has_equivalent_passing_candidate" not in features
    assert "has_overlapping_passing_candidate" not in features


def test_train_candidate_ranker_uses_relation_metadata_from_outcomes(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "boundary",
            "phase": "ranked",
            **_candidate_record(to="<", passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
            "overlapping_candidate_ranks": [2],
            "overlapping_candidate_count": 1,
        },
        {
            "task": "boundary",
            "phase": "ranked",
            **_candidate_record(to=">=", passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
            "overlapping_candidate_ranks": [],
            "overlapping_candidate_count": 0,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(candidate_outcome_paths=[outcomes], out_dir=tmp_path / "run")
    model = json.loads(result.ranker_path.read_text(encoding="utf-8"))

    assert result.training_pairs == 1
    assert "has_overlapping_candidate" in model["weights"]
    assert model["weights"]["has_overlapping_candidate"] < 0


def test_candidate_features_include_target_context_call_graph() -> None:
    candidate = _discounted_subtotal_candidate()

    features = candidate_features(
        candidate,
        hints=[PytestFailureHint(function_names={"quote_total"})],
    )

    assert features["target_role:helper"] == 1.0
    assert features["hint_call_graph_distance:1"] == 1.0
    assert features["hint_call_graph_closeness"] == 0.5
    assert features["target_is_downstream_of_hint"] == 1.0


def test_candidate_features_connect_subscript_write_to_returned_mapping_key(tmp_path) -> None:
    source = (
        "def parse_header(header):\n"
        "    directives = {\n"
        "        'no_cache': False,\n"
        "        'no_store': False,\n"
        "    }\n"
        "    if header == 'no-store':\n"
        "        directives['no-store'] = True\n"
        "    return directives\n"
    )
    repo_file = tmp_path / "policy.py"
    repo_file.write_text(source, encoding="utf-8")
    candidate = CandidatePatch(
        file_path="policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_SUBSCRIPT_KEY,
            target=PatchTarget(
                file_path="policy.py",
                start_line=7,
                end_line=7,
                symbol="parse_header",
                node_kind="Subscript",
            ),
            params={"from": "no-store", "to": "no_store"},
        ),
        edit=SourceEdit(start_line=7, start_col=19, end_line=7, end_col=29, replacement="'no_store'"),
        original_source=source,
        patched_source=source.replace("directives['no-store']", "directives['no_store']"),
        reason="try subscript key 'no_store'",
    )

    [candidate_with_context] = attach_target_context(tmp_path, [candidate])
    features = candidate_features(candidate_with_context)

    assert candidate_with_context.target_context["subscript_write_to_returned_mapping"] is True
    assert candidate_with_context.target_context["subscript_to_matches_returned_mapping_key"] is True
    assert "subscript_from_matches_returned_mapping_key" not in candidate_with_context.target_context
    assert features["subscript_write_to_returned_mapping"] == 1.0
    assert features["action_subscript_to_matches_returned_mapping_key:change_subscript_key"] == 1.0


def test_candidate_features_distinguish_same_mapping_asserted_key_value_and_key_decoy(tmp_path) -> None:
    value_candidate, key_candidate = _cookie_secure_candidates()
    repo_file = tmp_path / "policy.py"
    repo_file.write_text(value_candidate.original_source, encoding="utf-8")

    value_with_context, key_with_context = attach_target_context(
        tmp_path,
        [value_candidate, key_candidate],
    )
    hints = [
        PytestFailureHint(
            asserted_mapping_keys={"secure"},
            assertions=[AssertionComparison(actual=True, operator="is", expected=False)],
        )
    ]

    value_features = candidate_features(value_with_context, hints=hints)
    key_features = candidate_features(key_with_context, hints=hints)

    assert value_with_context.target_context["dict_value_key"] == "secure"
    assert key_with_context.target_context["dict_key_from"] == "secure"
    assert value_features["same_mapping_asserted_key_value_changed"] == 1.0
    assert (
        value_features[
            "same_mapping_asserted_key_value_matches_assertion_delta"
        ]
        == 1.0
    )
    assert (
        value_features[
            "action_same_mapping_asserted_key_value_matches_assertion_delta:change_dict_value"
        ]
        == 1.0
    )
    assert (
        value_features[
            "action_same_mapping_asserted_key_value_changed:change_dict_value"
        ]
        == 1.0
    )
    assert key_features["same_mapping_asserted_key_renamed_or_removed"] == 1.0
    assert "same_mapping_asserted_key_value_matches_assertion_delta" not in key_features
    assert (
        key_features[
            "action_same_mapping_asserted_key_renamed_or_removed:change_dict_key"
        ]
        == 1.0
    )


def test_candidate_features_distinguish_scalar_dict_value_assertion_delta() -> None:
    preferred, false = _cookie_host_prefix_candidates()
    hints = [
        PytestFailureHint(
            assertions=[
                AssertionComparison(actual="__Host", operator="==", expected="__Host-")
            ],
        )
    ]

    preferred_features = candidate_features(preferred, hints=hints)
    false_features = candidate_features(false, hints=hints)

    assert preferred_features["dict_value_scalar_assertion_delta_matches"] == 1.0
    assert (
        preferred_features[
            "action_dict_value_scalar_assertion_delta_matches:change_dict_value"
        ]
        == 1.0
    )
    assert (
        false_features["dict_value_scalar_assertion_delta_from_matches_actual_only"]
        == 1.0
    )
    assert "dict_value_scalar_assertion_delta_matches" not in false_features


def test_candidate_features_record_swap_call_arg_role_metadata(tmp_path) -> None:
    repair_candidate = _swap_call_alignment_candidate(
        source=(
            "def render_pair(name, value):\n"
            "    return f'{name}={value}'\n\n"
            "def cookie_pair(value, name):\n"
            "    return render_pair(value, name)\n"
        ),
        patched_call="render_pair(name, value)",
        symbol="cookie_pair",
        line=5,
    )
    broken_candidate = _swap_call_alignment_candidate(
        source=(
            "def normalize_scope(host, path):\n"
            "    return host, path\n\n"
            "def cookie_scope_key(host, path):\n"
            "    return normalize_scope(host, path)\n"
        ),
        patched_call="normalize_scope(path, host)",
        symbol="cookie_scope_key",
        line=5,
    )
    get_candidate = _swap_call_alignment_candidate(
        source=(
            "def should_store_response(headers):\n"
            "    cache_control = headers.get('cache-control', '')\n"
            "    return cache_control\n"
        ),
        patched_call="headers.get('', 'cache-control')",
        symbol="should_store_response",
        line=2,
    )
    (tmp_path / "cookies.py").write_text(repair_candidate.original_source, encoding="utf-8")
    repair_with_context = attach_target_context(tmp_path, [repair_candidate])[0]
    (tmp_path / "cookies.py").write_text(broken_candidate.original_source, encoding="utf-8")
    broken_with_context = attach_target_context(tmp_path, [broken_candidate])[0]
    (tmp_path / "cookies.py").write_text(get_candidate.original_source, encoding="utf-8")
    get_with_context = attach_target_context(tmp_path, [get_candidate])[0]

    repair_features = candidate_features(repair_with_context)
    broken_features = candidate_features(broken_with_context)
    get_features = candidate_features(get_with_context)

    assert repair_with_context.target_context["swap_call_name_alignment_before"] == "broken"
    assert repair_with_context.target_context["swap_call_name_alignment_after"] == "preserved"
    assert repair_features["swap_call_repairs_name_alignment"] == 1.0
    assert repair_features["action_swap_call_repairs_name_alignment:swap_call_arg"] == 1.0
    assert broken_with_context.target_context["swap_call_breaks_name_alignment"] is True
    assert broken_features["swap_call_breaks_name_alignment"] == 1.0
    assert get_with_context.target_context["swap_call_mapping_get_key_default_swapped"] is True
    assert get_features["swap_call_mapping_get_key_default_swapped"] == 1.0
    assert get_features["swap_call_role_pair:mapping_key->mapping_default"] == 1.0


def test_candidate_features_record_membership_predicate_metadata(tmp_path) -> None:
    source = (
        "def should_store_response(headers):\n"
        "    cache_control = headers.get('cache-control', '')\n"
        "    if 'no-store' not in cache_control and 'etag' in headers:\n"
        "        return True\n"
        "    return False\n"
    )
    package = tmp_path / "httpcache"
    package.mkdir()
    (package / "policy.py").write_text(source, encoding="utf-8")
    operator_candidate = _membership_operator_candidate(source)
    literal_candidate = _membership_literal_candidate(source)
    operator_with_context, literal_with_context = attach_target_context(
        tmp_path,
        [operator_candidate, literal_candidate],
    )

    operator_features = candidate_features(operator_with_context)
    literal_features = candidate_features(literal_with_context)

    assert operator_with_context.target_context["membership_predicate"] is True
    assert operator_with_context.target_context["membership_predicate_operator"] == "not_in"
    assert operator_with_context.target_context["membership_predicate_operator_changed"] is True
    assert operator_with_context.target_context["membership_predicate_operator_flipped"] is True
    assert operator_features["membership_predicate_operator_changed"] == 1.0
    assert (
        operator_features[
            "action_membership_predicate_operator_changed:change_operator"
        ]
        == 1.0
    )
    assert literal_with_context.target_context["membership_predicate_literal_role"] == "needle"
    assert literal_with_context.target_context["membership_predicate_needle_changed"] is True
    assert literal_features["membership_predicate_needle_changed"] == 1.0
    assert (
        literal_features[
            "action_membership_predicate_needle_changed:change_literal"
        ]
        == 1.0
    )


def test_train_candidate_ranker_uses_target_context_from_outcomes(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "quote_total",
            "phase": "ranked",
            **_quote_total_public_api_candidate_record(passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
            "failure_hints": [
                {
                    "function_names": ["quote_total"],
                    "assertions": [{"operator": "==", "actual": 20.0, "expected": 80}],
                }
            ],
        },
        {
            "task": "quote_total",
            "phase": "ranked",
            **_discounted_subtotal_candidate_record(passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
            "failure_hints": [
                {
                    "function_names": ["quote_total"],
                    "assertions": [{"operator": "==", "actual": 20.0, "expected": 80}],
                }
            ],
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(candidate_outcome_paths=[outcomes], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    ranked = rank_with_candidate_ranker(
        [
            _quote_total_public_api_candidate(),
            _discounted_subtotal_candidate(),
        ],
        ranker,
        hints=[PytestFailureHint(function_names={"quote_total"}, assertions=[])],
    )

    assert result.training_pairs == 1
    assert ranked[0].action.target.symbol == "discounted_subtotal"


def test_candidate_record_features_include_returned_mapping_key_context() -> None:
    record = {
        **_subscript_key_candidate_record(passed=True),
        "target_context": {
            "role": "helper",
            "subscript_write_to_returned_mapping": True,
            "returned_mapping_key_count": 3,
            "subscript_to_matches_returned_mapping_key": True,
        },
    }

    features = _candidate_record_features(record, [])

    assert features["subscript_write_to_returned_mapping"] == 1.0
    assert features["returned_mapping_key_count:2_3"] == 1.0
    assert features["action_subscript_to_matches_returned_mapping_key:change_subscript_key"] == 1.0


def test_candidate_record_features_include_asserted_mapping_key_matches() -> None:
    record = _subscript_key_candidate_record(passed=True)

    features = _candidate_record_features(
        record,
        [{"asserted_mapping_keys": ["customer_name"]}],
    )

    assert features["hint_has_asserted_mapping_key"] == 1.0
    assert features["hint_asserted_mapping_key_matches_to"] == 1.0
    assert features["action_hint_asserted_mapping_key_matches_to:change_subscript_key"] == 1.0


def test_candidate_record_features_distinguish_same_mapping_asserted_key_value_and_key_decoy() -> None:
    hints = [
        {
            "asserted_mapping_keys": ["secure"],
            "assertions": [{"actual": True, "operator": "is", "expected": False}],
        }
    ]

    value_features = _candidate_record_features(_cookie_secure_value_record(passed=True), hints)
    key_features = _candidate_record_features(_cookie_secure_key_record(passed=False), hints)

    assert value_features["same_mapping_asserted_key_value_changed"] == 1.0
    assert (
        value_features[
            "same_mapping_asserted_key_value_matches_assertion_delta"
        ]
        == 1.0
    )
    assert (
        value_features[
            "action_same_mapping_asserted_key_value_matches_assertion_delta:change_dict_value"
        ]
        == 1.0
    )
    assert (
        value_features[
            "action_same_mapping_asserted_key_value_changed:change_dict_value"
        ]
        == 1.0
    )
    assert key_features["same_mapping_asserted_key_renamed_or_removed"] == 1.0
    assert "same_mapping_asserted_key_value_matches_assertion_delta" not in key_features
    assert (
        key_features[
            "action_same_mapping_asserted_key_renamed_or_removed:change_dict_key"
        ]
        == 1.0
    )


def test_candidate_record_features_distinguish_scalar_dict_value_assertion_delta() -> None:
    hints = [
        {
            "assertions": [
                {"actual": "__Host", "operator": "==", "expected": "__Host-"},
            ],
        }
    ]

    preferred_features = _candidate_record_features(
        _cookie_host_prefix_value_record(to="__Host-", passed=True),
        hints,
    )
    false_features = _candidate_record_features(
        _cookie_host_prefix_value_record(to="host", passed=False),
        hints,
    )

    assert preferred_features["dict_value_scalar_assertion_delta_matches"] == 1.0
    assert (
        preferred_features[
            "action_dict_value_scalar_assertion_delta_matches:change_dict_value"
        ]
        == 1.0
    )
    assert (
        false_features["dict_value_scalar_assertion_delta_from_matches_actual_only"]
        == 1.0
    )
    assert "dict_value_scalar_assertion_delta_matches" not in false_features


def test_candidate_record_features_include_swap_call_arg_role_metadata() -> None:
    repair_features = _candidate_record_features(
        _swap_call_role_record(
            passed=True,
            target_context={
                "role": "helper",
                "swap_call_name_alignment_before": "broken",
                "swap_call_name_alignment_after": "preserved",
                "swap_call_repairs_name_alignment": True,
            },
        ),
        [],
    )
    broken_features = _candidate_record_features(
        _swap_call_role_record(
            passed=False,
            target_context={
                "role": "helper",
                "swap_call_name_alignment_before": "preserved",
                "swap_call_name_alignment_after": "broken",
                "swap_call_breaks_name_alignment": True,
            },
        ),
        [],
    )
    get_features = _candidate_record_features(
        _swap_call_role_record(
            passed=False,
            target_context={
                "role": "helper",
                "swap_call_method": "get",
                "swap_call_mapping_get_key_default_swapped": True,
                "swap_call_left_role": "mapping_key",
                "swap_call_right_role": "mapping_default",
                "swap_call_left_arg_kind": "string_literal",
                "swap_call_right_arg_kind": "empty_string_literal",
            },
        ),
        [],
    )

    assert repair_features["swap_call_repairs_name_alignment"] == 1.0
    assert repair_features["action_swap_call_name_alignment_after:swap_call_arg:preserved"] == 1.0
    assert broken_features["swap_call_breaks_name_alignment"] == 1.0
    assert get_features["swap_call_mapping_get_key_default_swapped"] == 1.0
    assert get_features["action_swap_call_method:swap_call_arg:get"] == 1.0
    assert get_features["swap_call_right_arg_kind:empty_string_literal"] == 1.0


def test_candidate_record_features_include_membership_predicate_metadata() -> None:
    operator_features = _candidate_record_features(
        _membership_context_record(
            action="change_operator",
            params={"from": "not in", "to": "in"},
            target_context={
                "role": "helper",
                "membership_predicate": True,
                "membership_predicate_operator": "not_in",
                "membership_predicate_needle_kind": "string_literal",
                "membership_predicate_container_kind": "name",
                "membership_predicate_in_branch_test": True,
                "membership_predicate_operator_changed": True,
                "membership_predicate_operator_flipped": True,
            },
        ),
        [],
    )
    literal_features = _candidate_record_features(
        _membership_context_record(
            action="change_literal",
            params={"from": "no-store", "to": "no_store"},
            target_context={
                "role": "helper",
                "membership_predicate": True,
                "membership_predicate_operator": "not_in",
                "membership_predicate_needle_kind": "string_literal",
                "membership_predicate_container_kind": "name",
                "membership_predicate_in_branch_test": True,
                "membership_predicate_literal_changed": True,
                "membership_predicate_literal_role": "needle",
                "membership_predicate_needle_changed": True,
            },
        ),
        [],
    )

    assert operator_features["membership_predicate_operator_flipped"] == 1.0
    assert (
        operator_features[
            "action_membership_predicate_operator_flipped:change_operator"
        ]
        == 1.0
    )
    assert literal_features["membership_predicate_needle_changed"] == 1.0
    assert (
        literal_features[
            "action_membership_predicate_literal_role:change_literal:needle"
        ]
        == 1.0
    )


def test_train_candidate_ranker_uses_same_mapping_asserted_key_metadata(tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "cookie_default_secure_flag_dict_value",
            "phase": "ranked",
            **_cookie_secure_key_record(passed=False),
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
            "failure_hints": [{"asserted_mapping_keys": ["secure"]}],
        },
        {
            "task": "cookie_default_secure_flag_dict_value",
            "phase": "ranked",
            **_cookie_secure_value_record(passed=True),
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
            "failure_hints": [{"asserted_mapping_keys": ["secure"]}],
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = train_candidate_ranker(candidate_outcome_paths=[outcomes], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    ranked = rank_with_candidate_ranker(
        list(_cookie_secure_candidates()),
        ranker,
        hints=[PytestFailureHint(asserted_mapping_keys={"secure"})],
    )

    assert result.training_pairs == 1
    assert ranked[0].action.kind == PatchActionKind.CHANGE_DICT_VALUE


def _candidate_record(*, to: str, passed: bool) -> dict[str, object]:
    return {
        "file_path": "bugs.py",
        "action": "change_operator",
        "symbol": "meets_minimum",
        "start_line": 2,
        "end_line": 2,
        "params": {"from": ">", "to": to},
        "reason": f"try comparison operator {to}",
        "model_score": 0.5,
        "failure_hint_score": 50.0,
        "ranker_score": None,
        "passed": passed,
    }


def _swap_call_alignment_candidate(
    *,
    source: str,
    patched_call: str,
    symbol: str,
    line: int,
) -> CandidatePatch:
    original_call = source.splitlines()[line - 1].strip().removeprefix("return ")
    return CandidatePatch(
        file_path="cookies.py",
        action=PatchAction(
            kind=PatchActionKind.SWAP_CALL_ARG,
            target=PatchTarget(
                file_path="cookies.py",
                start_line=line,
                end_line=line,
                symbol=symbol,
                node_kind="Call",
            ),
            params={"left": 0, "right": 1},
        ),
        edit=SourceEdit(
            start_line=line,
            start_col=11,
            end_line=line,
            end_col=11 + len(original_call),
            replacement=patched_call,
        ),
        original_source=source,
        patched_source=source.replace(original_call, patched_call),
        reason="swap call arguments 0 and 1",
        failure_hint_score=100.0,
    )


def _swap_call_role_record(
    *,
    passed: bool,
    target_context: dict[str, object],
) -> dict[str, object]:
    return {
        "file_path": "webcookies/policy.py",
        "action": "swap_call_arg",
        "symbol": "cookie_scope_key",
        "start_line": 5,
        "end_line": 5,
        "node_kind": "Call",
        "params": {"left": 0, "right": 1},
        "reason": "swap call arguments 0 and 1",
        "model_score": 0.0,
        "failure_hint_score": 100.0,
        "ranker_score": None,
        "passed": passed,
        "target_context": target_context,
    }


def _membership_operator_candidate(source: str) -> CandidatePatch:
    patched = source.replace("'no-store' not in cache_control", "'no-store' in cache_control")
    return CandidatePatch(
        file_path="httpcache/policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_OPERATOR,
            target=PatchTarget(
                file_path="httpcache/policy.py",
                start_line=3,
                end_line=3,
                symbol="should_store_response",
                node_kind="Compare",
            ),
            params={"from": "not in", "to": "in"},
        ),
        edit=SourceEdit(start_line=3, start_col=8, end_line=3, end_col=39, replacement="'no-store' in cache_control"),
        original_source=source,
        patched_source=patched,
        reason="try comparison operator in",
        failure_hint_score=100.0,
    )


def _membership_literal_candidate(source: str) -> CandidatePatch:
    patched = source.replace("'no-store' not in cache_control", "'no_store' not in cache_control")
    return CandidatePatch(
        file_path="httpcache/policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_LITERAL,
            target=PatchTarget(
                file_path="httpcache/policy.py",
                start_line=3,
                end_line=3,
                symbol="should_store_response",
                node_kind="Constant",
            ),
            params={"from": "no-store", "to": "no_store"},
        ),
        edit=SourceEdit(start_line=3, start_col=8, end_line=3, end_col=18, replacement="'no_store'"),
        original_source=source,
        patched_source=patched,
        reason="try nearby literal 'no_store'",
        failure_hint_score=100.0,
    )


def _membership_context_record(
    *,
    action: str,
    params: dict[str, object],
    target_context: dict[str, object],
) -> dict[str, object]:
    return {
        "file_path": "httpcache/policy.py",
        "action": action,
        "symbol": "should_store_response",
        "start_line": 3,
        "end_line": 3,
        "node_kind": "Compare",
        "params": params,
        "reason": "membership predicate edit",
        "model_score": 0.0,
        "failure_hint_score": 100.0,
        "ranker_score": None,
        "passed": True,
        "target_context": target_context,
    }


def _cookie_secure_candidates() -> tuple[CandidatePatch, CandidatePatch]:
    source = (
        "def default_cookie_attributes():\n"
        "    return {\n"
        "        'secure': True,\n"
        "        'http_only': True,\n"
        "        'same_site': 'Lax',\n"
        "    }\n"
    )
    value_patched = source.replace("'secure': True", "'secure': False")
    key_patched = source.replace("'secure': True", "'__Secure-': True")
    value_candidate = CandidatePatch(
        file_path="policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_DICT_VALUE,
            target=PatchTarget(
                file_path="policy.py",
                start_line=3,
                end_line=3,
                symbol="default_cookie_attributes",
                node_kind="Dict",
            ),
            params={"key": "secure", "from": True, "to": False},
        ),
        edit=SourceEdit(start_line=3, start_col=18, end_line=3, end_col=22, replacement="False"),
        original_source=source,
        patched_source=value_patched,
        reason="try dictionary value 'secure'=False",
        failure_hint_score=100.0,
    )
    key_candidate = CandidatePatch(
        file_path="policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_DICT_KEY,
            target=PatchTarget(
                file_path="policy.py",
                start_line=3,
                end_line=3,
                symbol="default_cookie_attributes",
                node_kind="Dict",
            ),
            params={"from": "secure", "to": "__Secure-"},
        ),
        edit=SourceEdit(
            start_line=3,
            start_col=8,
            end_line=3,
            end_col=16,
            replacement="'__Secure-'",
        ),
        original_source=source,
        patched_source=key_patched,
        reason="try dictionary key '__Secure-'",
        failure_hint_score=100.0,
    )
    return value_candidate, key_candidate


def _cookie_host_prefix_candidates() -> tuple[CandidatePatch, CandidatePatch]:
    source = (
        "PREFIXES = {\n"
        "    'host': '__Host',\n"
        "    'secure': '__Secure-',\n"
        "}\n"
    )
    preferred_patched = source.replace("'host': '__Host'", "'host': '__Host-'")
    false_patched = source.replace("'host': '__Host'", "'host': 'host'")
    target = PatchTarget(
        file_path="policy.py",
        start_line=2,
        end_line=2,
        symbol="PREFIXES",
        node_kind="Dict",
    )
    preferred = CandidatePatch(
        file_path="policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_DICT_VALUE,
            target=target,
            params={"key": "host", "from": "__Host", "to": "__Host-"},
        ),
        edit=SourceEdit(
            start_line=2,
            start_col=12,
            end_line=2,
            end_col=20,
            replacement="'__Host-'",
        ),
        original_source=source,
        patched_source=preferred_patched,
        reason="try dictionary value 'host'='__Host-'",
        failure_hint_score=100.0,
    )
    false = CandidatePatch(
        file_path="policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_DICT_VALUE,
            target=target,
            params={"key": "host", "from": "__Host", "to": "host"},
        ),
        edit=SourceEdit(
            start_line=2,
            start_col=12,
            end_line=2,
            end_col=20,
            replacement="'host'",
        ),
        original_source=source,
        patched_source=false_patched,
        reason="try dictionary value 'host'='host'",
        failure_hint_score=100.0,
    )
    return preferred, false


def _cookie_secure_value_record(*, passed: bool) -> dict[str, object]:
    return {
        "file_path": "webcookies/policy.py",
        "action": "change_dict_value",
        "symbol": "default_cookie_attributes",
        "start_line": 3,
        "end_line": 3,
        "node_kind": "Dict",
        "params": {"key": "secure", "from": True, "to": False},
        "reason": "try dictionary value 'secure'=False",
        "model_score": 0.0,
        "failure_hint_score": 100.0,
        "ranker_score": None,
        "passed": passed,
        "target_context": {
            "role": "helper",
            "dict_literal_key_count": 3,
            "dict_literal_keys": ["http_only", "same_site", "secure"],
            "dict_value_key": "secure",
            "dict_value_key_in_same_mapping": True,
        },
    }


def _cookie_host_prefix_value_record(*, to: str, passed: bool) -> dict[str, object]:
    return {
        "file_path": "webcookies/policy.py",
        "action": "change_dict_value",
        "symbol": "PREFIXES",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "Dict",
        "params": {"key": "host", "from": "__Host", "to": to},
        "reason": f"try dictionary value 'host'={to!r}",
        "model_score": 0.0,
        "failure_hint_score": 100.0,
        "ranker_score": None,
        "passed": passed,
        "target_context": {
            "role": "helper",
            "dict_literal_key_count": 2,
            "dict_literal_keys": ["host", "secure"],
            "dict_value_key": "host",
            "dict_value_key_in_same_mapping": True,
        },
    }


def _cookie_secure_key_record(*, passed: bool) -> dict[str, object]:
    return {
        "file_path": "webcookies/policy.py",
        "action": "change_dict_key",
        "symbol": "default_cookie_attributes",
        "start_line": 3,
        "end_line": 3,
        "node_kind": "Dict",
        "params": {"from": "secure", "to": "__Secure-"},
        "reason": "try dictionary key '__Secure-'",
        "model_score": 0.0,
        "failure_hint_score": 100.0,
        "ranker_score": None,
        "passed": passed,
        "target_context": {
            "role": "helper",
            "dict_literal_key_count": 3,
            "dict_literal_keys": ["http_only", "same_site", "secure"],
            "dict_key_from": "secure",
            "dict_key_from_in_same_mapping": True,
            "dict_key_to": "__Secure-",
        },
    }


def _subscript_key_candidate_record(*, passed: bool) -> dict[str, object]:
    return {
        "file_path": "orders.py",
        "action": "change_subscript_key",
        "symbol": "customer_display_name",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "Subscript",
        "params": {"from": "name", "to": "customer_name"},
        "reason": "try subscript key 'customer_name'",
        "model_score": 0.0,
        "failure_hint_score": 142.0,
        "ranker_score": None,
        "passed": passed,
    }


def _attribute_candidate_record(*, to: str, passed: bool) -> dict[str, object]:
    return {
        "file_path": "shop/accounts.py",
        "action": "change_attribute",
        "symbol": "account_balance",
        "start_line": 12,
        "end_line": 12,
        "node_kind": "Attribute",
        "params": {"from": "amount_cents", "to": to},
        "reason": f"try attribute {to}",
        "model_score": 0.0,
        "failure_hint_score": 122.0,
        "ranker_score": None,
        "passed": passed,
    }


def _candidate(
    *,
    to: str,
    failure_hint_score: float,
    symbol: str = "meets_minimum",
    ranker_score: float | None = None,
) -> CandidatePatch:
    source = "def meets_minimum(value, minimum):\n    return value > minimum\n"
    return CandidatePatch(
        file_path="bugs.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_OPERATOR,
            target=PatchTarget(
                file_path="bugs.py",
                start_line=2,
                end_line=2,
                symbol=symbol,
                node_kind="Compare",
            ),
            params={"from": ">", "to": to},
        ),
        edit=SourceEdit(start_line=2, start_col=11, end_line=2, end_col=26, replacement=f"value {to} minimum"),
        original_source=source,
        patched_source=source.replace("value > minimum", f"value {to} minimum"),
        reason=f"try comparison operator {to}",
        model_score=0.5,
        failure_hint_score=failure_hint_score,
        ranker_score=ranker_score,
    )


def _subscript_key_candidate() -> CandidatePatch:
    source = "def customer_display_name(order):\n    return order['name'].title()\n"
    patched = "def customer_display_name(order):\n    return order['customer_name'].title()\n"
    return CandidatePatch(
        file_path="orders.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_SUBSCRIPT_KEY,
            target=PatchTarget(
                file_path="orders.py",
                start_line=2,
                end_line=2,
                symbol="customer_display_name",
                node_kind="Subscript",
            ),
            params={"from": "name", "to": "customer_name"},
        ),
        edit=SourceEdit(start_line=2, start_col=17, end_line=2, end_col=23, replacement="'customer_name'"),
        original_source=source,
        patched_source=patched,
        reason="try subscript key 'customer_name'",
        model_score=0.5,
        failure_hint_score=122.0,
    )


def _attribute_candidate(*, to: str) -> CandidatePatch:
    source = "def account_balance(account):\n    return account.amount_cents\n"
    patched = source.replace("amount_cents", to)
    return CandidatePatch(
        file_path="shop/accounts.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_ATTRIBUTE,
            target=PatchTarget(
                file_path="shop/accounts.py",
                start_line=2,
                end_line=2,
                symbol="account_balance",
                node_kind="Attribute",
            ),
            params={"from": "amount_cents", "to": to},
        ),
        edit=SourceEdit(start_line=2, start_col=19, end_line=2, end_col=31, replacement=to),
        original_source=source,
        patched_source=patched,
        reason=f"try attribute {to}",
        model_score=0.0,
        failure_hint_score=122.0,
    )


def _quote_total_public_api_candidate_record(*, passed: bool) -> dict[str, object]:
    return {
        "file_path": "shop/api.py",
        "action": "swap_call_arg",
        "symbol": "quote_total",
        "start_line": 10,
        "end_line": 10,
        "node_kind": "Call",
        "params": {"left": 0, "right": 1},
        "reason": "swap call arguments 0 and 1",
        "model_score": 0.0,
        "failure_hint_score": 50.0,
        "ranker_score": None,
        "passed": passed,
        "target_context": {
            "role": "public_api",
            "qualified_symbol": "shop.api.quote_total",
            "caller_count": 0,
            "callee_count": 1,
        },
    }


def _discounted_subtotal_candidate_record(*, passed: bool) -> dict[str, object]:
    return {
        "file_path": "shop/pricing.py",
        "action": "replace_expr",
        "symbol": "discounted_subtotal",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "BinOp",
        "params": {"replacement": "subtotal - (subtotal * discount_percent / 100)"},
        "reason": "convert multiplier into subtraction from base value",
        "model_score": 0.4,
        "failure_hint_score": 5.0,
        "ranker_score": None,
        "passed": passed,
        "target_context": {
            "role": "helper",
            "qualified_symbol": "shop.pricing.discounted_subtotal",
            "caller_count": 1,
            "callee_count": 0,
            "upstream_callers": [
                {"symbol": "quote_total", "distance": 1},
            ],
        },
    }


def _quote_total_public_api_candidate() -> CandidatePatch:
    source = (
        "from .pricing import discounted_subtotal\n\n"
        "def quote_total(subtotal, discount_percent):\n"
        "    return discounted_subtotal(subtotal, discount_percent)\n"
    )
    patched = source.replace(
        "discounted_subtotal(subtotal, discount_percent)",
        "discounted_subtotal(discount_percent, subtotal)",
    )
    return CandidatePatch(
        file_path="shop/api.py",
        action=PatchAction(
            kind=PatchActionKind.SWAP_CALL_ARG,
            target=PatchTarget(
                file_path="shop/api.py",
                start_line=4,
                end_line=4,
                symbol="quote_total",
                node_kind="Call",
            ),
            params={"left": 0, "right": 1},
        ),
        edit=SourceEdit(
            start_line=4,
            start_col=11,
            end_line=4,
            end_col=57,
            replacement="discounted_subtotal(discount_percent, subtotal)",
        ),
        original_source=source,
        patched_source=patched,
        reason="swap call arguments 0 and 1",
        failure_hint_score=50.0,
        target_context={
            "role": "public_api",
            "qualified_symbol": "shop.api.quote_total",
            "caller_count": 0,
            "callee_count": 1,
        },
    )


def _discounted_subtotal_candidate() -> CandidatePatch:
    source = (
        "def discounted_subtotal(subtotal, discount_percent):\n"
        "    return subtotal * (discount_percent / 100)\n"
    )
    patched = (
        "def discounted_subtotal(subtotal, discount_percent):\n"
        "    return subtotal - (subtotal * discount_percent / 100)\n"
    )
    return CandidatePatch(
        file_path="shop/pricing.py",
        action=PatchAction(
            kind=PatchActionKind.REPLACE_EXPR,
            target=PatchTarget(
                file_path="shop/pricing.py",
                start_line=2,
                end_line=2,
                symbol="discounted_subtotal",
                node_kind="BinOp",
            ),
            params={"replacement": "subtotal - (subtotal * discount_percent / 100)"},
        ),
        edit=SourceEdit(
            start_line=2,
            start_col=11,
            end_line=2,
            end_col=46,
            replacement="subtotal - (subtotal * discount_percent / 100)",
        ),
        original_source=source,
        patched_source=patched,
        reason="convert multiplier into subtraction from base value",
        model_score=0.4,
        failure_hint_score=5.0,
        target_context={
            "role": "helper",
            "qualified_symbol": "shop.pricing.discounted_subtotal",
            "caller_count": 1,
            "callee_count": 0,
            "upstream_callers": [
                {"symbol": "quote_total", "distance": 1},
            ],
        },
    )
