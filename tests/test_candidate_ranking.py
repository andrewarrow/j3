from __future__ import annotations

import json

from actions import PatchAction, PatchActionKind, PatchTarget
from candidate_ranking import CandidateRankerModel, candidate_features, train_candidate_ranker
from candidate_ranker.features import _candidate_record_features
from failure_hints import PytestFailureHint
from patching import CandidatePatch, prioritize_candidate_patches, rank_with_candidate_ranker
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
