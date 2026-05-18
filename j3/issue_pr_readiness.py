"""Readiness gate for issue/PR replay candidate attempts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_preflight import (
    load_issue_pr_replay_manifest,
    select_issue_pr_replay_records,
)
from j3.issue_pr_prompt_spec import (
    PYTEST_STRICT_ADDOPTS_REPLAY_ID as PROMPT_SPEC_PYTEST_STRICT_ADDOPTS_REPLAY_ID,
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID as PROMPT_SPEC_PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID as PROMPT_SPEC_SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
    build_issue_pr_prompt_specs,
)
from j3.local_knowledge import (
    CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES,
    PYTEST_TIMEDELTA_APPROX_REQUIRED_KNOWLEDGE_CATEGORIES,
    REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    SCRAPY_DOWNLOADER_AWARE_REQUIRED_KNOWLEDGE_CATEGORIES,
)


ISSUE_PR_READINESS_SCHEMA_VERSION = "issue-pr-readiness-v1"
REQUESTS_REPLAY_ID = "psf__requests-issue-7432-pr-7433"
CLICK_DEFAULT_MAP_REPLAY_ID = "pallets__click-issue-2745-pr-3364"
CLICK_SEMVER_REPLAY_ID = "pallets__click-issue-3298-pr-3299"
PYTEST_STRICT_ADDOPTS_REPLAY_ID = PROMPT_SPEC_PYTEST_STRICT_ADDOPTS_REPLAY_ID
PYTEST_TIMEDELTA_APPROX_REPLAY_ID = PROMPT_SPEC_PYTEST_TIMEDELTA_APPROX_REPLAY_ID
SCRAPY_DOWNLOADER_AWARE_REPLAY_ID = PROMPT_SPEC_SCRAPY_DOWNLOADER_AWARE_REPLAY_ID
NEXT_STAGE_CHALLENGE_LABELS = ("materialization_gap", "ranking_gap")
REQUIRED_KNOWLEDGE_BY_REPLAY_ID = {
    REQUESTS_REPLAY_ID: REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    CLICK_SEMVER_REPLAY_ID: CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    PYTEST_STRICT_ADDOPTS_REPLAY_ID: PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES,
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID: (
        PYTEST_TIMEDELTA_APPROX_REQUIRED_KNOWLEDGE_CATEGORIES
    ),
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID: (
        SCRAPY_DOWNLOADER_AWARE_REQUIRED_KNOWLEDGE_CATEGORIES
    ),
}


def load_readiness_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Load JSONL evidence rows and attach their source path."""

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
        row.setdefault("_readiness_source_path", str(resolved))
        rows.append(row)
    return tuple(rows)


def load_readiness_jsonl_many(paths: Sequence[Path]) -> tuple[dict[str, object], ...]:
    """Load zero or more JSONL evidence files."""

    rows: list[dict[str, object]] = []
    for path in paths:
        rows.extend(load_readiness_jsonl(path))
    return tuple(rows)


def build_issue_pr_readiness_rows(
    *,
    manifest_path: Path,
    replay_ids: Sequence[str] = (),
    limit: int | None = None,
    preflight_records: Sequence[Mapping[str, object]] = (),
    validation_records: Sequence[Mapping[str, object]] = (),
    prompt_specs: Sequence[Mapping[str, object]] = (),
    local_knowledge_records: Sequence[Mapping[str, object]] = (),
) -> tuple[dict[str, object], ...]:
    """Build one candidate-readiness row per selected issue/PR replay id."""

    resolved_manifest = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(resolved_manifest)
    replay_records = select_issue_pr_replay_records(
        manifest,
        replay_ids=replay_ids,
        limit=limit,
    )
    selected_ids = tuple(str(record["id"]) for record in replay_records)
    generated_specs = build_issue_pr_prompt_specs(
        manifest_path=resolved_manifest,
        replay_ids=selected_ids,
    )
    spec_by_replay_id = _index_best_prompt_specs((*generated_specs, *prompt_specs))
    preflight_by_replay_id = _index_last_by_replay_id(preflight_records)
    validation_by_replay_id = _index_many_by_replay_id(validation_records)
    knowledge_by_replay_id = _index_many_local_knowledge(local_knowledge_records)

    rows = []
    for replay_record in replay_records:
        replay_id = str(replay_record["id"])
        rows.append(
            _build_readiness_row(
                manifest=manifest,
                manifest_path=resolved_manifest,
                replay_record=replay_record,
                prompt_spec=spec_by_replay_id.get(replay_id),
                preflight_record=preflight_by_replay_id.get(replay_id),
                validation_records=validation_by_replay_id.get(replay_id, ()),
                local_knowledge_records=knowledge_by_replay_id.get(replay_id, ()),
            )
        )
    return tuple(rows)


