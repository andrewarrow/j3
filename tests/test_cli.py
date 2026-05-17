from __future__ import annotations

import json
import shutil

import pytest

from cli import main


def _jsonl_rows(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_help_menu_prints_project_summary(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "local-first JEPA coding agent" in output
    assert "implement" in output
    assert "greenshot-7" in output
    assert "patch" in output
    assert "fix" in output
    assert "train" in output
    assert "train-ranker" in output
    assert "outcome-summary" in output
    assert "compare-diagnostics" in output
    assert "eval" in output


def test_actions_command_lists_structured_actions(capsys) -> None:
    assert main(["actions"]) == 0

    output = capsys.readouterr().out
    assert "change_operator" in output
    assert "modify_condition" in output


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
