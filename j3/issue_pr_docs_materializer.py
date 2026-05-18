"""Bounded docs materializer for Click issue/PR replay auxiliary paths."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_preflight import (
    load_issue_pr_replay_manifest,
    select_issue_pr_replay_record,
)


ISSUE_PR_DOCS_MATERIALIZER_SCHEMA_VERSION = "issue-pr-docs-materializer-v1"
ISSUE_PR_DOCS_MATERIALIZER_KIND = "issue_pr_docs_materializer"
CLICK_DEFAULT_MAP_REPLAY_ID = "pallets__click-issue-2745-pr-3364"
CLICK_COMMANDS_DOCS_PATH = "docs/commands.md"
CLICK_COMMANDS_DOCS_ACTION_FAMILY = (
    "click_default_map_docs_section_generator_v1+myst_markdown_section_insert_v1"
)
CLICK_COMMANDS_DOCS_SECTION_HEADING = "### Multi-value parameters"
CLICK_COMMANDS_DOCS_INSERT_ANCHOR = "\n## Context Defaults\n"
DEFAULT_DOCS_VALIDATION_COMMAND = (
    "python -m sphinx -W -b dirhtml docs /tmp/j3-data-019-docs-dirhtml"
)


class IssuePrDocsMaterializerError(ValueError):
    """Raised when the bounded docs materializer cannot proceed."""

    def __init__(self, message: str, *, blocker: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.blocker = blocker or {
            "field": "issue_pr_docs_materializer",
            "reason": "docs_materialization_blocked",
            "message": message,
        }


@dataclass(frozen=True, slots=True)
class IssuePrDocsMaterialization:
    """Structured result for one bounded issue/PR docs materialization."""

    candidate_id: str
    replay_id: str
    repo: str
    repo_before_ref: str
    prompt: str
    status: str
    action_family: str
    target_path: str
    generated_section: str
    evidence: dict[str, object] = field(default_factory=dict)
    actions: list[dict[str, object]] = field(default_factory=list)
    materialization: dict[str, object] = field(default_factory=dict)
    candidate_diff: dict[str, object] = field(default_factory=dict)
    mutation_scope: dict[str, object] = field(default_factory=dict)
    validation: dict[str, object] = field(default_factory=dict)
    residual_labels: list[str] = field(default_factory=list)
    blockers: list[dict[str, str]] = field(default_factory=list)
    zero_hosted_usage_confirmed: bool = True

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": ISSUE_PR_DOCS_MATERIALIZER_SCHEMA_VERSION,
            "record_kind": ISSUE_PR_DOCS_MATERIALIZER_KIND,
            "candidate_id": self.candidate_id,
            "replay_id": self.replay_id,
            "repo": self.repo,
            "repo_before_ref": self.repo_before_ref,
            "prompt": self.prompt,
            "status": self.status,
            "action_family": self.action_family,
            "target_path": self.target_path,
            "generated_section": self.generated_section,
            "evidence": _json_copy(self.evidence),
            "actions": _json_copy(self.actions),
            "materialization": _json_copy(self.materialization),
            "candidate_diff": _json_copy(self.candidate_diff),
            "mutation_scope": _json_copy(self.mutation_scope),
            "validation": _json_copy(self.validation),
            "residual_labels": list(self.residual_labels),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "zero_hosted_usage_confirmed": self.zero_hosted_usage_confirmed,
        }


def build_click_default_map_commands_docs_section() -> str:
    """Generate the bounded Click default_map multi-value docs section."""

    return (
        "### Multi-value parameters\n"
        "\n"
        "When a `default_map` value is a string for a parameter with `nargs > 1` or a\n"
        "{class}`Tuple` type, the string is split automatically, the same way an\n"
        "environment variable would be. By default, values are split on whitespace. See\n"
        "[Multiple Options from Environment\n"
        "Values](options.md#multiple-options-from-environment-values) for details on\n"
        "splitting behavior.\n"
        "\n"
        "```python\n"
        "default_map = {\n"
        '    "draw": {\n'
        '        "point": "3 4",  # split into ("3", "4") for nargs=2\n'
        '        "color": "red",  # passed as-is for nargs=1\n'
        "    }\n"
        "}\n"
        "```\n"
        "\n"
        "You can also pass an already-structured tuple or list, which will be used as-is\n"
        "without splitting:\n"
        "\n"
        "```python\n"
        "default_map = {\n"
        '    "draw": {\n'
        '        "point": (3, 4),  # used directly\n'
        "    }\n"
        "}\n"
        "```\n"
    )


def run_click_commands_docs_materializer(
    repo_path: Path,
    *,
    manifest_path: Path = Path("examples/issue_pr_mini_replay/manifest.json"),
    replay_id: str = CLICK_DEFAULT_MAP_REPLAY_ID,
    candidate_artifact_path: Path | None = Path("/tmp/j3-data-014-live/candidate.json"),
    auxiliary_gap_audit_path: Path | None = Path("/tmp/j3-data-017-aux-gap/audit.jsonl"),
    write: bool = True,
    validate: bool = False,
    validation_command: str | None = DEFAULT_DOCS_VALIDATION_COMMAND,
    validation_timeout_seconds: int = 180,
) -> IssuePrDocsMaterialization:
    """Generate and insert only the Click commands.md multi-value section."""

    if replay_id != CLICK_DEFAULT_MAP_REPLAY_ID:
        raise IssuePrDocsMaterializerError(
            f"unsupported replay id: {replay_id}",
            blocker={
                "field": "replay_id",
                "reason": "unsupported_issue_pr_docs_materializer",
                "message": "DATA-019 may materialize only Click #2745/#3364 docs.",
            },
        )

    resolved_repo = repo_path.expanduser().resolve()
    if not resolved_repo.is_dir():
        raise IssuePrDocsMaterializerError(
            f"repo does not exist: {resolved_repo}",
            blocker={
                "field": "repo_path",
                "reason": "missing_repo_before_checkout",
                "message": f"repo does not exist: {resolved_repo}",
            },
        )

    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_issue_pr_replay_manifest(manifest_path)
    replay_record = select_issue_pr_replay_record(manifest, replay_id)
    repo = _required_str(replay_record, "repo")
    prompt = _required_str(replay_record, "prompt_text")
    repo_before_ref = _mapping(replay_record.get("repo_before_ref"))
    expected_sha = _required_str(repo_before_ref, "sha")
    accepted_change = _mapping(replay_record.get("accepted_change"))
    accepted_paths = _string_sequence(accepted_change.get("changed_files"))

    actions: list[dict[str, object]] = [
        {
            "kind": "select_replay_row",
            "target": replay_id,
            "payload": {
                "manifest_path": str(manifest_path),
                "repo": repo,
                "repo_before_ref": expected_sha,
            },
        }
    ]
    blockers: list[dict[str, str]] = []
    pre_existing_changed_files = _git_changed_files(resolved_repo)
    head = _git_stdout(resolved_repo, ("rev-parse", "HEAD"))
    if head:
        actions.append(
            {
                "kind": "verify_repo_before_ref",
                "target": ".",
                "payload": {"expected": expected_sha, "actual": head},
            }
        )
        if head != expected_sha:
            blockers.append(
                {
                    "field": "repo_before_ref",
                    "reason": "repo_before_ref_mismatch",
                    "message": f"expected {expected_sha}, got {head}",
                }
            )

    target_file = resolved_repo / CLICK_COMMANDS_DOCS_PATH
    before_text = ""
    after_text = ""
    generated_section = build_click_default_map_commands_docs_section()
    materialization: dict[str, object] = {
        "status": "not_attempted",
        "target_path": CLICK_COMMANDS_DOCS_PATH,
    }

    content_blocker = validate_click_default_map_commands_docs_section(generated_section)
    if content_blocker is not None:
        blockers.append(content_blocker)

    if not blockers:
        try:
            before_text = target_file.read_text(encoding="utf-8")
            after_text = insert_click_default_map_commands_docs_section(
                before_text,
                generated_section,
            )
            if write:
                target_file.write_text(after_text, encoding="utf-8")
            materialization = {
                "status": "materialized",
                "target_path": CLICK_COMMANDS_DOCS_PATH,
                "insert_anchor": "before ## Context Defaults",
                "section_heading": CLICK_COMMANDS_DOCS_SECTION_HEADING,
                "wrote_file": write,
                "generated_line_count": len(generated_section.splitlines()),
                "preserved_unrelated_content": _unrelated_content_preserved(
                    before_text,
                    after_text,
                    generated_section,
                ),
            }
            actions.append(
                {
                    "kind": "generate_click_default_map_docs_section",
                    "target": CLICK_COMMANDS_DOCS_PATH,
                    "payload": {
                        "generator": "local_template_from_DATA_009_prompt_spec_facts",
                        "section_heading": CLICK_COMMANDS_DOCS_SECTION_HEADING,
                        "mentions": ["nargs > 1", "{class}`Tuple`"],
                        "includes_whitespace_splitting_example": True,
                    },
                }
            )
            actions.append(
                {
                    "kind": "myst_markdown_section_insert",
                    "target": CLICK_COMMANDS_DOCS_PATH,
                    "payload": {"anchor": "before ## Context Defaults"},
                }
            )
        except OSError as error:
            blockers.append(
                {
                    "field": "materialization",
                    "reason": "target_file_unavailable",
                    "message": str(error),
                }
            )
            materialization = {
                "status": "blocked",
                "target_path": CLICK_COMMANDS_DOCS_PATH,
                "not_available_reason": "target_file_unavailable",
            }
        except IssuePrDocsMaterializerError as error:
            blockers.append(error.blocker)
            materialization = {
                "status": "blocked",
                "target_path": CLICK_COMMANDS_DOCS_PATH,
                "not_available_reason": error.blocker.get("reason"),
            }

    candidate_diff = _candidate_diff(
        before_text=before_text,
        after_text=after_text,
        path=CLICK_COMMANDS_DOCS_PATH,
    )
    post_changed_files = _git_changed_files(resolved_repo)
    files_changed = post_changed_files if write else []
    writes_outside_target = sorted(
        path for path in files_changed if path != CLICK_COMMANDS_DOCS_PATH
    )
    mutation_scope = {
        "mode": "issue_pr_docs_materializer",
        "target_path": CLICK_COMMANDS_DOCS_PATH,
        "planned_write_files": [CLICK_COMMANDS_DOCS_PATH],
        "files_changed": files_changed,
        "pre_existing_changed_files": pre_existing_changed_files,
        "accepted_change_paths": accepted_paths,
        "allowed_docs_write_path_check_passed": files_changed
        in ([], [CLICK_COMMANDS_DOCS_PATH]),
        "writes_outside_target": writes_outside_target,
        "non_docs_accepted_paths_not_materialized": [
            path for path in accepted_paths if path != CLICK_COMMANDS_DOCS_PATH
        ],
    }
    if writes_outside_target:
        blockers.append(
            {
                "field": "mutation_scope",
                "reason": "unexpected_non_docs_mutation",
                "message": (
                    "docs materializer changed files outside docs/commands.md: "
                    + ", ".join(writes_outside_target)
                ),
            }
        )

    validation = _validation_not_run(validation_command)
    if validate and not blockers:
        validation = _run_validation_command(
            repo_path=resolved_repo,
            command=validation_command,
            timeout_seconds=validation_timeout_seconds,
        )
        if validation.get("status") == "blocked":
            blockers.append(
                {
                    "field": "docs_validation",
                    "reason": str(validation.get("failure_family") or "docs_build_blocked"),
                    "message": str(validation.get("failure_summary") or ""),
                }
            )

    residual_labels = _residual_labels(blockers=blockers, validation=validation)
    if materialization.get("status") == "materialized":
        residual_labels.insert(0, "docs_commands_section_materialized")
    status = (
        "validated"
        if materialization.get("status") == "materialized"
        and validation.get("status") == "passed"
        and not writes_outside_target
        else "blocked"
        if blockers
        else "materialized"
    )

    evidence = _build_evidence(
        manifest_path=manifest_path,
        manifest=manifest,
        replay_record=replay_record,
        candidate_artifact_path=candidate_artifact_path,
        auxiliary_gap_audit_path=auxiliary_gap_audit_path,
    )
    candidate_id = _candidate_id(
        replay_id=replay_id,
        generated_section=generated_section,
        candidate_diff=candidate_diff,
    )
    return IssuePrDocsMaterialization(
        candidate_id=candidate_id,
        replay_id=replay_id,
        repo=repo,
        repo_before_ref=expected_sha,
        prompt=prompt,
        status=status,
        action_family=CLICK_COMMANDS_DOCS_ACTION_FAMILY,
        target_path=CLICK_COMMANDS_DOCS_PATH,
        generated_section=generated_section,
        evidence=evidence,
        actions=actions,
        materialization=materialization,
        candidate_diff=candidate_diff,
        mutation_scope=mutation_scope,
        validation=validation,
        residual_labels=residual_labels,
        blockers=blockers,
    )


def validate_click_default_map_commands_docs_section(
    section: str,
) -> dict[str, str] | None:
    """Return a blocker if the generated section misses the DATA-019 contract."""

    required = {
        "expected_heading": CLICK_COMMANDS_DOCS_SECTION_HEADING,
        "nargs_behavior": "nargs > 1",
        "tuple_behavior": "Tuple",
        "whitespace_splitting_example": '"point": "3 4"',
    }
    for reason, needle in required.items():
        if needle not in section:
            return {
                "field": "generated_section",
                "reason": f"missing_{reason}",
                "message": f"generated section does not contain {needle!r}",
            }
    return None


def insert_click_default_map_commands_docs_section(
    commands_md_text: str,
    section: str,
) -> str:
    """Insert the generated section before the Context Defaults docs section."""

    if CLICK_COMMANDS_DOCS_SECTION_HEADING in commands_md_text:
        raise IssuePrDocsMaterializerError(
            "commands docs already contain the Multi-value parameters section",
            blocker={
                "field": CLICK_COMMANDS_DOCS_PATH,
                "reason": "duplicate_docs_section",
                "message": "commands docs already contain the target section heading",
            },
        )
    if CLICK_COMMANDS_DOCS_INSERT_ANCHOR not in commands_md_text:
        raise IssuePrDocsMaterializerError(
            "commands docs insertion anchor not found",
            blocker={
                "field": CLICK_COMMANDS_DOCS_PATH,
                "reason": "missing_context_defaults_anchor",
                "message": "expected anchor '## Context Defaults' was not found",
            },
        )
    insertion = f"\n{section}"
    return commands_md_text.replace(CLICK_COMMANDS_DOCS_INSERT_ANCHOR, insertion + CLICK_COMMANDS_DOCS_INSERT_ANCHOR, 1)


def write_issue_pr_docs_materialization_json(record: Mapping[str, object], path: Path) -> Path:
    """Write one docs materialization record as JSON."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(dict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved


