from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from cli import main


def _jsonl_rows(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_prompt_jepa_outcome_rows(path):
    rows = [
        {
            "schema_version": "request-repo-attempt-v1",
            "record_kind": "greenshot_7_request_to_repo_attempt",
            "raw_prompt": "make me a simple cli calc",
            "normalized_request_spec": {
                "schema_version": "request-spec-v1",
                "task_type": "create_app",
                "language": "python",
                "repo_mode": "new_repo",
                "domain": "calculator",
                "prompt": "make me a simple cli calc",
                "artifacts": ["calculator.py", "tests/test_calculator_cli.py"],
                "interfaces": [{"kind": "cli", "style": "argparse"}],
                "features": ["add", "subtract"],
                "operation_aliases": {"add": ["add", "+"], "subtract": ["-"]},
                "clarifications_needed": [],
                "validation": {"commands": ["python -m pytest"], "hidden_cases": True},
            },
            "greenfield_actions": [
                {"kind": "create_file", "target": "calculator.py", "payload": {}},
                {"kind": "add_cli_entrypoint", "target": "calculator.py", "payload": {}},
            ],
            "build_result": {
                "schema_version": "greenfield-build-v1",
                "status": "built",
                "files_written": ["calculator.py", "tests/test_calculator_cli.py"],
            },
            "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            "passed": True,
            "failure_observation": None,
        },
        {
            "schema_version": "existing-repo-change-attempt-v1",
            "record_kind": "greenshot_7_existing_repo_change_attempt",
            "raw_prompt": "add exponent support",
            "existing_repo_change_spec": {
                "schema_version": "existing-repo-change-spec-v1",
                "task_type": "modify_app",
                "repo_mode": "existing_repo",
                "domain": "calculator",
                "prompt": "add exponent support",
                "target_files": ["calculator.py", "tests/test_calculator_cli.py"],
                "features_to_add": ["power"],
                "operation_aliases": {"power": ["power", "pow", "^", "**"]},
                "validation": {"commands": ["python -m pytest"], "hidden_cases": True},
            },
            "existing_repo_actions": [
                {"kind": "inspect_repo", "target": None, "payload": {}},
                {"kind": "add_operator_dispatch", "target": "calculator.py", "payload": {}},
            ],
            "change_result": {
                "schema_version": "existing-repo-change-result-v1",
                "status": "validated",
                "repo_path": "/tmp/calc",
                "files_changed": ["calculator.py", "tests/test_calculator_cli.py"],
            },
            "validation": {"status": "passed", "command": "python -m pytest", "exit_code": 0},
            "passed": True,
            "failure_observation": None,
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_help_menu_prints_project_summary(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "local-first JEPA coding agent" in output
    assert "implement" in output
    assert "change" in output
    assert "greenshot-7" in output
    assert "patch" in output
    assert "fix" in output
    assert "train" in output
    assert "train-prompt-intents" in output
    assert "inspect-prompt-corpus" in output
    assert "demo-prompt-jepa" in output
    assert "build-prompt-jepa-index" in output
    assert "query-prompt-jepa-index" in output
    assert "propose-from-prompt-jepa" in output
    assert "eval-prompt-jepa-index" in output
    assert "train-ranker" in output
    assert "outcome-summary" in output
    assert "compare-diagnostics" in output
    assert "eval" in output


def test_actions_command_lists_structured_actions(capsys) -> None:
    assert main(["actions"]) == 0

    output = capsys.readouterr().out
    assert "change_operator" in output
    assert "modify_condition" in output


def test_train_prompt_intents_command_reports_json_metrics(capsys, tmp_path) -> None:
    labels = tmp_path / "prompt-labels.jsonl"
    labels.write_text(
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
                    '{"id":"test-create","split":"test","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"notes",'
                    '"prompt":"create a fresh notes cli","expected":{"action":"emit_request_spec"}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "train-prompt-intents",
                "--labels",
                str(labels),
                "--target",
                "expected_action",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output[0]["target_field"] == "expected_action"
    assert output[0]["train_rows"] == 4
    assert output[0]["decision"] == "evaluation_only_not_wired_to_production"
    assert output[0]["metrics"]["test"]["accuracy"] == 1.0


def test_train_prompt_intents_command_can_print_residuals(capsys, tmp_path) -> None:
    labels = tmp_path / "prompt-labels.jsonl"
    labels.write_text(
        "\n".join(
            [
                (
                    '{"id":"train-create","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator",'
                    '"prompt":"create a new calculator cli","expected":{"action":"emit_request_spec"}}'
                ),
                (
                    '{"id":"train-change","split":"train","source_type":"test",'
                    '"task_type":"add_feature","repo_mode":"existing_repo","domain":"calculator",'
                    '"prompt":"change the existing calculator","expected":'
                    '{"action":"emit_existing_repo_change_spec"}}'
                ),
                (
                    '{"id":"validation-clarify","split":"validation","source_type":"test",'
                    '"task_type":"clarify","repo_mode":"unknown","domain":"math",'
                    '"prompt":"validation only vague math thing","expected":'
                    '{"action":"ask_clarification"},"tags":["ambiguous","clarification"]}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "train-prompt-intents",
                "--labels",
                str(labels),
                "--target",
                "expected_action",
                "--show-residuals",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "validation residuals: 1" in output
    assert "validation-clarify: expected=ask_clarification predicted=" in output
    assert (
        "context: action=ask_clarification repo_mode=unknown "
        "primary_artifact=none requires_clarification=yes "
        "unsupported_requirement=none unsupported_requirement_family=none"
    ) in output
    assert "prompt: validation only vague math thing" in output
    assert "tags: ambiguous, clarification" in output


def test_train_prompt_intents_command_accepts_derived_targets(capsys, tmp_path) -> None:
    labels = tmp_path / "prompt-labels.jsonl"
    labels.write_text(
        "\n".join(
            [
                (
                    '{"id":"train-cli","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator",'
                    '"prompt":"create a new calculator cli","expected":'
                    '{"action":"emit_request_spec","artifacts":["cli","tests"],'
                    '"clarify":false}}'
                ),
                (
                    '{"id":"train-config","split":"train","source_type":"test",'
                    '"task_type":"config_change","repo_mode":"existing_repo","domain":"lint",'
                    '"prompt":"add ruff config","expected":'
                    '{"action":"emit_existing_repo_change_spec",'
                    '"artifacts":["pyproject"],"clarify":false}}'
                ),
                (
                    '{"id":"train-clarify","split":"train","source_type":"test",'
                    '"task_type":"clarify","repo_mode":"unknown","domain":"quality",'
                    '"prompt":"make it better","expected":'
                    '{"action":"ask_clarification","artifacts":[],'
                    '"clarify":true,"clarification_fields":["goal"]}}'
                ),
                (
                    '{"id":"train-ui","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo","domain":"calculator",'
                    '"prompt":"make a calculator UI","expected":'
                    '{"action":"ask_clarification","artifacts":[],'
                    '"requested_interfaces":["ui"],'
                    '"unsupported_requirements":["ui_interface"],'
                    '"clarify":true,"clarification_fields":["interfaces"]}}'
                ),
                (
                    '{"id":"test-config","split":"test","source_type":"test",'
                    '"task_type":"config_change","repo_mode":"existing_repo","domain":"ci",'
                    '"prompt":"add github actions","expected":'
                    '{"action":"emit_existing_repo_change_spec",'
                    '"artifacts":["ci_config"],"clarify":false}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "train-prompt-intents",
                "--labels",
                str(labels),
                "--target",
                "requires_clarification",
                "primary_artifact",
                "unsupported_requirement",
                "unsupported_requirement_family",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert [result["target_field"] for result in output] == [
        "requires_clarification",
        "primary_artifact",
        "unsupported_requirement",
        "unsupported_requirement_family",
    ]
    assert output[0]["model"]["labels"] == ["no", "yes"]
    assert output[1]["model"]["labels"] == ["cli", "none", "pyproject"]
    assert output[2]["model"]["labels"] == ["none", "ui_interface"]
    assert output[3]["model"]["labels"] == ["interface", "none"]


def test_inspect_prompt_corpus_command_reports_json_profile(capsys, tmp_path) -> None:
    labels = tmp_path / "prompt-labels.jsonl"
    labels.write_text(
        "\n".join(
            [
                (
                    '{"id":"train-create","split":"train","source_type":"human_seed",'
                    '"task_type":"create_app","repo_mode":"new_repo",'
                    '"domain":"calculator","prompt":"make me a simple cli calc",'
                    '"expected":{"action":"emit_request_spec","clarify":false,'
                    '"artifacts":["cli","tests"]},"tags":["family:calc-basic"]}'
                ),
                (
                    '{"id":"test-create","split":"test",'
                    '"source_type":"synthetic_template_v0",'
                    '"task_type":"create_app","repo_mode":"new_repo",'
                    '"domain":"calculator","prompt":"make me a simple cli calc",'
                    '"expected":{"action":"emit_request_spec","clarify":false,'
                    '"artifacts":["cli","tests"]},"tags":[],'
                    '"prompt_family":"calc-basic"}'
                ),
                (
                    '{"id":"bad-row","split":"holdout","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo",'
                    '"domain":"calculator","prompt":"make a calculator",'
                    '"expected":{"action":"ask_clarification","clarify":true}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "inspect-prompt-corpus",
                "--labels",
                str(labels),
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "prompt-corpus-profile-v1"
    assert output["labels"] == str(labels.resolve())
    assert output["total_rows"] == 3
    assert output["split_counts"] == {"holdout": 1, "test": 1, "train": 1}
    assert output["expected_action_counts"] == {
        "ask_clarification": 1,
        "emit_request_spec": 2,
    }
    assert output["clarification_counts"] == {"no": 2, "yes": 1}
    assert output["duplicate_normalized_prompt_count"] == 1
    assert output["near_duplicate_family_leakage_count"] == 1
    assert output["missing_required_field_count"] == 1
    assert output["missing_required_fields"][0]["field"] == "tags"
    assert {
        (issue["field"], issue["value"])
        for issue in output["unsupported_scalar_labels"]
    } >= {("split", "holdout"), ("source_type", "test")}


def test_demo_prompt_jepa_command_writes_local_report(capsys, tmp_path) -> None:
    labels = tmp_path / "prompt-labels.jsonl"
    labels.write_text(
        "\n".join(
            [
                (
                    '{"id":"train-calc","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo",'
                    '"domain":"calculator","prompt":"make me a simple cli calc",'
                    '"expected":{"action":"emit_request_spec","clarify":false,'
                    '"features":["add","subtract","multiply","divide"],'
                    '"artifacts":["cli","tests"],"interfaces":["cli"]},'
                    '"tags":["calculator","cli"]}'
                ),
                (
                    '{"id":"train-spaceship","split":"train","source_type":"test",'
                    '"task_type":"clarify","repo_mode":"new_repo",'
                    '"domain":"calculator",'
                    '"prompt":"make me a complex calc for spaceships",'
                    '"expected":{"action":"ask_clarification","clarify":true,'
                    '"clarification_fields":["feature_scope","operations"],'
                    '"unsupported_requirements":["scientific_operations_unspecified"]},'
                    '"tags":["ambiguous","calculator"]}'
                ),
                (
                    '{"id":"train-power","split":"train","source_type":"test",'
                    '"task_type":"add_feature","repo_mode":"existing_repo",'
                    '"domain":"calculator","prompt":"add exponent support",'
                    '"expected":{"action":"emit_existing_repo_change_spec",'
                    '"clarify":false,"features":["power"],'
                    '"artifacts":["calculator.py","tests"]},'
                    '"tags":["calculator","power"]}'
                ),
                (
                    '{"id":"train-todo","split":"train","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo",'
                    '"domain":"todo_cli",'
                    '"prompt":"build a small todo cli where I can add tasks and mark them done",'
                    '"expected":{"action":"emit_request_spec","clarify":false,'
                    '"features":["add_task","complete_task"],'
                    '"artifacts":["cli","storage","tests"],"interfaces":["cli"]},'
                    '"tags":["todo","cli"]}'
                ),
                (
                    '{"id":"train-auth","split":"train","source_type":"test",'
                    '"task_type":"clarify","repo_mode":"new_repo",'
                    '"domain":"auth","prompt":"add auth",'
                    '"expected":{"action":"ask_clarification","clarify":true,'
                    '"clarification_fields":["domain"],'
                    '"unsupported_requirements":["domain_unspecified"]},'
                    '"tags":["auth","ambiguous"]}'
                ),
                (
                    '{"id":"validation-calc","split":"validation","source_type":"test",'
                    '"task_type":"create_app","repo_mode":"new_repo",'
                    '"domain":"calculator","prompt":"build calculator cli",'
                    '"expected":{"action":"emit_request_spec","clarify":false,'
                    '"features":["add","subtract"],"artifacts":["cli"]},'
                    '"tags":["calculator"]}'
                ),
                (
                    '{"id":"test-power","split":"test","source_type":"test",'
                    '"task_type":"add_feature","repo_mode":"existing_repo",'
                    '"domain":"calculator","prompt":"add power operator",'
                    '"expected":{"action":"emit_existing_repo_change_spec",'
                    '"clarify":false,"features":["power"],"artifacts":["tests"]},'
                    '"tags":["calculator","power"]}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "demo"

    assert (
        main(
            [
                "demo-prompt-jepa",
                "--labels",
                str(labels),
                "--out",
                str(out_dir),
                "--top-k",
                "3",
                "--embedding-dim",
                "64",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    source_sidecar = json.loads(
        (out_dir / "source-embeddings.json").read_text(encoding="utf-8")
    )
    outcome_rows = _jsonl_rows(out_dir / "outcomes.jsonl")
    transition_rows = _jsonl_rows(out_dir / "transitions.jsonl")

    assert "j3 demo-prompt-jepa complete" in output
    assert "hosted_llm_api_tokens: 0" in output
    assert "hosted_repo_context_bytes: 0" in output
    assert report["schema_version"] == "prompt-jepa-demo-report-v1"
    assert report["decision"] == "demo_only_retrieval_not_wired_to_production"
    assert report["top_k"] == 3
    assert report["embedding_dim"] == 64
    assert report["hosted_llm_api_tokens"] == 0
    assert report["hosted_repo_context_bytes"] == 0
    assert report["corpus"]["rows"] == 7
    assert report["indexes"]["labels_index_rows"] == 7
    assert report["indexes"]["mixed_index_rows"] == 10
    assert (out_dir / "index.json").exists()
    assert (out_dir / "labels-index.json").exists()
    assert (out_dir / "transitions.jsonl").exists()
    source_embeddings = report["source_embeddings"]
    assert source_embeddings["schema_version"] == (
        "prompt-jepa-demo-source-embeddings-v1"
    )
    assert source_embeddings["artifact"] == str(out_dir / "source-embeddings.json")
    assert source_embeddings["embedding_feature_version"] == "ast-hash-v1"
    assert source_embeddings["embedding_dim"] == 64
    assert source_embeddings["embedding_lengths"] == [64]
    assert source_embeddings["repo_count"] == 1
    assert source_embeddings["file_count"] == 2
    assert source_embeddings["python_source_bytes"] > 0
    assert len(source_embeddings["source_sha256"]) == 64
    assert source_sidecar["schema_version"] == (
        "prompt-jepa-demo-source-embeddings-v1"
    )
    assert source_sidecar["embedding_feature_version"] == "ast-hash-v1"
    assert source_sidecar["embedding_dim"] == 64
    assert source_sidecar["file_count"] == source_embeddings["file_count"]
    assert source_sidecar["source_sha256"] == source_embeddings["source_sha256"]
    assert {file["path"] for file in source_sidecar["files"]} == {
        "repos/simple-calc/calculator.py",
        "repos/simple-calc/tests/test_calculator_cli.py",
    }
    assert all(file["embedding_length"] == 64 for file in source_sidecar["files"])
    assert all(len(file["embedding"]) == 64 for file in source_sidecar["files"])
    assert all(file["bytes"] > 0 for file in source_sidecar["files"])
    assert all(len(file["sha256"]) == 64 for file in source_sidecar["files"])
    assert [row["record_kind"] for row in outcome_rows] == [
        "greenshot_7_request_to_repo_attempt",
        "greenshot_7_request_to_repo_attempt",
        "greenshot_7_existing_repo_change_attempt",
    ]
    assert [row["passed"] for row in outcome_rows] == [True, False, True]
    assert [row["schema_version"] for row in transition_rows] == [
        "prompt-repo-transition-v1",
        "prompt-repo-transition-v1",
        "prompt-repo-transition-v1",
    ]
    assert [row["outcome"]["kind"] for row in transition_rows] == [
        "source_changed",
        "blocked_no_change",
        "source_changed",
    ]
    assert transition_rows[0]["repo_before"]["state"]["included_python_file_paths"] == []
    assert transition_rows[0]["repo_after"]["state"]["included_python_file_paths"] == [
        "calculator.py",
        "tests/test_calculator_cli.py",
    ]
    assert transition_rows[1]["repo_after"]["state_checksum"] == (
        transition_rows[1]["repo_before"]["state_checksum"]
    )
    assert report["transitions"]["artifact"] == str(out_dir / "transitions.jsonl")
    assert report["transitions"]["rows"] == 3
    supported = report["generated_calculator_results"]["supported"]
    blocked = report["generated_calculator_results"]["blocked"]
    assert supported[0]["validation"]["status"] == "passed"
    assert supported[1]["validation"]["status"] == "passed"
    assert blocked[0]["status"] == "blocked"
    assert blocked[0]["validation"]["status"] == "not_run"
    behaviors = {
        item["prompt"]: item["behavior"]["category"]
        for item in report["representative_queries"]
    }
    assert behaviors["make me a simple cli calc"] == "supported"
    assert behaviors["add exponent support"] == "supported"
    assert behaviors["add auth"] == "blocked"
    assert behaviors["build a small todo cli where I can add tasks and mark them done"] == (
        "retrieval_only"
    )
    assert all(
        proposal["mode"] == "dry_run" and proposal["applies_changes"] is False
        for proposal in report["dry_run_proposals"]
    )
    assert report["artifact_sizes_bytes"]["index.json"] > 0
    assert report["artifact_sizes_bytes"]["outcomes.jsonl"] > 0
    assert report["artifact_sizes_bytes"]["source-embeddings.json"] > 0
    assert report["artifact_sizes_bytes"]["transitions.jsonl"] > 0


def test_build_prompt_jepa_index_command_writes_index(capsys, tmp_path) -> None:
    labels = "examples/prompt_intents/greenshot_7_intents.jsonl"
    out_path = tmp_path / "prompt-jepa-index.json"

    assert (
        main(
            [
                "build-prompt-jepa-index",
                "--labels",
                labels,
                "--out",
                str(out_path),
                "--embedding-dim",
                "64",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    index_data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "j3 build-prompt-jepa-index complete" in output
    assert "rows: " in output
    assert "embedding dim: 64" in output
    assert f"out: {out_path.resolve()}" in output
    assert index_data["format"] == "j3.prompt-jepa-index.v1"
    assert index_data["embedding_dim"] == 64
    assert len(index_data["rows"]) > 0
    assert index_data["rows"][0]["id"] == "gs7-intent-0001"


def test_build_prompt_jepa_index_command_accepts_outcome_records(
    capsys,
    tmp_path,
) -> None:
    records_path = tmp_path / "records.jsonl"
    out_path = tmp_path / "prompt-jepa-outcome-index.json"
    _write_prompt_jepa_outcome_rows(records_path)

    assert (
        main(
            [
                "build-prompt-jepa-index",
                "--records",
                str(records_path),
                "--out",
                str(out_path),
                "--embedding-dim",
                "64",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    index_data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "j3 build-prompt-jepa-index complete" in output
    assert f"records: {records_path.resolve()}" in output
    assert "rows: 2" in output
    assert "embedding dim: 64" in output
    assert index_data["format"] == "j3.prompt-jepa-index.v1"
    assert index_data["embedding_dim"] == 64
    assert [row["id"] for row in index_data["rows"]] == [
        "request-repo-attempt-0001",
        "existing-repo-change-attempt-0002",
    ]
    assert index_data["rows"][0]["target"]["expected_action"] == "emit_request_spec"
    assert index_data["rows"][1]["target"]["expected_action"] == (
        "emit_existing_repo_change_spec"
    )


def test_prompt_jepa_index_command_queries_real_recorded_outcomes(
    capsys,
    tmp_path,
) -> None:
    repo_path = tmp_path / "calc"
    blocked_path = tmp_path / "graphic"
    records_path = tmp_path / "real-outcomes.jsonl"
    index_path = tmp_path / "real-outcome-index.json"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make me a simple cli calc",
                "--out",
                str(repo_path),
                "--record",
                str(records_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make me a complex graphic calc app",
                "--out",
                str(blocked_path),
                "--record",
                str(records_path),
            ]
        )
        == 1
    )
    capsys.readouterr()

    assert (
        main(
            [
                "change",
                "--repo",
                str(repo_path),
                "--prompt",
                "add exponent support",
                "--record",
                str(records_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    rows = _jsonl_rows(records_path)
    assert [row["record_kind"] for row in rows] == [
        "greenshot_7_request_to_repo_attempt",
        "greenshot_7_request_to_repo_attempt",
        "greenshot_7_existing_repo_change_attempt",
    ]
    assert [row["passed"] for row in rows] == [True, False, True]
    assert rows[1]["build_result"]["status"] == "blocked"

    assert (
        main(
            [
                "build-prompt-jepa-index",
                "--records",
                str(records_path),
                "--out",
                str(index_path),
                "--embedding-dim",
                "128",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert "rows: 3" in output
    assert [row["id"] for row in index_data["rows"]] == [
        "request-repo-attempt-0001",
        "request-repo-attempt-0002",
        "existing-repo-change-attempt-0003",
    ]
    assert index_data["rows"][1]["target"]["outcome_status"] == "blocked"
    assert index_data["rows"][1]["target"]["passed"] is False

    cases = [
        (
            "build a simple command line calculator",
            "request-repo-attempt-0001",
            "emit_request_spec",
        ),
        (
            "add power operator to the calculator",
            "existing-repo-change-attempt-0003",
            "emit_existing_repo_change_spec",
        ),
        (
            "build a graphical calculator app",
            "request-repo-attempt-0002",
            "emit_request_spec",
        ),
    ]
    for prompt, expected_id, expected_action in cases:
        assert (
            main(
                [
                    "query-prompt-jepa-index",
                    "--index",
                    str(index_path),
                    "--prompt",
                    prompt,
                    "--top-k",
                    "3",
                ]
            )
            == 0
        )
        query_output = capsys.readouterr().out
        first_result = next(
            line.strip()
            for line in query_output.splitlines()
            if line.strip().startswith("1. ")
        )
        assert f"id={expected_id}" in first_result
        assert f"expected_action={expected_action}" in first_result
        assert "domain=calculator" in first_result

    proposal_cases = [
        (
            "build a simple command line calculator",
            "request-repo-attempt-0001",
            "greenshot_7_request_to_repo_attempt",
            "built",
            "emit_request_spec",
            "new_repo",
        ),
        (
            "add power operator to the calculator",
            "existing-repo-change-attempt-0003",
            "greenshot_7_existing_repo_change_attempt",
            "validated",
            "emit_existing_repo_change_spec",
            "existing_repo",
        ),
        (
            "build a graphical calculator app",
            "request-repo-attempt-0002",
            "greenshot_7_request_to_repo_attempt",
            "blocked",
            "emit_request_spec",
            "new_repo",
        ),
    ]
    for (
        prompt,
        expected_id,
        expected_kind,
        expected_status,
        expected_action,
        expected_repo_mode,
    ) in proposal_cases:
        assert (
            main(
                [
                    "propose-from-prompt-jepa",
                    "--index",
                    str(index_path),
                    "--prompt",
                    prompt,
                    "--top-k",
                    "3",
                    "--json",
                ]
            )
            == 0
        )
        proposal = json.loads(capsys.readouterr().out)
        assert proposal["schema_version"] == "prompt-jepa-planner-proposal-v1"
        assert proposal["mode"] == "dry_run"
        assert proposal["applies_changes"] is False
        assert proposal["suggested_outcome_kind"] == expected_kind
        assert proposal["suggested_outcome_status"] == expected_status
        assert proposal["confidence"]["clear_nearest"] is True
        assert proposal["top_neighbors"][0]["id"] == expected_id
        assert proposal["suggested_target_summary"]["expected_action"] == expected_action
        assert proposal["suggested_target_summary"]["repo_mode"] == expected_repo_mode
        assert proposal["evidence"]["uses_real_outcome_metadata"] is True

    assert (
        main(
            [
                "propose-from-prompt-jepa",
                "--index",
                str(index_path),
                "--prompt",
                "build a graphical calculator app",
                "--top-k",
                "3",
            ]
        )
        == 0
    )
    proposal_output = capsys.readouterr().out
    assert "j3 propose-from-prompt-jepa complete" in proposal_output
    assert "mode: dry_run" in proposal_output
    assert "applies changes: false" in proposal_output
    assert "record kind: greenshot_7_request_to_repo_attempt" in proposal_output
    assert "status: blocked" in proposal_output
    assert "id=request-repo-attempt-0002" in proposal_output


def test_query_prompt_jepa_index_command_prints_top_rows(capsys, tmp_path) -> None:
    labels = "examples/prompt_intents/greenshot_7_intents.jsonl"
    out_path = tmp_path / "prompt-jepa-index.json"
    assert (
        main(
            [
                "build-prompt-jepa-index",
                "--labels",
                labels,
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "query-prompt-jepa-index",
                "--index",
                str(out_path),
                "--prompt",
                "make me a simple cli calc",
                "--top-k",
                "3",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "j3 query-prompt-jepa-index complete" in output
    assert f"index: {out_path.resolve()}" in output
    assert "prompt: make me a simple cli calc" in output
    assert "top k: 3" in output
    assert "results:" in output
    assert "1. score=" in output
    assert "id=gs7-intent-0001" in output
    assert "split=train" in output
    assert "expected_action=emit_request_spec" in output
    assert "repo_mode=new_repo" in output
    assert "domain=calculator" in output
    assert 'prompt="make me a simple cli calc"' in output


def test_eval_prompt_jepa_index_command_reports_json_metrics(capsys) -> None:
    labels = "examples/prompt_intents/greenshot_7_intents.jsonl"

    assert (
        main(
            [
                "eval-prompt-jepa-index",
                "--labels",
                labels,
                "--embedding-dim",
                "64",
                "--top-k",
                "3",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "prompt-jepa-retrieval-eval-v1"
    assert output["decision"] == "evaluation_only_not_wired_to_production"
    assert output["train_rows"] > 0
    assert output["embedding_dim"] == 64
    assert output["top_k"] == 3
    assert output["fields"] == [
        "expected_action",
        "repo_mode",
        "domain",
        "unsupported_requirement_family",
    ]
    assert set(output["splits"]) == {"validation", "test"}
    validation = output["splits"]["validation"]
    assert validation["total"] > 0
    assert validation["field_metrics"]["expected_action"]["total"] == validation["total"]
    assert (
        validation["field_metrics"]["expected_action"]["top_1_correct"]
        <= validation["field_metrics"]["expected_action"]["top_k_correct"]
    )


def test_eval_prompt_jepa_index_command_reports_predicted_target_metrics(
    capsys,
) -> None:
    labels = "examples/prompt_intents/greenshot_7_intents.jsonl"

    assert (
        main(
            [
                "eval-prompt-jepa-index",
                "--labels",
                labels,
                "--embedding-dim",
                "64",
                "--top-k",
                "3",
                "--mode",
                "predicted-target",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "prompt-jepa-predicted-target-eval-v1"
    assert output["mode"] == "predicted-target"
    assert output["predictor"]["kind"] == "nearest_context_delta"
    assert output["train_rows"] > 0
    assert set(output["splits"]) == {"validation", "test"}
    validation = output["splits"]["validation"]
    assert validation["field_metrics"]["expected_action"]["total"] == validation["total"]


def test_eval_prompt_jepa_index_command_can_print_misses(capsys) -> None:
    labels = "examples/prompt_intents/greenshot_7_intents.jsonl"

    assert (
        main(
            [
                "eval-prompt-jepa-index",
                "--labels",
                labels,
                "--embedding-dim",
                "64",
                "--top-k",
                "3",
                "--show-misses",
                "--miss-limit",
                "2",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "j3 eval-prompt-jepa-index complete" in output
    assert "train rows:" in output
    assert "validation: rows=" in output
    assert "test: rows=" in output
    assert "expected_action: top1=" in output
    assert "unsupported_requirement_family: top1=" in output
    assert "misses:" in output


def test_eval_prompt_jepa_index_command_compares_modes(capsys) -> None:
    labels = "examples/prompt_intents/greenshot_7_intents.jsonl"

    assert (
        main(
            [
                "eval-prompt-jepa-index",
                "--labels",
                labels,
                "--embedding-dim",
                "64",
                "--top-k",
                "3",
                "--mode",
                "compare",
                "--miss-limit",
                "2",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "prompt-jepa-mode-comparison-v1"
    assert output["context_neighbor"]["mode"] == "context-neighbor"
    assert output["predicted_target"]["mode"] == "predicted-target"
    assert output["residual_comparisons"]
    assert {
        item["field"] for item in output["residual_comparisons"]
    } >= {"expected_action", "repo_mode", "domain"}


def test_implement_command_builds_repo_and_request_spec_artifact(capsys, tmp_path) -> None:
    out_dir = tmp_path / "calc"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make me a simple cli calc",
                "--out",
                str(out_dir),
                "--no-validate",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "j3 implement complete" in output
    assert "task type: create_app" in output
    assert "status: built" in output
    assert "features: add, subtract, multiply, divide" in output
    assert "  calculator.py" in output
    assert "  tests/test_calculator_cli.py" in output
    assert "  request-spec.json" in output
    assert "validation: skipped" in output

    assert (out_dir / "calculator.py").exists()
    assert (out_dir / "tests/test_calculator_cli.py").exists()
    request_spec = json.loads(
        (out_dir / "request-spec.json").read_text(encoding="utf-8")
    )
    assert request_spec["schema_version"] == "request-spec-v1"
    assert request_spec["prompt"] == "make me a simple cli calc"
    assert request_spec["features"] == ["add", "subtract", "multiply", "divide"]


def test_implement_command_validates_generated_repo_by_default(capsys, tmp_path) -> None:
    out_dir = tmp_path / "calc"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make cli app to add two numbers",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "validation: passed (python -m pytest tests/test_calculator_cli.py -q)" in output
    assert (out_dir / "request-spec.json").exists()


def test_implement_command_appends_success_record(capsys, tmp_path) -> None:
    out_dir = tmp_path / "calc"
    record_path = tmp_path / "records.jsonl"
    record_path.write_text('{"existing": true}\n', encoding="utf-8")

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make cli app to add two numbers",
                "--out",
                str(out_dir),
                "--record",
                str(record_path),
            ]
        )
        == 0
    )

    capsys.readouterr()
    rows = _jsonl_rows(record_path)
    assert rows[0] == {"existing": True}
    row = rows[1]
    assert row["schema_version"] == "request-repo-attempt-v1"
    assert row["record_kind"] == "greenshot_7_request_to_repo_attempt"
    assert row["raw_prompt"] == "make cli app to add two numbers"
    assert row["output_repo_path"] == str(out_dir.resolve())
    assert row["metadata"]["source"] == "j3 implement"
    assert row["normalized_request_spec"]["schema_version"] == "request-spec-v1"
    assert row["normalized_request_spec"]["features"] == ["add"]
    assert row["inferred_defaults"] == []
    assert row["clarification_decision"] == {
        "status": "not_needed",
        "clarifications_needed": [],
    }
    assert row["greenfield_plan"]["schema_version"] == "greenfield-plan-v1"
    assert row["greenfield_plan"]["status"] == "ready"
    assert [action["kind"] for action in row["greenfield_actions"]] == [
        "create_file",
        "add_import",
        "add_function_def",
        "add_operator_dispatch",
        "add_cli_entrypoint",
        "create_test_file",
        "add_cli_behavior_tests",
    ]
    assert row["build_result"]["status"] == "built"
    assert row["build_result"]["files_written"] == [
        "calculator.py",
        "tests/test_calculator_cli.py",
    ]
    assert row["build_result"]["cli_files_written"] == [
        "calculator.py",
        "tests/test_calculator_cli.py",
        "request-spec.json",
    ]
    assert row["validation"]["status"] == "passed"
    assert row["validation"]["exit_code"] == 0
    assert row["passed"] is True
    assert row["failure_observation"] is None


def test_implement_command_records_skipped_validation(capsys, tmp_path) -> None:
    out_dir = tmp_path / "calc"
    record_path = tmp_path / "records.jsonl"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make me a simple cli calc",
                "--out",
                str(out_dir),
                "--no-validate",
                "--record",
                str(record_path),
            ]
        )
        == 0
    )

    capsys.readouterr()
    row = _jsonl_rows(record_path)[0]
    assert row["normalized_request_spec"]["features"] == [
        "add",
        "subtract",
        "multiply",
        "divide",
    ]
    assert row["inferred_defaults"] == [
        {
            "confidence": 0.84,
            "field": "features",
            "reason": "simple_calculator_default_operations",
            "value": ["add", "subtract", "multiply", "divide"],
        }
    ]
    assert row["build_result"]["status"] == "built"
    assert row["validation"] == {
        "status": "skipped",
        "command": "python -m pytest tests/test_calculator_cli.py -q",
        "exit_code": None,
    }
    assert row["passed"] is True
    assert row["failure_observation"] is None


def test_implement_command_blocks_clarification_without_calculator_files(
    capsys,
    tmp_path,
) -> None:
    out_dir = tmp_path / "blocked"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make a math thing",
                "--out",
                str(out_dir),
            ]
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "j3 implement blocked" in output
    assert "status: blocked" in output
    assert "domain: unknown" in output
    assert "Should this be a basic CLI calculator" in output
    assert not (out_dir / "calculator.py").exists()
    assert not (out_dir / "tests/test_calculator_cli.py").exists()


def test_change_command_adds_power_to_generated_calculator_repo(capsys, tmp_path) -> None:
    out_dir = tmp_path / "calc"
    record_path = tmp_path / "change-records.jsonl"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make me a simple cli calc",
                "--out",
                str(out_dir),
                "--no-validate",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "change",
                "--repo",
                str(out_dir),
                "--prompt",
                "add exponent support",
                "--record",
                str(record_path),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "j3 change complete" in output
    assert "task type: modify_app" in output
    assert "status: validated" in output
    assert "features added: power" in output
    assert "  calculator.py" in output
    assert "  tests/test_calculator_cli.py" in output
    assert "validation: passed (python -m pytest tests/test_calculator_cli.py -q)" in output

    for operator in ["^", "power", "**"]:
        result = subprocess.run(
            [sys.executable, str(out_dir / "calculator.py"), "2", operator, "3"],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "8"

    row = _jsonl_rows(record_path)[0]
    assert row["schema_version"] == "existing-repo-change-attempt-v1"
    assert row["record_kind"] == "greenshot_7_existing_repo_change_attempt"
    assert row["existing_repo_change_spec"]["schema_version"] == (  # type: ignore[index]
        "existing-repo-change-spec-v1"
    )
    assert row["existing_repo_change_spec"]["features_to_add"] == ["power"]  # type: ignore[index]
    assert [action["kind"] for action in row["existing_repo_actions"]] == [  # type: ignore[index]
        "inspect_repo",
        "parse_existing_calculator",
        "add_operator_aliases",
        "add_operator_dispatch",
        "add_cli_behavior_tests",
        "validate",
    ]
    assert row["change_result"]["status"] == "validated"  # type: ignore[index]
    assert row["validation"]["status"] == "passed"  # type: ignore[index]
    assert row["passed"] is True


def test_change_command_rejects_unrelated_repo(capsys, tmp_path) -> None:
    (tmp_path / "calculator.py").write_text("print('not generated')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_calculator_cli.py").write_text("", encoding="utf-8")

    assert (
        main(
            [
                "change",
                "--repo",
                str(tmp_path),
                "--prompt",
                "add exponent support",
            ]
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "j3 change blocked" in output
    assert "status: blocked" in output
    assert "known generated calculator" in output


def test_implement_script_blocks_prompt_intent_graphical_calculator(tmp_path) -> None:
    out_dir = tmp_path / "graphic"

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "implement",
            "--prompt",
            "make me a complex graphic calc app",
            "--out",
            str(out_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "j3 implement blocked" in result.stdout
    assert "status: blocked" in result.stdout
    assert "domain: calculator" in result.stdout
    assert "This slice only supports a Python CLI calculator" in result.stdout
    assert not (out_dir / "calculator.py").exists()
    assert not (out_dir / "tests/test_calculator_cli.py").exists()


def test_implement_command_records_blocked_clarification(capsys, tmp_path) -> None:
    out_dir = tmp_path / "blocked"
    record_path = tmp_path / "records.jsonl"

    assert (
        main(
            [
                "implement",
                "--prompt",
                "make a math thing",
                "--out",
                str(out_dir),
                "--record",
                str(record_path),
            ]
        )
        == 1
    )

    capsys.readouterr()
    row = _jsonl_rows(record_path)[0]
    assert row["raw_prompt"] == "make a math thing"
    assert row["normalized_request_spec"]["domain"] == "unknown"
    assert row["normalized_request_spec"]["features"] == []
    assert row["clarification_decision"]["status"] == "blocked"
    assert row["clarification_decision"]["clarifications_needed"] == [
        {
            "field": "domain",
            "question": (
                "Should this be a basic CLI calculator, and which operations "
                "should it support?"
            ),
        }
    ]
    assert row["greenfield_plan"]["status"] == "blocked"
    assert [action["kind"] for action in row["greenfield_actions"]] == [
        "ask_clarification"
    ]
    assert row["build_result"]["status"] == "blocked"
    assert row["build_result"]["files_written"] == []
    assert row["build_result"]["cli_files_written"] == []
    assert row["validation"] == {
        "status": "not_run",
        "command": None,
        "exit_code": None,
        "reason": "blocked_clarification",
    }
    assert row["passed"] is False
    assert row["failure_observation"]["kind"] == "blocking_clarification"
    assert not (out_dir / "calculator.py").exists()
    assert not (out_dir / "tests/test_calculator_cli.py").exists()


def test_train_ranker_command_prints_artifact_summary(capsys, tmp_path) -> None:
    diagnostics = tmp_path / "diagnostics.json"
    diagnostics.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "boundary",
                        "ranked": {
                            "selected": {"passed": True},
                            "failure_hints": [
                                {
                                    "function_names": ["meets_minimum"],
                                    "source_files": ["bugs.py"],
                                    "assertions": [
                                        {"operator": "is", "actual": False, "expected": True}
                                    ],
                                }
                            ],
                            "tested_candidates": [
                                {
                                    "file_path": "bugs.py",
                                    "action": "change_operator",
                                    "symbol": "meets_minimum",
                                    "params": {"from": ">", "to": "<"},
                                    "reason": "try comparison operator <",
                                    "model_score": 0.5,
                                    "failure_hint_score": 50.0,
                                    "ranker_score": None,
                                    "passed": False,
                                },
                                {
                                    "file_path": "bugs.py",
                                    "action": "change_operator",
                                    "symbol": "meets_minimum",
                                    "params": {"from": ">", "to": ">="},
                                    "reason": "try comparison operator >=",
                                    "model_score": 0.5,
                                    "failure_hint_score": 50.0,
                                    "ranker_score": None,
                                    "passed": True,
                                },
                            ],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "ranker"

    assert main(["train-ranker", "--diagnostics", str(diagnostics), "--out", str(out_dir)]) == 0

    output = capsys.readouterr().out
    assert "j3 train-ranker complete" in output
    assert "training pairs: 1" in output
    assert "training accuracy: 1.000" in output
    assert "margin violations: 0" in output
    assert "calibration brier:" in output
    assert "calibration ece:" in output
    assert f"ranker: {out_dir.resolve() / 'candidate-ranker.json'}" in output
    assert (out_dir / "candidate-ranker.json").exists()
    assert (out_dir / "candidate-ranker-metrics.json").exists()


def test_train_ranker_command_accepts_candidate_outcomes(capsys, tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "boundary",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "start_line": 2,
            "end_line": 2,
            "params": {"from": ">", "to": "<"},
            "reason": "try comparison operator <",
            "model_score": 0.5,
            "failure_hint_score": 50.0,
            "ranker_score": None,
            "passed": False,
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "boundary",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "start_line": 2,
            "end_line": 2,
            "params": {"from": ">", "to": ">="},
            "reason": "try comparison operator >=",
            "model_score": 0.5,
            "failure_hint_score": 50.0,
            "ranker_score": None,
            "passed": True,
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "ranker"

    assert (
        main(
            [
                "train-ranker",
                "--candidate-outcomes",
                str(outcomes),
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "candidate outcomes:" in output
    assert "rows: 2" in output
    assert "passing rows: 1" in output
    assert "failing rows: 1" in output
    assert "tasks: 1" in output
    assert "training pairs: 1" in output
    assert (out_dir / "candidate-ranker.json").exists()


def test_outcome_summary_command_reports_dataset_shape(capsys, tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "boundary",
            "task_family": "operator_boundary",
            "source_type": "mutation",
            "split": "validation",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "params": {"from": ">", "to": "<"},
            "reason": "try comparison operator <",
            "passed": False,
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "boundary",
            "task_family": "operator_boundary",
            "source_type": "mutation",
            "split": "validation",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "params": {"from": ">", "to": ">="},
            "reason": "try comparison operator >=",
            "passed": True,
            "preferred": True,
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
        {
            "task": "metadata",
            "task_family": "package_metadata",
            "source_type": "git_history",
            "split": "test",
            "phase": "ranked",
            "file_path": "pkgmeta/metadata.py",
            "action": "change_dict_value",
            "symbol": "build_metadata",
            "params": {"key": "license", "to": "MIT"},
            "reason": "try dict value MIT",
            "passed": True,
            "rank_index": 1,
            "first_passing_index": 1,
            "is_first_pass": True,
        },
        {
            "task": "baseline_only",
            "task_family": "ignored",
            "source_type": "handcrafted",
            "split": "train",
            "phase": "baseline",
            "action": "change_literal",
            "passed": True,
            "rank_index": 1,
            "is_first_pass": True,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    assert main(["outcome-summary", "--candidate-outcomes", str(outcomes)]) == 0

    output = capsys.readouterr().out
    assert "j3 outcome-summary" in output
    assert f"  {outcomes.resolve()}" in output
    assert "phase: ranked" in output
    assert "rows: 3" in output
    assert "tasks: 2" in output
    assert "plans: 2" in output
    assert "passing rows: 2" in output
    assert "preferred-positive rows: 1" in output
    assert "average candidates per task: 1.50" in output
    assert "operator_boundary: plans=1 rows=2 solved=1/1 pass@1=0/1" in output
    assert "package_metadata: plans=1 rows=1 solved=1/1 pass@1=1/1" in output
    assert "git_history: plans=1 rows=1 solved=1/1 pass@1=1/1" in output
    assert "validation: plans=1 rows=2 solved=1/1 pass@1=0/1" in output
    assert "test: plans=1 rows=1 solved=1/1 pass@1=1/1" in output
    assert "mutation: plans=1 rows=2 solved=1/1 pass@1=0/1" in output
    assert "change_dict_value: rows=1 passing=1" in output
    assert "change_operator: rows=2 passing=1" in output
    assert "baseline_only" not in output


def test_train_ranker_command_accepts_validation_outcomes(capsys, tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    validation = tmp_path / "validation-candidate-outcomes.jsonl"
    rows = [
        {
            "task": "boundary",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "start_line": 2,
            "end_line": 2,
            "params": {"from": ">", "to": "<"},
            "reason": "try comparison operator <",
            "model_score": 0.5,
            "failure_hint_score": 50.0,
            "ranker_score": None,
            "passed": False,
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "boundary",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "start_line": 2,
            "end_line": 2,
            "params": {"from": ">", "to": ">="},
            "reason": "try comparison operator >=",
            "model_score": 0.5,
            "failure_hint_score": 50.0,
            "ranker_score": None,
            "passed": True,
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
    ]
    text = "\n".join(json.dumps(row) for row in rows) + "\n"
    outcomes.write_text(text, encoding="utf-8")
    validation.write_text(text, encoding="utf-8")
    out_dir = tmp_path / "ranker"

    assert (
        main(
            [
                "train-ranker",
                "--candidate-outcomes",
                str(outcomes),
                "--validation-candidate-outcomes",
                str(validation),
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    metrics = json.loads((out_dir / "candidate-ranker-metrics.json").read_text(encoding="utf-8"))
    assert "validation candidate outcomes:" in output
    assert f"  {validation.resolve()}" in output
    assert "validation: plans=1 solved=1/1 pass@1=1/1 positive@1=1/1" in output
    assert metrics["validation"]["pass_at_1"] == 1


def test_train_ranker_command_accepts_holdout_task_family(capsys, tmp_path) -> None:
    outcomes = tmp_path / "candidate-outcomes.jsonl"
    rows = [
        {
            "task": "held_out_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "params": {"from": ">", "to": "<"},
            "reason": "try comparison operator <",
            "model_score": 0.5,
            "failure_hint_score": 50.0,
            "ranker_score": None,
            "passed": False,
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "held_out_boundary",
            "task_family": "operator_boundary",
            "phase": "ranked",
            "file_path": "bugs.py",
            "action": "change_operator",
            "symbol": "meets_minimum",
            "params": {"from": ">", "to": ">="},
            "reason": "try comparison operator >=",
            "model_score": 0.5,
            "failure_hint_score": 50.0,
            "ranker_score": None,
            "passed": True,
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
        {
            "task": "train_attribute",
            "task_family": "attribute_repair",
            "phase": "ranked",
            "file_path": "accounts.py",
            "action": "change_attribute",
            "symbol": "account_balance",
            "params": {"from": "amount_cents", "to": "available_cents"},
            "reason": "try attribute available_cents",
            "model_score": 0.0,
            "failure_hint_score": 20.0,
            "ranker_score": None,
            "passed": False,
            "rank_index": 1,
            "first_passing_index": 2,
            "is_first_pass": False,
        },
        {
            "task": "train_attribute",
            "task_family": "attribute_repair",
            "phase": "ranked",
            "file_path": "accounts.py",
            "action": "change_attribute",
            "symbol": "account_balance",
            "params": {"from": "amount_cents", "to": "balance_cents"},
            "reason": "try attribute balance_cents",
            "model_score": 0.0,
            "failure_hint_score": 20.0,
            "ranker_score": None,
            "passed": True,
            "rank_index": 2,
            "first_passing_index": 2,
            "is_first_pass": True,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "ranker"

    assert (
        main(
            [
                "train-ranker",
                "--candidate-outcomes",
                str(outcomes),
                "--holdout-task-family",
                "operator_boundary",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    metrics = json.loads((out_dir / "candidate-ranker-metrics.json").read_text(encoding="utf-8"))
    assert "holdout task families: operator_boundary" in output
    assert "rows: 2" in output
    assert "validation: plans=1 solved=1/1" in output
    assert metrics["holdout_task_families"] == ["operator_boundary"]
    assert metrics["validation"]["holdout_candidate_outcome_sources"] == [str(outcomes.resolve())]


def test_compare_diagnostics_command_reports_rank_movement(capsys, tmp_path) -> None:
    old = tmp_path / "old-diagnostics.json"
    new = tmp_path / "new-diagnostics.json"
    old.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "boundary",
                        "ranked": {
                            "skipped": False,
                            "first_passing_index": 2,
                            "summary": {
                                "failure_mode": "bad_ranking",
                                "top_failed_candidate_reasons": [
                                    {"reason": "try comparison operator <", "count": 1}
                                ],
                            },
                            "tested_candidates": [
                                {
                                    "reason": "try comparison operator <",
                                    "passed": False,
                                },
                                {
                                    "reason": "try comparison operator >=",
                                    "passed": True,
                                },
                            ],
                        },
                    },
                    {
                        "name": "nested_import",
                        "ranked": {
                            "skipped": False,
                            "first_passing_index": 1,
                            "summary": {
                                "failure_mode": "pass_at_1",
                                "top_failed_candidate_reasons": [],
                            },
                            "tested_candidates": [
                                {
                                    "reason": "add import shop.reports.money",
                                    "passed": True,
                                }
                            ],
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    new.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "boundary",
                        "ranked": {
                            "skipped": False,
                            "first_passing_index": 1,
                            "summary": {
                                "failure_mode": "pass_at_1",
                                "top_failed_candidate_reasons": [
                                    {"reason": "try comparison operator <", "count": 1}
                                ],
                            },
                            "tested_candidates": [
                                {
                                    "reason": "try comparison operator >=",
                                    "passed": True,
                                },
                                {
                                    "reason": "try comparison operator <",
                                    "passed": False,
                                },
                            ],
                        },
                    },
                    {
                        "name": "nested_import",
                        "ranked": {
                            "skipped": False,
                            "first_passing_index": 1,
                            "summary": {
                                "failure_mode": "pass_at_1",
                                "top_failed_candidate_reasons": [],
                            },
                            "tested_candidates": [
                                {
                                    "reason": "add import shop.reports.money",
                                    "passed": True,
                                }
                            ],
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["compare-diagnostics", str(old), str(new)]) == 0

    output = capsys.readouterr().out
    assert "j3 compare-diagnostics" in output
    assert "phase: ranked" in output
    assert "tasks: old=2 new=2 shared=2" in output
    assert "pass@1: 1/2 -> 2/2 (+1)" in output
    assert "bad-ranking: 1 -> 0 (-1)" in output
    assert "boundary: first_pass=2->1 movement=+1" in output
    assert "mode=bad_ranking->pass_at_1 pass@1 gained" in output
    assert "try comparison operator <: 1" in output


def test_patch_command_accepts_repo_and_test(capsys, tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    assert (
        main(
            [
                "patch",
                "--repo",
                str(repo),
                "--test",
                "python -m pytest tests/test_calculator.py",
                "--dry-run",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "j3 patch (dry run)" in output
    assert "pytest tests/test_calculator.py" in output
    assert "status: found passing patch" in output


def test_eval_default_progress_suppresses_candidate_lines(capsys) -> None:
    assert (
        main(
            [
                "eval",
                "--tasks",
                "examples/greenshot_3",
                "--checkpoint",
                "runs/greenshot-1/model.json",
                "--timeout",
                "10",
                "--max-candidates",
                "1",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "[eval] j3 eval starting" in output
    assert "task 1/4 swap_call_args: start" in output
    assert "test: candidate=" not in output
    assert "j3 eval complete" in output


def test_eval_verbose_progress_prints_candidate_lines(capsys) -> None:
    assert (
        main(
            [
                "eval",
                "--tasks",
                "examples/greenshot_3",
                "--checkpoint",
                "runs/greenshot-1/model.json",
                "--timeout",
                "10",
                "--max-candidates",
                "1",
                "--verbose",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "test: candidate=" in output
    assert "j3 eval complete" in output


def test_eval_quiet_suppresses_progress_lines(capsys) -> None:
    assert (
        main(
            [
                "eval",
                "--tasks",
                "examples/greenshot_3",
                "--checkpoint",
                "runs/greenshot-1/model.json",
                "--timeout",
                "10",
                "--max-candidates",
                "1",
                "--quiet",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "[eval]" not in output
    assert "j3 eval complete" in output


def test_eval_ranked_phase_skips_baseline_candidate_testing(capsys) -> None:
    assert (
        main(
            [
                "eval",
                "--tasks",
                "examples/greenshot_3",
                "--checkpoint",
                "runs/greenshot-1/model.json",
                "--timeout",
                "10",
                "--max-candidates",
                "1",
                "--phase",
                "ranked",
                "--verbose",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "baseline skipped" in output
    assert "baseline: skipped" in output
    assert "/baseline: test: candidate=" not in output
    assert "/model: test: candidate=" in output


def test_eval_both_phase_preserves_existing_summary_numbers(capsys) -> None:
    assert (
        main(
            [
                "eval",
                "--tasks",
                "examples/greenshot_3",
                "--checkpoint",
                "runs/greenshot-1/model.json",
                "--timeout",
                "10",
                "--max-candidates",
                "1",
                "--phase",
                "both",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "baseline: solved=1/4 pass@1=1/4 avg_candidates=1.00" in output
    assert "model-ranked: solved=4/4 pass@1=4/4 avg_candidates=1.00" in output
    assert "baseline: skipped" not in output


def test_eval_writes_candidate_outcomes_jsonl(capsys, tmp_path) -> None:
    outcomes = tmp_path / "candidate_outcomes.jsonl"

    assert (
        main(
            [
                "eval",
                "--tasks",
                "examples/greenshot_3",
                "--checkpoint",
                "runs/greenshot-1/model.json",
                "--timeout",
                "10",
                "--max-candidates",
                "1",
                "--candidate-outcomes",
                str(outcomes),
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    rows = [
        json.loads(line)
        for line in outcomes.read_text(encoding="utf-8").splitlines()
    ]

    assert f"candidate outcomes: {outcomes.resolve()}" in output
    assert len(rows) == 4
    assert {row["phase"] for row in rows} == {"ranked"}
    assert all(row["rank_index"] == 1 for row in rows)
    assert all("first_passing_index" in row for row in rows)
