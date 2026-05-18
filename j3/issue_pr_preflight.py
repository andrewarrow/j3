"""Preflight runner for compact issue/PR replay rows."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import time
from collections import Counter
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
    runtime_seconds: float = 0.0

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
            "runtime_seconds": round(self.runtime_seconds, 3),
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

    @property
    def runtime_seconds(self) -> float:
        return sum(result.runtime_seconds for result in self.command_results)

    def to_record(self) -> dict[str, object]:
        row: dict[str, object] = {
            "schema_version": ISSUE_PR_PREFLIGHT_SCHEMA_VERSION,
            "record_kind": "issue_pr_replay_preflight_outcome",
            "replay_id": self.replay_id,
            "repo": self.repo,
            "repo_before_ref": dict(self.repo_before_ref),
            "validation_command": self.validation_command,
            "pre_edit": True,
            "status": self.status,
            "runtime_seconds": round(self.runtime_seconds, 3),
            "command_stages_reached": [result.name for result in self.command_results],
            "first_failed_stage": first_failed_stage(self.command_results),
            "command_results": [result.to_record() for result in self.command_results],
            "blocker_labels": list(self.blocker_labels),
            "residual_category": self.residual_category,
            "provenance": dict(self.provenance),
        }
        row["blocker_details"] = derive_issue_pr_blocker_details(row)
        return row


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


def select_issue_pr_replay_records(
    manifest: Mapping[str, object],
    *,
    replay_ids: Sequence[str] = (),
    limit: int | None = None,
) -> tuple[dict[str, object], ...]:
    """Select replay rows by id, or the manifest's first rows when ids are empty."""

    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("issue/PR replay manifest records must be a list")
    typed_records = tuple(record for record in records if isinstance(record, dict))
    if replay_ids:
        selected = tuple(
            select_issue_pr_replay_record(manifest, replay_id)
            for replay_id in replay_ids
        )
    else:
        selected = typed_records
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        selected = selected[:limit]
    return selected


