from __future__ import annotations

from pathlib import Path

import json

from evaluation import evaluate_tasks, load_tasks, write_eval_diagnostics
from training import train_from_path


def test_load_tasks_from_directory() -> None:
    tasks = load_tasks(Path("examples/greenshot_bugs"))

    assert len(tasks) == 5
    assert tasks[0].name == "discount_return_expr"


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
    assert "tested_candidates" in payload["tasks"][0]["ranked"]
