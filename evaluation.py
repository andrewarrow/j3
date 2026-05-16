"""Evaluation harness for j3 repair tasks."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from patching import CandidatePatch, PatchPlanResult, plan_and_maybe_apply_patch


@dataclass(frozen=True, slots=True)
class RepairTask:
    name: str
    repo: Path
    test_command: str


@dataclass(frozen=True, slots=True)
class TaskEvalResult:
    task: RepairTask
    baseline: PatchPlanResult
    ranked: PatchPlanResult

    @property
    def baseline_solved(self) -> bool:
        return self.baseline.selected is not None

    @property
    def ranked_solved(self) -> bool:
        return self.ranked.selected is not None


@dataclass(frozen=True, slots=True)
class EvalSummary:
    tasks: list[TaskEvalResult]

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def baseline_solved(self) -> int:
        return sum(1 for task in self.tasks if task.baseline_solved)

    @property
    def ranked_solved(self) -> int:
        return sum(1 for task in self.tasks if task.ranked_solved)

    @property
    def baseline_pass_at_1(self) -> int:
        return sum(
            1
            for task in self.tasks
            if task.baseline_solved and task.baseline.candidates_tested == 1
        )

    @property
    def ranked_pass_at_1(self) -> int:
        return sum(
            1
            for task in self.tasks
            if task.ranked_solved and task.ranked.candidates_tested == 1
        )

    @property
    def baseline_avg_candidates_tested(self) -> float:
        return _average([task.baseline.candidates_tested for task in self.tasks])

    @property
    def ranked_avg_candidates_tested(self) -> float:
        return _average([task.ranked.candidates_tested for task in self.tasks])


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
            )
        )
    return tasks


def evaluate_tasks(
    *,
    tasks_path: Path,
    model_path: Path | None,
    timeout_seconds: int = 30,
    max_candidates: int = 80,
) -> EvalSummary:
    tasks = load_tasks(tasks_path)
    results = [
        TaskEvalResult(
            task=task,
            baseline=_run_task(
                task=task,
                model_path=None,
                use_failure_hints=False,
                timeout_seconds=timeout_seconds,
                max_candidates=max_candidates,
            ),
            ranked=_run_task(
                task=task,
                model_path=model_path,
                use_failure_hints=True,
                timeout_seconds=timeout_seconds,
                max_candidates=max_candidates,
            ),
        )
        for task in tasks
    ]
    return EvalSummary(tasks=results)


def write_eval_diagnostics(summary: EvalSummary, path: Path) -> Path:
    """Write per-task candidate diagnostics for later ranking analysis."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tasks": [
            {
                "name": result.task.name,
                "repo": str(result.task.repo),
                "test_command": result.task.test_command,
                "baseline": _plan_diagnostics(result.baseline),
                "ranked": _plan_diagnostics(result.ranked),
            }
            for result in summary.tasks
        ]
    }
    resolved.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return resolved


def _run_task(
    *,
    task: RepairTask,
    model_path: Path | None,
    use_failure_hints: bool,
    timeout_seconds: int,
    max_candidates: int,
) -> PatchPlanResult:
    with tempfile.TemporaryDirectory(prefix="j3-eval-") as tmp:
        tmp_repo = Path(tmp) / task.repo.name
        shutil.copytree(task.repo, tmp_repo)
        return plan_and_maybe_apply_patch(
            repo=tmp_repo,
            test_command=task.test_command,
            dry_run=False,
            timeout_seconds=timeout_seconds,
            max_candidates=max_candidates,
            model_path=model_path,
            use_failure_hints=use_failure_hints,
        )


def _average(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _plan_diagnostics(plan: PatchPlanResult) -> dict[str, object]:
    return {
        "baseline_exit_code": plan.baseline_exit_code,
        "candidates_generated": plan.candidates_generated,
        "candidates_tested": plan.candidates_tested,
        "applied": plan.applied,
        "selected": _candidate_diagnostics(plan.selected, passed=True) if plan.selected else None,
        "tested_candidates": [
            _candidate_diagnostics(candidate, passed=candidate == plan.selected)
            for candidate in plan.tested_candidates
        ],
    }


def _candidate_diagnostics(candidate: CandidatePatch, *, passed: bool) -> dict[str, object]:
    return {
        "file_path": candidate.file_path,
        "action": candidate.action.kind.value,
        "symbol": candidate.action.target.symbol,
        "start_line": candidate.action.target.start_line,
        "end_line": candidate.action.target.end_line,
        "reason": candidate.reason,
        "model_score": candidate.model_score,
        "failure_hint_score": candidate.failure_hint_score,
        "passed": passed,
    }
