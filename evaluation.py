"""Evaluation harness for j3 repair tasks."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

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
    ranker_path: Path | None = None,
    timeout_seconds: int = 30,
    max_candidates: int = 80,
    progress: Callable[[str], None] | None = None,
) -> EvalSummary:
    tasks = load_tasks(tasks_path)
    _emit_progress(progress, f"eval: loaded {len(tasks)} task(s) from {tasks_path}")
    results: list[TaskEvalResult] = []
    for index, task in enumerate(tasks, start=1):
        task_started = time.perf_counter()
        _emit_progress(progress, f"task {index}/{len(tasks)} {task.name}: start")
        baseline = _run_task(
            task=task,
            phase="baseline",
            model_path=None,
            ranker_path=None,
            use_failure_hints=False,
            timeout_seconds=timeout_seconds,
            max_candidates=max_candidates,
            progress=progress,
        )
        _emit_progress(
            progress,
            "task "
            f"{index}/{len(tasks)} {task.name}: baseline "
            f"solved={baseline.selected is not None} tested={baseline.candidates_tested}",
        )
        ranked = _run_task(
            task=task,
            phase="model",
            model_path=model_path,
            ranker_path=ranker_path,
            use_failure_hints=True,
            timeout_seconds=timeout_seconds,
            max_candidates=max_candidates,
            progress=progress,
        )
        _emit_progress(
            progress,
            "task "
            f"{index}/{len(tasks)} {task.name}: model "
            f"solved={ranked.selected is not None} tested={ranked.candidates_tested} "
            f"elapsed={time.perf_counter() - task_started:.2f}s",
        )
        results.append(TaskEvalResult(task=task, baseline=baseline, ranked=ranked))
    return EvalSummary(tasks=results)


def write_eval_diagnostics(summary: EvalSummary, path: Path) -> Path:
    """Write per-task candidate diagnostics for later ranking analysis."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "baseline": _aggregate_plan_summaries(result.baseline for result in summary.tasks),
            "ranked": _aggregate_plan_summaries(result.ranked for result in summary.tasks),
        },
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
    phase: str,
    model_path: Path | None,
    ranker_path: Path | None,
    use_failure_hints: bool,
    timeout_seconds: int,
    max_candidates: int,
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
            model_path=model_path,
            ranker_path=ranker_path,
            use_failure_hints=use_failure_hints,
            progress=(
                (lambda message: progress(f"{prefix}: {message}"))
                if progress is not None
                else None
            ),
        )


