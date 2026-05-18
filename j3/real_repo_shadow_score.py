"""Shadow scoring for the first real-repo tests-only product wedge."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Mapping, Sequence

from j3.existing_repo_tests import (
    SLUGIFY_SOURCE,
    SLUGIFY_TESTS,
    SLUGIFY_FEATURES,
)
from j3.real_repo_preflight import (
    DEFAULT_MANIFEST_PATH,
    load_real_repo_ladder_manifest,
)
from j3.request_spec import parse_request_to_spec


REAL_REPO_TESTS_SHADOW_SCORE_SCHEMA_VERSION = "real-repo-tests-shadow-score-v1"
REAL_REPO_TESTS_SHADOW_SCORE_KIND = "real_repo_tests_only_shadow_score"
SUPPORTED_ACTION_FAMILY = "add_existing_repo_tests"
SUPPORTED_DOMAIN = "text_slugify"
SUPPORTED_SOURCE_FILES = (SLUGIFY_SOURCE,)
SUPPORTED_TARGET_TEST_FILES = (SLUGIFY_TESTS,)
SUPPORTED_FEATURES = tuple(SLUGIFY_FEATURES)
DEFAULT_REPORT_PATH = Path("/tmp/j3-real-003-tests-only-shadow-score/report.md")
DEFAULT_SCORE_PATH = Path("/tmp/j3-real-003-tests-only-shadow-score/score.json")


def run_real_repo_tests_only_shadow_score(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    *,
    created_at: str | None = None,
) -> dict[str, object]:
    """Score current tests-only wedge coverage against REAL-001 tasks.

    This first wedge score is intentionally honest about the current action
    surface: the GS7-005 builder can author tests for a root ``slugify.py``
    fixture only. When a real-repo task cannot be targeted, the row records a
    no-candidate residual instead of manufacturing a synthetic pass.
    """

    started = perf_counter()
    manifest = load_real_repo_ladder_manifest(manifest_path)
    defaults = _mapping(manifest.get("defaults"), field="defaults")
    tests_only_tasks = _tests_only_tasks(manifest)
    rows = [
        _score_tests_only_task(repo=repo, task=task, defaults=defaults)
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

    score: dict[str, object] = {
        "schema_version": REAL_REPO_TESTS_SHADOW_SCORE_SCHEMA_VERSION,
        "record_kind": REAL_REPO_TESTS_SHADOW_SCORE_KIND,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "task_type": "tests_only",
        "max_candidates": int(defaults.get("max_candidates", 3)),
        "zero_hosted_usage_confirmed": True,
        "supported_action_surface": {
            "action_family": SUPPORTED_ACTION_FAMILY,
            "domain": SUPPORTED_DOMAIN,
            "source_files": list(SUPPORTED_SOURCE_FILES),
            "target_test_files": list(SUPPORTED_TARGET_TEST_FILES),
            "features": list(SUPPORTED_FEATURES),
            "scope_note": (
                "GS7-005 supports a one-file root slugify.py fixture only; "
                "it does not yet inspect arbitrary real-repo package/test layouts."
            ),
        },
        "metrics": {
            "tasks_scored": total,
            "candidate_count": candidate_count,
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
            "hidden_like_agreement": {
                "agreeing": 0,
                "disagreeing": 0,
                "not_run": total,
                "reason": "no public-validating candidates reached hidden-like checks",
            },
            "runtime_seconds": round(elapsed, 6),
            "runtime_not_run_reasons": runtime_not_run_reasons,
        },
        "gate_decision": {
            "gate": "Gate 2: Shadow Tests-Only Generalization",
            "source": "docs/PRODUCT_WEDGE_DECISION.md",
            "decision": "remain_shadow_only",
            "passed": False,
            "guarded_opt_in_allowed": False,
            "reason": (
                f"pass@3 is {pass_at_3_count}/{total}, below the "
                f"{minimum_pass_at_3}/{total} tests-only gate, because the "
                "current tests-only builder cannot target these real repos."
            ),
            "failed_checks": [
                "pass@3 below tests-only gate",
                "no hidden-like agreement can be measured without a passing public validation",
                "correct test location selected for fewer than 3/4 tasks",
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
        "# REAL-003 Tests-Only Shadow Score",
        "",
        f"- Schema: `{score.get('schema_version')}`",
        f"- Manifest: `{score.get('manifest_path')}`",
        f"- Max candidates: `{score.get('max_candidates')}`",
        f"- Zero hosted usage: `{str(score.get('zero_hosted_usage_confirmed')).lower()}`",
        f"- Candidate count: `{metrics.get('candidate_count')}`",
        f"- pass@1: `{metrics.get('pass@1')}`",
        f"- pass@3: `{metrics.get('pass@3')}`",
        f"- Correct test location: `{metrics.get('correct_test_location')}`",
        f"- Runtime: `{metrics.get('runtime_seconds')}s` for the shadow scorer; candidate validation was not run.",
        f"- Gate decision: `{gate.get('decision')}`",
        "",
        "## Task Results",
        "",
        "| Task | Split | pass@1 | pass@3 | First passing rank | Hidden-like | Residual labels |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row_value in rows:
        row = _mapping(row_value, field="task_result")
        labels = ", ".join(str(label) for label in _sequence(row.get("residual_labels"), field="residual_labels"))
        first_rank = row.get("first_passing_rank")
        lines.append(
            "| "
            f"`{row.get('task_id')}` | "
            f"{row.get('repo_split')} | "
            f"{row.get('pass@1')} | "
            f"{row.get('pass@3')} | "
            f"{first_rank if first_rank is not None else 'none'} | "
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
        description="Run the REAL-003 tests-only wedge shadow score."
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
    args = parser.parse_args(argv)

    score = run_real_repo_tests_only_shadow_score(args.manifest)
    score_path = write_real_repo_tests_only_shadow_score(score, args.out)
    report_path = write_real_repo_tests_only_shadow_report(score, args.report)
    metrics = _mapping(score["metrics"], field="metrics")
    gate = _mapping(score["gate_decision"], field="gate_decision")

    print("j3 real-repo tests-only shadow score complete")
    print(f"tasks scored: {metrics['tasks_scored']}")
    print(f"pass@1: {metrics['pass@1']}")
    print(f"pass@3: {metrics['pass@3']}")
    print(f"candidate count: {metrics['candidate_count']}")
    print(f"gate decision: {gate['decision']}")
    print(f"score: {score_path}")
    print(f"report: {report_path}")
    return 0


def _score_tests_only_task(
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    defaults: Mapping[str, object],
) -> dict[str, object]:
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
