"""Shadow scoring for the first real-repo tests-only product wedge."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Callable, Mapping, Sequence

from j3.existing_repo_tests import (
    SLUGIFY_SOURCE,
    SLUGIFY_TESTS,
    SLUGIFY_FEATURES,
)
from j3.local_knowledge import extract_local_knowledge_records
from j3.real_repo_preflight import (
    DEFAULT_MANIFEST_PATH,
    load_real_repo_ladder_manifest,
)
from j3.real_repo_tests_planner import (
    CANDIDATE_VALIDATION_DEFERRED,
    H11_BYTESIFY_MEMORYVIEW_TASK_ID,
    HUMANIZE_NATURALSIZE_NEGATIVE_STRINGS_TASK_ID,
    INICONFIG_PARSE_COMMENTS_TASK_ID,
    REAL_REPO_TESTS_ACTION_FAMILY,
    TEST_CASE_MATERIALIZATION_BLOCKER,
    RealRepoTestsPlannerError,
    blocker_from_error,
    plan_real_repo_tests_only_candidate,
)
from j3.request_spec import parse_request_to_spec


REAL_REPO_TESTS_SHADOW_SCORE_SCHEMA_VERSION = "real-repo-tests-shadow-score-v1"
REAL_REPO_TESTS_SHADOW_SCORE_KIND = "real_repo_tests_only_shadow_score"
SUPPORTED_ACTION_FAMILY = "add_existing_repo_tests"
SUPPORTED_DOMAIN = "text_slugify"
SUPPORTED_SOURCE_FILES = (SLUGIFY_SOURCE,)
SUPPORTED_TARGET_TEST_FILES = (SLUGIFY_TESTS,)
SUPPORTED_FEATURES = tuple(SLUGIFY_FEATURES)
DEFAULT_SCORE_PATH = Path("/tmp/j3-real-008-tests-only-shadow-score/score.json")
DEFAULT_REPORT_PATH = Path("/tmp/j3-real-008-tests-only-shadow-score/report.md")
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 120
MATERIALIZED_TESTS_ONLY_TASK_IDS = frozenset(
    {
        INICONFIG_PARSE_COMMENTS_TASK_ID,
        H11_BYTESIFY_MEMORYVIEW_TASK_ID,
        HUMANIZE_NATURALSIZE_NEGATIVE_STRINGS_TASK_ID,
    }
)

ValidationRunner = Callable[[str, Path, int], "CandidateValidationResult"]


@dataclass(frozen=True, slots=True)
class CandidateValidationResult:
    """Serializable result for one materialized candidate validation command."""

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


def run_real_repo_tests_only_shadow_score(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    created_at: str | None = None,
    repo_paths: Mapping[str, Path] | None = None,
    validate_candidates: bool = False,
    validation_timeout_seconds: int = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
    validation_runner: ValidationRunner | None = None,
) -> dict[str, object]:
    """Score current tests-only wedge coverage against REAL-001 tasks.

    The ``iniconfig`` calibration row and available held-out rows are scored
    through the real-repo tests planner when checkout paths are supplied. Rows
    without materializers stay as explicit machine-readable blockers.
    """

    started = perf_counter()
    manifest = load_real_repo_ladder_manifest(manifest_path)
    defaults = _mapping(manifest.get("defaults"), field="defaults")
    tests_only_tasks = _tests_only_tasks(manifest)
    resolved_repo_paths = {
        repo_id: path.expanduser().resolve()
        for repo_id, path in (repo_paths or {}).items()
    }
    runner = validation_runner or run_candidate_validation_command
    rows = [
        _score_tests_only_task(
            repo=repo,
            task=task,
            defaults=defaults,
            repo_path=resolved_repo_paths.get(_required_str(repo, "id")),
            validate_candidates=validate_candidates,
            validation_timeout_seconds=validation_timeout_seconds,
            validation_runner=runner,
        )
        for repo, task in tests_only_tasks
    ]
    elapsed = perf_counter() - started

    total = len(rows)
    pass_at_1_count = sum(1 for row in rows if row["pass@1"] is True)
    pass_at_3_count = sum(1 for row in rows if row["pass@3"] is True)
    correct_location_count = sum(
        1 for row in rows if row["selected_correct_test_location"] is True
    )
    candidate_count = sum(int(row["candidate_count"]) for row in rows)
    candidates_tested = sum(int(row["candidates_tested"]) for row in rows)
    calibration_metrics = _split_pass_metrics(rows, split="calibration")
    heldout_metrics = _split_pass_metrics(rows, split="heldout")
    runtime_not_run_reasons = sorted(
        {
            str(_mapping(row["runtime"], field="runtime").get("not_run_reason"))
            for row in rows
            if _mapping(row["runtime"], field="runtime").get("status") == "not_run"
        }
    )
    gates = _mapping(manifest.get("gates"), field="gates")
    tests_gate = _mapping(gates.get("tests_only"), field="tests_only")
    minimum_pass_at_3 = int(tests_gate.get("minimum_pass_at_3", 3))
    production_file_modifications = 0
    writes_outside_allowlist = 0
    candidate_target_path_violations = 0
    for row in rows:
        mutation_scope = _mapping(row["mutation_scope"], field="mutation_scope")
        production_file_modifications += len(
            _sequence(
                mutation_scope["production_files_changed"],
                field="production_files_changed",
            )
        )
        writes_outside_allowlist += len(
            _sequence(
                mutation_scope["writes_outside_allowlist"],
                field="writes_outside_allowlist",
            )
        )
        candidate_target_path_violations += len(
            _sequence(
                mutation_scope.get("candidate_target_path_violations"),
                field="candidate_target_path_violations",
            )
        )
    hidden_like_disagreeing = sum(
        1 for row in rows if row["hidden_like_agreement"] == "disagrees"
    )
    gate_passed = (
        pass_at_3_count >= minimum_pass_at_3
        and production_file_modifications == 0
        and writes_outside_allowlist == 0
        and candidate_target_path_violations == 0
        and hidden_like_disagreeing == 0
    )
    blocked_rows = [
        str(row["task_id"])
        for row in rows
        if row["pass@3"] is not True
    ]

    score: dict[str, object] = {
        "schema_version": REAL_REPO_TESTS_SHADOW_SCORE_SCHEMA_VERSION,
        "record_kind": REAL_REPO_TESTS_SHADOW_SCORE_KIND,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "task_type": "tests_only",
        "max_candidates": int(defaults.get("max_candidates", 3)),
        "zero_hosted_usage_confirmed": True,
        "supported_action_surface": {
            "legacy_action_family": SUPPORTED_ACTION_FAMILY,
            "real_repo_action_family": REAL_REPO_TESTS_ACTION_FAMILY,
            "calibration_materializers": [INICONFIG_PARSE_COMMENTS_TASK_ID],
            "heldout_materializers": [
                H11_BYTESIFY_MEMORYVIEW_TASK_ID,
                HUMANIZE_NATURALSIZE_NEGATIVE_STRINGS_TASK_ID,
            ],
            "legacy_domain": SUPPORTED_DOMAIN,
            "legacy_source_files": list(SUPPORTED_SOURCE_FILES),
            "legacy_target_test_files": list(SUPPORTED_TARGET_TEST_FILES),
            "legacy_features": list(SUPPORTED_FEATURES),
            "scope_note": (
                "GS7-008 materializes the iniconfig calibration tests-only "
                "candidate and GS7-009 materializes the first held-out h11 "
                "tests-only candidate. GS7-010 materializes the held-out "
                "humanize tests-only candidate. Other held-out tasks remain "
                "explicit materialization blockers until implemented and live "
                "validated."
            ),
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
            "correct_test_location_count": correct_location_count,
            "correct_test_location": f"{correct_location_count}/{total}",
            "production_file_modifications": production_file_modifications,
            "writes_outside_allowlist": writes_outside_allowlist,
            "mutation_scope_violations": {
                "production_file_modifications": production_file_modifications,
                "writes_outside_allowlist": writes_outside_allowlist,
                "candidate_target_path_violations": sum(
                    len(
                        _sequence(
                            _mapping(row["mutation_scope"], field="mutation_scope").get(
                                "candidate_target_path_violations"
                            ),
                            field="candidate_target_path_violations",
                        )
                    )
                    for row in rows
                ),
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
                "reason": (
                    "hidden-like agreement is evaluated only for public-validating "
                    "materialized candidates with explicit local signals"
                ),
            },
            "runtime_seconds": round(elapsed, 6),
            "runtime_not_run_reasons": runtime_not_run_reasons,
        },
        "gate_decision": {
            "gate": "Gate 2: Shadow Tests-Only Generalization",
            "source": "docs/PRODUCT_WEDGE_DECISION.md",
            "decision": (
                "allow_guarded_tests_only_opt_in"
                if gate_passed
                else "remain_shadow_only"
            ),
            "passed": gate_passed,
            "guarded_opt_in_allowed": gate_passed,
            "reason": (
                f"pass@3 is {pass_at_3_count}/{total} against the "
                f"{minimum_pass_at_3}/{total} tests-only gate. "
                "Guarded tests-only opt-in is allowed for materialized, "
                "validation-passing tests-only candidates that write only "
                "task-allowlisted test files, preserve production files, have "
                "no writes outside the allowlist, and have no hidden-like "
                "disagreement."
                if gate_passed
                else (
                    f"pass@3 is {pass_at_3_count}/{total}, below the "
                    f"{minimum_pass_at_3}/{total} tests-only gate or blocked "
                    "by mutation/hidden-like violations."
                )
            ),
            "guarded_opt_in_scope": {
                "allowed": gate_passed,
                "mode": "guarded_tests_only_opt_in" if gate_passed else None,
                "task_type": "tests_only",
                "action_family": REAL_REPO_TESTS_ACTION_FAMILY,
                "allowed_repo_ids": [
                    str(row["repo_id"]) for row in rows if row["pass@3"] is True
                ],
                "allowed_task_ids": [
                    str(row["task_id"]) for row in rows if row["pass@3"] is True
                ],
                "path_scope": "task allowlisted test files only",
                "requires": [
                    "candidate validation passes before applying",
                    "production files remain byte-for-byte unchanged",
                    "writes stay inside task allowlists",
                    "hidden-like checks do not disagree with public validation",
                    "planned action, changed paths, validation command, and rollback path are shown before applying",
                ],
            },
            "blocked_rows": blocked_rows,
            "failed_checks": []
            if gate_passed
            else [
                "pass@3 below tests-only gate",
                "mutation-scope violations must be zero",
                "hidden-like disagreements must be zero",
            ],
        },
        "task_results": rows,
    }
    return score


def write_real_repo_tests_only_shadow_score(
    score: Mapping[str, object],
    path: Path = DEFAULT_SCORE_PATH,
) -> Path:
    """Write one compact JSON shadow-score artifact."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(score, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved


