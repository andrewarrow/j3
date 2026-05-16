from __future__ import annotations

from pathlib import Path

from evaluation import evaluate_tasks, load_tasks
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
