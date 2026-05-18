from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.prompt_intents import (
    PROMPT_FEATURE_SCHEMA_VERSION,
    _prompt_token_features,
    evaluate_prompt_intent_predictions,
    load_prompt_intent_records,
    predict_prompt_intent,
    profile_prompt_corpus_rows,
    profile_prompt_intents,
    train_prompt_intent_token_baseline,
    validate_prompt_corpus,
    validate_prompt_corpus_rows,
)


GREENSHOT_7_INTENTS = Path("examples/prompt_intents/greenshot_7_intents.jsonl")
SEED_CORPUS = Path("../prompts/coding_agent_prompts_seed.jsonl")
EXPANDED_CORPUS = Path("../prompts/coding_agent_prompts_expanded_v0.jsonl")


def test_loads_greenshot_7_prompt_intent_fixtures() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)
    profile = profile_prompt_intents(records)

    assert len(records) == 87
    assert profile["split_counts"] == {"test": 18, "train": 53, "validation": 16}
    assert profile["expected_action_counts"] == {
        "ask_clarification": 76,
        "emit_existing_repo_change_spec": 7,
        "emit_request_spec": 4,
    }
    assert profile["repo_mode_counts"] == {
        "existing_repo": 7,
        "new_repo": 71,
        "unknown": 9,
    }
    assert profile["unsupported_requirement_count"] == 76
    assert profile["existing_repo_change_count"] == 7
    assert profile["requires_clarification_counts"] == {"no": 11, "yes": 76}
    assert profile["primary_artifact_counts"] == {"none": 87}
    assert profile["unsupported_requirement_counts"] == {
        "desktop_interface": 2,
        "domain_unspecified": 9,
        "graphical_interface": 18,
        "graphing_feature_unspecified": 16,
        "none": 11,
        "scientific_operations_unspecified": 8,
        "ui_interface": 9,
        "visual_interface_scope": 9,
        "web_interface": 5,
    }
    assert profile["unsupported_requirement_family_counts"] == {
        "domain": 9,
        "feature_scope": 24,
        "interface": 43,
        "none": 11,
    }
    assert profile["missing_artifact_label_count"] == 87

    unsupported = next(
        record
        for record in records
        if record.prompt == "make me a complex graphic calc app"
    )
    assert unsupported.target.expected_action == "ask_clarification"
    assert unsupported.target.requires_clarification == "yes"
    assert unsupported.target.primary_artifact == "none"
    assert unsupported.target.unsupported_requirement == "graphical_interface"
    assert unsupported.target.unsupported_requirement_family == "interface"
    assert unsupported.target.requested_interfaces == ("graphic",)
    assert unsupported.target.unsupported_requirements == (
        "complex_scope",
        "graphical_interface",
    )
    assert unsupported.target.clarification_fields == ("interfaces",)

    labeled_unsupported_requirements = {
        record.target.unsupported_requirement
        for record in records
        if record.target.unsupported_requirement != "none"
    }
    assert {
        "desktop_interface",
        "graphing_feature_unspecified",
        "graphical_interface",
        "scientific_operations_unspecified",
        "ui_interface",
        "web_interface",
    }.issubset(labeled_unsupported_requirements)

    power_change = next(record for record in records if record.prompt == "add exponent support")
    assert power_change.target.repo_mode == "existing_repo"
    assert power_change.target.expected_action == "emit_existing_repo_change_spec"
    assert power_change.target.requires_clarification == "no"
    assert power_change.target.features == ("power",)
    assert power_change.target.target_files == (
        "calculator.py",
        "tests/test_calculator_cli.py",
    )


