"""Console output helpers for eval progress and summaries."""

from __future__ import annotations

from evaluation import EvalSummary


def progress(message: str) -> None:
    print(f"[eval] {message}", flush=True)


def summary_progress(message: str) -> None:
    if not is_candidate_level_progress(message):
        progress(message)


def verbose_progress(message: str) -> None:
    progress(message)


def phase_summary_line(
    label: str,
    skipped: bool,
    solved: int,
    pass_at_1: int,
    avg_candidates: float,
    total: int,
) -> str:
    if skipped:
        return f"{label}: skipped"
    return (
        f"{label}: "
        f"solved={solved}/{total} "
        f"pass@1={pass_at_1}/{total} "
        f"avg_candidates={avg_candidates:.2f}"
    )


def task_phase_status(*, skipped: bool, solved: bool) -> str:
    if skipped:
        return "skipped"
    return "solved" if solved else "failed"


def eval_phase_solved(*, summary: EvalSummary, phase: str) -> bool:
    if phase == "baseline":
        return summary.baseline_solved == summary.total
    return summary.ranked_solved == summary.total


_CANDIDATE_LEVEL_PROGRESS_PREFIXES = (
    "baseline: running",
    "baseline: exit",
    "candidates:",
    "rank:",
    "hints:",
    "test: candidate=",
    "selected:",
    "status: no passing candidate",
)


def is_candidate_level_progress(message: str) -> bool:
    if message.startswith(_CANDIDATE_LEVEL_PROGRESS_PREFIXES):
        return True
    _, separator, phase_message = message.partition(": ")
    return bool(separator) and phase_message.startswith(_CANDIDATE_LEVEL_PROGRESS_PREFIXES)
