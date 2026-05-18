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
REQUESTS_PREPARE_BODY_REPLAY_ID = "psf__requests-issue-7432-pr-7433"
CLICK_SEMVER_DEFAULT_REPLAY_ID = "pallets__click-issue-3298-pr-3299"
PYTEST_STRICT_ADDOPTS_REPLAY_ID = "pytest-dev__pytest-issue-14442-pr-14443"
PYTEST_TIMEDELTA_APPROX_REPLAY_ID = "pytest-dev__pytest-issue-14462-pr-14466"
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
REQUESTS_PREPARE_BODY_REQUIRED_FIELDS = (
    "minimal_reproduction",
    "observed_behavior",
    "expected_behavior",
    "affected_api_symbol",
    "input_shape",
    "acceptance_test_shape",
    "getattr_file_wrapper_behavior",
    "stream_detection_semantics",
    "redirect_rewind_behavior",
)
CLICK_SEMVER_DEFAULT_REQUIRED_FIELDS = (
    "minimal_reproduction",
    "observed_behavior",
    "expected_behavior",
    "affected_api_symbol",
    "input_shape",
    "acceptance_test_shape",
    "non_string_default_behavior",
    "type_conversion_semantics",
    "empty_string_check_scope",
    "third_party_semver_version_reproduction_context",
)
PYTEST_STRICT_ADDOPTS_REQUIRED_FIELDS = (
    "minimal_reproduction",
    "observed_behavior",
    "expected_behavior",
    "affected_api_symbol",
    "input_shape",
    "acceptance_test_shape",
    "strict_addopts_behavior",
    "strict_markers_config_semantics",
)
PYTEST_TIMEDELTA_APPROX_REQUIRED_FIELDS = (
    "minimal_reproduction",
    "observed_behavior",
    "expected_behavior",
    "affected_api_symbol",
    "input_shape",
    "acceptance_test_shape",
    "relative_tolerance_semantics",
    "datetime_timedelta_comparison_behavior",
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
    if replay_id == REQUESTS_PREPARE_BODY_REPLAY_ID:
        return _requests_prepare_body_prompt_spec(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
        )
    if replay_id == CLICK_SEMVER_DEFAULT_REPLAY_ID:
        return _click_semver_default_prompt_spec(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
        )
    if replay_id == PYTEST_STRICT_ADDOPTS_REPLAY_ID:
        return _pytest_strict_addopts_prompt_spec(
            manifest=manifest,
            manifest_path=manifest_path,
            record=record,
        )
    if replay_id == PYTEST_TIMEDELTA_APPROX_REPLAY_ID:
        return _pytest_timedelta_approx_prompt_spec(
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
        f"# {_prompt_spec_report_title(specs)}",
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


def _prompt_spec_report_title(specs: Sequence[Mapping[str, object]]) -> str:
    kinds = {str(spec.get("prompt_spec_kind")) for spec in specs}
    if kinds == {"click_default_map_multi_value_parameter"}:
        return "DATA-009 Click Default Map Prompt Spec"
    if kinds == {"requests_prepare_body_getattr_stream"}:
        return "DATA-011 Requests Prepare Body Prompt Spec"
    if kinds == {"click_semver_non_string_default_help"}:
        return "DATA-013 Click Semver Default Prompt Spec"
    if kinds == {"pytest_strict_addopts_config"}:
        return "DATA-021 Pytest Strict Addopts Prompt Spec"
    return "Issue/PR Prompt Spec Report"


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


def _requests_prepare_body_prompt_spec(
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
    focused_validation_command = (
        ".venv/bin/python -m pytest tests/test_requests.py -q "
        "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
    )
    field_provenance = {
        "minimal_reproduction": [
            "github_pr_7433_diff",
            "know_005_requests_getattr_file_wrapper_behavior",
        ],
        "observed_behavior": [
            "data_011_repo_before_prepare_body_probe",
            "know_005_requests_prepare_body_stream_detection",
        ],
        "expected_behavior": [
            "github_pr_7433_diff",
            "know_005_requests_redirect_rewind_body_semantics",
        ],
        "affected_api_symbol": [
            "github_pr_7433_diff",
            "know_005_requests_prepare_body_stream_detection",
        ],
        "input_shape": ["github_pr_7433_diff"],
        "acceptance_test_shape": [
            "github_pr_7433_diff",
            "data_008_focused_validation_recipe",
        ],
        "getattr_file_wrapper_behavior": [
            "github_pr_7433_diff",
            "know_005_requests_getattr_file_wrapper_behavior",
        ],
        "stream_detection_semantics": [
            "github_pr_7433_diff",
            "know_005_requests_prepare_body_stream_detection",
        ],
        "redirect_rewind_behavior": [
            "know_005_requests_redirect_rewind_body_semantics",
            "data_008_focused_validation_recipe",
        ],
    }
    normalized_fields = {
        "minimal_reproduction": {
            "kind": "requests_post_redirect_attr_proxy_stream",
            "request": {
                "method": "POST",
                "url_shape": "httpbin('redirect-to?url=/post&status_code=307')",
                "data_argument": "AttrProxy()",
            },
            "local_wrapper": {
                "class_name": "AttrProxy",
                "backing_store": "io.BytesIO(b'data')",
                "direct_methods": ["__init__", "__getattr__"],
                "delegation": "__getattr__ returns attributes from the backing BytesIO",
                "class_does_not_define": ["__iter__", "read", "tell", "seek"],
            },
            "assertion": {
                "response_accessor": "r.json()['data']",
                "expected_value": "data",
            },
        },
        "observed_behavior": {
            "repo_before_ref": "0b401c76b6e80a4eecf3c690085b2553f6e261ca",
            "failure_mode": "attribute_proxy_body_not_marked_rewindable",
            "prepare_body_probe": {
                "body_type_after_prepare": "AttrProxy",
                "content_length": "4",
                "body_position_before_fix": None,
                "body_position_after_accepted_fix": 0,
            },
            "stream_detection_gap": (
                "The repo-before predicate uses isinstance(data, Iterable), so "
                "an object whose __iter__ is exposed only through __getattr__ is "
                "not treated as the stream branch that records _body_position."
            ),
        },
        "expected_behavior": {
            "behavior": "treat_getattr_iter_file_wrapper_as_stream",
            "redirect_semantics": (
                "A 307 redirect should resend the original streamed bytes after "
                "Requests rewinds the prepared body to the recorded position."
            ),
            "body_position": "record integer tell() position before redirect-prone sends",
            "preserve_exclusions": [
                "str",
                "bytes",
                "list",
                "tuple",
                "Mapping",
            ],
        },
        "affected_api_symbol": {
            "public_surface": "requests.PreparedRequest.prepare_body",
            "implementation_symbol": "requests.models.PreparedRequest.prepare_body",
            "redirect_surface": "requests.sessions.SessionRedirectMixin.resolve_redirects",
            "rewind_helper": "requests.utils.rewind_body",
            "changed_file": "src/requests/models.py",
            "changed_test_file": "tests/test_requests.py",
        },
        "input_shape": {
            "source": "requests.post(data=...)",
            "value_kind": "attribute_proxy_file_wrapper",
            "excluded_kinds": ["str", "bytes", "list", "tuple", "Mapping"],
            "required_attributes_via_getattr": ["__iter__", "tell", "seek", "read"],
            "example_backing_object": "io.BytesIO",
        },
        "acceptance_test_shape": {
            "test_file": "tests/test_requests.py",
            "test_class": "TestRequests",
            "test_name": "test_getattr_proxy_stream_follows_redirect",
            "fixture_arguments": ["httpbin"],
            "cases": [
                "local AttrProxy wraps io.BytesIO(b'data')",
                "AttrProxy delegates methods through __getattr__",
                "POST goes through httpbin 307 redirect to /post",
                "response JSON data echoes the original uploaded bytes",
            ],
            "validation_command": focused_validation_command,
            "setup_command": (
                "python -m venv .venv && .venv/bin/python -m pip install -q "
                "--upgrade pip setuptools wheel && .venv/bin/python -m pip "
                "install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme"
            ),
        },
        "getattr_file_wrapper_behavior": {
            "wrapper": "AttrProxy",
            "delegated_to": "io.BytesIO",
            "delegation_method": "__getattr__",
            "direct_iter_method_on_class": False,
            "hasattr_wrapper_dunder_iter": True,
            "candidate_constraint": (
                "Stream detection must consider attribute-proxied __iter__ "
                "without classifying ordinary str, bytes, list, tuple, or "
                "Mapping inputs as streamed bodies."
            ),
        },
        "stream_detection_semantics": {
            "repo_before_condition": (
                "isinstance(data, Iterable) and not isinstance(data, "
                "(str, bytes, list, tuple, Mapping))"
            ),
            "accepted_condition_shape": (
                "(isinstance(data, Iterable) or hasattr(data, '__iter__')) "
                "and not isinstance(data, (str, bytes, list, tuple, Mapping))"
            ),
            "stream_branch_effects": [
                "body is the original data object",
                "length is computed with super_len(data)",
                "self._body_position records body.tell() when available",
                "Content-Length is set when length is known",
                "Transfer-Encoding is set to chunked when length is unknown",
            ],
        },
        "redirect_rewind_behavior": {
            "redirect_status": 307,
            "rewind_trigger": (
                "resolve_redirects treats a prepared request as rewindable when "
                "_body_position is not None and Content-Length or "
                "Transfer-Encoding is present."
            ),
            "rewind_helper": "requests.utils.rewind_body",
            "rewind_action": "seek prepared_request.body to _body_position",
            "error_behavior": "raise UnrewindableBodyError when seek/tell state is unusable",
            "issue_specific_effect": (
                "Recording _body_position for the AttrProxy stream lets the "
                "redirect resend b'data' instead of losing the request body."
            ),
        },
    }
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": str(record.get("id")),
        "repo": str(record.get("repo")),
        "prompt_spec_kind": "requests_prepare_body_getattr_stream",
        "status": "normalized",
        "candidate_code_edits_attempted": False,
        "required_prompt_fields": list(REQUESTS_PREPARE_BODY_REQUIRED_FIELDS),
        "missing_prompt_fields": [],
        "required_prompt_fields_complete": True,
        "source_text_blockers": [],
        "source_text_gaps": [
            {
                "source": "github_issue_7432_body",
                "availability": "not_checked_in",
                "impact": (
                    "Exact issue body text is unavailable locally; fields were "
                    "normalized from compact manifest metadata, accepted PR diff, "
                    "DATA-008 validation evidence, and KNOW-005 local knowledge."
                ),
            },
            {
                "source": "github_pr_7433_conversation",
                "availability": "not_checked_in",
                "impact": (
                    "PR discussion text is unavailable locally; no required "
                    "prompt/spec field depends on unretrieved conversation text."
                ),
            },
        ],
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
                    "id": "github_issue_7432_compact_manifest",
                    "kind": "github_issue_metadata",
                    "url": issue_url,
                    "fields": [
                        "minimal_reproduction",
                        "observed_behavior",
                        "affected_api_symbol",
                    ],
                },
                {
                    "id": "github_pr_7433_diff",
                    "kind": "github_pull_request_diff",
                    "url": diff_url,
                    "merge_commit_sha": accepted_change.get("merge_commit_sha"),
                    "fields": [
                        "minimal_reproduction",
                        "expected_behavior",
                        "affected_api_symbol",
                        "input_shape",
                        "acceptance_test_shape",
                        "getattr_file_wrapper_behavior",
                        "stream_detection_semantics",
                    ],
                },
                {
                    "id": "data_008_focused_validation_recipe",
                    "kind": "local_validation_report",
                    "url": "docs/DATA_008_REQUESTS_VALIDATION_RECIPE_2026-05-18.md",
                    "fields": ["acceptance_test_shape", "redirect_rewind_behavior"],
                },
                {
                    "id": "know_005_requests_local_knowledge",
                    "kind": "local_knowledge_jsonl",
                    "url": "/tmp/j3-know-005-requests-records.jsonl",
                    "fields": [
                        "observed_behavior",
                        "getattr_file_wrapper_behavior",
                        "stream_detection_semantics",
                        "redirect_rewind_behavior",
                    ],
                },
                {
                    "id": "github_pr_7433_conversation",
                    "kind": "github_pull_request",
                    "url": pr_url,
                    "fields": [],
                    "availability": "not_checked_in_not_required",
                },
            ],
        ),
    }