def test_prompt_corpus_profile_reports_quality_issues() -> None:
    rows = [
        {
            "id": "train-create",
            "split": "train",
            "source_type": "human_seed",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "prompt": "Make me a simple CLI calc",
            "expected": {
                "action": "emit_request_spec",
                "clarify": False,
                "artifacts": ["cli", "tests"],
                "inferred": ["multiply"],
            },
            "tags": ["family:calc-basic"],
        },
        {
            "id": "test-create",
            "split": "test",
            "source_type": "synthetic_template_v0",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "prompt": " make me a simple cli calc ",
            "expected": {
                "action": "emit_request_spec",
                "clarify": False,
                "artifacts": ["cli", "tests"],
                "inferred": [],
            },
            "tags": [],
            "prompt_family": "calc-basic",
            "generation": {
                "template_version": "prompt-corpus-template-v0",
                "review_status": "unreviewed_synthetic",
            },
        },
        {
            "id": "bad-row",
            "split": "holdout",
            "source_type": "unknown_generator",
            "task_type": "invent_magic",
            "repo_mode": "scratch",
            "domain": "calculator",
            "prompt": "make a calculator",
            "expected": {
                "action": "write_patch",
                "clarify": True,
                "features": "calculator",
            },
        },
    ]

    profile = profile_prompt_corpus_rows(rows)

    assert profile["schema_version"] == "prompt-corpus-profile-v1"
    assert profile["total_rows"] == 3
    assert profile["split_counts"] == {"holdout": 1, "test": 1, "train": 1}
    assert profile["source_type_counts"] == {
        "human_seed": 1,
        "synthetic_template_v0": 1,
        "unknown_generator": 1,
    }
    assert profile["task_type_counts"]["create_app"] == 2  # type: ignore[index]
    assert profile["repo_mode_counts"] == {"new_repo": 2, "scratch": 1}
    assert profile["domain_counts"] == {"calculator": 3}
    assert profile["expected_action_counts"] == {
        "emit_request_spec": 2,
        "write_patch": 1,
    }
    assert profile["clarification_counts"] == {"no": 2, "yes": 1}
    assert profile["ambiguity_counts"] == {"ambiguous": 1, "not_ambiguous": 2}
    assert profile["inferred_default_counts"] == {"multiply": 1}
    assert profile["inferred_default_presence_counts"] == {"missing": 1, "present": 2}
    assert profile["synthetic_template_family_counts"] == {"calc-basic": 1}
    assert profile["template_version_counts"] == {"prompt-corpus-template-v0": 1}
    assert profile["generation_review_status_counts"] == {
        "unreviewed_synthetic": 1
    }
    assert profile["duplicate_normalized_prompt_count"] == 1
    duplicate = profile["duplicate_normalized_prompts"][0]  # type: ignore[index]
    assert duplicate["normalized_prompt"] == "make me a simple cli calc"
    assert [row["id"] for row in duplicate["rows"]] == [
        "train-create",
        "test-create",
    ]
    leakage = profile["near_duplicate_family_leakage"][0]  # type: ignore[index]
    assert leakage["family"] == "calc-basic"
    assert leakage["splits"] == ["test", "train"]
    assert profile["duplicate_cross_split_prompt_count"] == 1
    assert profile["near_duplicate_cross_split_prompt_count"] == 1
    near_duplicate = profile["near_duplicate_cross_split_prompts"][0]  # type: ignore[index]
    assert near_duplicate["similarity"] == 1.0
    assert profile["row_schema_variant_count"] == 3
    assert profile["expected_schema_variant_count"] == 2
    assert profile["missing_required_fields"] == [
        {
            "row_index": 2,
            "line": 3,
            "id": "bad-row",
            "field": "tags",
            "issue": "missing",
        }
    ]
    assert profile["expected_field_type_issues"] == [
        {
            "row_index": 2,
            "line": 3,
            "id": "bad-row",
            "field": "expected.features",
            "issue": "invalid_type",
            "expected_type": "list",
            "actual_type": "str",
        }
    ]
    unsupported = {
        (item["field"], item["value"])
        for item in profile["unsupported_scalar_labels"]  # type: ignore[union-attr]
    }
    assert {
        ("split", "holdout"),
        ("source_type", "unknown_generator"),
        ("task_type", "invent_magic"),
        ("repo_mode", "scratch"),
        ("expected_action", "write_patch"),
    }.issubset(unsupported)
    issue_names = {
        issue["issue"]
        for issue in profile["schema_consistency_issues"]  # type: ignore[union-attr]
    }
    assert {
        "top_level_schema_variants",
        "expected_schema_variants",
        "expected_field_type_issues",
        "unsupported_scalar_labels",
        "duplicate_prompt_cross_split_leakage",
        "near_duplicate_prompt_cross_split_risk",
        "prompt_family_cross_split_leakage",
    }.issubset(issue_names)
    validate_fields = {
        field["field"]
        for field in profile["data_002_validate_fields"]  # type: ignore[union-attr]
    }
    assert {"expected.action", "expected.features", "prompt_family"}.issubset(
        validate_fields
    )


