"""Structured prompt/spec records for issue/PR replay rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_preflight import (
    load_issue_pr_replay_manifest,
    select_issue_pr_replay_record,
    select_issue_pr_replay_records,
)


ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION = "issue-pr-prompt-spec-v1"
CLICK_DEFAULT_MAP_REPLAY_ID = "pallets__click-issue-2745-pr-3364"
DEFAULT_MAP_REQUIRED_FIELDS = (
    "minimal_reproduction",
    "observed_behavior",
    "expected_behavior",
    "affected_api_symbol",
    "input_shape",
    "acceptance_test_shape",
    "default_map_mutation_timing",
    "multi_value_parameter_shape",
    "string_splitting_semantics",
)


def build_issue_pr_prompt_spec(
    manifest: Mapping[str, object],
    replay_id: str,
    *,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    """Build a machine-readable prompt/spec record for one replay row."""

    record = select_issue_pr_replay_record(manifest, replay_id)
    if replay_id == CLICK_DEFAULT_MAP_REPLAY_ID:
        return _click_default_map_prompt_spec(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
        )

    return _blocked_prompt_spec(
        manifest=manifest,
        manifest_path=manifest_path,
        record=record,
        source_text_blockers=[
            {
                "source": "curated_prompt_normalizer",
                "availability": "missing",
                "impact": (
                    "No checked-in normalizer exists for this replay row, so "
                    "required prompt/spec fields cannot be trusted yet."
                ),
            }
        ],
    )


def build_issue_pr_prompt_specs(
    *,
    manifest_path: Path,
    replay_ids: Sequence[str] = (),
    limit: int | None = None,
) -> tuple[dict[str, object], ...]:
    """Build prompt/spec records for selected replay rows."""

    resolved = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(resolved)
    records = select_issue_pr_replay_records(
        manifest,
        replay_ids=replay_ids,
        limit=limit,
    )
    return tuple(
        build_issue_pr_prompt_spec(
            manifest,
            str(record["id"]),
            manifest_path=resolved,
        )
        for record in records
    )


def write_issue_pr_prompt_specs_jsonl(
    specs: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write prompt/spec records as JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for spec in specs:
            handle.write(json.dumps(dict(spec), sort_keys=True))
            handle.write("\n")
    return resolved


def summarize_issue_pr_prompt_specs(
    specs: Sequence[Mapping[str, object]],
    *,
    outcome_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    """Summarize prompt/spec normalization records."""

    status_counts = Counter(str(spec.get("status")) for spec in specs)
    missing_counts = Counter(
        field
        for spec in specs
        for field in _string_sequence(spec.get("missing_prompt_fields"))
    )
    blocker_counts = Counter(
        str(blocker.get("source"))
        for spec in specs
        for blocker in _mapping_sequence(spec.get("source_text_blockers"))
    )
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec_summary",
        "outcome_path": (
            str(outcome_path.expanduser().resolve()) if outcome_path else None
        ),
        "report_path": str(report_path.expanduser().resolve()) if report_path else None,
        "row_count": len(specs),
        "replay_ids": [str(spec.get("replay_id")) for spec in specs],
        "status_counts": dict(sorted(status_counts.items())),
        "missing_prompt_field_counts": dict(sorted(missing_counts.items())),
        "source_text_blocker_counts": dict(sorted(blocker_counts.items())),
        "candidate_code_edits_attempted": False,
    }


def write_issue_pr_prompt_spec_report(
    specs: Sequence[Mapping[str, object]],
    path: Path,
    *,
    summary: Mapping[str, object] | None = None,
) -> Path:
    """Write a compact Markdown report for prompt/spec records."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    report_summary = dict(summary or summarize_issue_pr_prompt_specs(specs))
    lines = [
        "# DATA-009 Click Default Map Prompt Spec",
        "",
        "Prompt/spec normalization only; no candidate source edits were attempted.",
        "",
        "## Summary",
        "",
        f"- Rows: `{report_summary.get('row_count', 0)}`",
        f"- Status counts: `{_json_inline(report_summary.get('status_counts', {}))}`",
        "- Missing prompt fields: "
        f"`{_json_inline(report_summary.get('missing_prompt_field_counts', {}))}`",
        "- Source text blockers: "
        f"`{_json_inline(report_summary.get('source_text_blocker_counts', {}))}`",
        "",
        "## Records",
        "",
    ]
    for spec in specs:
        lines.extend(_prompt_spec_markdown(spec))
    if report_summary.get("outcome_path"):
        lines.extend(["## Artifacts", "", f"- JSONL: `{report_summary['outcome_path']}`"])
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for prompt/spec normalization records."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--replay-id", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    specs = build_issue_pr_prompt_specs(
        manifest_path=args.manifest,
        replay_ids=tuple(args.replay_id),
        limit=args.limit,
    )
    out_path = write_issue_pr_prompt_specs_jsonl(specs, args.out)
    summary = summarize_issue_pr_prompt_specs(
        specs,
        outcome_path=out_path,
        report_path=args.report,
    )
    if args.report is not None:
        report_path = write_issue_pr_prompt_spec_report(
            specs,
            args.report,
            summary=summary,
        )
        summary["report_path"] = str(report_path)
    print(json.dumps(summary, sort_keys=True))
    return 0