def _click_semver_default_prompt_spec(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path | None,
    record: Mapping[str, object],
) -> dict[str, object]:
    prompt_source = _mapping(record.get("prompt_source"))
    accepted_change = _mapping(record.get("accepted_change"))
    validation = _mapping(record.get("validation"))
    issue_url = str(prompt_source.get("issue_url") or "")
    pr_url = str(prompt_source.get("pull_request_url") or "")
    diff_url = str(accepted_change.get("diff_url") or "")
    validation_command = str(validation.get("command") or "pytest tests/test_options.py -q")
    knowledge_path = "/tmp/j3-know-004-click-records.jsonl"
    field_provenance = {
        "minimal_reproduction": [
            "github_issue_3298",
            "know_004_third_party_semver_version_reproduction",
        ],
        "observed_behavior": [
            "github_issue_3298",
            "know_004_click_non_string_default_handling",
        ],
        "expected_behavior": [
            "github_pr_3299_conversation",
            "github_pr_3299_diff",
            "know_004_click_empty_string_check_semantics",
        ],
        "affected_api_symbol": [
            "github_pr_3299_diff",
            "know_004_repo_changed_file_context",
        ],
        "input_shape": [
            "github_issue_3298",
            "know_004_click_parameter_default_handling",
        ],
        "acceptance_test_shape": [
            "github_pr_3299_diff",
            "know_004_repo_test_pattern",
            "know_004_focused_validation_recipe",
        ],
        "non_string_default_behavior": [
            "github_issue_3298",
            "know_004_click_non_string_default_handling",
        ],
        "type_conversion_semantics": [
            "github_issue_3298",
            "know_004_click_type_conversion_semantics",
        ],
        "empty_string_check_scope": [
            "github_pr_3299_diff",
            "know_004_click_empty_string_check_semantics",
        ],
        "third_party_semver_version_reproduction_context": [
            "github_issue_3298",
            "github_pr_3299_diff",
            "know_004_third_party_semver_version_reproduction",
        ],
    }
    normalized_fields = {
        "minimal_reproduction": {
            "kind": "click_help_rendering_semver_default",
            "package_context": {
                "python_version": "3.12",
                "click_version": "8.3.1",
                "semver_version": "3.0.4",
            },
            "command_shape": {
                "decorator": "click.option",
                "option_decls": ["--version"],
                "type": "SemverType()",
                "default": "semver.Version(1, 0, 0)",
                "show_default": True,
            },
            "param_type_shape": {
                "class_name": "SemverType",
                "base": "click.ParamType",
                "convert_accepts": ["str", "semver.Version"],
                "convert_returns": "semver.Version",
                "string_conversion": "Version.parse(value)",
                "already_converted_behavior": "return value unchanged",
            },
            "trigger": {
                "operation": "render_help_text",
                "representative_call": "runner.invoke(cli, ['--help'])",
                "internal_call": "click.Option.get_help_record(ctx)",
            },
        },
        "observed_behavior": {
            "repo_before_ref": "04ef3a6f473deb2499721a8d11f92a7d2c0912f2",
            "failure_mode": "non_string_default_compared_to_empty_string",
            "exception_type": "ValueError",
            "exception_message": " is not valid SemVer string",
            "failing_expression": "default_value == ''",
            "call_path": [
                "click.Option.get_help_record",
                "click.Option.get_help_extra",
                "semver.Version.__eq__",
                "semver.Version.compare",
                "semver.Version.parse",
            ],
        },
        "expected_behavior": {
            "behavior": "render_non_string_default_without_string_equality_probe",
            "help_default_output": "[default: 1.0.0]",
            "accepted_fix_shape": (
                "Only run the empty-string display branch when the default "
                "value is a string; otherwise fall back to str(default_value)."
            ),
            "preserve_empty_string_display": (
                "A real empty string default remains displayed as "
                "`[default: \"\"]`."
            ),
            "candidate_constraint": (
                "Do not disable type conversion or remove empty-string display "
                "semantics while avoiding equality against arbitrary objects."
            ),
        },
        "affected_api_symbol": {
            "public_surface": "click.option(..., default=..., show_default=True)",
            "parameter_surface": "click.Option",
            "implementation_symbol": "click.core.Option.get_help_extra",
            "related_symbols": [
                "click.core.Option.get_help_record",
                "click.core.Option.get_default",
                "click.core.Parameter.type_cast_value",
            ],
            "changed_file": "src/click/core.py",
            "changed_test_file": "tests/test_options.py",
        },
        "input_shape": {
            "source": "click.Option.default",
            "value_kind": "non_string_object_with_string_comparison_side_effect",
            "third_party_example": "semver.Version(1, 0, 0)",
            "local_regression_double": "_StrictEq()",
            "option_kwargs": {
                "show_default": True,
                "type": "custom click.ParamType returning the object unchanged",
            },
            "excluded_from_empty_string_branch": ["semver.Version", "_StrictEq"],
            "still_in_empty_string_branch": [""],
        },
        "acceptance_test_shape": {
            "test_file": "tests/test_options.py",
            "test_name": "test_show_default_with_empty_string",
            "helper_class": "_StrictEq",
            "parametrize_cases": [
                {
                    "id": "empty-string",
                    "default": "",
                    "expected": "[default: \"\"]",
                },
                {
                    "id": "non-string-comparable-object",
                    "default": "_StrictEq()",
                    "expected": "[default: strict]",
                },
            ],
            "validation_command": validation_command,
            "setup_command": "python -m pip install -e . pytest",
            "third_party_dependency_policy": (
                "The accepted regression test does not require semver; it uses "
                "a local strict-equality object that raises on string operands."
            ),
        },
        "non_string_default_behavior": {
            "source_method": "click.core.Option.get_help_extra",
            "default_lookup": "self.get_default(ctx, call=False)",
            "before_fix_risk": (
                "A default object can execute arbitrary __eq__ behavior when "
                "Click compares it to the empty string."
            ),
            "after_fix_behavior": (
                "Non-string defaults skip the empty-string branch and render "
                "through str(default_value) unless an earlier branch handles "
                "them specially."
            ),
            "known_special_cases_preserved": [
                "UNSET or suppressed show_default",
                "tuple and list display",
                "Enum value display",
                "dynamic default function display",
                "single bool flag with false default",
            ],
        },
        "type_conversion_semantics": {
            "conversion_layer": "click.core.Parameter.type_cast_value",
            "processing_layer": "click.core.Parameter.process_value",
            "help_rendering_constraint": (
                "Help default rendering must inspect and stringify defaults "
                "without forcing conversion changes for command execution."
            ),
            "semver_param_type": {
                "already_version": "convert returns the Version instance unchanged",
                "string_input": "convert parses strings with Version.parse",
                "failure_surface": "type conversion failure should remain a BadParameter path",
            },
            "candidate_constraint": (
                "The fix belongs in help text default formatting, not in "
                "generic type conversion or missing-value detection."
            ),
        },
        "empty_string_check_scope": {
            "repo_before_condition": "default_value == ''",
            "accepted_condition": "isinstance(default_value, str) and default_value == ''",
            "scope": "click.core.Option.get_help_extra default_string formatting",
            "preserved_behavior": "empty string defaults render as quoted empty strings",
            "out_of_scope": [
                "non-string default object equality",
                "command invocation value conversion",
                "environment variable parsing",
                "multiple or nargs missing-value detection",
            ],
        },
        "third_party_semver_version_reproduction_context": {
            "package": "semver",
            "class": "semver.Version",
            "reported_version": "3.0.4",
            "reported_default": "Version(1, 0, 0)",
            "comparison_behavior": (
                "Version.__eq__ accepts string operands by parsing them; an "
                "empty string raises ValueError because it is not valid SemVer."
            ),
            "accepted_test_substitute": {
                "class_name": "_StrictEq",
                "eq_behavior": "raise ValueError when other is a str",
                "str_behavior": "return 'strict'",
                "reason": (
                    "Captures Click's invalid equality probe without adding a "
                    "semver dependency to the Click test suite."
                ),
            },
        },
    }
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": str(record.get("id")),
        "repo": str(record.get("repo")),
        "prompt_spec_kind": "click_semver_non_string_default_help",
        "status": "normalized",
        "candidate_code_edits_attempted": False,
        "required_prompt_fields": list(CLICK_SEMVER_DEFAULT_REQUIRED_FIELDS),
        "missing_prompt_fields": [],
        "required_prompt_fields_complete": True,
        "source_text_blockers": [],
        "source_text_gaps": [],
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
                    "id": "github_issue_3298",
                    "kind": "github_issue",
                    "url": issue_url,
                    "fields": [
                        "minimal_reproduction",
                        "observed_behavior",
                        "input_shape",
                        "non_string_default_behavior",
                        "type_conversion_semantics",
                        "third_party_semver_version_reproduction_context",
                    ],
                },
                {
                    "id": "github_pr_3299_conversation",
                    "kind": "github_pull_request",
                    "url": pr_url,
                    "fields": ["expected_behavior", "empty_string_check_scope"],
                },
                {
                    "id": "github_pr_3299_diff",
                    "kind": "github_pull_request_diff",
                    "url": diff_url,
                    "merge_commit_sha": accepted_change.get("merge_commit_sha"),
                    "fields": [
                        "expected_behavior",
                        "affected_api_symbol",
                        "acceptance_test_shape",
                        "empty_string_check_scope",
                        "third_party_semver_version_reproduction_context",
                    ],
                },
                {
                    "id": "know_004_click_local_knowledge",
                    "kind": "local_knowledge_jsonl",
                    "url": knowledge_path,
                    "fields": [
                        "affected_api_symbol",
                        "acceptance_test_shape",
                        "non_string_default_behavior",
                        "type_conversion_semantics",
                        "empty_string_check_scope",
                        "third_party_semver_version_reproduction_context",
                    ],
                    "record_ids": [
                        "1904a6fa15665899650dbaec21829fdac4fdc493daddef9f118928262649d73a",
                        "637634d1dee21f7cb4dbc244ebe384a4d8c75fb8070735345fac822cdb16ee7a",
                        "9ec7175c0affa313906dcae73c5304d2dd6bfe1853cfdc05aa4273ebf0948147",
                        "311aef2b41343232a5491c610f636efdf966891f32767d5e3a574ddc64ded546",
                        "0dde986e749141c71f592950b9d7518adcb72b4447c488329df813b418bbdd99",
                        "2882ec4082f4ea978c942600690cf8b99b95bcc92c921293ed6e637f441e67a0",
                        "f96ac571dae6b2a53647803ebd07d034e91895a038ab1bb19ba6d528d97f7587",
                        "29bde1f5e4eed1864b02359519d15579d45e2e5c0d697aece2772004f2eed2f1",
                    ],
                },
            ],
        ),
    }


