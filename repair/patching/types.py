"""Shared patching data structures."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from actions import PatchAction
from failure_hints import PytestFailureHint
from synth import SourceEdit


@dataclass(frozen=True, slots=True)
class CandidatePatch:
    file_path: str
    action: PatchAction
    edit: SourceEdit
    original_source: str
    patched_source: str
    reason: str
    model_score: float | None = None
    failure_hint_score: float = 0.0
    ranker_score: float | None = None

    def diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.original_source.splitlines(keepends=True),
                self.patched_source.splitlines(keepends=True),
                fromfile=f"a/{self.file_path}",
                tofile=f"b/{self.file_path}",
            )
        )


@dataclass(frozen=True, slots=True)
class PatchPlanResult:
    repo: Path
    test_command: str
    baseline_exit_code: int
    candidates_generated: int
    candidates_tested: int
    selected: CandidatePatch | None
    applied: bool
    test_output: str
    model_path: Path | None = None
    ranker_path: Path | None = None
    tested_candidates: tuple[CandidatePatch, ...] = ()
    failure_hints: tuple[PytestFailureHint, ...] = ()
    first_passing_index: int | None = None
    passing_candidates: tuple[CandidatePatch, ...] = ()


