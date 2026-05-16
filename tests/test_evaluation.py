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

    assert len(tasks) == 4
    assert tasks[0].name == "quote_total_helper_discount"
    assert tasks[-1].name == "profile_signature_propagation"


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