def test_prompt_corpus_validation_reports_schema_errors() -> None:
    rows = [
        {
            "id": "train-create",
            "split": "holdout",
            "source_type": "synthetic_template_v0",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "prompt": "Make me a simple CLI calc",
            "expected": {
                "action": "write_patch",
                "features": "calculator",
                "artifacts": ["cli"],
                "interfaces": ["cli"],
                "inferred": [],
                "clarify": False,
                "clarification_fields": [],
                "unsupported_requirements": [],
            },
            "tags": ["synthetic"],
        },
        {
            "id": "train-create",
            "split": "train",
            "source_type": "human_seed",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "prompt": "make another calc",
            "expected": {
                "features": ["add"],
                "artifacts": ["cli"],
                "interfaces": ["cli"],
                "clarify": False,
            },
        },
    ]

    report = validate_prompt_corpus_rows(rows)

    assert report["status"] == "invalid"
    issue_names = {
        issue["issue"]
        for issue in report["issues"]  # type: ignore[union-attr]
    }
    assert {
        "unsupported_scalar_label",
        "invalid_type",
        "synthetic_generation_metadata_missing",
        "prompt_family_missing",
        "missing_required_field",
        "duplicate_id",
    }.issubset(issue_names)


def test_prompt_corpus_validation_warns_for_review_duplicates() -> None:
    rows = [
        {
            "id": "train-create",
            "split": "train",
            "source_type": "human_seed",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "prompt": "Make me a simple CLI calc",
            "expected": {
                "features": ["add"],
                "artifacts": ["cli"],
                "interfaces": ["cli"],
                "clarify": False,
            },
            "tags": ["greenfield"],
        },
        {
            "id": "test-create",
            "split": "test",
            "source_type": "human_seed",
            "task_type": "create_app",
            "repo_mode": "new_repo",
            "domain": "calculator",
            "prompt": "make me a simple cli calculator",
            "expected": {
                "features": ["add"],
                "artifacts": ["cli"],
                "interfaces": ["cli"],
                "clarify": False,
            },
            "tags": ["greenfield"],
        },
    ]

    report = validate_prompt_corpus_rows(rows)

    assert report["status"] == "valid_with_warnings"
    assert report["error_count"] == 0
    warnings = [
        issue
        for issue in report["issues"]  # type: ignore[union-attr]
        if issue["severity"] == "warning"
    ]
    assert {issue["issue"] for issue in warnings} == {
        "legacy_expected_action_missing",
        "near_duplicate_prompt_cross_split_review",
    }

    strict_report = validate_prompt_corpus_rows(rows, fail_on_review=True)
    assert strict_report["status"] == "invalid"
    assert strict_report["error_count"] == 1


def test_prompt_corpus_validation_accepts_current_label_files() -> None:
    paths = [GREENSHOT_7_INTENTS]
    if SEED_CORPUS.exists():
        paths.append(SEED_CORPUS)
    if EXPANDED_CORPUS.exists():
        paths.append(EXPANDED_CORPUS)

    reports = {path: validate_prompt_corpus(path) for path in paths}

    assert {
        str(path): report["error_count"]
        for path, report in reports.items()
    } == {str(path): 0 for path in paths}
    assert reports[GREENSHOT_7_INTENTS]["status"] == "valid_with_warnings"


def test_prompt_intent_eval_scores_future_predictors() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    perfect = evaluate_prompt_intent_predictions(records, lambda record: record.target)
    perfect_record = perfect.to_record()

    assert perfect_record["exact_accuracy"] == 1.0
    assert perfect_record["mismatches"] == []
    assert all(
        field["accuracy"] == 1.0
        for field in perfect_record["field_accuracy"].values()  # type: ignore[union-attr]
    )

    def misses_action(record):
        if record.row_id == "gs7-intent-0004":
            return {
                **record.target.to_record(),
                "expected_action": "emit_request_spec",
                "requested_interfaces": [],
            }
        return record.target

    result = evaluate_prompt_intent_predictions(records, misses_action).to_record()
    assert result["exact_matches"] == len(records) - 1
    assert result["field_accuracy"]["expected_action"]["correct"] == len(records) - 1  # type: ignore[index]
    assert result["field_accuracy"]["requested_interfaces"]["correct"] == len(records) - 1  # type: ignore[index]
    assert result["mismatches"][0]["id"] == "gs7-intent-0004"  # type: ignore[index]