def _pytest_strict_addopts_prompt_spec(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path | None,
    record: Mapping[str, object],
) -> dict[str, object]:
    prompt_source = _mapping(record.get("prompt_source"))
    accepted_change = _mapping(record.get("accepted_change"))
    validation = _mapping(record.get("validation"))
    issue_url = str(prompt_source.get("issue_url") or "")
    pr_url = str(prompt_source.get("pull_request_url") or "")
    diff_url = str(accepted_change.get("diff_url") or "")
    validation_command = str(
        validation.get("command") or "pytest testing/test_config.py testing/test_mark.py -q"
    )
    knowledge_path = "/tmp/j3-data-021-pytest-14442-knowledge.jsonl"
    field_provenance = {
        "minimal_reproduction": [
            "github_issue_14442_compact_manifest",
            "github_pr_14443_diff",
        ],
        "observed_behavior": [
            "github_issue_14442_compact_manifest",
            "data_018_pytest_preflight",
        ],
        "expected_behavior": [
            "github_pr_14443_diff",
            "know_data_021_pytest_strict_addopts_behavior",
        ],
        "affected_api_symbol": [
            "github_pr_14443_diff",
            "know_data_021_repo_changed_file_context",
        ],
        "input_shape": [
            "github_issue_14442_compact_manifest",
            "github_pr_14443_diff",
        ],
        "acceptance_test_shape": [
            "github_pr_14443_diff",
            "data_018_pytest_preflight",
            "know_data_021_pytest_repo_test_patterns",
        ],
        "strict_addopts_behavior": [
            "github_pr_14443_diff",
            "know_data_021_pytest_strict_addopts_behavior",
        ],
        "strict_markers_config_semantics": [
            "github_pr_14443_diff",
            "know_data_021_pytest_strict_markers_config_semantics",
        ],
    }
    normalized_fields = {
        "minimal_reproduction": {
            "kind": "pytest_strict_options_from_addopts",
            "config_file": {
                "section": "pytest",
                "option": "addopts",
                "values": ["--strict-markers", "--strict-config"],
            },
            "strict_config_case": {
                "ini_body": [
                    "[pytest]",
                    "unknown_option = 1",
                    "addopts = --strict-config",
                ],
                "operation": "pytester.runpytest()",
            },
            "strict_markers_case": {
                "ini_body": ["[pytest]", "addopts = --strict-markers"],
                "test_body_shape": "@pytest.mark.unregisteredmark on a test function",
                "operation": "pytester.runpytest()",
            },
        },
        "observed_behavior": {
            "repo_before_ref": "8f81c76744daf72d4f77cfc8423f4bdc60733d78",
            "failure_mode": "strict_options_from_addopts_silently_ignored",
            "strict_config_effect_before_fix": (
                "Unknown configuration keys only warn instead of raising UsageError "
                "when --strict-config is supplied via addopts."
            ),
            "strict_markers_effect_before_fix": (
                "Unregistered marks are not rejected when --strict-markers is "
                "supplied via addopts."
            ),
            "baseline_validation": {
                "source": "DATA-018",
                "command": validation_command,
                "repo_before_result": "353 passed, 2 xfailed in 3.29s",
            },
        },
        "expected_behavior": {
            "behavior": "apply_strict_options_declared_in_addopts",
            "strict_config_result": (
                "Unknown config option fails with pytest.ExitCode.USAGE_ERROR "
                "when addopts contains --strict-config."
            ),
            "strict_markers_result": (
                "Unregistered marker collection fails when addopts contains "
                "--strict-markers."
            ),
            "accepted_fix_shape": (
                "After parsing command-line plus addopts, re-apply override-ini "
                "values into Config._inicfg and clear Config._inicache once."
            ),
            "candidate_constraint": (
                "Do not attempt candidate edits from this evidence task; a future "
                "candidate must preserve existing strict_config, strict, "
                "strict_markers, and strict option behavior."
            ),
        },
        "affected_api_symbol": {
            "public_surface": "pytest configuration addopts",
            "option_surfaces": ["--strict-markers", "--strict-config", "-o/--override-ini"],
            "ini_surfaces": ["addopts", "strict_markers", "strict_config", "strict"],
            "implementation_symbol": "_pytest.config.Config.parse",
            "related_symbols": [
                "_pytest.config.Config._warn_or_fail_if_strict",
                "_pytest.config.findpaths.parse_override_ini",
                "_pytest.config.Parser.parse_known_args",
            ],
            "changed_file": "src/_pytest/config/__init__.py",
            "changed_test_files": ["testing/test_config.py", "testing/test_mark.py"],
            "auxiliary_changed_files": ["AUTHORS", "changelog/14442.bugfix.rst"],
        },
        "input_shape": {
            "source": "pytest ini addopts",
            "value_kind": "args list from configuration",
            "examples": [
                {"addopts": "--strict-config", "bad_ini_key": "unknown_option"},
                {"addopts": "--strict-markers", "bad_marker": "unregisteredmark"},
            ],
            "parse_order_constraint": (
                "addopts is appended before the known-args namespace used by strict "
                "checks is finalized."
            ),
            "override_ini_interaction": (
                "Strict options can arrive through OverrideIniAction-compatible "
                "arguments, so parsed override ini values must update _inicfg before "
                "strict config checks read cached ini values."
            ),
        },
        "acceptance_test_shape": {
            "test_files": ["testing/test_config.py", "testing/test_mark.py"],
            "test_cases": [
                {
                    "test_file": "testing/test_config.py",
                    "test_name": "test_strict_config_ini_option",
                    "new_case": "addopts = --strict-config",
                    "assertion": "stderr contains Unknown config option and ret is USAGE_ERROR",
                },
                {
                    "test_file": "testing/test_mark.py",
                    "test_name": "test_strict_prohibits_unregistered_markers",
                    "new_case": "addopts = --strict-markers",
                    "assertion": (
                        "stdout reports unregisteredmark missing from markers "
                        "configuration and ret is nonzero"
                    ),
                },
            ],
            "validation_command": validation_command,
            "setup_command": "python -m pip install -e . pytest",
        },
        "strict_addopts_behavior": {
            "config_option": "addopts",
            "parse_method": "_pytest.config.Config.parse",
            "accepted_sequence": [
                "validate PYTEST_ADDOPTS and prepend to args",
                "determine setup and load ini config",
                "register addopts and core ini options",
                "validate ini addopts and prepend to args",
                "parse known args into known_args_namespace",
                "update _inicfg from parsed override_ini and clear _inicache",
            ],
            "fix_scope": "one-level addopts override update, not recursive addopts expansion",
        },
        "strict_markers_config_semantics": {
            "strict_config": {
                "ini_options": ["strict_config", "strict"],
                "effect": "unknown config keys become UsageError instead of warnings",
                "test_file": "testing/test_config.py",
            },
            "strict_markers": {
                "cli_options": ["--strict-markers", "--strict"],
                "ini_options": ["strict_markers", "strict"],
                "effect": "unregistered markers are prohibited",
                "test_file": "testing/test_mark.py",
            },
            "candidate_constraint": (
                "Preserve legacy strict aliases while making addopts-supplied "
                "strict options observable to the same code paths."
            ),
        },
    }
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": str(record.get("id")),
        "repo": str(record.get("repo")),
        "prompt_spec_kind": "pytest_strict_addopts_config",
        "status": "normalized",
        "candidate_code_edits_attempted": False,
        "required_prompt_fields": list(PYTEST_STRICT_ADDOPTS_REQUIRED_FIELDS),
        "missing_prompt_fields": [],
        "required_prompt_fields_complete": True,
        "source_text_blockers": [],
        "source_text_gaps": [
            {
                "source": "github_issue_14442_body",
                "availability": "not_checked_in",
                "impact": (
                    "Exact issue body text is unavailable locally; fields were "
                    "normalized from compact manifest metadata, accepted PR diff, "
                    "DATA-018 validation evidence, and DATA-021 local knowledge."
                ),
            },
            {
                "source": "github_pr_14443_conversation",
                "availability": "not_checked_in",
                "impact": (
                    "PR discussion text is unavailable locally; no required "
                    "prompt/spec field depends on unretrieved conversation text."
                ),
            },
        ],
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
                    "id": "github_issue_14442_compact_manifest",
                    "kind": "github_issue_metadata",
                    "url": issue_url,
                    "fields": [
                        "minimal_reproduction",
                        "observed_behavior",
                        "input_shape",
                    ],
                },
                {
                    "id": "github_pr_14443_diff",
                    "kind": "github_pull_request_diff",
                    "url": diff_url,
                    "merge_commit_sha": accepted_change.get("merge_commit_sha"),
                    "fields": [
                        "minimal_reproduction",
                        "expected_behavior",
                        "affected_api_symbol",
                        "input_shape",
                        "acceptance_test_shape",
                        "strict_addopts_behavior",
                        "strict_markers_config_semantics",
                    ],
                },
                {
                    "id": "data_018_pytest_preflight",
                    "kind": "local_validation_report",
                    "url": "docs/DATA_018_PYTEST_ISSUE_PR_PREFLIGHT_2026-05-18.md",
                    "fields": ["observed_behavior", "acceptance_test_shape"],
                },
                {
                    "id": "know_data_021_pytest_local_knowledge",
                    "kind": "local_knowledge_jsonl",
                    "url": knowledge_path,
                    "fields": [
                        "expected_behavior",
                        "affected_api_symbol",
                        "acceptance_test_shape",
                        "strict_addopts_behavior",
                        "strict_markers_config_semantics",
                    ],
                },
                {
                    "id": "github_pr_14443_conversation",
                    "kind": "github_pull_request",
                    "url": pr_url,
                    "fields": [],
                    "availability": "not_checked_in_not_required",
                },
            ],
        ),
    }