def run_issue_pr_replay_preflight(
    *,
    manifest_path: Path,
    replay_id: str,
    workspace: Path,
    setup_command: str | None = DEFAULT_SETUP_COMMAND,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    clean_checkout: bool = True,
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
    if clean_checkout and checkout_dir.exists():
        shutil.rmtree(checkout_dir)
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


def run_issue_pr_replay_preflight_batch(
    *,
    manifest_path: Path,
    workspace: Path,
    replay_ids: Sequence[str] = (),
    limit: int | None = None,
    setup_command: str | None = DEFAULT_SETUP_COMMAND,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    clean_checkout: bool = True,
    runner: SubprocessRunner | None = None,
) -> tuple[IssuePrPreflightOutcome, ...]:
    """Run pre-edit preflight for a bounded batch of replay rows."""

    manifest = load_issue_pr_replay_manifest(manifest_path)
    records = select_issue_pr_replay_records(
        manifest,
        replay_ids=replay_ids,
        limit=limit,
    )
    return tuple(
        run_issue_pr_replay_preflight(
            manifest_path=manifest_path,
            replay_id=_required_str(record, "id", context="record"),
            workspace=workspace,
            setup_command=setup_command,
            timeout_seconds=timeout_seconds,
            clean_checkout=clean_checkout,
            runner=runner,
        )
        for record in records
    )


def first_failed_stage(command_results: Sequence[PreflightCommandResult]) -> str:
    """Return the first failed command stage, or none when all stages passed."""

    for result in command_results:
        if not result.passed:
            return result.name
    return "none"


def summarize_issue_pr_preflight_outcomes(
    outcomes: Sequence[IssuePrPreflightOutcome],
    *,
    outcome_path: Path | None = None,
    report_path: Path | None = None,
    batch_runtime_seconds: float | None = None,
) -> dict[str, object]:
    """Summarize status, blockers, residuals, runtimes, and reached stages."""

    rows = [outcome.to_record() for outcome in outcomes]
    return summarize_issue_pr_preflight_records(
        rows,
        outcome_path=outcome_path,
        report_path=report_path,
        batch_runtime_seconds=batch_runtime_seconds,
    )


def summarize_issue_pr_preflight_records(
    rows: Sequence[Mapping[str, object]],
    *,
    outcome_path: Path | None = None,
    report_path: Path | None = None,
    batch_runtime_seconds: float | None = None,
) -> dict[str, object]:
    """Summarize preflight records, including blocker drilldown fields."""

    status_counts = Counter(str(row["status"]) for row in rows)
    blocker_counts: Counter[str] = Counter()
    for row in rows:
        blocker_labels = _string_sequence(
            row.get("blocker_labels"),
            field="blocker_labels",
        )
        blocker_counts.update(blocker_labels or ("none",))
    residual_counts = Counter(str(row["residual_category"]) for row in rows)
    stage_counts = Counter(
        stage
        for row in rows
        for stage in _string_sequence(
            row.get("command_stages_reached"),
            field="command_stages_reached",
        )
    )
    first_failed_stage_counts = Counter(str(row["first_failed_stage"]) for row in rows)
    deferred_counts = Counter(
        label
        for row in rows
        for label in _string_sequence(
            _mapping(row.get("provenance"), field="provenance").get(
                "deferred_agent_residual_labels"
            ),
            field="deferred_agent_residual_labels",
        )
    )
    failure_family_counts = Counter(
        str(detail["failure_family"])
        for row in rows
        for detail in _detail_records(row)
        if detail.get("failure_family")
    )
    missing_prompt_field_counts = Counter(
        field
        for row in rows
        for detail in _detail_records(row)
        for field in _string_sequence(
            detail.get("missing_prompt_fields"),
            field="missing_prompt_fields",
        )
    )
    required_knowledge_counts = Counter(
        category
        for row in rows
        for detail in _detail_records(row)
        for category in _string_sequence(
            detail.get("required_knowledge_categories"),
            field="required_knowledge_categories",
        )
    )
    runtime_by_replay = {
        str(row["replay_id"]): round(float(row["runtime_seconds"]), 3) for row in rows
    }
    total_runtime = (
        round(batch_runtime_seconds, 3)
        if batch_runtime_seconds is not None
        else round(sum(runtime_by_replay.values()), 3)
    )
    return {
        "schema_version": ISSUE_PR_PREFLIGHT_SCHEMA_VERSION,
        "record_kind": "issue_pr_replay_preflight_summary",
        "outcome_path": (
            str(outcome_path.expanduser().resolve()) if outcome_path else None
        ),
        "report_path": str(report_path.expanduser().resolve()) if report_path else None,
        "row_count": len(rows),
        "replay_ids": [str(row["replay_id"]) for row in rows],
        "repo_counts": dict(sorted(Counter(str(row["repo"]) for row in rows).items())),
        "status_counts": dict(sorted(status_counts.items())),
        "blocker_label_counts": dict(sorted(blocker_counts.items())),
        "residual_category_counts": dict(sorted(residual_counts.items())),
        "runtime_seconds": total_runtime,
        "runtime_seconds_by_replay": runtime_by_replay,
        "command_stage_counts": dict(sorted(stage_counts.items())),
        "first_failed_stage_counts": dict(sorted(first_failed_stage_counts.items())),
        "deferred_agent_residual_label_counts": dict(sorted(deferred_counts.items())),
        "failure_family_counts": dict(sorted(failure_family_counts.items())),
        "missing_prompt_field_counts": dict(
            sorted(missing_prompt_field_counts.items())
        ),
        "required_knowledge_category_counts": dict(
            sorted(required_knowledge_counts.items())
        ),
        "pre_edit": True,
    }


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


def load_issue_pr_preflight_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Load existing preflight JSONL rows and add current blocker details."""

    resolved = path.expanduser().resolve()
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(
        resolved.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{resolved}:{line_number}: row must be an object")
        if row.get("record_kind") != "issue_pr_replay_preflight_outcome":
            raise ValueError(
                f"{resolved}:{line_number}: unsupported preflight record_kind"
            )
        rows.append(add_issue_pr_blocker_details(row))
    return tuple(rows)


def write_issue_pr_preflight_records_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write already-materialized preflight records to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(add_issue_pr_blocker_details(row), sort_keys=True))
            handle.write("\n")
    return resolved


def add_issue_pr_blocker_details(row: Mapping[str, object]) -> dict[str, object]:
    """Return a row with blocker_details derived from command and prompt metadata."""

    materialized = dict(row)
    materialized["blocker_details"] = derive_issue_pr_blocker_details(materialized)
    return materialized


def derive_issue_pr_blocker_details(
    row: Mapping[str, object],
) -> list[dict[str, object]]:
    """Build machine-readable pre-edit blocker details for one replay row."""

    details: list[dict[str, object]] = []
    blocker_labels = _string_sequence(row.get("blocker_labels"), field="blocker_labels")
    for label in blocker_labels:
        if label in {
            "validation_baseline_failed",
            "validation_recipe_partial",
            "prompt_spec_missing_validation_command",
        }:
            details.append(_validation_blocker_detail(row, label=label))
        elif label == "prompt_spec_ambiguous_or_incomplete":
            details.append(_prompt_spec_blocker_detail(row, label=label))
        elif label == "local_knowledge_required":
            details.append(_local_knowledge_blocker_detail(row, label=label))
        elif label.startswith("environment_"):
            details.append(_environment_blocker_detail(row, label=label))
        else:
            details.append(_generic_blocker_detail(row, label=label))
    return details


def write_issue_pr_preflight_report(
    outcomes: Sequence[IssuePrPreflightOutcome],
    path: Path,
    *,
    summary: Mapping[str, object] | None = None,
    title: str = "DATA-006 Issue/PR Mini Replay Preflight",
) -> Path:
    """Write a compact Markdown report for a preflight batch."""

    rows = [outcome.to_record() for outcome in outcomes]
    return write_issue_pr_preflight_records_report(
        rows,
        path,
        summary=summary,
        title=title,
    )


def write_issue_pr_preflight_records_report(
    rows: Sequence[Mapping[str, object]],
    path: Path,
    *,
    summary: Mapping[str, object] | None = None,
    title: str = "DATA-007 Issue/PR Replay Blocker Drilldown",
) -> Path:
    """Write a compact Markdown report from preflight records."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    materialized_rows = tuple(add_issue_pr_blocker_details(row) for row in rows)
    report_summary = dict(
        summary or summarize_issue_pr_preflight_records(materialized_rows)
    )
    deferred_counts = _json_inline(
        report_summary.get("deferred_agent_residual_label_counts", {})
    )
    lines = [
        f"# {title}",
        "",
        "Pre-edit replay preflight only; no candidate code edits were attempted.",
        "",
        "## Summary",
        "",
        f"- Rows: `{report_summary.get('row_count', 0)}`",
        f"- Status counts: `{_json_inline(report_summary.get('status_counts', {}))}`",
        "- Blocker labels: "
        f"`{_json_inline(report_summary.get('blocker_label_counts', {}))}`",
        "- Residual categories: "
        f"`{_json_inline(report_summary.get('residual_category_counts', {}))}`",
        f"- Runtime seconds: `{report_summary.get('runtime_seconds', 0)}`",
        "- Command stages reached: "
        f"`{_json_inline(report_summary.get('command_stage_counts', {}))}`",
        "- First failed stages: "
        f"`{_json_inline(report_summary.get('first_failed_stage_counts', {}))}`",
        f"- Deferred agent residual labels: `{deferred_counts}`",
        "- Failure families: "
        f"`{_json_inline(report_summary.get('failure_family_counts', {}))}`",
        "- Missing prompt fields: "
        f"`{_json_inline(report_summary.get('missing_prompt_field_counts', {}))}`",
        "- Required knowledge categories: "
        f"`{_json_inline(report_summary.get('required_knowledge_category_counts', {}))}`",
        "",
        "## Rows",
        "",
        "| Replay | Repo | Status | Blockers | Residual | "
        "First failed stage | Runtime |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in materialized_rows:
        blockers = ", ".join(
            _string_sequence(row.get("blocker_labels"), field="blocker_labels")
        ) or "none"
        lines.append(
            "| `{replay_id}` | `{repo}` | `{status}` | `{blockers}` | `{residual}` | "
            "`{stage}` | `{runtime}` |".format(
                replay_id=row["replay_id"],
                repo=row["repo"],
                status=row["status"],
                blockers=blockers,
                residual=row["residual_category"],
                stage=row["first_failed_stage"],
                runtime=row["runtime_seconds"],
            )
        )
    lines.extend(["", "## Blocker Drilldown", ""])
    for row in materialized_rows:
        for detail in _detail_records(row):
            lines.extend(_blocker_detail_markdown(row, detail))
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- JSONL: `{report_summary.get('outcome_path')}`",
        ]
    )
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for live issue/PR replay preflight batches."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--outcome", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--from-outcome-jsonl", type=Path)
    parser.add_argument("--replay-id", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--setup-command", default=DEFAULT_SETUP_COMMAND)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--no-clean-checkout", action="store_true")
    args = parser.parse_args(argv)

    if args.from_outcome_jsonl is not None:
        rows = load_issue_pr_preflight_jsonl(args.from_outcome_jsonl)
        outcome_path = write_issue_pr_preflight_records_jsonl(rows, args.outcome)
        summary = summarize_issue_pr_preflight_records(
            rows,
            outcome_path=outcome_path,
            report_path=args.report,
        )
        if args.report is not None:
            report_path = write_issue_pr_preflight_records_report(
                rows,
                args.report,
                summary=summary,
            )
            summary["report_path"] = str(report_path)
        print(json.dumps(summary, sort_keys=True))
        return 0

    if args.workspace is None:
        parser.error("--workspace is required unless --from-outcome-jsonl is used")

    setup_command = args.setup_command if args.setup_command else None
    started = time.monotonic()
    outcomes = run_issue_pr_replay_preflight_batch(
        manifest_path=args.manifest,
        workspace=args.workspace,
        replay_ids=tuple(args.replay_id),
        limit=args.limit,
        setup_command=setup_command,
        timeout_seconds=args.timeout_seconds,
        clean_checkout=not args.no_clean_checkout,
    )
    runtime_seconds = time.monotonic() - started
    outcome_path = write_issue_pr_preflight_jsonl(outcomes, args.outcome)
    summary = summarize_issue_pr_preflight_outcomes(
        outcomes,
        outcome_path=outcome_path,
        report_path=args.report,
        batch_runtime_seconds=runtime_seconds,
    )
    if args.report is not None:
        report_path = write_issue_pr_preflight_report(
            outcomes,
            args.report,
            summary=summary,
        )
        summary["report_path"] = str(report_path)
    print(json.dumps(summary, sort_keys=True))
    return 0


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
    started = time.monotonic()
    try:
        completed = runner(command, cwd, timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        runtime_seconds = time.monotonic() - started
        return PreflightCommandResult(
            name=name,
            command=command_text,
            cwd=str(cwd) if cwd is not None else None,
            exit_code=None,
            stdout=_optional_str(exc.stdout),
            stderr=_optional_str(exc.stderr),
            timed_out=True,
            runtime_seconds=runtime_seconds,
        )
    runtime_seconds = time.monotonic() - started
    return PreflightCommandResult(
        name=name,
        command=command_text,
        cwd=str(cwd) if cwd is not None else None,
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        runtime_seconds=runtime_seconds,
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
            "prompt_text": record.get("prompt_text"),
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
    safe_id = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in replay_id
    )
    return workspace.expanduser().resolve() / f"{safe_repo}-{safe_id}-{sha[:12]}"


def _command_text(command: Command) -> str:
    if isinstance(command, str):
        return command
    return shlex.join(str(part) for part in command)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _string_sequence(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return tuple(item for item in value if isinstance(item, str))


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


def _json_inline(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validation_blocker_detail(
    row: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    result = _first_failed_command_result(row)
    failure_family = _classify_command_failure(row, result)
    evidence = _command_failure_evidence(result)
    return {
        "blocker_label": label,
        "blocker_type": "validation",
        "failure_family": failure_family,
        "replay_id": row.get("replay_id"),
        "repo": row.get("repo"),
        "prompt_source": _prompt_source(row),
        "evidence_stage": result.get("name") or row.get("first_failed_stage"),
        "command": result.get("command") or row.get("validation_command"),
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out")),
        "evidence": evidence,
        "required_next_actions": _validation_next_actions(failure_family, evidence),
    }


def _environment_blocker_detail(
    row: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    result = _first_failed_command_result(row)
    failure_family = _classify_command_failure(row, result)
    evidence = _command_failure_evidence(result)
    return {
        "blocker_label": label,
        "blocker_type": "environment",
        "failure_family": failure_family,
        "replay_id": row.get("replay_id"),
        "repo": row.get("repo"),
        "prompt_source": _prompt_source(row),
        "evidence_stage": result.get("name") or row.get("first_failed_stage"),
        "command": result.get("command"),
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out")),
        "evidence": evidence,
        "required_next_actions": _environment_next_actions(failure_family),
    }


def _prompt_spec_blocker_detail(
    row: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    missing_fields = _missing_prompt_fields(row)
    return {
        "blocker_label": label,
        "blocker_type": "prompt_spec",
        "failure_family": "prompt_spec_incomplete",
        "replay_id": row.get("replay_id"),
        "repo": row.get("repo"),
        "prompt_source": _prompt_source(row),
        "accepted_change": _accepted_change(row),
        "available_prompt_text": _provenance(row).get("prompt_text"),
        "missing_prompt_fields": missing_fields,
        "required_next_actions": _prompt_spec_next_actions(row, missing_fields),
    }


def _local_knowledge_blocker_detail(
    row: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    categories = _required_knowledge_categories(row)
    return {
        "blocker_label": label,
        "blocker_type": "local_knowledge",
        "failure_family": "local_knowledge_missing",
        "replay_id": row.get("replay_id"),
        "repo": row.get("repo"),
        "prompt_source": _prompt_source(row),
        "accepted_change": _accepted_change(row),
        "required_knowledge_categories": categories,
        "required_next_actions": _local_knowledge_next_actions(row, categories),
    }


def _generic_blocker_detail(
    row: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    return {
        "blocker_label": label,
        "blocker_type": str(row.get("residual_category") or "unknown"),
        "failure_family": "unclassified_pre_edit_blocker",
        "replay_id": row.get("replay_id"),
        "repo": row.get("repo"),
        "prompt_source": _prompt_source(row),
        "required_next_actions": [
            "Add a typed blocker classifier for this pre-edit label before "
            "using the row as candidate-generation evidence."
        ],
    }


def _classify_command_failure(
    row: Mapping[str, object],
    result: Mapping[str, object],
) -> str:
    if bool(result.get("timed_out")):
        return "timeout"
    text = _command_output_text(result).lower()
    stage = str(result.get("name") or row.get("first_failed_stage") or "")
    exit_code = result.get("exit_code")
    if _looks_like_dependency_fixture_failure(text):
        return "dependency_fixture_setup_failure"
    if stage == "setup":
        return "dependency_setup_failure"
    if exit_code in {126, 127} or _looks_like_command_failure(text):
        return "command_failure"
    return "validation_recipe_failure"


def _looks_like_dependency_fixture_failure(text: str) -> bool:
    patterns = (
        "recursive dependency involving fixture",
        "fixture '",
        "fixture \"",
        "importerror while loading conftest",
        "modulenotfounderror",
        "no module named",
        "failed to import",
    )
    return any(pattern in text for pattern in patterns)


def _looks_like_command_failure(text: str) -> bool:
    patterns = (
        "command not found",
        "no such file or directory",
        "can't open file",
        "not recognized as an internal or external command",
    )
    return any(pattern in text for pattern in patterns)


def _command_failure_evidence(result: Mapping[str, object]) -> dict[str, object]:
    text = _command_output_text(result)
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    interesting = _interesting_failure_lines(lines)
    summary = interesting[0] if interesting else (lines[-1] if lines else "")
    source_location = _source_location_from_lines(lines)
    return {
        "summary": summary,
        "source_location": source_location,
        "lines": interesting[:4] if interesting else lines[-4:],
    }


def _interesting_failure_lines(lines: Sequence[str]) -> list[str]:
    needles = (
        "recursive dependency involving fixture",
        "fixture ",
        "ImportError",
        "ModuleNotFoundError",
        "No module named",
        "command not found",
        "No such file or directory",
        "ERROR ",
        "FAILED ",
    )
    interesting: list[str] = []
    seen: set[str] = set()
    for needle in needles:
        needle_lower = needle.lower()
        for line in lines:
            if needle_lower in line.lower() and line not in seen:
                interesting.append(line)
                seen.add(line)
    return interesting


def _source_location_from_lines(lines: Sequence[str]) -> str | None:
    for line in lines:
        match = re.search(r"(?P<path>[\w./-]+tests/[\w./-]+\.py):(?P<line>\d+)", line)
        if match:
            return f"{match.group('path')}:{match.group('line')}"
    return None


def _validation_next_actions(
    failure_family: str,
    evidence: Mapping[str, object],
) -> list[str]:
    if failure_family == "dependency_fixture_setup_failure":
        summary = str(evidence.get("summary") or "fixture/dependency setup failed")
        return [
            "Fix or replace the baseline validation recipe so it is hermetic "
            f"before candidate generation. Evidence: {summary}",
            "If the upstream test module depends on external pytest fixtures, "
            "install/configure those fixtures or select a focused test subset "
            "that does not fail during fixture setup.",
        ]
    if failure_family == "timeout":
        return [
            "Reduce the baseline validation command to a bounded focused subset "
            "or raise the timeout with a recorded runtime budget."
        ]
    if failure_family == "command_failure":
        return [
            "Fix the validation command path or executable before treating this "
            "row as edit-quality evidence."
        ]
    return [
        "Confirm whether the pre-edit baseline is expected to fail. If not, "
        "replace the validation recipe with a passing baseline command before "
        "attempting candidate edits."
    ]


def _environment_next_actions(failure_family: str) -> list[str]:
    if failure_family == "dependency_setup_failure":
        return [
            "Record the repository-specific dependency install command and rerun "
            "preflight until setup succeeds before baseline validation."
        ]
    if failure_family == "timeout":
        return [
            "Bound the checkout/setup command or raise the timeout with a "
            "documented runtime budget."
        ]
    return ["Fix the environment command before attempting issue/PR replay edits."]


def _missing_prompt_fields(row: Mapping[str, object]) -> list[str]:
    prompt_text = " ".join(
        str(value or "")
        for value in (
            _provenance(row).get("prompt_text"),
            _prompt_source(row).get("issue_title"),
            _prompt_source(row).get("pull_request_title"),
        )
    )
    missing = [
        "minimal_reproduction",
        "observed_behavior",
        "expected_behavior",
        "affected_api_symbol",
        "input_shape",
        "acceptance_test_shape",
    ]
    if "default_map" in prompt_text:
        missing.extend(
            [
                "default_map_mutation_timing",
                "multi_value_parameter_shape",
                "string_splitting_semantics",
            ]
        )
    if "semver" in prompt_text.lower():
        missing.extend(["non_string_default_type", "empty_string_check_scope"])
    return missing


def _prompt_spec_next_actions(
    row: Mapping[str, object],
    missing_fields: Sequence[str],
) -> list[str]:
    source = _prompt_source(row)
    issue = source.get("issue_number")
    pull = source.get("pull_request_number")
    return [
        "Fetch or read the issue and PR metadata for "
        f"issue #{issue} / PR #{pull}, then convert the prompt into a "
        f"structured spec with these missing fields: {', '.join(missing_fields)}.",
        "Do not generate candidates until the spec names the affected API, "
        "reproduction input, expected behavior, and focused acceptance test.",
    ]


def _required_knowledge_categories(row: Mapping[str, object]) -> list[str]:
    repo = str(row.get("repo") or "")
    text = " ".join(
        str(value or "")
        for value in (
            _provenance(row).get("prompt_text"),
            _prompt_source(row).get("issue_title"),
            _prompt_source(row).get("pull_request_title"),
        )
    ).lower()
    categories = [
        "repo_changed_file_context",
        "repo_test_pattern",
        "focused_validation_recipe",
    ]
    if repo == "pallets/click":
        categories.extend(
            [
                "click_parameter_default_handling",
                "click_type_conversion_semantics",
            ]
        )
    if "semver" in text or "non-string" in text or "empty string" in text:
        categories.extend(
            [
                "click_non_string_default_handling",
                "click_empty_string_check_semantics",
                "third_party_semver_version_reproduction",
            ]
        )
    if "default_map" in text:
        categories.extend(
            [
                "click_default_map_callback_semantics",
                "click_multi_value_parameter_defaults",
            ]
        )
    return list(dict.fromkeys(categories))


def _local_knowledge_next_actions(
    row: Mapping[str, object],
    categories: Sequence[str],
) -> list[str]:
    changed_files = _string_sequence(
        _accepted_change(row).get("changed_files"),
        field="changed_files",
    )
    return [
        "Acquire local knowledge records for "
        f"{', '.join(categories)} using the replay row's repo-before checkout "
        f"and changed-file context: {', '.join(changed_files) or 'unknown'}.",
        "Record provenance and split labels for those knowledge records before "
        "candidate generation or ranking uses this row.",
    ]


def _blocker_detail_markdown(
    row: Mapping[str, object],
    detail: Mapping[str, object],
) -> list[str]:
    replay_id = str(row.get("replay_id"))
    label = str(detail.get("blocker_label"))
    family = str(detail.get("failure_family"))
    lines = [f"### `{replay_id}` - `{label}`", ""]
    lines.append(f"- Family: `{family}`")
    if detail.get("evidence_stage"):
        lines.append(f"- Evidence stage: `{detail.get('evidence_stage')}`")
    evidence = detail.get("evidence")
    if isinstance(evidence, dict) and evidence.get("summary"):
        lines.append(f"- Evidence: `{evidence.get('summary')}`")
    missing_fields = _string_sequence(
        detail.get("missing_prompt_fields"),
        field="missing_prompt_fields",
    )
    if missing_fields:
        lines.append(f"- Missing prompt fields: `{_json_inline(list(missing_fields))}`")
    categories = _string_sequence(
        detail.get("required_knowledge_categories"),
        field="required_knowledge_categories",
    )
    if categories:
        lines.append(f"- Required knowledge: `{_json_inline(list(categories))}`")
    actions = _string_sequence(
        detail.get("required_next_actions"),
        field="required_next_actions",
    )
    for action in actions:
        lines.append(f"- Next: {action}")
    lines.append("")
    return lines


def _detail_records(row: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    value = row.get("blocker_details")
    if not isinstance(value, list):
        return ()
    return tuple(detail for detail in value if isinstance(detail, dict))


def _first_failed_command_result(row: Mapping[str, object]) -> Mapping[str, object]:
    value = row.get("command_results")
    if isinstance(value, list):
        for result in value:
            if isinstance(result, dict) and not bool(result.get("passed")):
                return result
    return {}


def _command_output_text(result: Mapping[str, object]) -> str:
    return "\n".join(
        part
        for part in (
            _optional_str(result.get("stdout")),
            _optional_str(result.get("stderr")),
        )
        if part
    )


def _provenance(row: Mapping[str, object]) -> Mapping[str, object]:
    value = row.get("provenance")
    if isinstance(value, dict):
        return value
    return {}


def _prompt_source(row: Mapping[str, object]) -> Mapping[str, object]:
    value = _provenance(row).get("prompt_source")
    if isinstance(value, dict):
        return value
    return {}


def _accepted_change(row: Mapping[str, object]) -> Mapping[str, object]:
    value = _provenance(row).get("accepted_change")
    if isinstance(value, dict):
        return value
    return {}


if __name__ == "__main__":
    raise SystemExit(main())
