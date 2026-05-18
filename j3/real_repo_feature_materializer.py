"""One-file source feature materialization for real-repo ladder tasks."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from j3.ast_delta import python_ast_delta_metadata
from j3.real_repo_preflight import load_real_repo_ladder_manifest
from j3.source_region_materializer import (
    SourceRegionAction,
    SourceRegionActionKind,
    SourceRegionConstraints,
    SourceRegionMaterializationError,
    SourceRegionMaterializationResult,
    SourceRegionTarget,
    materialize_source_region,
)


REAL_REPO_FEATURE_CANDIDATE_SCHEMA_VERSION = "real-repo-feature-candidate-v1"
REAL_REPO_FEATURE_CANDIDATE_KIND = "real_repo_one_file_feature_candidate"
REAL_REPO_FEATURE_ACTION_FAMILY = "one_file_source_feature_region"
INICONFIG_SECTION_DEFAULT_TASK_ID = "iniconfig-feature-section-default"
H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID = "h11-feature-bytesify-object-message"
HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID = (
    "humanize-feature-naturalsize-zero-format"
)
CANDIDATE_VALIDATION_DEFERRED = "candidate_validation_deferred"


class RealRepoFeatureMaterializerError(ValueError):
    """Raised when a one-file feature candidate cannot be materialized."""

    def __init__(self, message: str, *, blocker: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.blocker = blocker or {
            "field": "real_repo_feature_materializer",
            "reason": "unsupported_real_repo_feature_task",
            "message": message,
        }


@dataclass(frozen=True, slots=True)
class RealRepoFeatureCandidate:
    """Structured candidate/action record for one source feature attempt."""

    candidate_id: str
    repo_id: str
    repo_split: str
    checkout_ref: str
    task_id: str
    task_type: str
    prompt: str
    status: str
    target_source_file: str
    target_test_file: str
    validation_commands: list[str] = field(default_factory=list)
    allowed_write_paths: list[str] = field(default_factory=list)
    hidden_like_checks: list[str] = field(default_factory=list)
    expected_failure_modes: list[str] = field(default_factory=list)
    production_files: list[str] = field(default_factory=list)
    production_file_hashes_before: dict[str, str] = field(default_factory=dict)
    production_file_hashes_after: dict[str, str] = field(default_factory=dict)
    source_action: dict[str, object] | None = None
    candidate_after: dict[str, object] = field(default_factory=dict)
    mutation_scope: dict[str, object] = field(default_factory=dict)
    validation: dict[str, object] = field(default_factory=dict)
    blockers: list[dict[str, str]] = field(default_factory=list)
    residual_labels: list[str] = field(default_factory=list)
    zero_hosted_usage_confirmed: bool = True

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": REAL_REPO_FEATURE_CANDIDATE_SCHEMA_VERSION,
            "record_kind": REAL_REPO_FEATURE_CANDIDATE_KIND,
            "candidate_id": self.candidate_id,
            "repo_id": self.repo_id,
            "repo_split": self.repo_split,
            "checkout_ref": self.checkout_ref,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "action_family": REAL_REPO_FEATURE_ACTION_FAMILY,
            "status": self.status,
            "target_source_file": self.target_source_file,
            "target_test_file": self.target_test_file,
            "validation_commands": list(self.validation_commands),
            "allowed_write_paths": list(self.allowed_write_paths),
            "hidden_like_checks": list(self.hidden_like_checks),
            "expected_failure_modes": list(self.expected_failure_modes),
            "production_files": list(self.production_files),
            "production_file_hashes_before": dict(self.production_file_hashes_before),
            "production_file_hashes_after": dict(self.production_file_hashes_after),
            "source_action": _json_copy(self.source_action),
            "candidate_after": _json_copy(self.candidate_after),
            "mutation_scope": _json_copy(self.mutation_scope),
            "validation": _json_copy(self.validation),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "residual_labels": list(self.residual_labels),
            "zero_hosted_usage_confirmed": self.zero_hosted_usage_confirmed,
        }


def materialize_real_repo_feature_candidate(
    repo_path: Path,
    *,
    repo: Mapping[str, object],
    task: Mapping[str, object],
    write: bool = True,
    validate: bool = False,
    validation_timeout_seconds: int = 120,
) -> RealRepoFeatureCandidate:
    """Materialize the supported real-repo one-file source feature candidate."""

    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise _blocker_error(
            f"repo does not exist: {resolved_repo}",
            field="repo_state",
            reason="missing_repo_state",
        )

    repo_id = _required_str(repo, "id")
    repo_split = str(repo.get("split", "unknown"))
    checkout_ref = _required_str(repo, "checkout_ref")
    task_id = _required_str(task, "id")
    task_type = _required_str(task, "task_type")
    if task_type != "one_file_feature":
        raise _blocker_error(
            "real-repo feature materializer requires task_type='one_file_feature'",
            field="task_type",
            reason="unsupported_task_type",
        )
    if repo_id == "h11" and task_id == H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID:
        target_source_file = "h11/_util.py"
        target_test_file = "h11/tests/test_util.py"
    elif repo_id == "iniconfig" and task_id == INICONFIG_SECTION_DEFAULT_TASK_ID:
        target_source_file = "src/iniconfig/__init__.py"
        target_test_file = "testing/test_iniconfig.py"
    elif repo_id == "humanize" and task_id == HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID:
        target_source_file = "src/humanize/filesize.py"
        target_test_file = "tests/test_filesize.py"
    else:
        raise _blocker_error(
            "one-file feature materialization is only implemented for "
            "h11-feature-bytesify-object-message and "
            "iniconfig-feature-section-default and "
            "humanize-feature-naturalsize-zero-format",
            field="task_id",
            reason="unsupported_real_repo_feature_task",
        )

    prompt = _required_str(task, "prompt")
    allowed_write_paths = _string_sequence(
        task.get("allowed_write_paths"),
        field="allowed_write_paths",
    )
    validation_commands = _string_sequence(
        task.get("public_validation_commands"),
        field="public_validation_commands",
    )
    hidden_like_checks = _string_sequence(
        task.get("hidden_like_checks"),
        field="hidden_like_checks",
    )
    expected_failure_modes = _string_sequence(
        task.get("expected_failure_modes"),
        field="expected_failure_modes",
    )
    production_files = _production_python_files(resolved_repo, repo_id=repo_id)
    production_hashes_before = _file_hashes(resolved_repo, production_files)

    blockers: list[dict[str, str]] = []
    source_action: SourceRegionAction | None = None
    source_result: SourceRegionMaterializationResult | None = None
    source_candidate_after: dict[str, object]
    planned_source_file_changed = False
    source_file_changed = False

    try:
        source_text = _repo_file(resolved_repo, target_source_file).read_text(
            encoding="utf-8"
        )
        if task_id == H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID:
            source_action = _h11_bytesify_object_message_source_action(source_text)
        elif task_id == INICONFIG_SECTION_DEFAULT_TASK_ID:
            source_action = _iniconfig_section_default_source_action(source_text)
        else:
            source_action = _humanize_naturalsize_zero_format_source_action(source_text)
        source_result = materialize_source_region(
            resolved_repo,
            source_action,
            write=write,
        )
        source_file_changed = write
        planned_source_file_changed = source_result.changed_line_count > 0
        source_candidate_after = source_result.to_record()
    except SourceRegionMaterializationError as error:
        if error.residual == "already_applied":
            source_candidate_after = _already_applied_source_record(target_source_file)
        else:
            blockers.append(
                {
                    "field": "source_region",
                    "reason": error.residual,
                    "message": str(error),
                }
            )
            source_candidate_after = {
                "available": False,
                "target_source_file": target_source_file,
                "not_available_reason": error.residual,
            }

    if task_id == H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID:
        test_materialization = _materialize_h11_object_message_test(
            resolved_repo,
            target_test_file=target_test_file,
            write=write and not blockers,
        )
    elif task_id == INICONFIG_SECTION_DEFAULT_TASK_ID:
        test_materialization = _materialize_iniconfig_section_default_tests(
            resolved_repo,
            target_test_file=target_test_file,
            write=write and not blockers,
        )
    else:
        test_materialization = _materialize_humanize_zero_format_tests(
            resolved_repo,
            target_test_file=target_test_file,
            write=write and not blockers,
        )
    test_files_changed = _string_sequence(
        test_materialization["files_changed"],
        field="test_materialization.files_changed",
    )
    test_candidate_after = _mapping(
        test_materialization["candidate_after"],
        field="test_materialization.candidate_after",
    )
    planned_test_files_changed = _string_sequence(
        test_candidate_after.get("planned_changed_files", []),
        field="test_materialization.candidate_after.planned_changed_files",
    )

    production_hashes_after = _file_hashes(resolved_repo, production_files)
    production_changed = [
        path
        for path in production_files
        if production_hashes_before.get(path) != production_hashes_after.get(path)
    ]
    writes = [
        *([target_source_file] if source_file_changed else []),
        *test_files_changed,
    ]
    planned_writes = [
        *([target_source_file] if planned_source_file_changed else []),
        *planned_test_files_changed,
    ]
    writes_outside_allowlist = _paths_outside_allowlist(writes, allowed_write_paths)
    production_scope_violations = [
        path for path in production_changed if path != target_source_file
    ]
    if len(production_changed) > 1 or production_scope_violations:
        blockers.append(
            {
                "field": "production_files",
                "reason": "one_file_production_scope_violation",
                "message": (
                    "candidate changed production files outside "
                    f"{target_source_file}"
                ),
            }
        )
    if writes_outside_allowlist:
        blockers.append(
            {
                "field": "allowed_write_paths",
                "reason": "writes_outside_allowlist",
                "message": "candidate wrote paths outside the task allowlist",
            }
        )

    validation = _deferred_validation_record(validation_commands)
    if validate and not blockers:
        validation = validate_feature_candidate(
            resolved_repo,
            validation_commands=validation_commands,
            timeout_seconds=validation_timeout_seconds,
        )

    status = "blocked" if blockers else "already_applied"
    if not blockers and planned_writes:
        status = "materialized" if write else "planned"

    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation["status"] == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation['status']}"]
        else:
            residual_labels = [CANDIDATE_VALIDATION_DEFERRED]

    candidate_after = {
        "source_file": source_candidate_after,
        "test_file": _json_copy(test_materialization["candidate_after"]),
        "planned_changed_files": _unique(planned_writes),
        "actual_changed_files": _unique(writes),
    }
    mutation_scope = {
        "mode": "one_file_feature",
        "planned_write_files": [target_source_file, target_test_file],
        "files_changed": _unique(writes),
        "allowed_write_paths": list(allowed_write_paths),
        "writes_outside_allowlist": writes_outside_allowlist,
        "production_files": list(production_files),
        "production_files_changed": production_changed,
        "maximum_production_files_changed": 1,
        "allowed_production_file": target_source_file,
        "one_production_file_constraint_preserved": (
            len(production_changed) <= 1 and not production_scope_violations
        ),
    }
    candidate_id = _candidate_id(
        repo_id=repo_id,
        checkout_ref=checkout_ref,
        task_id=task_id,
        source_hash=production_hashes_after.get(target_source_file, ""),
        test_hash=str(
            _mapping(
                test_materialization["candidate_after"],
                field="test_materialization.candidate_after",
            ).get("sha256_after", "")
        ),
    )

    return RealRepoFeatureCandidate(
        candidate_id=candidate_id,
        repo_id=repo_id,
        repo_split=repo_split,
        checkout_ref=checkout_ref,
        task_id=task_id,
        task_type=task_type,
        prompt=prompt,
        status=status,
        target_source_file=target_source_file,
        target_test_file=target_test_file,
        validation_commands=list(validation_commands),
        allowed_write_paths=list(allowed_write_paths),
        hidden_like_checks=list(hidden_like_checks),
        expected_failure_modes=list(expected_failure_modes),
        production_files=list(production_files),
        production_file_hashes_before=production_hashes_before,
        production_file_hashes_after=production_hashes_after,
        source_action=source_action.to_record() if source_action is not None else None,
        candidate_after=candidate_after,
        mutation_scope=mutation_scope,
        validation=validation,
        blockers=blockers,
        residual_labels=residual_labels,
    )


def validate_feature_candidate(
    repo_path: Path,
    *,
    validation_commands: Sequence[str],
    timeout_seconds: int = 120,
) -> dict[str, object]:
    """Run the selected candidate validation command and return metadata."""

    if not validation_commands:
        return {
            "status": "not_run",
            "commands": [],
            "selected_command": None,
            "not_run_reason": "validation_selection_gap",
            "candidate_validation_network_allowed": False,
            "runtime_seconds": 0.0,
        }

    command = validation_commands[0]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        runtime_seconds = round(time.monotonic() - started, 3)
        status = "passed" if result.returncode == 0 else "failed"
        return {
            "status": status,
            "commands": list(validation_commands),
            "selected_command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "runtime_seconds": runtime_seconds,
            "candidate_validation_network_allowed": False,
        }
    except subprocess.TimeoutExpired as error:
        runtime_seconds = round(time.monotonic() - started, 3)
        return {
            "status": "timeout",
            "commands": list(validation_commands),
            "selected_command": command,
            "returncode": None,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
            "runtime_seconds": runtime_seconds,
            "timeout_seconds": timeout_seconds,
            "candidate_validation_network_allowed": False,
        }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for a live source materialization probe."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("examples/real_repo_eval_ladder.json"))
    parser.add_argument("--repo-id", default="h11")
    parser.add_argument("--task-id", default=H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID)
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--validation-timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)

    manifest = load_real_repo_ladder_manifest(args.manifest)
    repo = next(
        item
        for item in _sequence(manifest["repositories"], field="repositories")
        if _mapping(item, field="repository").get("id") == args.repo_id
    )
    repo_record = _mapping(repo, field="repository")
    task = next(
        item
        for item in _sequence(repo_record["tasks"], field="tasks")
        if _mapping(item, field="task").get("id") == args.task_id
    )
    candidate = materialize_real_repo_feature_candidate(
        args.repo_path,
        repo=repo_record,
        task=_mapping(task, field="task"),
        validate=args.validate,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    record = candidate.to_record()
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(_summary(record), sort_keys=True))
    return 0 if candidate.status != "blocked" and candidate.validation.get("status") != "failed" else 1


def _h11_bytesify_object_message_source_action(source: str) -> SourceRegionAction:
    if '"expected bytes-like object, not {}".format(type(s).__name__)' in source:
        raise SourceRegionMaterializationError(
            "h11 bytesify object TypeError message edit is already applied",
            residual="already_applied",
        )
    target_line = _line_number(source, "    return bytes(s)")
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path="h11/_util.py",
            function_name="bytesify",
            region_name="unsupported_object_type_error_message",
            start_line=target_line,
            end_line=target_line,
        ),
        replacement_source="\n".join(
            [
                "    try:",
                "        return bytes(s)",
                "    except TypeError:",
                "        raise TypeError(",
                '            "expected bytes-like object, not {}".format(type(s).__name__)',
                "        ) from None",
            ]
        ),
        constraints=SourceRegionConstraints(max_changed_source_lines=8),
        rationale=(
            "unsupported object TypeError should name the concrete input type "
            "while preserving existing bytes-like and ASCII str behavior"
        ),
    )


def _iniconfig_section_default_source_action(source: str) -> SourceRegionAction:
    if "def get_section(" in source:
        raise SourceRegionMaterializationError(
            "iniconfig get_section default edit is already applied",
            residual="already_applied",
        )
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_DELIMITED_REGION,
        target=SourceRegionTarget(
            file_path="src/iniconfig/__init__.py",
            region_name="optional_section_default_method",
            start_marker="                return value",
            end_marker="    def __getitem__(self, name: str) -> SectionWrapper:",
        ),
        replacement_source="\n".join(
            [
                "",
                "    @overload",
                "    def get_section(self, name: str) -> SectionWrapper | None: ...",
                "",
                "    @overload",
                "    def get_section(self, name: str, default: _D) -> SectionWrapper | _D: ...",
                "",
                "    def get_section(",
                "        self, name: str, default: _D | None = None",
                "    ) -> SectionWrapper | _D | None:",
                "        if name not in self.sections:",
                "            return default",
                "        return SectionWrapper(self, name)",
                "",
                "",
            ]
        ),
        constraints=SourceRegionConstraints(
            max_changed_source_lines=14,
            must_preserve_signature=False,
        ),
        rationale=(
            "add a narrow section lookup helper that leaves __getitem__ KeyError "
            "semantics intact while returning caller-provided defaults for "
            "missing optional sections"
        ),
    )


def _humanize_naturalsize_zero_format_source_action(source: str) -> SourceRegionAction:
    if "zero_format: str | None = None" in source:
        raise SourceRegionMaterializationError(
            "humanize naturalsize zero_format edit is already applied",
            residual="already_applied",
        )

    start_line = _line_number(source, '    format: str = "%.1f",')
    end_line = _line_number(source, "    abs_bytes = abs(bytes_)")
    source_lines = source.splitlines()
    replacement_lines = list(source_lines[start_line - 1 : end_line])
    _insert_after(
        replacement_lines,
        '    format: str = "%.1f",',
        "    zero_format: str | None = None,",
    )
    _insert_after(
        replacement_lines,
        "        format (str): Custom formatter.",
        "        zero_format (str | None): Optional text returned for zero bytes.",
        required=False,
    )
    _insert_after(
        replacement_lines,
        "    abs_bytes = abs(bytes_)",
        "    if abs_bytes == 0 and zero_format is not None:\n"
        "        return zero_format",
    )
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path="src/humanize/filesize.py",
            function_name="naturalsize",
            region_name="zero_format_signature_and_zero_guard",
            start_line=start_line,
            end_line=end_line,
        ),
        replacement_source="\n".join(replacement_lines),
        constraints=SourceRegionConstraints(
            max_changed_source_lines=6,
            must_preserve_signature=False,
        ),
        rationale=(
            "add an optional zero_format argument and return it only for values "
            "whose absolute byte count is zero, before the existing small-byte "
            "formatting branches"
        ),
    )


def _materialize_h11_object_message_test(
    repo: Path,
    *,
    target_test_file: str,
    write: bool,
) -> dict[str, object]:
    target_path = _repo_file(repo, target_test_file)
    before_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    after_text = _merge_h11_object_message_test(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")
    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []
    return {
        "status": status,
        "files_changed": files_changed,
        "candidate_after": _text_candidate_after_record(
            file_path=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            test_case_ids=["h11_bytesify_unsupported_object_type_name"],
            test_functions=["test_bytesify_rejects_unsupported_object_with_type_name"],
        ),
    }


def _merge_h11_object_message_test(existing_text: str) -> str:
    function_name = "test_bytesify_rejects_unsupported_object_with_type_name"
    if f"def {function_name}" in existing_text:
        return existing_text
    append_block = (
        "def test_bytesify_rejects_unsupported_object_with_type_name() -> None:\n"
        "    class UnsupportedThing:\n"
        "        pass\n"
        "\n"
        "    with pytest.raises(TypeError, match=\"UnsupportedThing\") as excinfo:\n"
        "        bytesify(UnsupportedThing())\n"
        "\n"
        "    assert \"bytes-like object\" in str(excinfo.value)\n"
    )
    if not existing_text.strip():
        return (
            "import pytest\n"
            "\n"
            "from .._util import bytesify\n"
            "\n\n"
            + append_block
        )
    return existing_text.rstrip() + "\n\n\n" + append_block


def _materialize_iniconfig_section_default_tests(
    repo: Path,
    *,
    target_test_file: str,
    write: bool,
) -> dict[str, object]:
    target_path = _repo_file(repo, target_test_file)
    before_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    after_text = _merge_iniconfig_section_default_tests(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")
    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []
    return {
        "status": status,
        "files_changed": files_changed,
        "candidate_after": _text_candidate_after_record(
            file_path=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            test_case_ids=[
                "iniconfig_get_section_missing_default",
                "iniconfig_get_section_existing_order",
            ],
            test_functions=[
                "test_get_section_returns_default_for_missing_section",
                "test_get_section_existing_section_preserves_order",
            ],
        ),
    }


def _merge_iniconfig_section_default_tests(existing_text: str) -> str:
    first_function = "test_get_section_returns_default_for_missing_section"
    if f"def {first_function}" in existing_text:
        return existing_text
    append_block = (
        "def test_get_section_returns_default_for_missing_section() -> None:\n"
        "    config = IniConfig(\"x\", data=\"[section]\\nvalue=1\")\n"
        "    default = {\"fallback\": \"value\"}\n"
        "\n"
        "    assert config.get_section(\"missing\", default) is default\n"
        "    assert config.get_section(\"missing\") is None\n"
        "    with pytest.raises(KeyError):\n"
        "        config[\"missing\"]\n"
        "\n\n"
        "def test_get_section_existing_section_preserves_order() -> None:\n"
        "    config = IniConfig(\n"
        "        \"x.ini\",\n"
        "        data=\"[section]\\nsecond = 2\\nfirst = 1\\nthird = 3\",\n"
        "    )\n"
        "    default = {\"fallback\": \"value\"}\n"
        "\n"
        "    section = config.get_section(\"section\", default)\n"
        "\n"
        "    assert section is not default\n"
        "    assert list(section) == [\"second\", \"first\", \"third\"]\n"
        "    assert list(section.items()) == [\n"
        "        (\"second\", \"2\"),\n"
        "        (\"first\", \"1\"),\n"
        "        (\"third\", \"3\"),\n"
        "    ]\n"
    )
    if not existing_text.strip():
        return "import pytest\n\nfrom iniconfig import IniConfig\n\n\n" + append_block
    return existing_text.rstrip() + "\n\n\n" + append_block


def _materialize_humanize_zero_format_tests(
    repo: Path,
    *,
    target_test_file: str,
    write: bool,
) -> dict[str, object]:
    target_path = _repo_file(repo, target_test_file)
    before_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    after_text = _merge_humanize_zero_format_tests(before_text)
    planned_changed_files = [target_test_file] if after_text != before_text else []
    if write and planned_changed_files:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(after_text, encoding="utf-8")
    status = "already_applied"
    files_changed: list[str] = []
    if planned_changed_files:
        status = "materialized" if write else "planned"
        files_changed = list(planned_changed_files) if write else []
    return {
        "status": status,
        "files_changed": files_changed,
        "candidate_after": _text_candidate_after_record(
            file_path=target_test_file,
            before_text=before_text,
            after_text=after_text,
            planned_changed_files=planned_changed_files,
            wrote_file=write and bool(planned_changed_files),
            test_case_ids=[
                "humanize_naturalsize_zero_format_zero_values",
                "humanize_naturalsize_zero_format_default_unchanged",
                "humanize_naturalsize_zero_format_nonzero_ignored",
            ],
            test_functions=[
                "test_naturalsize_zero_format_handles_zero_values",
                "test_naturalsize_zero_format_default_behavior_is_unchanged",
                "test_naturalsize_zero_format_is_only_used_for_zero_values",
            ],
        ),
    }


def _merge_humanize_zero_format_tests(existing_text: str) -> str:
    first_function = "test_naturalsize_zero_format_handles_zero_values"
    if f"def {first_function}" in existing_text:
        return existing_text
    append_block = (
        "def test_naturalsize_zero_format_handles_zero_values() -> None:\n"
        "    assert humanize.naturalsize(0, zero_format=\"empty\") == \"empty\"\n"
        "    assert humanize.naturalsize(-0.0, zero_format=\"empty\") == \"empty\"\n"
        "\n\n"
        "def test_naturalsize_zero_format_default_behavior_is_unchanged() -> None:\n"
        "    assert humanize.naturalsize(0) == \"0 Bytes\"\n"
        "    assert humanize.naturalsize(-0.0) == \"0 Bytes\"\n"
        "\n\n"
        "def test_naturalsize_zero_format_is_only_used_for_zero_values() -> None:\n"
        "    assert humanize.naturalsize(1, zero_format=\"empty\") == \"1 Byte\"\n"
        "    assert humanize.naturalsize(1024, True, zero_format=\"empty\") == \"1.0 KiB\"\n"
        "    assert humanize.naturalsize(1024, False, True, zero_format=\"empty\") == \"1.0K\"\n"
    )
    if not existing_text.strip():
        return "import humanize\n\n\n" + append_block
    return existing_text.rstrip() + "\n\n\n" + append_block


def _text_candidate_after_record(
    *,
    file_path: str,
    before_text: str,
    after_text: str,
    planned_changed_files: Sequence[str],
    wrote_file: bool,
    test_case_ids: Sequence[str] = (),
    test_functions: Sequence[str] = (),
) -> dict[str, object]:
    return {
        "available": True,
        "file_path": file_path,
        "planned_changed_files": list(planned_changed_files),
        "wrote_file": wrote_file,
        "sha256_before": _sha256_text(before_text),
        "sha256_after": _sha256_text(after_text),
        "diff_summary": _diff_summary(before_text, after_text),
        "diff": _unified_diff(before_text, after_text, file_path),
        "ast_delta": python_ast_delta_metadata(before_text, after_text),
        "test_case_ids": list(test_case_ids),
        "test_functions": list(test_functions),
    }


def _already_applied_source_record(file_path: str) -> dict[str, object]:
    return {
        "schema_version": "source-region-candidate-after-v1",
        "status": "already_applied",
        "file_path": file_path,
        "candidate_after": {
            "changed_line_count": 0,
            "added_line_count": 0,
            "removed_line_count": 0,
            "ast_parse_ok": True,
            "diff_summary": {
                "hunk_count": 0,
                "changed_line_count": 0,
                "added_line_count": 0,
                "removed_line_count": 0,
            },
            "diff": "",
        },
    }


def _production_python_files(repo: Path, *, repo_id: str) -> list[str]:
    package_roots = {
        "h11": repo / "h11",
        "iniconfig": repo / "src" / "iniconfig",
        "humanize": repo / "src" / "humanize",
    }
    package_root = package_roots.get(repo_id)
    if package_root is None:
        return []
    if not package_root.exists():
        return []
    paths = []
    for path in package_root.rglob("*.py"):
        relative = path.relative_to(repo).as_posix()
        if "/tests/" in f"/{relative}/":
            continue
        paths.append(relative)
    return sorted(paths)


def _file_hashes(repo: Path, paths: Sequence[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        file_path = _repo_file(repo, path)
        if file_path.exists() and file_path.is_file():
            hashes[path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return hashes


def _paths_outside_allowlist(paths: Sequence[str], allowlist: Sequence[str]) -> list[str]:
    allowed = {_normalize_relative_path(path) for path in allowlist}
    return [
        path
        for path in _unique(paths)
        if _normalize_relative_path(path) not in allowed
    ]


def _repo_file(repo: Path, path: str) -> Path:
    return repo / _normalize_relative_path(path)


def _normalize_relative_path(path: str) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"path must be relative to the repository root: {path}")
    return pure.as_posix()


def _line_number(source: str, needle: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if line == needle:
            return index
    raise SourceRegionMaterializationError(
        f"target source line not found: {needle}",
        residual="target_selection",
    )


def _insert_after(
    lines: list[str],
    needle: str,
    insertion: str,
    *,
    required: bool = True,
) -> None:
    for index, line in enumerate(lines):
        if line == needle:
            lines[index + 1 : index + 1] = insertion.splitlines()
            return
    if required:
        raise SourceRegionMaterializationError(
            f"target source line not found: {needle}",
            residual="target_selection",
        )


def _diff_summary(before_text: str, after_text: str) -> dict[str, int]:
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    added = 0
    removed = 0
    for tag, start_a, end_a, start_b, end_b in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed += end_a - start_a
        added += end_b - start_b
    diff = _unified_diff(before_text, after_text, "candidate")
    return {
        "hunk_count": diff.count("\n@@ "),
        "changed_line_count": added + removed,
        "added_line_count": added,
        "removed_line_count": removed,
    }


def _unified_diff(before_text: str, after_text: str, file_path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )


def _deferred_validation_record(validation_commands: Sequence[str]) -> dict[str, object]:
    selected = validation_commands[0] if validation_commands else None
    return {
        "status": "not_run",
        "commands": list(validation_commands),
        "selected_command": selected,
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
        "runtime_seconds": 0.0,
    }


def _candidate_id(
    *,
    repo_id: str,
    checkout_ref: str,
    task_id: str,
    source_hash: str,
    test_hash: str,
) -> str:
    payload = "|".join([repo_id, checkout_ref, task_id, source_hash, test_hash])
    return "feature-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _summary(record: Mapping[str, object]) -> dict[str, object]:
    mutation_scope = _mapping(record.get("mutation_scope"), field="mutation_scope")
    validation = _mapping(record.get("validation"), field="validation")
    return {
        "candidate_id": record.get("candidate_id"),
        "task_id": record.get("task_id"),
        "status": record.get("status"),
        "files_changed": mutation_scope.get("files_changed", []),
        "production_files_changed": mutation_scope.get("production_files_changed", []),
        "validation_status": validation.get("status"),
        "runtime_seconds": validation.get("runtime_seconds"),
        "zero_hosted_usage_confirmed": record.get("zero_hosted_usage_confirmed"),
        "blockers": record.get("blockers", []),
    }


def _blocker_error(
    message: str,
    *,
    field: str,
    reason: str,
) -> RealRepoFeatureMaterializerError:
    return RealRepoFeatureMaterializerError(
        message,
        blocker={"field": field, "reason": reason, "message": message},
    )


def _required_str(mapping: Mapping[str, object], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_sequence(value: object, *, field: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{field} must be a sequence of strings")
    result = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field} must contain only strings")
        result.append(item)
    return result


def _sequence(value: object, *, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{field} must be a sequence")
    return value


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))


if __name__ == "__main__":
    raise SystemExit(main())
