"""Audit accepted-path materialization coverage for issue/PR replays."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_preflight import (
    load_issue_pr_replay_manifest,
    select_issue_pr_replay_record,
)


MATERIALIZATION_AUDIT_SCHEMA_VERSION = "issue-pr-materialization-audit-v1"
PYTEST_STRICT_ADDOPTS_REPLAY_ID = "pytest-dev__pytest-issue-14442-pr-14443"
PYTEST_TIMEDELTA_APPROX_REPLAY_ID = "pytest-dev__pytest-issue-14462-pr-14466"

COVERED_BY_CURRENT_STRUCTURED_ACTION = "covered_by_current_structured_action"
COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION = (
    "covered_by_small_proposed_deterministic_action"
)
REQUIRING_CONSTRAINED_LOCAL_GENERATOR = (
    "requiring_constrained_local_generator_or_source_region_action"
)
NOT_CURRENTLY_EXPRESSIBLE = "not_currently_expressible"


@dataclass(frozen=True, slots=True)
class MaterializationPathFinding:
    path: str
    accepted_diff_summary: Mapping[str, object]
    classification: str
    current_action_family: str
    proposed_action_family: str
    action_family_recommendation: str
    validation_cost: Mapping[str, object]
    likely_failure_mode_if_attempted: str
    smallest_next_falsifiable_materializer_task: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class MaterializationAuditDefinition:
    task_id: str
    report_title: str
    report_description: str
    out_of_scope_failure_mode: str
    findings: tuple[MaterializationPathFinding, ...]


PYTEST_STRICT_ADDOPTS_FINDINGS = (
    MaterializationPathFinding(
        path="AUTHORS",
        accepted_diff_summary={
            "change_kind": "newline_delimited_contributor_insert",
            "accepted_numstat": {"added": 2, "removed": 0},
            "added_entries": ["Hamza Mobeen", "Praneeth Kodumagulla"],
            "anchor": "alphabetical contributor-list positions",
            "semantic_payload": "two contributor names added to the AUTHORS roster",
        },
        classification=COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION,
        current_action_family="none",
        proposed_action_family="newline_delimited_sorted_unique_insert_v1",
        action_family_recommendation=(
            "Add a deterministic newline-delimited contributor inserter, but require "
            "an explicit contributor-name payload from provenance or local knowledge."
        ),
        validation_cost={
            "tier": "cheap",
            "commands": ["git diff --check"],
            "notes": (
                "No behavior test is needed; validate sorted unique insertion, "
                "duplicate avoidance, and whitespace only."
            ),
        },
        likely_failure_mode_if_attempted=(
            "missing or incomplete contributor-name evidence, duplicate insertion, "
            "or locale/case ordering drift in the AUTHORS file"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-023-next-authors-inserter",
            "description": (
                "Implement a deterministic sorted newline-entry inserter for AUTHORS "
                "and prove it inserts exactly the accepted two names in the repo-before "
                "checkout without touching behavior files."
            ),
            "target_path": "AUTHORS",
            "expected_mutation_scope": ["AUTHORS"],
            "acceptance_probe": (
                "AUTHORS contains the two accepted names once, in sorted neighborhood "
                "position, and git diff --check passes"
            ),
        },
    ),
    MaterializationPathFinding(
        path="changelog/14442.bugfix.rst",
        accepted_diff_summary={
            "change_kind": "towncrier_bugfix_fragment_create",
            "accepted_numstat": {"added": 3, "removed": 0},
            "anchor": "new changelog/<issue>.bugfix.rst fragment",
            "semantic_payload": (
                "bugfix note for strict markers/config from addopts, with pytest "
                "documentation roles"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family="none",
        proposed_action_family=(
            "pytest_bugfix_changelog_fragment_generator_v1 + "
            "towncrier_fragment_create_v1"
        ),
        action_family_recommendation=(
            "Use a deterministic fragment-path creator plus a constrained local "
            "changelog-text generator that can emit pytest Sphinx roles."
        ),
        validation_cost={
            "tier": "cheap_to_moderate",
            "commands": ["git diff --check"],
            "notes": (
                "The file path is deterministic, but the release-note text needs "
                "semantic validation against the prompt/spec and accepted behavior."
            ),
        },
        likely_failure_mode_if_attempted=(
            "generic changelog prose, missing issue-specific regression wording, "
            "broken Sphinx roles, duplicate fragment, or wrong fragment suffix"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-023-next-pytest-changelog-fragment",
            "description": (
                "Build a pytest bugfix-fragment materializer for one issue-numbered "
                "RST file using DATA-021 prompt/spec fields as input."
            ),
            "target_path": "changelog/14442.bugfix.rst",
            "expected_mutation_scope": ["changelog/14442.bugfix.rst"],
            "acceptance_probe": (
                "the fragment is a new .bugfix.rst file, mentions strict options "
                "from addopts, uses valid pytest docs roles, and passes diff checks"
            ),
        },
    ),
    MaterializationPathFinding(
        path="src/_pytest/config/__init__.py",
        accepted_diff_summary={
            "change_kind": "python_import_plus_config_parse_region_update",
            "accepted_numstat": {"added": 7, "removed": 0},
            "anchors": [
                "from .findpaths import determine_setup",
                "Config.parse after final addopts parse_known_args",
            ],
            "semantic_payload": (
                "import parse_override_ini, apply override_ini values derived from "
                "addopts once, and clear _inicache"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family=(
            "source_region_replace_v1 exists, but the accepted edit is "
            "non-contiguous and also needs an import insertion"
        ),
        proposed_action_family=(
            "python_from_import_insert_v1 + "
            "config_parse_addopts_override_source_region_v1"
        ),
        action_family_recommendation=(
            "Split into a deterministic import inserter plus a bounded source-region "
            "action inside Config.parse, generated from the strict-addopts spec."
        ),
        validation_cost={
            "tier": "moderate",
            "commands": [
                "python -m py_compile src/_pytest/config/__init__.py",
                "pytest testing/test_config.py testing/test_mark.py -q",
            ],
            "notes": (
                "Syntax is cheap; behavior needs the focused strict config/mark tests "
                "because parse-order regressions are easy to miss."
            ),
        },
        likely_failure_mode_if_attempted=(
            "missing import, update placed before addopts is parsed, stale _inicache, "
            "recursive addopts behavior beyond the accepted one-level fix, or "
            "unintended override_ini ordering changes"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-023-next-config-parse-region",
            "description": (
                "Materialize only the accepted Config.parse import plus bounded "
                "override update in a repo-before checkout, then run the focused "
                "pytest strict-addopts tests."
            ),
            "target_path": "src/_pytest/config/__init__.py",
            "expected_mutation_scope": ["src/_pytest/config/__init__.py"],
            "acceptance_probe": (
                "py_compile passes, the diff has one parse_override_ini import and "
                "one post-addopts override update, and focused pytest validation passes"
            ),
        },
    ),
    MaterializationPathFinding(
        path="testing/test_config.py",
        accepted_diff_summary={
            "change_kind": "pytest_parametrize_method_refine",
            "accepted_numstat": {"added": 10, "removed": 5},
            "anchor": "TestParseIni.test_strict_config_ini_option",
            "semantic_payload": (
                "extend strict-config coverage with addopts = --strict-config"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family=(
            "deterministic pytest insertion/replacement exists only for prior "
            "bounded replay fixtures"
        ),
        proposed_action_family="pytest_parametrize_existing_test_refine_v1",
        action_family_recommendation=(
            "Use a constrained pytest-test updater that can replace one selected "
            "test method and validate the changed case count against prompt/spec facts."
        ),
        validation_cost={
            "tier": "moderate",
            "commands": ["pytest testing/test_config.py -q"],
            "notes": (
                "The edit is test-only, but the selected test module is large enough "
                "that the focused module command is the useful behavior check."
            ),
        },
        likely_failure_mode_if_attempted=(
            "wrong parametrized variable rewrite, addopts case inserted without "
            "preserving strict/strict_config coverage, or brittle string matching "
            "inside the existing test class"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-023-next-test-config-parametrize-refine",
            "description": (
                "Implement a constrained existing-pytest-test refiner for one "
                "parametrized test method and prove it can add the addopts "
                "--strict-config case without changing unrelated tests."
            ),
            "target_path": "testing/test_config.py",
            "expected_mutation_scope": ["testing/test_config.py"],
            "acceptance_probe": (
                "only test_strict_config_ini_option changes, it has the accepted "
                "three option cases, and pytest testing/test_config.py -q passes"
            ),
        },
    ),
    MaterializationPathFinding(
        path="testing/test_mark.py",
        accepted_diff_summary={
            "change_kind": "pytest_parametrize_function_refine",
            "accepted_numstat": {"added": 13, "removed": 8},
            "anchor": "test_strict_prohibits_unregistered_markers",
            "semantic_payload": (
                "extend strict-markers coverage with addopts = --strict-markers "
                "while preserving CLI and ini strict cases"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family=(
            "deterministic pytest insertion/replacement exists only for prior "
            "bounded replay fixtures"
        ),
        proposed_action_family="pytest_parametrize_existing_test_refine_v1",
        action_family_recommendation=(
            "Use the same constrained pytest-test updater as testing/test_config.py, "
            "with branch-shape checks for CLI options versus ini option text."
        ),
        validation_cost={
            "tier": "moderate",
            "commands": ["pytest testing/test_mark.py -q"],
            "notes": (
                "Focused module validation catches the strict-marker behavior and "
                "keeps the cost lower than the full pytest suite."
            ),
        },
        likely_failure_mode_if_attempted=(
            "misclassifying addopts as a CLI argument, losing legacy --strict or "
            "strict ini coverage, or inserting the new case in the wrong marker test"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-023-next-test-mark-parametrize-refine",
            "description": (
                "Extend the constrained existing-pytest-test refiner to a top-level "
                "function with CLI-versus-ini branching and materialize the accepted "
                "strict-markers addopts case."
            ),
            "target_path": "testing/test_mark.py",
            "expected_mutation_scope": ["testing/test_mark.py"],
            "acceptance_probe": (
                "only test_strict_prohibits_unregistered_markers changes, it has "
                "the accepted five option cases, and pytest testing/test_mark.py -q passes"
            ),
        },
    ),
)


PYTEST_TIMEDELTA_APPROX_FINDINGS = (
    MaterializationPathFinding(
        path="src/_pytest/python_api.py",
        accepted_diff_summary={
            "change_kind": "python_approx_timedelta_dispatch_and_tolerance_update",
            "accepted_numstat": {"added": 31, "removed": 12},
            "anchors": [
                "ApproxBase._approx_scalar",
                "ApproxTimedelta.__init__",
                "approx datetime/timedelta documentation",
            ],
            "semantic_payload": (
                "dispatch datetime/timedelta values inside containers to "
                "ApproxTimedelta, accept numeric timedelta rel values, validate "
                "negative/NaN rel and negative abs, compute rel * abs(expected), "
                "and keep datetime rel unsupported"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family=(
            "source_region_replace_v1 exists, but the accepted edit spans "
            "dispatch typing, ApproxTimedelta validation/tolerance logic, and "
            "documentation text"
        ),
        proposed_action_family=(
            "pytest_approx_timedelta_source_region_update_v1 + "
            "python_dispatch_branch_insert_v1"
        ),
        action_family_recommendation=(
            "Use a bounded source-region materializer for ApproxTimedelta.__init__ "
            "plus a deterministic dispatch branch inserter in ApproxBase._approx_scalar; "
            "gate it on DATA-026 relative-tolerance and datetime-policy facts."
        ),
        validation_cost={
            "tier": "moderate",
            "commands": [
                "python -m py_compile src/_pytest/python_api.py",
                "pytest testing/python/approx.py -q",
            ],
            "notes": (
                "Syntax is cheap; behavior needs the focused approx test module "
                "because container dispatch and datetime rejection are easy to "
                "regress while fixing timedelta rel."
            ),
        },
        likely_failure_mode_if_attempted=(
            "accepting rel for datetime by accident, continuing to treat timedelta "
            "rel as an absolute timedelta, failing sequence/mapping dispatch, "
            "missing negative or NaN validation, or comparing against the actual "
            "value rather than abs(expected)"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-028-next-approx-timedelta-source-region",
            "description": (
                "Materialize only the accepted ApproxBase._approx_scalar dispatch "
                "branch plus ApproxTimedelta.__init__ tolerance update in the "
                "repo-before checkout, without editing tests first."
            ),
            "target_path": "src/_pytest/python_api.py",
            "expected_mutation_scope": ["src/_pytest/python_api.py"],
            "acceptance_probe": (
                "py_compile passes, the diff changes only the dispatch branch and "
                "ApproxTimedelta/docstring regions, datetime rel still raises, and "
                "focused approx validation can run after tests are materialized"
            ),
        },
    ),
    MaterializationPathFinding(
        path="testing/python/approx.py",
        accepted_diff_summary={
            "change_kind": "pytest_datetime_test_class_refine_and_extend",
            "accepted_numstat": {"added": 95, "removed": 5},
            "anchors": [
                "TestApproxDatetime.test_timedelta_rel_within_tolerance",
                "TestApproxDatetime.test_timedelta_rel_outside_tolerance",
                "TestApproxDatetime container dispatch tests",
            ],
            "semantic_payload": (
                "change timedelta rel tests from timedelta rel values to numeric "
                "fractions, add invalid rel/abs validation cases, abs+rel and zero "
                "rel coverage, expected-value scaling coverage, and datetime/"
                "timedelta sequence and mapping dispatch tests"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family=(
            "deterministic pytest insertion/replacement exists only for prior "
            "bounded replay fixtures and cannot yet refine this class plus append "
            "the accepted datetime/timedelta cases"
        ),
        proposed_action_family="pytest_existing_class_method_refine_and_insert_v1",
        action_family_recommendation=(
            "Use a constrained pytest test-class refiner that can replace selected "
            "methods, rename one method, and insert focused methods under "
            "TestApproxDatetime using DATA-026 acceptance-test facts."
        ),
        validation_cost={
            "tier": "moderate",
            "commands": ["pytest testing/python/approx.py -q"],
            "notes": (
                "The module command is cheap in DATA-018 and covers source/test "
                "interaction, including skips from optional numpy tests."
            ),
        },
        likely_failure_mode_if_attempted=(
            "adding generic timedelta cases without expected-value scaling, "
            "forgetting container dispatch, preserving the obsolete rel=timedelta "
            "expectation, or placing tests outside TestApproxDatetime conventions"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-028-next-approx-test-class-refiner",
            "description": (
                "Implement a constrained TestApproxDatetime refiner that changes "
                "the two existing rel tests and appends the smallest representative "
                "numeric-rel validation, scaling, and container cases."
            ),
            "target_path": "testing/python/approx.py",
            "expected_mutation_scope": ["testing/python/approx.py"],
            "acceptance_probe": (
                "only TestApproxDatetime changes, obsolete rel=timedelta assertions "
                "are replaced, numeric rel scaling and sequence/mapping cases exist, "
                "and pytest testing/python/approx.py -q passes with the source edit"
            ),
        },
    ),
)


AUDIT_DEFINITIONS = {
    PYTEST_STRICT_ADDOPTS_REPLAY_ID: MaterializationAuditDefinition(
        task_id="DATA-023",
        report_title="DATA-023 Pytest #14442 Materialization Coverage Audit",
        report_description=(
            "Machine-readable audit over the accepted pytest #14442/#14443 changed "
            "paths. No candidate source edits were attempted."
        ),
        out_of_scope_failure_mode=(
            "path is not part of the DATA-023 pytest #14442 audit scope"
        ),
        findings=PYTEST_STRICT_ADDOPTS_FINDINGS,
    ),
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID: MaterializationAuditDefinition(
        task_id="DATA-028",
        report_title="DATA-028 Pytest #14462 Materialization Coverage Audit",
        report_description=(
            "Machine-readable audit over the accepted pytest #14462/#14466 changed "
            "paths. No candidate source edits were attempted."
        ),
        out_of_scope_failure_mode=(
            "path is not part of the DATA-028 pytest #14462 audit scope"
        ),
        findings=PYTEST_TIMEDELTA_APPROX_FINDINGS,
    ),
}


def build_issue_pr_materialization_audit_rows(
    *,
    manifest_path: Path,
    replay_id: str = PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    repo_path: Path | None = None,
    preflight_outcome_path: Path | None = None,
    prompt_spec_evidence_path: Path | None = None,
    local_knowledge_evidence_path: Path | None = None,
) -> tuple[dict[str, object], ...]:
    """Build one materialization coverage audit row per accepted changed path."""

    resolved_manifest = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(resolved_manifest)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    accepted_change = _mapping(replay_record.get("accepted_change"))
    repo_before_ref = _mapping(replay_record.get("repo_before_ref"))
    accepted_paths = _string_sequence(accepted_change.get("changed_files"))
    diff_stats = _accepted_diff_stats_by_path(
        repo_path=repo_path,
        before_sha=str(repo_before_ref.get("sha") or ""),
        merge_sha=str(accepted_change.get("merge_commit_sha") or ""),
        paths=accepted_paths,
    )
    evidence_provenance = _evidence_provenance(
        replay_id=replay_id,
        preflight_outcome_path=preflight_outcome_path,
        prompt_spec_evidence_path=prompt_spec_evidence_path,
        local_knowledge_evidence_path=local_knowledge_evidence_path,
    )

    rows: list[dict[str, object]] = []
    audit_definition = AUDIT_DEFINITIONS.get(
        replay_id,
        MaterializationAuditDefinition(
            task_id="needs-classification",
            report_title="Issue/PR Materialization Coverage Audit",
            report_description=(
                "Machine-readable audit over accepted changed paths. No candidate "
                "source edits were attempted."
            ),
            out_of_scope_failure_mode=(
                "path is not part of a classified materialization audit scope"
            ),
            findings=(),
        ),
    )
    findings_by_path = {finding.path: finding for finding in audit_definition.findings}
    for path in accepted_paths:
        finding = findings_by_path.get(path)
        if finding is None:
            rows.append(
                _unknown_path_row(
                    path=path,
                    audit_definition=audit_definition,
                    manifest=manifest,
                    manifest_path=resolved_manifest,
                    replay_record=replay_record,
                    evidence_provenance=evidence_provenance,
                )
            )
            continue
        accepted_diff_summary = dict(finding.accepted_diff_summary)
        if path in diff_stats:
            accepted_diff_summary["git_diff_stats"] = diff_stats[path]
        rows.append(
            {
                "schema_version": MATERIALIZATION_AUDIT_SCHEMA_VERSION,
                "record_kind": "issue_pr_materialization_audit",
                "audit_id": f"{audit_definition.task_id}/{replay_id}/{path}",
                "audit_task_id": audit_definition.task_id,
                "replay_id": replay_id,
                "repo": str(replay_record.get("repo") or ""),
                "path": path,
                "classification": finding.classification,
                "current_action_family": finding.current_action_family,
                "proposed_action_family": finding.proposed_action_family,
                "action_family_recommendation": finding.action_family_recommendation,
                "accepted_diff_summary": accepted_diff_summary,
                "validation_cost": dict(finding.validation_cost),
                "likely_failure_mode_if_attempted": (
                    finding.likely_failure_mode_if_attempted
                ),
                "smallest_next_falsifiable_materializer_task": dict(
                    finding.smallest_next_falsifiable_materializer_task
                ),
                "manifest_provenance": _manifest_provenance(
                    manifest=manifest,
                    manifest_path=resolved_manifest,
                    replay_record=replay_record,
                ),
                "evidence_provenance": evidence_provenance,
                "audit_provenance": _audit_provenance(audit_definition.task_id),
            }
        )
    return tuple(rows)


def write_issue_pr_materialization_audit_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write materialization coverage audit rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True))
            handle.write("\n")
    return resolved


def summarize_issue_pr_materialization_audit_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    outcome_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Summarize path classifications and recommended action families."""

    classification_counts = Counter(str(row.get("classification")) for row in rows)
    proposed_action_counts = Counter(str(row.get("proposed_action_family")) for row in rows)
    paths = [str(row.get("path")) for row in rows]
    return {
        "schema_version": MATERIALIZATION_AUDIT_SCHEMA_VERSION,
        "record_kind": "issue_pr_materialization_audit_summary",
        "outcome_path": (
            str(outcome_path.expanduser().resolve()) if outcome_path else None
        ),
        "report_path": str(report_path.expanduser().resolve()) if report_path else None,
        "row_count": len(rows),
        "replay_ids": sorted({str(row.get("replay_id")) for row in rows}),
        "paths": paths,
        "classification_counts": dict(sorted(classification_counts.items())),
        "proposed_action_family_counts": dict(sorted(proposed_action_counts.items())),
        "current_action_covered_count": classification_counts.get(
            COVERED_BY_CURRENT_STRUCTURED_ACTION,
            0,
        ),
        "accepted_paths_fully_expressible_now": (
            bool(rows) and classification_counts == {COVERED_BY_CURRENT_STRUCTURED_ACTION: len(rows)}
        ),
    }


