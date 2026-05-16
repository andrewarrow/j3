"""Evaluation task loading and execution."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable

from evaluation.models import EvalPhase, EvalSummary, RepairTask, TaskEvalResult
from patching import PatchPlanResult, plan_and_maybe_apply_patch


def load_tasks(path: Path) -> list[RepairTask]:
    """Load a task manifest from a JSON file or directory containing tasks.json."""

    resolved = path.expanduser().resolve()
    manifest = resolved / "tasks.json" if resolved.is_dir() else resolved
    base_dir = manifest.parent
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    tasks: list[RepairTask] = []
    for item in payload:
        tasks.append(
            RepairTask(
                name=str(item["name"]),
                repo=(base_dir / str(item.get("repo", "."))).resolve(),
                test_command=str(item["test"]),
                family=str(item.get("family", "unclassified")),
                preferred_patch=(
                    dict(item["preferred"])
                    if isinstance(item.get("preferred"), dict)
                    else None
                ),
                max_steps=int(item.get("max_steps", 1)),
            )
        )
    return tasks


def evaluate_tasks(
    *,
    tasks_path: Path,
    model_path: Path | None,
    ranker_path: Path | None = None,
    timeout_seconds: int = 30,
    max_candidates: int = 80,
    max_steps: int = 1,
    phase: EvalPhase = "both",
    explore_after_pass: int = 0,
    progress: Callable[[str], None] | None = None,
) -> EvalSummary:
    if phase not in {"baseline", "ranked", "both"}:
        raise ValueError(f"unsupported eval phase: {phase}")
    if explore_after_pass < 0:
        raise ValueError("explore_after_pass must be >= 0")
    tasks = load_tasks(tasks_path)
    _emit_progress(progress, f"eval: loaded {len(tasks)} task(s) from {tasks_path}")
    results: list[TaskEvalResult] = []
    for index, task in enumerate(tasks, start=1):
        task_started = time.perf_counter()
        _emit_progress(progress, f"task {index}/{len(tasks)} {task.name}: start")
        baseline: PatchPlanResult | None = None
        if phase in {"baseline", "both"}:
            baseline = _run_task(
                task=task,
                phase="baseline",
                model_path=None,
                ranker_path=None,
                use_failure_hints=False,
                timeout_seconds=timeout_seconds,
                max_candidates=max_candidates,
                max_steps=task.max_steps if task.max_steps != 1 else max_steps,
                explore_after_pass=explore_after_pass,
                progress=progress,
            )
            _emit_progress(
                progress,
                "task "
                f"{index}/{len(tasks)} {task.name}: baseline "
                f"solved={baseline.selected is not None} tested={baseline.candidates_tested}",
            )
        else:
            _emit_progress(progress, f"task {index}/{len(tasks)} {task.name}: baseline skipped")

        ranked: PatchPlanResult | None = None
        if phase in {"ranked", "both"}:
            ranked = _run_task(
                task=task,
                phase="model",
                model_path=model_path,
                ranker_path=ranker_path,
                use_failure_hints=True,
                timeout_seconds=timeout_seconds,
                max_candidates=max_candidates,
                max_steps=task.max_steps if task.max_steps != 1 else max_steps,
                explore_after_pass=explore_after_pass,
                progress=progress,
            )
            _emit_progress(
                progress,
                "task "
                f"{index}/{len(tasks)} {task.name}: model "
                f"solved={ranked.selected is not None} tested={ranked.candidates_tested} "
                f"elapsed={time.perf_counter() - task_started:.2f}s",
            )
        else:
            _emit_progress(
                progress,
                "task "
                f"{index}/{len(tasks)} {task.name}: model skipped "
                f"elapsed={time.perf_counter() - task_started:.2f}s",
            )
        results.append(TaskEvalResult(task=task, baseline=baseline, ranked=ranked))
    return EvalSummary(tasks=results)


def _run_task(
    *,
    task: RepairTask,
    phase: str,
    model_path: Path | None,
    ranker_path: Path | None,
    use_failure_hints: bool,
    timeout_seconds: int,
    max_candidates: int,
    max_steps: int,
    explore_after_pass: int,
    progress: Callable[[str], None] | None,
) -> PatchPlanResult:
    with tempfile.TemporaryDirectory(prefix="j3-eval-") as tmp:
        tmp_repo = Path(tmp) / task.repo.name
        shutil.copytree(task.repo, tmp_repo)
        prefix = f"{task.name}/{phase}"
        return plan_and_maybe_apply_patch(
            repo=tmp_repo,
            test_command=task.test_command,
            dry_run=False,
            timeout_seconds=timeout_seconds,
            max_candidates=max_candidates,
            max_steps=max_steps,
            model_path=model_path,
            ranker_path=ranker_path,
            use_failure_hints=use_failure_hints,
            explore_after_pass=explore_after_pass,
            progress=(
                (lambda message: progress(f"{prefix}: {message}"))
                if progress is not None
                else None
            ),
        )


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)
