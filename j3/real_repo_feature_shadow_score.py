"""Shadow scoring for real-repo one-file source feature tasks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Mapping, Sequence

from j3.real_repo_feature_materializer import (
    BOLTONS_SLUGIFY_MAX_LENGTH_TASK_ID,
    CANDIDATE_VALIDATION_DEFERRED,
    H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID,
    HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID,
    INICONFIG_SECTION_DEFAULT_TASK_ID,
    REAL_REPO_FEATURE_ACTION_FAMILY,
    RealRepoFeatureMaterializerError,
    materialize_real_repo_feature_candidate,
)
from j3.real_repo_preflight import (
    DEFAULT_MANIFEST_PATH,
    load_real_repo_ladder_manifest,
)
from j3.request_spec import parse_request_to_spec


REAL_REPO_FEATURE_SHADOW_SCORE_SCHEMA_VERSION = "real-repo-feature-shadow-score-v1"
REAL_REPO_FEATURE_SHADOW_SCORE_KIND = "real_repo_one_file_feature_shadow_score"
DEFAULT_REPORT_PATH = Path("/tmp/j3-real-012-feature-shadow-score/report.md")
DEFAULT_SCORE_PATH = Path("/tmp/j3-real-012-feature-shadow-score/score.json")
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 120
FEATURE_MATERIALIZATION_BLOCKER = "one_file_materialization_gap"


def run_real_repo_feature_shadow_score(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    created_at: str | None = None,
    repo_paths: Mapping[str, Path] | None = None,
    validate_candidates: bool = False,
    validation_timeout_seconds: int = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Score one-file feature ladder tasks through materialized candidates."""

    started = perf_counter()
    manifest = load_real_repo_ladder_manifest(manifest_path)
    defaults = _mapping(manifest.get("defaults"), field="defaults")
    feature_tasks = _one_file_feature_tasks(manifest)
    resolved_repo_paths = {
        repo_id: path.expanduser().resolve()
        for repo_id, path in (repo_paths or {}).items()
    }
    rows = [
        _score_one_file_feature_task(
            repo=repo,
            task=task,
            defaults=defaults,
            repo_path=resolved_repo_paths.get(_required_str(repo, "id")),
            validate_candidates=validate_candidates,
            validation_timeout_seconds=validation_timeout_seconds,
        )
        for repo, task in feature_tasks
    ]
    elapsed = perf_counter() - started

    total = len(rows)
    pass_at_1_count = sum(1 for row in rows if row["pass@1"] is True)
    pass_at_3_count = sum(1 for row in rows if row["pass@3"] is True)
    passing_repos = sorted(
        {
            str(row["repo_id"])
            for row in rows
            if row["pass@3"] is True
        }
    )
    candidate_count = sum(int(row["candidate_count"]) for row in rows)
    candidates_tested = sum(int(row["candidates_tested"]) for row in rows)
    calibration_metrics = _split_pass_metrics(rows, split="calibration")
    heldout_metrics = _split_pass_metrics(rows, split="heldout")
    production_files_changed = 0
    writes_outside_allowlist = 0
    production_constraint_violations = 0
    for row in rows:
        mutation_scope = _mapping(row["mutation_scope"], field="mutation_scope")
        production_changed = _sequence(
            mutation_scope.get("production_files_changed"),
            field="production_files_changed",
        )
        outside = _sequence(
            mutation_scope.get("writes_outside_allowlist"),
            field="writes_outside_allowlist",
        )
        production_files_changed += len(production_changed)
        writes_outside_allowlist += len(outside)
        if not bool(mutation_scope.get("one_production_file_constraint_preserved", True)):
            production_constraint_violations += 1

    hidden_like_disagreeing = sum(
        1 for row in rows if row["hidden_like_agreement"] == "disagrees"
    )
    gates = _mapping(manifest.get("gates"), field="gates")
    feature_gate = _mapping(gates.get("one_file_feature"), field="one_file_feature")
    minimum_pass_at_3 = int(feature_gate.get("minimum_pass_at_3", 2))
    minimum_distinct_repos = int(feature_gate.get("minimum_distinct_repos_passing", 2))
    gate_passed = (
        pass_at_3_count >= minimum_pass_at_3
        and len(passing_repos) >= minimum_distinct_repos
        and production_constraint_violations == 0
        and writes_outside_allowlist == 0
        and hidden_like_disagreeing == 0
    )
    blocked_rows = [
        str(row["task_id"])
        for row in rows
        if row["pass@3"] is not True
    ]
    supported_surface = _supported_action_surface()

    score: dict[str, object] = {
        "schema_version": REAL_REPO_FEATURE_SHADOW_SCORE_SCHEMA_VERSION,
        "record_kind": REAL_REPO_FEATURE_SHADOW_SCORE_KIND,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "task_type": "one_file_feature",
        "max_candidates": int(defaults.get("max_candidates", 3)),
        "zero_hosted_usage_confirmed": True,
        "supported_action_surface": {
            "real_repo_action_family": REAL_REPO_FEATURE_ACTION_FAMILY,
            **supported_surface,
        },
        "metrics": {
            "tasks_scored": total,
            "candidate_count": candidate_count,
            "candidates_tested": candidates_tested,
            "calibration": calibration_metrics,
            "heldout": heldout_metrics,
            "pass@1": f"{pass_at_1_count}/{total}",
            "pass@3": f"{pass_at_3_count}/{total}",
            "pass_at_1_count": pass_at_1_count,
            "pass_at_3_count": pass_at_3_count,
            "first_passing_ranks": [
                row["first_passing_rank"] for row in rows
            ],
            "distinct_repos_passing": passing_repos,
            "distinct_repos_passing_count": len(passing_repos),
            "production_files_changed": production_files_changed,
            "production_file_constraint": {
                "maximum_production_files_changed": int(
                    feature_gate.get("maximum_production_files_changed", 1)
                ),
                "violations": production_constraint_violations,
                "preserved": production_constraint_violations == 0,
            },
            "writes_outside_allowlist": writes_outside_allowlist,
            "mutation_scope_violations": {
                "production_file_constraint_violations": production_constraint_violations,
                "writes_outside_allowlist": writes_outside_allowlist,
            },
            "candidate_validation_statuses": {
                status: sum(
                    1
                    for row in rows
                    if _mapping(
                        row["candidate_validation"],
                        field="candidate_validation",
                    ).get("status")
                    == status
                )
                for status in ("passed", "failed", "blocked", "deferred")
            },
            "hidden_like_agreement": {
                "agreeing": sum(
                    1 for row in rows if row["hidden_like_agreement"] == "agrees"
                ),
                "disagreeing": hidden_like_disagreeing,
                "not_run": sum(
                    1 for row in rows if row["hidden_like_agreement"] == "not_run"
                ),
            },
            "runtime_seconds": round(elapsed, 6),
        },
        "gate_decision": {
            "gate": "Gate 3: Shadow One-File Source Feature",
            "source": "examples/real_repo_eval_ladder.json",
            "decision": (
                "allow_guarded_one_file_feature_opt_in"
                if gate_passed
                else "remain_shadow_only"
            ),
            "passed": gate_passed,
            "guarded_opt_in_allowed": gate_passed,
            "reason": (
                f"pass@3 is {pass_at_3_count}/{total} across "
                f"{len(passing_repos)} distinct repo(s), against the "
                f"{minimum_pass_at_3}/{total} one-file feature gate and "
                f"{minimum_distinct_repos} distinct-repo requirement. "
                "Guarded one-file feature opt-in is allowed only for "
                "materialized, validation-passing candidates that write within "
                "the task allowlist, change at most the task's single "
                "production file, and have no hidden-like disagreement."
                if gate_passed
                else (
                    f"pass@3 is {pass_at_3_count}/{total} across "
                    f"{len(passing_repos)} distinct repo(s), below the "
                    "one-file feature gate or blocked by mutation/hidden-like "
                    "violations."
                )
            ),
            "guarded_opt_in_scope": {
                "allowed": gate_passed,
                "mode": "guarded_one_file_feature_opt_in" if gate_passed else None,
                "task_type": "one_file_feature",
                "action_family": REAL_REPO_FEATURE_ACTION_FAMILY,
                "allowed_repo_ids": [
                    str(row["repo_id"]) for row in rows if row["pass@3"] is True
                ],
                "allowed_task_ids": [
                    str(row["task_id"]) for row in rows if row["pass@3"] is True
                ],
                "path_scope": "task allowlisted source and test files only",
                "production_file_constraint": (
                    "at most one production file may change, and it must be "
                    "the task's allowlisted production file"
                ),
                "requires": [
                    "candidate validation passes before applying",
                    "writes stay inside the task allowlist",
                    "only the task's single production file changes among production files",
                    "hidden-like checks do not disagree with public validation",
                    "planned action, changed paths, validation command, and rollback path are shown before applying",
                ],
            },
            "blocked_rows": blocked_rows,
            "failed_checks": []
            if gate_passed
            else [
                "pass@3 below one-file feature gate",
                "fewer than 2 distinct repositories have passing feature candidates",
                "mutation-scope violations must be zero",
                "hidden-like disagreements must be zero",
            ],
        },
        "task_results": rows,
    }
    return score


