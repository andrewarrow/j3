"""Evaluation data models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evaluation.plan_utils import _average, _first_passing_index
from j3.patching import PatchPlanResult

EvalPhase = Literal["baseline", "ranked", "both"]


@dataclass(frozen=True, slots=True)
class RepairTask:
    name: str
    repo: Path
    test_command: str
    family: str = "unclassified"
    source_type: str = "handcrafted"
    split: str = "train"
    preferred_patch: dict[str, object] | None = None
    max_steps: int = 1


@dataclass(frozen=True, slots=True)
class TaskEvalResult:
    task: RepairTask
    baseline: PatchPlanResult | None
    ranked: PatchPlanResult | None

    @property
    def baseline_solved(self) -> bool:
        return self.baseline is not None and self.baseline.selected is not None

    @property
    def ranked_solved(self) -> bool:
        return self.ranked is not None and self.ranked.selected is not None

    @property
    def baseline_skipped(self) -> bool:
        return self.baseline is None

    @property
    def ranked_skipped(self) -> bool:
        return self.ranked is None


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
            if (
                task.baseline_solved
                and task.baseline is not None
                and _first_passing_index(task.baseline) == 1
            )
        )

    @property
    def ranked_pass_at_1(self) -> int:
        return sum(
            1
            for task in self.tasks
            if (
                task.ranked_solved
                and task.ranked is not None
                and _first_passing_index(task.ranked) == 1
            )
        )

    @property
    def baseline_avg_candidates_tested(self) -> float:
        return _average(
            [task.baseline.candidates_tested for task in self.tasks if task.baseline is not None]
        )

    @property
    def ranked_avg_candidates_tested(self) -> float:
        return _average(
            [task.ranked.candidates_tested for task in self.tasks if task.ranked is not None]
        )

    @property
    def baseline_skipped(self) -> bool:
        return all(task.baseline_skipped for task in self.tasks)

    @property
    def ranked_skipped(self) -> bool:
        return all(task.ranked_skipped for task in self.tasks)
