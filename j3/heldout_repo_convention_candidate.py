"""Held-out repo-convention candidate materialization with reusable actions."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from j3.ast_delta import python_ast_delta_metadata
from j3.heldout_source_region_candidate import (
    _accepted_diff_comparison,
    _deferred_validation,
    _diff_summary,
    _file_hashes,
    _git_changed_files,
    _git_diff,
    _git_stdout,
    _json_copy,
    _paths_outside_allowlist,
    _run_validation,
    _sha256_text,
    _unified_diff,
    _validate_relative_path,
)


REPO_CONVENTION_CANDIDATE_SCHEMA_VERSION = "heldout-repo-convention-candidate-v1"
PYTEST_FIXTURE_INSERTION_SCHEMA_VERSION = "repo-convention-pytest-fixture-insertion-v1"
DEFAULT_REQUESTS_CLEAN_PROXY_BASE_REF = (
    "e8d2c015eecda8273612dd4562425e00cd164ba5"
)
DEFAULT_REQUESTS_CLEAN_PROXY_HEAD_REF = (
    "da905d0eb1de1184d323d39dfc2ce2b423df7bee"
)
DEFAULT_REQUESTS_CLEAN_PROXY_VALIDATION_COMMAND = (
    "HTTP_PROXY=http://127.0.0.1:1 "
    "HTTPS_PROXY=http://127.0.0.1:1 "
    "ALL_PROXY=http://127.0.0.1:1 "
    "PYTHONPATH=src python -m pytest "
    "tests/test_requests.py::TestRequests::test_HTTP_200_OK_GET_ALTERNATIVE -q"
)
REQUESTS_CONFTEST_PATH = "tests/conftest.py"


class RepoConventionCandidateError(ValueError):
    """Raised when a repo-convention candidate cannot be built."""

    def __init__(self, message: str, *, blocker: dict[str, str]) -> None:
        super().__init__(message)
        self.blocker = blocker


@dataclass(frozen=True, slots=True)
class PytestFixtureInsertionAction:
    """Reusable repo-convention action for inserting a pytest fixture."""

    target_file: str
    anchor_function_name: str
    fixture_name: str
    insertion_source: str
    kind: str = "insert_pytest_fixture_after_anchor"
    schema_version: str = PYTEST_FIXTURE_INSERTION_SCHEMA_VERSION
    max_added_lines: int = 20
    require_conftest_target: bool = True
    require_local_pytest_fixture_convention: bool = True
    require_autouse_fixture: bool = False
    rationale: str | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.target_file)
        if self.require_conftest_target and not self.target_file.endswith("conftest.py"):
            raise ValueError("target_file must be a conftest.py path")
        if not self.anchor_function_name:
            raise ValueError("anchor_function_name is required")
        if not self.fixture_name:
            raise ValueError("fixture_name is required")
        if self.max_added_lines < 1:
            raise ValueError("max_added_lines must be >= 1")

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "target": {
                "file_path": self.target_file,
                "anchor_function_name": self.anchor_function_name,
                "fixture_name": self.fixture_name,
                "position": "after_anchor_function",
            },
            "constraints": {
                "max_added_lines": self.max_added_lines,
                "must_parse_ast": True,
                "require_conftest_target": self.require_conftest_target,
                "require_local_pytest_fixture_convention": (
                    self.require_local_pytest_fixture_convention
                ),
                "require_autouse_fixture": self.require_autouse_fixture,
            },
            "insertion_source": self.insertion_source,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class RepoConventionSpec:
    """Parameterized repo-convention candidate replay spec."""

    candidate_id: str
    repo_id: str
    repo_url: str
    repo_split: str
    base_ref: str
    accepted_head_ref: str
    reference_pr_url: str
    prompt: str
    validation_command: str
    allowed_write_paths: tuple[str, ...]
    fixture_action: PytestFixtureInsertionAction
    action_family_reuse_evidence: tuple[dict[str, object], ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        for path in self.allowed_write_paths:
            _validate_relative_path(path)


@dataclass(frozen=True, slots=True)
class PytestFixtureInsertionResult:
    """Candidate-after metadata for a pytest fixture insertion action."""

    status: str
    target_file: str
    fixture_name: str
    insertion_line: int | None
    added_line_count: int
    diff: str
    diff_summary: dict[str, object]
    ast_delta: dict[str, object]
    ast_parse_ok: bool
    convention_evidence: dict[str, object]
    sha256_before: str
    sha256_after: str
    patched_source: str = field(repr=False)
    wrote_file: bool = False

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "pytest-fixture-insertion-candidate-after-v1",
            "status": self.status,
            "target_file": self.target_file,
            "fixture_name": self.fixture_name,
            "insertion_line": self.insertion_line,
            "wrote_file": self.wrote_file,
            "convention_evidence": _json_copy(self.convention_evidence),
            "candidate_after": {
                "added_line_count": self.added_line_count,
                "diff_summary": dict(self.diff_summary),
                "diff": self.diff,
                "ast_parse_ok": self.ast_parse_ok,
                "ast_delta": _json_copy(self.ast_delta),
                "sha256_before": self.sha256_before,
                "sha256_after": self.sha256_after,
            },
        }


@dataclass(frozen=True, slots=True)
class RepoConventionCandidate:
    """Structured candidate record for a held-out repo-convention attempt."""

    candidate_id: str
    repo_id: str
    repo_url: str
    repo_split: str
    base_ref: str
    accepted_head_ref: str
    reference_pr_url: str
    prompt: str
    status: str
    action_records: list[dict[str, object]]
    action_family_reuse_evidence: list[dict[str, object]]
    validation_command: str
    allowed_write_paths: list[str]
    candidate_after: dict[str, object]
    mutation_scope: dict[str, object]
    accepted_diff_comparison: dict[str, object]
    validation: dict[str, object]
    blockers: list[dict[str, str]]
    residual_labels: list[str]
    zero_hosted_llm_source_judgment: bool = True

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": REPO_CONVENTION_CANDIDATE_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "repo_id": self.repo_id,
            "repo_url": self.repo_url,
            "repo_split": self.repo_split,
            "base_ref": self.base_ref,
            "accepted_head_ref": self.accepted_head_ref,
            "reference_pr_url": self.reference_pr_url,
            "prompt": self.prompt,
            "status": self.status,
            "action_records": _json_copy(self.action_records),
            "action_family_reuse_evidence": _json_copy(
                self.action_family_reuse_evidence
            ),
            "validation_command": self.validation_command,
            "allowed_write_paths": list(self.allowed_write_paths),
            "candidate_after": _json_copy(self.candidate_after),
            "mutation_scope": _json_copy(self.mutation_scope),
            "accepted_diff_comparison": _json_copy(self.accepted_diff_comparison),
            "validation": _json_copy(self.validation),
            "blockers": [dict(blocker) for blocker in self.blockers],
            "residual_labels": list(self.residual_labels),
            "zero_hosted_llm_source_judgment": self.zero_hosted_llm_source_judgment,
        }


def build_requests_clean_proxy_conftest_spec(
    repo_path: Path,
    *,
    base_ref: str = DEFAULT_REQUESTS_CLEAN_PROXY_BASE_REF,
    accepted_head_ref: str = DEFAULT_REQUESTS_CLEAN_PROXY_HEAD_REF,
    validation_command: str = DEFAULT_REQUESTS_CLEAN_PROXY_VALIDATION_COMMAND,
) -> RepoConventionSpec:
    """Build the held-out Requests clean-proxy conftest fixture candidate spec."""

    _repo_file(repo_path, REQUESTS_CONFTEST_PATH)
    fixture_action = PytestFixtureInsertionAction(
        target_file=REQUESTS_CONFTEST_PATH,
        anchor_function_name="prepare_url",
        fixture_name="clean_proxy_environ",
        insertion_source=_requests_clean_proxy_fixture_source(),
        require_autouse_fixture=True,
        rationale=(
            "insert an autouse conftest fixture after the local URL helper and "
            "before existing Requests test fixtures"
        ),
    )
    return RepoConventionSpec(
        candidate_id="mat-027-requests-clean-proxy-conftest",
        repo_id="psf/requests",
        repo_url="https://github.com/psf/requests",
        repo_split="held_out",
        base_ref=base_ref,
        accepted_head_ref=accepted_head_ref,
        reference_pr_url="https://github.com/psf/requests/pull/7423",
        prompt=(
            "Clear proxy-related environment variables before each Requests test "
            "so ambient proxy configuration cannot leak into the suite."
        ),
        validation_command=validation_command,
        allowed_write_paths=(REQUESTS_CONFTEST_PATH,),
        fixture_action=fixture_action,
        action_family_reuse_evidence=(
            {
                "action_kind": "insert_pytest_fixture_after_anchor",
                "reused_from": [
                    "insert_pytest_function_after_anchor",
                    "repo-local pytest fixture convention",
                ],
                "evidence": (
                    "same bounded pytest insertion family, specialized to "
                    "repo-local conftest fixture placement, fixture decorator "
                    "validation, and monkeypatch fixture dependency detection"
                ),
            },
        ),
    )


def materialize_repo_convention_candidate(
    repo_path: Path,
    spec: RepoConventionSpec,
    *,
    write: bool = True,
    validate: bool = False,
    accepted_diff_path: Path | None = None,
    validation_timeout_seconds: int = 180,
) -> RepoConventionCandidate:
    """Materialize repo-convention actions and record candidate-after metadata."""

    repo = repo_path.expanduser().resolve()
    blockers: list[dict[str, str]] = []
    action_records = [spec.fixture_action.to_record()]

    head = _git_stdout(repo, ("rev-parse", "HEAD"))
    if head and head != spec.base_ref:
        blockers.append(
            {
                "field": "repo_before_ref",
                "reason": "repo_before_ref_mismatch",
                "message": f"expected {spec.base_ref}, got {head}",
            }
        )

    hashes_before = _file_hashes(repo, spec.allowed_write_paths)
    fixture_result: PytestFixtureInsertionResult | None = None
    if not blockers:
        try:
            fixture_result = materialize_pytest_fixture_insertion(
                repo,
                spec.fixture_action,
                write=write,
            )
        except RepoConventionCandidateError as error:
            blockers.append(error.blocker)

    hashes_after = _file_hashes(repo, spec.allowed_write_paths)
    candidate_diff = _git_diff(repo, spec.allowed_write_paths)
    changed_files = _git_changed_files(repo, spec.allowed_write_paths)
    writes_outside_allowlist = _paths_outside_allowlist(
        changed_files,
        spec.allowed_write_paths,
    )
    if writes_outside_allowlist:
        blockers.append(
            {
                "field": "mutation_scope",
                "reason": "writes_outside_allowlist",
                "message": "candidate changed files outside the allowed write paths",
            }
        )

    validation = _deferred_validation(spec.validation_command)
    if validate and not blockers:
        validation = _run_validation(
            repo,
            spec.validation_command,
            timeout_seconds=validation_timeout_seconds,
        )

    accepted_diff_comparison = _accepted_diff_comparison(
        candidate_diff,
        accepted_diff_path=accepted_diff_path,
        scope_path_sets={"repo_convention": spec.allowed_write_paths},
    )
    if accepted_diff_comparison.get("accepted_diff_available") is False:
        blockers.append(
            {
                "field": "accepted_diff",
                "reason": "accepted_diff_unavailable",
                "message": str(accepted_diff_comparison.get("message", "")),
            }
        )

    fixture_record: dict[str, object]
    if fixture_result is None:
        fixture_record = {
            "available": False,
            "target_file": spec.fixture_action.target_file,
        }
    else:
        fixture_record = fixture_result.to_record()

    candidate_after = {
        "fixture_file": fixture_record,
        "candidate_diff": candidate_diff,
        "candidate_diff_summary": _diff_summary(candidate_diff),
        "candidate_changed_files": changed_files,
        "file_hashes_before": hashes_before,
        "file_hashes_after": hashes_after,
    }
    mutation_scope = {
        "mode": "heldout_repo_convention_pytest_conftest_fixture",
        "allowed_write_paths": list(spec.allowed_write_paths),
        "planned_write_files": [spec.fixture_action.target_file],
        "actual_changed_files": changed_files,
        "writes_outside_allowlist": writes_outside_allowlist,
        "only_allowed_convention_files_changed": (
            not writes_outside_allowlist
            and set(changed_files) <= set(spec.allowed_write_paths)
        ),
    }
    status = "blocked" if blockers else "planned"
    if not blockers and write:
        status = "validated" if validation["status"] == "passed" else "materialized"

    residual_labels = [blocker["reason"] for blocker in blockers]
    if not residual_labels:
        if validation["status"] == "passed":
            residual_labels = ["candidate_validation_passed"]
        elif validate:
            residual_labels = [f"candidate_validation_{validation['status']}"]
        else:
            residual_labels = ["candidate_validation_deferred"]

    return RepoConventionCandidate(
        candidate_id=spec.candidate_id,
        repo_id=spec.repo_id,
        repo_url=spec.repo_url,
        repo_split=spec.repo_split,
        base_ref=spec.base_ref,
        accepted_head_ref=spec.accepted_head_ref,
        reference_pr_url=spec.reference_pr_url,
        prompt=spec.prompt,
        status=status,
        action_records=action_records,
        action_family_reuse_evidence=[
            dict(item) for item in spec.action_family_reuse_evidence
        ],
        validation_command=spec.validation_command,
        allowed_write_paths=list(spec.allowed_write_paths),
        candidate_after=candidate_after,
        mutation_scope=mutation_scope,
        accepted_diff_comparison=accepted_diff_comparison,
        validation=validation,
        blockers=blockers,
        residual_labels=residual_labels,
    )


def materialize_pytest_fixture_insertion(
    repo_path: Path,
    action: PytestFixtureInsertionAction,
    *,
    write: bool = False,
) -> PytestFixtureInsertionResult:
    """Insert a pytest fixture in conftest.py and record metadata."""

    repo = repo_path.expanduser().resolve()
    target_path = _repo_file(repo, action.target_file)
    before = target_path.read_text(encoding="utf-8")
    if f"def {action.fixture_name}(" in before:
        convention_evidence = _pytest_fixture_convention_evidence(
            _parse_python(before, filename=action.target_file, field="conftest")
        )
        return PytestFixtureInsertionResult(
            status="already_applied",
            target_file=action.target_file,
            fixture_name=action.fixture_name,
            insertion_line=None,
            added_line_count=0,
            diff="",
            diff_summary={"hunk_count": 0, "changed_line_count": 0},
            ast_delta=python_ast_delta_metadata(before, before),
            ast_parse_ok=True,
            convention_evidence=convention_evidence,
            sha256_before=_sha256_text(before),
            sha256_after=_sha256_text(before),
            patched_source=before,
            wrote_file=False,
        )

    tree = _parse_python(before, filename=action.target_file, field="conftest")
    convention_evidence = _pytest_fixture_convention_evidence(tree)
    if action.require_local_pytest_fixture_convention and not (
        convention_evidence["imports_pytest"]
        and int(convention_evidence["existing_fixture_count"]) > 0
    ):
        raise RepoConventionCandidateError(
            "local pytest fixture convention was not detected",
            blocker={
                "field": "fixture_convention",
                "reason": "repo_convention_fixture_detection_blocked",
                "message": (
                    "target conftest.py does not import pytest and define "
                    "existing pytest fixtures"
                ),
            },
        )

    anchor = _find_function(tree, action.anchor_function_name)
    if anchor is None or anchor.end_lineno is None:
        raise RepoConventionCandidateError(
            f"anchor function not found: {action.anchor_function_name}",
            blocker={
                "field": "conftest_insertion",
                "reason": "repo_convention_conftest_insertion_blocked",
                "message": f"anchor function not found: {action.anchor_function_name}",
            },
        )

    insertion_lines = _insertion_lines(action.insertion_source)
    added_line_count = sum(1 for line in insertion_lines if line.strip())
    if added_line_count > action.max_added_lines:
        raise RepoConventionCandidateError(
            "pytest fixture insertion added-line budget exceeded",
            blocker={
                "field": "conftest_insertion",
                "reason": "repo_convention_conftest_insertion_blocked",
                "message": "pytest fixture insertion added-line budget exceeded",
            },
        )

    insertion_tree = _parse_python(
        action.insertion_source + "\n",
        filename=action.target_file,
        field="fixture_insertion",
    )
    inserted = _find_function(insertion_tree, action.fixture_name)
    if inserted is None:
        raise RepoConventionCandidateError(
            f"inserted fixture function not found: {action.fixture_name}",
            blocker={
                "field": "fixture_source",
                "reason": "repo_convention_fixture_source_blocked",
                "message": f"inserted fixture function not found: {action.fixture_name}",
            },
        )
    fixture_evidence = _fixture_decorator_evidence(inserted)
    if not fixture_evidence["is_pytest_fixture"]:
        raise RepoConventionCandidateError(
            "inserted function is not decorated as a pytest fixture",
            blocker={
                "field": "fixture_source",
                "reason": "repo_convention_fixture_source_blocked",
                "message": "inserted function is not decorated as a pytest fixture",
            },
        )
    if action.require_autouse_fixture and not fixture_evidence["autouse"]:
        raise RepoConventionCandidateError(
            "inserted fixture is not autouse",
            blocker={
                "field": "fixture_source",
                "reason": "repo_convention_fixture_source_blocked",
                "message": "inserted fixture is not autouse",
            },
        )

    source_lines = before.splitlines(keepends=True)
    insert_index = anchor.end_lineno
    while insert_index < len(source_lines) and not source_lines[insert_index].strip():
        insert_index += 1
    patched = "".join(
        source_lines[: anchor.end_lineno]
        + ["\n", "\n"]
        + insertion_lines
        + ["\n", "\n"]
        + source_lines[insert_index:]
    )
    _parse_python(patched, filename=action.target_file, field="conftest")
    if write:
        target_path.write_text(patched, encoding="utf-8")

    diff = _unified_diff(before, patched, action.target_file)
    convention_evidence = {
        **convention_evidence,
        "inserted_fixture": fixture_evidence,
        "anchor_function_name": action.anchor_function_name,
        "target_is_conftest": action.target_file.endswith("conftest.py"),
    }
    return PytestFixtureInsertionResult(
        status="materialized" if write else "candidate_after",
        target_file=action.target_file,
        fixture_name=action.fixture_name,
        insertion_line=anchor.end_lineno + 2,
        added_line_count=added_line_count,
        diff=diff,
        diff_summary=_diff_summary(diff),
        ast_delta=python_ast_delta_metadata(before, patched),
        ast_parse_ok=True,
        convention_evidence=convention_evidence,
        sha256_before=_sha256_text(before),
        sha256_after=_sha256_text(patched),
        patched_source=patched,
        wrote_file=write,
    )


def write_repo_convention_artifacts(
    candidate: RepoConventionCandidate,
    *,
    out_path: Path,
    report_path: Path | None = None,
    diff_path: Path | None = None,
) -> None:
    """Write JSON, optional markdown, and optional diff artifacts."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(candidate.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_repo_convention_report(candidate), encoding="utf-8")
    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(
            str(candidate.candidate_after.get("candidate_diff", "")),
            encoding="utf-8",
        )