def _click_default_map_prompt_spec(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path | None,
    record: Mapping[str, object],
) -> dict[str, object]:
    prompt_source = _mapping(record.get("prompt_source"))
    accepted_change = _mapping(record.get("accepted_change"))
    issue_url = str(prompt_source.get("issue_url") or "")
    pr_url = str(prompt_source.get("pull_request_url") or "")
    diff_url = str(accepted_change.get("diff_url") or "")
    field_provenance = {
        "minimal_reproduction": ["github_issue_2745"],
        "observed_behavior": ["github_issue_2745"],
        "expected_behavior": ["github_pr_3364_conversation", "github_pr_3364_diff"],
        "affected_api_symbol": ["github_pr_3364_diff"],
        "input_shape": ["github_issue_2745", "github_pr_3364_diff"],
        "acceptance_test_shape": ["github_pr_3364_diff"],
        "default_map_mutation_timing": ["github_issue_2745"],
        "multi_value_parameter_shape": ["github_issue_2745", "github_pr_3364_diff"],
        "string_splitting_semantics": [
            "github_pr_3364_conversation",
            "github_pr_3364_diff",
        ],
    }
    normalized_fields = {
        "minimal_reproduction": {
            "kind": "click_command_default_map_callback",
            "invocation": ["hello", "--settings", "hello"],
            "root_default_map": {},
            "group_callback_effect": {
                "target": "ctx.default_map['hello']",
                "value_shape": {"settings": "settings option value"},
            },
            "command_callbacks": [
                {
                    "callback": "load_settings",
                    "trigger_option": "--settings",
                    "is_eager": True,
                    "mutations": [
                        {
                            "target": "ctx.default_map['general_foo']",
                            "value_expression": "value + 'foo'",
                        },
                        {
                            "target": "ctx.default_map['general_bar']",
                            "value_expression": "value + 'bar'",
                        },
                    ],
                }
            ],
            "dependent_options": [
                {"name": "general_foo", "opts": ["--general-foo", "--foo"], "nargs": 2},
                {"name": "general_bar", "opts": ["--general-bar", "--bar"], "nargs": 1},
            ],
        },
        "observed_behavior": {
            "click_versions": ["8.0.0", "later"],
            "failure_mode": "multi_value_default_map_string_rejected",
            "error_option": "--general-foo / --foo",
            "error_summary": "Value must be an iterable.",
            "contrast_version": {
                "click_version": "7.1.2",
                "behavior": "string default_map value was unpacked character-by-character",
            },
        },
        "expected_behavior": {
            "behavior": "split_string_default_map_values_for_multi_value_parameters",
            "semantics": (
                "A string value read from default_map for a multi-value option is "
                "split the same way Click splits environment variable values, then "
                "normal arity and type conversion still apply."
            ),
            "single_value_string": "passed_through_without_splitting",
            "structured_sequence": "tuple_or_list_values_are_used_without_string_splitting",
            "cli_precedence": "explicit_cli_args_override_default_map",
        },
        "affected_api_symbol": {
            "public_surface": "click.Context.default_map",
            "parameter_surface": "click.Option",
            "implementation_symbol": "click.core.Option.consume_value",
            "changed_file": "src/click/core.py",
        },
        "input_shape": {
            "source": "default_map",
            "value_kind": "string",
            "examples": [
                {"default_map": {"point": "3 4"}, "option_kwargs": {"nargs": 2, "type": "int"}},
                {"default_map": {"point": "hello world"}, "option_kwargs": {"type": ["str", "str"]}},
                {"default_map": {"point": ["a", "b"]}, "option_kwargs": {"nargs": 2}},
            ],
        },
        "acceptance_test_shape": {
            "test_file": "tests/test_defaults.py",
            "test_name": "test_default_map_nargs",
            "cases": [
                "string default_map value splits for nargs=2 option",
                "string default_map value splits for explicit Tuple type",
                "tuple default_map value passes through unchanged",
                "list default_map value passes through unchanged",
                "CLI arguments override default_map for nargs > 1",
            ],
            "validation_command": "pytest tests/test_defaults.py -q",
        },
        "default_map_mutation_timing": {
            "timing": "during_eager_option_callback_before_dependent_option_defaults",
            "mutation_site": "load_settings callback for --settings",
            "consumer": "later option default resolution reads mutated ctx.default_map",
            "candidate_constraint": (
                "Do not assume default_map is immutable after command invocation; "
                "the spec requires callback-time mutations to be respected."
            ),
        },
        "multi_value_parameter_shape": {
            "nargs_option": {"opts": ["--general-foo", "--foo"], "nargs": 2},
            "tuple_type_option": {"type_shape": ["str", "str"], "effective_nargs": 2},
            "single_value_control": {"nargs": 1, "string_default_map_value": "not split"},
        },
        "string_splitting_semantics": {
            "condition": "isinstance(default_map_value, str) and parameter nargs != 1",
            "splitter": "ParamType.split_envvar_value",
            "default_delimiter": "whitespace",
            "matches": "value_from_envvar behavior",
            "not_split": ["tuple", "list", "single-value string"],
        },
    }
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": str(record.get("id")),
        "repo": str(record.get("repo")),
        "prompt_spec_kind": "click_default_map_multi_value_parameter",
        "status": "normalized",
        "candidate_code_edits_attempted": False,
        "required_prompt_fields": list(DEFAULT_MAP_REQUIRED_FIELDS),
        "missing_prompt_fields": [],
        "required_prompt_fields_complete": True,
        "source_text_blockers": [],
        "normalized_fields": normalized_fields,
        "field_provenance": field_provenance,
        "prompt_source": dict(prompt_source),
        "accepted_change": dict(accepted_change),
        "provenance": _prompt_spec_provenance(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            normalized_from=[
                {
                    "id": "github_issue_2745",
                    "kind": "github_issue",
                    "url": issue_url,
                    "fields": [
                        "minimal_reproduction",
                        "observed_behavior",
                        "default_map_mutation_timing",
                    ],
                },
                {
                    "id": "github_pr_3364_conversation",
                    "kind": "github_pull_request",
                    "url": pr_url,
                    "fields": ["expected_behavior", "string_splitting_semantics"],
                },
                {
                    "id": "github_pr_3364_diff",
                    "kind": "github_pull_request_diff",
                    "url": diff_url,
                    "merge_commit_sha": accepted_change.get("merge_commit_sha"),
                    "fields": [
                        "affected_api_symbol",
                        "acceptance_test_shape",
                        "multi_value_parameter_shape",
                        "string_splitting_semantics",
                    ],
                },
            ],
        ),
    }


