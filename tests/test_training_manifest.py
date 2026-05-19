from __future__ import annotations

import json

import pytest

from j3.training_manifest import (
    SOURCE_KIND_REQUIRED_FIELDS,
    TRAINING_MANIFEST_ROW_SCHEMA_VERSION,
    load_training_manifest_jsonl,
    validate_training_manifest_row,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
COMMIT = "1" * 40


def _base_row(source_kind: str = "repo_code") -> dict[str, object]:
    return {
        "record_id": f"scale-003-{source_kind}",
        "schema_version": TRAINING_MANIFEST_ROW_SCHEMA_VERSION,
        "artifact_class": "external_snapshot",
        "source_kind": source_kind,
        "source_uri": "https://github.com/example/project",
        "source_ref": COMMIT,
        "retrieved_at": "2026-05-19T00:00:00Z",
        "captured_by": "manual-fixture",
        "review_status": "reviewed",
        "license_spdx": "MIT",
        "license_url": "https://github.com/example/project/LICENSE",
        "terms_url": "https://docs.github.com/site-policy/github-terms/github-terms-of-service",
        "redistribution_class": "local_only",
        "retention_class": "durable_local",
        "split": "train",
        "split_basis": {
            "repository": "example/project",
            "task": "scale-003-fixture",
            "policy": "repository_and_task_lineage",
        },
        "checksum_algorithm": "sha256",
        "content_checksum": SHA_A,
        "normalized_checksum": SHA_B,
        "pii_secret_scan": {
            "status": "passed",
            "tool": "fixture-scan",
            "scanned_at": "2026-05-19T00:01:00Z",
            "result": "no findings",
        },
        "exclusion_reasons": [],
        "leakage_metadata": {
            "repository_key": "example/project",
            "task_key": "scale-003-fixture",
            "prompt_seed_key": None,
            "template_family_key": None,
            "validation_recipe_key": "pytest-fixture",
            "lineage_record_ids": ["source-row"],
            "feature_input_exclusions": ["accepted_diff_paths", "known_pass_fail"],
            "accepted_structure_derived": False,
        },
    }


def _row(source_kind: str = "repo_code") -> dict[str, object]:
    row = _base_row(source_kind)
    if source_kind == "repo_code":
        row.update(
            {
                "provider": "github",
                "owner": "example",
                "repo": "project",
                "clone_url": "https://github.com/example/project.git",
                "commit_sha": COMMIT,
                "file_path": "src/project/core.py",
                "blob_sha": "abc123",
                "language": "Python",
                "repo_license_spdx": "MIT",
                "generated_or_vendor_flag": False,
                "submodule_flag": False,
                "snapshot_manifest_checksum": SHA_C,
            }
        )
    elif source_kind == "repo_docs":
        row.update(
            {
                "artifact_class": "checked_in_example",
                "doc_url_or_path": "docs/usage.md",
                "doc_version_or_ref": COMMIT,
                "section_id": "usage",
                "doc_license_spdx": "MIT",
                "excerpt_policy": "metadata_only",
                "excerpt_checksum": SHA_C,
                "retrieval_method": "git_checkout",
            }
        )
    elif source_kind == "issue_pr":
        row.update(
            {
                "artifact_class": "issue_pr",
                "provider": "github",
                "owner": "example",
                "repo": "project",
                "issue_numbers": ["12"],
                "pr_numbers": ["13"],
                "issue_urls": ["https://github.com/example/project/issues/12"],
                "pr_urls": ["https://github.com/example/project/pull/13"],
                "base_ref": COMMIT,
                "merge_or_head_ref": "2" * 40,
                "linked_diff_url": "https://github.com/example/project/pull/13.diff",
                "text_fields_present": ["issue_title", "pr_title"],
                "comment_count": 2,
                "terms_review_status": "reviewed",
            }
        )
    elif source_kind == "candidate":
        row.update(
            {
                "artifact_class": "generated",
                "candidate_id": "candidate-1",
                "candidate_generator": "typed-builder",
                "generator_version": "v1",
                "input_record_ids": ["repo-row"],
                "action_family": "type_annotation_update",
                "mutation_scope": {
                    "allowed_write_paths": ["src/project/core.py"],
                    "production_files_changed": ["src/project/core.py"],
                },
                "candidate_after_checksum": SHA_C,
                "candidate_diff_checksum": SHA_D,
                "derived_from_records": ["repo-row"],
                "validation_record_ids": ["validation-row"],
            }
        )
    elif source_kind == "synthetic_prompt":
        row.update(
            {
                "artifact_class": "synthetic",
                "redistribution_class": "redistributable",
                "retention_class": "checked_in",
                "template_family": "small-library",
                "template_id": "slugify-request",
                "template_version": "v1",
                "seed": 7,
                "generator_name": "j3-fixture-generator",
                "generator_version": "v1",
                "source_family": "project_owned_template",
                "human_seed_record_ids": [],
                "synthetic_transform": "slot_fill",
                "teacher_assisted": False,
            }
        )
    elif source_kind == "validation":
        row.update(
            {
                "artifact_class": "generated",
                "validation_id": "validation-1",
                "command": "python -m pytest tests/test_core.py -q",
                "environment_fingerprint": "python=3.12 pytest=8",
                "repo_ref": COMMIT,
                "candidate_id": "candidate-1",
                "started_at": "2026-05-19T00:02:00Z",
                "duration_seconds": 0.12,
                "exit_code": 0,
                "stdout_checksum": SHA_C,
                "stderr_checksum": SHA_D,
                "result": "passed",
                "flaky_label": "not_flaky",
                "timeout_seconds": 30.0,
            }
        )
    elif source_kind == "teacher_label":
        row.update(
            {
                "artifact_class": "generated",
                "teacher_kind": "tool",
                "teacher_model_or_tool": "local-reviewer",
                "teacher_version": "v1",
                "prompt_checksum": SHA_C,
                "response_checksum": SHA_D,
                "human_reviewer": "reviewer-1",
                "review_decision": "approved_for_shadow",
                "allowed_use": "shadow_supervision",
                "split_restriction": "no_heldout",
                "label_confidence": 0.8,
            }
        )
    elif source_kind == "local_knowledge":
        row.update(
            {
                "artifact_class": "checked_in_example",
                "knowledge_id": "pytest-import-style",
                "knowledge_kind": "import_style",
                "provenance_hash": SHA_C,
                "extracted_by": "j3.local_knowledge",
                "source_record_ids": ["repo-row"],
            }
        )
    else:
        raise AssertionError(f"unhandled source kind {source_kind}")
    return row


@pytest.mark.parametrize("source_kind", sorted(SOURCE_KIND_REQUIRED_FIELDS))
def test_accepts_valid_rows_for_policy_source_kinds(source_kind: str) -> None:
    validate_training_manifest_row(_row(source_kind))


def test_load_training_manifest_jsonl_validates_rows(tmp_path) -> None:
    path = tmp_path / "manifest.jsonl"
    path.write_text(json.dumps(_row("synthetic_prompt"), sort_keys=True) + "\n")

    rows = load_training_manifest_jsonl(path)

    assert rows[0]["source_kind"] == "synthetic_prompt"


def test_rejects_missing_common_fields() -> None:
    row = _row("repo_code")
    del row["split_basis"]

    with pytest.raises(ValueError, match="missing required field: split_basis"):
        validate_training_manifest_row(row)


def test_rejects_missing_source_kind_fields() -> None:
    row = _row("candidate")
    del row["candidate_diff_checksum"]

    with pytest.raises(ValueError, match="candidate row missing required field"):
        validate_training_manifest_row(row)


def test_rejects_source_kind_field_type_errors() -> None:
    row = _row("issue_pr")
    row["comment_count"] = -1

    with pytest.raises(ValueError, match="comment_count must be a nonnegative int"):
        validate_training_manifest_row(row)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("split", "dev", "split has unsupported value"),
        ("redistribution_class", "public", "redistribution_class has unsupported value"),
        ("retention_class", "forever", "retention_class has unsupported value"),
        ("review_status", "approved", "review_status has unsupported value"),
        ("artifact_class", "blob", "artifact_class has unsupported value"),
        ("source_kind", "webpage", "source_kind has unsupported value"),
        ("checksum_algorithm", "md5", "checksum_algorithm has unsupported value"),
    ],
)
def test_rejects_invalid_policy_classes(
    field_name: str,
    value: object,
    message: str,
) -> None:
    row = _row("repo_code")
    row[field_name] = value

    with pytest.raises(ValueError, match=message):
        validate_training_manifest_row(row)


