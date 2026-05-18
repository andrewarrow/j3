"""Preflight runner for compact issue/PR replay rows."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


ISSUE_PR_PREFLIGHT_SCHEMA_VERSION = "issue-pr-replay-preflight-v1"
DEFAULT_SETUP_COMMAND = "python -m pip install -e ."
DEFAULT_TIMEOUT_SECONDS = 120

Command = str | Sequence[str]
SubprocessRunner = Callable[
    [Command, Path | None, int],
    subprocess.CompletedProcess[str],
]


@dataclass(frozen=True, slots=True)
class PreflightCommandResult:
    """Serializable result for one checkout, setup, or validation command."""

    name: str
    command: str
    cwd: str | None
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True, slots=True)
class IssuePrPreflightOutcome:
    """Outcome row for one pre-edit issue/PR replay preflight."""

    replay_id: str
    repo: str
    repo_before_ref: Mapping[str, object]
    validation_command: str
    command_results: tuple[PreflightCommandResult, ...]
    blocker_labels: tuple[str, ...]
    residual_category: str
    provenance: Mapping[str, object]

    @property
    def status(self) -> str:
        return "passed" if not self.blocker_labels else "blocked"

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": ISSUE_PR_PREFLIGHT_SCHEMA_VERSION,
            "record_kind": "issue_pr_replay_preflight_outcome",
            "replay_id": self.replay_id,
            "repo": self.repo,
            "repo_before_ref": dict(self.repo_before_ref),
            "validation_command": self.validation_command,
            "pre_edit": True,
            "status": self.status,
            "command_results": [result.to_record() for result in self.command_results],
            "blocker_labels": list(self.blocker_labels),
            "residual_category": self.residual_category,
            "provenance": dict(self.provenance),
        }


def load_issue_pr_replay_manifest(path: Path) -> dict[str, object]:
    """Load the compact issue/PR replay manifest."""

    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("issue/PR replay manifest must be a JSON object")
    if value.get("schema_version") != "issue-pr-mini-replay-v0":
        raise ValueError("unsupported issue/PR replay manifest schema_version")
    records = value.get("records")
    if not isinstance(records, list):
        raise ValueError("issue/PR replay manifest records must be a list")
    return value


def select_issue_pr_replay_record(
    manifest: Mapping[str, object],
    replay_id: str,
) -> dict[str, object]:
    """Select one replay row by stable id."""

    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("issue/PR replay manifest records must be a list")
    for record in records:
        if isinstance(record, dict) and record.get("id") == replay_id:
            return record
    raise KeyError(f"unknown issue/PR replay id: {replay_id}")


def run_issue_pr_replay_preflight(
    *,
    manifest_path: Path,
    replay_id: str,
    workspace: Path,
    setup_command: str | None = DEFAULT_SETUP_COMMAND,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    runner: SubprocessRunner | None = None,
) -> IssuePrPreflightOutcome:
    """Run checkout, setup, and baseline validation for one replay row."""

    if runner is None:
        runner = run_subprocess

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(record, "repo", context=replay_id)
    repo_before_ref = _mapping(record.get("repo_before_ref"), field="repo_before_ref")
    sha = _required_str(repo_before_ref, "sha", context="repo_before_ref")
    validation = _mapping(record.get("validation"), field="validation")
    validation_command = _optional_str(validation.get("command"))

    command_results: list[PreflightCommandResult] = []
    blockers: list[str] = []
    residual_category = "none"

    checkout_dir = _checkout_dir(workspace, repo=repo, replay_id=replay_id, sha=sha)
    checkout_dir.parent.mkdir(parents=True, exist_ok=True)

    clone_url = f"https://github.com/{repo}.git"
    clone = _run_command(
        name="checkout_clone",
        command=["git", "clone", clone_url, str(checkout_dir)],
        cwd=checkout_dir.parent,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    command_results.append(clone)
    if not clone.passed:
        blockers.append("environment_checkout_failed")
        residual_category = "environment"
        return _outcome(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            repo_before_ref=repo_before_ref,
            validation_command=validation_command,
            command_results=command_results,
            blockers=blockers,
            residual_category=residual_category,
        )

    checkout = _run_command(
        name="checkout_ref",
        command=["git", "checkout", sha],
        cwd=checkout_dir,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    command_results.append(checkout)
    if not checkout.passed:
        blockers.append("environment_checkout_ref_failed")
        residual_category = "environment"
        return _outcome(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            repo_before_ref=repo_before_ref,
            validation_command=validation_command,
            command_results=command_results,
            blockers=blockers,
            residual_category=residual_category,
        )

    verify = _run_command(
        name="checkout_verify",
        command=["git", "rev-parse", "HEAD"],
        cwd=checkout_dir,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    command_results.append(verify)
    if not verify.passed or verify.stdout.strip() != sha:
        blockers.append("environment_checkout_ref_mismatch")
        residual_category = "environment"
        return _outcome(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            repo_before_ref=repo_before_ref,
            validation_command=validation_command,
            command_results=command_results,
            blockers=blockers,
            residual_category=residual_category,
        )

    if setup_command:
        setup = _run_command(
            name="setup",
            command=setup_command,
            cwd=checkout_dir,
            timeout_seconds=timeout_seconds,
            runner=runner,
        )
        command_results.append(setup)
        if not setup.passed:
            blockers.append("environment_setup_failed")
            residual_category = "environment"
            return _outcome(
                manifest=manifest,
                manifest_path=manifest_path,
                record=record,
                repo_before_ref=repo_before_ref,
                validation_command=validation_command,
                command_results=command_results,
                blockers=blockers,
                residual_category=residual_category,
            )
    else:
        blockers.append("environment_setup_command_missing")
        residual_category = "environment"
        return _outcome(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            repo_before_ref=repo_before_ref,
            validation_command=validation_command,
            command_results=command_results,
            blockers=blockers,
            residual_category=residual_category,
        )

    if not validation_command:
        blockers.append("prompt_spec_missing_validation_command")
        residual_category = "prompt_spec"
        return _outcome(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            repo_before_ref=repo_before_ref,
            validation_command=validation_command,
            command_results=command_results,
            blockers=blockers,
            residual_category=residual_category,
        )

    baseline = _run_command(
        name="baseline_validation",
        command=validation_command,
        cwd=checkout_dir,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    command_results.append(baseline)
    if not baseline.passed:
        blockers.append("validation_baseline_failed")
        residual_category = "validation"
        return _outcome(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            repo_before_ref=repo_before_ref,
            validation_command=validation_command,
            command_results=command_results,
            blockers=blockers,
            residual_category=residual_category,
        )

    residual_category, blockers = classify_pre_edit_residuals(
        record.get("initial_residual_labels", []),
        validation_availability=_optional_str(validation.get("availability")),
    )
    return _outcome(
        manifest=manifest,
        manifest_path=manifest_path,
        record=record,
        repo_before_ref=repo_before_ref,
        validation_command=validation_command,
        command_results=command_results,
        blockers=blockers,
        residual_category=residual_category,
    )


def classify_pre_edit_residuals(
    initial_residual_labels: object,
    *,
    validation_availability: str,
) -> tuple[str, list[str]]:
    """Classify pre-edit blockers without blaming ranking or materialization."""

    labels: set[str] = set()
    if isinstance(initial_residual_labels, list):
        labels = {label for label in initial_residual_labels if isinstance(label, str)}
    if "local_knowledge_gap" in labels:
        return "local_knowledge", ["local_knowledge_required"]
    if "prompt_spec_parsing_gap" in labels:
        return "prompt_spec", ["prompt_spec_ambiguous_or_incomplete"]
    if "validation_gap" in labels or validation_availability == "partial":
        return "validation", ["validation_recipe_partial"]
    return "none", []


def write_issue_pr_preflight_jsonl(
    outcomes: Sequence[IssuePrPreflightOutcome],
    path: Path,
) -> Path:
    """Write preflight outcome rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for outcome in outcomes:
            handle.write(json.dumps(outcome.to_record(), sort_keys=True) + "\n")
    return resolved


