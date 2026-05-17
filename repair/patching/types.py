"""Shared patching data structures."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from j3.actions import PatchAction
from j3.failure_hints import PytestFailureHint
from j3.synth import SourceEdit


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
    target_context: Mapping[str, object] = field(default_factory=dict)

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
    tested_candidate_hints: tuple[tuple[PytestFailureHint, ...], ...] = ()
    first_passing_index: int | None = None
    passing_candidates: tuple[CandidatePatch, ...] = ()
    selected_candidates: tuple[CandidatePatch, ...] = ()
    transition_advice: Mapping[str, object] | None = None
