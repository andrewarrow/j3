"""Audit accepted auxiliary materialization gaps for issue/PR candidates."""

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


AUXILIARY_GAP_AUDIT_SCHEMA_VERSION = "issue-pr-auxiliary-gap-audit-v1"
CLICK_DEFAULT_MAP_REPLAY_ID = "pallets__click-issue-2745-pr-3364"

COVERED_BY_CURRENT_STRUCTURED_ACTION = "covered_by_current_structured_action"
COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION = (
    "covered_by_small_proposed_deterministic_action"
)
REQUIRING_CONSTRAINED_LOCAL_GENERATOR = "requiring_constrained_local_generator"
NOT_CURRENTLY_EXPRESSIBLE = "not_currently_expressible"


@dataclass(frozen=True, slots=True)
class AuxiliaryPathFinding:
    path: str
    accepted_diff_summary: Mapping[str, object]
    classification: str
    current_action_family: str
    proposed_action_family: str
    validation_cost: Mapping[str, object]
    likely_failure_mode_if_attempted: str
    smallest_next_falsifiable_materializer_task: Mapping[str, object]


CLICK_DEFAULT_MAP_AUXILIARY_FINDINGS = (
    AuxiliaryPathFinding(
        path="CHANGES.rst",
        accepted_diff_summary={
            "change_kind": "rst_changelog_entry_insert",
            "added_line_count": 3,
            "removed_line_count": 0,
            "anchor": "Version 8.4.0 / Unreleased",
            "semantic_payload": (
                "release-note bullet for splitting string default_map values "
                "for multi-value parameters"
            ),
        },
        classification=COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION,
        current_action_family="none",
        proposed_action_family="rst_changelog_unreleased_bullet_insert_v1",
        validation_cost={
            "tier": "cheap",
            "commands": ["git diff --check", "python -m sphinx -b html docs /tmp/j3-docs"],
            "notes": "The materializer can be checked by exact path diff plus docs build.",
        },
        likely_failure_mode_if_attempted=(
            "wrong release-section anchor, duplicate release note, or malformed "
            "RST issue/pr role references"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-017-next-changelog-materializer",
            "description": (
                "Implement a deterministic RST changelog bullet inserter for the "
                "top Unreleased section, then compare the CHANGES.rst hunk against "
                "the accepted Click #3364 auxiliary hunk."
            ),
            "target_path": "CHANGES.rst",
            "expected_mutation_scope": ["CHANGES.rst"],
            "acceptance_probe": (
                "one three-line bullet is inserted under Version 8.4.0 / "
                "Unreleased and no source or test files change"
            ),
        },
    ),
    AuxiliaryPathFinding(
        path="docs/commands.md",
        accepted_diff_summary={
            "change_kind": "myst_markdown_section_insert",
            "added_line_count": 29,
            "removed_line_count": 0,
            "anchor": "before '## Context Defaults'",
            "semantic_payload": (
                "new Multi-value parameters subsection with prose, an options.md "
                "anchor link, and two Python examples"
            ),
        },
        classification=REQUIRING_CONSTRAINED_LOCAL_GENERATOR,
        current_action_family="none",
        proposed_action_family=(
            "click_default_map_docs_section_generator_v1 + "
            "myst_markdown_section_insert_v1"
        ),
        validation_cost={
            "tier": "moderate",
            "commands": ["git diff --check", "python -m sphinx -b html docs /tmp/j3-docs"],
            "notes": (
                "The insertion anchor is deterministic, but useful section text "
                "and examples require a constrained docs generator."
            ),
        },
        likely_failure_mode_if_attempted=(
            "generic or inaccurate docs prose, broken MyST roles or links, "
            "invalid examples, or insertion under the wrong command-doc section"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-017-next-docs-section-generator",
            "description": (
                "Build a constrained Click docs-section generator that receives "
                "the normalized prompt/spec facts and emits only the bounded "
                "default_map multi-value subsection payload."
            ),
            "target_path": "docs/commands.md",
            "expected_mutation_scope": ["docs/commands.md"],
            "acceptance_probe": (
                "the generated section has the expected heading, mentions "
                "nargs > 1 and Tuple behavior, includes one whitespace-split "
                "example, and passes a docs build"
            ),
        },
    ),
    AuxiliaryPathFinding(
        path="docs/conf.py",
        accepted_diff_summary={
            "change_kind": "sphinx_config_assignment_insert",
            "added_line_count": 1,
            "removed_line_count": 0,
            "anchor": "after intersphinx_mapping",
            "semantic_payload": "myst_heading_anchors = 3",
        },
        classification=COVERED_BY_SMALL_PROPOSED_DETERMINISTIC_ACTION,
        current_action_family="none",
        proposed_action_family="sphinx_conf_scalar_assignment_insert_v1",
        validation_cost={
            "tier": "cheap",
            "commands": ["python -m py_compile docs/conf.py", "git diff --check"],
            "notes": "A one-line Python assignment can be syntax-checked cheaply.",
        },
        likely_failure_mode_if_attempted=(
            "duplicate setting, insertion in a non-import-safe location, or "
            "silently stale docs behavior if the Markdown heading anchors are not built"
        ),
        smallest_next_falsifiable_materializer_task={
            "task_id": "DATA-017-next-sphinx-conf-assignment",
            "description": (
                "Implement a deterministic Sphinx config assignment inserter "
                "with duplicate-key detection and py_compile validation."
            ),
            "target_path": "docs/conf.py",
            "expected_mutation_scope": ["docs/conf.py"],
            "acceptance_probe": (
                "exactly one myst_heading_anchors = 3 assignment is inserted and "
                "docs/conf.py compiles"
            ),
        },
    ),
)


