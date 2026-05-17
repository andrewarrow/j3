from __future__ import annotations

import json
import shutil

import pytest

from cli import main


def test_help_menu_prints_project_summary(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "local-first JEPA coding agent" in output
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