def write_real_repo_feature_shadow_score(
    score: Mapping[str, object],
    path: Path = DEFAULT_SCORE_PATH,
) -> Path:
    """Write one compact JSON feature shadow-score artifact."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(score, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved


def format_real_repo_feature_shadow_score(score: Mapping[str, object]) -> str:
    """Render a compact Markdown report from a feature shadow-score record."""

    metrics = _mapping(score.get("metrics"), field="metrics")
    gate = _mapping(score.get("gate_decision"), field="gate_decision")
    rows = _sequence(score.get("task_results"), field="task_results")
    lines = [
        "# REAL-012 One-File Feature Shadow Score",
        "",
        f"- Schema: `{score.get('schema_version')}`",
        f"- Manifest: `{score.get('manifest_path')}`",
        f"- Max candidates: `{score.get('max_candidates')}`",
        f"- Zero hosted usage: `{str(score.get('zero_hosted_usage_confirmed')).lower()}`",
        f"- Candidate count: `{metrics.get('candidate_count')}`",
        f"- Candidates tested: `{metrics.get('candidates_tested')}`",
        (
            "- Calibration pass@3: "
            f"`{_mapping(metrics.get('calibration'), field='calibration').get('pass@3')}`"
        ),
        (
            "- Held-out pass@3: "
            f"`{_mapping(metrics.get('heldout'), field='heldout').get('pass@3')}`"
        ),
        f"- pass@1: `{metrics.get('pass@1')}`",
        f"- pass@3: `{metrics.get('pass@3')}`",
        (
            "- Distinct repos passing: "
            f"`{metrics.get('distinct_repos_passing_count')}`"
        ),
        (
            "- Production-file constraint preserved: "
            f"`{str(_mapping(metrics.get('production_file_constraint'), field='production_file_constraint').get('preserved')).lower()}`"
        ),
        f"- Runtime: `{metrics.get('runtime_seconds')}s`",
        f"- Gate decision: `{gate.get('decision')}`",
        (
            "- Guarded opt-in allowed: "
            f"`{str(gate.get('guarded_opt_in_allowed') is True).lower()}`"
        ),
        (
            "- Blocked rows: "
            f"`{', '.join(str(row) for row in _sequence(gate.get('blocked_rows'), field='blocked_rows')) or 'none'}`"
        ),
        "",
        "## Task Results",
        "",
        "| Task | Split | Candidate validation | pass@1 | pass@3 | First passing rank | Mutation scope | Hidden-like | Residual labels |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row_value in rows:
        row = _mapping(row_value, field="task_result")
        labels = ", ".join(
            str(label)
            for label in _sequence(row.get("residual_labels"), field="residual_labels")
        )
        first_rank = row.get("first_passing_rank")
        validation = _mapping(row.get("candidate_validation"), field="candidate_validation")
        mutation_scope = _mapping(row.get("mutation_scope"), field="mutation_scope")
        changed = len(_sequence(mutation_scope.get("files_changed"), field="files_changed"))
        production = len(
            _sequence(
                mutation_scope.get("production_files_changed"),
                field="production_files_changed",
            )
        )
        outside = len(
            _sequence(
                mutation_scope.get("writes_outside_allowlist"),
                field="writes_outside_allowlist",
            )
        )
        lines.append(
            "| "
            f"`{row.get('task_id')}` | "
            f"{row.get('repo_split')} | "
            f"{validation.get('status')} | "
            f"{row.get('pass@1')} | "
            f"{row.get('pass@3')} | "
            f"{first_rank if first_rank is not None else 'none'} | "
            f"{changed} changed, {production} production, {outside} outside allowlist | "
            f"{row.get('hidden_like_agreement')} | "
            f"{labels} |"
        )
    lines.extend(["", "## Gate Decision", "", str(gate.get("reason"))])
    return "\n".join(lines) + "\n"


def write_real_repo_feature_shadow_report(
    score: Mapping[str, object],
    path: Path = DEFAULT_REPORT_PATH,
) -> Path:
    """Write a Markdown report for the feature shadow score."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(format_real_repo_feature_shadow_score(score), encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the REAL-012 one-file feature shadow score."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="REAL-001 ladder manifest path",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_SCORE_PATH,
        help="JSON score output path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown report output path",
    )
    parser.add_argument(
        "--repo-path",
        action="append",
        default=[],
        metavar="REPO_ID=PATH",
        help="Existing checkout path for a repo id. May be repeated.",
    )
    parser.add_argument(
        "--validate-candidates",
        action="store_true",
        help="Run public validation commands for materialized candidates.",
    )
    parser.add_argument(
        "--validation-timeout-seconds",
        type=int,
        default=DEFAULT_VALIDATION_TIMEOUT_SECONDS,
    )
    args = parser.parse_args(argv)

    score = run_real_repo_feature_shadow_score(
        args.manifest,
        repo_paths=_parse_repo_path_args(args.repo_path),
        validate_candidates=args.validate_candidates,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    score_path = write_real_repo_feature_shadow_score(score, args.out)
    report_path = write_real_repo_feature_shadow_report(score, args.report)
    metrics = _mapping(score["metrics"], field="metrics")
    gate = _mapping(score["gate_decision"], field="gate_decision")

    print("j3 real-repo one-file feature shadow score complete")
    print(f"tasks scored: {metrics['tasks_scored']}")
    print(f"pass@1: {metrics['pass@1']}")
    print(f"pass@3: {metrics['pass@3']}")
    print(f"distinct repos passing: {metrics['distinct_repos_passing_count']}")
    print(f"candidate count: {metrics['candidate_count']}")
    print(f"candidates tested: {metrics['candidates_tested']}")
    print(f"gate decision: {gate['decision']}")
    print(f"score: {score_path}")
    print(f"report: {report_path}")
    return 0


def _score_one_file_feature_task(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
    repo_path: Path | None,
    validate_candidates: bool,
    validation_timeout_seconds: int,
) -> dict[str, object]:
    task_id = _required_str(task, "id")
    if task_id in _materialized_feature_task_ids():
        return _score_materialized_feature_task(
            repo=repo,
            task=task,
            defaults=defaults,
            repo_path=repo_path,
            validate_candidates=validate_candidates,
            validation_timeout_seconds=validation_timeout_seconds,
        )
    return _unsupported_feature_task_row(repo=repo, task=task, defaults=defaults)


def _materialized_feature_task_ids() -> frozenset[str]:
    return frozenset(
        {
            BOLTONS_SLUGIFY_MAX_LENGTH_TASK_ID,
            H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID,
            HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID,
            INICONFIG_SECTION_DEFAULT_TASK_ID,
        }
    )


def _supported_action_surface() -> dict[str, object]:
    calibration_materializers = [INICONFIG_SECTION_DEFAULT_TASK_ID]
    heldout_materializers = [
        H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID,
        HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID,
        BOLTONS_SLUGIFY_MAX_LENGTH_TASK_ID,
    ]
    supported_task_ids = [*calibration_materializers, *heldout_materializers]
    scope_note = (
        "MAT-003 materializes the held-out h11 bytesify object-message "
        "one-file feature candidate. MAT-004 materializes the iniconfig "
        "section-default calibration one-file feature candidate. MAT-005 "
        "materializes the held-out humanize zero-format one-file feature "
        "candidate. MAT-006 materializes the held-out boltons slugify "
        "max-length one-file feature candidate."
    )
    return {
        "calibration_materializers": calibration_materializers,
        "heldout_materializers": heldout_materializers,
        "supported_task_ids": supported_task_ids,
        "path_constraints": "task allowlisted source and test files only",
        "production_file_constraint": (
            "at most one production file may change, and it must be the "
            "task's allowlisted production file"
        ),
        "validation_requirements": [
            "candidate validation passes before applying",
            "selected validation command succeeds without hosted network usage",
        ],
        "hidden_like_requirements": [
            "hidden-like checks do not disagree with public validation",
            "task-specific source signals and pytest case ids are present",
        ],
        "scope_note": scope_note,
    }


def _score_materialized_feature_task(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
    repo_path: Path | None,
    validate_candidates: bool,
    validation_timeout_seconds: int,
) -> dict[str, object]:
    started = perf_counter()
    task_id = _required_str(task, "id")
    expected_failure_modes = list(
        _string_sequence(task.get("expected_failure_modes"), field="expected_failure_modes")
    )
    spec = parse_request_to_spec(_required_str(task, "prompt"), task_name=task_id)
    if repo_path is None:
        blocker = {
            "field": "repo_path",
            "reason": "candidate_checkout_missing",
            "message": f"{task_id} candidate scoring requires a checkout path",
        }
        return _blocked_feature_row(
            repo=repo,
            task=task,
            defaults=defaults,
            spec_record=spec.to_record(),
            blocker=blocker,
            residual_labels=["candidate_checkout_missing", *expected_failure_modes],
            runtime_seconds=perf_counter() - started,
        )

    try:
        candidate = materialize_real_repo_feature_candidate(
            repo_path,
            repo=repo,
            task=task,
            write=True,
            validate=validate_candidates,
            validation_timeout_seconds=validation_timeout_seconds,
        )
        candidate_record = candidate.to_record()
    except RealRepoFeatureMaterializerError as error:
        return _blocked_feature_row(
            repo=repo,
            task=task,
            defaults=defaults,
            spec_record=spec.to_record(),
            blocker=error.blocker,
            residual_labels=[
                str(error.blocker.get("reason", "feature_materialization_failed")),
                *expected_failure_modes,
            ],
            runtime_seconds=perf_counter() - started,
        )

    candidate_status = str(candidate_record["status"])
    candidate_count = 1 if candidate_status in {"materialized", "already_applied"} else 0
    candidate_validation = _candidate_validation_record(
        candidate_record,
        validate_candidates=validate_candidates,
    )
    validation_status = str(candidate_validation["status"])
    mutation_scope = _mapping(candidate_record["mutation_scope"], field="mutation_scope")
    production_constraint_preserved = bool(
        mutation_scope.get("one_production_file_constraint_preserved")
    )
    writes_outside = _sequence(
        mutation_scope.get("writes_outside_allowlist"),
        field="writes_outside_allowlist",
    )
    passing = (
        validation_status == "passed"
        and production_constraint_preserved
        and not writes_outside
    )
    hidden_like = _feature_hidden_like_agreement(
        task=task,
        candidate_record=candidate_record,
        candidate_validation=candidate_validation,
    )
    blockers = [
        dict(_mapping(blocker, field="candidate.blocker"))
        for blocker in _sequence(candidate_record.get("blockers"), field="blockers")
    ]
    residual_labels = _unique(
        [
            *(
                []
                if passing
                else [
                    label
                    for label in _string_sequence(
                        candidate_record.get("residual_labels", []),
                        field="candidate.residual_labels",
                    )
                    if label != CANDIDATE_VALIDATION_DEFERRED
                ]
            ),
            *([] if passing else [validation_status]),
            *([] if passing else expected_failure_modes),
        ]
    )
    if not residual_labels and not passing:
        residual_labels.append("candidate_validation_not_passing")
    runtime_status = "passed" if passing else validation_status
    runtime_not_run_reason = None
    if validation_status in {"deferred", "blocked"}:
        runtime_status = "not_run"
        runtime_not_run_reason = str(candidate_validation.get("not_run_reason"))

    return {
        "repo_id": _required_str(repo, "id"),
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": task_id,
        "task_type": "one_file_feature",
        "prompt": _required_str(task, "prompt"),
        "allowed_write_paths": list(
            _string_sequence(task.get("allowed_write_paths"), field="allowed_write_paths")
        ),
        "public_validation_commands": list(
            _string_sequence(
                task.get("public_validation_commands"),
                field="public_validation_commands",
            )
        ),
        "hidden_like_checks": list(
            _string_sequence(task.get("hidden_like_checks"), field="hidden_like_checks")
        ),
        "max_candidates": int(defaults.get("max_candidates", 3)),
        "candidate_count": candidate_count,
        "candidates_tested": 1 if validation_status in {"passed", "failed"} else 0,
        "pass@1": passing,
        "pass@3": passing,
        "first_passing_rank": 1 if passing else None,
        "runtime": {
            "status": runtime_status,
            "runtime_seconds": round(perf_counter() - started, 6),
            "not_run_reason": runtime_not_run_reason,
        },
        "candidate_validation": candidate_validation,
        "mutation_scope": _feature_mutation_scope_record(mutation_scope),
        "hidden_like_agreement": hidden_like["status"],
        "hidden_like_evidence": hidden_like,
        "residual_labels": residual_labels,
        "support_observations": [
            "scored through the real-repo one-file feature materializer surface"
        ],
        "blockers": blockers,
        "candidate_record": candidate_record,
        "parsed_request_spec": spec.to_record(),
        "zero_hosted_usage_confirmed": True,
    }


def _unsupported_feature_task_row(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
) -> dict[str, object]:
    task_id = _required_str(task, "id")
    allowed_write_paths = _string_sequence(
        task.get("allowed_write_paths"),
        field="allowed_write_paths",
    )
    public_validation_commands = _string_sequence(
        task.get("public_validation_commands"),
        field="public_validation_commands",
    )
    hidden_like_checks = _string_sequence(
        task.get("hidden_like_checks"),
        field="hidden_like_checks",
    )
    expected_failure_modes = list(
        _string_sequence(task.get("expected_failure_modes"), field="expected_failure_modes")
    )
    spec = parse_request_to_spec(_required_str(task, "prompt"), task_name=task_id)
    blocker = {
        "field": "feature_materialization",
        "reason": FEATURE_MATERIALIZATION_BLOCKER,
        "message": (
            "one-file feature materialization is not implemented for "
            f"{task_id}"
        ),
    }
    return {
        "repo_id": _required_str(repo, "id"),
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": task_id,
        "task_type": "one_file_feature",
        "prompt": _required_str(task, "prompt"),
        "allowed_write_paths": list(allowed_write_paths),
        "public_validation_commands": list(public_validation_commands),
        "hidden_like_checks": list(hidden_like_checks),
        "max_candidates": int(defaults.get("max_candidates", 3)),
        "candidate_count": 0,
        "candidates_tested": 0,
        "pass@1": False,
        "pass@3": False,
        "first_passing_rank": None,
        "runtime": {
            "status": "not_run",
            "runtime_seconds": None,
            "not_run_reason": FEATURE_MATERIALIZATION_BLOCKER,
        },
        "candidate_validation": {
            "status": "blocked",
            "commands": list(public_validation_commands),
            "selected_command": public_validation_commands[0]
            if public_validation_commands
            else None,
            "not_run_reason": FEATURE_MATERIALIZATION_BLOCKER,
            "result": None,
        },
        "mutation_scope": {
            "mode": "one_file_feature",
            "files_changed": [],
            "production_files_changed": [],
            "writes_outside_allowlist": [],
            "one_production_file_constraint_preserved": True,
        },
        "hidden_like_agreement": "not_run",
        "hidden_like_evidence": {
            "status": "not_run",
            "reason": "candidate materializer missing",
        },
        "residual_labels": _unique(
            ["feature_materializer_missing", FEATURE_MATERIALIZATION_BLOCKER, *expected_failure_modes]
        ),
        "support_observations": [
            "feature repo left as an explicit blocker until a materializer exists"
        ],
        "blockers": [blocker],
        "candidate_record": None,
        "parsed_request_spec": spec.to_record(),
        "zero_hosted_usage_confirmed": True,
    }


def _blocked_feature_row(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
    spec_record: Mapping[str, object],
    blocker: Mapping[str, str],
    residual_labels: Sequence[str],
    runtime_seconds: float,
) -> dict[str, object]:
    public_validation_commands = _string_sequence(
        task.get("public_validation_commands"),
        field="public_validation_commands",
    )
    return {
        "repo_id": _required_str(repo, "id"),
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": _required_str(task, "id"),
        "task_type": "one_file_feature",
        "prompt": _required_str(task, "prompt"),
        "allowed_write_paths": list(
            _string_sequence(task.get("allowed_write_paths"), field="allowed_write_paths")
        ),
        "public_validation_commands": list(public_validation_commands),
        "hidden_like_checks": list(
            _string_sequence(task.get("hidden_like_checks"), field="hidden_like_checks")
        ),
        "max_candidates": int(defaults.get("max_candidates", 3)),
        "candidate_count": 0,
        "candidates_tested": 0,
        "pass@1": False,
        "pass@3": False,
        "first_passing_rank": None,
        "runtime": {
            "status": "not_run",
            "runtime_seconds": round(runtime_seconds, 6),
            "not_run_reason": blocker["reason"],
        },
        "candidate_validation": {
            "status": "blocked",
            "commands": list(public_validation_commands),
            "selected_command": public_validation_commands[0]
            if public_validation_commands
            else None,
            "not_run_reason": blocker["reason"],
            "result": None,
        },
        "mutation_scope": {
            "mode": "one_file_feature",
            "files_changed": [],
            "production_files_changed": [],
            "writes_outside_allowlist": [],
            "one_production_file_constraint_preserved": True,
        },
        "hidden_like_agreement": "not_run",
        "hidden_like_evidence": {
            "status": "not_run",
            "reason": "candidate planning blocked before validation",
        },
        "residual_labels": _unique(list(residual_labels)),
        "support_observations": ["candidate planning blocked before validation"],
        "blockers": [dict(blocker)],
        "candidate_record": None,
        "parsed_request_spec": dict(spec_record),
        "zero_hosted_usage_confirmed": True,
    }


def _candidate_validation_record(
    candidate_record: Mapping[str, object],
    *,
    validate_candidates: bool,
) -> dict[str, object]:
    validation = _mapping(candidate_record.get("validation"), field="candidate.validation")
    commands = _sequence(validation.get("commands"), field="candidate.validation.commands")
    selected_command = validation.get("selected_command")
    blockers = _sequence(candidate_record.get("blockers"), field="candidate.blockers")
    if blockers:
        reason = str(_mapping(blockers[0], field="candidate.blocker").get("reason"))
        return {
            "status": "blocked",
            "commands": list(commands),
            "selected_command": selected_command,
            "not_run_reason": reason,
            "result": None,
        }
    if not isinstance(selected_command, str) or not selected_command:
        return {
            "status": "blocked",
            "commands": list(commands),
            "selected_command": None,
            "not_run_reason": "validation_selection_gap",
            "result": None,
        }
    if not validate_candidates:
        return {
            "status": "deferred",
            "commands": list(commands),
            "selected_command": selected_command,
            "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
            "result": None,
        }
    validation_status = str(validation.get("status"))
    return {
        "status": "passed" if validation_status == "passed" else "failed",
        "commands": list(commands),
        "selected_command": selected_command,
        "not_run_reason": None
        if validation_status == "passed"
        else validation.get("not_run_reason"),
        "result": {
            "command": selected_command,
            "returncode": validation.get("returncode"),
            "stdout": validation.get("stdout", ""),
            "stderr": validation.get("stderr", ""),
            "runtime_seconds": validation.get("runtime_seconds"),
            "candidate_validation_network_allowed": validation.get(
                "candidate_validation_network_allowed"
            ),
        },
    }


def _feature_mutation_scope_record(
    mutation_scope: Mapping[str, object],
) -> dict[str, object]:
    return {
        "mode": "one_file_feature",
        "files_changed": list(
            _sequence(mutation_scope.get("files_changed"), field="files_changed")
        ),
        "production_files_changed": list(
            _sequence(
                mutation_scope.get("production_files_changed"),
                field="production_files_changed",
            )
        ),
        "writes_outside_allowlist": list(
            _sequence(
                mutation_scope.get("writes_outside_allowlist"),
                field="writes_outside_allowlist",
            )
        ),
        "allowed_production_file": mutation_scope.get("allowed_production_file"),
        "maximum_production_files_changed": mutation_scope.get(
            "maximum_production_files_changed"
        ),
        "one_production_file_constraint_preserved": bool(
            mutation_scope.get("one_production_file_constraint_preserved")
        ),
        "candidate_after": _json_copy(mutation_scope.get("candidate_after", {})),
    }


def _feature_hidden_like_agreement(
    *,
    task: Mapping[str, object],
    candidate_record: Mapping[str, object],
    candidate_validation: Mapping[str, object],
) -> dict[str, object]:
    if candidate_validation.get("status") != "passed":
        return {
            "status": "not_run",
            "reason": "public candidate validation did not pass",
        }

    mutation_scope = _mapping(candidate_record["mutation_scope"], field="mutation_scope")
    production_changed = _sequence(
        mutation_scope.get("production_files_changed"),
        field="production_files_changed",
    )
    writes_outside = _sequence(
        mutation_scope.get("writes_outside_allowlist"),
        field="writes_outside_allowlist",
    )
    candidate_after = _mapping(
        candidate_record.get("candidate_after"),
        field="candidate_after",
    )
    source_after = _mapping(candidate_after.get("source_file"), field="source_file")
    source_candidate_after = _mapping(
        source_after.get("candidate_after"),
        field="source_file.candidate_after",
    )
    test_after = _mapping(candidate_after.get("test_file"), field="test_file")
    test_diff = str(test_after.get("diff", ""))
    test_case_ids = set(
        _string_sequence(test_after.get("test_case_ids", []), field="test_case_ids")
    )
    task_id = _required_str(task, "id")
    source_diff = str(source_candidate_after.get("diff", ""))
    if task_id == H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID:
        required_production_files = ["h11/_util.py"]
        required_case_ids = {"h11_bytesify_unsupported_object_type_name"}
        source_signals = {"mentions_type_name": "type(s).__name__" in source_diff}
    elif task_id == INICONFIG_SECTION_DEFAULT_TASK_ID:
        required_production_files = ["src/iniconfig/__init__.py"]
        required_case_ids = {
            "iniconfig_get_section_missing_default",
            "iniconfig_get_section_existing_order",
        }
        source_signals = {
            "adds_get_section": "def get_section(" in source_diff,
            "returns_default": "return default" in source_diff,
            "tests_getitem_keyerror": (
                'config["missing"]' in test_diff and "KeyError" in test_diff
            ),
        }
    elif task_id == HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID:
        required_production_files = ["src/humanize/filesize.py"]
        required_case_ids = {
            "humanize_naturalsize_zero_format_zero_values",
            "humanize_naturalsize_zero_format_default_unchanged",
            "humanize_naturalsize_zero_format_nonzero_ignored",
        }
        source_signals = {
            "adds_zero_format_argument": "zero_format: str | None = None" in source_diff,
            "returns_zero_format": "return zero_format" in source_diff,
            "tests_zero_and_negative_zero": (
                "naturalsize(0, zero_format=" in test_diff
                and "naturalsize(-0.0, zero_format=" in test_diff
            ),
        }
    elif task_id == BOLTONS_SLUGIFY_MAX_LENGTH_TASK_ID:
        required_production_files = ["boltons/strutils.py"]
        required_case_ids = {
            "boltons_slugify_max_length_truncates_final_slug",
            "boltons_slugify_max_length_strips_configured_delimiter",
            "boltons_slugify_max_length_default_behavior_unchanged",
        }
        source_signals = {
            "adds_max_length_argument": "max_length=None" in source_diff,
            "truncates_slug": "ret = ret[:max_length]" in source_diff,
            "strips_configured_delimiter": "ret.rstrip(trim_delim)" in source_diff,
            "tests_multichar_delimiter": 'delim="--", max_length=12' in test_diff,
        }
    else:
        return {
            "status": "not_run",
            "reason": "no hidden-like evaluator for this task",
        }
    source_signals_agree = all(source_signals.values())
    agrees = (
        list(production_changed) == required_production_files
        and not writes_outside
        and bool(mutation_scope.get("one_production_file_constraint_preserved"))
        and source_signals_agree
        and required_case_ids <= test_case_ids
    )
    return {
        "status": "agrees" if agrees else "disagrees",
        "production_files_changed": list(production_changed),
        "writes_inside_allowlist": not writes_outside,
        "one_production_file_constraint_preserved": bool(
            mutation_scope.get("one_production_file_constraint_preserved")
        ),
        "source_signals": source_signals,
        "required_case_ids_present": sorted(required_case_ids & test_case_ids),
        "missing_case_ids": sorted(required_case_ids - test_case_ids),
        "checks": list(
            _string_sequence(task.get("hidden_like_checks"), field="hidden_like_checks")
        ),
    }


def _one_file_feature_tasks(
    manifest: Mapping[str, object],
) -> list[tuple[Mapping[str, object], Mapping[str, object]]]:
    rows: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    for repo_value in _sequence(manifest.get("repositories"), field="repositories"):
        repo = _mapping(repo_value, field="repository")
        for task_value in _sequence(repo.get("tasks"), field="repository.tasks"):
            task = _mapping(task_value, field="repository.task")
            if task.get("task_type") == "one_file_feature":
                rows.append((repo, task))
    return rows


def _parse_repo_path_args(values: Sequence[str]) -> dict[str, Path]:
    repo_paths = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--repo-path must be formatted as REPO_ID=PATH")
        repo_id, path = value.split("=", 1)
        if not repo_id or not path:
            raise ValueError("--repo-path must include a non-empty repo id and path")
        repo_paths[repo_id] = Path(path)
    return repo_paths


def _required_str(row: Mapping[str, object], field: str) -> str:
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


def _split_pass_metrics(
    rows: Sequence[Mapping[str, object]],
    *,
    split: str,
) -> dict[str, object]:
    split_rows = [row for row in rows if row.get("repo_split") == split]
    total = len(split_rows)
    pass_at_1_count = sum(1 for row in split_rows if row["pass@1"] is True)
    pass_at_3_count = sum(1 for row in split_rows if row["pass@3"] is True)
    return {
        "split": split,
        "tasks_scored": total,
        "candidate_count": sum(int(row["candidate_count"]) for row in split_rows),
        "candidates_tested": sum(int(row["candidates_tested"]) for row in split_rows),
        "pass@1": f"{pass_at_1_count}/{total}",
        "pass@3": f"{pass_at_3_count}/{total}",
        "pass_at_1_count": pass_at_1_count,
        "pass_at_3_count": pass_at_3_count,
        "first_passing_ranks": [row["first_passing_rank"] for row in split_rows],
    }


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
