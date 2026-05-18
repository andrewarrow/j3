"""Extract compact local-knowledge records for the tests-only wedge."""

from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import tomllib


LOCAL_KNOWLEDGE_SCHEMA_VERSION = "local-knowledge-record-v1"
LOCAL_KNOWLEDGE_EXTRACTOR_NAME = "local_knowledge"
LOCAL_KNOWLEDGE_EXTRACTOR_VERSION = "v1"
LOCAL_KNOWLEDGE_EXTRACTED_BY = (
    f"{LOCAL_KNOWLEDGE_EXTRACTOR_NAME}/{LOCAL_KNOWLEDGE_EXTRACTOR_VERSION}"
)

RECORD_TYPES = {
    "library_idiom_record",
    "pytest_layout_record",
    "pytest_pattern_record",
    "packaging_layout_record",
    "public_api_record",
    "repo_changed_file_context_record",
    "validation_recipe_record",
    "knowledge_use_record",
}
SPLITS = {"calibration", "train", "validation", "test", "heldout"}
CONFIDENCE_VALUES = {"observed", "inferred", "validated"}
RAW_BLOB_KEYS = {
    "raw_source",
    "source_text",
    "source_blob",
    "raw_blob",
    "raw_diff",
    "full_source",
}
CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES = (
    "repo_changed_file_context",
    "repo_test_pattern",
    "focused_validation_recipe",
    "click_parameter_default_handling",
    "click_type_conversion_semantics",
    "click_non_string_default_handling",
    "click_empty_string_check_semantics",
    "third_party_semver_version_reproduction",
)
REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES = (
    "repo_changed_file_context",
    "focused_validation_recipe",
    "requests_prepare_body_stream_detection",
    "requests_getattr_file_wrapper_behavior",
    "requests_redirect_rewind_body_semantics",
    "requests_pytest_httpbin_fixture_setup",
    "requests_ranking_changed_test_patterns",
)
PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES = (
    "repo_changed_file_context",
    "focused_validation_recipe",
    "pytest_strict_addopts_behavior",
    "pytest_strict_markers_config_semantics",
    "pytest_repo_test_patterns",
    "pytest_changelog_fragment_convention",
    "pytest_authors_convention",
)
PYTEST_TIMEDELTA_APPROX_REQUIRED_KNOWLEDGE_CATEGORIES = (
    "repo_changed_file_context",
    "focused_validation_recipe",
    "pytest_approx_timedelta_tolerance_semantics",
    "pytest_datetime_timedelta_comparison_behavior",
    "pytest_repo_test_patterns",
    "pytest_timedelta_approx_readiness_blockers",
)
SCRAPY_DOWNLOADER_AWARE_REQUIRED_KNOWLEDGE_CATEGORIES = (
    "repo_changed_file_context",
    "focused_validation_recipe",
    "scrapy_downloader_aware_priority_queue",
    "scrapy_slot_active_download_accounting",
    "scrapy_pqueue_test_patterns",
    "scrapy_pqueue_readiness_blockers",
)


def extract_local_knowledge_records(
    repo: Path,
    *,
    repo_id: str,
    repo_ref: str,
    split: str = "calibration",
    repo_url: str = "",
    license: str = "",
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
    tasks: Sequence[Mapping[str, object]] = (),
    outcome_ids_by_task: Mapping[str, Sequence[str]] | None = None,
) -> tuple[dict[str, object], ...]:
    """Extract JSONL-ready pytest, packaging, import, and validation records.

    The extractor works from a local checkout or fixture. It stores compact
    config and AST shapes plus checksums, not raw source blobs.
    """

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")
    _validate_split(split)

    context = {
        "repo_id": repo_id,
        "repo_ref": repo_ref,
        "split": split,
        "repo_url": repo_url,
        "license": license,
        "retrieved_at": retrieved_at,
    }
    pyproject = _load_pyproject(resolved)
    pytest_ini = _load_pytest_ini(resolved)
    python_files = _python_files(resolved)
    test_files = tuple(path for path in python_files if _is_test_file(path))

    records: list[dict[str, object]] = [
        _packaging_layout_record(resolved, context, pyproject, python_files),
        _pytest_layout_record(resolved, context, pyproject, pytest_ini, test_files),
    ]
    records.extend(_public_api_records(resolved, context, python_files))
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=tasks,
            outcome_ids_by_task=outcome_ids_by_task or {},
        )
    )
    records.extend(_pytest_pattern_records(resolved, context, test_files))

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def build_knowledge_use_record(
    *,
    candidate_id: str,
    task_id: str,
    retrieved_record_ids: Sequence[str],
    action_family: str,
    validation_result: Mapping[str, object],
    split: str = "calibration",
    outcome_id: str | None = None,
    residual_labels: Sequence[str] = (),
    cited_purposes: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Build the citation row a tests-only planner can attach to a candidate."""

    _validate_split(split)
    data = {
        "candidate_id": candidate_id,
        "retrieved_record_ids": list(retrieved_record_ids),
        "cited_purposes": {
            key: list(value) for key, value in (cited_purposes or {}).items()
        },
        "action_family": action_family,
        "validation_result": _json_copy(validation_result),
    }
    links = {
        "task_ids": [task_id],
        "outcome_ids": [outcome_id] if outcome_id else [],
        "residual_labels": list(residual_labels),
    }
    source = {
        "kind": "candidate_outcome",
        "repo": "",
        "ref": "",
        "path": candidate_id,
        "url": "",
        "license": "",
        "retrieved_at": "candidate-time",
    }
    return _record(
        record_type="knowledge_use_record",
        source=source,
        split=split,
        provenance_hash=_sha256_json({"data": data, "links": links}),
        confidence="observed",
        links=links,
        data=data,
    )


def build_click_replay_local_knowledge_records(
    repo: Path,
    replay_row: Mapping[str, object],
    *,
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Build Click issue/PR replay knowledge rows from a repo-before checkout.

    This extractor is intentionally narrow: it emits compact records for the
    `pallets__click-issue-3298-pr-3299` row without copying source or diffs.
    """

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")

    replay_id = _required_str(replay_row, "id")
    if replay_id != "pallets__click-issue-3298-pr-3299":
        raise ValueError(f"unsupported Click replay row: {replay_id}")

    repo_id = _required_str(replay_row, "repo")
    repo_before_ref = _mapping(replay_row.get("repo_before_ref"), field="repo_before_ref")
    accepted_change = _mapping(replay_row.get("accepted_change"), field="accepted_change")
    validation = _mapping(replay_row.get("validation"), field="validation")
    provenance_license = _mapping(
        replay_row.get("provenance_license"),
        field="provenance_license",
    )
    prompt_source = _mapping(replay_row.get("prompt_source"), field="prompt_source")
    stable_split = _mapping(replay_row.get("stable_split"), field="stable_split")

    changed_files = _string_sequence(accepted_change.get("changed_files", ()))
    validation_command = _required_str(validation, "command")
    split = _required_str(stable_split, "split")
    _validate_split(split)

    context = {
        "repo_id": repo_id,
        "repo_ref": _required_str(repo_before_ref, "sha"),
        "split": split,
        "repo_url": _optional_str(provenance_license.get("repository_url")),
        "license": _optional_str(provenance_license.get("license_spdx")),
        "retrieved_at": retrieved_at,
    }
    links = {
        "task_ids": [replay_id],
        "outcome_ids": ["DATA-007/pallets__click-issue-3298-pr-3299"],
        "residual_labels": ["local_knowledge_gap"],
    }
    task = {
        "id": replay_id,
        "task_type": "issue_pr_replay",
        "allowed_write_paths": changed_files,
        "public_validation_commands": [validation_command],
        "expected_failure_modes": ["local_knowledge_gap"],
        "required_knowledge_categories": CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    }

    records: list[dict[str, object]] = [
        _click_changed_file_context_record(
            resolved,
            context,
            replay_row=replay_row,
            changed_files=changed_files,
            links=links,
        ),
        _click_repo_test_pattern_record(
            resolved,
            context,
            replay_id=replay_id,
            test_path=_click_test_path(changed_files),
            links=links,
        ),
    ]
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=[task],
            outcome_ids_by_task={replay_id: ["DATA-007/pallets__click-issue-3298-pr-3299"]},
        )
    )
    records.extend(
        _click_library_idiom_records(
            resolved,
            context,
            replay_id=replay_id,
            prompt_source=prompt_source,
            changed_files=changed_files,
            validation_command=validation_command,
            links=links,
        )
    )

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def build_requests_replay_local_knowledge_records(
    repo: Path,
    replay_row: Mapping[str, object],
    *,
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Build Requests issue/PR replay knowledge rows from a repo-before checkout."""

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")

    replay_id = _required_str(replay_row, "id")
    if replay_id != "psf__requests-issue-7432-pr-7433":
        raise ValueError(f"unsupported Requests replay row: {replay_id}")

    repo_id = _required_str(replay_row, "repo")
    repo_before_ref = _mapping(replay_row.get("repo_before_ref"), field="repo_before_ref")
    accepted_change = _mapping(replay_row.get("accepted_change"), field="accepted_change")
    validation = _mapping(replay_row.get("validation"), field="validation")
    provenance_license = _mapping(
        replay_row.get("provenance_license"),
        field="provenance_license",
    )
    prompt_source = _mapping(replay_row.get("prompt_source"), field="prompt_source")
    stable_split = _mapping(replay_row.get("stable_split"), field="stable_split")

    changed_files = _string_sequence(accepted_change.get("changed_files", ()))
    split = _required_str(stable_split, "split")
    _validate_split(split)
    focused_validation_command = (
        ".venv/bin/python -m pytest tests/test_requests.py -q "
        "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
    )

    context = {
        "repo_id": repo_id,
        "repo_ref": _required_str(repo_before_ref, "sha"),
        "split": split,
        "repo_url": _optional_str(provenance_license.get("repository_url")),
        "license": _optional_str(provenance_license.get("license_spdx")),
        "retrieved_at": retrieved_at,
    }
    links = {
        "task_ids": [replay_id],
        "outcome_ids": ["DATA-008/psf__requests-issue-7432-pr-7433"],
        "residual_labels": ["local_knowledge_gap"],
    }
    task = {
        "id": replay_id,
        "task_type": "issue_pr_replay",
        "allowed_write_paths": changed_files,
        "public_validation_commands": [focused_validation_command],
        "expected_failure_modes": ["local_knowledge_gap"],
        "required_knowledge_categories": REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    }

    records: list[dict[str, object]] = [
        _requests_changed_file_context_record(
            resolved,
            context,
            replay_row=replay_row,
            changed_files=changed_files,
            links=links,
        )
    ]
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=[task],
            outcome_ids_by_task={
                replay_id: ["DATA-008/psf__requests-issue-7432-pr-7433"]
            },
        )
    )
    records.extend(
        _requests_library_idiom_records(
            resolved,
            context,
            replay_id=replay_id,
            prompt_source=prompt_source,
            changed_files=changed_files,
            manifest_validation_command=_required_str(validation, "command"),
            focused_validation_command=focused_validation_command,
            links=links,
        )
    )

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def build_pytest_strict_addopts_local_knowledge_records(
    repo: Path,
    replay_row: Mapping[str, object],
    *,
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Build pytest #14442/#14443 local-knowledge rows from repo-before."""

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")

    replay_id = _required_str(replay_row, "id")
    if replay_id != "pytest-dev__pytest-issue-14442-pr-14443":
        raise ValueError(f"unsupported pytest strict-addopts replay row: {replay_id}")

    repo_id = _required_str(replay_row, "repo")
    repo_before_ref = _mapping(replay_row.get("repo_before_ref"), field="repo_before_ref")
    accepted_change = _mapping(replay_row.get("accepted_change"), field="accepted_change")
    validation = _mapping(replay_row.get("validation"), field="validation")
    provenance_license = _mapping(
        replay_row.get("provenance_license"),
        field="provenance_license",
    )
    prompt_source = _mapping(replay_row.get("prompt_source"), field="prompt_source")
    stable_split = _mapping(replay_row.get("stable_split"), field="stable_split")

    changed_files = _string_sequence(accepted_change.get("changed_files", ()))
    split = _required_str(stable_split, "split")
    _validate_split(split)
    focused_validation_command = _required_str(validation, "command")

    context = {
        "repo_id": repo_id,
        "repo_ref": _required_str(repo_before_ref, "sha"),
        "split": split,
        "repo_url": _optional_str(provenance_license.get("repository_url")),
        "license": _optional_str(provenance_license.get("license_spdx")),
        "retrieved_at": retrieved_at,
    }
    links = {
        "task_ids": [replay_id],
        "outcome_ids": ["DATA-018/pytest-dev__pytest-issue-14442-pr-14443"],
        "residual_labels": ["local_knowledge_gap"],
    }
    task = {
        "id": replay_id,
        "task_type": "issue_pr_replay",
        "allowed_write_paths": changed_files,
        "public_validation_commands": [focused_validation_command],
        "expected_failure_modes": ["local_knowledge_gap"],
        "required_knowledge_categories": PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES,
    }

    records: list[dict[str, object]] = [
        _pytest_strict_changed_file_context_record(
            resolved,
            context,
            replay_row=replay_row,
            changed_files=changed_files,
            links=links,
        )
    ]
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=[task],
            outcome_ids_by_task={
                replay_id: ["DATA-018/pytest-dev__pytest-issue-14442-pr-14443"]
            },
        )
    )
    records.extend(
        _pytest_strict_idiom_records(
            resolved,
            context,
            replay_id=replay_id,
            prompt_source=prompt_source,
            changed_files=changed_files,
            focused_validation_command=focused_validation_command,
            links=links,
        )
    )

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def build_pytest_timedelta_approx_local_knowledge_records(
    repo: Path,
    replay_row: Mapping[str, object],
    *,
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Build pytest #14462/#14466 local-knowledge rows from repo-before."""

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")

    replay_id = _required_str(replay_row, "id")
    if replay_id != "pytest-dev__pytest-issue-14462-pr-14466":
        raise ValueError(f"unsupported pytest timedelta-approx replay row: {replay_id}")

    repo_id = _required_str(replay_row, "repo")
    repo_before_ref = _mapping(replay_row.get("repo_before_ref"), field="repo_before_ref")
    accepted_change = _mapping(replay_row.get("accepted_change"), field="accepted_change")
    validation = _mapping(replay_row.get("validation"), field="validation")
    provenance_license = _mapping(
        replay_row.get("provenance_license"),
        field="provenance_license",
    )
    prompt_source = _mapping(replay_row.get("prompt_source"), field="prompt_source")
    stable_split = _mapping(replay_row.get("stable_split"), field="stable_split")

    changed_files = _string_sequence(accepted_change.get("changed_files", ()))
    split = _required_str(stable_split, "split")
    _validate_split(split)
    focused_validation_command = _required_str(validation, "command")

    context = {
        "repo_id": repo_id,
        "repo_ref": _required_str(repo_before_ref, "sha"),
        "split": split,
        "repo_url": _optional_str(provenance_license.get("repository_url")),
        "license": _optional_str(provenance_license.get("license_spdx")),
        "retrieved_at": retrieved_at,
    }
    links = {
        "task_ids": [replay_id],
        "outcome_ids": ["DATA-018/pytest-dev__pytest-issue-14462-pr-14466"],
        "residual_labels": ["local_knowledge_gap"],
    }
    task = {
        "id": replay_id,
        "task_type": "issue_pr_replay",
        "allowed_write_paths": changed_files,
        "public_validation_commands": [focused_validation_command],
        "expected_failure_modes": ["local_knowledge_gap"],
        "required_knowledge_categories": (
            PYTEST_TIMEDELTA_APPROX_REQUIRED_KNOWLEDGE_CATEGORIES
        ),
    }

    records: list[dict[str, object]] = [
        _pytest_approx_changed_file_context_record(
            resolved,
            context,
            replay_row=replay_row,
            changed_files=changed_files,
            links=links,
        )
    ]
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=[task],
            outcome_ids_by_task={
                replay_id: ["DATA-018/pytest-dev__pytest-issue-14462-pr-14466"]
            },
        )
    )
    records.extend(
        _pytest_approx_idiom_records(
            resolved,
            context,
            replay_id=replay_id,
            prompt_source=prompt_source,
            changed_files=changed_files,
            focused_validation_command=focused_validation_command,
            links=links,
        )
    )

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def build_scrapy_downloader_aware_local_knowledge_records(
    repo: Path,
    replay_row: Mapping[str, object],
    *,
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Build Scrapy #7293/#7351 local-knowledge rows from repo-before."""

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")

    replay_id = _required_str(replay_row, "id")
    if replay_id != "scrapy__scrapy-issue-7293-pr-7351":
        raise ValueError(f"unsupported Scrapy downloader-aware replay row: {replay_id}")

    repo_id = _required_str(replay_row, "repo")
    repo_before_ref = _mapping(replay_row.get("repo_before_ref"), field="repo_before_ref")
    accepted_change = _mapping(replay_row.get("accepted_change"), field="accepted_change")
    validation = _mapping(replay_row.get("validation"), field="validation")
    provenance_license = _mapping(
        replay_row.get("provenance_license"),
        field="provenance_license",
    )
    prompt_source = _mapping(replay_row.get("prompt_source"), field="prompt_source")
    stable_split = _mapping(replay_row.get("stable_split"), field="stable_split")

    changed_files = _string_sequence(accepted_change.get("changed_files", ()))
    split = _required_str(stable_split, "split")
    _validate_split(split)
    focused_validation_command = _required_str(validation, "command")

    context = {
        "repo_id": repo_id,
        "repo_ref": _required_str(repo_before_ref, "sha"),
        "split": split,
        "repo_url": _optional_str(provenance_license.get("repository_url")),
        "license": _optional_str(provenance_license.get("license_spdx")),
        "retrieved_at": retrieved_at,
    }
    links = {
        "task_ids": [replay_id],
        "outcome_ids": ["DATA-030/scrapy__scrapy-issue-7293-pr-7351"],
        "residual_labels": ["local_knowledge_gap"],
    }
    task = {
        "id": replay_id,
        "task_type": "issue_pr_replay",
        "allowed_write_paths": changed_files,
        "public_validation_commands": [focused_validation_command],
        "expected_failure_modes": ["local_knowledge_gap"],
        "required_knowledge_categories": (
            SCRAPY_DOWNLOADER_AWARE_REQUIRED_KNOWLEDGE_CATEGORIES
        ),
    }

    records: list[dict[str, object]] = [
        _scrapy_changed_file_context_record(
            resolved,
            context,
            replay_row=replay_row,
            changed_files=changed_files,
            links=links,
        )
    ]
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=[task],
            outcome_ids_by_task={
                replay_id: ["DATA-030/scrapy__scrapy-issue-7293-pr-7351"]
            },
        )
    )
    records.extend(
        _scrapy_downloader_aware_idiom_records(
            resolved,
            context,
            replay_id=replay_id,
            prompt_source=prompt_source,
            changed_files=changed_files,
            focused_validation_command=focused_validation_command,
            links=links,
        )
    )

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def write_local_knowledge_jsonl(
    records: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write validated local-knowledge rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for record in records:
            validate_local_knowledge_record(record)
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return resolved


def validate_local_knowledge_record(row: Mapping[str, object]) -> None:
    """Validate the stable local-knowledge schema surface."""

    if row.get("schema_version") != LOCAL_KNOWLEDGE_SCHEMA_VERSION:
        raise ValueError("local knowledge record has unsupported schema_version")
    if row.get("record_type") not in RECORD_TYPES:
        raise ValueError("local knowledge record has unsupported record_type")
    record_id = row.get("id")
    if not isinstance(record_id, str) or not _is_sha256(record_id):
        raise ValueError("local knowledge record id must be a sha256 hex digest")
    provenance_hash = row.get("provenance_hash")
    if not isinstance(provenance_hash, str) or not _is_sha256(provenance_hash):
        raise ValueError("local knowledge record provenance_hash must be sha256")
    if row.get("split") not in SPLITS:
        raise ValueError("local knowledge record has unsupported split")
    if row.get("confidence") not in CONFIDENCE_VALUES:
        raise ValueError("local knowledge record has unsupported confidence")
    if row.get("extracted_by") != LOCAL_KNOWLEDGE_EXTRACTED_BY:
        raise ValueError("local knowledge record has unsupported extracted_by")

    source = row.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("local knowledge record source must be an object")
    for field_name in ("kind", "repo", "ref", "path", "retrieved_at"):
        if not isinstance(source.get(field_name), str):
            raise ValueError(f"local knowledge source.{field_name} must be a string")

    extractor = row.get("extractor")
    if not isinstance(extractor, Mapping):
        raise ValueError("local knowledge record extractor must be an object")
    if extractor.get("name") != LOCAL_KNOWLEDGE_EXTRACTOR_NAME:
        raise ValueError("local knowledge record extractor.name is unsupported")
    if extractor.get("version") != LOCAL_KNOWLEDGE_EXTRACTOR_VERSION:
        raise ValueError("local knowledge record extractor.version is unsupported")

    links = row.get("links")
    if not isinstance(links, Mapping):
        raise ValueError("local knowledge record links must be an object")
    for field_name in ("task_ids", "outcome_ids", "residual_labels"):
        value = links.get(field_name)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"local knowledge links.{field_name} must be strings")

    if _contains_raw_blob_key(row):
        raise ValueError("local knowledge records must not contain raw source blobs")
    json.dumps(row, sort_keys=True)


