"""Human-facing fix workflow for j3."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from patching import PatchPlanResult, plan_and_maybe_apply_patch


FAILED_TARGET_RE = re.compile(r"^FAILED\s+([^\s]+::[^\s]+)")


@dataclass(frozen=True, slots=True)
class FixAttempt:
    target: str
    test_command: str
    plan: PatchPlanResult
    applied: bool


@dataclass(frozen=True, slots=True)
class FixWorkflowResult:
    repo: Path
    test_command: str
    baseline_exit_code: int
    failing_targets: list[str]
    attempts: list[FixAttempt]
    test_output: str

    @property
    def solved(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.plan.selected is not None)

    @property
    def applied(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.applied)


def run_fix_workflow(
    *,
    repo: Path,
    test_command: str,
    model_path: Path | None,
    ranker_path: Path | None = None,
    yes: bool,
    dry_run: bool,
    timeout_seconds: int = 30,
    max_candidates: int = 80,
    confirm: Callable[[str], bool] | None = None,
    progress: Callable[[str], None] | None = None,
) -> FixWorkflowResult:
    """Run tests, identify failing pytest targets, and patch them one by one."""

    root = repo.expanduser().resolve()
    baseline = _run_command(root, test_command, timeout_seconds)
    output = _combined_output(baseline)
    if baseline.returncode == 0:
        return FixWorkflowResult(
            repo=root,
            test_command=test_command,
            baseline_exit_code=0,
            failing_targets=[],
            attempts=[],
            test_output=output,
        )

    targets = parse_pytest_failures(output)
    if not targets:
        targets = ["."]

    attempts: list[FixAttempt] = []
    for target in targets:
        target_command = _target_command(test_command, target)
        preview = plan_and_maybe_apply_patch(
            repo=root,
            test_command=target_command,
            dry_run=True,
            timeout_seconds=timeout_seconds,
            max_candidates=max_candidates,
            model_path=model_path,
            ranker_path=ranker_path,
            progress=progress,
        )

        should_apply = False
        applied_plan = preview
        if preview.selected is not None and not dry_run:
            should_apply = yes or (confirm is not None and confirm(_confirmation_prompt(preview)))
            if should_apply:
                applied_plan = plan_and_maybe_apply_patch(
                    repo=root,
                    test_command=target_command,
                    dry_run=False,
                    timeout_seconds=timeout_seconds,
                    max_candidates=max_candidates,
                    model_path=model_path,
                    ranker_path=ranker_path,
                    progress=progress,
                )

        attempts.append(
            FixAttempt(
                target=target,
                test_command=target_command,
                plan=applied_plan,
                applied=applied_plan.applied,
            )
        )

    return FixWorkflowResult(
        repo=root,
        test_command=test_command,
        baseline_exit_code=baseline.returncode,
        failing_targets=targets,
        attempts=attempts,
        test_output=output,
    )


def parse_pytest_failures(output: str) -> list[str]:
    """Extract failed pytest node IDs from pytest summary output."""

    targets: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        match = FAILED_TARGET_RE.match(line.strip())
        if not match:
            continue
        target = match.group(1)
        if target not in seen:
            targets.append(target)
            seen.add(target)
    return targets


def _target_command(original_command: str, target: str) -> str:
    if target == ".":
        return original_command
    if "python -m pytest" in original_command:
        return f"python -m pytest {target}"
    if "pytest" in original_command:
        return f"pytest {target}"
    return original_command


def _confirmation_prompt(plan: PatchPlanResult) -> str:
    if plan.selected is None:
        return "Apply patch? [y/N] "
    return f"Apply patch to {plan.selected.file_path}? [y/N] "


def _run_command(repo: Path, command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repo,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + result.stderr).strip()