def write_issue_pr_readiness_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write readiness rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True))
            handle.write("\n")
    return resolved


def summarize_issue_pr_readiness_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    outcome_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Summarize readiness status, missing evidence, and next-stage residuals."""

    status_counts = Counter(
        "ready" if row.get("ready_for_candidate_attempt") is True else "blocked"
        for row in rows
    )
    missing_counts = Counter(
        label
        for row in rows
        for label in _string_sequence(row.get("missing_evidence_labels"))
    )
    next_stage_counts = Counter(
        label
        for row in rows
        for label in _string_sequence(row.get("next_stage_challenge_labels"))
    )
    evidence_type_counts = Counter(
        str(evidence.get("evidence_type"))
        for row in rows
        for evidence in _mapping_sequence(row.get("evidence_sources"))
    )
    return {
        "schema_version": ISSUE_PR_READINESS_SCHEMA_VERSION,
        "record_kind": "issue_pr_candidate_readiness_summary",
        "outcome_path": (
            str(outcome_path.expanduser().resolve()) if outcome_path else None
        ),
        "report_path": str(report_path.expanduser().resolve()) if report_path else None,
        "row_count": len(rows),
        "replay_ids": [str(row.get("replay_id")) for row in rows],
        "ready_replay_ids": [
            str(row.get("replay_id"))
            for row in rows
            if row.get("ready_for_candidate_attempt") is True
        ],
        "status_counts": dict(sorted(status_counts.items())),
        "missing_evidence_label_counts": dict(sorted(missing_counts.items())),
        "next_stage_challenge_label_counts": dict(sorted(next_stage_counts.items())),
        "evidence_type_counts": dict(sorted(evidence_type_counts.items())),
        "candidate_code_edits_attempted": False,
    }


def write_issue_pr_readiness_report(
    rows: Sequence[Mapping[str, object]],
    path: Path,
    *,
    summary: Mapping[str, object] | None = None,
    title: str = "Issue/PR Candidate Readiness Gate",
) -> Path:
    """Write a compact Markdown readiness report."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    report_summary = dict(summary or summarize_issue_pr_readiness_rows(rows))
    lines = [
        f"# {title}",
        "",
        "Readiness scoring only; no candidate source edits were attempted.",
        "",
        "## Summary",
        "",
        f"- Rows: `{report_summary.get('row_count', 0)}`",
        f"- Status counts: `{_json_inline(report_summary.get('status_counts', {}))}`",
        "- Missing evidence: "
        f"`{_json_inline(report_summary.get('missing_evidence_label_counts', {}))}`",
        "- Next-stage challenges: "
        f"`{_json_inline(report_summary.get('next_stage_challenge_label_counts', {}))}`",
        "- Ready replay ids: "
        f"`{_json_inline(report_summary.get('ready_replay_ids', []))}`",
        "",
        "## Rows",
        "",
        "| Replay | Repo | Ready | Missing evidence | Validation command | Recommendation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        missing = ", ".join(_string_sequence(row.get("missing_evidence_labels"))) or "none"
        lines.append(
            "| `{replay_id}` | `{repo}` | `{ready}` | `{missing}` | `{command}` | `{rec}` |".format(
                replay_id=row.get("replay_id"),
                repo=row.get("repo"),
                ready=str(row.get("ready_for_candidate_attempt")).lower(),
                missing=missing,
                command=row.get("validation_command") or "",
                rec=row.get("blocker_recommendation"),
            )
        )
    lines.extend(["", "## Evidence", ""])
    for row in rows:
        lines.append(f"### `{row.get('replay_id')}`")
        lines.append("")
        lines.append(
            f"- Allowed write scope: `{_json_inline(row.get('allowed_write_scope', {}))}`"
        )
        if row.get("accepted_edit_scope_note"):
            lines.append(f"- Accepted edit scope note: {row['accepted_edit_scope_note']}")
        lines.append(
            f"- Residual labels: `{_json_inline(row.get('residual_labels', []))}`"
        )
        lines.append(
            "- Next-stage challenge labels: "
            f"`{_json_inline(row.get('next_stage_challenge_labels', []))}`"
        )
        for challenge in _mapping_sequence(row.get("next_stage_challenges")):
            lines.append(
                "- Next-stage challenge: `{label}` - {detail}".format(
                    label=challenge.get("label"),
                    detail=challenge.get("remaining_challenge"),
                )
            )
        for evidence in _mapping_sequence(row.get("evidence_sources")):
            lines.append(
                "- Evidence: `{kind}` `{evidence_id}` from `{source}`".format(
                    kind=evidence.get("evidence_type"),
                    evidence_id=evidence.get("id"),
                    source=evidence.get("source"),
                )
            )
        lines.append("")
    if report_summary.get("outcome_path"):
        lines.extend(["## Artifacts", "", f"- JSONL: `{report_summary['outcome_path']}`"])
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for issue/PR replay readiness scoring."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--replay-id", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--preflight-evidence", type=Path, action="append", default=[])
    parser.add_argument("--validation-evidence", type=Path, action="append", default=[])
    parser.add_argument("--prompt-spec-evidence", type=Path, action="append", default=[])
    parser.add_argument("--local-knowledge-evidence", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--report-title",
        default="Issue/PR Candidate Readiness Gate",
    )
    args = parser.parse_args(argv)

    rows = build_issue_pr_readiness_rows(
        manifest_path=args.manifest,
        replay_ids=tuple(args.replay_id),
        limit=args.limit,
        preflight_records=load_readiness_jsonl_many(args.preflight_evidence),
        validation_records=load_readiness_jsonl_many(args.validation_evidence),
        prompt_specs=load_readiness_jsonl_many(args.prompt_spec_evidence),
        local_knowledge_records=load_readiness_jsonl_many(args.local_knowledge_evidence),
    )
    out_path = write_issue_pr_readiness_jsonl(rows, args.out)
    summary = summarize_issue_pr_readiness_rows(
        rows,
        outcome_path=out_path,
        report_path=args.report,
    )
    if args.report is not None:
        report_path = write_issue_pr_readiness_report(
            rows,
            args.report,
            summary=summary,
            title=args.report_title,
        )
        summary["report_path"] = str(report_path)
    print(json.dumps(summary, sort_keys=True))
    return 0


def _build_readiness_row(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path,
    replay_record: Mapping[str, object],
    prompt_spec: Mapping[str, object] | None,
    preflight_record: Mapping[str, object] | None,
    validation_records: Sequence[Mapping[str, object]],
    local_knowledge_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    replay_id = str(replay_record["id"])
    accepted_change = _mapping(replay_record.get("accepted_change"))
    validation = _mapping(replay_record.get("validation"))
    changed_files = _string_sequence(accepted_change.get("changed_files"))
    manifest_validation_command = str(validation.get("command") or "")
    validation_command, validation_evidence = _validation_command_and_evidence(
        replay_id=replay_id,
        manifest_validation_command=manifest_validation_command,
        preflight_record=preflight_record,
        validation_records=validation_records,
        local_knowledge_records=local_knowledge_records,
    )
    prompt_ok, prompt_missing, prompt_evidence = _prompt_spec_status(prompt_spec)
    required_knowledge = _required_knowledge_categories(
        replay_id=replay_id,
        replay_record=replay_record,
        preflight_record=preflight_record,
    )
    (
        missing_knowledge,
        knowledge_evidence,
        knowledge_categories_present,
    ) = _local_knowledge_status(
        required_categories=required_knowledge,
        local_knowledge_records=local_knowledge_records,
    )

    missing_labels: list[str] = []
    if not prompt_ok:
        missing_labels.append("missing_prompt_spec")
        missing_labels.extend(f"missing_prompt_field:{field}" for field in prompt_missing)
    validation_ok = any(
        evidence.get("status") == "passed" for evidence in validation_evidence
    )
    if not validation_ok:
        missing_labels.append(
            "failing_validation_evidence"
            if validation_evidence
            else "missing_validation_evidence"
        )
    missing_labels.extend(
        f"missing_local_knowledge:{category}" for category in missing_knowledge
    )

    ready = not missing_labels
    next_stage = _next_stage_challenge_labels(replay_record, changed_files)
    allowed_write_scope = _allowed_write_scope(changed_files)
    residual_labels = _residual_labels(
        replay_record=replay_record,
        prompt_ok=prompt_ok,
        validation_ok=validation_ok,
        local_knowledge_ok=not missing_knowledge,
        next_stage_labels=next_stage,
    )
    evidence_sources = (
        [item for item in (prompt_evidence,) if item]
        + validation_evidence
        + knowledge_evidence
    )
    evidence_counts = Counter(
        str(evidence.get("evidence_type")) for evidence in evidence_sources
    )
    return {
        "schema_version": ISSUE_PR_READINESS_SCHEMA_VERSION,
        "record_kind": "issue_pr_candidate_readiness",
        "replay_id": replay_id,
        "repo": str(replay_record.get("repo") or ""),
        "ready_for_candidate_attempt": ready,
        "blocker_recommendation": _recommendation(
            ready=ready,
            missing_labels=missing_labels,
            next_stage_labels=next_stage,
        ),
        "evidence_ids": [str(evidence.get("id")) for evidence in evidence_sources],
        "evidence_counts": dict(sorted(evidence_counts.items())),
        "evidence_sources": evidence_sources,
        "missing_evidence_labels": sorted(missing_labels),
        "allowed_write_scope": allowed_write_scope,
        "accepted_edit_scope_note": _accepted_edit_scope_note(allowed_write_scope),
        "validation_command": validation_command,
        "required_local_knowledge_categories": list(required_knowledge),
        "local_knowledge_categories_present": sorted(knowledge_categories_present),
        "residual_labels": residual_labels,
        "next_stage_challenge_labels": list(next_stage),
        "next_stage_challenges": _next_stage_challenges(
            next_stage,
            allowed_write_scope,
        ),
        "candidate_code_edits_attempted": False,
        "provenance": {
            "manifest_path": str(manifest_path),
            "manifest_schema_version": manifest.get("schema_version"),
            "manifest_curated_at": manifest.get("curated_at"),
            "prompt_source": replay_record.get("prompt_source"),
            "repo_before_ref": replay_record.get("repo_before_ref"),
            "accepted_change": replay_record.get("accepted_change"),
            "stable_split": replay_record.get("stable_split"),
        },
    }


def _validation_command_and_evidence(
    *,
    replay_id: str,
    manifest_validation_command: str,
    preflight_record: Mapping[str, object] | None,
    validation_records: Sequence[Mapping[str, object]],
    local_knowledge_records: Sequence[Mapping[str, object]],
) -> tuple[str, list[dict[str, object]]]:
    evidence: list[dict[str, object]] = []
    selected_command = manifest_validation_command
    for record in validation_records:
        if record.get("record_kind") != "issue_pr_validation_recipe_attempt":
            continue
        command = str(record.get("validation_command") or "")
        if record.get("status") == "passed" and command:
            selected_command = command
        evidence.append(
            {
                "evidence_type": "validation",
                "id": f"DATA-008/{replay_id}/{record.get('recipe_name', 'recipe')}",
                "source": _source_path(record),
                "record_kind": record.get("record_kind"),
                "status": record.get("status"),
                "validation_command": command,
            }
        )
    if preflight_record is not None and _preflight_baseline_passed(preflight_record):
        command = str(preflight_record.get("validation_command") or "")
        selected_command = selected_command or command
        evidence.append(
            {
                "evidence_type": "validation",
                "id": f"DATA-006/{replay_id}/baseline_validation",
                "source": _source_path(preflight_record),
                "record_kind": preflight_record.get("record_kind"),
                "status": "passed",
                "validation_command": command,
            }
        )
    for record in local_knowledge_records:
        if record.get("record_type") != "validation_recipe_record":
            continue
        data = _mapping(record.get("data"))
        commands = _string_sequence(data.get("focused_commands"))
        if commands and not selected_command:
            selected_command = commands[0]
    return selected_command, evidence


def _prompt_spec_status(
    prompt_spec: Mapping[str, object] | None,
) -> tuple[bool, list[str], dict[str, object] | None]:
    if prompt_spec is None:
        return False, [], None
    missing_fields = _string_sequence(prompt_spec.get("missing_prompt_fields"))
    ok = (
        prompt_spec.get("status") == "normalized"
        and prompt_spec.get("required_prompt_fields_complete") is True
        and not missing_fields
    )
    evidence = {
        "evidence_type": "prompt_spec",
        "id": f"prompt-spec/{prompt_spec.get('replay_id')}/{prompt_spec.get('prompt_spec_kind')}",
        "source": _source_path(prompt_spec)
        or "j3.issue_pr_prompt_spec.build_issue_pr_prompt_specs",
        "record_kind": prompt_spec.get("record_kind"),
        "status": prompt_spec.get("status"),
        "missing_prompt_fields": missing_fields,
    }
    return ok, missing_fields, evidence


def _required_knowledge_categories(
    *,
    replay_id: str,
    replay_record: Mapping[str, object],
    preflight_record: Mapping[str, object] | None,
) -> tuple[str, ...]:
    from_preflight: list[str] = []
    if preflight_record is not None:
        for detail in _mapping_sequence(preflight_record.get("blocker_details")):
            from_preflight.extend(
                _string_sequence(detail.get("required_knowledge_categories"))
            )
    initial_labels = set(_string_sequence(replay_record.get("initial_residual_labels")))
    static_required = (
        REQUIRED_KNOWLEDGE_BY_REPLAY_ID.get(replay_id, ())
        if "local_knowledge_gap" in initial_labels
        else ()
    )
    if static_required:
        return tuple(static_required)
    return tuple(dict.fromkeys((*from_preflight, *static_required)))


def _local_knowledge_status(
    *,
    required_categories: Sequence[str],
    local_knowledge_records: Sequence[Mapping[str, object]],
) -> tuple[list[str], list[dict[str, object]], set[str]]:
    records_by_category: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in local_knowledge_records:
        category = _knowledge_category(record)
        if category:
            records_by_category[category].append(record)

    evidence: list[dict[str, object]] = []
    for category in required_categories:
        for record in records_by_category.get(category, ()):
            evidence.append(
                {
                    "evidence_type": "local_knowledge",
                    "id": str(record.get("id") or f"local-knowledge/{category}"),
                    "source": _source_path(record),
                    "record_kind": record.get("record_type"),
                    "status": "available",
                    "knowledge_category": category,
                }
            )
    present = set(records_by_category)
    missing = [category for category in required_categories if category not in present]
    return missing, evidence, present


def _index_best_prompt_specs(
    prompt_specs: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    by_replay: dict[str, Mapping[str, object]] = {}
    for spec in prompt_specs:
        replay_id = str(spec.get("replay_id") or "")
        if not replay_id:
            continue
        current = by_replay.get(replay_id)
        if current is None or _prompt_spec_rank(spec) >= _prompt_spec_rank(current):
            by_replay[replay_id] = spec
    return by_replay


def _prompt_spec_rank(spec: Mapping[str, object]) -> int:
    if spec.get("status") == "normalized" and spec.get("required_prompt_fields_complete") is True:
        return 2
    if spec.get("record_kind") == "issue_pr_prompt_spec":
        return 1
    return 0


def _index_last_by_replay_id(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for row in rows:
        replay_id = str(row.get("replay_id") or "")
        if replay_id:
            result[replay_id] = row
    return result


def _index_many_by_replay_id(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, tuple[Mapping[str, object], ...]]:
    result: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        replay_id = str(row.get("replay_id") or "")
        if replay_id:
            result[replay_id].append(row)
    return {key: tuple(value) for key, value in result.items()}


def _index_many_local_knowledge(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, tuple[Mapping[str, object], ...]]:
    result: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        links = _mapping(row.get("links"))
        task_ids = _string_sequence(links.get("task_ids"))
        for task_id in task_ids:
            result[task_id].append(row)
    return {key: tuple(value) for key, value in result.items()}


def _preflight_baseline_passed(row: Mapping[str, object]) -> bool:
    if row.get("first_failed_stage") not in {"none", None}:
        return False
    for result in _mapping_sequence(row.get("command_results")):
        if result.get("name") == "baseline_validation":
            return result.get("passed") is True
    return "baseline_validation" in _string_sequence(row.get("command_stages_reached"))


def _knowledge_category(record: Mapping[str, object]) -> str:
    data = _mapping(record.get("data"))
    return str(data.get("knowledge_category") or "")


def _allowed_write_scope(changed_files: Sequence[str]) -> dict[str, object]:
    source_paths = [path for path in changed_files if not _is_test_file(path)]
    python_source_paths = [
        path for path in changed_files if _is_python_source_file(path)
    ]
    test_paths = [path for path in changed_files if _is_test_file(path)]
    source_test_paths = [*python_source_paths, *test_paths]
    auxiliary_paths = [path for path in changed_files if path not in source_test_paths]
    return {
        "paths": list(changed_files),
        "source_paths": source_paths,
        "python_source_paths": python_source_paths,
        "test_paths": test_paths,
        "source_test_paths": source_test_paths,
        "auxiliary_paths": auxiliary_paths,
        "full_accepted_edit_scope_paths": list(changed_files),
        "policy": "candidate_attempt_must_stay_within_accepted_change_paths",
    }


def _next_stage_challenge_labels(
    replay_record: Mapping[str, object],
    changed_files: Sequence[str],
) -> tuple[str, ...]:
    labels = set(_string_sequence(replay_record.get("initial_residual_labels")))
    labels.add("ranking_gap")
    if any(not _is_test_file(path) for path in changed_files):
        labels.add("materialization_gap")
    return tuple(label for label in NEXT_STAGE_CHALLENGE_LABELS if label in labels)


def _residual_labels(
    *,
    replay_record: Mapping[str, object],
    prompt_ok: bool,
    validation_ok: bool,
    local_knowledge_ok: bool,
    next_stage_labels: Sequence[str],
) -> list[str]:
    labels = set(_string_sequence(replay_record.get("initial_residual_labels")))
    if prompt_ok:
        labels.discard("prompt_spec_parsing_gap")
    else:
        labels.add("prompt_spec_parsing_gap")
    if validation_ok:
        labels.discard("validation_gap")
    else:
        labels.add("validation_gap")
    if local_knowledge_ok:
        labels.discard("local_knowledge_gap")
    else:
        labels.add("local_knowledge_gap")
    labels.update(next_stage_labels)
    return sorted(labels)


def _recommendation(
    *,
    ready: bool,
    missing_labels: Sequence[str],
    next_stage_labels: Sequence[str],
) -> str:
    if ready:
        return (
            "ready_for_candidate_attempt; next_stage_challenge="
            + ",".join(next_stage_labels)
        )
    return "blocked_until_evidence:" + ",".join(sorted(missing_labels))


def _next_stage_challenges(
    labels: Sequence[str],
    allowed_write_scope: Mapping[str, object],
) -> list[dict[str, object]]:
    source_test_paths = _string_sequence(allowed_write_scope.get("source_test_paths"))
    auxiliary_paths = _string_sequence(allowed_write_scope.get("auxiliary_paths"))
    challenges: list[dict[str, object]] = []
    for label in labels:
        if label == "materialization_gap":
            if auxiliary_paths:
                remaining_challenge = (
                    "materialize the accepted source/test edit paths "
                    f"{source_test_paths}; full accepted-edit parity also "
                    "requires either auxiliary materializers or explicit "
                    f"exclusion for {auxiliary_paths}"
                )
            else:
                remaining_challenge = (
                    "materialize the accepted source/test edit paths "
                    f"{source_test_paths}; source/test scope matches the full "
                    "accepted edit scope"
                )
            challenges.append(
                {
                    "label": label,
                    "remaining_challenge": remaining_challenge,
                    "source_test_paths": source_test_paths,
                    "auxiliary_paths": auxiliary_paths,
                }
            )
        elif label == "ranking_gap":
            challenges.append(
                {
                    "label": label,
                    "remaining_challenge": (
                        "rank the candidate action sequence against decoys using "
                        "repo-state, prompt/spec, validation, and local-knowledge "
                        "evidence before any guarded use"
                    ),
                }
            )
        else:
            challenges.append(
                {
                    "label": label,
                    "remaining_challenge": "unclassified next-stage challenge",
                }
            )
    return challenges


def _accepted_edit_scope_note(allowed_write_scope: Mapping[str, object]) -> str:
    source_test_paths = _string_sequence(allowed_write_scope.get("source_test_paths"))
    auxiliary_paths = _string_sequence(allowed_write_scope.get("auxiliary_paths"))
    if not auxiliary_paths:
        return (
            "Source/test candidate scope matches the full accepted edit scope: "
            f"{source_test_paths}."
        )
    return (
        "Source/test candidate scope covers "
        f"{source_test_paths}; full accepted-edit scope also includes auxiliary "
        f"paths {auxiliary_paths}, which require auxiliary materializers or an "
        "explicit source/test-only scope decision."
    )


def _is_python_source_file(path: str) -> bool:
    return path.endswith(".py") and not _is_test_file(path)


def _is_test_file(path: str) -> bool:
    name = Path(path).name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or path.startswith(("test/", "tests/", "testing/"))
        or "/test" in path
    )


def _source_path(row: Mapping[str, object]) -> str:
    explicit = row.get("_readiness_source_path")
    if isinstance(explicit, str):
        return explicit
    source = row.get("source")
    if isinstance(source, Mapping):
        repo = str(source.get("repo") or "")
        path = str(source.get("path") or "")
        return ":".join(part for part in (repo, path) if part)
    provenance = row.get("provenance")
    if isinstance(provenance, Mapping):
        manifest_path = provenance.get("manifest_path")
        if isinstance(manifest_path, str):
            return manifest_path
    return ""


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_sequence(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _json_inline(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