def _packaging_layout_record(
    repo: Path,
    context: Mapping[str, str],
    pyproject: Mapping[str, object],
    python_files: Sequence[str],
) -> dict[str, object]:
    source_roots = ["src"] if (repo / "src").is_dir() else ["."]
    package_roots = _package_roots(repo, python_files)
    single_modules = _single_modules(python_files)
    source_paths = ["pyproject.toml"] if (repo / "pyproject.toml").exists() else list(python_files)
    data = {
        "layout_kind": "src" if "src" in source_roots else "flat",
        "source_roots": source_roots,
        "package_roots": package_roots,
        "single_modules": single_modules,
        "build_backend": _nested_str(pyproject, ("build-system", "build-backend")),
        "project_name": _nested_str(pyproject, ("project", "name")),
        "requires_python": _nested_str(pyproject, ("project", "requires-python")),
        "optional_dependency_groups": sorted(
            _nested_mapping(pyproject, ("project", "optional-dependencies")).keys()
        ),
        "editable_install_command": "python -m pip install -e .",
        "config_shape": {
            "pyproject_tables": sorted(pyproject.keys()),
            "has_setup_cfg": (repo / "setup.cfg").exists(),
            "has_setup_py": (repo / "setup.py").exists(),
        },
    }
    return _source_record(
        record_type="packaging_layout_record",
        repo=repo,
        context=context,
        source_kind="repo_config",
        source_path="pyproject.toml" if (repo / "pyproject.toml").exists() else ".",
        provenance_paths=source_paths,
        confidence="observed",
        links={"task_ids": _tests_only_task_ids(()), "outcome_ids": [], "residual_labels": []},
        data=data,
    )


def _pytest_layout_record(
    repo: Path,
    context: Mapping[str, str],
    pyproject: Mapping[str, object],
    pytest_ini: Mapping[str, str],
    test_files: Sequence[str],
) -> dict[str, object]:
    configured_testpaths = _pytest_config_list(pyproject, pytest_ini, "testpaths")
    python_files = _pytest_config_list(pyproject, pytest_ini, "python_files")
    python_functions = _pytest_config_list(pyproject, pytest_ini, "python_functions")
    python_classes = _pytest_config_list(pyproject, pytest_ini, "python_classes")
    test_roots = configured_testpaths or _discovered_test_roots(test_files)
    data = {
        "test_roots": test_roots,
        "naming_patterns": {
            "files": python_files or ["test_*.py", "*_test.py"],
            "functions": python_functions or ["test_*"],
            "classes": python_classes or ["Test*"],
        },
        "config_files": [
            path
            for path in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
            if (repo / path).exists()
        ],
        "import_mode_hints": _import_mode_hints(repo, test_files),
        "adjacent_examples": _test_file_examples(repo, test_files),
    }
    source_path = "pyproject.toml" if (repo / "pyproject.toml").exists() else (
        test_files[0] if test_files else "."
    )
    provenance_paths = [source_path, *test_files[:5]]
    return _source_record(
        record_type="pytest_layout_record",
        repo=repo,
        context=context,
        source_kind="repo_test_tree",
        source_path=source_path,
        provenance_paths=provenance_paths,
        confidence="observed",
        links={"task_ids": _tests_only_task_ids(()), "outcome_ids": [], "residual_labels": []},
        data=data,
    )


