"""Materialize and validate live issue/PR ranking decoys.

DATA-039 keeps this evidence shadow-only. The records produced here are meant
to remove label-only decoy blockers from the issue/PR ranking harness without
changing any production ranking gate.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from j3.ast_delta import python_ast_delta_metadata
from j3.issue_pr_candidate_attempt import (
    PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS,
    PYTEST_TIMEDELTA_APPROX_ACTION_FAMILY,
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
    PYTEST_TIMEDELTA_APPROX_TEST_PATH,
    SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS,
    SCRAPY_DOWNLOADER_AWARE_ACTION_FAMILY,
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
    SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
    SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND,
    _candidate_diff,
    _git_stdout,
    run_pytest_timedelta_approx_issue_pr_candidate_attempt,
    run_scrapy_downloader_aware_issue_pr_candidate_attempt,
    validate_issue_pr_candidate,
)
from j3.issue_pr_preflight import (
    load_issue_pr_replay_manifest,
    select_issue_pr_replay_record,
)


ISSUE_PR_DECOY_VALIDATION_SCHEMA_VERSION = "issue-pr-decoy-validation-v1"
DEFAULT_OUT_DIR = Path("/tmp/j3-data-039-scrapy-decoy-validation")
DEFAULT_SETUP_COMMAND = "python -c 'print(\"setup skipped for focused validation\")'"
PYTEST_DECOY_SETUP_COMMAND = (
    "python -m venv .venv && "
    ".venv/bin/python -m pip install -q -e . pytest"
)
PYTEST_DECOY_VALIDATION_COMMAND = (
    ".venv/bin/python -m py_compile src/_pytest/python_api.py && "
    ".venv/bin/python -m pytest testing/python/approx.py -q"
)


class IssuePrDecoyValidationError(ValueError):
    """Raised when DATA-039 decoy validation cannot be built."""


@dataclass(frozen=True, slots=True)
class ScrapyDecoySpec:
    decoy_id: str
    description: str
    targeted_mistakes: tuple[str, ...]
    residual_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PytestDecoySpec:
    decoy_id: str
    description: str
    targeted_mistakes: tuple[str, ...]
    residual_labels: tuple[str, ...]


SCRAPY_DECOY_SPECS: tuple[ScrapyDecoySpec, ...] = (
    ScrapyDecoySpec(
        decoy_id="scrapy_stale_min_stats_selection",
        description=(
            "Keeps the repo-before min(stats)[1] source selection while adding "
            "the accepted tie-breaking regression tests."
        ),
        targeted_mistakes=(
            "stale_min_stats_selection",
            "keeps_lexicographic_slot_tie_breaking",
        ),
        residual_labels=("semantic_decoy", "slot_rotation_gap"),
    ),
    ScrapyDecoySpec(
        decoy_id="scrapy_mutating_peek",
        description=(
            "Uses the accepted slot selector but calls it from peek with "
            "update_state=True, so observing the queue can mutate rotation state."
        ),
        targeted_mistakes=("mutating_peek", "updates_last_selected_slot_during_peek"),
        residual_labels=("semantic_decoy", "peek_side_effect_gap"),
    ),
    ScrapyDecoySpec(
        decoy_id="scrapy_missing_last_selected_slot",
        description=(
            "Adds the slot helper and tests but makes the helper stateless by "
            "not preserving _last_selected_slot across pops."
        ),
        targeted_mistakes=("missing_last_selected_slot", "stateless_rotation_helper"),
        residual_labels=("state_decoy", "source_state_gap"),
    ),
    ScrapyDecoySpec(
        decoy_id="scrapy_missing_tests",
        description=(
            "Keeps the accepted source behavior but restores the repo-before "
            "test file, yielding a source-only candidate with no issue regression tests."
        ),
        targeted_mistakes=("missing_tests", "source_only_candidate"),
        residual_labels=("test_decoy", "coverage_gap"),
    ),
)

PYTEST_DECOY_SPECS: tuple[PytestDecoySpec, ...] = (
    PytestDecoySpec(
        decoy_id="pytest_rel_timedelta_object_semantics",
        description=(
            "Adds the accepted tests and surrounding timedelta support but keeps "
            "the obsolete rel=timedelta absolute-tolerance implementation."
        ),
        targeted_mistakes=(
            "incomplete_timedelta_relative_tolerance_semantics",
            "keeps_rel_as_timedelta_instead_of_numeric_fraction",
        ),
        residual_labels=("semantic_decoy", "pytest_timedelta_rel_semantics_gap"),
    ),
    PytestDecoySpec(
        decoy_id="pytest_missing_container_dispatch",
        description=(
            "Updates ApproxTimedelta.__init__ and tests but omits the "
            "ApproxBase._approx_scalar datetime/timedelta container dispatch."
        ),
        targeted_mistakes=(
            "incomplete_source_materialization",
            "missing_sequence_mapping_approx_timedelta_dispatch",
        ),
        residual_labels=("source_decoy", "candidate_after_observation_gap"),
    ),
    PytestDecoySpec(
        decoy_id="pytest_missing_invalid_tolerance_tests",
        description=(
            "Keeps accepted source behavior but removes focused tests for "
            "invalid rel/abs tolerance values and rel/abs max behavior."
        ),
        targeted_mistakes=(
            "missing_test_coverage",
            "missing_negative_and_nan_tolerance_tests",
        ),
        residual_labels=("test_decoy", "coverage_gap"),
    ),
    PytestDecoySpec(
        decoy_id="pytest_partial_source_test_materialization",
        description=(
            "Adds accepted tests and docs but leaves relative tolerance as the "
            "raw rel value instead of rel * abs(expected)."
        ),
        targeted_mistakes=(
            "incomplete_source_test_materialization",
            "docs_and_tests_without_full_source_semantics",
        ),
        residual_labels=("materialization_decoy", "source_semantics_gap"),
    ),
)


def build_scrapy_decoy_validation_bundle(
    repo_path: Path,
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    setup_command: str = DEFAULT_SETUP_COMMAND,
    validation_command: str = SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
    decoy_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Materialize Scrapy #7293 decoys and optionally live-validate them."""

    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrDecoyValidationError(f"repo does not exist: {resolved_repo}")

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected_specs = _selected_specs(decoy_ids)
    records = [
        _materialize_scrapy_decoy(
            base_repo=resolved_repo,
            out_dir=output,
            manifest_path=manifest_path,
            setup_command=setup_command,
            validation_command=validation_command,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
            spec=spec,
        )
        for spec in selected_specs
    ]
    blockers = [
        blocker
        for record in records
        for blocker in _list_of_mappings(record.get("blockers"))
    ]
    live_validated = [
        record
        for record in records
        if _mapping(record.get("validation")).get("status")
        in {"passed", "failed", "timeout"}
    ]
    return {
        "schema_version": ISSUE_PR_DECOY_VALIDATION_SCHEMA_VERSION,
        "record_kind": "issue_pr_decoy_validation_bundle",
        "task_id": "DATA-039",
        "mode": "shadow_only_decoy_validation",
        "production_ranking_gate_changed": False,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": True,
        },
        "summary": {
            "replay_id": SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
            "repo": "scrapy/scrapy",
            "candidate_count": len(records),
            "live_validated_count": len(live_validated),
            "validation_status_counts": _counts(
                str(_mapping(record.get("validation")).get("status", ""))
                for record in records
            ),
            "candidate_after_available_count": sum(
                1
                for record in records
                if _mapping(record.get("candidate_after")).get("available") is True
            ),
            "snapshot_file_count": sum(
                len(_list_of_mappings(record.get("snapshots"))) for record in records
            ),
            "blocker_reasons": _sorted_unique(
                str(blocker.get("reason", "")) for blocker in blockers
            ),
            "residual_labels": _sorted_unique(
                label
                for record in records
                for label in _string_list(record.get("residual_labels"))
            ),
        },
        "candidates": records,
    }