def render_repo_convention_report(candidate: RepoConventionCandidate) -> str:
    """Render a compact markdown report for a repo-convention candidate."""

    validation = candidate.validation
    comparison = candidate.accepted_diff_comparison
    lines = [
        "# Held-Out Repo-Convention Candidate",
        "",
        f"- Candidate: `{candidate.candidate_id}`",
        f"- Repo: `{candidate.repo_id}`",
        f"- Base ref: `{candidate.base_ref}`",
        f"- Accepted head ref: `{candidate.accepted_head_ref}`",
        f"- Reference PR: {candidate.reference_pr_url}",
        f"- Status: `{candidate.status}`",
        f"- Changed files: `{candidate.mutation_scope.get('actual_changed_files')}`",
        f"- Accepted changed files: `{comparison.get('accepted_changed_files')}`",
        f"- Validation: `{validation.get('status')}` "
        f"(`{candidate.validation_command}`)",
        f"- Accepted diff normalized match: "
        f"`{comparison.get('normalized_diff_equal')}`",
        f"- Repo-convention scoped match: "
        f"`{comparison.get('scope_comparisons', {}).get('repo_convention', {}).get('normalized_diff_equal')}`",
        f"- Zero hosted LLM source judgment: "
        f"`{candidate.zero_hosted_llm_source_judgment}`",
        "",
        "## Reusable Actions",
        "",
    ]
    for action in candidate.action_records:
        lines.append(f"- `{action.get('kind')}`")
    lines.extend(["", "## Residuals", ""])
    if candidate.blockers:
        for blocker in candidate.blockers:
            lines.append(
                f"- `{blocker['field']}`: `{blocker['reason']}` - "
                f"{blocker['message']}"
            )
    elif candidate.residual_labels:
        for label in candidate.residual_labels:
            lines.append(f"- `{label}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _requests_clean_proxy_fixture_source() -> str:
    return "\n".join(
        [
            "@pytest.fixture(autouse=True)",
            "def clean_proxy_environ(monkeypatch):",
            '    """Remove proxy related environment variables for every test."""',
            '    proxy_vars = ("http_proxy", "https_proxy", "no_proxy", "ftp_proxy", "all_proxy")',
            "    for var in proxy_vars:",
            "        monkeypatch.delenv(var, raising=False)",
            "        monkeypatch.delenv(var.upper(), raising=False)",
        ]
    )


def _repo_file(repo: Path, relative_path: str) -> Path:
    _validate_relative_path(relative_path)
    path = repo / relative_path
    if not path.exists():
        raise RepoConventionCandidateError(
            f"target file not found: {relative_path}",
            blocker={
                "field": "target_file",
                "reason": "repo_convention_target_missing",
                "message": f"target file not found: {relative_path}",
            },
        )
    return path


def _parse_python(source: str, *, filename: str, field: str) -> ast.Module:
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError as error:
        raise RepoConventionCandidateError(
            f"Python parse failed for {filename}: {error}",
            blocker={
                "field": field,
                "reason": "repo_convention_python_parse_blocked",
                "message": f"Python parse failed for {filename}: {error}",
            },
        ) from error


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _pytest_fixture_convention_evidence(tree: ast.Module) -> dict[str, object]:
    fixture_names = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _fixture_decorator_evidence(node)["is_pytest_fixture"]
    ]
    return {
        "imports_pytest": _imports_pytest(tree),
        "existing_fixture_count": len(fixture_names),
        "existing_fixture_names": fixture_names,
    }


