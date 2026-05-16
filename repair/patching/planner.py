"""Patch planning loop and test validation."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from candidate_ranking import CandidateRankerModel
from failure_hints import parse_pytest_failure_hints
from repo import DEFAULT_EXCLUDE_DIRS

from .generation import generate_candidate_patches
from .model import PatchRankingModel
from .ranking import (
    prioritize_candidate_patches,
    rank_candidate_patches,
    rank_with_candidate_ranker,
)
from .types import CandidatePatch, PatchPlanResult


DEFAULT_PATCH_TIMEOUT_SECONDS = 30


def plan_and_maybe_apply_patch(
    *,
    repo: Path,
    test_command: str,
    dry_run: bool,
    timeout_seconds: int = DEFAULT_PATCH_TIMEOUT_SECONDS,
    max_candidates: int = 80,
    model_path: Path | None = None,
    ranker_path: Path | None = None,
    use_failure_hints: bool = True,
    explore_after_pass: int = 0,
    progress: Callable[[str], None] | None = None,
) -> PatchPlanResult:
    """Find the first candidate patch that makes the requested test pass."""

    if explore_after_pass < 0:
        raise ValueError("explore_after_pass must be >= 0")

    root = repo.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"repo does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repo is not a directory: {root}")

    _emit_progress(progress, f"baseline: running `{test_command}`")
    started = time.perf_counter()
    baseline = _run_test(root, test_command, timeout_seconds)
    _emit_progress(
        progress,
        f"baseline: exit={baseline.returncode} elapsed={time.perf_counter() - started:.2f}s",
    )
    baseline_output = _combined_output(baseline)
    if baseline.returncode == 0:
        return PatchPlanResult(
            repo=root,
            test_command=test_command,
            baseline_exit_code=0,
            candidates_generated=0,
            candidates_tested=0,
            selected=None,
            applied=False,
            test_output=baseline_output,
            model_path=None,
            ranker_path=None,
        )

    _emit_progress(progress, "candidates: generating structured patches")
    started = time.perf_counter()
    candidates = generate_candidate_patches(root)
    _emit_progress(
        progress,
        f"candidates: generated={len(candidates)} elapsed={time.perf_counter() - started:.2f}s",
    )
    model = _load_model_if_available(model_path)
    if model is not None:
        _emit_progress(progress, f"rank: scoring with model {model.path}")
        candidates = rank_candidate_patches(candidates, model)
    baseline_hints = parse_pytest_failure_hints(baseline_output)
    hints = baseline_hints if use_failure_hints else []
    ranker = _load_candidate_ranker_if_available(ranker_path)
    if hints:
        _emit_progress(progress, f"hints: parsed={len(hints)}; prioritizing candidates")
        candidates = prioritize_candidate_patches(candidates, hints, ranker=ranker)
    elif ranker is not None:
        _emit_progress(progress, f"rank: scoring with candidate ranker {ranker.path}")
        candidates = rank_with_candidate_ranker(candidates, ranker, hints=[])
    candidates_tested = 0
    tested_candidates: list[CandidatePatch] = []
    passing_candidates: list[CandidatePatch] = []
    selected: CandidatePatch | None = None
    first_passing_index: int | None = None
    for candidate in candidates[:max_candidates]:
        candidates_tested += 1
        _emit_progress(
            progress,
            "test: "
            f"candidate={candidates_tested}/{min(max_candidates, len(candidates))} "
            f"action={candidate.action.kind.value} "
            f"symbol={candidate.action.target.symbol or '-'} "
            f"reason={candidate.reason}",
        )
        with tempfile.TemporaryDirectory(prefix="j3-patch-") as tmp:
            tmp_repo = Path(tmp) / root.name
            _copy_repo(root, tmp_repo)
            _write_candidate(tmp_repo, candidate)
            started = time.perf_counter()
            attempt = _run_test(tmp_repo, test_command, timeout_seconds)
            elapsed = time.perf_counter() - started
            tested_candidates.append(candidate)
            _emit_progress(
                progress,
                f"test: candidate={candidates_tested} exit={attempt.returncode} elapsed={elapsed:.2f}s",
            )
            if attempt.returncode == 0:
                passing_candidates.append(candidate)
                if selected is None:
                    selected = candidate
                    first_passing_index = candidates_tested
                    baseline_output = _combined_output(attempt)
                    _emit_progress(progress, f"selected: candidate={candidates_tested} passed")

            if (
                selected is not None
                and first_passing_index is not None
                and candidates_tested - first_passing_index >= explore_after_pass
            ):
                break

    if selected is not None:
        if not dry_run:
            _write_candidate(root, selected)
        return PatchPlanResult(
            repo=root,
            test_command=test_command,
            baseline_exit_code=baseline.returncode,
            candidates_generated=len(candidates),
            candidates_tested=candidates_tested,
            selected=selected,
            applied=not dry_run,
            test_output=baseline_output,
            model_path=model.path if model else None,
            ranker_path=ranker.path if ranker else None,
            tested_candidates=tuple(tested_candidates),
            failure_hints=tuple(baseline_hints),
            first_passing_index=first_passing_index,
            passing_candidates=tuple(passing_candidates),
        )

    _emit_progress(progress, f"status: no passing candidate within tested={candidates_tested}")
    return PatchPlanResult(
        repo=root,
        test_command=test_command,
        baseline_exit_code=baseline.returncode,
        candidates_generated=len(candidates),
        candidates_tested=candidates_tested,
        selected=None,
        applied=False,
        test_output=baseline_output,
        model_path=model.path if model else None,
        ranker_path=ranker.path if ranker else None,
        tested_candidates=tuple(tested_candidates),
        failure_hints=tuple(baseline_hints),
        first_passing_index=None,
        passing_candidates=(),
    )


def _write_candidate(repo: Path, candidate: CandidatePatch) -> None:
    path = repo / candidate.file_path
    path.write_text(candidate.patched_source, encoding="utf-8")


def _run_test(repo: Path, command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repo,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _copy_repo(source: Path, destination: Path) -> None:
    def ignore(_: str, names: list[str]) -> set[str]:
        return {name for name in names if name in DEFAULT_EXCLUDE_DIRS or name == "runs"}

    shutil.copytree(source, destination, ignore=ignore)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + result.stderr).strip()


def _emit_progress(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _load_model_if_available(model_path: Path | None) -> PatchRankingModel | None:
    if model_path is None:
        return None
    resolved = model_path.expanduser().resolve()
    if not resolved.exists():
        return None
    return PatchRankingModel.load(resolved)


def _load_candidate_ranker_if_available(ranker_path: Path | None) -> CandidateRankerModel | None:
    if ranker_path is None:
        return None
    resolved = ranker_path.expanduser().resolve()
    if not resolved.exists():
        return None
    return CandidateRankerModel.load(resolved)