def build_pytest_decoy_validation_bundle(
    repo_path: Path,
    *,
    out_dir: Path = Path("/tmp/j3-data-040-pytest-decoy-validation"),
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    setup_command: str = PYTEST_DECOY_SETUP_COMMAND,
    validation_command: str = PYTEST_DECOY_VALIDATION_COMMAND,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
    decoy_ids: Sequence[str] | None = None,
) -> dict[str, object]:
    """Materialize pytest #14462 decoys and optionally live-validate them."""

    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrDecoyValidationError(f"repo does not exist: {resolved_repo}")

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected_specs = _selected_pytest_specs(decoy_ids)
    records = [
        _materialize_pytest_decoy(
            base_repo=resolved_repo,
            out_dir=output,
            manifest_path=manifest_path,
            setup_command=setup_command,
            validation_command=validation_command,
            validate=validate,
            validation_timeout_seconds=validation_timeout_seconds,
            spec=spec,
        )
        for spec in selected_specs
    ]
    blockers = [
        blocker
        for record in records
        for blocker in _list_of_mappings(record.get("blockers"))
    ]
    live_validated = [
        record
        for record in records
        if _mapping(record.get("validation")).get("status")
        in {"passed", "failed", "timeout"}
    ]
    return {
        "schema_version": ISSUE_PR_DECOY_VALIDATION_SCHEMA_VERSION,
        "record_kind": "issue_pr_decoy_validation_bundle",
        "task_id": "DATA-040",
        "mode": "shadow_only_decoy_validation",
        "production_ranking_gate_changed": False,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": True,
        },
        "summary": {
            "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
            "repo": "pytest-dev/pytest",
            "candidate_count": len(records),
            "live_validated_count": len(live_validated),
            "validation_status_counts": _counts(
                str(_mapping(record.get("validation")).get("status", ""))
                for record in records
            ),
            "candidate_after_available_count": sum(
                1
                for record in records
                if _mapping(record.get("candidate_after")).get("available") is True
            ),
            "snapshot_file_count": sum(
                len(_list_of_mappings(record.get("snapshots"))) for record in records
            ),
            "blocker_reasons": _sorted_unique(
                str(blocker.get("reason", "")) for blocker in blockers
            ),
            "residual_labels": _sorted_unique(
                label
                for record in records
                for label in _string_list(record.get("residual_labels"))
            ),
        },
        "candidates": records,
    }


