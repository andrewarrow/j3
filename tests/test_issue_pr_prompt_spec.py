from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_prompt_spec import (
    CLICK_DEFAULT_MAP_REPLAY_ID,
    CLICK_SEMVER_DEFAULT_REPLAY_ID,
    REQUESTS_PREPARE_BODY_REPLAY_ID,
    build_issue_pr_prompt_spec,
    build_issue_pr_prompt_specs,
    load_issue_pr_replay_manifest,
    summarize_issue_pr_prompt_specs,
    write_issue_pr_prompt_spec_report,
    write_issue_pr_prompt_specs_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"


def test_builds_click_default_map_prompt_spec() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    spec = build_issue_pr_prompt_spec(
        manifest,
        CLICK_DEFAULT_MAP_REPLAY_ID,
        manifest_path=MANIFEST_PATH,
    )

    assert spec["schema_version"] == "issue-pr-prompt-spec-v1"
    assert spec["record_kind"] == "issue_pr_prompt_spec"
    assert spec["status"] == "normalized"
    assert spec["candidate_code_edits_attempted"] is False
    assert spec["required_prompt_fields_complete"] is True
    assert spec["missing_prompt_fields"] == []
    assert spec["source_text_blockers"] == []

    fields = spec["normalized_fields"]
    assert fields["minimal_reproduction"]["invocation"] == [
        "hello",
        "--settings",
        "hello",
    ]
    assert fields["observed_behavior"]["error_option"] == "--general-foo / --foo"
    assert (
        fields["expected_behavior"]["behavior"]
        == "split_string_default_map_values_for_multi_value_parameters"
    )
    assert (
        fields["affected_api_symbol"]["implementation_symbol"]
        == "click.core.Option.consume_value"
    )
    assert fields["acceptance_test_shape"]["test_file"] == "tests/test_defaults.py"
    assert (
        fields["default_map_mutation_timing"]["timing"]
        == "during_eager_option_callback_before_dependent_option_defaults"
    )
    assert fields["multi_value_parameter_shape"]["nargs_option"]["nargs"] == 2
    assert fields["string_splitting_semantics"]["splitter"] == (
        "ParamType.split_envvar_value"
    )


def test_click_default_map_prompt_spec_records_provenance() -> None:
    specs = build_issue_pr_prompt_specs(
        manifest_path=MANIFEST_PATH,
        replay_ids=[CLICK_DEFAULT_MAP_REPLAY_ID],
    )
    spec = specs[0]
    provenance = spec["provenance"]

    assert provenance["manifest_schema_version"] == "issue-pr-mini-replay-v0"
    assert provenance["stable_split"]["split"] == "train"
    assert provenance["local_source_availability"] == {
        "compact_manifest_metadata": "available",
        "issue_body": "not_checked_in_manifest_available_at_prompt_source_url",
        "pull_request_body": "not_checked_in_manifest_available_at_prompt_source_url",
        "pull_request_diff": "not_checked_in_manifest_available_at_diff_url",
    }
    normalized_from = provenance["normalized_from"]
    assert [source["id"] for source in normalized_from] == [
        "github_issue_2745",
        "github_pr_3364_conversation",
        "github_pr_3364_diff",
    ]
    assert normalized_from[0]["url"].endswith("/issues/2745")
    assert normalized_from[2]["url"].endswith("/pull/3364.diff")


def test_builds_requests_prepare_body_prompt_spec() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    spec = build_issue_pr_prompt_spec(
        manifest,
        REQUESTS_PREPARE_BODY_REPLAY_ID,
        manifest_path=MANIFEST_PATH,
    )

    assert spec["schema_version"] == "issue-pr-prompt-spec-v1"
    assert spec["record_kind"] == "issue_pr_prompt_spec"
    assert spec["prompt_spec_kind"] == "requests_prepare_body_getattr_stream"
    assert spec["status"] == "normalized"
    assert spec["candidate_code_edits_attempted"] is False
    assert spec["required_prompt_fields_complete"] is True
    assert spec["missing_prompt_fields"] == []
    assert spec["source_text_blockers"] == []

    fields = spec["normalized_fields"]
    assert fields["minimal_reproduction"]["request"] == {
        "method": "POST",
        "url_shape": "httpbin('redirect-to?url=/post&status_code=307')",
        "data_argument": "AttrProxy()",
    }
    assert fields["observed_behavior"]["prepare_body_probe"] == {
        "body_type_after_prepare": "AttrProxy",
        "content_length": "4",
        "body_position_before_fix": None,
        "body_position_after_accepted_fix": 0,
    }
    assert (
        fields["expected_behavior"]["behavior"]
        == "treat_getattr_iter_file_wrapper_as_stream"
    )
    assert (
        fields["affected_api_symbol"]["implementation_symbol"]
        == "requests.models.PreparedRequest.prepare_body"
    )
    assert fields["input_shape"]["value_kind"] == "attribute_proxy_file_wrapper"
    assert (
        fields["acceptance_test_shape"]["test_name"]
        == "test_getattr_proxy_stream_follows_redirect"
    )
    assert fields["getattr_file_wrapper_behavior"]["direct_iter_method_on_class"] is False
    assert fields["getattr_file_wrapper_behavior"]["hasattr_wrapper_dunder_iter"] is True
    assert "hasattr(data, '__iter__')" in fields["stream_detection_semantics"][
        "accepted_condition_shape"
    ]
    assert fields["redirect_rewind_behavior"]["redirect_status"] == 307


def test_requests_prepare_body_prompt_spec_records_provenance_and_source_gaps() -> None:
    specs = build_issue_pr_prompt_specs(
        manifest_path=MANIFEST_PATH,
        replay_ids=[REQUESTS_PREPARE_BODY_REPLAY_ID],
    )
    spec = specs[0]
    provenance = spec["provenance"]

    assert provenance["manifest_schema_version"] == "issue-pr-mini-replay-v0"
    assert provenance["stable_split"]["split"] == "train"
    normalized_from = provenance["normalized_from"]
    assert [source["id"] for source in normalized_from] == [
        "github_issue_7432_compact_manifest",
        "github_pr_7433_diff",
        "data_008_focused_validation_recipe",
        "know_005_requests_local_knowledge",
        "github_pr_7433_conversation",
    ]
    assert normalized_from[1]["merge_commit_sha"] == (
        "6404f345e562d962abe6700a1c357ec1e7e18232"
    )
    assert normalized_from[1]["url"].endswith("/pull/7433.diff")
    assert normalized_from[4]["availability"] == "not_checked_in_not_required"
    assert spec["field_provenance"]["redirect_rewind_behavior"] == [
        "know_005_requests_redirect_rewind_body_semantics",
        "data_008_focused_validation_recipe",
    ]
    assert spec["source_text_gaps"] == [
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
    ]


def test_builds_click_semver_default_prompt_spec() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    spec = build_issue_pr_prompt_spec(
        manifest,
        CLICK_SEMVER_DEFAULT_REPLAY_ID,
        manifest_path=MANIFEST_PATH,
    )

    assert spec["schema_version"] == "issue-pr-prompt-spec-v1"
    assert spec["record_kind"] == "issue_pr_prompt_spec"
    assert spec["prompt_spec_kind"] == "click_semver_non_string_default_help"
    assert spec["status"] == "normalized"
    assert spec["candidate_code_edits_attempted"] is False
    assert spec["required_prompt_fields_complete"] is True
    assert spec["missing_prompt_fields"] == []
    assert spec["source_text_blockers"] == []

    fields = spec["normalized_fields"]
    assert fields["minimal_reproduction"]["command_shape"] == {
        "decorator": "click.option",
        "option_decls": ["--version"],
        "type": "SemverType()",
        "default": "semver.Version(1, 0, 0)",
        "show_default": True,
    }
    assert (
        fields["observed_behavior"]["failure_mode"]
        == "non_string_default_compared_to_empty_string"
    )
    assert fields["observed_behavior"]["failing_expression"] == "default_value == ''"
    assert (
        fields["expected_behavior"]["behavior"]
        == "render_non_string_default_without_string_equality_probe"
    )
    assert (
        fields["affected_api_symbol"]["implementation_symbol"]
        == "click.core.Option.get_help_extra"
    )
    assert fields["input_shape"]["third_party_example"] == "semver.Version(1, 0, 0)"
    assert fields["acceptance_test_shape"]["test_file"] == "tests/test_options.py"
    assert fields["acceptance_test_shape"]["helper_class"] == "_StrictEq"
    assert (
        fields["non_string_default_behavior"]["after_fix_behavior"]
        == "Non-string defaults skip the empty-string branch and render "
        "through str(default_value) unless an earlier branch handles "
        "them specially."
    )
    assert (
        fields["type_conversion_semantics"]["conversion_layer"]
        == "click.core.Parameter.type_cast_value"
    )
    assert fields["empty_string_check_scope"]["accepted_condition"] == (
        "isinstance(default_value, str) and default_value == ''"
    )
    assert (
        fields["third_party_semver_version_reproduction_context"][
            "accepted_test_substitute"
        ]["class_name"]
        == "_StrictEq"
    )


def test_click_semver_default_prompt_spec_records_provenance() -> None:
    specs = build_issue_pr_prompt_specs(
        manifest_path=MANIFEST_PATH,
        replay_ids=[CLICK_SEMVER_DEFAULT_REPLAY_ID],
    )
    spec = specs[0]
    provenance = spec["provenance"]

    assert provenance["manifest_schema_version"] == "issue-pr-mini-replay-v0"
    assert provenance["stable_split"]["split"] == "train"
    normalized_from = provenance["normalized_from"]
    assert [source["id"] for source in normalized_from] == [
        "github_issue_3298",
        "github_pr_3299_conversation",
        "github_pr_3299_diff",
        "know_004_click_local_knowledge",
    ]
    assert normalized_from[0]["url"].endswith("/issues/3298")
    assert normalized_from[2]["merge_commit_sha"] == (
        "1458800409ed12076f18451889b0857db36aa522"
    )
    assert normalized_from[2]["url"].endswith("/pull/3299.diff")
    assert normalized_from[3]["record_ids"] == [
        "1904a6fa15665899650dbaec21829fdac4fdc493daddef9f118928262649d73a",
        "637634d1dee21f7cb4dbc244ebe384a4d8c75fb8070735345fac822cdb16ee7a",
        "9ec7175c0affa313906dcae73c5304d2dd6bfe1853cfdc05aa4273ebf0948147",
        "311aef2b41343232a5491c610f636efdf966891f32767d5e3a574ddc64ded546",
        "0dde986e749141c71f592950b9d7518adcb72b4447c488329df813b418bbdd99",
        "2882ec4082f4ea978c942600690cf8b99b95bcc92c921293ed6e637f441e67a0",
        "f96ac571dae6b2a53647803ebd07d034e91895a038ab1bb19ba6d528d97f7587",
        "29bde1f5e4eed1864b02359519d15579d45e2e5c0d697aece2772004f2eed2f1",
    ]
    assert spec["field_provenance"]["empty_string_check_scope"] == [
        "github_pr_3299_diff",
        "know_004_click_empty_string_check_semantics",
    ]
    assert spec["source_text_gaps"] == []


def test_prompt_spec_jsonl_summary_and_report(tmp_path: Path) -> None:
    specs = build_issue_pr_prompt_specs(
        manifest_path=MANIFEST_PATH,
        replay_ids=[CLICK_DEFAULT_MAP_REPLAY_ID],
    )

    out_path = write_issue_pr_prompt_specs_jsonl(specs, tmp_path / "specs.jsonl")
    summary = summarize_issue_pr_prompt_specs(specs, outcome_path=out_path)
    report_path = write_issue_pr_prompt_spec_report(
        specs,
        tmp_path / "report.md",
        summary=summary,
    )

    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["replay_id"] == CLICK_DEFAULT_MAP_REPLAY_ID
    assert summary["status_counts"] == {"normalized": 1}
    assert summary["missing_prompt_field_counts"] == {}
    report = report_path.read_text(encoding="utf-8")
    assert "DATA-009 Click Default Map Prompt Spec" in report
    assert "click.core.Option.consume_value" in report


def test_unknown_prompt_spec_stays_machine_readable_blocked() -> None:
    manifest = load_issue_pr_replay_manifest(MANIFEST_PATH)
    spec = build_issue_pr_prompt_spec(manifest, "pytest-dev__pytest-issue-14442-pr-14443")

    assert spec["status"] == "blocked"
    assert spec["required_prompt_fields_complete"] is False
    assert "minimal_reproduction" in spec["missing_prompt_fields"]
    assert spec["source_text_blockers"] == [
        {
            "source": "curated_prompt_normalizer",
            "availability": "missing",
            "impact": (
                "No checked-in normalizer exists for this replay row, so "
                "required prompt/spec fields cannot be trusted yet."
            ),
        }
    ]