def write_issue_pr_materialization_audit_report(
    rows: Sequence[Mapping[str, object]],
    path: Path,
    *,
    summary: Mapping[str, object] | None = None,
) -> Path:
    """Write a compact Markdown report for materialization coverage."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    report_summary = dict(summary or summarize_issue_pr_materialization_audit_rows(rows))
    audit_definition = _audit_definition_for_rows(rows)
    lines = [
        f"# {audit_definition.report_title}",
        "",
        audit_definition.report_description,
        "",
        "## Summary",
        "",
        f"- Rows: `{report_summary.get('row_count', 0)}`",
        "- Classification counts: "
        f"`{_json_inline(report_summary.get('classification_counts', {}))}`",
        "- Current structured-action covered paths: "
        f"`{report_summary.get('current_action_covered_count', 0)}`",
        "- Accepted paths fully expressible now: "
        f"`{str(report_summary.get('accepted_paths_fully_expressible_now')).lower()}`",
        "",
        "## Path Audit",
        "",
        "| Path | Classification | Current action | Proposed action | Validation cost |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        validation_cost = _mapping(row.get("validation_cost"))
        lines.append(
            "| `{path}` | `{classification}` | `{current}` | `{proposed}` | `{tier}` |".format(
                path=row.get("path"),
                classification=row.get("classification"),
                current=row.get("current_action_family"),
                proposed=row.get("proposed_action_family"),
                tier=validation_cost.get("tier", ""),
            )
        )
    lines.extend(["", "## Findings", ""])
    for row in rows:
        lines.append(f"### `{row.get('path')}`")
        lines.append("")
        lines.append(
            f"- Accepted diff stats: `{_json_inline(row.get('accepted_diff_summary', {}))}`"
        )
        lines.append(
            f"- Action recommendation: {row.get('action_family_recommendation')}"
        )
        lines.append(
            "- Likely failure mode: "
            f"{row.get('likely_failure_mode_if_attempted')}"
        )
        task = _mapping(row.get("smallest_next_falsifiable_materializer_task"))
        lines.append(f"- Smallest next task: `{task.get('task_id')}`")
        lines.append(f"- Probe: {task.get('acceptance_probe')}")
        lines.append("")
    if report_summary.get("outcome_path"):
        lines.extend(["## Artifacts", "", f"- JSONL: `{report_summary['outcome_path']}`"])
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for issue/PR materialization coverage audit."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--replay-id", default=PYTEST_STRICT_ADDOPTS_REPLAY_ID)
    parser.add_argument("--repo-path", type=Path)
    parser.add_argument("--preflight-outcome", type=Path)
    parser.add_argument("--prompt-spec-evidence", type=Path)
    parser.add_argument("--local-knowledge-evidence", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    rows = build_issue_pr_materialization_audit_rows(
        manifest_path=args.manifest,
        replay_id=args.replay_id,
        repo_path=args.repo_path,
        preflight_outcome_path=args.preflight_outcome,
        prompt_spec_evidence_path=args.prompt_spec_evidence,
        local_knowledge_evidence_path=args.local_knowledge_evidence,
    )
    out_path = write_issue_pr_materialization_audit_jsonl(rows, args.out)
    summary = summarize_issue_pr_materialization_audit_rows(
        rows,
        outcome_path=out_path,
        report_path=args.report,
    )
    if args.report is not None:
        report_path = write_issue_pr_materialization_audit_report(
            rows,
            args.report,
            summary=summary,
        )
        summary["report_path"] = str(report_path)
    print(json.dumps(summary, sort_keys=True))
    return 0


def _accepted_diff_stats_by_path(
    *,
    repo_path: Path | None,
    before_sha: str,
    merge_sha: str,
    paths: Sequence[str],
) -> dict[str, dict[str, int]]:
    if repo_path is None or not before_sha or not merge_sha:
        return {}
    resolved = repo_path.expanduser().resolve()
    if not resolved.exists():
        return {}
    numstat = _git_numstat(
        repo_path=resolved,
        before_sha=before_sha,
        merge_sha=merge_sha,
        paths=paths,
    )
    hunk_counts = _git_hunk_counts(
        repo_path=resolved,
        before_sha=before_sha,
        merge_sha=merge_sha,
        paths=paths,
    )
    stats = dict(numstat)
    for path, hunk_count in hunk_counts.items():
        stats.setdefault(path, {"added": 0, "removed": 0})
        stats[path]["hunk_count"] = hunk_count
    return stats


def _git_numstat(
    *,
    repo_path: Path,
    before_sha: str,
    merge_sha: str,
    paths: Sequence[str],
) -> dict[str, dict[str, int]]:
    completed = _run_git_diff(
        repo_path=repo_path,
        args=["--numstat", before_sha, merge_sha, "--", *paths],
    )
    stats: dict[str, dict[str, int]] = {}
    for line in completed.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if added.isdigit() and removed.isdigit():
            stats[path] = {"added": int(added), "removed": int(removed)}
    return stats


def _git_hunk_counts(
    *,
    repo_path: Path,
    before_sha: str,
    merge_sha: str,
    paths: Sequence[str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        diff = _run_git_diff(
            repo_path=repo_path,
            args=["--unified=0", before_sha, merge_sha, "--", path],
        )
        if diff:
            counts[path] = sum(1 for line in diff.splitlines() if line.startswith("@@ "))
    return counts


def _run_git_diff(*, repo_path: Path, args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", *args],
            cwd=repo_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _manifest_provenance(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path,
    replay_record: Mapping[str, object],
) -> dict[str, object]:
    return {
        "manifest_path": str(manifest_path),
        "manifest_schema_version": manifest.get("schema_version"),
        "manifest_curated_at": manifest.get("curated_at"),
        "prompt_source": replay_record.get("prompt_source"),
        "repo_before_ref": replay_record.get("repo_before_ref"),
        "accepted_change": replay_record.get("accepted_change"),
        "stable_split": replay_record.get("stable_split"),
    }


def _evidence_provenance(
    *,
    replay_id: str,
    preflight_outcome_path: Path | None,
    prompt_spec_evidence_path: Path | None,
    local_knowledge_evidence_path: Path | None,
) -> dict[str, object]:
    return {
        "preflight_outcome": _preflight_summary(preflight_outcome_path, replay_id),
        "prompt_spec_evidence": _jsonl_summary(
            prompt_spec_evidence_path,
            replay_id=replay_id,
            record_kind_field="record_kind",
        ),
        "local_knowledge_evidence": _jsonl_summary(
            local_knowledge_evidence_path,
            replay_id=replay_id,
            record_kind_field="record_type",
        ),
    }


def _preflight_summary(path: Path | None, replay_id: str) -> dict[str, object] | None:
    rows = _load_jsonl_records(path)
    for row in rows:
        if row.get("replay_id") != replay_id:
            continue
        command_results = [
            {
                "name": result.get("name"),
                "passed": result.get("passed"),
                "runtime_seconds": result.get("runtime_seconds"),
            }
            for result in _mapping_sequence(row.get("command_results"))
        ]
        return {
            "path": str(path.expanduser().resolve()) if path else None,
            "schema_version": row.get("schema_version"),
            "record_kind": row.get("record_kind"),
            "status": row.get("status"),
            "validation_command": row.get("validation_command"),
            "first_failed_stage": row.get("first_failed_stage"),
            "command_results": command_results,
        }
    return None


def _jsonl_summary(
    path: Path | None,
    *,
    replay_id: str,
    record_kind_field: str,
) -> dict[str, object] | None:
    rows = [row for row in _load_jsonl_records(path) if _row_matches_replay(row, replay_id)]
    if not rows:
        return None
    return {
        "path": str(path.expanduser().resolve()) if path else None,
        "row_count": len(rows),
        "schema_versions": sorted({str(row.get("schema_version")) for row in rows}),
        "record_kinds": sorted({str(row.get(record_kind_field)) for row in rows}),
        "ids": [str(row.get("id")) for row in rows if row.get("id") is not None],
    }


def _load_jsonl_records(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return []
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in resolved.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, Mapping):
            rows.append(dict(value))
    return rows


def _row_matches_replay(row: Mapping[str, object], replay_id: str) -> bool:
    if row.get("replay_id") == replay_id:
        return True
    data = _mapping(row.get("data"))
    if data.get("replay_id") == replay_id:
        return True
    links = _mapping(row.get("links"))
    task_ids = _string_sequence(links.get("task_ids"))
    return replay_id in task_ids


def _unknown_path_row(
    *,
    path: str,
    audit_definition: MaterializationAuditDefinition,
    manifest: Mapping[str, object],
    manifest_path: Path,
    replay_record: Mapping[str, object],
    evidence_provenance: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_version": MATERIALIZATION_AUDIT_SCHEMA_VERSION,
        "record_kind": "issue_pr_materialization_audit",
        "audit_id": f"{audit_definition.task_id}/{replay_record.get('id')}/{path}",
        "audit_task_id": audit_definition.task_id,
        "replay_id": str(replay_record.get("id") or ""),
        "repo": str(replay_record.get("repo") or ""),
        "path": path,
        "classification": NOT_CURRENTLY_EXPRESSIBLE,
        "current_action_family": "none",
        "proposed_action_family": "none",
        "action_family_recommendation": "classify this accepted path before materializing it",
        "accepted_diff_summary": {"change_kind": "unknown_accepted_path"},
        "validation_cost": {"tier": "unknown", "commands": []},
        "likely_failure_mode_if_attempted": audit_definition.out_of_scope_failure_mode,
        "smallest_next_falsifiable_materializer_task": {
            "task_id": "needs-coordinator-scope",
            "description": "Classify this accepted path before materializing it.",
            "target_path": path,
            "expected_mutation_scope": [path],
            "acceptance_probe": "path-specific classifier exists",
        },
        "manifest_provenance": _manifest_provenance(
            manifest=manifest,
            manifest_path=manifest_path,
            replay_record=replay_record,
        ),
        "evidence_provenance": dict(evidence_provenance),
        "audit_provenance": _audit_provenance(audit_definition.task_id),
    }


def _audit_provenance(task_id: str) -> list[str]:
    if task_id == "DATA-028":
        return ["DATA-018", "DATA-026", "DATA-028"]
    if task_id == "DATA-023":
        return ["DATA-018", "DATA-021", "DATA-023"]
    return [task_id]


def _audit_definition_for_rows(
    rows: Sequence[Mapping[str, object]],
) -> MaterializationAuditDefinition:
    replay_ids = [str(row.get("replay_id")) for row in rows if row.get("replay_id")]
    if replay_ids:
        definition = AUDIT_DEFINITIONS.get(replay_ids[0])
        if definition is not None:
            return definition
    return MaterializationAuditDefinition(
        task_id="needs-classification",
        report_title="Issue/PR Materialization Coverage Audit",
        report_description=(
            "Machine-readable audit over accepted changed paths. No candidate "
            "source edits were attempted."
        ),
        out_of_scope_failure_mode=(
            "path is not part of a classified materialization audit scope"
        ),
        findings=(),
    )


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_sequence(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _json_inline(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