def format_real_repo_tests_only_shadow_score(score: Mapping[str, object]) -> str:
    """Render a compact Markdown report from a shadow-score record."""

    metrics = _mapping(score.get("metrics"), field="metrics")
    gate = _mapping(score.get("gate_decision"), field="gate_decision")
    rows = _sequence(score.get("task_results"), field="task_results")
    lines = [
        "# REAL-008 Tests-Only Shadow Score",
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
        f"- Correct test location: `{metrics.get('correct_test_location')}`",
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
        labels = ", ".join(str(label) for label in _sequence(row.get("residual_labels"), field="residual_labels"))
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
    lines.extend(
        [
            "",
            "## Gate Decision",
            "",
            str(gate.get("reason")),
        ]
    )
    return "\n".join(lines) + "\n"


def write_real_repo_tests_only_shadow_report(
    score: Mapping[str, object],
    path: Path = DEFAULT_REPORT_PATH,
) -> Path:
    """Write a Markdown report for the shadow score."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(format_real_repo_tests_only_shadow_score(score), encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the REAL-008 tests-only wedge shadow score."
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

    score = run_real_repo_tests_only_shadow_score(
        args.manifest,
        repo_paths=_parse_repo_path_args(args.repo_path),
        validate_candidates=args.validate_candidates,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    score_path = write_real_repo_tests_only_shadow_score(score, args.out)
    report_path = write_real_repo_tests_only_shadow_report(score, args.report)
    metrics = _mapping(score["metrics"], field="metrics")
    gate = _mapping(score["gate_decision"], field="gate_decision")

    print("j3 real-repo tests-only shadow score complete")
    print(f"tasks scored: {metrics['tasks_scored']}")
    print(f"pass@1: {metrics['pass@1']}")
    print(f"pass@3: {metrics['pass@3']}")
    print(f"candidate count: {metrics['candidate_count']}")
    print(f"candidates tested: {metrics['candidates_tested']}")
    print(f"gate decision: {gate['decision']}")
    print(f"score: {score_path}")
    print(f"report: {report_path}")
    return 0


def _score_tests_only_task(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
    repo_path: Path | None,
    validate_candidates: bool,
    validation_timeout_seconds: int,
    validation_runner: ValidationRunner,
) -> dict[str, object]:
    task_id = _required_str(task, "id")
    repo_id = _required_str(repo, "id")
    prompt = _required_str(task, "prompt")
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

    if task_id in MATERIALIZED_TESTS_ONLY_TASK_IDS:
        return _score_materialized_tests_only_task(
            repo=repo,
            task=task,
            defaults=defaults,
            repo_path=repo_path,
            validate_candidates=validate_candidates,
            validation_timeout_seconds=validation_timeout_seconds,
            validation_runner=validation_runner,
        )

    spec = parse_request_to_spec(prompt, task_name=task_id)
    residual_labels = _unique(
        [
            "heldout_materializer_missing",
            TEST_CASE_MATERIALIZATION_BLOCKER,
            *expected_failure_modes,
        ]
    )
    blocker = {
        "field": "test_case_materialization",
        "reason": TEST_CASE_MATERIALIZATION_BLOCKER,
        "message": (
            "held-out tests-only candidate materialization is not implemented "
            f"for {task_id}"
        ),
    }
    return {
        "repo_id": repo_id,
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": task_id,
        "task_type": "tests_only",
        "prompt": prompt,
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
            "not_run_reason": TEST_CASE_MATERIALIZATION_BLOCKER,
        },
        "candidate_validation": {
            "status": "blocked",
            "commands": list(public_validation_commands),
            "selected_command": public_validation_commands[0] if public_validation_commands else None,
            "not_run_reason": TEST_CASE_MATERIALIZATION_BLOCKER,
            "result": None,
        },
        "mutation_scope": {
            "files_changed": [],
            "production_files_changed": [],
            "writes_outside_allowlist": [],
            "candidate_target_paths_considered": [],
            "candidate_target_path_violations": [],
        },
        "hidden_like_agreement": "not_run",
        "hidden_like_evidence": {
            "status": "not_run",
            "reason": "candidate materializer missing",
        },
        "selected_correct_test_location": False,
        "residual_labels": residual_labels,
        "support_observations": [
            "held-out repo left as an explicit blocker until a materializer exists"
        ],
        "blockers": [blocker],
        "candidate_record": None,
        "parsed_request_spec": spec.to_record(),
        "zero_hosted_usage_confirmed": True,
    }


def _score_materialized_tests_only_task(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
    repo_path: Path | None,
    validate_candidates: bool,
    validation_timeout_seconds: int,
    validation_runner: ValidationRunner,
) -> dict[str, object]:
    started = perf_counter()
    repo_id = _required_str(repo, "id")
    task_id = _required_str(task, "id")
    prompt = _required_str(task, "prompt")
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
    spec = parse_request_to_spec(prompt, task_name=task_id)

    if repo_path is None:
        blocker = {
            "field": "repo_path",
            "reason": "candidate_checkout_missing",
            "message": f"{task_id} candidate scoring requires a checkout path",
        }
        return _blocked_materialized_row(
            repo=repo,
            task=task,
            defaults=defaults,
            spec_record=spec.to_record(),
            blocker=blocker,
            residual_labels=["candidate_checkout_missing", *expected_failure_modes],
            runtime_seconds=perf_counter() - started,
        )

    try:
        knowledge_records = extract_local_knowledge_records(
            repo_path,
            repo_id=repo_id,
            repo_ref=_required_str(repo, "checkout_ref"),
            split=str(repo.get("split", "unknown")),
            repo_url=_required_str(repo, "upstream"),
            license=_required_str(repo, "license"),
            retrieved_at="2026-05-18T00:00:00Z",
            setup_commands=_string_sequence(repo.get("setup_commands"), field="setup_commands"),
            baseline_validation_commands=_string_sequence(
                repo.get("baseline_validation_commands"),
                field="baseline_validation_commands",
            ),
            tasks=[task],
        )
        candidate = plan_real_repo_tests_only_candidate(
            repo_path,
            repo=repo,
            task=task,
            local_knowledge_records=knowledge_records,
            write=True,
        )
        candidate_record = candidate.to_record()
    except RealRepoTestsPlannerError as error:
        blocker = blocker_from_error(error)
        return _blocked_materialized_row(
            repo=repo,
            task=task,
            defaults=defaults,
            spec_record=spec.to_record(),
            blocker=blocker,
            residual_labels=[
                str(blocker.get("reason", "candidate_planning_failed")),
                *expected_failure_modes,
            ],
            runtime_seconds=perf_counter() - started,
        )

    candidate_status = str(candidate_record["status"])
    candidate_count = 1 if candidate_status in {"materialized", "already_applied"} else 0
    candidate_validation = _candidate_validation_record(
        repo_path=repo_path,
        candidate_record=candidate_record,
        validate_candidates=validate_candidates,
        timeout_seconds=validation_timeout_seconds,
        runner=validation_runner,
    )
    validation_status = str(candidate_validation["status"])
    passing = validation_status == "passed"
    mutation_scope = _mapping(candidate_record["mutation_scope"], field="mutation_scope")
    target_test_file = str(candidate_record["target_test_file"])
    target_violations = _paths_outside_allowlist([target_test_file], allowed_write_paths)
    hidden_like = _hidden_like_agreement(
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
        "repo_id": repo_id,
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": task_id,
        "task_type": "tests_only",
        "prompt": prompt,
        "allowed_write_paths": list(allowed_write_paths),
        "public_validation_commands": list(public_validation_commands),
        "hidden_like_checks": list(hidden_like_checks),
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
        "mutation_scope": {
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
            "candidate_target_paths_considered": [target_test_file],
            "candidate_target_path_violations": list(target_violations),
            "candidate_after": _json_copy(candidate_record.get("candidate_after", {})),
        },
        "hidden_like_agreement": hidden_like["status"],
        "hidden_like_evidence": hidden_like,
        "selected_correct_test_location": not target_violations,
        "residual_labels": residual_labels,
        "support_observations": [
            "scored through the real-repo tests-only planner candidate surface"
        ],
        "blockers": blockers,
        "candidate_record": candidate_record,
        "parsed_request_spec": spec.to_record(),
        "zero_hosted_usage_confirmed": True,
    }


def _blocked_materialized_row(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
    spec_record: Mapping[str, object],
    blocker: Mapping[str, str],
    residual_labels: Sequence[str],
    runtime_seconds: float,
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
    return {
        "repo_id": _required_str(repo, "id"),
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": task_id,
        "task_type": "tests_only",
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
            "runtime_seconds": round(runtime_seconds, 6),
            "not_run_reason": blocker["reason"],
        },
        "candidate_validation": {
            "status": "blocked",
            "commands": list(public_validation_commands),
            "selected_command": public_validation_commands[0] if public_validation_commands else None,
            "not_run_reason": blocker["reason"],
            "result": None,
        },
        "mutation_scope": {
            "files_changed": [],
            "production_files_changed": [],
            "writes_outside_allowlist": [],
            "candidate_target_paths_considered": [],
            "candidate_target_path_violations": [],
        },
        "hidden_like_agreement": "not_run",
        "hidden_like_evidence": {
            "status": "not_run",
            "reason": "candidate did not reach public validation",
        },
        "selected_correct_test_location": False,
        "residual_labels": _unique(list(residual_labels)),
        "support_observations": ["candidate planning blocked before validation"],
        "blockers": [dict(blocker)],
        "candidate_record": None,
        "parsed_request_spec": dict(spec_record),
        "zero_hosted_usage_confirmed": True,
    }


def _candidate_validation_record(
    *,
    repo_path: Path,
    candidate_record: Mapping[str, object],
    validate_candidates: bool,
    timeout_seconds: int,
    runner: ValidationRunner,
) -> dict[str, object]:
    validation = _mapping(candidate_record.get("validation"), field="candidate.validation")
    selected_command = validation.get("selected_command")
    commands = _sequence(validation.get("commands"), field="candidate.validation.commands")
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

    result = runner(selected_command, repo_path, timeout_seconds)
    return {
        "status": "passed" if result.status == "passed" else "failed",
        "commands": list(commands),
        "selected_command": selected_command,
        "not_run_reason": None,
        "result": result.to_record(),
    }


def run_candidate_validation_command(
    command: str,
    cwd: Path,
    timeout_seconds: int,
) -> CandidateValidationResult:
    """Run one candidate validation command in a checkout."""

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return CandidateValidationResult(
            command=command,
            cwd=str(cwd),
            timeout_seconds=timeout_seconds,
            returncode=None,
            stdout=error.stdout or "",
            stderr=error.stderr or "",
            status="timeout",
        )
    return CandidateValidationResult(
        command=command,
        cwd=str(cwd),
        timeout_seconds=timeout_seconds,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        status="passed" if completed.returncode == 0 else "failed",
    )


def _hidden_like_agreement(
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
    test_case_ids = set(
        _string_sequence(candidate_after.get("test_case_ids", []), field="test_case_ids")
    )
    task_id = _required_str(task, "id")
    if task_id == INICONFIG_PARSE_COMMENTS_TASK_ID:
        required_case_ids = {
            "iniconfig_comment_only_lines",
            "iniconfig_inline_section_comments",
            "iniconfig_duplicate_key_reports_name",
        }
        agrees = (
            not production_changed
            and not writes_outside
            and required_case_ids <= test_case_ids
        )
        return {
            "status": "agrees" if agrees else "disagrees",
            "production_files_unchanged": not production_changed,
            "writes_inside_allowlist": not writes_outside,
            "required_case_ids_present": sorted(required_case_ids & test_case_ids),
            "missing_case_ids": sorted(required_case_ids - test_case_ids),
            "checks": list(
                _string_sequence(
                    task.get("hidden_like_checks"),
                    field="hidden_like_checks",
                )
            ),
        }
    if task_id == H11_BYTESIFY_MEMORYVIEW_TASK_ID:
        required_case_ids = {
            "h11_bytesify_bytearray",
            "h11_bytesify_memoryview",
            "h11_bytesify_ascii_str",
            "h11_bytesify_non_ascii_str",
            "h11_bytesify_int_type_error",
        }
        agrees = (
            not production_changed
            and not writes_outside
            and required_case_ids <= test_case_ids
        )
        return {
            "status": "agrees" if agrees else "disagrees",
            "production_files_unchanged": not production_changed,
            "writes_inside_allowlist": not writes_outside,
            "required_case_ids_present": sorted(required_case_ids & test_case_ids),
            "missing_case_ids": sorted(required_case_ids - test_case_ids),
            "checks": list(
                _string_sequence(
                    task.get("hidden_like_checks"),
                    field="hidden_like_checks",
                )
            ),
        }
    if task_id == HUMANIZE_NATURALSIZE_NEGATIVE_STRINGS_TASK_ID:
        required_case_ids = {
            "humanize_naturalsize_negative_numeric_strings",
            "humanize_naturalsize_negative_gnu_suffixes",
            "humanize_naturalsize_negative_binary_suffixes",
        }
        agrees = (
            not production_changed
            and not writes_outside
            and required_case_ids <= test_case_ids
        )
        return {
            "status": "agrees" if agrees else "disagrees",
            "production_files_unchanged": not production_changed,
            "writes_inside_allowlist": not writes_outside,
            "required_case_ids_present": sorted(required_case_ids & test_case_ids),
            "missing_case_ids": sorted(required_case_ids - test_case_ids),
            "checks": list(
                _string_sequence(
                    task.get("hidden_like_checks"),
                    field="hidden_like_checks",
                )
            ),
        }

    return {
        "status": "not_run",
        "reason": "no hidden-like evaluator for this task",
    }


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


def _legacy_score_tests_only_task(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
) -> dict[str, object]:
    """Return the REAL-003 slugify-only score row for historical comparison."""

    task_id = _required_str(task, "id")
    prompt = _required_str(task, "prompt")
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

    spec = parse_request_to_spec(prompt, task_name=task_id)
    spec_record = spec.to_record()
    residual_labels = ["unsupported_tests_only_action_slice"]
    support_observations: list[str] = []
    candidate_target_paths: tuple[str, ...] = ()
    selected_correct_test_location = False

    if spec.clarifications_needed:
        residual_labels.append("prompt_spec_existing_repo_gap")
        support_observations.append(
            "request parser returned a clarification rather than a supported tests-only spec"
        )
    elif spec.task_type != "add_tests" or spec.repo_mode != "existing_repo":
        residual_labels.append("prompt_spec_existing_repo_gap")
        support_observations.append(
            f"request parser produced task_type={spec.task_type!r}, repo_mode={spec.repo_mode!r}"
        )
    elif spec.domain != SUPPORTED_DOMAIN:
        residual_labels.append("prompt_spec_existing_repo_gap")
        support_observations.append(
            f"supported domain is {SUPPORTED_DOMAIN!r}, parsed domain was {spec.domain!r}"
        )
    else:
        candidate_target_paths = SUPPORTED_TARGET_TEST_FILES
        target_violations = _paths_outside_allowlist(
            candidate_target_paths,
            allowed_write_paths,
        )
        if target_violations:
            residual_labels.extend(["wrong_test_location", "repo_state_planning_gap"])
            support_observations.append(
                "slugify fixture target tests/test_slugify.py is outside the task allowlist"
            )
        else:
            selected_correct_test_location = True
        if tuple(spec.artifacts) != (*SUPPORTED_SOURCE_FILES, *SUPPORTED_TARGET_TEST_FILES):
            residual_labels.append("repo_state_planning_gap")
            support_observations.append(
                "supported artifacts do not match the real-repo package/test layout"
            )

    if not support_observations:
        support_observations.append(
            "builder is still limited to root slugify.py and cannot inspect arbitrary real repos"
        )

    expected_failure_modes = list(
        _string_sequence(task.get("expected_failure_modes"), field="expected_failure_modes")
    )
    residual_labels = _unique([*residual_labels, *expected_failure_modes])

    return {
        "repo_id": _required_str(repo, "id"),
        "repo_split": str(repo.get("split", "unknown")),
        "checkout_ref": _required_str(repo, "checkout_ref"),
        "task_id": task_id,
        "task_type": "tests_only",
        "prompt": prompt,
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
            "not_run_reason": "unsupported_tests_only_action_slice",
        },
        "mutation_scope": {
            "files_changed": [],
            "production_files_changed": [],
            "writes_outside_allowlist": [],
            "candidate_target_paths_considered": list(candidate_target_paths),
            "candidate_target_path_violations": list(
                _paths_outside_allowlist(candidate_target_paths, allowed_write_paths)
            ),
        },
        "hidden_like_agreement": "not_run",
        "selected_correct_test_location": selected_correct_test_location,
        "residual_labels": residual_labels,
        "support_observations": support_observations,
        "parsed_request_spec": spec_record,
        "zero_hosted_usage_confirmed": True,
    }


def _tests_only_tasks(
    manifest: Mapping[str, object],
) -> list[tuple[Mapping[str, object], Mapping[str, object]]]:
    rows: list[tuple[Mapping[str, object], Mapping[str, object]]] = []
    for repo_value in _sequence(manifest.get("repositories"), field="repositories"):
        repo = _mapping(repo_value, field="repository")
        for task_value in _sequence(repo.get("tasks"), field="repository.tasks"):
            task = _mapping(task_value, field="repository.task")
            if task.get("task_type") == "tests_only":
                rows.append((repo, task))
    return rows


def _paths_outside_allowlist(
    candidate_paths: Sequence[str],
    allowed_write_paths: Sequence[str],
) -> tuple[str, ...]:
    normalized_allowed = tuple(_normalize_relative_path(path) for path in allowed_write_paths)
    violations: list[str] = []
    for candidate_path in candidate_paths:
        normalized = _normalize_relative_path(candidate_path)
        if not any(_path_is_allowed(normalized, allowed) for allowed in normalized_allowed):
            violations.append(normalized)
    return tuple(violations)


def _path_is_allowed(candidate: str, allowed_path: str) -> bool:
    return candidate == allowed_path or candidate.startswith(f"{allowed_path.rstrip('/')}/")


def _normalize_relative_path(path: str) -> str:
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ValueError(f"path must be repository-relative: {path}")
    normalized = pure_path.as_posix().strip("/")
    if not normalized or normalized == ".":
        raise ValueError("path must not be empty")
    return normalized


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
