"""Durable training manifest row validation.

This module is intentionally a schema skeleton, not a dataset builder.  It
validates the stable per-row contract needed before future training and
evaluation manifests consume durable rows.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from collections.abc import Mapping, Sequence


TRAINING_MANIFEST_ROW_SCHEMA_VERSION = "training-manifest-row-v1"

ARTIFACT_CLASSES = frozenset(
    {
        "scratch",
        "checked_in_example",
        "release_archive",
        "synthetic",
        "issue_pr",
        "generated",
        "external_snapshot",
    }
)

SOURCE_KINDS = frozenset(
    {
        "repo_code",
        "repo_docs",
        "issue_pr",
        "candidate",
        "synthetic_prompt",
        "validation",
        "teacher_label",
        "local_knowledge",
    }
)

REDISTRIBUTION_CLASSES = frozenset(
    {"redistributable", "metadata_only", "local_only", "excluded"}
)
RETENTION_CLASSES = frozenset({"scratch", "durable_local", "checked_in", "release"})
REVIEW_STATUSES = frozenset(
    {"unreviewed", "reviewed", "rejected", "release_cleared"}
)
SPLITS = frozenset({"train", "validation", "test", "calibration", "heldout", "excluded"})
CHECKSUM_ALGORITHMS = frozenset({"sha256"})

EXCLUSION_REASONS = frozenset(
    {
        "license_unknown",
        "license_incompatible",
        "terms_unknown",
        "secret_detected",
        "pii_detected",
        "generated_vendor",
        "large_raw_external_payload",
        "accepted_label_leakage",
        "teacher_provenance_missing",
        "split_lineage_ambiguous",
        "checksum_missing",
        "cannot_regenerate",
        "binary_or_compiled",
        "bulk_examples",
    }
)

PII_SECRET_SCAN_STATUSES = frozenset(
    {"not_required", "pending", "passed", "failed", "manual_review"}
)

TERMS_REVIEW_STATUSES = frozenset(
    {"not_required", "unreviewed", "reviewed", "rejected"}
)

VALIDATION_RESULTS = frozenset({"passed", "failed", "errored", "timeout", "skipped"})
FLAKY_LABELS = frozenset({"unknown", "not_flaky", "suspected_flaky", "known_flaky"})
TEACHER_ALLOWED_USES = frozenset({"dev_review", "triage", "shadow_supervision"})
TEACHER_SPLIT_RESTRICTIONS = frozenset(
    {"no_heldout", "no_calibration", "shadow_only", "excluded"}
)

COMMON_REQUIRED_FIELDS = (
    "record_id",
    "schema_version",
    "artifact_class",
    "source_kind",
    "source_uri",
    "source_ref",
    "retrieved_at",
    "captured_by",
    "review_status",
    "license_spdx",
    "license_url",
    "terms_url",
    "redistribution_class",
    "retention_class",
    "split",
    "split_basis",
    "checksum_algorithm",
    "content_checksum",
    "normalized_checksum",
    "pii_secret_scan",
    "exclusion_reasons",
    "leakage_metadata",
)

SOURCE_KIND_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "repo_code": (
        "provider",
        "owner",
        "repo",
        "clone_url",
        "commit_sha",
        "file_path",
        "blob_sha",
        "language",
        "repo_license_spdx",
        "generated_or_vendor_flag",
        "submodule_flag",
        "snapshot_manifest_checksum",
    ),
    "repo_docs": (
        "doc_url_or_path",
        "doc_version_or_ref",
        "section_id",
        "doc_license_spdx",
        "excerpt_policy",
        "excerpt_checksum",
        "retrieval_method",
    ),
    "issue_pr": (
        "provider",
        "owner",
        "repo",
        "issue_numbers",
        "pr_numbers",
        "issue_urls",
        "pr_urls",
        "base_ref",
        "merge_or_head_ref",
        "linked_diff_url",
        "text_fields_present",
        "comment_count",
        "terms_review_status",
    ),
    "candidate": (
        "candidate_id",
        "candidate_generator",
        "generator_version",
        "input_record_ids",
        "action_family",
        "mutation_scope",
        "candidate_after_checksum",
        "candidate_diff_checksum",
        "derived_from_records",
        "validation_record_ids",
    ),
    "synthetic_prompt": (
        "template_family",
        "template_id",
        "template_version",
        "seed",
        "generator_name",
        "generator_version",
        "source_family",
        "human_seed_record_ids",
        "synthetic_transform",
        "teacher_assisted",
    ),
    "validation": (
        "validation_id",
        "command",
        "environment_fingerprint",
        "repo_ref",
        "candidate_id",
        "started_at",
        "duration_seconds",
        "exit_code",
        "stdout_checksum",
        "stderr_checksum",
        "result",
        "flaky_label",
        "timeout_seconds",
    ),
    "teacher_label": (
        "teacher_kind",
        "teacher_model_or_tool",
        "teacher_version",
        "prompt_checksum",
        "response_checksum",
        "human_reviewer",
        "review_decision",
        "allowed_use",
        "split_restriction",
        "label_confidence",
    ),
    "local_knowledge": (
        "knowledge_id",
        "knowledge_kind",
        "provenance_hash",
        "extracted_by",
        "source_record_ids",
    ),
}

LEAKAGE_METADATA_FIELDS = (
    "repository_key",
    "task_key",
    "prompt_seed_key",
    "template_family_key",
    "validation_recipe_key",
    "lineage_record_ids",
    "feature_input_exclusions",
    "accepted_structure_derived",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")


def validate_training_manifest_row(row: Mapping[str, object]) -> None:
    """Validate one durable training/evaluation manifest row."""

    if not isinstance(row, Mapping):
        raise ValueError("training manifest row must be an object")

    for field_name in COMMON_REQUIRED_FIELDS:
        if field_name not in row:
            raise ValueError(f"training manifest row missing required field: {field_name}")

    if row.get("schema_version") != TRAINING_MANIFEST_ROW_SCHEMA_VERSION:
        raise ValueError("training manifest row has unsupported schema_version")

    source_kind = _enum(row, "source_kind", SOURCE_KINDS)
    _enum(row, "artifact_class", ARTIFACT_CLASSES)
    _enum(row, "review_status", REVIEW_STATUSES)
    redistribution_class = _enum(
        row, "redistribution_class", REDISTRIBUTION_CLASSES
    )
    retention_class = _enum(row, "retention_class", RETENTION_CLASSES)
    split = _enum(row, "split", SPLITS)
    _enum(row, "checksum_algorithm", CHECKSUM_ALGORITHMS)

    _string(row, "record_id")
    for field_name in (
        "source_uri",
        "source_ref",
        "retrieved_at",
        "captured_by",
        "license_spdx",
    ):
        _string(row, field_name)
    _optional_string(row, "license_url")
    _optional_string(row, "terms_url")
    _mapping(row, "split_basis")
    _validate_pii_secret_scan(row["pii_secret_scan"])
    _validate_exclusion_reasons(row["exclusion_reasons"])
    _validate_leakage_metadata(row["leakage_metadata"])

    required_source_fields = SOURCE_KIND_REQUIRED_FIELDS[source_kind]
    for field_name in required_source_fields:
        if field_name not in row:
            raise ValueError(
                f"{source_kind} row missing required field: {field_name}"
            )

    _validate_source_kind_fields(row, source_kind)
    _validate_checksum_fields(row)
    _validate_durable_checksum_policy(row, split, retention_class, redistribution_class)
    _validate_release_and_exclusion_policy(row, split, retention_class, redistribution_class)

    json.dumps(row, sort_keys=True)


def validate_training_manifest_rows(rows: Sequence[Mapping[str, object]]) -> None:
    """Validate rows without doing cross-row split overlap checks."""

    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("training manifest rows must be a sequence")
    for row in rows:
        validate_training_manifest_row(row)


def load_training_manifest_jsonl(path: Path | str) -> list[dict[str, object]]:
    """Load and validate a JSONL manifest file."""

    resolved = Path(path).expanduser().resolve()
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(
        resolved.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{resolved}:{line_number}: expected JSON object")
        validate_training_manifest_row(value)
        rows.append(value)
    return rows


def _validate_source_kind_fields(row: Mapping[str, object], source_kind: str) -> None:
    if source_kind == "repo_code":
        for field_name in (
            "provider",
            "owner",
            "repo",
            "clone_url",
            "commit_sha",
            "file_path",
            "blob_sha",
            "language",
            "repo_license_spdx",
        ):
            _string(row, field_name)
        _bool(row, "generated_or_vendor_flag")
        _bool(row, "submodule_flag")
        _commit(row, "commit_sha")
        _sha256(row, "snapshot_manifest_checksum")
        return

    if source_kind == "repo_docs":
        for field_name in (
            "doc_url_or_path",
            "doc_version_or_ref",
            "section_id",
            "doc_license_spdx",
            "excerpt_policy",
            "retrieval_method",
        ):
            _string(row, field_name)
        _sha256(row, "excerpt_checksum")
        return

    if source_kind == "issue_pr":
        for field_name in (
            "provider",
            "owner",
            "repo",
            "base_ref",
            "merge_or_head_ref",
            "linked_diff_url",
        ):
            _string(row, field_name)
        _strings(row, "issue_numbers")
        _strings(row, "pr_numbers")
        _strings(row, "issue_urls")
        _strings(row, "pr_urls")
        _strings(row, "text_fields_present")
        _nonnegative_int(row, "comment_count")
        _enum(row, "terms_review_status", TERMS_REVIEW_STATUSES)
        return

    if source_kind == "candidate":
        for field_name in (
            "candidate_id",
            "candidate_generator",
            "generator_version",
            "action_family",
        ):
            _string(row, field_name)
        _strings(row, "input_record_ids")
        _strings(row, "derived_from_records")
        _strings(row, "validation_record_ids")
        _mapping(row, "mutation_scope")
        _sha256(row, "candidate_after_checksum")
        _sha256(row, "candidate_diff_checksum")
        return

    if source_kind == "synthetic_prompt":
        for field_name in (
            "template_family",
            "template_id",
            "template_version",
            "generator_name",
            "generator_version",
            "source_family",
            "synthetic_transform",
        ):
            _string(row, field_name)
        _string_or_int(row, "seed")
        _strings(row, "human_seed_record_ids")
        _bool(row, "teacher_assisted")
        return

    if source_kind == "validation":
        for field_name in (
            "validation_id",
            "command",
            "environment_fingerprint",
            "repo_ref",
            "candidate_id",
            "started_at",
        ):
            _string(row, field_name)
        _nonnegative_number(row, "duration_seconds")
        _nonnegative_int(row, "exit_code")
        _nonnegative_number(row, "timeout_seconds")
        _sha256(row, "stdout_checksum")
        _sha256(row, "stderr_checksum")
        _enum(row, "result", VALIDATION_RESULTS)
        _enum(row, "flaky_label", FLAKY_LABELS)
        return

    if source_kind == "teacher_label":
        for field_name in (
            "teacher_kind",
            "teacher_model_or_tool",
            "teacher_version",
            "human_reviewer",
            "review_decision",
        ):
            _string(row, field_name)
        _sha256(row, "prompt_checksum")
        _sha256(row, "response_checksum")
        _enum(row, "allowed_use", TEACHER_ALLOWED_USES)
        _enum(row, "split_restriction", TEACHER_SPLIT_RESTRICTIONS)
        _number_between(row, "label_confidence", minimum=0.0, maximum=1.0)
        if row.get("split") in {"heldout", "calibration", "test"}:
            raise ValueError("teacher_label rows cannot use heldout, calibration, or test split")
        return

    if source_kind == "local_knowledge":
        for field_name in ("knowledge_id", "knowledge_kind", "extracted_by"):
            _string(row, field_name)
        _sha256(row, "provenance_hash")
        _strings(row, "source_record_ids")
        return

    raise ValueError(f"unsupported source_kind: {source_kind}")


def _validate_pii_secret_scan(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("pii_secret_scan must be an object")
    _enum(value, "status", PII_SECRET_SCAN_STATUSES)
    for field_name in ("tool", "scanned_at"):
        _optional_string(value, field_name)
    _optional_string(value, "result")
    if value.get("status") == "failed":
        result = value.get("result")
        if not isinstance(result, str) or not result:
            raise ValueError("failed pii_secret_scan requires result")


def _validate_exclusion_reasons(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("exclusion_reasons must be a list")
    for reason in value:
        if reason not in EXCLUSION_REASONS:
            raise ValueError(f"unsupported exclusion reason: {reason!r}")


def _validate_leakage_metadata(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("leakage_metadata must be an object")
    for field_name in LEAKAGE_METADATA_FIELDS:
        if field_name not in value:
            raise ValueError(f"leakage_metadata missing required field: {field_name}")
    for field_name in (
        "repository_key",
        "task_key",
        "prompt_seed_key",
        "template_family_key",
        "validation_recipe_key",
    ):
        item = value[field_name]
        if item is not None and not isinstance(item, str):
            raise ValueError(f"leakage_metadata.{field_name} must be string or null")
    for field_name in ("lineage_record_ids", "feature_input_exclusions"):
        item = value[field_name]
        if not isinstance(item, list) or not all(isinstance(i, str) for i in item):
            raise ValueError(f"leakage_metadata.{field_name} must be strings")
    if not isinstance(value["accepted_structure_derived"], bool):
        raise ValueError("leakage_metadata.accepted_structure_derived must be bool")


def _validate_checksum_fields(row: Mapping[str, object]) -> None:
    for path, value in _walk_checksum_fields(row):
        if value is None:
            continue
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"{path} must be a sha256 hex digest")


def _walk_checksum_fields(
    value: object,
    *,
    prefix: str = "",
) -> list[tuple[str, object]]:
    fields: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.endswith("_checksum") or key_text in {"content_checksum"}:
                fields.append((path, item))
            fields.extend(_walk_checksum_fields(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            fields.extend(_walk_checksum_fields(item, prefix=f"{prefix}[{index}]"))
    return fields


def _validate_durable_checksum_policy(
    row: Mapping[str, object],
    split: str,
    retention_class: str,
    redistribution_class: str,
) -> None:
    content_checksum = row.get("content_checksum")
    missing_checksum = not isinstance(content_checksum, str) or not content_checksum
    scratch_excluded = (
        split == "excluded"
        and retention_class == "scratch"
        and redistribution_class == "excluded"
    )
    if missing_checksum and not scratch_excluded:
        raise ValueError(
            "durable training/eval rows require content_checksum; missing checksums "
            "are allowed only for scratch excluded rows"
        )
    if scratch_excluded:
        reasons = row.get("exclusion_reasons")
        if not isinstance(reasons, list) or not reasons:
            raise ValueError("scratch excluded rows require exclusion_reasons")


def _validate_release_and_exclusion_policy(
    row: Mapping[str, object],
    split: str,
    retention_class: str,
    redistribution_class: str,
) -> None:
    reasons = row.get("exclusion_reasons")
    excluded = split == "excluded" or redistribution_class == "excluded"
    if excluded:
        if split != "excluded" or redistribution_class != "excluded":
            raise ValueError("excluded rows must use split and redistribution_class excluded")
        if not isinstance(reasons, list) or not reasons:
            raise ValueError("excluded rows require exclusion_reasons")
    elif reasons:
        raise ValueError("non-excluded rows must not include exclusion_reasons")

    if retention_class == "release" and redistribution_class != "redistributable":
        raise ValueError("release retention requires redistributable rows")
    if row.get("review_status") == "release_cleared" and redistribution_class == "local_only":
        raise ValueError("local_only rows cannot be release_cleared")


def _enum(row: Mapping[str, object], field_name: str, allowed: frozenset[str]) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{field_name} has unsupported value: {value!r}")
    return value


def _mapping(row: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    value = row.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _string(row: Mapping[str, object], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(row: Mapping[str, object], field_name: str) -> str | None:
    value = row.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return value


def _strings(row: Mapping[str, object], field_name: str) -> list[str]:
    value = row.get(field_name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return value


def _bool(row: Mapping[str, object], field_name: str) -> bool:
    value = row.get(field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")
    return value


def _nonnegative_int(row: Mapping[str, object], field_name: str) -> int:
    value = row.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative int")
    return value


def _nonnegative_number(row: Mapping[str, object], field_name: str) -> float:
    value = row.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a nonnegative number")
    return float(value)


def _number_between(
    row: Mapping[str, object],
    field_name: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    value = row.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    value_float = float(value)
    if value_float < minimum or value_float > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return value_float


def _string_or_int(row: Mapping[str, object], field_name: str) -> str | int:
    value = row.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{field_name} must be a string or int")
    if isinstance(value, str) and not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def _sha256(row: Mapping[str, object], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a sha256 hex digest")
    return value


def _commit(row: Mapping[str, object], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a 40-64 character hex commit")
    return value
