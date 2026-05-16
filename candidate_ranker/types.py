"""Data contracts for the candidate ranker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from actions import PatchAction


class CandidateLike(Protocol):
    file_path: str
    action: PatchAction
    reason: str
    model_score: float | None
    failure_hint_score: float


@dataclass(frozen=True, slots=True)
class CandidateRankerTrainingResult:
    out_dir: Path
    ranker_path: Path
    metrics_path: Path
    diagnostics_paths: list[Path]
    candidate_outcome_paths: list[Path]
    validation_diagnostics_paths: list[Path]
    validation_candidate_outcome_paths: list[Path]
    holdout_tasks: list[str]
    holdout_task_families: list[str]
    rows: int
    passing_rows: int
    failing_rows: int
    tasks: int
    plans: int
    training_pairs: int
    features: int
    mistakes: int
    training_accuracy: float
    margin_violations: int
    calibration: dict[str, object]
    validation: dict[str, object]
    per_action: dict[str, dict[str, object]]
    per_task_family: dict[str, dict[str, object]]