def test_rejects_invalid_checksum_shape() -> None:
    row = _row("validation")
    row["stdout_checksum"] = SHA_E.upper()

    with pytest.raises(ValueError, match="stdout_checksum must be a sha256"):
        validate_training_manifest_row(row)


def test_rejects_missing_checksums_for_durable_rows() -> None:
    row = _row("repo_code")
    row["content_checksum"] = None

    with pytest.raises(ValueError, match="durable training/eval rows require"):
        validate_training_manifest_row(row)


def test_accepts_excluded_scratch_row_without_content_checksum() -> None:
    row = _row("issue_pr")
    row.update(
        {
            "retention_class": "scratch",
            "redistribution_class": "excluded",
            "split": "excluded",
            "review_status": "rejected",
            "content_checksum": None,
            "normalized_checksum": None,
            "exclusion_reasons": ["terms_unknown", "checksum_missing"],
        }
    )

    validate_training_manifest_row(row)


def test_accepts_local_only_durable_training_row_with_checksums() -> None:
    row = _row("repo_code")
    row["redistribution_class"] = "local_only"
    row["retention_class"] = "durable_local"
    row["split"] = "train"

    validate_training_manifest_row(row)


def test_rejects_release_cleared_local_only_rows() -> None:
    row = _row("repo_code")
    row["review_status"] = "release_cleared"
    row["redistribution_class"] = "local_only"

    with pytest.raises(ValueError, match="local_only rows cannot be release_cleared"):
        validate_training_manifest_row(row)


def test_rejects_non_excluded_rows_with_exclusion_reasons() -> None:
    row = _row("synthetic_prompt")
    row["exclusion_reasons"] = ["accepted_label_leakage"]

    with pytest.raises(ValueError, match="non-excluded rows must not include"):
        validate_training_manifest_row(row)


def test_requires_split_leakage_metadata_fields() -> None:
    row = _row("repo_code")
    leakage = row["leakage_metadata"]
    assert isinstance(leakage, dict)
    del leakage["feature_input_exclusions"]

    with pytest.raises(ValueError, match="leakage_metadata missing required field"):
        validate_training_manifest_row(row)


def test_rejects_teacher_labels_in_heldout_like_splits() -> None:
    row = _row("teacher_label")
    row["split"] = "heldout"

    with pytest.raises(ValueError, match="teacher_label rows cannot use heldout"):
        validate_training_manifest_row(row)