def _blocked_prompt_spec(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path | None,
    record: Mapping[str, object],
    source_text_blockers: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": str(record.get("id")),
        "repo": str(record.get("repo")),
        "prompt_spec_kind": "unclassified_issue_pr_prompt",
        "status": "blocked",
        "candidate_code_edits_attempted": False,
        "required_prompt_fields": list(DEFAULT_MAP_REQUIRED_FIELDS),
        "missing_prompt_fields": list(DEFAULT_MAP_REQUIRED_FIELDS),
        "required_prompt_fields_complete": False,
        "source_text_blockers": [dict(blocker) for blocker in source_text_blockers],
        "normalized_fields": {},
        "field_provenance": {},
        "prompt_source": dict(_mapping(record.get("prompt_source"))),
        "accepted_change": dict(_mapping(record.get("accepted_change"))),
        "provenance": _prompt_spec_provenance(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
            normalized_from=[],
        ),
    }


def _prompt_spec_provenance(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path | None,
    record: Mapping[str, object],
    normalized_from: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "manifest_schema_version": manifest.get("schema_version"),
        "manifest_curated_at": manifest.get("curated_at"),
        "manifest_source": manifest.get("source"),
        "prompt_text": record.get("prompt_text"),
        "repo_before_ref": record.get("repo_before_ref"),
        "stable_split": record.get("stable_split"),
        "provenance_license": record.get("provenance_license"),
        "normalized_from": [dict(source) for source in normalized_from],
        "local_source_availability": {
            "compact_manifest_metadata": "available",
            "issue_body": "not_checked_in_manifest_available_at_prompt_source_url",
            "pull_request_body": "not_checked_in_manifest_available_at_prompt_source_url",
            "pull_request_diff": "not_checked_in_manifest_available_at_diff_url",
        },
    }


def _prompt_spec_markdown(spec: Mapping[str, object]) -> list[str]:
    replay_id = str(spec.get("replay_id"))
    status = str(spec.get("status"))
    fields = _mapping(spec.get("normalized_fields"))
    affected = _mapping(fields.get("affected_api_symbol"))
    acceptance = _mapping(fields.get("acceptance_test_shape"))
    lines = [f"### `{replay_id}`", "", f"- Status: `{status}`"]
    if affected:
        lines.append(
            "- Affected API: "
            f"`{affected.get('public_surface')}` via `{affected.get('implementation_symbol')}`"
        )
    if acceptance:
        lines.append(
            "- Acceptance test shape: "
            f"`{acceptance.get('test_file')}::{acceptance.get('test_name')}`"
        )
    missing = _string_sequence(spec.get("missing_prompt_fields"))
    if missing:
        lines.append(f"- Missing fields: `{_json_inline(list(missing))}`")
    blockers = _mapping_sequence(spec.get("source_text_blockers"))
    if blockers:
        lines.append(f"- Source blockers: `{_json_inline(blockers)}`")
    lines.append("")
    return lines


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
