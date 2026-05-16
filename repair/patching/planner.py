"""Patch planning loop and test validation."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from candidate_ranking import CandidateRankerModel
from failure_hints import PytestFailureHint, parse_pytest_failure_hints
from repo import DEFAULT_EXCLUDE_DIRS

from .context import attach_target_context
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
    max_steps: int = 1,
    model_path: Path | None = None,
    ranker_path: Path | None = None,
    use_failure_hints: bool = True,
    explore_after_pass: int = 0,
    progress: Callable[[str], None] | None = None,
) -> PatchPlanResult:
    """Find the first candidate patch that makes the requested test pass."""

    if explore_after_pass < 0:
        raise ValueError("explore_after_pass must be >= 0")
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")

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

    model = _load_model_if_available(model_path)
    baseline_hints = parse_pytest_failure_hints(baseline_output)
    ranker = _load_candidate_ranker_if_available(ranker_path)

    planning_tmp: tempfile.TemporaryDirectory[str] | None = None
    planning_root = root
    if max_steps > 1:
        planning_tmp = tempfile.TemporaryDirectory(prefix="j3-plan-")
        planning_root = Path(planning_tmp.name) / root.name
        _copy_repo(root, planning_root)

    candidates_tested = 0
    candidates_generated = 0
    tested_candidates: list[CandidatePatch] = []
    tested_candidate_hints: list[tuple[PytestFailureHint, ...]] = []
    passing_candidates: list[CandidatePatch] = []
    selected_candidates: list[CandidatePatch] = []
    selected: CandidatePatch | None = None
    first_passing_index: int | None = None
    current_output = baseline_output
    seen_failures = {_failure_signature(current_output)}

    try:
        for step_index in range(1, max_steps + 1):
            step_hints = parse_pytest_failure_hints(current_output) if use_failure_hints else []
            _emit_progress(
                progress,
                f"candidates: generating structured patches for step {step_index}",
            )
            started = time.perf_counter()
            candidates = generate_candidate_patches(planning_root)
            candidates = attach_target_context(planning_root, candidates)
            candidates_generated += len(candidates)
            elapsed = time.perf_counter() - started
            _emit_progress(
                progress,
                f"candidates: generated={len(candidates)} elapsed={elapsed:.2f}s",
            )
            if model is not None:
                _emit_progress(progress, f"rank: scoring with model {model.path}")
                candidates = rank_candidate_patches(candidates, model)
            if step_hints:
                _emit_progress(
                    progress,
                    f"hints: parsed={len(step_hints)}; prioritizing candidates",
                )
                candidates = prioritize_candidate_patches(candidates, step_hints, ranker=ranker)
            elif ranker is not None:
                _emit_progress(progress, f"rank: scoring with candidate ranker {ranker.path}")
                candidates = rank_with_candidate_ranker(candidates, ranker, hints=[])

            improved_candidate: CandidatePatch | None = None
            improved_output = current_output
            remaining = max_candidates - candidates_tested
            if remaining <= 0:
                break
            for candidate in candidates[:remaining]:
                candidates_tested += 1
                _emit_progress(
                    progress,
                    "test: "
                    f"candidate={candidates_tested}/{max_candidates} "
                    f"step={step_index}/{max_steps} "
                    f"action={candidate.action.kind.value} "
                    f"symbol={candidate.action.target.symbol or '-'} "
                    f"reason={candidate.reason}",
                )
                with tempfile.TemporaryDirectory(prefix="j3-patch-") as tmp:
                    tmp_repo = Path(tmp) / root.name
                    _copy_repo(planning_root, tmp_repo)
                    _write_candidate(tmp_repo, candidate)
                    started = time.perf_counter()
                    attempt = _run_test(tmp_repo, test_command, timeout_seconds)
                    elapsed = time.perf_counter() - started
                    tested_candidates.append(candidate)
                    tested_candidate_hints.append(tuple(step_hints))
                    attempt_output = _combined_output(attempt)
                    _emit_progress(
                        progress,
                        "test: "
                        f"candidate={candidates_tested} "
                        f"exit={attempt.returncode} "
                        f"elapsed={elapsed:.2f}s",
                    )
                    if attempt.returncode == 0:
                        passing_candidates.append(candidate)
                        if selected is None:
                            selected = candidate
                            first_passing_index = candidates_tested
                            current_output = attempt_output
                            _emit_progress(
                                progress,
                                f"selected: candidate={candidates_tested} passed",
                            )
                    elif selected is None and step_index < max_steps:
                        signature = _failure_signature(attempt_output)
                        if signature not in seen_failures:
                            improved_candidate = candidate
                            improved_output = attempt_output
                            seen_failures.add(signature)
                            message = (
                                f"selected: candidate={candidates_tested} "
                                "changed failure for next step"
                            )
                            _emit_progress(
                                progress,
                                message,
                            )
                            break

                    if (
                        selected is not None
                        and first_passing_index is not None
                        and candidates_tested - first_passing_index >= explore_after_pass
                    ):
                        break

            if selected is not None:
                break
            if improved_candidate is None or candidates_tested >= max_candidates:
                break
            selected_candidates.append(improved_candidate)
            _write_candidate(planning_root, improved_candidate)
            current_output = improved_output
    finally:
        if planning_tmp is not None:
            planning_tmp.cleanup()

    if selected is not None:
        selected_candidates.append(selected)
        if not dry_run:
            for candidate in selected_candidates:
                _write_candidate(root, candidate)
        return PatchPlanResult(
            repo=root,
            test_command=test_command,
            baseline_exit_code=baseline.returncode,
            candidates_generated=candidates_generated,
            candidates_tested=candidates_tested,
            selected=selected,
            applied=not dry_run,
            test_output=current_output,
            model_path=model.path if model else None,
            ranker_path=ranker.path if ranker else None,
            tested_candidates=tuple(tested_candidates),
            failure_hints=tuple(baseline_hints),
            tested_candidate_hints=tuple(tested_candidate_hints),
            first_passing_index=first_passing_index,
            passing_candidates=tuple(passing_candidates),
            selected_candidates=tuple(selected_candidates),
        )

    _emit_progress(progress, f"status: no passing candidate within tested={candidates_tested}")
    return PatchPlanResult(
        repo=root,
        test_command=test_command,
        baseline_exit_code=baseline.returncode,
        candidates_generated=candidates_generated,
        candidates_tested=candidates_tested,
        selected=None,
        applied=False,
        test_output=current_output,
        model_path=model.path if model else None,
        ranker_path=ranker.path if ranker else None,
        tested_candidates=tuple(tested_candidates),
        failure_hints=tuple(baseline_hints),
        tested_candidate_hints=tuple(tested_candidate_hints),
        first_passing_index=None,
        passing_candidates=(),
        selected_candidates=tuple(selected_candidates),
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


def _failure_signature(output: str) -> tuple[object, ...]:
    hints = parse_pytest_failure_hints(output)
    if hints:
        return tuple(
            (
                hint.nodeid,
                hint.exception_type,
                tuple(sorted(hint.missing_names)),
                tuple(sorted(hint.missing_attributes)),
                tuple(sorted(hint.missing_modules)),
                tuple(sorted(hint.missing_keys)),
                tuple(sorted(hint.type_error_names)),
                tuple(
                    (assertion.operator, assertion.actual, assertion.expected)
                    for assertion in hint.assertions
                ),
            )
            for hint in hints
        )
    return (output[-500:],)