def run_subprocess(
    command: Command,
    cwd: Path | None,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    """Default subprocess runner used by the preflight orchestration."""

    return subprocess.run(
        command,
        cwd=cwd,
        shell=isinstance(command, str),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _run_command(
    *,
    name: str,
    command: Command,
    cwd: Path | None,
    timeout_seconds: int,
    runner: SubprocessRunner,
) -> PreflightCommandResult:
    command_text = _command_text(command)
    try:
        completed = runner(command, cwd, timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return PreflightCommandResult(
            name=name,
            command=command_text,
            cwd=str(cwd) if cwd is not None else None,
            exit_code=None,
            stdout=_optional_str(exc.stdout),
            stderr=_optional_str(exc.stderr),
            timed_out=True,
        )
    return PreflightCommandResult(
        name=name,
        command=command_text,
        cwd=str(cwd) if cwd is not None else None,
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _outcome(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path,
    record: Mapping[str, object],
    repo_before_ref: Mapping[str, object],
    validation_command: str,
    command_results: Sequence[PreflightCommandResult],
    blockers: Sequence[str],
    residual_category: str,
) -> IssuePrPreflightOutcome:
    return IssuePrPreflightOutcome(
        replay_id=_required_str(record, "id", context="record"),
        repo=_required_str(record, "repo", context="record"),
        repo_before_ref=dict(repo_before_ref),
        validation_command=validation_command,
        command_results=tuple(command_results),
        blocker_labels=tuple(blockers),
        residual_category=residual_category,
        provenance={
            "manifest_path": str(manifest_path),
            "manifest_schema_version": manifest.get("schema_version"),
            "manifest_curated_at": manifest.get("curated_at"),
            "source": manifest.get("source"),
            "prompt_source": record.get("prompt_source"),
            "accepted_change": record.get("accepted_change"),
            "provenance_license": record.get("provenance_license"),
            "stable_split": record.get("stable_split"),
            "initial_residual_labels": record.get("initial_residual_labels", []),
            "deferred_agent_residual_labels": _deferred_agent_residual_labels(
                record.get("initial_residual_labels", [])
            ),
        },
    )


def _deferred_agent_residual_labels(initial_residual_labels: object) -> list[str]:
    if not isinstance(initial_residual_labels, list):
        return []
    return [
        label
        for label in initial_residual_labels
        if label in {"materialization_gap", "ranking_gap"}
    ]


def _checkout_dir(workspace: Path, *, repo: str, replay_id: str, sha: str) -> Path:
    safe_repo = repo.replace("/", "__")
    safe_id = "".join(char if char.isalnum() or char in "._-" else "_" for char in replay_id)
    return workspace.expanduser().resolve() / f"{safe_repo}-{safe_id}-{sha[:12]}"


def _command_text(command: Command) -> str:
    if isinstance(command, str):
        return command
    return shlex.join(str(part) for part in command)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _required_str(mapping: Mapping[str, object], field: str, *, context: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value


def _optional_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    if isinstance(value, str):
        return value
    return str(value)