def build_issue_pr_auxiliary_gap_audit_rows(
    *,
    manifest_path: Path,
    candidate_artifact_path: Path,
    replay_id: str = CLICK_DEFAULT_MAP_REPLAY_ID,
    repo_path: Path | None = None,
) -> tuple[dict[str, object], ...]:
    """Build one auxiliary materialization-gap audit row per accepted path."""

    resolved_manifest = manifest_path.expanduser().resolve()
    resolved_candidate = candidate_artifact_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(resolved_manifest)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    candidate = _load_candidate_artifact(resolved_candidate, replay_id=replay_id)
    accepted_change = _mapping(replay_record.get("accepted_change"))
    repo_before_ref = _mapping(replay_record.get("repo_before_ref"))
    audited_paths = _audited_auxiliary_paths(candidate, replay_record)
    diff_stats = _accepted_diff_stats_by_path(
        repo_path=repo_path,
        before_sha=str(repo_before_ref.get("sha") or ""),
        merge_sha=str(accepted_change.get("merge_commit_sha") or ""),
        paths=audited_paths,
    )

    rows = []
    for finding in CLICK_DEFAULT_MAP_AUXILIARY_FINDINGS:
        if finding.path not in audited_paths:
            continue
        accepted_diff_summary = dict(finding.accepted_diff_summary)
        if finding.path in diff_stats:
            accepted_diff_summary["git_numstat"] = diff_stats[finding.path]
        rows.append(
            {
                "schema_version": AUXILIARY_GAP_AUDIT_SCHEMA_VERSION,
                "record_kind": "issue_pr_auxiliary_gap_audit",
                "audit_id": f"DATA-017/{replay_id}/{finding.path}",
                "replay_id": replay_id,
                "repo": str(replay_record.get("repo") or ""),
                "path": finding.path,
                "classification": finding.classification,
                "current_action_family": finding.current_action_family,
                "proposed_action_family": finding.proposed_action_family,
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
                "data014_candidate_provenance": _candidate_provenance(
                    candidate=candidate,
                    candidate_artifact_path=resolved_candidate,
                ),
            }
        )
    _append_unknown_path_rows(
        rows=rows,
        audited_paths=audited_paths,
        manifest=manifest,
        manifest_path=resolved_manifest,
        replay_record=replay_record,
        candidate=candidate,
        candidate_artifact_path=resolved_candidate,
    )
    return tuple(rows)


