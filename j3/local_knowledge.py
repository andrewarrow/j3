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