def _public_api_records(
    repo: Path,
    context: Mapping[str, str],
    python_files: Sequence[str],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    test_files = tuple(path for path in python_files if _is_test_file(path))
    for path in python_files:
        if _is_test_file(path) or Path(path).name == "conftest.py":
            continue
        if not (path.endswith("__init__.py") or _is_public_single_module(path, python_files)):
            continue
        module = _module_name_from_path(path)
        if not module:
            continue
        tree = _parse_python(repo / path)
        exports = _public_exports(tree)
        data = {
            "module": module,
            "source_path": path,
            "exported_names": exports["exported_names"],
            "explicit_all": exports["explicit_all"],
            "re_export_paths": exports["re_export_paths"],
            "test_import_examples": _test_import_examples(repo, test_files, module),
        }
        records.append(
            _source_record(
                record_type="public_api_record",
                repo=repo,
                context=context,
                source_kind="repo_file",
                source_path=path,
                provenance_paths=[path, *test_files[:3]],
                confidence="observed",
                links={"task_ids": [], "outcome_ids": [], "residual_labels": []},
                data=data,
            )
        )
    return tuple(records)


def _validation_recipe_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    setup_commands: Sequence[str],
    baseline_validation_commands: Sequence[str],
    tasks: Sequence[Mapping[str, object]],
    outcome_ids_by_task: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for task in tasks:
        task_id = _required_str(task, "id")
        commands = _string_sequence(task.get("public_validation_commands", ()))
        if not commands:
            continue
        data = {
            "knowledge_category": "focused_validation_recipe",
            "task_id": task_id,
            "setup_commands": list(setup_commands),
            "baseline_validation_commands": list(baseline_validation_commands),
            "focused_commands": commands,
            "allowed_write_paths": _string_sequence(task.get("allowed_write_paths", ())),
            "required_knowledge_categories": _string_sequence(
                task.get("required_knowledge_categories", ())
            ),
            "network_policy": {
                "setup_network_allowed": True,
                "candidate_validation_network_allowed": False,
            },
            "timeout_seconds": 600,
            "observed_result": "not_run",
        }
        links = {
            "task_ids": [task_id],
            "outcome_ids": list(outcome_ids_by_task.get(task_id, ())),
            "residual_labels": _string_sequence(task.get("expected_failure_modes", ())),
        }
        records.append(
            _source_record(
                record_type="validation_recipe_record",
                repo=repo,
                context=context,
                source_kind="repo_manifest",
                source_path="task:" + task_id,
                provenance_paths=_validation_provenance_paths(repo),
                confidence="inferred",
                links=links,
                data=data,
            )
        )
    return tuple(records)


def _click_changed_file_context_record(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_row: Mapping[str, object],
    changed_files: Sequence[str],
    links: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    source_files = [path for path in changed_files if not _is_test_file(path)]
    test_files = [path for path in changed_files if _is_test_file(path)]
    data = {
        "knowledge_category": "repo_changed_file_context",
        "replay_id": _required_str(replay_row, "id"),
        "issue_pr": _issue_pr_summary(replay_row),
        "changed_files": list(changed_files),
        "source_files": source_files,
        "test_files": test_files,
        "source_context": [
            _python_file_context(repo, path, focus_names=("Option", "Parameter"))
            for path in source_files
        ],
        "test_context": [
            _python_file_context(repo, path, focus_names=("test_", "_StrictEq"))
            for path in test_files
        ],
    }
    return _source_record(
        record_type="repo_changed_file_context_record",
        repo=repo,
        context=context,
        source_kind="accepted_diff_context",
        source_path=",".join(changed_files),
        provenance_paths=[*changed_files, "task:" + _required_str(replay_row, "id")],
        confidence="observed",
        links=links,
        data=data,
    )


def _click_repo_test_pattern_record(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_id: str,
    test_path: str,
    links: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    tree = _parse_python(repo / test_path)
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    default_tests = [
        _function_test_shape(node)
        for node in functions
        if "default" in node.name or _function_uses_click_option(node)
    ]
    data = {
        "knowledge_category": "repo_test_pattern",
        "replay_id": replay_id,
        "test_file": test_path,
        "neighboring_imports": list(_imports(tree)),
        "fixture_arguments": sorted(
            {
                arg.arg
                for node in functions
                for arg in node.args.args
                if arg.arg in {"runner", "isolated_filesystem", "monkeypatch"}
            }
        ),
        "click_assertion_shapes": default_tests[:20],
        "parametrize_shapes": [
            _pytest_pattern_from_function(node, _imports(tree))
            for node in functions
            if _pytest_pattern_from_function(node, _imports(tree)) is not None
        ][:10],
    }
    return _source_record(
        record_type="pytest_pattern_record",
        repo=repo,
        context=context,
        source_kind="repo_file",
        source_path=test_path,
        provenance_paths=[test_path],
        confidence="observed",
        links=links,
        data=data,
    )


def _requests_changed_file_context_record(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_row: Mapping[str, object],
    changed_files: Sequence[str],
    links: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    source_path = _requests_source_path(changed_files)
    test_path = _requests_test_path(changed_files)
    data = {
        "knowledge_category": "repo_changed_file_context",
        "replay_id": _required_str(replay_row, "id"),
        "issue_pr": _issue_pr_summary(replay_row),
        "changed_files": list(changed_files),
        "source_files": [source_path],
        "test_files": [test_path],
        "source_context": _requests_models_semantic_context(repo / source_path),
        "test_context": _requests_test_semantic_context(repo / test_path),
    }
    return _source_record(
        record_type="repo_changed_file_context_record",
        repo=repo,
        context=context,
        source_kind="accepted_diff_context",
        source_path=",".join(changed_files),
        provenance_paths=[*changed_files, "task:" + _required_str(replay_row, "id")],
        confidence="observed",
        links=links,
        data=data,
    )


def _click_library_idiom_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_id: str,
    prompt_source: Mapping[str, object],
    changed_files: Sequence[str],
    validation_command: str,
    links: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    source_path = _click_source_path(changed_files)
    test_path = _click_test_path(changed_files)
    core_context = _click_core_semantic_context(repo / source_path)
    test_context = _click_option_test_context(repo / test_path)
    base = {
        "replay_id": replay_id,
        "target_source_path": source_path,
        "target_test_path": test_path,
        "validation_command": validation_command,
    }
    rows = [
        {
            **base,
            "knowledge_category": "click_parameter_default_handling",
            "problem_label": "click_option_help_default_rendering",
            "behavior_facts": [
                "Option help rendering asks get_default with call=False before formatting default text.",
                "show_default may be option-local, context-level, or a literal display string.",
                "default values flow into help formatting before stringification.",
            ],
            "source_evidence": {
                "methods": _pick_methods(
                    core_context,
                    ["Option.get_help_extra", "Option.get_default", "Parameter.consume_value"],
                ),
                "default_value_branches": core_context["default_value_branches"],
            },
            "test_evidence": {
                "default_help_tests": test_context["default_help_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "click_type_conversion_semantics",
            "problem_label": "click_parameter_type_cast_pipeline",
            "behavior_facts": [
                "Parameter.process_value is the layer that shields type_cast_value from UNSET.",
                "type_cast_value applies the parameter type and handles multiple or nargs shapes.",
                "value_is_missing treats UNSET and empty multi-value tuples as missing.",
            ],
            "source_evidence": {
                "methods": _pick_methods(
                    core_context,
                    [
                        "Parameter.type_cast_value",
                        "Parameter.process_value",
                        "Parameter.value_is_missing",
                    ],
                ),
                "type_cast_call_shapes": core_context["type_cast_call_shapes"],
            },
            "test_evidence": {
                "option_default_tests": test_context["default_help_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "click_non_string_default_handling",
            "problem_label": "non_string_default_help_rendering",
            "behavior_facts": [
                "Non-string default objects can reach Option.get_help_extra.",
                "String-specific empty checks must be guarded before comparing with arbitrary objects.",
                "Fallback rendering uses str(default_value) for objects not handled by earlier branches.",
            ],
            "source_evidence": {
                "methods": _pick_methods(core_context, ["Option.get_help_extra"]),
                "empty_string_comparison": core_context["empty_string_comparison"],
            },
            "test_evidence": {
                "strict_equality_reproduction_shape": test_context[
                    "strict_equality_reproduction_shape"
                ],
            },
        },
        {
            **base,
            "knowledge_category": "click_empty_string_check_semantics",
            "problem_label": "empty_string_default_display",
            "behavior_facts": [
                "An empty string default is a real displayable default for help output.",
                "The displayed help value for an empty string default is a quoted empty string.",
                "The empty-string branch must not classify unrelated non-string defaults.",
            ],
            "source_evidence": {
                "methods": _pick_methods(core_context, ["Option.get_help_extra"]),
                "empty_string_comparison": core_context["empty_string_comparison"],
            },
            "test_evidence": {
                "empty_string_tests": test_context["empty_string_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "third_party_semver_version_reproduction",
            "problem_label": "semver_version_default_comparison",
            "behavior_facts": [
                "The replay issue reports semver.Version as the non-string default object.",
                "The accepted regression shape can be reproduced with an object whose equality rejects string operands.",
                "The candidate should not require semver as a hard test dependency when a local strict-equality double captures the same comparison failure.",
            ],
            "issue_pr": {
                "issue_number": prompt_source.get("issue_number"),
                "issue_title": prompt_source.get("issue_title"),
                "issue_url": prompt_source.get("issue_url"),
                "pull_request_number": prompt_source.get("pull_request_number"),
                "pull_request_url": prompt_source.get("pull_request_url"),
            },
            "test_evidence": {
                "strict_equality_reproduction_shape": test_context[
                    "strict_equality_reproduction_shape"
                ],
            },
        },
    ]
    return tuple(
        _source_record(
            record_type="library_idiom_record",
            repo=repo,
            context=context,
            source_kind="repo_file",
            source_path=source_path if row["knowledge_category"].startswith("click_") else test_path,
            provenance_paths=[source_path, test_path, "task:" + replay_id],
            confidence="observed",
            links=links,
            data=row,
        )
        for row in rows
    )


def _requests_library_idiom_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_id: str,
    prompt_source: Mapping[str, object],
    changed_files: Sequence[str],
    manifest_validation_command: str,
    focused_validation_command: str,
    links: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    source_path = _requests_source_path(changed_files)
    test_path = _requests_test_path(changed_files)
    models_context = _requests_models_semantic_context(repo / source_path)
    test_context = _requests_test_semantic_context(repo / test_path)
    redirect_context = _requests_redirect_semantic_context(repo)
    fixture_context = _requests_fixture_context(repo)
    base = {
        "replay_id": replay_id,
        "target_source_path": source_path,
        "target_test_path": test_path,
        "manifest_validation_command": manifest_validation_command,
        "focused_validation_command": focused_validation_command,
    }
    rows = [
        {
            **base,
            "knowledge_category": "requests_prepare_body_stream_detection",
            "problem_label": "prepare_body_attribute_proxy_stream_detection",
            "behavior_facts": [
                "PreparedRequest.prepare_body separates streamed bodies from raw data before encoding parameters.",
                "Streamed bodies get super_len detection, body position recording through tell, and either Content-Length or Transfer-Encoding.",
                "The accepted fix treats objects that expose __iter__ via attribute proxying as streams, not form data.",
            ],
            "source_evidence": {
                "methods": _pick_methods(
                    models_context,
                    ["PreparedRequest.prepare_body", "PreparedRequest.prepare_content_length"],
                ),
                "stream_detection": models_context["stream_detection"],
                "body_position_tracking": models_context["body_position_tracking"],
                "header_effects": models_context["header_effects"],
            },
        },
        {
            **base,
            "knowledge_category": "requests_getattr_file_wrapper_behavior",
            "problem_label": "file_wrapper_dunder_iter_via_getattr",
            "behavior_facts": [
                "The issue-specific wrapper delegates file methods through __getattr__ instead of defining __iter__ directly.",
                "A candidate should cover this with a local wrapper around io.BytesIO and a 307 redirect POST.",
                "The future accepted test is named test_getattr_proxy_stream_follows_redirect.",
            ],
            "issue_pr": {
                "issue_number": prompt_source.get("issue_number"),
                "issue_title": prompt_source.get("issue_title"),
                "issue_url": prompt_source.get("issue_url"),
                "pull_request_number": prompt_source.get("pull_request_number"),
                "pull_request_url": prompt_source.get("pull_request_url"),
            },
            "source_evidence": {
                "stream_detection": models_context["stream_detection"],
            },
            "test_evidence": {
                "expected_new_test": {
                    "name": "test_getattr_proxy_stream_follows_redirect",
                    "fixture_arguments": ["httpbin"],
                    "local_class_methods": ["__getattr__"],
                    "request_shape": "requests.post(httpbin('redirect-to?url=/post&status_code=307'), data=AttrProxy())",
                    "assertion_shape": "response json data echoes uploaded bytes",
                },
                "neighbor_rewind_tests": test_context["rewind_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "requests_redirect_rewind_body_semantics",
            "problem_label": "redirect_reuses_stream_body_after_307",
            "behavior_facts": [
                "Redirect handling rewinds a prepared request body only when _body_position is not None and a length or transfer header marks the body as resendable.",
                "requests.utils.rewind_body seeks to the recorded integer body position and raises UnrewindableBodyError otherwise.",
                "The issue regression is observable on redirects because a misclassified wrapper is not rewound and resent as the original bytes.",
            ],
            "source_evidence": redirect_context,
            "test_evidence": {
                "manual_redirect_tests": test_context["redirect_tests"],
                "rewind_tests": test_context["rewind_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "requests_pytest_httpbin_fixture_setup",
            "problem_label": "pytest_httpbin_fixture_dependencies",
            "behavior_facts": [
                "Requests wraps pytest-httpbin's httpbin and httpbin_secure fixtures in tests/conftest.py to normalize URL construction.",
                "DATA-008 proved the focused replay recipe needs pytest-httpbin==2.1.0, httpbin~=0.10.0, and trustme in the checkout venv.",
                "The focused command uses a -k selector so repo-before passes and the accepted issue-specific test is selected once present.",
            ],
            "fixture_evidence": fixture_context,
            "validation_evidence": {
                "setup_command": (
                    "python -m venv .venv && .venv/bin/python -m pip install -q "
                    "--upgrade pip setuptools wheel && .venv/bin/python -m pip "
                    "install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme"
                ),
                "focused_command": focused_validation_command,
                "repo_before_smoke": "5 passed, 333 deselected",
                "accepted_merge_smoke": "6 passed, 333 deselected",
            },
        },
        {
            **base,
            "knowledge_category": "requests_ranking_changed_test_patterns",
            "problem_label": "rank_stream_predicate_and_redirect_test_over_encoding_decoys",
            "behavior_facts": [
                "Ranking should prefer a bounded prepare_body stream predicate edit in src/requests/models.py.",
                "Changed tests live in TestRequests near rewind_body coverage and use requests.post plus httpbin redirect helpers.",
                "Candidates that only edit form encoding, content length for raw bytes, or broad redirect history behavior miss the issue-specific wrapper shape.",
            ],
            "source_evidence": {
                "accepted_change_shape": {
                    "source_file": source_path,
                    "changed_function": "PreparedRequest.prepare_body",
                    "predicate_keywords": ["Iterable", "hasattr", "__iter__", "Mapping"],
                },
                "method_calls": _pick_methods(
                    models_context,
                    ["PreparedRequest.prepare_body"],
                ),
            },
            "test_evidence": {
                "target_test_class": "TestRequests",
                "future_test_name": "test_getattr_proxy_stream_follows_redirect",
                "neighboring_test_names": [
                    item["name"] for item in test_context["rewind_tests"]
                ],
                "httpbin_fixture_required": "httpbin",
            },
        },
    ]
    return tuple(
        _source_record(
            record_type=(
                "pytest_pattern_record"
                if row["knowledge_category"] == "requests_ranking_changed_test_patterns"
                else "library_idiom_record"
            ),
            repo=repo,
            context=context,
            source_kind="repo_file",
            source_path=(
                "tests/conftest.py"
                if row["knowledge_category"] == "requests_pytest_httpbin_fixture_setup"
                else test_path
                if row["knowledge_category"] in {
                    "requests_getattr_file_wrapper_behavior",
                    "requests_ranking_changed_test_patterns",
                }
                else source_path
            ),
            provenance_paths=_requests_idiom_provenance_paths(
                repo,
                row["knowledge_category"],
                source_path=source_path,
                test_path=test_path,
                replay_id=replay_id,
            ),
            confidence="observed",
            links=links,
            data=row,
        )
        for row in rows
    )


def _pytest_strict_changed_file_context_record(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_row: Mapping[str, object],
    changed_files: Sequence[str],
    links: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    python_files = [path for path in changed_files if path.endswith(".py")]
    source_files = [path for path in python_files if not _is_test_file(path)]
    test_files = [path for path in python_files if _is_test_file(path)]
    auxiliary_files = [path for path in changed_files if path not in python_files]
    data = {
        "knowledge_category": "repo_changed_file_context",
        "replay_id": _required_str(replay_row, "id"),
        "issue_pr": _issue_pr_summary(replay_row),
        "changed_files": list(changed_files),
        "source_files": source_files,
        "test_files": test_files,
        "auxiliary_files": auxiliary_files,
        "source_context": [
            _python_file_context(repo, path, focus_names=("Config",))
            for path in source_files
        ],
        "test_context": [
            _python_file_context(
                repo,
                path,
                focus_names=("test_", "TestParseIni", "TestInvocationVariants"),
            )
            for path in test_files
        ],
        "auxiliary_context": [
            _pytest_auxiliary_file_context(repo, path) for path in auxiliary_files
        ],
    }
    return _source_record(
        record_type="repo_changed_file_context_record",
        repo=repo,
        context=context,
        source_kind="accepted_diff_context",
        source_path=",".join(changed_files),
        provenance_paths=[*changed_files, "task:" + _required_str(replay_row, "id")],
        confidence="observed",
        links=links,
        data=data,
    )


def _pytest_approx_changed_file_context_record(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_row: Mapping[str, object],
    changed_files: Sequence[str],
    links: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    python_files = [path for path in changed_files if path.endswith(".py")]
    source_files = [path for path in python_files if not _is_test_file(path)]
    test_files = [path for path in python_files if _is_test_file(path)]
    data = {
        "knowledge_category": "repo_changed_file_context",
        "replay_id": _required_str(replay_row, "id"),
        "issue_pr": _issue_pr_summary(replay_row),
        "changed_files": list(changed_files),
        "source_files": source_files,
        "test_files": test_files,
        "auxiliary_files": [path for path in changed_files if path not in python_files],
        "source_context": [
            _python_file_context(
                repo,
                path,
                focus_names=("ApproxTimedelta", "ApproxBase", "ApproxScalar", "approx"),
            )
            for path in source_files
        ],
        "test_context": [
            _python_file_context(
                repo,
                path,
                focus_names=("TestApproxDatetime", "test_timedelta", "test_datetime"),
            )
            for path in test_files
        ],
    }
    return _source_record(
        record_type="repo_changed_file_context_record",
        repo=repo,
        context=context,
        source_kind="accepted_diff_context",
        source_path=",".join(changed_files),
        provenance_paths=[*changed_files, "task:" + _required_str(replay_row, "id")],
        confidence="observed",
        links=links,
        data=data,
    )


def _scrapy_changed_file_context_record(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_row: Mapping[str, object],
    changed_files: Sequence[str],
    links: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    python_files = [path for path in changed_files if path.endswith(".py")]
    source_files = [path for path in python_files if not _is_test_file(path)]
    test_files = [path for path in python_files if _is_test_file(path)]
    data = {
        "knowledge_category": "repo_changed_file_context",
        "replay_id": _required_str(replay_row, "id"),
        "issue_pr": _issue_pr_summary(replay_row),
        "changed_files": list(changed_files),
        "source_files": source_files,
        "test_files": test_files,
        "auxiliary_files": [path for path in changed_files if path not in python_files],
        "source_context": [
            _python_file_context(
                repo,
                path,
                focus_names=(
                    "DownloaderInterface",
                    "DownloaderAwarePriorityQueue",
                    "ScrapyPriorityQueue",
                ),
            )
            for path in source_files
        ],
        "test_context": [
            _python_file_context(
                repo,
                path,
                focus_names=("TestDownloaderAwarePriorityQueue", "test_"),
            )
            for path in test_files
        ],
    }
    return _source_record(
        record_type="repo_changed_file_context_record",
        repo=repo,
        context=context,
        source_kind="accepted_diff_context",
        source_path=",".join(changed_files),
        provenance_paths=[*changed_files, "task:" + _required_str(replay_row, "id")],
        confidence="observed",
        links=links,
        data=data,
    )


def _pytest_strict_idiom_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_id: str,
    prompt_source: Mapping[str, object],
    changed_files: Sequence[str],
    focused_validation_command: str,
    links: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    source_path = _pytest_config_source_path(changed_files)
    config_test_path = "testing/test_config.py"
    mark_test_path = "testing/test_mark.py"
    config_context = _pytest_config_semantic_context(repo / source_path)
    test_context = _pytest_strict_test_context(repo, config_test_path, mark_test_path)
    base = {
        "replay_id": replay_id,
        "target_source_path": source_path,
        "target_test_files": [config_test_path, mark_test_path],
        "focused_validation_command": focused_validation_command,
    }
    rows = [
        {
            **base,
            "knowledge_category": "pytest_strict_addopts_behavior",
            "problem_label": "strict_options_from_addopts_ignored",
            "behavior_facts": [
                "Config.parse prepends validated PYTEST_ADDOPTS before setup discovery.",
                "Config.parse registers addopts after setup discovery, then prepends validated ini addopts before known-args parsing.",
                "Strict options supplied through addopts must affect the same known-args and ini-cache state as command-line strict options.",
                "The accepted change performs one post-addopts override-ini update and clears the ini cache; it is not an unbounded recursive addopts expansion.",
            ],
            "source_evidence": {
                "methods": _pick_methods(config_context, ["Config.parse"]),
                "parse_flow": config_context["parse_flow"],
                "override_ini_handling": config_context["override_ini_handling"],
            },
            "test_evidence": {
                "strict_config_tests": test_context["strict_config_tests"],
                "strict_mark_tests": test_context["strict_mark_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "pytest_strict_markers_config_semantics",
            "problem_label": "strict_config_and_marker_semantics",
            "behavior_facts": [
                "strict_config and legacy strict turn unknown config option warnings into UsageError.",
                "--strict-markers, --strict, strict_markers, and strict prohibit unregistered markers.",
                "The regression-specific behavior is the addopts delivery path, not a new strictness policy.",
            ],
            "issue_pr": {
                "issue_number": prompt_source.get("issue_number"),
                "issue_title": prompt_source.get("issue_title"),
                "issue_url": prompt_source.get("issue_url"),
                "pull_request_number": prompt_source.get("pull_request_number"),
                "pull_request_url": prompt_source.get("pull_request_url"),
            },
            "source_evidence": {
                "methods": _pick_methods(
                    config_context,
                    ["Config._warn_or_fail_if_strict", "Config.parse"],
                ),
                "strict_ini_gets": config_context["strict_ini_gets"],
                "unknown_ini_check": config_context["unknown_ini_check"],
            },
            "test_evidence": {
                "strict_config_tests": test_context["strict_config_tests"],
                "strict_mark_tests": test_context["strict_mark_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "pytest_repo_test_patterns",
            "problem_label": "pytester_strict_option_regression_tests",
            "behavior_facts": [
                "Config parser tests use Pytester.makeini, runpytest, stderr/stdout fnmatch_lines, and ExitCode assertions.",
                "Marker strictness tests use Pytester.makepyfile plus either direct CLI options or ini-driven addopts cases.",
                "The focused validation command runs only testing/test_config.py and testing/test_mark.py.",
            ],
            "test_evidence": test_context,
        },
        {
            **base,
            "knowledge_category": "pytest_changelog_fragment_convention",
            "problem_label": "pytest_changelog_bugfix_fragment",
            "behavior_facts": [
                "Pytest bugfix news entries are stored as changelog/<issue>.bugfix.rst fragments.",
                "The accepted PR adds changelog/14442.bugfix.rst as an auxiliary file.",
                "A source/test-only candidate attempt should record this auxiliary path as deferred unless a changelog materializer is in scope.",
            ],
            "changelog_evidence": _pytest_changelog_context(
                repo,
                target_path="changelog/14442.bugfix.rst",
            ),
        },
        {
            **base,
            "knowledge_category": "pytest_authors_convention",
            "problem_label": "pytest_authors_contributor_entry",
            "behavior_facts": [
                "AUTHORS is a newline-delimited contributor list maintained as a repository auxiliary file.",
                "The accepted PR adds the contributor name for this replay row.",
                "A source/test-only candidate attempt should record AUTHORS as deferred unless auxiliary authors materialization is in scope.",
            ],
            "authors_evidence": _pytest_authors_context(
                repo,
                expected_new_entry="Praneeth Kodumagulla",
            ),
        },
    ]
    return tuple(
        _source_record(
            record_type=(
                "pytest_pattern_record"
                if row["knowledge_category"] == "pytest_repo_test_patterns"
                else "library_idiom_record"
            ),
            repo=repo,
            context=context,
            source_kind="repo_file",
            source_path=_pytest_idiom_source_path(row["knowledge_category"], source_path),
            provenance_paths=_pytest_idiom_provenance_paths(
                repo,
                row["knowledge_category"],
                source_path=source_path,
                config_test_path=config_test_path,
                mark_test_path=mark_test_path,
                replay_id=replay_id,
            ),
            confidence="observed",
            links=links,
            data=row,
        )
        for row in rows
    )


def _pytest_approx_idiom_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_id: str,
    prompt_source: Mapping[str, object],
    changed_files: Sequence[str],
    focused_validation_command: str,
    links: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    source_path = _pytest_approx_source_path(changed_files)
    test_path = _pytest_approx_test_path(changed_files)
    source_context = _pytest_approx_semantic_context(repo / source_path)
    test_context = _pytest_approx_test_context(repo / test_path)
    base = {
        "replay_id": replay_id,
        "target_source_path": source_path,
        "target_test_files": [test_path],
        "focused_validation_command": focused_validation_command,
    }
    rows = [
        {
            **base,
            "knowledge_category": "pytest_approx_timedelta_tolerance_semantics",
            "problem_label": "timedelta_rel_treated_as_absolute_tolerance",
            "behavior_facts": [
                "ApproxScalar computes relative tolerance as rel * abs(expected).",
                "Repo-before ApproxTimedelta requires rel to be a timedelta and then stores max(abs, rel) as an absolute tolerance.",
                "Accepted behavior makes timedelta rel a numeric fraction and computes rel * abs(expected).",
                "When abs and rel are both provided, the effective timedelta tolerance is the larger of abs and the scaled relative tolerance.",
            ],
            "source_evidence": {
                "methods": _pick_methods(
                    source_context,
                    [
                        "ApproxTimedelta.__init__",
                        "ApproxTimedelta.__eq__",
                        "ApproxScalar.tolerance",
                    ],
                ),
                "timedelta_constructor": source_context["timedelta_constructor"],
                "scalar_tolerance": source_context["scalar_tolerance"],
            },
            "test_evidence": {
                "timedelta_tests": test_context["timedelta_tests"],
                "target_future_tests": [
                    "test_timedelta_rel_within_tolerance",
                    "test_timedelta_rel_outside_tolerance",
                    "test_timedelta_rel_scales_with_expected",
                    "test_timedelta_rel_must_be_number",
                ],
            },
        },
        {
            **base,
            "knowledge_category": "pytest_datetime_timedelta_comparison_behavior",
            "problem_label": "datetime_and_timedelta_approx_policy",
            "behavior_facts": [
                "datetime comparisons require abs=timedelta(...) and reject rel.",
                "timedelta comparisons support abs=timedelta(...) and should support numeric rel fractions.",
                "nan_ok is rejected for datetime/timedelta comparisons.",
                "Incompatible actual values compare False rather than leaking TypeError.",
            ],
            "issue_pr": {
                "issue_number": prompt_source.get("issue_number"),
                "issue_title": prompt_source.get("issue_title"),
                "issue_url": prompt_source.get("issue_url"),
                "pull_request_number": prompt_source.get("pull_request_number"),
                "pull_request_url": prompt_source.get("pull_request_url"),
            },
            "source_evidence": {
                "methods": _pick_methods(
                    source_context,
                    [
                        "ApproxTimedelta.__init__",
                        "ApproxTimedelta.__eq__",
                        "ApproxTimedelta._repr_compare",
                    ],
                ),
                "timedelta_constructor": source_context["timedelta_constructor"],
            },
            "test_evidence": {
                "datetime_tests": test_context["datetime_tests"],
                "timedelta_tests": test_context["timedelta_tests"],
            },
        },
        {
            **base,
            "knowledge_category": "pytest_repo_test_patterns",
            "problem_label": "pytest_approx_datetime_timedelta_tests",
            "behavior_facts": [
                "Approx tests live in testing/python/approx.py under TestApproxDatetime.",
                "Tests import datetime and timedelta locally inside each test method.",
                "Existing patterns use direct equality, inequality, pytest.raises, and repr assertions.",
                "Optional numpy coverage is skipped with pytest.importorskip, so focused validation may report skipped tests.",
            ],
            "test_evidence": test_context,
        },
        {
            **base,
            "knowledge_category": "pytest_timedelta_approx_readiness_blockers",
            "problem_label": "candidate_readiness_remaining_gaps",
            "behavior_facts": [
                "DATA-018 proved checkout, editable install, and focused baseline validation pass.",
                "The row still has materialization_gap and ranking_gap residual labels after evidence acquisition.",
                "Accepted changed paths are only src/_pytest/python_api.py and testing/python/approx.py; no auxiliary file materializer is required for this row.",
                "A future candidate attempt must materialize source dispatch/tolerance edits and focused tests before readiness can be scored.",
            ],
            "validation_evidence": {
                "data_018_command": focused_validation_command,
                "data_018_result": "102 passed, 18 skipped in 0.15s",
                "setup_command": "python -m pip install -e . pytest",
            },
            "remaining_residual_labels": ["materialization_gap", "ranking_gap"],
            "candidate_scope": {
                "source_paths": [source_path],
                "test_paths": [test_path],
                "auxiliary_paths": [],
            },
        },
    ]
    return tuple(
        _source_record(
            record_type=(
                "pytest_pattern_record"
                if row["knowledge_category"] == "pytest_repo_test_patterns"
                else "library_idiom_record"
            ),
            repo=repo,
            context=context,
            source_kind="repo_file",
            source_path=(
                test_path
                if row["knowledge_category"] == "pytest_repo_test_patterns"
                else source_path
            ),
            provenance_paths=[source_path, test_path, "task:" + replay_id],
            confidence="observed",
            links=links,
            data=row,
        )
        for row in rows
    )


def _scrapy_downloader_aware_idiom_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    replay_id: str,
    prompt_source: Mapping[str, object],
    changed_files: Sequence[str],
    focused_validation_command: str,
    links: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    source_path = _scrapy_pqueue_source_path(changed_files)
    test_path = _scrapy_pqueue_test_path(changed_files)
    source_context = _scrapy_pqueue_semantic_context(repo / source_path)
    test_context = _scrapy_pqueue_test_context(repo / test_path)
    base = {
        "replay_id": replay_id,
        "target_source_path": source_path,
        "target_test_files": [test_path],
        "focused_validation_command": focused_validation_command,
    }
    rows = [
        {
            **base,
            "knowledge_category": "scrapy_downloader_aware_priority_queue",
            "problem_label": "equal_active_slot_tie_breaking_starves_later_slots",
            "behavior_facts": [
                "DownloaderAwarePriorityQueue keeps one ScrapyPriorityQueue per downloader slot.",
                "DownloaderInterface.stats returns (active_download_count, slot) tuples for queued slots.",
                "Repo-before pop and peek select min(stats)[1], so ties are broken by slot name.",
                "Accepted behavior adds last-selected-slot state and rotates among slots with equal active counts.",
                "peek must compute the same selected slot without mutating last-selected-slot state.",
            ],
            "source_evidence": {
                "methods": _pick_methods(
                    source_context,
                    [
                        "DownloaderAwarePriorityQueue.pop",
                        "DownloaderAwarePriorityQueue.peek",
                        "DownloaderAwarePriorityQueue.push",
                        "DownloaderAwarePriorityQueue.__init__",
                    ],
                ),
                "slot_selection": source_context["slot_selection"],
                "queue_lifecycle": source_context["queue_lifecycle"],
            },
            "test_evidence": {
                "downloader_aware_tests": test_context["downloader_aware_tests"],
                "future_tie_breaking_tests": [
                    "test_tie_breaking_rotates_slots",
                    "test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted",
                ],
            },
        },
        {
            **base,
            "knowledge_category": "scrapy_slot_active_download_accounting",
            "problem_label": "slot_active_download_count_used_as_queue_score",
            "behavior_facts": [
                "DownloaderInterface._active_downloads returns 0 for slots absent from downloader.slots.",
                "For present slots, _active_downloads returns len(downloader.slots[slot].active).",
                "The scheduling score is still the active-download count; the bug is tie ordering among equal scores.",
                "Request slots are assigned through request.meta[Downloader.DOWNLOAD_SLOT] when present.",
            ],
            "issue_pr": {
                "issue_number": prompt_source.get("issue_number"),
                "issue_title": prompt_source.get("issue_title"),
                "issue_url": prompt_source.get("issue_url"),
                "pull_request_number": prompt_source.get("pull_request_number"),
                "pull_request_url": prompt_source.get("pull_request_url"),
            },
            "source_evidence": {
                "methods": _pick_methods(
                    source_context,
                    [
                        "DownloaderInterface.stats",
                        "DownloaderInterface._active_downloads",
                        "DownloaderInterface.get_slot_key",
                    ],
                ),
                "active_downloads": source_context["active_downloads"],
            },
            "test_evidence": {
                "mock_downloader_import": test_context["mock_downloader_import"],
                "slot_meta_key_import": test_context["slot_meta_key_import"],
            },
        },
        {
            **base,
            "knowledge_category": "scrapy_pqueue_test_patterns",
            "problem_label": "scrapy_pqueue_queue_ordering_tests",
            "behavior_facts": [
                "tests/test_pqueues.py uses get_crawler(Spider), MockDownloader, FifoMemoryQueue, and Request objects.",
                "Downloader-aware queue tests live on TestDownloaderAwarePriorityQueue.",
                "The accepted tests assert popped request URL or Downloader.DOWNLOAD_SLOT sequence directly.",
                "The focused validation command runs only tests/test_pqueues.py.",
            ],
            "test_evidence": test_context,
        },
        {
            **base,
            "knowledge_category": "scrapy_pqueue_readiness_blockers",
            "problem_label": "candidate_readiness_remaining_gaps",
            "behavior_facts": [
                "DATA-030 proved checkout, editable install, and focused baseline validation pass for the Scrapy row.",
                "Prompt/spec and local-knowledge evidence are now available, but candidate materialization and ranking remain deferred.",
                "Accepted changed paths are only scrapy/pqueues.py and tests/test_pqueues.py; no auxiliary materializer is required.",
                "A future candidate attempt must materialize the slot-rotation source edit and the focused pqueue tests before readiness can be scored.",
            ],
            "validation_evidence": {
                "data_030_command": focused_validation_command,
                "data_030_result": "11 passed, 2 skipped, 2 warnings in 0.20s",
                "setup_command": "python -m pip install -e .",
            },
            "remaining_residual_labels": ["materialization_gap", "ranking_gap"],
            "candidate_scope": {
                "source_paths": [source_path],
                "test_paths": [test_path],
                "auxiliary_paths": [],
            },
        },
    ]
    return tuple(
        _source_record(
            record_type=(
                "pytest_pattern_record"
                if row["knowledge_category"] == "scrapy_pqueue_test_patterns"
                else "library_idiom_record"
            ),
            repo=repo,
            context=context,
            source_kind="repo_file",
            source_path=(
                test_path
                if row["knowledge_category"] == "scrapy_pqueue_test_patterns"
                else source_path
            ),
            provenance_paths=[source_path, test_path, "task:" + replay_id],
            confidence="observed",
            links=links,
            data=row,
        )
        for row in rows
    )


def _pytest_pattern_records(
    repo: Path,
    context: Mapping[str, str],
    test_files: Sequence[str],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for path in test_files:
        tree = _parse_python(repo / path)
        imports = _imports(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            pattern = _pytest_pattern_from_function(node, imports)
            if pattern is None:
                continue
            pattern["source_path"] = path
            records.append(
                _source_record(
                    record_type="pytest_pattern_record",
                    repo=repo,
                    context=context,
                    source_kind="repo_file",
                    source_path=path,
                    provenance_paths=[path],
                    confidence="observed",
                    links={"task_ids": [], "outcome_ids": [], "residual_labels": []},
                    data=pattern,
                )
            )
    return tuple(records)


def _pytest_pattern_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    imports: Sequence[Mapping[str, str]],
) -> dict[str, object] | None:
    decorators = [_call_name(decorator) for decorator in node.decorator_list]
    tools = sorted(_pytest_tools(node))
    pattern_kind = None
    parametrize_shape: dict[str, object] | None = None
    if any(name.endswith("parametrize") for name in decorators):
        pattern_kind = "parametrize"
        parametrize_shape = _parametrize_shape(node.decorator_list)
    elif any(name.endswith("fixture") for name in decorators):
        pattern_kind = "fixture"
    elif any(tool.startswith("pytest.raises") for tool in tools):
        pattern_kind = "exception_assertion"
    elif any(tool.startswith("monkeypatch.") for tool in tools) or any(
        arg.arg == "monkeypatch" for arg in node.args.args
    ):
        pattern_kind = "monkeypatch"

    if pattern_kind is None:
        return None
    return {
        "pattern_kind": pattern_kind,
        "function_name": node.name,
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "decorator_shape": {
            "names": decorators,
            "parametrize": parametrize_shape,
        },
        "argument_names": [arg.arg for arg in node.args.args],
        "pytest_tools": tools,
        "neighboring_imports": list(imports),
    }


def _source_record(
    *,
    record_type: str,
    repo: Path,
    context: Mapping[str, str],
    source_kind: str,
    source_path: str,
    provenance_paths: Sequence[str],
    confidence: str,
    links: Mapping[str, Sequence[str]],
    data: Mapping[str, object],
) -> dict[str, object]:
    source = {
        "kind": source_kind,
        "repo": context["repo_id"],
        "ref": context["repo_ref"],
        "path": source_path,
        "url": context["repo_url"],
        "license": context["license"],
        "retrieved_at": context["retrieved_at"],
    }
    return _record(
        record_type=record_type,
        source=source,
        split=context["split"],
        provenance_hash=_provenance_hash(repo, provenance_paths),
        confidence=confidence,
        links={
            "task_ids": list(links.get("task_ids", ())),
            "outcome_ids": list(links.get("outcome_ids", ())),
            "residual_labels": list(links.get("residual_labels", ())),
        },
        data=data,
    )


def _record(
    *,
    record_type: str,
    source: Mapping[str, str],
    split: str,
    provenance_hash: str,
    confidence: str,
    links: Mapping[str, Sequence[str]],
    data: Mapping[str, object],
) -> dict[str, object]:
    payload = {
        "record_type": record_type,
        "source": dict(source),
        "split": split,
        "provenance_hash": provenance_hash,
        "confidence": confidence,
        "links": {
            "task_ids": list(links.get("task_ids", ())),
            "outcome_ids": list(links.get("outcome_ids", ())),
            "residual_labels": list(links.get("residual_labels", ())),
        },
        "data": _json_copy(data),
    }
    record_id = _sha256_json(payload)
    row = {
        "schema_version": LOCAL_KNOWLEDGE_SCHEMA_VERSION,
        "id": record_id,
        "extracted_by": LOCAL_KNOWLEDGE_EXTRACTED_BY,
        "extractor": {
            "name": LOCAL_KNOWLEDGE_EXTRACTOR_NAME,
            "version": LOCAL_KNOWLEDGE_EXTRACTOR_VERSION,
        },
        **payload,
    }
    return row


def _load_pyproject(repo: Path) -> Mapping[str, object]:
    path = repo / "pyproject.toml"
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_pytest_ini(repo: Path) -> Mapping[str, str]:
    for name in ("pytest.ini", "tox.ini", "setup.cfg"):
        path = repo / name
        if not path.exists():
            continue
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        section = "tool:pytest" if name == "setup.cfg" else "pytest"
        if parser.has_section(section):
            return dict(parser.items(section))
    return {}


def _python_files(repo: Path) -> tuple[str, ...]:
    files = []
    for path in repo.rglob("*.py"):
        if any(part.startswith(".") or part in {"__pycache__", ".tox", "build", "dist"} for part in path.parts):
            continue
        files.append(_relative_path(repo, path))
    return tuple(sorted(files))


def _package_roots(repo: Path, python_files: Sequence[str]) -> list[dict[str, str]]:
    roots = []
    for path in python_files:
        if not path.endswith("__init__.py"):
            continue
        package_path = path.removesuffix("/__init__.py")
        module_path = package_path.removeprefix("src/")
        roots.append(
            {
                "package": module_path.replace("/", "."),
                "path": package_path,
                "source_root": "src" if package_path.startswith("src/") else ".",
            }
        )
    return sorted(roots, key=lambda item: item["package"])


def _single_modules(python_files: Sequence[str]) -> list[dict[str, str]]:
    modules = []
    for path in python_files:
        parts = PurePosixPath(path).parts
        if len(parts) != 1 or path in {"setup.py", "conftest.py"}:
            continue
        name = Path(path).stem
        if not name.startswith("test_") and name != "__init__":
            modules.append({"module": name, "path": path})
    return sorted(modules, key=lambda item: item["module"])


def _is_public_single_module(path: str, python_files: Sequence[str]) -> bool:
    parts = PurePosixPath(path).parts
    if len(parts) != 1 or path in {"setup.py", "conftest.py"}:
        return False
    if Path(path).stem.startswith("test_"):
        return False
    return not any(file.endswith("__init__.py") for file in python_files)


def _module_name_from_path(path: str) -> str:
    if path.endswith("/__init__.py"):
        return path.removesuffix("/__init__.py").removeprefix("src/").replace("/", ".")
    if path.endswith(".py"):
        return path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    return ""


def _public_exports(tree: ast.Module) -> dict[str, object]:
    explicit_all: list[str] = []
    exported_names: set[str] = set()
    re_export_paths: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "__all__" in targets:
                explicit_all = _string_literal_sequence(node.value)
                exported_names.update(explicit_all)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exported_names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                if not name.startswith("_"):
                    exported_names.add(name)
                    re_export_paths.append({"name": name, "from": module})
    return {
        "explicit_all": explicit_all,
        "exported_names": sorted(exported_names),
        "re_export_paths": sorted(re_export_paths, key=lambda item: item["name"]),
    }


def _test_import_examples(
    repo: Path,
    test_files: Sequence[str],
    module: str,
) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    for path in test_files:
        tree = _parse_python(repo / path)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == module or alias.name.startswith(f"{module}."):
                        examples.append({"path": path, "import": alias.name, "kind": "import"})
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == module or node.module.startswith(f"{module}."):
                    examples.append(
                        {
                            "path": path,
                            "import": node.module,
                            "names": [alias.asname or alias.name for alias in node.names],
                            "kind": "from_import",
                        }
                    )
    return examples[:10]


def _issue_pr_summary(replay_row: Mapping[str, object]) -> dict[str, object]:
    prompt_source = _mapping(replay_row.get("prompt_source"), field="prompt_source")
    accepted_change = _mapping(replay_row.get("accepted_change"), field="accepted_change")
    return {
        "issue_number": prompt_source.get("issue_number"),
        "issue_title": prompt_source.get("issue_title"),
        "issue_url": prompt_source.get("issue_url"),
        "pull_request_number": prompt_source.get("pull_request_number"),
        "pull_request_title": prompt_source.get("pull_request_title"),
        "pull_request_url": prompt_source.get("pull_request_url"),
        "merge_commit_sha": accepted_change.get("merge_commit_sha"),
    }


def _python_file_context(
    repo: Path,
    relative_path: str,
    *,
    focus_names: Sequence[str],
) -> dict[str, object]:
    path = repo / relative_path
    tree = _parse_python(path)
    classes = []
    functions = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                {
                    "name": child.name,
                    "line_span": [child.lineno, child.end_lineno or child.lineno],
                    "argument_names": [arg.arg for arg in child.args.args],
                }
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if not focus_names or any(name in node.name for name in focus_names):
                classes.append(
                    {
                        "name": node.name,
                        "line_span": [node.lineno, node.end_lineno or node.lineno],
                        "methods": methods,
                    }
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not focus_names or any(node.name.startswith(name) for name in focus_names):
                functions.append(_function_test_shape(node))
    return {
        "path": relative_path,
        "imports": list(_imports(tree))[:20],
        "classes": classes[:10],
        "functions": functions[:25],
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _click_core_semantic_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    methods: dict[str, dict[str, object]] = {}
    for class_node in [node for node in tree.body if isinstance(node, ast.ClassDef)]:
        if class_node.name not in {"Parameter", "Option"}:
            continue
        for child in class_node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f"{class_node.name}.{child.name}"
            calls = sorted(
                {
                    _call_name(grandchild.func)
                    for grandchild in ast.walk(child)
                    if isinstance(grandchild, ast.Call) and _call_name(grandchild.func)
                }
            )
            methods[key] = {
                "name": key,
                "line_span": [child.lineno, child.end_lineno or child.lineno],
                "argument_names": [arg.arg for arg in child.args.args],
                "call_names": calls[:30],
            }
    return {
        "methods": methods,
        "default_value_branches": _branch_shapes(
            tree,
            function_name="get_help_extra",
            left_name="default_value",
        ),
        "empty_string_comparison": _empty_string_comparison_shape(tree),
        "type_cast_call_shapes": _type_cast_call_shapes(tree),
    }


def _click_option_test_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    default_help_tests = [
        _function_test_shape(node)
        for node in functions
        if "default" in node.name or _function_uses_click_option(node)
    ]
    empty_string_tests = [
        shape
        for shape in default_help_tests
        if "empty" in str(shape.get("name", "")) or '""' in str(shape.get("string_literals", ()))
    ]
    strict_classes = [
        {
            "name": node.name,
            "line_span": [node.lineno, node.end_lineno or node.lineno],
            "methods": [
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
        }
        for node in classes
        if any(
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name in {"__eq__", "__str__"}
            for child in node.body
        )
    ]
    return {
        "default_help_tests": default_help_tests[:20],
        "empty_string_tests": empty_string_tests[:10],
        "strict_equality_reproduction_shape": {
            "classes": strict_classes[:5],
            "parametrized_default_tests": [
                shape
                for shape in default_help_tests
                if shape.get("parametrize") is not None
            ][:5],
        },
    }


def _function_test_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, object]:
    calls = sorted(
        {
            _call_name(child.func)
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and _call_name(child.func)
        }
    )
    string_literals = sorted(
        {
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        }
    )
    return {
        "name": node.name,
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "argument_names": [arg.arg for arg in node.args.args],
        "call_names": calls[:30],
        "string_literals": string_literals[:20],
        "parametrize": _parametrize_shape(node.decorator_list),
    }


def _function_uses_click_option(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _call_name(child.func) in {
            "click.Option",
            "Option",
        }:
            return True
    return False


def _pick_methods(
    core_context: Mapping[str, object],
    names: Sequence[str],
) -> list[dict[str, object]]:
    methods = _mapping(core_context.get("methods"), field="methods")
    picked = []
    for name in names:
        method = methods.get(name)
        if isinstance(method, Mapping):
            picked.append(dict(method))
    return picked


def _branch_shapes(
    tree: ast.Module,
    *,
    function_name: str,
    left_name: str,
) -> list[dict[str, object]]:
    branches = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != function_name:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                names = sorted(_names_in_node(child.test))
                if left_name in names:
                    branches.append(
                        {
                            "line": child.lineno,
                            "test_names": names,
                            "test_shape": type(child.test).__name__,
                            "call_names": sorted(_calls_in_node(child.test)),
                        }
                    )
    return branches


def _empty_string_comparison_shape(tree: ast.Module) -> dict[str, object]:
    comparisons = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        literals = [
            comparator.value
            for comparator in node.comparators
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
        ]
        names = sorted(_names_in_node(node))
        if "" in literals and "default_value" in names:
            comparisons.append(
                {
                    "line": node.lineno,
                    "names": names,
                    "operators": [type(operator).__name__ for operator in node.ops],
                    "string_literals": literals,
                    "has_isinstance_string_guard_in_same_test": _has_isinstance_string_guard(node),
                }
            )
    return {
        "comparisons": comparisons,
        "unguarded_empty_string_comparison_present": any(
            not item["has_isinstance_string_guard_in_same_test"] for item in comparisons
        ),
    }


def _type_cast_call_shapes(tree: ast.Module) -> list[dict[str, object]]:
    shapes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in {"type_cast_value", "process_value", "value_is_missing"}:
            continue
        shapes.append(
            {
                "function": node.name,
                "line_span": [node.lineno, node.end_lineno or node.lineno],
                "call_names": sorted(_calls_in_node(node))[:30],
                "mentions": sorted(_names_in_node(node) & {"UNSET", "multiple", "nargs"}),
            }
        )
    return shapes


def _names_in_node(node: ast.AST) -> set[str]:
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _calls_in_node(node: ast.AST) -> set[str]:
    return {
        _call_name(child.func)
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and _call_name(child.func)
    }


def _has_isinstance_string_guard(node: ast.AST) -> bool:
    parent = node
    while isinstance(parent, ast.BoolOp):
        parent = parent.values[0]
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _call_name(child.func) == "isinstance":
            if len(child.args) >= 2 and _call_name(child.args[1]) == "str":
                return True
    return False


def _click_source_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "src/click/core.py":
            return path
    for path in changed_files:
        if not _is_test_file(path):
            return path
    raise ValueError("Click replay row must include a source changed file")


def _click_test_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "tests/test_options.py":
            return path
    for path in changed_files:
        if _is_test_file(path):
            return path
    raise ValueError("Click replay row must include a test changed file")


def _requests_source_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "src/requests/models.py":
            return path
    for path in changed_files:
        if path.endswith(".py") and not _is_test_file(path):
            return path
    raise ValueError("Requests replay row must include a source changed file")


def _requests_test_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "tests/test_requests.py":
            return path
    for path in changed_files:
        if _is_test_file(path):
            return path
    raise ValueError("Requests replay row must include a test changed file")


def _requests_models_semantic_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    methods = _class_method_contexts(tree, class_names={"PreparedRequest"})
    prepare_body = _class_method_node(
        tree,
        class_name="PreparedRequest",
        method_name="prepare_body",
    )
    return {
        "methods": methods,
        "stream_detection": _requests_stream_detection_shape(prepare_body),
        "body_position_tracking": _body_position_shape(prepare_body),
        "header_effects": _header_assignment_shape(prepare_body),
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _requests_test_semantic_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    functions = _class_functions(tree, class_name="TestRequests")
    relevant = [
        node
        for node in functions
        if any(
            token in node.name
            for token in (
                "prepare_body",
                "rewind_body",
                "redirect",
                "stream",
                "transfer_enc",
            )
        )
    ]
    return {
        "test_class": {
            "name": "TestRequests",
            "method_count": len(functions),
            "line_span": _class_line_span(tree, "TestRequests"),
        },
        "rewind_tests": [
            _function_test_shape(node)
            for node in relevant
            if "rewind_body" in node.name or "prepare_body" in node.name
        ][:12],
        "redirect_tests": [
            _function_test_shape(node)
            for node in relevant
            if "redirect" in node.name or "transfer_enc" in node.name
        ][:12],
        "imports": list(_imports(tree))[:30],
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _requests_redirect_semantic_context(repo: Path) -> dict[str, object]:
    sessions_path = repo / "src/requests/sessions.py"
    utils_path = repo / "src/requests/utils.py"
    sessions_tree = _parse_python(sessions_path)
    utils_tree = _parse_python(utils_path)
    resolve_redirects = _class_method_node(
        sessions_tree,
        class_name="SessionRedirectMixin",
        method_name="resolve_redirects",
    ) or _class_method_node(
        sessions_tree,
        class_name="Session",
        method_name="resolve_redirects",
    )
    rewind_body = _module_function_node(utils_tree, "rewind_body")
    return {
        "resolve_redirects": _function_semantic_shape(resolve_redirects),
        "rewind_body": _function_semantic_shape(rewind_body),
        "rewindable_predicate": _rewindable_predicate_shape(resolve_redirects),
        "rewind_body_error_paths": _raise_call_shapes(rewind_body),
        "provenance_files": [
            {
                "path": "src/requests/sessions.py",
                "sha256": _sha256_bytes(sessions_path.read_bytes()),
            },
            {
                "path": "src/requests/utils.py",
                "sha256": _sha256_bytes(utils_path.read_bytes()),
            },
        ],
    }


def _requests_fixture_context(repo: Path) -> dict[str, object]:
    pyproject = _load_pyproject(repo)
    conftest_path = repo / "tests/conftest.py"
    conftest_tree = _parse_python(conftest_path)
    fixtures = [
        _function_semantic_shape(node)
        for node in ast.walk(conftest_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_call_name(decorator).endswith("fixture") for decorator in node.decorator_list)
    ]
    optional_dependencies = _nested_mapping(
        pyproject,
        ("project", "optional-dependencies"),
    )
    dev_dependencies = _string_sequence(optional_dependencies.get("dev", ()))
    return {
        "config_files": [
            path
            for path in ("pyproject.toml", "requirements-dev.txt", "tests/conftest.py")
            if (repo / path).exists()
        ],
        "dev_dependencies": [
            dependency
            for dependency in dev_dependencies
            if any(name in dependency for name in ("pytest-httpbin", "httpbin", "trustme"))
        ],
        "conftest_fixtures": fixtures,
        "conftest_imports": list(_imports(conftest_tree)),
        "conftest_sha256": _sha256_bytes(conftest_path.read_bytes()),
    }


def _requests_idiom_provenance_paths(
    repo: Path,
    knowledge_category: object,
    *,
    source_path: str,
    test_path: str,
    replay_id: str,
) -> list[str]:
    paths = [source_path, test_path, "task:" + replay_id]
    if knowledge_category == "requests_redirect_rewind_body_semantics":
        paths.extend(["src/requests/sessions.py", "src/requests/utils.py"])
    if knowledge_category == "requests_pytest_httpbin_fixture_setup":
        paths.extend(
            path
            for path in ("pyproject.toml", "requirements-dev.txt", "tests/conftest.py")
            if (repo / path).exists()
        )
    return paths


def _pytest_config_source_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "src/_pytest/config/__init__.py":
            return path
    for path in changed_files:
        if path.endswith(".py") and not _is_test_file(path):
            return path
    raise ValueError("pytest strict-addopts replay row must include a source file")


def _pytest_approx_source_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "src/_pytest/python_api.py":
            return path
    for path in changed_files:
        if path.endswith(".py") and not _is_test_file(path):
            return path
    raise ValueError("pytest timedelta-approx replay row must include a source file")


def _pytest_approx_test_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "testing/python/approx.py":
            return path
    for path in changed_files:
        if path.endswith(".py") and _is_test_file(path):
            return path
    raise ValueError("pytest timedelta-approx replay row must include a test file")


def _scrapy_pqueue_source_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "scrapy/pqueues.py":
            return path
    for path in changed_files:
        if path.endswith(".py") and not _is_test_file(path):
            return path
    raise ValueError("Scrapy downloader-aware replay row must include a source file")


def _scrapy_pqueue_test_path(changed_files: Sequence[str]) -> str:
    for path in changed_files:
        if path == "tests/test_pqueues.py":
            return path
    for path in changed_files:
        if path.endswith(".py") and _is_test_file(path):
            return path
    raise ValueError("Scrapy downloader-aware replay row must include a test file")


def _pytest_approx_semantic_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    methods = _class_method_contexts(
        tree,
        class_names={"ApproxTimedelta", "ApproxScalar", "ApproxBase"},
    )
    timedelta_init = _class_method_node(
        tree,
        class_name="ApproxTimedelta",
        method_name="__init__",
    )
    timedelta_eq = _class_method_node(
        tree,
        class_name="ApproxTimedelta",
        method_name="__eq__",
    )
    scalar_tolerance = _class_property_node(
        tree,
        class_name="ApproxScalar",
        property_name="tolerance",
    )
    approx_scalar = _class_method_node(
        tree,
        class_name="ApproxBase",
        method_name="_approx_scalar",
    )
    approx_function = _module_function_node(tree, "approx")
    return {
        "methods": methods,
        "timedelta_constructor": _pytest_timedelta_constructor_shape(timedelta_init),
        "timedelta_eq": _function_semantic_shape(timedelta_eq),
        "scalar_tolerance": _pytest_scalar_tolerance_shape(scalar_tolerance),
        "approx_scalar_dispatch": _function_semantic_shape(approx_scalar),
        "approx_function": _function_semantic_shape(approx_function),
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _pytest_timedelta_constructor_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    return {
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "argument_names": [arg.arg for arg in node.args.args],
        "call_names": sorted(_calls_in_node(node))[:60],
        "mentions": sorted(
            _names_in_node(node)
            & {"expected", "rel", "abs", "nan_ok", "timedelta", "datetime", "max"}
        ),
        "string_literals": sorted(_string_constants(node))[:40],
        "rejects_datetime_rel": "datetime" in _names_in_node(node)
        and "rel" in _names_in_node(node),
        "requires_explicit_tolerance": any(
            "requires an explicit tolerance" in literal for literal in _string_constants(node)
        ),
        "repo_before_requires_rel_timedelta": any(
            "relative tolerance for timedelta must be a" in literal
            and "timedelta" in literal
            for literal in _string_constants(node)
        ),
        "uses_max_over_abs_rel": "max" in _calls_in_node(node)
        and {"abs", "rel"} <= _names_in_node(node),
        "mentions_nan_ok": "nan_ok" in _names_in_node(node),
    }


def _pytest_scalar_tolerance_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    return {
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "call_names": sorted(_calls_in_node(node))[:60],
        "mentions": sorted(
            _names_in_node(node)
            & {"relative_tolerance", "absolute_tolerance", "expected", "rel", "abs"}
        ),
        "multiplies_relative_by_expected": _has_multiply_of_names(
            node,
            left_names={"rel", "self.rel"},
            right_names={"expected", "self.expected"},
        ),
        "returns_max_relative_absolute": "max" in _calls_in_node(node)
        and {"relative_tolerance", "absolute_tolerance"} <= _names_in_node(node),
    }


def _class_property_node(
    tree: ast.Module,
    *,
    class_name: str,
    property_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != property_name:
                continue
            if any(_call_name(decorator) == "property" for decorator in child.decorator_list):
                return child
    return None


def _has_multiply_of_names(
    node: ast.AST,
    *,
    left_names: set[str],
    right_names: set[str],
) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.BinOp) or not isinstance(child.op, ast.Mult):
            continue
        left = _names_in_node(child.left) | {_call_name(child.left)}
        right = _names_in_node(child.right) | {_call_name(child.right)}
        if left & left_names and right & right_names:
            return True
        if left & right_names and right & left_names:
            return True
    return False


def _pytest_approx_test_context(repo: Path) -> dict[str, object]:
    tree = _parse_python(repo)
    functions = _all_functions(tree)
    datetime_tests = [
        _function_test_shape(node)
        for node in functions
        if "datetime" in node.name
    ][:30]
    timedelta_tests = [
        _function_test_shape(node)
        for node in functions
        if "timedelta" in node.name
    ][:30]
    return {
        "test_file": repo.name if repo.name == "approx.py" else repo.as_posix(),
        "test_class": "TestApproxDatetime",
        "datetime_tests": datetime_tests,
        "timedelta_tests": timedelta_tests,
        "pytest_tools": sorted(
            tool for node in functions for tool in _pytest_tools(node)
        )[:60],
        "importorskip_calls": sorted(
            {
                literal
                for node in functions
                for literal in _string_constants(node)
                if literal == "numpy"
            }
        ),
        "imports": list(_imports(tree))[:40],
        "sha256": _sha256_bytes(repo.read_bytes()),
    }


def _scrapy_pqueue_semantic_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    methods = _class_method_contexts(
        tree,
        class_names={"DownloaderInterface", "DownloaderAwarePriorityQueue"},
    )
    active_downloads = _class_method_node(
        tree,
        class_name="DownloaderInterface",
        method_name="_active_downloads",
    )
    stats = _class_method_node(
        tree,
        class_name="DownloaderInterface",
        method_name="stats",
    )
    pop = _class_method_node(
        tree,
        class_name="DownloaderAwarePriorityQueue",
        method_name="pop",
    )
    peek = _class_method_node(
        tree,
        class_name="DownloaderAwarePriorityQueue",
        method_name="peek",
    )
    push = _class_method_node(
        tree,
        class_name="DownloaderAwarePriorityQueue",
        method_name="push",
    )
    init = _class_method_node(
        tree,
        class_name="DownloaderAwarePriorityQueue",
        method_name="__init__",
    )
    return {
        "methods": methods,
        "active_downloads": _scrapy_active_downloads_shape(active_downloads),
        "stats": _function_semantic_shape(stats),
        "slot_selection": {
            "pop": _scrapy_slot_selection_shape(pop),
            "peek": _scrapy_slot_selection_shape(peek),
        },
        "queue_lifecycle": {
            "init": _function_semantic_shape(init),
            "push": _function_semantic_shape(push),
            "pop": _function_semantic_shape(pop),
        },
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _scrapy_active_downloads_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    return {
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "argument_names": [arg.arg for arg in node.args.args],
        "mentions": sorted(_names_in_node(node) & {"slot", "downloader", "slots", "active"}),
        "call_names": sorted(_calls_in_node(node))[:40],
        "returns_zero_for_missing_slot": any(
            isinstance(child, ast.Constant) and child.value == 0 for child in ast.walk(node)
        ),
        "uses_len_slot_active": "len" in _calls_in_node(node)
        and {"slots", "active"} <= _names_in_node(node),
    }


def _scrapy_slot_selection_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    return {
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "call_names": sorted(_calls_in_node(node))[:40],
        "mentions": sorted(
            _names_in_node(node)
            & {"stats", "slot", "pqueues", "_next_slot", "_last_selected_slot"}
        ),
        "uses_min_stats": "min" in _calls_in_node(node) and "stats" in _names_in_node(node),
        "uses_next_slot_helper": "_next_slot" in _calls_in_node(node),
        "deletes_empty_queue": _scrapy_deletes_empty_queue(node),
    }


def _scrapy_deletes_empty_queue(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Delete):
            continue
        for target in child.targets:
            if "pqueues" in _names_in_node(target):
                return True
    return False


def _scrapy_pqueue_test_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    functions = _all_functions(tree)
    downloader_aware_tests = [
        _function_test_shape(node)
        for node in functions
        if "tie_breaking" in node.name
        or "push_pop" in node.name
        or "peek" in node.name
    ][:30]
    return {
        "test_file": path.name if path.name == "test_pqueues.py" else path.as_posix(),
        "test_class": "TestDownloaderAwarePriorityQueue",
        "downloader_aware_tests": downloader_aware_tests,
        "pytest_tools": sorted(
            tool for node in functions for tool in _pytest_tools(node)
        )[:60],
        "mock_downloader_import": any(
            "MockDownloader" in str(item.get("names", ""))
            for item in _imports(tree)
        ),
        "slot_meta_key_import": any(
            "Downloader" in str(item.get("names", ""))
            or item.get("module") == "scrapy.core.downloader"
            for item in _imports(tree)
        ),
        "imports": list(_imports(tree))[:40],
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _pytest_config_semantic_context(path: Path) -> dict[str, object]:
    tree = _parse_python(path)
    methods = _class_method_contexts(tree, class_names={"Config"})
    parse_node = _class_method_node(tree, class_name="Config", method_name="parse")
    strict_node = _class_method_node(
        tree,
        class_name="Config",
        method_name="_warn_or_fail_if_strict",
    )
    unknown_ini_node = _class_method_node(
        tree,
        class_name="Config",
        method_name="_get_unknown_ini_keys",
    )
    return {
        "methods": methods,
        "parse_flow": _pytest_parse_flow_shape(parse_node),
        "override_ini_handling": _pytest_override_ini_shape(tree, parse_node),
        "strict_ini_gets": _pytest_getini_calls(strict_node),
        "unknown_ini_check": _function_semantic_shape(unknown_ini_node),
        "sha256": _sha256_bytes(path.read_bytes()),
    }


def _pytest_parse_flow_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    return {
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "argument_names": [arg.arg for arg in node.args.args],
        "call_names": sorted(_calls_in_node(node))[:60],
        "mentions": sorted(
            _names_in_node(node)
            & {
                "addopts",
                "PYTEST_ADDOPTS",
                "override_ini",
                "known_args_namespace",
                "_inicfg",
                "_inicache",
                "getini",
                "_validate_args",
            }
        ),
        "string_literals": sorted(
            literal
            for literal in _string_constants(node)
            if literal in {"PYTEST_ADDOPTS", "addopts", "via PYTEST_ADDOPTS", "via addopts config"}
        ),
        "getini_names": _pytest_getini_calls(node),
        "assignments": _pytest_assignment_shapes(
            node,
            names={"args", "known_args_namespace", "_inicfg", "_inicache"},
        ),
    }


def _pytest_override_ini_shape(
    tree: ast.Module,
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    imports_parse_override = any(
        isinstance(child, ast.ImportFrom)
        and child.module == "_pytest.config.findpaths"
        and any(alias.name == "parse_override_ini" for alias in child.names)
        for child in tree.body
    )
    call_names = sorted(_calls_in_node(node)) if node is not None else []
    names = sorted(_names_in_node(node)) if node is not None else []
    return {
        "imports_parse_override_ini": imports_parse_override,
        "parse_calls_parse_override_ini": "parse_override_ini" in call_names,
        "mentions_override_ini": "override_ini" in names,
        "updates_inicfg": "_inicfg" in names and "update" in call_names,
        "clears_inicache": "_inicache" in names and "clear" in call_names,
    }


def _pytest_getini_calls(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> list[str]:
    if node is None:
        return []
    values = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or _call_name(child.func) != "self.getini":
            continue
        if child.args and isinstance(child.args[0], ast.Constant):
            value = child.args[0].value
            if isinstance(value, str):
                values.append(value)
    return sorted(dict.fromkeys(values))


def _pytest_assignment_shapes(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    names: set[str],
) -> list[dict[str, object]]:
    rows = []
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AugAssign)):
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        target_names = sorted(
            target_name
            for target in targets
            if (target_name := _call_name(target))
            and any(name in target_name for name in names)
        )
        if not target_names:
            continue
        value = child.value if isinstance(child, ast.Assign) else child.value
        rows.append(
            {
                "line": child.lineno,
                "targets": target_names,
                "value_calls": sorted(_calls_in_node(value)),
                "value_names": sorted(_names_in_node(value)),
            }
        )
    return rows


def _pytest_strict_test_context(
    repo: Path,
    config_test_path: str,
    mark_test_path: str,
) -> dict[str, object]:
    config_tree = _parse_python(repo / config_test_path)
    mark_tree = _parse_python(repo / mark_test_path)
    config_functions = _all_functions(config_tree)
    mark_functions = _all_functions(mark_tree)
    return {
        "config_test_file": config_test_path,
        "mark_test_file": mark_test_path,
        "strict_config_tests": [
            _function_test_shape(node)
            for node in config_functions
            if "strict_config" in node.name or "invalid_config" in node.name
        ][:12],
        "addopts_tests": [
            _function_test_shape(node)
            for node in config_functions
            if "addopts" in node.name
        ][:12],
        "strict_mark_tests": [
            _function_test_shape(node)
            for node in mark_functions
            if "strict" in node.name or "marker" in node.name
        ][:12],
        "pytester_tools": sorted(
            tool
            for node in [*config_functions, *mark_functions]
            for tool in _pytester_tools(node)
        )[:40],
        "config_imports": list(_imports(config_tree))[:30],
        "mark_imports": list(_imports(mark_tree))[:30],
        "sha256": {
            config_test_path: _sha256_bytes((repo / config_test_path).read_bytes()),
            mark_test_path: _sha256_bytes((repo / mark_test_path).read_bytes()),
        },
    }


def _all_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _pytester_tools(node: ast.AST) -> set[str]:
    return {
        name
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and (name := _call_name(child.func))
        and (
            name.startswith("pytester.")
            or name
            in {
                "result.stdout.fnmatch_lines",
                "result.stderr.fnmatch_lines",
                "result.stdout.no_fnmatch_line",
                "rec.assertoutcome",
                "rec.assert_outcomes",
            }
        )
    }


def _pytest_auxiliary_file_context(repo: Path, relative_path: str) -> dict[str, object]:
    path = repo / relative_path
    if relative_path == "AUTHORS":
        return _pytest_authors_context(repo, expected_new_entry="Praneeth Kodumagulla")
    if relative_path.startswith("changelog/"):
        return _pytest_changelog_context(repo, target_path=relative_path)
    return {
        "path": relative_path,
        "exists": path.exists(),
        "sha256": _sha256_bytes(path.read_bytes()) if path.is_file() else None,
    }


def _pytest_changelog_context(repo: Path, *, target_path: str) -> dict[str, object]:
    changelog_dir = repo / "changelog"
    fragments = sorted(
        path.relative_to(repo).as_posix()
        for path in changelog_dir.glob("*.rst")
        if path.is_file()
    ) if changelog_dir.is_dir() else []
    suffix_counts: dict[str, int] = {}
    for fragment in fragments:
        suffix = ".".join(Path(fragment).name.split(".")[1:])
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
    target = repo / target_path
    return {
        "path": target_path,
        "exists_in_repo_before": target.exists(),
        "expected_fragment_suffix": ".bugfix.rst",
        "issue_number_in_filename": "14442",
        "fragment_count": len(fragments),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "nearby_bugfix_fragments": [
            fragment for fragment in fragments if fragment.endswith(".bugfix.rst")
        ][:12],
        "target_sha256": _sha256_bytes(target.read_bytes()) if target.is_file() else None,
    }


def _pytest_authors_context(
    repo: Path,
    *,
    expected_new_entry: str,
) -> dict[str, object]:
    path = repo / "AUTHORS"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    non_empty = [line for line in lines if line.strip()]
    first_letter = expected_new_entry[:1].casefold()
    neighborhood = [
        line
        for line in non_empty
        if line[:1].casefold() in {first_letter, chr(ord(first_letter) - 1), chr(ord(first_letter) + 1)}
    ]
    return {
        "path": "AUTHORS",
        "exists": path.exists(),
        "line_count": len(lines),
        "non_empty_line_count": len(non_empty),
        "expected_new_entry": expected_new_entry,
        "expected_entry_present_in_repo_before": expected_new_entry in non_empty,
        "entry_shape": "one contributor name per line",
        "alphabetical_neighborhood_sample": neighborhood[:20],
        "sha256": _sha256_bytes(path.read_bytes()) if path.is_file() else None,
    }


def _pytest_idiom_source_path(knowledge_category: object, source_path: str) -> str:
    if knowledge_category == "pytest_changelog_fragment_convention":
        return "changelog"
    if knowledge_category == "pytest_authors_convention":
        return "AUTHORS"
    if knowledge_category == "pytest_repo_test_patterns":
        return "testing/test_config.py,testing/test_mark.py"
    return source_path


def _pytest_idiom_provenance_paths(
    repo: Path,
    knowledge_category: object,
    *,
    source_path: str,
    config_test_path: str,
    mark_test_path: str,
    replay_id: str,
) -> list[str]:
    paths = [source_path, config_test_path, mark_test_path, "task:" + replay_id]
    if knowledge_category == "pytest_changelog_fragment_convention":
        paths = [
            path
            for path in ("changelog", "changelog/14442.bugfix.rst", "task:" + replay_id)
            if path.startswith("task:") or (repo / path).exists()
        ]
    elif knowledge_category == "pytest_authors_convention":
        paths = ["AUTHORS", "task:" + replay_id]
    return paths


def _class_method_contexts(
    tree: ast.Module,
    *,
    class_names: set[str],
) -> dict[str, dict[str, object]]:
    methods: dict[str, dict[str, object]] = {}
    for class_node in [node for node in tree.body if isinstance(node, ast.ClassDef)]:
        if class_node.name not in class_names:
            continue
        for child in class_node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = f"{class_node.name}.{child.name}"
            methods[key] = _function_semantic_shape(child)
    return methods


def _class_method_node(
    tree: ast.Module,
    *,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                child.name == method_name
            ):
                return child
    return None


def _class_functions(
    tree: ast.Module,
    *,
    class_name: str,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
    return []


def _class_line_span(tree: ast.Module, class_name: str) -> list[int] | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [node.lineno, node.end_lineno or node.lineno]
    return None


def _module_function_node(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _function_semantic_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    return {
        "name": node.name,
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "argument_names": [arg.arg for arg in node.args.args],
        "call_names": sorted(_calls_in_node(node))[:40],
        "mentions": sorted(_names_in_node(node))[:60],
    }


def _requests_stream_detection_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    iterable_checks = []
    for child in ast.walk(node):
        if isinstance(child, ast.If) and "data" in _names_in_node(child.test):
            test_names = sorted(_names_in_node(child.test))
            if "Iterable" in test_names or "__iter__" in _string_constants(child.test):
                iterable_checks.append(
                    {
                        "line": child.lineno,
                        "test_shape": type(child.test).__name__,
                        "test_names": test_names,
                        "call_names": sorted(_calls_in_node(child.test)),
                        "string_literals": sorted(_string_constants(child.test)),
                    }
                )
    return {
        "iterable_checks": iterable_checks,
        "has_iterable_isinstance_check": any(
            "isinstance" in item["call_names"] and "Iterable" in item["test_names"]
            for item in iterable_checks
        ),
        "has_dunder_iter_hasattr_check": any(
            "hasattr" in item["call_names"] and "__iter__" in item["string_literals"]
            for item in iterable_checks
        ),
        "excluded_raw_data_types": sorted(
            _names_in_node(node) & {"str", "bytes", "list", "tuple", "Mapping"}
        ),
    }


def _body_position_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> dict[str, object]:
    if node is None:
        return {}
    assignments = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign):
            continue
        targets = [
            _call_name(target)
            for target in child.targets
            if _call_name(target).endswith("_body_position")
        ]
        if targets:
            assignments.append(
                {
                    "line": child.lineno,
                    "targets": targets,
                    "value_calls": sorted(_calls_in_node(child.value)),
                    "value_names": sorted(_names_in_node(child.value)),
                }
            )
    return {
        "assignments": assignments,
        "getattr_tell_lines": [
            child.lineno
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and _call_name(child.func) == "getattr"
            and "tell" in _string_constants(child)
        ],
    }


def _header_assignment_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> list[dict[str, object]]:
    if node is None:
        return []
    rows = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign):
            continue
        for target in child.targets:
            if not isinstance(target, ast.Subscript):
                continue
            target_name = _call_name(target.value)
            if target_name != "self.headers":
                continue
            rows.append(
                {
                    "line": child.lineno,
                    "key_literals": sorted(_string_constants(target.slice)),
                    "value_calls": sorted(_calls_in_node(child.value)),
                    "value_names": sorted(_names_in_node(child.value)),
                }
            )
    return rows


def _rewindable_predicate_shape(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> list[dict[str, object]]:
    if node is None:
        return []
    rows = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assign) and any(
            _call_name(target) == "rewindable" for target in child.targets
        ):
            rows.append(
                {
                    "line": child.lineno,
                    "value_shape": type(child.value).__name__,
                    "names": sorted(_names_in_node(child.value)),
                    "string_literals": sorted(_string_constants(child.value)),
                    "call_names": sorted(_calls_in_node(child.value)),
                }
            )
    return rows


def _raise_call_shapes(
    node: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> list[dict[str, object]]:
    if node is None:
        return []
    rows = []
    for child in ast.walk(node):
        if isinstance(child, ast.Raise) and child.exc is not None:
            rows.append(
                {
                    "line": child.lineno,
                    "exception": _call_name(child.exc),
                    "string_literals": sorted(_string_constants(child.exc)),
                }
            )
    return rows


def _string_constants(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def _pytest_config_list(
    pyproject: Mapping[str, object],
    pytest_ini: Mapping[str, str],
    key: str,
) -> list[str]:
    ini_options = _nested_mapping(pyproject, ("tool", "pytest", "ini_options"))
    value = ini_options.get(key)
    if isinstance(value, str):
        return value.split()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    ini_value = pytest_ini.get(key)
    if ini_value:
        return ini_value.split()
    return []


def _discovered_test_roots(test_files: Sequence[str]) -> list[str]:
    roots = set()
    for path in test_files:
        parts = PurePosixPath(path).parts
        if parts and parts[0] in {"tests", "testing"}:
            roots.add(parts[0])
        elif len(parts) > 1:
            roots.add(PurePosixPath(*parts[:-1]).as_posix())
        else:
            roots.add(".")
    return sorted(roots)


def _import_mode_hints(repo: Path, test_files: Sequence[str]) -> list[dict[str, object]]:
    hints = []
    for path in test_files[:10]:
        tree = _parse_python(repo / path)
        hints.append({"path": path, "imports": list(_imports(tree))})
    return hints


def _test_file_examples(repo: Path, test_files: Sequence[str]) -> list[dict[str, object]]:
    examples = []
    for path in test_files[:10]:
        tree = _parse_python(repo / path)
        functions = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        examples.append({"path": path, "test_functions": functions[:10]})
    return examples


def _imports(tree: ast.Module) -> tuple[dict[str, str], ...]:
    imports: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"kind": "import", "module": alias.name})
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(
                {
                    "kind": "from_import",
                    "module": node.module,
                    "names": ",".join(alias.asname or alias.name for alias in node.names),
                }
            )
    return tuple(imports)


def _pytest_tools(node: ast.AST) -> set[str]:
    tools = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name.startswith("pytest.") or name.startswith("monkeypatch."):
                tools.add(name)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            if child.value.id == "monkeypatch":
                tools.add(f"monkeypatch.{child.attr}")
    return tools


def _parametrize_shape(decorators: Sequence[ast.expr]) -> dict[str, object] | None:
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if not _call_name(decorator.func).endswith("parametrize"):
            continue
        arg_names: list[str] = []
        case_count = None
        if decorator.args:
            first = decorator.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                arg_names = [part.strip() for part in first.value.split(",") if part.strip()]
        if len(decorator.args) >= 2 and isinstance(decorator.args[1], (ast.List, ast.Tuple)):
            case_count = len(decorator.args[1].elts)
        return {
            "arg_names": arg_names,
            "case_count": case_count,
            "keyword_names": [keyword.arg for keyword in decorator.keywords if keyword.arg],
        }
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _string_literal_sequence(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return []
    values = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            values.append(item.value)
    return values


def _validation_provenance_paths(repo: Path) -> list[str]:
    paths = [
        path
        for path in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
        if (repo / path).exists()
    ]
    return paths or ["."]


def _provenance_hash(repo: Path, relative_paths: Sequence[str]) -> str:
    payload = []
    for relative_path in sorted(dict.fromkeys(relative_paths)):
        if relative_path.startswith("task:"):
            payload.append({"path": relative_path, "sha256": _sha256_text(relative_path)})
            continue
        path = _repo_path(repo, relative_path)
        if path.is_file():
            payload.append({"path": relative_path, "sha256": _sha256_bytes(path.read_bytes())})
        elif path.is_dir():
            payload.append({"path": relative_path, "sha256": _tree_hash(path)})
        else:
            payload.append({"path": relative_path, "sha256": _sha256_text(relative_path)})
    return _sha256_json(payload)


def _tree_hash(path: Path) -> str:
    payload = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        payload.append(
            {
                "path": child.relative_to(path).as_posix(),
                "sha256": _sha256_bytes(child.read_bytes()),
            }
        )
    return _sha256_json(payload)


def _is_test_file(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        "tests" in pure.parts
        or "testing" in pure.parts
        or pure.name.startswith("test_")
        or pure.name.endswith("_test.py")
    )


def _nested_mapping(value: Mapping[str, object], path: Sequence[str]) -> Mapping[str, object]:
    current: object = value
    for part in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(part, {})
    return current if isinstance(current, Mapping) else {}


def _nested_str(value: Mapping[str, object], path: Sequence[str]) -> str | None:
    current: object = value
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current if isinstance(current, str) else None


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _string_sequence(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("expected a sequence of strings")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError("expected non-empty string entries")
        result.append(item)
    return result


def _tests_only_task_ids(tasks: Sequence[Mapping[str, object]]) -> list[str]:
    return [
        _required_str(task, "id")
        for task in tasks
        if task.get("task_type") == "tests_only"
    ]


def _repo_path(repo: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"path must be repository-relative: {relative_path}")
    if relative_path in {"", "."}:
        return repo
    return repo / Path(*pure.parts)


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _parse_python(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate_split(split: str) -> None:
    if split not in SPLITS:
        raise ValueError(f"unsupported split: {split}")


def _contains_raw_blob_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in RAW_BLOB_KEYS:
                return True
            if _contains_raw_blob_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_raw_blob_key(item) for item in value)
    return False


def _load_manifest_replay_row(manifest: Path, replay_id: str) -> Mapping[str, object]:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("issue/PR replay manifest must contain records")
    for row in records:
        if isinstance(row, Mapping) and row.get("id") == replay_id:
            return row
    raise ValueError(f"replay row not found in manifest: {replay_id}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit compact local-knowledge records from local sources."
    )
    parser.add_argument("--click-replay-row", help="issue/PR replay row id to extract")
    parser.add_argument("--requests-replay-row", help="issue/PR replay row id to extract")
    parser.add_argument(
        "--pytest-strict-addopts-replay-row",
        help="pytest strict addopts issue/PR replay row id to extract",
    )
    parser.add_argument(
        "--pytest-timedelta-approx-replay-row",
        help="pytest timedelta approx issue/PR replay row id to extract",
    )
    parser.add_argument(
        "--scrapy-downloader-aware-replay-row",
        help="Scrapy downloader-aware queue issue/PR replay row id to extract",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
        help="issue/PR mini replay manifest",
    )
    parser.add_argument("--repo", type=Path, help="local repo-before checkout")
    parser.add_argument("--out", type=Path, required=True, help="output JSONL path")
    parser.add_argument("--retrieved-at", default="unknown")
    parser.add_argument(
        "--setup-command",
        action="append",
        default=[],
        help="setup command to store in validation recipe records",
    )
    parser.add_argument(
        "--baseline-validation-command",
        action="append",
        default=[],
        help="baseline validation command to store in validation recipe records",
    )
    args = parser.parse_args(argv)

    modes = [
        args.click_replay_row,
        args.requests_replay_row,
        args.pytest_strict_addopts_replay_row,
        args.pytest_timedelta_approx_replay_row,
        args.scrapy_downloader_aware_replay_row,
    ]
    if sum(1 for mode in modes if mode) > 1:
        parser.error("choose only one replay extraction mode")
    if args.click_replay_row:
        if args.repo is None:
            parser.error("--repo is required with --click-replay-row")
        row = _load_manifest_replay_row(args.manifest, args.click_replay_row)
        records = build_click_replay_local_knowledge_records(
            args.repo,
            row,
            retrieved_at=args.retrieved_at,
            setup_commands=args.setup_command,
            baseline_validation_commands=args.baseline_validation_command,
        )
    elif args.requests_replay_row:
        if args.repo is None:
            parser.error("--repo is required with --requests-replay-row")
        row = _load_manifest_replay_row(args.manifest, args.requests_replay_row)
        records = build_requests_replay_local_knowledge_records(
            args.repo,
            row,
            retrieved_at=args.retrieved_at,
            setup_commands=args.setup_command,
            baseline_validation_commands=args.baseline_validation_command,
        )
    elif args.pytest_strict_addopts_replay_row:
        if args.repo is None:
            parser.error("--repo is required with --pytest-strict-addopts-replay-row")
        row = _load_manifest_replay_row(
            args.manifest,
            args.pytest_strict_addopts_replay_row,
        )
        records = build_pytest_strict_addopts_local_knowledge_records(
            args.repo,
            row,
            retrieved_at=args.retrieved_at,
            setup_commands=args.setup_command,
            baseline_validation_commands=args.baseline_validation_command,
        )
    elif args.pytest_timedelta_approx_replay_row:
        if args.repo is None:
            parser.error("--repo is required with --pytest-timedelta-approx-replay-row")
        row = _load_manifest_replay_row(
            args.manifest,
            args.pytest_timedelta_approx_replay_row,
        )
        records = build_pytest_timedelta_approx_local_knowledge_records(
            args.repo,
            row,
            retrieved_at=args.retrieved_at,
            setup_commands=args.setup_command,
            baseline_validation_commands=args.baseline_validation_command,
        )
    elif args.scrapy_downloader_aware_replay_row:
        if args.repo is None:
            parser.error("--repo is required with --scrapy-downloader-aware-replay-row")
        row = _load_manifest_replay_row(
            args.manifest,
            args.scrapy_downloader_aware_replay_row,
        )
        records = build_scrapy_downloader_aware_local_knowledge_records(
            args.repo,
            row,
            retrieved_at=args.retrieved_at,
            setup_commands=args.setup_command,
            baseline_validation_commands=args.baseline_validation_command,
        )
    else:
        parser.error("no extraction mode selected")

    output = write_local_knowledge_jsonl(records, args.out)
    print(
        json.dumps(
            {
                "output": str(output),
                "records": len(records),
                "record_type_counts": dict(
                    sorted(
                        {
                            record_type: sum(
                                1
                                for record in records
                                if record["record_type"] == record_type
                            )
                            for record_type in {str(record["record_type"]) for record in records}
                        }.items()
                    )
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