def test_local_fixture_trains_unsupported_requirement_target() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    result = train_prompt_intent_token_baseline(
        records,
        target_field="unsupported_requirement",
    )

    assert result.model.labels == (
        "desktop_interface",
        "domain_unspecified",
        "graphical_interface",
        "graphing_feature_unspecified",
        "none",
        "scientific_operations_unspecified",
        "ui_interface",
        "visual_interface_scope",
        "web_interface",
    )
    assert result.model.feature_schema == PROMPT_FEATURE_SCHEMA_VERSION
    assert result.metrics["validation"].accuracy == 1.0
    assert (
        result.metrics["validation"].accuracy
        > result.metrics["validation"].baseline_accuracy
    )
    assert result.metrics["test"].accuracy >= 16 / 18
    assert result.metrics["test"].accuracy > result.metrics["test"].baseline_accuracy
    assert result.metrics["validation"].residuals == ()
    assert [residual.row_id for residual in result.metrics["test"].residuals] == [
        "gs7-intent-0025",
        "gs7-intent-0047",
    ]
    previous_interface_residual_ids = {
        "gs7-intent-0020",
        "gs7-intent-0041",
        "gs7-intent-0035",
    }
    residual_ids = {
        residual.row_id
        for metrics in result.metrics.values()
        for residual in metrics.residuals
    }
    assert previous_interface_residual_ids.isdisjoint(residual_ids)
    critical_graphical_holdout_ids = {
        "gs7-intent-0004",
        "gs7-intent-0005",
        "gs7-intent-0006",
        "gs7-intent-0024",
    }
    assert critical_graphical_holdout_ids.isdisjoint(residual_ids)
    assert result.decision == "evaluation_only_not_wired_to_production"


def test_graphing_calculator_labels_are_feature_scope_not_interface_by_default() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)
    by_id = {record.row_id: record for record in records}

    scientific_graphing = by_id["gs7-intent-0025"]
    assert scientific_graphing.target.unsupported_requirement == (
        "graphing_feature_unspecified"
    )
    assert scientific_graphing.target.unsupported_requirement_family == "feature_scope"
    assert scientific_graphing.target.requested_interfaces == ()
    assert scientific_graphing.target.unsupported_requirements == (
        "graphing_feature_unspecified",
        "scientific_operations_unspecified",
    )

    graphing_splits = {
        record.split
        for record in records
        if record.target.unsupported_requirement == "graphing_feature_unspecified"
    }
    assert graphing_splits == {"train", "validation", "test"}

    plotting_screen = by_id["gs7-intent-0071"]
    assert plotting_screen.target.unsupported_requirement == "graphical_interface"
    assert plotting_screen.target.unsupported_requirement_family == "interface"
    assert plotting_screen.target.unsupported_requirements == (
        "graphical_interface",
        "graphing_feature_unspecified",
    )


def test_prompt_feature_extraction_includes_morphology_and_skip_bigrams() -> None:
    features = _prompt_token_features("Create calculator with graphical interface")

    assert features["tok=graphical"] == 1
    assert features["bigram=graphical interface"] == 1
    assert features["char4=grap"] == 1
    assert features["char5=ical "] == 1
    assert features["skip2=calculator graphical"] == 1
    assert features["skip3=calculator interface"] == 1


def test_local_fixture_trains_unsupported_requirement_family_target() -> None:
    records = load_prompt_intent_records(GREENSHOT_7_INTENTS)

    result = train_prompt_intent_token_baseline(
        records,
        target_field="unsupported_requirement_family",
    )

    assert result.model.labels == ("domain", "feature_scope", "interface", "none")
    assert result.metrics["train"].accuracy == 1.0
    assert result.metrics["validation"].accuracy == 1.0
    assert result.metrics["test"].accuracy == 1.0
    assert result.metrics["validation"].residuals == ()
    assert result.metrics["test"].residuals == ()
    assert result.decision == "evaluation_only_not_wired_to_production"


def test_fixture_backed_prompt_intent_prediction_is_exact_boundary() -> None:
    prediction = predict_prompt_intent("make me a complex graphic calc app")

    assert prediction is not None
    assert prediction.source == "prompt_intent_fixture_exact_match"
    assert prediction.record_id == "gs7-intent-0004"
    assert prediction.target.expected_action == "ask_clarification"
    assert prediction.target.unsupported_requirement == "graphical_interface"
    assert prediction.target.requested_interfaces == ("graphic",)
    assert prediction.target.unsupported_requirements == (
        "complex_scope",
        "graphical_interface",
    )

    assert predict_prompt_intent("make me a complex graphic spreadsheet") is None


