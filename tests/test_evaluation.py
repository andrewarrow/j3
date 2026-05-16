from __future__ import annotations

from pathlib import Path

import json

from actions import PatchAction, PatchActionKind, PatchTarget
from evaluation import (
    EvalSummary,
    RepairTask,
    TaskEvalResult,
    evaluate_tasks,
    load_tasks,
    write_candidate_outcomes,
    write_eval_diagnostics,
)
from patching import CandidatePatch, PatchPlanResult
from synth import SourceEdit
from training import train_from_path


def test_load_tasks_from_directory() -> None:
    tasks = load_tasks(Path("examples/greenshot_bugs"))

    assert len(tasks) == 5
    assert tasks[0].name == "discount_return_expr"


def test_load_greenshot_4_tasks() -> None:
    tasks = load_tasks(Path("examples/greenshot_4"))

    assert len(tasks) == 27
    assert tasks[0].name == "discount_remaining_price"
    assert tasks[-1].name == "parse_port_try_except"


def test_load_greenshot_5_tasks() -> None:
    tasks = load_tasks(Path("examples/greenshot_5"))

    assert len(tasks) == 8
    assert tasks[0].name == "quote_total_helper_discount"
    assert tasks[-1].name == "loyalty_points_wrapper_exception_handler"


def test_evaluate_greenshot_bugs(tmp_path) -> None:
    training = train_from_path(
        data_path=Path("examples/greenshot_bugs"),
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=80,
    )

    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_bugs"),
        model_path=training.model_path,
        timeout_seconds=10,
    )

    assert summary.total == 5
    assert summary.ranked_solved >= 4


def test_evaluate_greenshot_3() -> None:
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_3"),
        model_path=None,
        timeout_seconds=10,
    )

    assert summary.total == 4
    assert summary.ranked_solved == 4
    assert summary.ranked_pass_at_1 == 4


def test_write_eval_diagnostics(tmp_path) -> None:
    training = train_from_path(
        data_path=Path("examples/greenshot_bugs"),
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=80,
    )
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_bugs"),
        model_path=training.model_path,
        timeout_seconds=10,
        max_candidates=5,
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))

    assert payload["tasks"]
    assert "summary" in payload
    assert "ranker_paths" in payload["summary"]["ranked"]
    assert "ranker_scores_present" in payload["summary"]["ranked"]
    assert "per_action" in payload["summary"]["ranked"]
    assert "top_failed_candidate_reasons" in payload["summary"]["ranked"]
    assert "failure_modes" in payload["summary"]["ranked"]
    assert "summary" in payload["tasks"][0]["ranked"]
    assert "ranker_path" in payload["tasks"][0]["ranked"]["summary"]
    assert "ranker_scores_present" in payload["tasks"][0]["ranked"]["summary"]
    assert "selected_ranker_score" in payload["tasks"][0]["ranked"]["summary"]
    assert "failure_hints" in payload["tasks"][0]["ranked"]
    assert "tested_candidates" in payload["tasks"][0]["ranked"]
    assert "params" in payload["tasks"][0]["ranked"]["tested_candidates"][0]
    assert "ranker_score" in payload["tasks"][0]["ranked"]["tested_candidates"][0]


def test_write_eval_diagnostics_records_ranker_scores(tmp_path) -> None:
    ranker_path = tmp_path / "candidate-ranker.json"
    selected = _candidate_patch(ranker_score=1.25)
    plan = PatchPlanResult(
        repo=tmp_path,
        test_command="python -m pytest tests/test_bug.py",
        baseline_exit_code=1,
        candidates_generated=1,
        candidates_tested=1,
        selected=selected,
        applied=True,
        test_output="",
        ranker_path=ranker_path,
        tested_candidates=(selected,),
    )
    summary = EvalSummary(
        tasks=[
            TaskEvalResult(
                task=RepairTask(
                    name="ranked",
                    repo=tmp_path,
                    test_command="python -m pytest tests/test_bug.py",
                ),
                baseline=plan,
                ranked=plan,
            )
        ]
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))

    assert payload["summary"]["ranked"]["ranker_paths"] == [str(ranker_path)]
    assert payload["summary"]["ranked"]["ranker_scores_present"] is True
    assert payload["tasks"][0]["ranked"]["summary"]["ranker_path"] == str(ranker_path)
    assert payload["tasks"][0]["ranked"]["summary"]["ranker_scores_present"] is True
    assert payload["tasks"][0]["ranked"]["summary"]["selected_ranker_score"] == 1.25