def write_issue_pr_docs_materialization_report(
    record: Mapping[str, object],
    path: Path,
) -> Path:
    """Write a compact Markdown report for the docs materialization attempt."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    mutation_scope = _mapping(record.get("mutation_scope"))
    validation = _mapping(record.get("validation"))
    candidate_diff = _mapping(record.get("candidate_diff"))
    lines = [
        "# DATA-019 Click Commands Docs Materializer",
        "",
        "Bounded materialization attempt for the Click #2745/#3364 `docs/commands.md` auxiliary gap.",
        "",
        "## Summary",
        "",
        f"- Replay: `{record.get('replay_id')}`",
        f"- Status: `{record.get('status')}`",
        f"- Target path: `{record.get('target_path')}`",
        f"- Action family: `{record.get('action_family')}`",
        f"- Files changed: `{_json_inline(mutation_scope.get('files_changed', []))}`",
        "- Writes outside `docs/commands.md`: "
        f"`{_json_inline(mutation_scope.get('writes_outside_target', []))}`",
        f"- Residual labels: `{_json_inline(record.get('residual_labels', []))}`",
        f"- Validation command: `{validation.get('command')}`",
        f"- Validation status: `{validation.get('status')}`",
        f"- Validation runtime seconds: `{validation.get('runtime_seconds')}`",
        "",
        "## Section Contract",
        "",
        "- Heading: `### Multi-value parameters`",
        "- Mentions: `nargs > 1` and the `{class}` role for `Tuple`",
        "- Whitespace-splitting example: `\"point\": \"3 4\"`",
        "- Insertion anchor: before `## Context Defaults`",
        "",
        "## Candidate Diff",
        "",
        "```diff",
        str(candidate_diff.get("diff") or ""),
        "```",
        "",
        "## Blockers",
        "",
    ]
    blockers = record.get("blockers")
    if isinstance(blockers, list) and blockers:
        for blocker in blockers:
            if isinstance(blocker, Mapping):
                lines.append(
                    f"- `{blocker.get('reason')}`: {blocker.get('message')}"
                )
    else:
        lines.append("- none")
    resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for DATA-019 Click docs materialization."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("examples/issue_pr_mini_replay/manifest.json"),
    )
    parser.add_argument("--replay-id", default=CLICK_DEFAULT_MAP_REPLAY_ID)
    parser.add_argument("--candidate-artifact", type=Path, default=Path("/tmp/j3-data-014-live/candidate.json"))
    parser.add_argument("--auxiliary-gap-audit", type=Path, default=Path("/tmp/j3-data-017-aux-gap/audit.jsonl"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--validation-command", default=DEFAULT_DOCS_VALIDATION_COMMAND)
    parser.add_argument("--validation-timeout-seconds", type=int, default=180)
    args = parser.parse_args(argv)

    result = run_click_commands_docs_materializer(
        args.repo_path,
        manifest_path=args.manifest,
        replay_id=args.replay_id,
        candidate_artifact_path=args.candidate_artifact,
        auxiliary_gap_audit_path=args.auxiliary_gap_audit,
        write=not args.dry_run,
        validate=args.validate,
        validation_command=args.validation_command,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    record = result.to_record()
    out_path = write_issue_pr_docs_materialization_json(record, args.out)
    if args.report is not None:
        write_issue_pr_docs_materialization_report(record, args.report)
    print(
        json.dumps(
            {
                "schema_version": ISSUE_PR_DOCS_MATERIALIZER_SCHEMA_VERSION,
                "record_kind": "issue_pr_docs_materializer_summary",
                "outcome_path": str(out_path),
                "report_path": str(args.report.expanduser().resolve())
                if args.report is not None
                else None,
                "status": record["status"],
                "files_changed": record["mutation_scope"]["files_changed"],
                "validation_status": record["validation"]["status"],
                "residual_labels": record["residual_labels"],
            },
            sort_keys=True,
        )
    )
    return 0


def _build_evidence(
    *,
    manifest_path: Path,
    manifest: Mapping[str, object],
    replay_record: Mapping[str, object],
    candidate_artifact_path: Path | None,
    auxiliary_gap_audit_path: Path | None,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "manifest": {
            "path": str(manifest_path),
            "schema_version": manifest.get("schema_version"),
            "curated_at": manifest.get("curated_at"),
            "prompt_source": replay_record.get("prompt_source"),
            "repo_before_ref": replay_record.get("repo_before_ref"),
            "accepted_change": replay_record.get("accepted_change"),
            "stable_split": replay_record.get("stable_split"),
        },
        "data019_scope": {
            "source": "DATA-017 docs/commands.md auxiliary gap",
            "target_path": CLICK_COMMANDS_DOCS_PATH,
            "non_targets_intentionally_not_materialized": [
                "CHANGES.rst",
                "docs/conf.py",
                "src/click/core.py",
                "tests/test_defaults.py",
            ],
        },
    }
    if candidate_artifact_path is not None:
        candidate = _load_json_if_available(candidate_artifact_path)
        evidence["data014_candidate"] = _candidate_provenance(
            candidate,
            candidate_artifact_path,
        )
    if auxiliary_gap_audit_path is not None:
        evidence["data017_auxiliary_gap"] = _auxiliary_gap_provenance(
            auxiliary_gap_audit_path,
            replay_id=str(replay_record.get("id") or ""),
        )
    return evidence


def _candidate_provenance(
    candidate: Mapping[str, object] | None,
    path: Path,
) -> dict[str, object]:
    if candidate is None:
        return {"path": str(path.expanduser().resolve()), "status": "unavailable"}
    mutation_scope = _mapping(candidate.get("mutation_scope"))
    return {
        "path": str(path.expanduser().resolve()),
        "status": "loaded",
        "candidate_id": candidate.get("candidate_id"),
        "record_kind": candidate.get("record_kind"),
        "schema_version": candidate.get("schema_version"),
        "action_family": candidate.get("action_family"),
        "materialized_files_changed": mutation_scope.get("files_changed", []),
        "materialization_gap_paths": mutation_scope.get("materialization_gap_paths", []),
        "residual_labels": candidate.get("residual_labels", []),
    }


def _auxiliary_gap_provenance(path: Path, *, replay_id: str) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return {"path": str(resolved), "status": "unavailable"}
    rows = []
    for line in resolved.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict) and value.get("replay_id") == replay_id:
            rows.append(value)
    docs_rows = [row for row in rows if row.get("path") == CLICK_COMMANDS_DOCS_PATH]
    docs_row = docs_rows[0] if docs_rows else {}
    return {
        "path": str(resolved),
        "status": "loaded",
        "row_count": len(rows),
        "docs_commands_classification": docs_row.get("classification"),
        "docs_commands_proposed_action_family": docs_row.get("proposed_action_family"),
        "docs_commands_validation_cost": docs_row.get("validation_cost"),
    }


def _load_json_if_available(path: Path) -> Mapping[str, object] | None:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return None
    value = json.loads(resolved.read_text(encoding="utf-8"))
    return value if isinstance(value, Mapping) else None


def _validation_not_run(command: str | None) -> dict[str, object]:
    return {
        "status": "not_run",
        "command": command,
        "runtime_seconds": 0.0,
        "docs_build_passed": False,
        "failure_family": "not_requested",
    }


def _run_validation_command(
    *,
    repo_path: Path,
    command: str | None,
    timeout_seconds: int,
) -> dict[str, object]:
    if not command:
        return {
            "status": "blocked",
            "command": command,
            "runtime_seconds": 0.0,
            "docs_build_passed": False,
            "failure_family": "missing_docs_validation_command",
            "failure_summary": "no validation command was provided",
        }
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        runtime = round(time.monotonic() - started, 3)
        return {
            "status": "passed" if completed.returncode == 0 else "blocked",
            "command": command,
            "exit_code": completed.returncode,
            "runtime_seconds": runtime,
            "docs_build_passed": completed.returncode == 0,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
            "failure_family": "none"
            if completed.returncode == 0
            else _classify_docs_validation_failure(completed.stderr + completed.stdout),
            "failure_summary": _tail(completed.stderr or completed.stdout, lines=8),
        }
    except subprocess.TimeoutExpired as error:
        return {
            "status": "blocked",
            "command": command,
            "exit_code": None,
            "runtime_seconds": round(time.monotonic() - started, 3),
            "docs_build_passed": False,
            "timed_out": True,
            "stdout_tail": _tail(error.stdout or ""),
            "stderr_tail": _tail(error.stderr or ""),
            "failure_family": "docs_validation_timeout",
            "failure_summary": f"timed out after {timeout_seconds}s",
        }
    except OSError as error:
        return {
            "status": "blocked",
            "command": command,
            "exit_code": None,
            "runtime_seconds": round(time.monotonic() - started, 3),
            "docs_build_passed": False,
            "failure_family": "docs_validation_command_unavailable",
            "failure_summary": str(error),
        }


def _classify_docs_validation_failure(output: str) -> str:
    lowered = output.lower()
    if "no module named sphinx" in lowered or "sphinx-build: command not found" in lowered:
        return "docs_dependency_missing"
    if (
        "undefined label" in lowered
        or "unknown target name" in lowered
        or "local id not found" in lowered
    ):
        return "docs_reference_resolution_failure"
    if "warning" in lowered:
        return "docs_build_warning_as_error"
    return "docs_build_command_failed"


def _candidate_diff(*, before_text: str, after_text: str, path: str) -> dict[str, object]:
    if not before_text and not after_text:
        return {
            "changed_files": [],
            "diff": "",
            "diff_summary": {"added_line_count": 0, "removed_line_count": 0, "hunk_count": 0},
        }
    diff_lines = list(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    return {
        "changed_files": [path] if before_text != after_text else [],
        "diff": "\n".join(diff_lines),
        "diff_summary": {
            "added_line_count": added,
            "removed_line_count": removed,
            "hunk_count": sum(1 for line in diff_lines if line.startswith("@@")),
        },
    }


def _unrelated_content_preserved(before_text: str, after_text: str, section: str) -> bool:
    return after_text.replace("\n" + section, "", 1) == before_text


def _git_changed_files(repo_path: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=repo_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _git_stdout(repo_path: Path, args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _residual_labels(
    *,
    blockers: Sequence[Mapping[str, str]],
    validation: Mapping[str, object],
) -> list[str]:
    labels = []
    validation_status = validation.get("status")
    if validation_status == "passed":
        labels.append("docs_validation_passed")
    elif validation_status == "blocked":
        labels.append("docs_validation_blocked")
        failure_family = validation.get("failure_family")
        if failure_family and failure_family != "none":
            labels.append(str(failure_family))
    elif validation_status == "not_run":
        labels.append("docs_validation_not_run")
    for blocker in blockers:
        reason = blocker.get("reason")
        if reason and reason not in labels:
            labels.append(reason)
    return labels


def _candidate_id(
    *,
    replay_id: str,
    generated_section: str,
    candidate_diff: Mapping[str, object],
) -> str:
    digest = hashlib.sha256()
    digest.update(replay_id.encode())
    digest.update(b"\0")
    digest.update(generated_section.encode())
    digest.update(b"\0")
    digest.update(str(candidate_diff.get("diff", "")).encode())
    return f"issue-pr-docs-materializer/{replay_id}/{digest.hexdigest()[:16]}"


def _required_str(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise IssuePrDocsMaterializerError(
            f"missing required string field {key!r}",
            blocker={
                "field": key,
                "reason": "missing_required_manifest_field",
                "message": f"missing required string field {key!r}",
            },
        )
    return value


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _json_inline(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _tail(output: str | bytes, *, lines: int = 20) -> str:
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    return "\n".join(output.splitlines()[-lines:])


if __name__ == "__main__":
    raise SystemExit(main())
