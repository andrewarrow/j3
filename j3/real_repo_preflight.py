"""Preflight runner for the real-repo evaluation ladder."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence


REAL_REPO_PREFLIGHT_SCHEMA_VERSION = "real-repo-preflight-outcome-v1"
REAL_REPO_PREFLIGHT_KIND = "real_repo_eval_ladder_preflight"
DEFAULT_MANIFEST_PATH = Path("examples/real_repo_eval_ladder.json")
DEFAULT_WORK_ROOT = Path("/tmp/j3-real-repo-preflight")

CommandRunner = Callable[[str, Path, int], "PreflightCommandResult"]


@dataclass(frozen=True, slots=True)
class PreflightCommandResult:
    """Serializable result for one setup or validation command."""

    command: str
    cwd: str
    timeout_seconds: int
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    status: str = "passed"

    def to_record(self) -> dict[str, object]:
        return {
            "command": self.command,
            "cwd": self.cwd,
            "timeout_seconds": self.timeout_seconds,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class AllowedWritePathCheck:
    """Result of checking candidate writes against a task allowlist."""

    status: str
    allowed_write_paths: tuple[str, ...]
    candidate_paths: tuple[str, ...]
    violations: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "status": self.status,
            "allowed_write_paths": list(self.allowed_write_paths),
            "candidate_paths": list(self.candidate_paths),
            "violations": list(self.violations),
        }


@dataclass(frozen=True, slots=True)
class RepoPreflightResult:
    """Shared checkout, setup, and baseline result for one repository."""

    repo_id: str
    checkout_ref: str
    repo_path: Path
    checkout_command_results: tuple[PreflightCommandResult, ...] = ()
    setup_command_results: tuple[PreflightCommandResult, ...] = ()
    baseline_validation_command_results: tuple[PreflightCommandResult, ...] = ()
    environment_blocker_label: str = "none"


@dataclass(frozen=True, slots=True)
class RealRepoPreflightOptions:
    """Runtime options for a real-repo ladder preflight run."""

    manifest_path: Path = DEFAULT_MANIFEST_PATH
    work_root: Path = DEFAULT_WORK_ROOT
    outcome_path: Path | None = None
    checkout_timeout_seconds: int = 120
    setup_timeout_seconds: int = 600
    baseline_timeout_seconds: int = 600
    clean_worktree: bool = True
    candidate_paths_by_task: Mapping[str, Sequence[str]] = field(default_factory=dict)


def load_real_repo_ladder_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, object]:
    """Load the REAL-001 ladder manifest."""

    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("real-repo ladder manifest must be a JSON object")
    if manifest.get("schema_version") != "real-repo-eval-ladder-v1":
        raise ValueError("unsupported real-repo ladder schema_version")
    repositories = manifest.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("real-repo ladder manifest must include repositories")
    return manifest


def run_real_repo_preflight(
    options: RealRepoPreflightOptions | None = None,
    *,
    command_runner: CommandRunner | None = None,
) -> tuple[dict[str, object], ...]:
    """Run checkout, setup, baseline validation, and write-scope checks.

    The command runner is injectable so unit tests can prove orchestration
    without cloning from the network or installing upstream dependencies.
    """

    resolved_options = options or RealRepoPreflightOptions()
    runner = command_runner or run_subprocess_command
    manifest = load_real_repo_ladder_manifest(resolved_options.manifest_path)
    defaults = _mapping(manifest.get("defaults"), field="defaults")
    rows: list[dict[str, object]] = []

    for repo in _sequence(manifest["repositories"], field="repositories"):
        repo_record = _mapping(repo, field="repository")
        repo_result = preflight_repository(
            repo_record,
            work_root=resolved_options.work_root,
            checkout_timeout_seconds=resolved_options.checkout_timeout_seconds,
            setup_timeout_seconds=resolved_options.setup_timeout_seconds,
            baseline_timeout_seconds=resolved_options.baseline_timeout_seconds,
            clean_worktree=resolved_options.clean_worktree,
            command_runner=runner,
        )
        for task in _sequence(repo_record.get("tasks"), field="repository.tasks"):
            task_record = _mapping(task, field="repository.task")
            rows.append(
                real_repo_preflight_outcome_row(
                    repo=repo_record,
                    task=task_record,
                    repo_result=repo_result,
                    defaults=defaults,
                    candidate_paths=resolved_options.candidate_paths_by_task.get(
                        _required_str(task_record, "id"),
                        task_record.get("allowed_write_paths", ()),
                    ),
                )
            )

    if resolved_options.outcome_path is not None:
        write_real_repo_preflight_jsonl(rows, resolved_options.outcome_path)
    return tuple(rows)


def preflight_repository(
    repo: Mapping[str, object],
    *,
    work_root: Path,
    checkout_timeout_seconds: int,
    setup_timeout_seconds: int,
    baseline_timeout_seconds: int,
    clean_worktree: bool,
    command_runner: CommandRunner,
) -> RepoPreflightResult:
    """Clone a pinned repo and run setup plus baseline validation commands."""

    repo_id = _required_str(repo, "id")
    upstream = _required_str(repo, "upstream")
    checkout_ref = _required_str(repo, "checkout_ref")
    repo_path = work_root.expanduser().resolve() / repo_id

    if clean_worktree and repo_path.exists():
        shutil.rmtree(repo_path)
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    checkout_results = _run_commands(
        [
            "git clone --no-checkout "
            f"{shlex.quote(upstream)} {shlex.quote(str(repo_path))}",
            f"git checkout --detach {shlex.quote(checkout_ref)}",
        ],
        cwd_sequence=[repo_path.parent, repo_path],
        timeout_seconds=checkout_timeout_seconds,
        command_runner=command_runner,
    )
    if _has_failed_command(checkout_results):
        return RepoPreflightResult(
            repo_id=repo_id,
            checkout_ref=checkout_ref,
            repo_path=repo_path,
            checkout_command_results=checkout_results,
            environment_blocker_label="checkout_failed",
        )

    setup_results = _run_commands(
        _string_sequence(repo.get("setup_commands"), field="setup_commands"),
        cwd_sequence=None,
        cwd=repo_path,
        timeout_seconds=setup_timeout_seconds,
        command_runner=command_runner,
    )
    if _has_failed_command(setup_results):
        return RepoPreflightResult(
            repo_id=repo_id,
            checkout_ref=checkout_ref,
            repo_path=repo_path,
            checkout_command_results=checkout_results,
            setup_command_results=setup_results,
            environment_blocker_label="setup_failed",
        )

    baseline_results = _run_commands(
        _string_sequence(
            repo.get("baseline_validation_commands"),
            field="baseline_validation_commands",
        ),
        cwd_sequence=None,
        cwd=repo_path,
        timeout_seconds=baseline_timeout_seconds,
        command_runner=command_runner,
    )
    blocker = (
        "baseline_validation_failed" if _has_failed_command(baseline_results) else "none"
    )
    return RepoPreflightResult(
        repo_id=repo_id,
        checkout_ref=checkout_ref,
        repo_path=repo_path,
        checkout_command_results=checkout_results,
        setup_command_results=setup_results,
        baseline_validation_command_results=baseline_results,
        environment_blocker_label=blocker,
    )


def real_repo_preflight_outcome_row(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object] | None,
    repo_result: RepoPreflightResult,
    defaults: Mapping[str, object],
    candidate_paths: Sequence[str],
) -> dict[str, object]:
    """Build one JSON-compatible real-repo preflight outcome row."""

    allowed_paths = _string_sequence(
        task.get("allowed_write_paths") if task else (),
        field="allowed_write_paths",
    )
    allowed_check = check_allowed_write_paths(
        allowed_paths,
        candidate_paths=candidate_paths,
    )
    blocker_label = _blocker_label(repo_result, allowed_check)

    row: dict[str, object] = {
        "schema_version": REAL_REPO_PREFLIGHT_SCHEMA_VERSION,
        "record_kind": REAL_REPO_PREFLIGHT_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_id": _required_str(repo, "id"),
        "repo_upstream": _required_str(repo, "upstream"),
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": repo_result.checkout_ref,
        "repo_path": str(repo_result.repo_path),
        "task_id": _required_str(task, "id") if task else None,
        "task_type": str(task.get("task_type")) if task else None,
        "checkout_command_results": [
            result.to_record() for result in repo_result.checkout_command_results
        ],
        "setup_command_results": [
            result.to_record() for result in repo_result.setup_command_results
        ],
        "baseline_validation_command_results": [
            result.to_record()
            for result in repo_result.baseline_validation_command_results
        ],
        "timeout_policy": {
            "max_candidates": _optional_int(defaults.get("max_candidates")),
            "per_candidate_timeout_seconds": _optional_int(
                defaults.get("per_candidate_timeout_seconds")
            ),
            "per_task_timeout_seconds": _optional_int(
                defaults.get("per_task_timeout_seconds")
            ),
        },
        "network_policy": {
            "description": str(defaults.get("network_policy", "")),
            "checkout_network_allowed": True,
            "setup_network_allowed": True,
            "baseline_validation_network_allowed": False,
            "candidate_validation_network_allowed": False,
        },
        "allowed_write_path_check": allowed_check.to_record(),
        "environment_blocker_label": repo_result.environment_blocker_label,
        "blocker_label": blocker_label,
        "preflight_status": "passed" if blocker_label == "none" else "blocked",
        "zero_hosted_usage_confirmed": True,
    }
    return row


def check_allowed_write_paths(
    allowed_write_paths: Sequence[str],
    *,
    candidate_paths: Sequence[str],
) -> AllowedWritePathCheck:
    """Check that candidate writes stay within task allowed paths."""

    allowed = tuple(_normalize_relative_path(path) for path in allowed_write_paths)
    candidates = tuple(_normalize_relative_path(path) for path in candidate_paths)
    violations = tuple(
        candidate
        for candidate in candidates
        if not any(_path_is_allowed(candidate, allowed_path) for allowed_path in allowed)
    )
    return AllowedWritePathCheck(
        status="failed" if violations else "passed",
        allowed_write_paths=allowed,
        candidate_paths=candidates,
        violations=violations,
    )


def run_subprocess_command(
    command: str,
    cwd: Path,
    timeout_seconds: int,
) -> PreflightCommandResult:
    """Run one shell command and normalize subprocess failures."""

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return PreflightCommandResult(
            command=command,
            cwd=str(cwd),
            timeout_seconds=timeout_seconds,
            returncode=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            status="timeout",
        )

    return PreflightCommandResult(
        command=command,
        cwd=str(cwd),
        timeout_seconds=timeout_seconds,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        status="passed" if completed.returncode == 0 else "failed",
    )


def write_real_repo_preflight_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write preflight rows to deterministic JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            validate_real_repo_preflight_row(row)
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def validate_real_repo_preflight_row(row: Mapping[str, object]) -> None:
    """Validate the stable surface consumed by later scoring gates."""

    if row.get("schema_version") != REAL_REPO_PREFLIGHT_SCHEMA_VERSION:
        raise ValueError("preflight row has unsupported schema_version")
    for field_name in (
        "repo_id",
        "checkout_ref",
        "checkout_command_results",
        "setup_command_results",
        "baseline_validation_command_results",
        "timeout_policy",
        "network_policy",
        "allowed_write_path_check",
        "blocker_label",
    ):
        if field_name not in row:
            raise ValueError(f"preflight row missing {field_name}")
    allowed_check = row["allowed_write_path_check"]
    if not isinstance(allowed_check, Mapping):
        raise ValueError("allowed_write_path_check must be an object")
    if allowed_check.get("status") not in {"passed", "failed"}:
        raise ValueError("allowed_write_path_check.status must be passed or failed")
    if row.get("blocker_label") not in {
        "none",
        "checkout_failed",
        "setup_failed",
        "baseline_validation_failed",
        "allowed_write_path_violation",
    }:
        raise ValueError("preflight row has unsupported blocker_label")


def _run_commands(
    commands: Sequence[str],
    *,
    cwd_sequence: Sequence[Path] | None,
    timeout_seconds: int,
    command_runner: CommandRunner,
    cwd: Path | None = None,
) -> tuple[PreflightCommandResult, ...]:
    results: list[PreflightCommandResult] = []
    for index, command in enumerate(commands):
        command_cwd = cwd_sequence[index] if cwd_sequence is not None else cwd
        if command_cwd is None:
            raise ValueError("command cwd is required")
        result = command_runner(command, command_cwd, timeout_seconds)
        results.append(result)
        if result.status != "passed":
            break
    return tuple(results)


def _has_failed_command(results: Sequence[PreflightCommandResult]) -> bool:
    return any(result.status != "passed" for result in results)


def _blocker_label(
    repo_result: RepoPreflightResult,
    allowed_check: AllowedWritePathCheck,
) -> str:
    if allowed_check.status == "failed":
        return "allowed_write_path_violation"
    return repo_result.environment_blocker_label


def _path_is_allowed(candidate: str, allowed_path: str) -> bool:
    if candidate == allowed_path:
        return True
    return candidate.startswith(f"{allowed_path.rstrip('/')}/")


def _normalize_relative_path(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"path must be repository-relative: {path}")
    normalized = pure.as_posix().strip("/")
    if not normalized or normalized == ".":
        raise ValueError("path must not be empty")
    return normalized


def _required_str(row: Mapping[str, object] | None, field: str) -> str:
    if row is None:
        raise ValueError(f"missing object for {field}")
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_sequence(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{field} entries must be non-empty strings")
        result.append(item)
    return tuple(result)


def _sequence(value: object, *, field: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a sequence")
    return tuple(value)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("timeout policy values must be integers")
    return value