def test_diagnostics_records_skipped_phase(tmp_path) -> None:
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_3"),
        model_path=None,
        timeout_seconds=10,
        max_candidates=1,
        phase="ranked",
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))

    assert payload["summary"]["baseline"]["skipped"] is True
    assert payload["summary"]["baseline"]["tasks"] == 0
    assert payload["summary"]["baseline"]["skipped_tasks"] == 4
    assert payload["summary"]["ranked"]["skipped"] is False
    assert payload["tasks"][0]["baseline"] == {"skipped": True}
    assert payload["tasks"][0]["ranked"]["skipped"] is False


def test_eval_explores_after_first_passing_candidate(tmp_path) -> None:
    tasks_dir = _write_multi_pass_task(tmp_path)

    summary = evaluate_tasks(
        tasks_path=tasks_dir,
        model_path=None,
        timeout_seconds=10,
        max_candidates=3,
        phase="ranked",
        explore_after_pass=2,
    )

    plan = summary.tasks[0].ranked
    assert plan is not None
    assert plan.selected is not None
    assert plan.first_passing_index == 1
    assert plan.candidates_tested == 3
    assert len(plan.passing_candidates) == 2
    assert summary.ranked_solved == 1
    assert summary.ranked_pass_at_1 == 1


def test_diagnostics_records_exploration_after_pass(tmp_path) -> None:
    tasks_dir = _write_multi_pass_task(tmp_path)
    summary = evaluate_tasks(
        tasks_path=tasks_dir,
        model_path=None,
        timeout_seconds=10,
        max_candidates=3,
        phase="ranked",
        explore_after_pass=2,
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))
    ranked = payload["tasks"][0]["ranked"]

    assert ranked["first_passing_index"] == 1
    assert ranked["candidates_tested_before_pass"] == 0
    assert ranked["candidates_tested_after_pass"] == 2
    assert len(ranked["passing_candidates"]) == 2
    assert [candidate["passed"] for candidate in ranked["tested_candidates"]] == [True, True, False]
    assert ranked["summary"]["first_passing_index"] == 1
    assert ranked["summary"]["passing_candidates"] == 2


def test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate(tmp_path) -> None:
    tasks_dir = _write_multi_pass_task(tmp_path)
    summary = evaluate_tasks(
        tasks_path=tasks_dir,
        model_path=None,
        timeout_seconds=10,
        max_candidates=3,
        phase="ranked",
        explore_after_pass=2,
    )

    outcomes = write_candidate_outcomes(summary, tmp_path / "candidate_outcomes.jsonl")
    rows = [
        json.loads(line)
        for line in outcomes.read_text(encoding="utf-8").splitlines()
    ]

    assert len(rows) == 3
    assert {row["task"] for row in rows} == {"multi_pass_literal"}
    assert {row["phase"] for row in rows} == {"ranked"}
    assert [row["rank_index"] for row in rows] == [1, 2, 3]
    assert [row["passed"] for row in rows] == [True, True, False]
    assert [row["is_first_pass"] for row in rows] == [True, False, False]
    assert all(row["first_passing_index"] == 1 for row in rows)
    assert all(row["passing_candidates"] == 2 for row in rows)
    assert all(row["other_candidates_also_passed"] is True for row in rows)
    assert all("failure_hints" in row for row in rows)
    assert all(isinstance(row["failure_hints"], list) for row in rows)
    assert {
        "file_path",
        "action",
        "params",
        "reason",
        "model_score",
        "failure_hint_score",
        "ranker_score",
    }.issubset(rows[0])


def _candidate_patch(*, ranker_score: float | None) -> CandidatePatch:
    source = "def answer() -> int:\n    return 1\n"
    patched = "def answer() -> int:\n    return 2\n"
    return CandidatePatch(
        file_path="bug.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_LITERAL,
            target=PatchTarget(
                file_path="bug.py",
                start_line=2,
                end_line=2,
                symbol="answer",
                node_kind="Constant",
            ),
            params={"from": 1, "to": 2},
        ),
        edit=SourceEdit(start_line=2, start_col=11, end_line=2, end_col=12, replacement="2"),
        original_source=source,
        patched_source=patched,
        reason="try nearby literal 2",
        ranker_score=ranker_score,
    )


def _write_multi_pass_task(tmp_path) -> Path:
    repo = tmp_path / "multi_pass"
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (repo / "bug.py").write_text(
        "def lucky() -> int:\n"
        "    return 10\n",
        encoding="utf-8",
    )
    (tests / "test_bug.py").write_text(
        "from bug import lucky\n\n"
        "def test_accepts_two_repairs() -> None:\n"
        "    assert 7 < lucky() < 10\n",
        encoding="utf-8",
    )
    (repo / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "name": "multi_pass_literal",
                    "repo": ".",
                    "test": "python -m pytest tests/test_bug.py -q",
                }
            ]
        ),
        encoding="utf-8",
    )
    return repo