def write_issue_pr_decoy_validation_bundle(
    bundle: Mapping[str, object],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write DATA-039 decoy validation JSON, JSONL, and markdown artifacts."""

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle_json = output / "decoy-validation-bundle.json"
    candidates_jsonl = output / "decoy-validation-candidates.jsonl"
    report_md = output / "decoy-validation-report.md"
    bundle_json.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    candidates = [
        candidate
        for candidate in bundle.get("candidates", [])
        if isinstance(candidate, Mapping)
    ]
    candidates_jsonl.write_text(
        "\n".join(json.dumps(candidate, sort_keys=True) for candidate in candidates)
        + ("\n" if candidates else ""),
        encoding="utf-8",
    )
    report_md.write_text(format_issue_pr_decoy_validation_markdown(bundle), encoding="utf-8")
    return {
        "bundle_json": bundle_json,
        "candidates_jsonl": candidates_jsonl,
        "report_md": report_md,
    }


def format_issue_pr_decoy_validation_markdown(bundle: Mapping[str, object]) -> str:
    summary = _mapping(bundle.get("summary"))
    task_id = str(bundle.get("task_id", "DATA-039"))
    lines = [
        f"# {task_id} Live Issue/PR Decoy Validation",
        "",
        f"- Replay: {summary.get('replay_id')}",
        f"- Repo: {summary.get('repo')}",
        f"- Decoys: {summary.get('candidate_count')}",
        f"- Live validated: {summary.get('live_validated_count')}",
        f"- Candidate-after available: {summary.get('candidate_after_available_count')}",
        f"- Snapshot files: {summary.get('snapshot_file_count')}",
        "- Production ranking gate changed: false",
        "- Hosted LLM usage: false",
        "",
        "| Candidate | Validation | Runtime | Touched files | Residual labels | Snapshots |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for candidate in _list_of_mappings(bundle.get("candidates")):
        validation = _mapping(candidate.get("validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    str(candidate.get("candidate_id", "")),
                    str(validation.get("status", "")),
                    str(validation.get("runtime_seconds", "")),
                    ", ".join(_string_list(candidate.get("touched_file_paths"))),
                    ", ".join(_string_list(candidate.get("residual_labels"))),
                    str(len(_list_of_mappings(candidate.get("snapshots")))),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def load_issue_pr_decoy_validation_bundle_index(
    bundle_path: Path,
) -> dict[str, dict[str, object]]:
    """Load DATA-039 decoy validation records keyed by candidate id."""

    payload = json.loads(bundle_path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrDecoyValidationError(
            f"decoy validation bundle must be a JSON object: {bundle_path}"
        )
    index: dict[str, dict[str, object]] = {}
    for candidate in _list_of_mappings(payload.get("candidates")):
        candidate_id = str(candidate.get("candidate_id", ""))
        if candidate_id:
            index[candidate_id] = dict(candidate)
    return index


def _materialize_scrapy_decoy(
    *,
    base_repo: Path,
    out_dir: Path,
    manifest_path: Path,
    setup_command: str,
    validation_command: str,
    validate: bool,
    validation_timeout_seconds: int,
    spec: ScrapyDecoySpec,
) -> dict[str, object]:
    checkout = out_dir / "checkouts" / spec.decoy_id
    _fresh_copytree(base_repo, checkout)
    source_path = checkout / SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH
    test_path = checkout / SCRAPY_DOWNLOADER_AWARE_TEST_PATH
    before_source = source_path.read_text(encoding="utf-8")
    before_tests = test_path.read_text(encoding="utf-8")
    replay_record = select_issue_pr_replay_record(
        load_issue_pr_replay_manifest(manifest_path),
        SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    )
    repo_before_ref = str(_mapping(replay_record.get("repo_before_ref")).get("sha", ""))
    head = _git_stdout(checkout, ("rev-parse", "HEAD"))
    blockers: list[dict[str, str]] = []
    if head and repo_before_ref and head != repo_before_ref:
        blockers.append(
            {
                "field": "repo_before_ref",
                "reason": "repo_before_ref_mismatch",
                "message": f"expected {repo_before_ref}, got {head}",
            }
        )

    accepted_attempt = run_scrapy_downloader_aware_issue_pr_candidate_attempt(
        checkout,
        manifest_path=manifest_path,
        write=True,
        validate=False,
    )
    _apply_scrapy_decoy_variant(
        spec.decoy_id,
        source_path=source_path,
        test_path=test_path,
        before_source=before_source,
        before_tests=before_tests,
    )
    after_source = source_path.read_text(encoding="utf-8")
    after_tests = test_path.read_text(encoding="utf-8")
    materializations = {
        SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH: _path_materialization(
            path=SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH,
            before_text=before_source,
            after_text=after_source,
            kind="source",
        ),
        SCRAPY_DOWNLOADER_AWARE_TEST_PATH: _path_materialization(
            path=SCRAPY_DOWNLOADER_AWARE_TEST_PATH,
            before_text=before_tests,
            after_text=after_tests,
            kind="test",
        ),
    }
    candidate_diff = _candidate_diff(checkout, SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS)
    touched_files = _string_list(candidate_diff.get("changed_files"))
    if not touched_files:
        touched_files = [
            path
            for path, materialization in materializations.items()
            if materialization.get("changed") is True
        ]
        candidate_diff = {
            **candidate_diff,
            "changed_files": touched_files,
            "diff": "\n".join(
                str(materializations[path].get("diff", ""))
                for path in touched_files
            ),
        }
    validation = _deferred_validation(
        setup_command=setup_command,
        validation_command=validation_command,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            checkout,
            setup_command=setup_command,
            validation_command=validation_command,
            timeout_seconds=validation_timeout_seconds,
        )
    if validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "decoy_validation_timeout",
                "message": "focused Scrapy #7293 validation command timed out for decoy",
            }
        )
    snapshots = _write_candidate_after_snapshots(
        checkout=checkout,
        out_dir=out_dir,
        candidate_id=f"{SCRAPY_DOWNLOADER_AWARE_REPLAY_ID}:{spec.decoy_id}",
        touched_files=touched_files,
        materializations=materializations,
    )
    candidate_after = _candidate_after_record(
        candidate_id=f"{SCRAPY_DOWNLOADER_AWARE_REPLAY_ID}:{spec.decoy_id}",
        replay_id=SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        snapshots=snapshots,
    )
    residual_labels = _decoy_residual_labels(
        spec=spec,
        validation_status=str(validation.get("status", "")),
        blockers=blockers,
    )
    return {
        "schema_version": ISSUE_PR_DECOY_VALIDATION_SCHEMA_VERSION,
        "record_kind": "issue_pr_decoy_validation_candidate",
        "task_id": "DATA-039",
        "candidate_id": f"{SCRAPY_DOWNLOADER_AWARE_REPLAY_ID}:{spec.decoy_id}",
        "candidate_kind": "realistic_decoy",
        "expected_accepted": False,
        "decoy_id": spec.decoy_id,
        "replay_id": SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        "repo": "scrapy/scrapy",
        "repo_before_ref": repo_before_ref,
        "checkout_path": str(checkout),
        "status": "validated" if validate else "materialized",
        "action_family": SCRAPY_DOWNLOADER_AWARE_ACTION_FAMILY,
        "allowed_write_paths": list(SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS),
        "touched_file_paths": touched_files,
        "candidate_diff": candidate_diff,
        "source_materialization": materializations[SCRAPY_DOWNLOADER_AWARE_SOURCE_PATH],
        "test_materialization": materializations[SCRAPY_DOWNLOADER_AWARE_TEST_PATH],
        "mutation_scope": {
            "mode": "issue_pr_decoy_validation_source_test_scope",
            "allowed_write_paths": list(SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS),
            "files_changed": touched_files,
            "writes_outside_allowlist": [
                path
                for path in touched_files
                if path not in SCRAPY_DOWNLOADER_AWARE_ACCEPTED_PATHS
            ],
        },
        "validation": validation,
        "candidate_after": candidate_after,
        "snapshots": snapshots,
        "decoy_evidence": {
            "description": spec.description,
            "targeted_mistakes": list(spec.targeted_mistakes),
            "source": "DATA-039 live materialization",
            "accepted_materializer": "DATA-035",
        },
        "provenance": {
            "base_repo_path": str(base_repo),
            "manifest_path": str(manifest_path),
            "accepted_attempt_status": accepted_attempt.status,
            "accepted_attempt_candidate_id": accepted_attempt.candidate_id,
        },
        "residual_labels": residual_labels,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": True,
        },
        "blockers": blockers,
    }


def _materialize_pytest_decoy(
    *,
    base_repo: Path,
    out_dir: Path,
    manifest_path: Path,
    setup_command: str,
    validation_command: str,
    validate: bool,
    validation_timeout_seconds: int,
    spec: PytestDecoySpec,
) -> dict[str, object]:
    checkout = out_dir / "checkouts" / spec.decoy_id
    _fresh_copytree(base_repo, checkout)
    source_path = checkout / PYTEST_TIMEDELTA_APPROX_SOURCE_PATH
    test_path = checkout / PYTEST_TIMEDELTA_APPROX_TEST_PATH
    before_source = source_path.read_text(encoding="utf-8")
    before_tests = test_path.read_text(encoding="utf-8")
    replay_record = select_issue_pr_replay_record(
        load_issue_pr_replay_manifest(manifest_path),
        PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    )
    repo_before_ref = str(_mapping(replay_record.get("repo_before_ref")).get("sha", ""))
    head = _git_stdout(checkout, ("rev-parse", "HEAD"))
    blockers: list[dict[str, str]] = []
    if head and repo_before_ref and head != repo_before_ref:
        blockers.append(
            {
                "field": "repo_before_ref",
                "reason": "repo_before_ref_mismatch",
                "message": f"expected {repo_before_ref}, got {head}",
            }
        )

    accepted_attempt = run_pytest_timedelta_approx_issue_pr_candidate_attempt(
        checkout,
        manifest_path=manifest_path,
        write=True,
        validate=False,
    )
    _apply_pytest_decoy_variant(
        spec.decoy_id,
        source_path=source_path,
        test_path=test_path,
    )
    after_source = source_path.read_text(encoding="utf-8")
    after_tests = test_path.read_text(encoding="utf-8")
    materializations = {
        PYTEST_TIMEDELTA_APPROX_SOURCE_PATH: _path_materialization(
            path=PYTEST_TIMEDELTA_APPROX_SOURCE_PATH,
            before_text=before_source,
            after_text=after_source,
            kind="source",
        ),
        PYTEST_TIMEDELTA_APPROX_TEST_PATH: _path_materialization(
            path=PYTEST_TIMEDELTA_APPROX_TEST_PATH,
            before_text=before_tests,
            after_text=after_tests,
            kind="test",
        ),
    }
    candidate_diff = _candidate_diff(checkout, PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS)
    touched_files = _string_list(candidate_diff.get("changed_files"))
    if not touched_files:
        touched_files = [
            path
            for path, materialization in materializations.items()
            if materialization.get("changed") is True
        ]
        candidate_diff = {
            **candidate_diff,
            "changed_files": touched_files,
            "diff": "\n".join(
                str(materializations[path].get("diff", ""))
                for path in touched_files
            ),
        }
    validation = _deferred_validation(
        setup_command=setup_command,
        validation_command=validation_command,
    )
    if validate and not blockers:
        validation = validate_issue_pr_candidate(
            checkout,
            setup_command=setup_command,
            validation_command=validation_command,
            timeout_seconds=validation_timeout_seconds,
        )
    if validation.get("status") == "timeout":
        blockers.append(
            {
                "field": "validation",
                "reason": "decoy_validation_timeout",
                "message": "focused pytest #14462 validation command timed out for decoy",
            }
        )
    candidate_id = f"{PYTEST_TIMEDELTA_APPROX_REPLAY_ID}:{spec.decoy_id}"
    snapshots = _write_candidate_after_snapshots(
        checkout=checkout,
        out_dir=out_dir,
        candidate_id=candidate_id,
        touched_files=touched_files,
        materializations=materializations,
    )
    candidate_after = _candidate_after_record(
        candidate_id=candidate_id,
        replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        snapshots=snapshots,
    )
    residual_labels = _pytest_decoy_residual_labels(
        spec=spec,
        validation_status=str(validation.get("status", "")),
        blockers=blockers,
    )
    return {
        "schema_version": ISSUE_PR_DECOY_VALIDATION_SCHEMA_VERSION,
        "record_kind": "issue_pr_decoy_validation_candidate",
        "task_id": "DATA-040",
        "candidate_id": candidate_id,
        "candidate_kind": "realistic_decoy",
        "expected_accepted": False,
        "decoy_id": spec.decoy_id,
        "replay_id": PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        "repo": "pytest-dev/pytest",
        "repo_before_ref": repo_before_ref,
        "checkout_path": str(checkout),
        "status": "validated" if validate else "materialized",
        "action_family": PYTEST_TIMEDELTA_APPROX_ACTION_FAMILY,
        "allowed_write_paths": list(PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS),
        "touched_file_paths": touched_files,
        "candidate_diff": candidate_diff,
        "source_materialization": materializations[PYTEST_TIMEDELTA_APPROX_SOURCE_PATH],
        "test_materialization": materializations[PYTEST_TIMEDELTA_APPROX_TEST_PATH],
        "mutation_scope": {
            "mode": "issue_pr_decoy_validation_source_test_scope",
            "allowed_write_paths": list(PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS),
            "files_changed": touched_files,
            "writes_outside_allowlist": [
                path
                for path in touched_files
                if path not in PYTEST_TIMEDELTA_APPROX_ACCEPTED_PATHS
            ],
        },
        "validation": validation,
        "candidate_after": candidate_after,
        "snapshots": snapshots,
        "decoy_evidence": {
            "description": spec.description,
            "targeted_mistakes": list(spec.targeted_mistakes),
            "source": "DATA-040 live materialization",
            "accepted_materializer": "DATA-029",
        },
        "provenance": {
            "base_repo_path": str(base_repo),
            "manifest_path": str(manifest_path),
            "accepted_attempt_status": accepted_attempt.status,
            "accepted_attempt_candidate_id": accepted_attempt.candidate_id,
        },
        "residual_labels": residual_labels,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": True,
        },
        "blockers": blockers,
    }


def _apply_scrapy_decoy_variant(
    decoy_id: str,
    *,
    source_path: Path,
    test_path: Path,
    before_source: str,
    before_tests: str,
) -> None:
    source = source_path.read_text(encoding="utf-8")
    tests = test_path.read_text(encoding="utf-8")
    if decoy_id == "scrapy_stale_min_stats_selection":
        source_path.write_text(before_source, encoding="utf-8")
        return
    if decoy_id == "scrapy_mutating_peek":
        old = "        slot = self._next_slot(stats, update_state=False)"
        new = "        slot = self._next_slot(stats, update_state=True)"
        if old not in source:
            raise IssuePrDecoyValidationError("accepted peek selector anchor missing")
        source_path.write_text(source.replace(old, new, 1), encoding="utf-8")
        return
    if decoy_id == "scrapy_missing_last_selected_slot":
        source = source.replace(
            "        self._last_selected_slot: str | None = None\n",
            "",
            1,
        )
        old = "        last = self._last_selected_slot"
        new = "        last: str | None = None"
        if old not in source:
            raise IssuePrDecoyValidationError("accepted _last_selected_slot anchor missing")
        source_path.write_text(source.replace(old, new, 1), encoding="utf-8")
        return
    if decoy_id == "scrapy_missing_tests":
        test_path.write_text(before_tests, encoding="utf-8")
        return
    raise IssuePrDecoyValidationError(f"unsupported Scrapy decoy id: {decoy_id}")


def _apply_pytest_decoy_variant(
    decoy_id: str,
    *,
    source_path: Path,
    test_path: Path,
) -> None:
    source = source_path.read_text(encoding="utf-8")
    tests = test_path.read_text(encoding="utf-8")
    if decoy_id == "pytest_rel_timedelta_object_semantics":
        source_path.write_text(
            _replace_required(
                source,
                _pytest_accepted_rel_block(),
                _pytest_stale_rel_timedelta_block(),
                "accepted ApproxTimedelta rel block missing",
            ),
            encoding="utf-8",
        )
        return
    if decoy_id == "pytest_missing_container_dispatch":
        source_path.write_text(
            _replace_required(
                source,
                _pytest_accepted_scalar_dispatch_block(),
                _pytest_repo_before_scalar_dispatch_block(),
                "accepted ApproxBase._approx_scalar dispatch block missing",
            ),
            encoding="utf-8",
        )
        return
    if decoy_id == "pytest_missing_invalid_tolerance_tests":
        test_path.write_text(
            _remove_pytest_test_methods(
                tests,
                (
                    "test_timedelta_rel_must_be_non_negative",
                    "test_timedelta_rel_must_not_be_nan",
                    "test_timedelta_abs_must_be_non_negative",
                    "test_timedelta_rel_with_abs",
                ),
            ),
            encoding="utf-8",
        )
        return
    if decoy_id == "pytest_partial_source_test_materialization":
        old = "        rel_tolerance = rel * builtins.abs(expected) if rel is not None else None"
        new = "        rel_tolerance = rel if rel is not None else None"
        source_path.write_text(
            _replace_required(
                source,
                old,
                new,
                "accepted rel_tolerance scaling line missing",
            ),
            encoding="utf-8",
        )
        return
    raise IssuePrDecoyValidationError(f"unsupported pytest decoy id: {decoy_id}")


def _path_materialization(
    *,
    path: str,
    before_text: str,
    after_text: str,
    kind: str,
) -> dict[str, object]:
    target_key = "target_source_file" if kind == "source" else "target_test_file"
    record = {
        "status": "materialized" if before_text != after_text else "unchanged",
        target_key: path,
        "planned_changed_files": [path] if before_text != after_text else [],
        "changed": before_text != after_text,
        "sha256_before": _sha256_text(before_text),
        "sha256_after": _sha256_text(after_text),
        "diff_summary": _diff_summary(before_text, after_text),
        "diff": _unified_diff(before_text, after_text, path),
    }
    if path.endswith(".py"):
        record["ast_delta"] = python_ast_delta_metadata(before_text, after_text)
    return record


def _write_candidate_after_snapshots(
    *,
    checkout: Path,
    out_dir: Path,
    candidate_id: str,
    touched_files: Sequence[str],
    materializations: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    snapshot_root = out_dir / "snapshots" / _safe_id(candidate_id)
    snapshots: list[dict[str, object]] = []
    for touched_file in touched_files:
        source_path = checkout / touched_file
        if not source_path.is_file():
            continue
        snapshot_path = snapshot_root / touched_file
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        data = source_path.read_bytes()
        snapshot_path.write_bytes(data)
        materialization = _mapping(materializations.get(touched_file))
        snapshots.append(
            {
                "path": touched_file,
                "source_after_path": str(source_path),
                "after_snapshot_path": str(snapshot_path),
                "sha256_before": materialization.get("sha256_before"),
                "sha256_after": _sha256_bytes(data),
                "candidate_record_sha256_after": materialization.get("sha256_after"),
                "snapshot_sha256": _sha256_bytes(data),
                "size_bytes": len(data),
                "diff_summary": _json_copy(materialization.get("diff_summary", {})),
                "ast_delta": _json_copy(materialization.get("ast_delta", {})),
            }
        )
    return snapshots


def _candidate_after_record(
    *,
    candidate_id: str,
    replay_id: str,
    snapshots: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "available": bool(snapshots),
        "kind": "full_file_snapshot_bundle" if snapshots else "unavailable",
        "schema_version": ISSUE_PR_DECOY_VALIDATION_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "replay_id": replay_id,
        "touched_file_paths": [str(snapshot.get("path", "")) for snapshot in snapshots],
        "file_count": len(snapshots),
        "files": {
            str(snapshot.get("path", "")): {
                "path": str(snapshot.get("path", "")),
                "sha256_before": snapshot.get("sha256_before"),
                "sha256_after": snapshot.get("sha256_after"),
                "after_snapshot_path": snapshot.get("after_snapshot_path"),
                "diff_summary": _json_copy(snapshot.get("diff_summary", {})),
                "ast_delta": _json_copy(snapshot.get("ast_delta", {})),
            }
            for snapshot in snapshots
        },
        "embedding_available": False,
        "embedding": None,
    }


def _selected_specs(decoy_ids: Sequence[str] | None) -> tuple[ScrapyDecoySpec, ...]:
    if not decoy_ids:
        return SCRAPY_DECOY_SPECS
    by_id = {spec.decoy_id: spec for spec in SCRAPY_DECOY_SPECS}
    missing = [decoy_id for decoy_id in decoy_ids if decoy_id not in by_id]
    if missing:
        raise IssuePrDecoyValidationError(
            "unsupported Scrapy decoy ids: " + ", ".join(missing)
        )
    return tuple(by_id[decoy_id] for decoy_id in decoy_ids)


def _selected_pytest_specs(decoy_ids: Sequence[str] | None) -> tuple[PytestDecoySpec, ...]:
    if not decoy_ids:
        return PYTEST_DECOY_SPECS
    by_id = {spec.decoy_id: spec for spec in PYTEST_DECOY_SPECS}
    missing = [decoy_id for decoy_id in decoy_ids if decoy_id not in by_id]
    if missing:
        raise IssuePrDecoyValidationError(
            "unsupported pytest decoy ids: " + ", ".join(missing)
        )
    return tuple(by_id[decoy_id] for decoy_id in decoy_ids)


def _fresh_copytree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(".venv", "__pycache__", ".mypy_cache", ".pytest_cache")
    shutil.copytree(source, destination, symlinks=True, ignore=ignore)


def _deferred_validation(*, setup_command: str, validation_command: str) -> dict[str, object]:
    return {
        "status": "not_run",
        "setup_command": setup_command,
        "validation_command": validation_command,
        "runtime_seconds": 0.0,
    }


def _decoy_residual_labels(
    *,
    spec: ScrapyDecoySpec,
    validation_status: str,
    blockers: Sequence[Mapping[str, str]],
) -> list[str]:
    labels = [*spec.residual_labels]
    labels.extend(str(blocker.get("reason", "")) for blocker in blockers)
    if validation_status == "passed":
        labels.append("decoy_validation_passed")
    elif validation_status == "failed":
        labels.append("decoy_validation_failed")
    elif validation_status == "timeout":
        labels.append("decoy_validation_timeout")
    else:
        labels.append("decoy_validation_deferred")
    return _sorted_unique(labels)


def _pytest_decoy_residual_labels(
    *,
    spec: PytestDecoySpec,
    validation_status: str,
    blockers: Sequence[Mapping[str, str]],
) -> list[str]:
    labels = [*spec.residual_labels]
    labels.extend(str(blocker.get("reason", "")) for blocker in blockers)
    if validation_status == "passed":
        labels.append("decoy_validation_passed")
    elif validation_status == "failed":
        labels.append("decoy_validation_failed")
    elif validation_status == "timeout":
        labels.append("decoy_validation_timeout")
    else:
        labels.append("decoy_validation_deferred")
    return _sorted_unique(labels)


def _replace_required(
    text: str,
    old: str,
    new: str,
    missing_message: str,
) -> str:
    if old not in text:
        raise IssuePrDecoyValidationError(missing_message)
    return text.replace(old, new, 1)


def _remove_pytest_test_methods(text: str, method_names: Sequence[str]) -> str:
    result = text
    for method_name in method_names:
        lines = result.splitlines(keepends=True)
        start = None
        for index, line in enumerate(lines):
            if line.startswith(f"    def {method_name}(self):"):
                start = index
                break
        if start is None:
            raise IssuePrDecoyValidationError(
                f"accepted pytest test method missing: {method_name}"
            )
        end = len(lines)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.startswith("    def ") or line.startswith("class "):
                end = index
                break
        result = "".join(lines[:start] + lines[end:])
    return result


def _pytest_repo_before_scalar_dispatch_block() -> str:
    return "\n".join(
        [
            "    def _approx_scalar(self, x) -> ApproxScalar:",
            "        if isinstance(x, Decimal):",
            "            return ApproxDecimal(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
            "        return ApproxScalar(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
        ]
    )


def _pytest_accepted_scalar_dispatch_block() -> str:
    return "\n".join(
        [
            "    def _approx_scalar(self, x) -> ApproxBase:",
            "        if isinstance(x, Decimal):",
            "            return ApproxDecimal(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
            "        if isinstance(x, (datetime, timedelta)):",
            "            return ApproxTimedelta(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
            "        return ApproxScalar(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)",
        ]
    )


def _pytest_stale_rel_timedelta_block() -> str:
    return "\n".join(
        [
            "        if rel is not None and not isinstance(rel, timedelta):",
            "            raise TypeError(",
            "                f\"relative tolerance for timedelta must be a \"",
            "                f\"timedelta, got {type(rel).__name__}\"",
            "            )",
            "        tolerance = max(t for t in (abs, rel) if t is not None)",
            "        super().__init__(expected, rel=None, abs=tolerance, nan_ok=False)",
        ]
    )


def _pytest_accepted_rel_block() -> str:
    return "\n".join(
        [
            "        if abs is not None and abs < timedelta(0):",
            "            raise ValueError(f\"absolute tolerance can't be negative: {abs}\")",
            "        if rel is not None:",
            "            if not isinstance(rel, (int, float)):",
            "                raise TypeError(",
            "                    f\"relative tolerance for timedelta must be a \"",
            "                    f\"number, got {type(rel).__name__}\"",
            "                )",
            "            if rel < 0:",
            "                raise ValueError(f\"relative tolerance can't be negative: {rel}\")",
            "            if math.isnan(rel):",
            "                raise ValueError(\"relative tolerance can't be NaN.\")",
            "        # Compute the effective tolerance. abs_tolerance is a timedelta, rel * expected",
            "        # gives a timedelta (timedelta * float works in Python).",
            "        abs_tolerance = abs",
            "        rel_tolerance = rel * builtins.abs(expected) if rel is not None else None",
            "        if abs_tolerance is not None and rel_tolerance is not None:",
            "            tolerance = max(abs_tolerance, rel_tolerance)",
            "        else:",
            "            tolerance = abs_tolerance if abs_tolerance is not None else rel_tolerance",
            "        super().__init__(expected, rel=rel, abs=tolerance, nan_ok=False)",
        ]
    )


def _unified_diff(before_text: str, after_text: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _diff_summary(before_text: str, after_text: str) -> dict[str, int]:
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    diff = _unified_diff(before_text, after_text, "candidate")
    return {
        "hunk_count": sum(1 for line in diff.splitlines() if line.startswith("@@ ")),
        "changed_line_count": sum(
            max(i2 - i1, j2 - j1)
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                a=before_lines,
                b=after_lines,
            ).get_opcodes()
            if tag != "equal"
        ),
        "added_line_count": sum(
            1 for line in difflib.ndiff(before_lines, after_lines) if line.startswith("+ ")
        ),
        "removed_line_count": sum(
            1 for line in difflib.ndiff(before_lines, after_lines) if line.startswith("- ")
        ),
    }


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value)
        if text:
            counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _sorted_unique(values: object) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument(
        "--replay-id",
        choices=(SCRAPY_DOWNLOADER_AWARE_REPLAY_ID, PYTEST_TIMEDELTA_APPROX_REPLAY_ID),
        default=SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--setup-command", default=None)
    parser.add_argument(
        "--validation-command",
        default=None,
    )
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--decoy-id",
        action="append",
        dest="decoy_ids",
        help="Specific decoy id to materialize. May be supplied more than once.",
    )
    args = parser.parse_args(argv)

    if args.replay_id == PYTEST_TIMEDELTA_APPROX_REPLAY_ID:
        bundle = build_pytest_decoy_validation_bundle(
            args.repo_path,
            out_dir=args.out_dir,
            manifest_path=args.manifest,
            setup_command=args.setup_command or PYTEST_DECOY_SETUP_COMMAND,
            validation_command=(
                args.validation_command or PYTEST_DECOY_VALIDATION_COMMAND
            ),
            validate=args.validate,
            validation_timeout_seconds=args.timeout_seconds,
            decoy_ids=args.decoy_ids,
        )
    else:
        bundle = build_scrapy_decoy_validation_bundle(
            args.repo_path,
            out_dir=args.out_dir,
            manifest_path=args.manifest,
            setup_command=args.setup_command or DEFAULT_SETUP_COMMAND,
            validation_command=(
                args.validation_command or SCRAPY_DOWNLOADER_AWARE_VALIDATION_COMMAND
            ),
            validate=args.validate,
            validation_timeout_seconds=args.timeout_seconds,
            decoy_ids=args.decoy_ids,
        )
    artifacts = write_issue_pr_decoy_validation_bundle(bundle, out_dir=args.out_dir)
    print(json.dumps({name: str(path) for name, path in artifacts.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