def _imports_pytest(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pytest":
                    return True
        if isinstance(node, ast.ImportFrom) and node.module == "pytest":
            return True
    return False


def _fixture_decorator_evidence(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, object]:
    autouse = False
    is_fixture = False
    for decorator in node.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        target = call.func if call is not None else decorator
        if _is_pytest_fixture_target(target):
            is_fixture = True
            if call is not None:
                for keyword in call.keywords:
                    if (
                        keyword.arg == "autouse"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        autouse = True
    return {
        "name": node.name,
        "is_pytest_fixture": is_fixture,
        "autouse": autouse,
        "arguments": [arg.arg for arg in node.args.args],
    }


def _is_pytest_fixture_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return (
            node.attr == "fixture"
            and isinstance(node.value, ast.Name)
            and node.value.id == "pytest"
        )
    return isinstance(node, ast.Name) and node.id == "fixture"


def _insertion_lines(source: str) -> list[str]:
    lines = source.splitlines()
    if not lines:
        raise RepoConventionCandidateError(
            "fixture insertion source is empty",
            blocker={
                "field": "fixture_source",
                "reason": "repo_convention_fixture_source_blocked",
                "message": "fixture insertion source is empty",
            },
        )
    return [f"{line}\n" for line in lines]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize a held-out repo-convention candidate."
    )
    parser.add_argument("--candidate", choices=("requests-7423",), default="requests-7423")
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--accepted-diff", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--diff-out", type=Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--validation-timeout-seconds", type=int, default=180)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    spec = build_requests_clean_proxy_conftest_spec(args.repo_path)
    candidate = materialize_repo_convention_candidate(
        args.repo_path,
        spec,
        write=not args.no_write,
        validate=args.validate,
        accepted_diff_path=args.accepted_diff,
        validation_timeout_seconds=args.validation_timeout_seconds,
    )
    write_repo_convention_artifacts(
        candidate,
        out_path=args.out,
        report_path=args.report,
        diff_path=args.diff_out,
    )
    return 0 if candidate.status != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
