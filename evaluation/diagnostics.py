"""Evaluation diagnostics and candidate outcome serialization."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ast_delta import python_ast_delta_metadata
from evaluation.models import EvalSummary, RepairTask
from evaluation.plan_utils import (
    _average,
    _candidate_passed,
    _candidates_tested_after_pass,
    _candidates_tested_before_pass,
    _first_passing_index,
    _passing_candidates,
)
from patching import CandidatePatch, PatchPlanResult


def write_eval_diagnostics(summary: EvalSummary, path: Path) -> Path:
    """Write per-task candidate diagnostics for later ranking analysis."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "baseline": _aggregate_plan_summaries(
                ((result.task, result.baseline) for result in summary.tasks),
                total_tasks=summary.total,
            ),
            "ranked": _aggregate_plan_summaries(
                ((result.task, result.ranked) for result in summary.tasks),
                total_tasks=summary.total,
            ),
        },
        "tasks": [
            {
                "name": result.task.name,
                "family": result.task.family,
                "source_type": result.task.source_type,
                "split": result.task.split,
                "repo": str(result.task.repo),
                "test_command": result.task.test_command,
                "max_steps": result.task.max_steps,
                "baseline": _plan_diagnostics(result.baseline),
                "ranked": _plan_diagnostics(result.ranked),
            }
            for result in summary.tasks
        ],
    }
    resolved.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return resolved