def _pytest_timedelta_approx_prompt_spec(
    *,
    manifest: Mapping[str, object],
    manifest_path: Path | None,
    record: Mapping[str, object],
) -> dict[str, object]:
    prompt_source = _mapping(record.get("prompt_source"))
    accepted_change = _mapping(record.get("accepted_change"))
    validation = _mapping(record.get("validation"))
    issue_url = str(prompt_source.get("issue_url") or "")
    pr_url = str(prompt_source.get("pull_request_url") or "")
    diff_url = str(accepted_change.get("diff_url") or "")
    validation_command = str(validation.get("command") or "pytest testing/python/approx.py -q")
    knowledge_path = "/tmp/j3-data-026-pytest-14462-knowledge.jsonl"
    field_provenance = {
        "minimal_reproduction": [
            "github_issue_14462_compact_manifest",
            "github_pr_14466_diff",
        ],
        "observed_behavior": [
            "github_issue_14462_compact_manifest",
            "data_018_pytest_preflight",
            "know_data_026_pytest_approx_timedelta_tolerance_semantics",
        ],
        "expected_behavior": [
            "github_pr_14466_diff",
            "know_data_026_pytest_approx_timedelta_tolerance_semantics",
        ],
        "affected_api_symbol": [
            "github_pr_14466_diff",
            "know_data_026_repo_changed_file_context",
        ],
        "input_shape": [
            "github_issue_14462_compact_manifest",
            "github_pr_14466_diff",
        ],
        "acceptance_test_shape": [
            "github_pr_14466_diff",
            "data_018_pytest_preflight",
            "know_data_026_pytest_repo_test_patterns",
        ],
        "relative_tolerance_semantics": [
            "github_pr_14466_diff",
            "know_data_026_pytest_approx_timedelta_tolerance_semantics",
        ],
        "datetime_timedelta_comparison_behavior": [
            "github_pr_14466_diff",
            "know_data_026_pytest_datetime_timedelta_comparison_behavior",
        ],
    }
    normalized_fields = {
        "minimal_reproduction": {
            "kind": "pytest_approx_timedelta_relative_tolerance",
            "expected_value": "timedelta(seconds=100)",
            "actual_values": [
                "timedelta(seconds=100.5)",
                "timedelta(seconds=102)",
                "timedelta(seconds=111)",
            ],
            "operation": "actual == pytest.approx(expected, rel=0.01)",
            "relative_tolerance": 0.01,
            "expected_effective_tolerance": "timedelta(seconds=1)",
        },
        "observed_behavior": {
            "repo_before_ref": "fbab7c5dfe63a22f545207e8dc163ed61ad51d98",
            "failure_mode": "timedelta_rel_parameter_treated_as_timedelta_absolute_tolerance",
            "pre_fix_type_check": (
                "ApproxTimedelta rejects rel=0.01 because rel must be a timedelta."
            ),
            "pre_fix_tolerance_calculation": (
                "When rel is a timedelta, ApproxTimedelta takes max(abs, rel) and "
                "stores it as an absolute tolerance instead of scaling by expected."
            ),
            "baseline_validation": {
                "source": "DATA-018",
                "command": validation_command,
                "repo_before_result": "102 passed, 18 skipped in 0.15s",
            },
        },
        "expected_behavior": {
            "behavior": "compute_timedelta_relative_tolerance_from_expected_value",
            "relative_tolerance_result": (
                "For timedelta expected values, rel is a numeric fraction and "
                "rel_tolerance = rel * abs(expected)."
            ),
            "absolute_tolerance_result": (
                "abs remains a datetime.timedelta and is combined with relative "
                "tolerance by taking the larger effective timedelta."
            ),
            "datetime_result": (
                "datetime expected values continue to reject rel and require "
                "abs=timedelta(...)."
            ),
            "candidate_constraint": (
                "Do not attempt candidate edits from DATA-026; future source/test "
                "candidate scope is only src/_pytest/python_api.py and "
                "testing/python/approx.py."
            ),
        },
        "affected_api_symbol": {
            "public_surface": "pytest.approx",
            "implementation_symbol": "_pytest.python_api.ApproxTimedelta",
            "related_symbols": [
                "_pytest.python_api.ApproxBase._approx_scalar",
                "_pytest.python_api.ApproxScalar.tolerance",
                "_pytest.python_api.approx",
            ],
            "changed_file": "src/_pytest/python_api.py",
            "changed_test_files": ["testing/python/approx.py"],
            "auxiliary_changed_files": [],
        },
        "input_shape": {
            "expected_types": ["datetime.timedelta", "datetime.datetime"],
            "actual_types": ["datetime.timedelta", "datetime.datetime"],
            "timedelta_rel_type_after_fix": "float_or_int_fraction",
            "timedelta_abs_type": "datetime.timedelta",
            "datetime_rel_policy": "unsupported",
            "invalid_values": [
                {"argument": "rel", "value": "timedelta(seconds=1)", "result": "TypeError"},
                {"argument": "rel", "value": "-0.1", "result": "ValueError"},
                {"argument": "rel", "value": "float('nan')", "result": "ValueError"},
                {"argument": "abs", "value": "timedelta(seconds=-1)", "result": "ValueError"},
            ],
        },
        "acceptance_test_shape": {
            "test_files": ["testing/python/approx.py"],
            "test_class": "TestApproxDatetime",
            "test_cases": [
                {
                    "test_name": "test_timedelta_rel_within_tolerance",
                    "assertion": "100s actual is equal to approx(100.5s, rel=0.01)",
                },
                {
                    "test_name": "test_timedelta_rel_outside_tolerance",
                    "assertion": "102s actual is not equal to approx(100s, rel=0.01)",
                },
                {
                    "test_name": "test_timedelta_rel_scales_with_expected",
                    "assertion": "same rel fraction creates larger tolerance for larger expected timedelta",
                },
                {
                    "test_name": "test_timedelta_rel_must_be_number",
                    "assertion": "rel=timedelta(...) raises TypeError",
                },
                {
                    "test_name": "test_timedelta_in_sequence / test_timedelta_in_mapping",
                    "assertion": "nested sequence and mapping approx values use ApproxTimedelta",
                },
            ],
            "validation_command": validation_command,
            "setup_command": "python -m pip install -e . pytest",
        },
        "relative_tolerance_semantics": {
            "timedelta_rel_argument_type": "int_or_float",
            "effective_tolerance_formula": "max(abs_tolerance, rel * abs(expected))",
            "reference_value": "expected",
            "zero_rel_behavior": "exact match required unless abs supplies a positive tolerance",
            "negative_rel_behavior": "ValueError",
            "nan_rel_behavior": "ValueError",
            "sequence_mapping_requirement": (
                "ApproxBase._approx_scalar must dispatch datetime/timedelta elements "
                "to ApproxTimedelta so containers preserve the same semantics."
            ),
        },
        "datetime_timedelta_comparison_behavior": {
            "datetime": {
                "relative_tolerance": "unsupported",
                "absolute_tolerance": "required datetime.timedelta",
                "comparison": "abs(expected - actual) <= abs_tolerance",
            },
            "timedelta": {
                "relative_tolerance": "numeric fraction of abs(expected)",
                "absolute_tolerance": "optional datetime.timedelta",
                "comparison": "abs(expected - actual) <= effective_tolerance",
            },
            "unsupported_options": ["nan_ok"],
            "incompatible_actual_result": "False rather than propagated TypeError",
        },
    }
    return {
        "schema_version": ISSUE_PR_PROMPT_SPEC_SCHEMA_VERSION,
        "record_kind": "issue_pr_prompt_spec",
        "replay_id": str(record.get("id")),
        "repo": str(record.get("repo")),
        "prompt_spec_kind": "pytest_timedelta_approx_relative_tolerance",
        "status": "normalized",
        "candidate_code_edits_attempted": False,
        "required_prompt_fields": list(PYTEST_TIMEDELTA_APPROX_REQUIRED_FIELDS),
        "missing_prompt_fields": [],
        "required_prompt_fields_complete": True,
        "source_text_blockers": [],
        "source_text_gaps": [
            {
                "source": "github_issue_14462_body",
                "availability": "not_checked_in",
                "impact": (
                    "Exact issue body text is unavailable locally; fields were "
                    "normalized from compact manifest metadata, accepted PR diff, "
                    "DATA-018 validation evidence, and DATA-026 local knowledge."
                ),
            },
            {
                "source": "github_pr_14466_conversation",
                "availability": "not_checked_in",
                "impact": (
                    "PR discussion text is unavailable locally; no required "
                    "prompt/spec field depends on unretrieved conversation text."
                ),
            },
        ],
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
                    "id": "github_issue_14462_compact_manifest",
                    "kind": "github_issue_metadata",
                    "url": issue_url,
                    "fields": [
                        "minimal_reproduction",
                        "observed_behavior",
                        "input_shape",
                    ],
                },
                {
                    "id": "github_pr_14466_diff",
                    "kind": "github_pull_request_diff",
                    "url": diff_url,
                    "merge_commit_sha": accepted_change.get("merge_commit_sha"),
                    "fields": [
                        "minimal_reproduction",
                        "expected_behavior",
                        "affected_api_symbol",
                        "input_shape",
                        "acceptance_test_shape",
                        "relative_tolerance_semantics",
                        "datetime_timedelta_comparison_behavior",
                    ],
                },
                {
                    "id": "data_018_pytest_preflight",
                    "kind": "local_validation_report",
                    "url": "docs/DATA_018_PYTEST_ISSUE_PR_PREFLIGHT_2026-05-18.md",
                    "fields": ["observed_behavior", "acceptance_test_shape"],
                },
                {
                    "id": "know_data_026_pytest_local_knowledge",
                    "kind": "local_knowledge_jsonl",
                    "url": knowledge_path,
                    "fields": [
                        "observed_behavior",
                        "expected_behavior",
                        "affected_api_symbol",
                        "acceptance_test_shape",
                        "relative_tolerance_semantics",
                        "datetime_timedelta_comparison_behavior",
                    ],
                },
                {
                    "id": "github_pr_14466_conversation",
                    "kind": "github_pull_request",
                    "url": pr_url,
                    "fields": [],
                    "availability": "not_checked_in_not_required",
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
        test_file = acceptance.get("test_file")
        if test_file:
            lines.append(
                "- Acceptance test shape: "
                f"`{test_file}::{acceptance.get('test_name')}`"
            )
        else:
            lines.append(
                "- Acceptance test files: "
                f"`{_json_inline(acceptance.get('test_files', []))}`"
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