def test_loads_external_seed_prompt_corpus_profile() -> None:
    if not SEED_CORPUS.exists():
        pytest.skip(f"seed prompt corpus is not available: {SEED_CORPUS}")

    records = load_prompt_intent_records(SEED_CORPUS)
    profile = profile_prompt_intents(records)

    assert profile["total"] >= 80
    assert profile["split_counts"]["train"] > 0  # type: ignore[index]
    assert profile["split_counts"]["validation"] > 0  # type: ignore[index]
    assert profile["split_counts"]["test"] > 0  # type: ignore[index]
    assert profile["repo_mode_counts"]["existing_repo"] > 0  # type: ignore[index]
    assert profile["repo_mode_counts"]["new_repo"] > 0  # type: ignore[index]
    assert profile["artifact_counts"]["module"] > 0  # type: ignore[index]
    assert profile["artifact_counts"]["pyproject"] > 0  # type: ignore[index]
    assert profile["requires_clarification_counts"] == {"no": 72, "yes": 8}
    assert profile["unsupported_requirement_counts"] == {"none": len(records)}
    assert profile["unsupported_requirement_family_counts"] == {"none": len(records)}
    assert profile["primary_artifact_counts"]["pyproject"] == 4  # type: ignore[index]
    assert profile["primary_artifact_counts"]["package"] == 1  # type: ignore[index]
    assert profile["primary_artifact_counts"]["ci_config"] == 1  # type: ignore[index]
    assert profile["missing_artifact_label_count"] == 8
    assert profile["clarification_count"] > 0
    assert profile["existing_repo_change_count"] > 0


def test_inspects_expanded_prompt_corpus_when_available() -> None:
    if not EXPANDED_CORPUS.exists():
        pytest.skip(f"expanded prompt corpus is not available: {EXPANDED_CORPUS}")

    profile = profile_prompt_corpus_rows(
        [
            json.loads(line)
            for line in EXPANDED_CORPUS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ],
        labels_path=EXPANDED_CORPUS,
    )

    assert profile["total_rows"] == 320
    assert profile["source_type_counts"] == {
        "human_seed": 80,
        "synthetic_template_v0": 240,
    }
    assert profile["duplicate_normalized_prompt_count"] == 0
    assert profile["unsupported_scalar_label_count"] == 0
    assert profile["near_duplicate_cross_split_prompt_count"] >= 1


def test_prompt_intent_loader_validates_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        (
            '{"id":"missing-prompt","split":"train","source_type":"test",'
            '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator"}\n'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="prompt"):
        load_prompt_intent_records(path)