def write_issue_pr_auxiliary_gap_audit_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write auxiliary materialization-gap audit rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True))
            handle.write("\n")
    return resolved


def summarize_issue_pr_auxiliary_gap_audit_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    outcome_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Summarize path classifications and proposed action families."""

    classification_counts = Counter(str(row.get("classification")) for row in rows)
    proposed_action_counts = Counter(str(row.get("proposed_action_family")) for row in rows)
    replay_ids = sorted({str(row.get("replay_id")) for row in rows})
    return {
        "schema_version": AUXILIARY_GAP_AUDIT_SCHEMA_VERSION,
        "record_kind": "issue_pr_auxiliary_gap_audit_summary",
        "outcome_path": (
            str(outcome_path.expanduser().resolve()) if outcome_path else None
        ),
        "report_path": str(report_path.expanduser().resolve()) if report_path else None,
        "row_count": len(rows),
        "replay_ids": replay_ids,
        "paths": [str(row.get("path")) for row in rows],
        "classification_counts": dict(sorted(classification_counts.items())),
        "proposed_action_family_counts": dict(sorted(proposed_action_counts.items())),
        "current_action_covered_count": classification_counts.get(
            COVERED_BY_CURRENT_STRUCTURED_ACTION,
            0,
        ),
        "accepted_auxiliary_paths_fully_expressible_now": False,
    }


def write_issue_pr_auxiliary_gap_audit_report(
    rows: Sequence[Mapping[str, object]],
    path: Path,
    *,
    summary: Mapping[str, object] | None = None,
) -> Path:
    """Write a compact Markdown report for auxiliary materialization gaps."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    report_summary = dict(summary or summarize_issue_pr_auxiliary_gap_audit_rows(rows))
    lines = [
        "# DATA-017 Click Auxiliary Materialization Gap Audit",
        "",
        "Machine-readable audit over the DATA-014 accepted auxiliary paths. "
        "No candidate source edits were attempted.",
        "",
        "## Summary",
        "",
        f"- Rows: `{report_summary.get('row_count', 0)}`",
        "- Classification counts: "
        f"`{_json_inline(report_summary.get('classification_counts', {}))}`",
        "- Current structured-action covered paths: "
        f"`{report_summary.get('current_action_covered_count', 0)}`",
        "- Accepted auxiliary paths fully expressible now: "
        f"`{str(report_summary.get('accepted_auxiliary_paths_fully_expressible_now')).lower()}`",
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
            f"- Accepted diff summary: `{_json_inline(row.get('accepted_diff_summary', {}))}`"
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
    """CLI entrypoint for DATA-017 auxiliary materialization-gap audit."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument(
        "--candidate-artifact",
        type=Path,
        default=Path("/tmp/j3-data-014-live/candidate.json"),
    )
    parser.add_argument("--replay-id", default=CLICK_DEFAULT_MAP_REPLAY_ID)
    parser.add_argument("--repo-path", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    rows = build_issue_pr_auxiliary_gap_audit_rows(
        manifest_path=args.manifest,
        candidate_artifact_path=args.candidate_artifact,
        replay_id=args.replay_id,
        repo_path=args.repo_path,
    )
    out_path = write_issue_pr_auxiliary_gap_audit_jsonl(rows, args.out)
    summary = summarize_issue_pr_auxiliary_gap_audit_rows(
        rows,
        outcome_path=out_path,
        report_path=args.report,
    )
    if args.report is not None:
        report_path = write_issue_pr_auxiliary_gap_audit_report(
            rows,
            args.report,
            summary=summary,
        )
        summary["report_path"] = str(report_path)
    print(json.dumps(summary, sort_keys=True))
    return 0


def _load_candidate_artifact(path: Path, *, replay_id: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("candidate artifact must be a JSON object")
    if value.get("record_kind") != "issue_pr_candidate_attempt":
        raise ValueError("candidate artifact must be an issue_pr_candidate_attempt")
    if value.get("replay_id") != replay_id:
        raise ValueError(
            f"candidate artifact replay_id {value.get('replay_id')!r} "
            f"does not match {replay_id!r}"
        )
    return value


def _audited_auxiliary_paths(
    candidate: Mapping[str, object],
    replay_record: Mapping[str, object],
) -> tuple[str, ...]:
    mutation_scope = _mapping(candidate.get("mutation_scope"))
    paths = _string_sequence(mutation_scope.get("materialization_gap_paths"))
    if paths:
        return tuple(paths)
    accepted_change = _mapping(replay_record.get("accepted_change"))
    changed_files = set(_string_sequence(accepted_change.get("changed_files")))
    materialized = set(_string_sequence(mutation_scope.get("files_changed")))
    return tuple(sorted(changed_files - materialized))


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
    command = ["git", "diff", "--numstat", before_sha, merge_sha, "--", *paths]
    try:
        completed = subprocess.run(
            command,
            cwd=resolved,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if completed.returncode != 0:
        return {}
    stats: dict[str, dict[str, int]] = {}
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if added.isdigit() and removed.isdigit():
            stats[path] = {"added": int(added), "removed": int(removed)}
    return stats


def _append_unknown_path_rows(
    *,
    rows: list[dict[str, object]],
    audited_paths: Sequence[str],
    manifest: Mapping[str, object],
    manifest_path: Path,
    replay_record: Mapping[str, object],
    candidate: Mapping[str, object],
    candidate_artifact_path: Path,
) -> None:
    known_paths = {finding.path for finding in CLICK_DEFAULT_MAP_AUXILIARY_FINDINGS}
    for path in audited_paths:
        if path in known_paths:
            continue
        rows.append(
            {
                "schema_version": AUXILIARY_GAP_AUDIT_SCHEMA_VERSION,
                "record_kind": "issue_pr_auxiliary_gap_audit",
                "audit_id": f"DATA-017/{replay_record.get('id')}/{path}",
                "replay_id": str(replay_record.get("id") or ""),
                "repo": str(replay_record.get("repo") or ""),
                "path": path,
                "classification": NOT_CURRENTLY_EXPRESSIBLE,
                "current_action_family": "none",
                "proposed_action_family": "none",
                "accepted_diff_summary": {"change_kind": "unknown_auxiliary_path"},
                "validation_cost": {"tier": "unknown", "commands": []},
                "likely_failure_mode_if_attempted": (
                    "path is not part of the DATA-017 Click auxiliary audit scope"
                ),
                "smallest_next_falsifiable_materializer_task": {
                    "task_id": "needs-coordinator-scope",
                    "description": "Classify this additional path before materializing it.",
                    "target_path": path,
                    "expected_mutation_scope": [path],
                    "acceptance_probe": "path-specific classifier exists",
                },
                "manifest_provenance": _manifest_provenance(
                    manifest=manifest,
                    manifest_path=manifest_path,
                    replay_record=replay_record,
                ),
                "data014_candidate_provenance": _candidate_provenance(
                    candidate=candidate,
                    candidate_artifact_path=candidate_artifact_path,
                ),
            }
        )


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


def _candidate_provenance(
    *,
    candidate: Mapping[str, object],
    candidate_artifact_path: Path,
) -> dict[str, object]:
    mutation_scope = _mapping(candidate.get("mutation_scope"))
    validation = _mapping(candidate.get("validation"))
    structured_action_coverage = _mapping(candidate.get("structured_action_coverage"))
    return {
        "candidate_artifact_path": str(candidate_artifact_path),
        "candidate_id": candidate.get("candidate_id"),
        "record_kind": candidate.get("record_kind"),
        "schema_version": candidate.get("schema_version"),
        "status": candidate.get("status"),
        "action_family": candidate.get("action_family"),
        "materialized_files_changed": mutation_scope.get("files_changed", []),
        "materialization_gap_paths": mutation_scope.get("materialization_gap_paths", []),
        "structured_action_coverage": structured_action_coverage,
        "validation_status": validation.get("status"),
        "validation_runtime_seconds": validation.get("runtime_seconds"),
        "residual_labels": candidate.get("residual_labels", []),
    }


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _json_inline(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
