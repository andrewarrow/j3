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
    assert f"ranker: {out_dir.resolve() / 'candidate-ranker.json'}" in output
    assert (out_dir / "candidate-ranker.json").exists()
    assert (out_dir / "candidate-ranker-metrics.json").exists()


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