def write_candidate_outcomes(summary: EvalSummary, path: Path) -> Path:
    """Write one JSONL row per tested candidate from an eval summary."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    rows = list(_candidate_outcome_rows(summary))
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    resolved.write_text(text, encoding="utf-8")
    return resolved


def _plan_diagnostics(plan: PatchPlanResult | None) -> dict[str, object]:
    if plan is None:
        return {"skipped": True}
    candidate_hints = _candidate_hints_by_rank(plan)
    return {
        "skipped": False,
        "baseline_exit_code": plan.baseline_exit_code,
        "candidates_generated": plan.candidates_generated,
        "candidates_tested": plan.candidates_tested,
        "first_passing_index": _first_passing_index(plan),
        "passing_candidates": [
            _candidate_diagnostics(candidate, passed=True)
            for candidate in _passing_candidates(plan)
        ],
        "candidates_tested_before_pass": _candidates_tested_before_pass(plan),
        "candidates_tested_after_pass": _candidates_tested_after_pass(plan),
        "applied": plan.applied,
        "summary": _single_plan_summary(plan),
        "failure_hints": [_failure_hint_diagnostics(hint) for hint in plan.failure_hints],
        "selected": _candidate_diagnostics(plan.selected, passed=True) if plan.selected else None,
        "selected_candidates": [
            _candidate_diagnostics(
                candidate,
                passed=_candidate_passed(candidate, plan),
            )
            for candidate in plan.selected_candidates
        ],
        "tested_candidates": [
            _candidate_diagnostics(
                candidate,
                passed=_candidate_passed(candidate, plan),
                rank_index=rank_index,
                failure_hints=candidate_hints[rank_index - 1],
            )
            for rank_index, candidate in enumerate(plan.tested_candidates, start=1)
        ],
    }


def _candidate_diagnostics(
    candidate: CandidatePatch,
    *,
    passed: bool,
    rank_index: int | None = None,
    failure_hints: tuple[object, ...] | None = None,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {
        "file_path": candidate.file_path,
        "action": candidate.action.kind.value,
        "symbol": candidate.action.target.symbol,
        "start_line": candidate.action.target.start_line,
        "end_line": candidate.action.target.end_line,
        "node_kind": candidate.action.target.node_kind,
        "params": dict(candidate.action.params),
        "reason": candidate.reason,
        "model_score": candidate.model_score,
        "failure_hint_score": candidate.failure_hint_score,
        "ranker_score": candidate.ranker_score,
        "target_context": dict(candidate.target_context),
        "passed": passed,
        **_candidate_edit_metadata(candidate),
    }
    if rank_index is not None:
        diagnostics["rank_index"] = rank_index
    if failure_hints is not None:
        diagnostics["failure_hints"] = [
            _failure_hint_diagnostics(hint) for hint in failure_hints
        ]
    return diagnostics


def _candidate_outcome_rows(summary: EvalSummary) -> Iterable[dict[str, object]]:
    for result in summary.tasks:
        for phase, plan in (("baseline", result.baseline), ("ranked", result.ranked)):
            if plan is None:
                continue
            first_passing_index = _first_passing_index(plan)
            passing_candidates = _passing_candidates(plan)
            passing_count = len(passing_candidates)
            candidate_hints = _candidate_hints_by_rank(plan)
            for rank_index, candidate in enumerate(plan.tested_candidates, start=1):
                passed = _candidate_passed(candidate, plan)
                failure_hints = [
                    _failure_hint_diagnostics(hint)
                    for hint in candidate_hints[rank_index - 1]
                ]
                yield {
                    "task": result.task.name,
                    "task_family": result.task.family,
                    "source_type": result.task.source_type,
                    "split": result.task.split,
                    "language": "python",
                    "phase": phase,
                    "file_path": candidate.file_path,
                    "action": candidate.action.kind.value,
                    "symbol": candidate.action.target.symbol,
                    "start_line": candidate.action.target.start_line,
                    "end_line": candidate.action.target.end_line,
                    "node_kind": candidate.action.target.node_kind,
                    "params": dict(candidate.action.params),
                    "reason": candidate.reason,
                    "model_score": candidate.model_score,
                    "failure_hint_score": candidate.failure_hint_score,
                    "ranker_score": candidate.ranker_score,
                    "target_context": dict(candidate.target_context),
                    "passed": passed,
                    "preferred": _candidate_matches_preferred(candidate, result.task.preferred_patch),
                    "rank_index": rank_index,
                    "first_passing_index": first_passing_index,
                    "is_first_pass": passed and rank_index == first_passing_index,
                    "passing_candidates": passing_count,
                    "other_candidates_also_passed": passing_count > 1,
                    "failure_hints": failure_hints,
                    **_candidate_edit_metadata(candidate),
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
        "expected_strings": sorted(getattr(hint, "expected_strings", set())),
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


def _candidate_hints_by_rank(plan: PatchPlanResult) -> tuple[tuple[object, ...], ...]:
    if len(plan.tested_candidate_hints) == len(plan.tested_candidates):
        return tuple(plan.tested_candidate_hints)
    return tuple(plan.failure_hints for _candidate in plan.tested_candidates)


def _candidate_edit_metadata(candidate: CandidatePatch) -> dict[str, object]:
    added_lines, removed_lines = _diff_line_counts(candidate.diff())
    edit = candidate.edit
    target = candidate.action.target
    edit_line_span = max(1, edit.end_line - edit.start_line + 1)
    replacement_lines = _replacement_line_count(edit.replacement)
    return {
        "diff_added_lines": added_lines,
        "diff_removed_lines": removed_lines,
        "diff_changed_lines": added_lines + removed_lines,
        "edit_line_span": edit_line_span,
        "edit_replacement_lines": replacement_lines,
        "edit_line_delta": replacement_lines - edit_line_span,
        "edit_start_col": edit.start_col,
        "edit_end_col": edit.end_col,
        "edit_target_line_distance": min(
            abs(edit.start_line - target.start_line),
            abs(edit.end_line - target.end_line),
        ),
        "edit_within_target_span": (
            target.start_line <= edit.start_line and edit.end_line <= target.end_line
        ),
        "edit_is_single_line": edit.start_line == edit.end_line and replacement_lines <= 1,
        **python_ast_delta_metadata(candidate.original_source, candidate.patched_source),
    }


def _diff_line_counts(diff_text: str) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _replacement_line_count(replacement: str) -> int:
    if not replacement:
        return 0
    return max(1, len(replacement.splitlines()))


def _aggregate_plan_summaries(
    task_plans: Iterable[tuple[RepairTask, PatchPlanResult | None]],
    *,
    total_tasks: int,
) -> dict[str, object]:
    plan_items = [(task, plan) for task, plan in task_plans if plan is not None]
    plan_list = [plan for _task, plan in plan_items]
    action_stats: defaultdict[str, _ActionSummaryAccumulator] = defaultdict(_ActionSummaryAccumulator)
    family_stats: defaultdict[str, _ActionSummaryAccumulator] = defaultdict(_ActionSummaryAccumulator)
    source_type_stats: defaultdict[str, _ActionSummaryAccumulator] = defaultdict(_ActionSummaryAccumulator)
    failed_reasons: Counter[str] = Counter()
    failure_modes: Counter[str] = Counter()
    ranker_paths = sorted({str(plan.ranker_path) for plan in plan_list if plan.ranker_path is not None})

    for task, plan in plan_items:
        action = plan.selected.action.kind.value if plan.selected else "unsolved"
        stats = action_stats[action]
        stats.tasks += 1
        stats.candidate_counts.append(plan.candidates_tested)
        family = task.family or "unclassified"
        family_stat = family_stats[family]
        family_stat.tasks += 1
        family_stat.candidate_counts.append(plan.candidates_tested)
        source_type = task.source_type or "unknown"
        source_type_stat = source_type_stats[source_type]
        source_type_stat.tasks += 1
        source_type_stat.candidate_counts.append(plan.candidates_tested)
        if plan.selected is not None:
            stats.solved += 1
            family_stat.solved += 1
            source_type_stat.solved += 1
            if _first_passing_index(plan) == 1:
                stats.pass_at_1 += 1
                family_stat.pass_at_1 += 1
                source_type_stat.pass_at_1 += 1

        failed_reasons.update(
            candidate.reason
            for candidate in plan.tested_candidates
            if not _candidate_passed(candidate, plan)
        )
        failure_modes[_failure_mode(plan)] += 1

    return {
        "skipped": len(plan_list) == 0,
        "tasks": len(plan_list),
        "total_tasks": total_tasks,
        "skipped_tasks": total_tasks - len(plan_list),
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
        "per_task_family": {
            family: {
                "tasks": stats.tasks,
                "solved": stats.solved,
                "pass_at_1": stats.pass_at_1,
                "avg_candidates": _average(stats.candidate_counts),
            }
            for family, stats in sorted(family_stats.items())
        },
        "per_source_type": {
            source_type: {
                "tasks": stats.tasks,
                "solved": stats.solved,
                "pass_at_1": stats.pass_at_1,
                "avg_candidates": _average(stats.candidate_counts),
            }
            for source_type, stats in sorted(source_type_stats.items())
        },
        "top_failed_candidate_reasons": _top_counter(failed_reasons),
        "failure_modes": dict(sorted(failure_modes.items())),
    }


def _single_plan_summary(plan: PatchPlanResult) -> dict[str, object]:
    failed_reasons = Counter(
        candidate.reason
        for candidate in plan.tested_candidates
        if not _candidate_passed(candidate, plan)
    )
    return {
        "failure_mode": _failure_mode(plan),
        "ranker_path": str(plan.ranker_path) if plan.ranker_path is not None else None,
        "ranker_scores_present": _plan_has_ranker_scores(plan),
        "selected_ranker_score": plan.selected.ranker_score if plan.selected else None,
        "first_passing_index": _first_passing_index(plan),
        "passing_candidates": len(_passing_candidates(plan)),
        "candidates_tested_before_pass": _candidates_tested_before_pass(plan),
        "candidates_tested_after_pass": _candidates_tested_after_pass(plan),
        "top_failed_candidate_reasons": _top_counter(failed_reasons),
    }


def _plan_has_ranker_scores(plan: PatchPlanResult) -> bool:
    return any(candidate.ranker_score is not None for candidate in plan.tested_candidates)


def _failure_mode(plan: PatchPlanResult) -> str:
    if plan.selected is not None:
        if _first_passing_index(plan) == 1:
            return "pass_at_1"
        return "bad_ranking"
    if plan.candidates_generated == 0:
        return "missing_action"
    if plan.candidates_tested >= plan.candidates_generated:
        return "missing_action"
    return "search_budget_or_bad_ranking"


def _candidate_matches_preferred(
    candidate: CandidatePatch,
    preferred_patch: dict[str, object] | None,
) -> bool:
    if preferred_patch is None:
        return False
    if preferred_patch.get("file_path") not in (None, candidate.file_path):
        return False
    if preferred_patch.get("action") not in (None, candidate.action.kind.value):
        return False
    if preferred_patch.get("symbol") not in (None, candidate.action.target.symbol):
        return False

    preferred_params = preferred_patch.get("params")
    if isinstance(preferred_params, dict):
        for key, value in preferred_params.items():
            if candidate.action.params.get(key) != value:
                return False
    return True


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