def test_trains_token_baseline_only_from_train_split(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    path.write_text(
        "\n".join(
            [
                (
                    '{"id":"train-create-1","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator",'
                    '"prompt":"create a new calculator cli","expected":{"action":"emit_request_spec"}}'
                ),
                (
                    '{"id":"train-create-2","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"timer",'
                    '"prompt":"build a fresh timer cli","expected":{"action":"emit_request_spec"}}'
                ),
                (
                    '{"id":"train-change-1","split":"train","source_type":"test",'
                    '"task_type":"add_feature","repo_mode":"existing_repo","domain":"calculator",'
                    '"prompt":"change the existing calculator","expected":'
                    '{"action":"emit_existing_repo_change_spec"}}'
                ),
                (
                    '{"id":"train-change-2","split":"train","source_type":"test",'
                    '"task_type":"bugfix","repo_mode":"existing_repo","domain":"parser",'
                    '"prompt":"fix an existing parser bug","expected":'
                    '{"action":"emit_existing_repo_change_spec"}}'
                ),
                (
                    '{"id":"validation-unseen","split":"validation","source_type":"test",'
                    '"task_type":"clarify","repo_mode":"unknown","domain":"math",'
                    '"prompt":"validation only vague math thing","expected":'
                    '{"action":"ask_clarification"}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = load_prompt_intent_records(path)
    result = train_prompt_intent_token_baseline(
        records,
        target_field="expected_action",
        eval_splits=("train", "validation"),
    )

    assert result.train_rows == 4
    assert result.decision == "evaluation_only_not_wired_to_production"
    assert result.majority_label == "emit_existing_repo_change_spec"
    assert result.model.labels == (
        "emit_existing_repo_change_spec",
        "emit_request_spec",
    )
    assert "ask_clarification" not in result.model.labels
    assert result.metrics["train"].accuracy == 1.0
    assert result.metrics["validation"].total == 1
    assert result.metrics["validation"].correct == 0
    assert result.metrics["validation"].residuals[0].to_record() == {
        "target_field": "expected_action",
        "id": "validation-unseen",
        "split": "validation",
        "source_type": "test",
        "prompt": "validation only vague math thing",
        "expected": "ask_clarification",
        "predicted": "emit_existing_repo_change_spec",
        "baseline_label": "emit_existing_repo_change_spec",
        "baseline_correct": False,
        "tags": [],
        "target_context": {
            "repo_mode": "unknown",
            "task_type": "clarify",
            "domain": "math",
            "expected_action": "ask_clarification",
            "requires_clarification": "yes",
            "primary_artifact": "none",
            "unsupported_requirement": "none",
            "unsupported_requirement_family": "none",
            "artifacts": [],
            "unsupported_requirements": [],
            "clarification_fields": [],
        },
    }


def test_seed_corpus_learned_baseline_reports_held_out_metrics() -> None:
    if not SEED_CORPUS.exists():
        pytest.skip(f"seed prompt corpus is not available: {SEED_CORPUS}")

    records = load_prompt_intent_records(SEED_CORPUS)

    expected_action = train_prompt_intent_token_baseline(
        records,
        target_field="expected_action",
    )
    repo_mode = train_prompt_intent_token_baseline(
        records,
        target_field="repo_mode",
    )
    requires_clarification = train_prompt_intent_token_baseline(
        records,
        target_field="requires_clarification",
    )
    primary_artifact = train_prompt_intent_token_baseline(
        records,
        target_field="primary_artifact",
    )

    assert expected_action.metrics["validation"].accuracy >= 0.66
    assert expected_action.metrics["test"].accuracy >= 0.75
    assert (
        expected_action.metrics["validation"].accuracy
        > expected_action.metrics["validation"].baseline_accuracy
    )
    assert (
        expected_action.metrics["test"].accuracy
        > expected_action.metrics["test"].baseline_accuracy
    )
    assert repo_mode.metrics["validation"].accuracy >= 0.86
    assert repo_mode.metrics["test"].accuracy >= 0.91
    assert (
        repo_mode.metrics["validation"].accuracy
        > repo_mode.metrics["validation"].baseline_accuracy
    )
    assert repo_mode.metrics["test"].accuracy > repo_mode.metrics["test"].baseline_accuracy
    assert [residual.row_id for residual in expected_action.metrics["validation"].residuals] == [
        "seed-0015",
        "seed-0059",
        "seed-0074",
        "seed-0078",
    ]
    assert [residual.row_id for residual in expected_action.metrics["test"].residuals] == [
        "seed-0065",
        "seed-0076",
    ]
    assert [residual.row_id for residual in repo_mode.metrics["validation"].residuals] == [
        "seed-0015",
        "seed-0059",
    ]
    assert [residual.row_id for residual in repo_mode.metrics["test"].residuals] == [
        "seed-0065",
    ]
    assert requires_clarification.metrics["validation"].accuracy >= 0.86
    assert requires_clarification.metrics["test"].accuracy >= 0.83
    assert [
        residual.row_id
        for residual in requires_clarification.metrics["validation"].residuals
    ] == ["seed-0074", "seed-0078"]
    assert [residual.row_id for residual in requires_clarification.metrics["test"].residuals] == [
        "seed-0076",
        "seed-0080",
    ]
    assert primary_artifact.metrics["validation"].accuracy >= 0.46
    assert primary_artifact.metrics["test"].accuracy >= 0.58
    assert (
        primary_artifact.metrics["validation"].accuracy
        > primary_artifact.metrics["validation"].baseline_accuracy
    )
    assert (
        primary_artifact.metrics["test"].accuracy
        > primary_artifact.metrics["test"].baseline_accuracy
    )
    artifact_validation_misses = [
        residual.row_id for residual in primary_artifact.metrics["validation"].residuals
    ]
    artifact_test_misses = [
        residual.row_id for residual in primary_artifact.metrics["test"].residuals
    ]
    assert "seed-0067" in artifact_validation_misses
    assert "seed-0065" in artifact_test_misses
    pyproject_residuals = [
        residual
        for residual in primary_artifact.metrics["test"].residuals
        if residual.row_id == "seed-0065"
    ]
    assert pyproject_residuals[0].target_context["primary_artifact"] == "pyproject"
    assert expected_action.decision == "evaluation_only_not_wired_to_production"
    assert repo_mode.decision == "evaluation_only_not_wired_to_production"
    assert requires_clarification.decision == "evaluation_only_not_wired_to_production"
    assert primary_artifact.decision == "evaluation_only_not_wired_to_production"