def _average(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _plan_diagnostics(plan: PatchPlanResult) -> dict[str, object]:
    return {
        "baseline_exit_code": plan.baseline_exit_code,
        "candidates_generated": plan.candidates_generated,
        "candidates_tested": plan.candidates_tested,
        "applied": plan.applied,
        "summary": _single_plan_summary(plan),
        "failure_hints": [_failure_hint_diagnostics(hint) for hint in plan.failure_hints],
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
        "params": dict(candidate.action.params),
        "reason": candidate.reason,
        "model_score": candidate.model_score,
        "failure_hint_score": candidate.failure_hint_score,
        "ranker_score": candidate.ranker_score,
        "passed": passed,
    }


def _failure_hint_diagnostics(hint: object) -> dict[str, object]:
    return {
        "nodeid": getattr(hint, "nodeid", None),
        "summary": getattr(hint, "summary", None),
        "exception_type": getattr(hint, "exception_type", None),
        "source_files": sorted(getattr(hint, "source_files", set())),
        "function_names": sorted(getattr(hint, "function_names", set())),
        "missing_names": sorted(getattr(hint, "missing_names", set())),
        "missing_attributes": sorted(getattr(hint, "missing_attributes", set())),
        "missing_modules": sorted(getattr(hint, "missing_modules", set())),
        "missing_keys": sorted(getattr(hint, "missing_keys", set())),
        "type_error_names": sorted(getattr(hint, "type_error_names", set())),
        "assertion_diff_lines": list(getattr(hint, "assertion_diff_lines", [])),
        "assertions": [
            {
                "actual": assertion.actual,
                "operator": assertion.operator,
                "expected": assertion.expected,
                "numeric_delta": assertion.numeric_delta,
            }
            for assertion in getattr(hint, "assertions", [])
        ],
        "traceback_locations": [
            {
                "file_path": location.file_path,
                "line": location.line,
                "exception_type": location.exception_type,
            }
            for location in getattr(hint, "traceback_locations", [])
        ],
        "tool_diagnostics": [
            {
                "tool": diagnostic.tool,
                "file_path": diagnostic.file_path,
                "line": diagnostic.line,
                "message": diagnostic.message,
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "column": diagnostic.column,
            }
            for diagnostic in getattr(hint, "tool_diagnostics", [])
        ],
    }


def _aggregate_plan_summaries(plans: Iterable[PatchPlanResult]) -> dict[str, object]:
    plan_list = list(plans)
    action_stats: defaultdict[str, _ActionSummaryAccumulator] = defaultdict(_ActionSummaryAccumulator)
    failed_reasons: Counter[str] = Counter()
    failure_modes: Counter[str] = Counter()
    ranker_paths = sorted({str(plan.ranker_path) for plan in plan_list if plan.ranker_path is not None})

    for plan in plan_list:
        action = plan.selected.action.kind.value if plan.selected else "unsolved"
        stats = action_stats[action]
        stats.tasks += 1
        stats.candidate_counts.append(plan.candidates_tested)
        if plan.selected is not None:
            stats.solved += 1
            if plan.candidates_tested == 1:
                stats.pass_at_1 += 1

        failed_reasons.update(
            candidate.reason
            for candidate in plan.tested_candidates
            if candidate != plan.selected
        )
        failure_modes[_failure_mode(plan)] += 1

    return {
        "tasks": len(plan_list),
        "ranker_paths": ranker_paths,
        "ranker_scores_present": any(_plan_has_ranker_scores(plan) for plan in plan_list),
        "per_action": {
            action: {
                "tasks": stats.tasks,
                "solved": stats.solved,
                "pass_at_1": stats.pass_at_1,
                "avg_candidates": _average(stats.candidate_counts),
            }
            for action, stats in sorted(action_stats.items())
        },
        "top_failed_candidate_reasons": _top_counter(failed_reasons),
        "failure_modes": dict(sorted(failure_modes.items())),
    }


def _single_plan_summary(plan: PatchPlanResult) -> dict[str, object]:
    failed_reasons = Counter(
        candidate.reason
        for candidate in plan.tested_candidates
        if candidate != plan.selected
    )
    return {
        "failure_mode": _failure_mode(plan),
        "ranker_path": str(plan.ranker_path) if plan.ranker_path is not None else None,
        "ranker_scores_present": _plan_has_ranker_scores(plan),
        "selected_ranker_score": plan.selected.ranker_score if plan.selected else None,
        "top_failed_candidate_reasons": _top_counter(failed_reasons),
    }


def _plan_has_ranker_scores(plan: PatchPlanResult) -> bool:
    return any(candidate.ranker_score is not None for candidate in plan.tested_candidates)


def _failure_mode(plan: PatchPlanResult) -> str:
    if plan.selected is not None:
        if plan.candidates_tested == 1:
            return "pass_at_1"
        return "bad_ranking"
    if plan.candidates_generated == 0:
        return "missing_action"
    if plan.candidates_tested >= plan.candidates_generated:
        return "missing_action"
    return "search_budget_or_bad_ranking"


def _top_counter(counter: Counter[str], limit: int = 10) -> list[dict[str, object]]:
    return [
        {"reason": reason, "count": count}
        for reason, count in counter.most_common(limit)
    ]


@dataclass(slots=True)
class _ActionSummaryAccumulator:
    tasks: int = 0
    solved: int = 0
    pass_at_1: int = 0
    candidate_counts: list[int] = field(default_factory=list)
