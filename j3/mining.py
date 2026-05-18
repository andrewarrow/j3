"""Mine prototype transition records from git and issue/PR exports."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ISSUE_PR_TRANSITION_MANIFEST_SCHEMA_VERSION = "issue-pr-transition-manifest-v0"
ISSUE_PR_TRANSITION_RECORD_SCHEMA_VERSION = "issue-pr-transition-record-v0"


@dataclass(frozen=True, slots=True)
class MineResult:
    repo: Path
    out_path: Path
    commits_scanned: int
    transitions_written: int


@dataclass(frozen=True, slots=True)
class IssuePrManifestResult:
    source_path: Path
    out_path: Path
    repository: str
    records_written: int


def mine_git_transitions(
    *,
    repo: Path,
    out_path: Path,
    max_commits: int = 50,
    max_files_per_commit: int = 20,
) -> MineResult:
    """Write JSONL records for Python files changed across recent commits."""

    root = repo.expanduser().resolve()
    if not (root / ".git").exists():
        raise ValueError(f"not a git repository: {root}")
    if max_commits < 1:
        raise ValueError("max_commits must be >= 1")
    if max_files_per_commit < 1:
        raise ValueError("max_files_per_commit must be >= 1")

    commits = _git_lines(root, ["log", "--format=%H", f"--max-count={max_commits}", "--", "*.py"])
    output = out_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output.open("w", encoding="utf-8") as handle:
        for commit in commits:
            parent = _first_parent(root, commit)
            if parent is None:
                continue

            changed_files = _changed_python_files(root, parent, commit)[:max_files_per_commit]
            for file_path in changed_files:
                before = _show_text(root, f"{parent}:{file_path}")
                after = _show_text(root, f"{commit}:{file_path}")
                if before is None or after is None or before == after:
                    continue

                diff = _git_text(root, ["diff", "--unified=3", parent, commit, "--", file_path])
                record = {
                    "kind": "git_transition",
                    "repo": root.name,
                    "repo_path": str(root),
                    "commit": commit,
                    "parent": parent,
                    "file_path": file_path,
                    "before_source": before,
                    "after_source": after,
                    "diff": diff,
                    "mined_at": datetime.now(timezone.utc).isoformat(),
                }
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                written += 1

    return MineResult(
        repo=root,
        out_path=output,
        commits_scanned=len(commits),
        transitions_written=written,
    )


def mine_issue_pr_transition_manifest(
    *,
    source_path: Path,
    out_path: Path,
    source_kind: str = "github_fixture",
) -> IssuePrManifestResult:
    """Write a deterministic issue/PR-linked transition manifest.

    The source is a small JSON export with repository, issue, and pull request
    objects. This intentionally does not call live APIs; large harvested data
    should be generated outside the repository and reviewed before training use.
    """

    manifest = build_issue_pr_transition_manifest(
        source_path=source_path,
        source_kind=source_kind,
    )
    output = out_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return IssuePrManifestResult(
        source_path=source_path.expanduser().resolve(),
        out_path=output,
        repository=str(_mapping(manifest["repository"]).get("full_name", "")),
        records_written=len(_list(manifest["records"])),
    )


def build_issue_pr_transition_manifest(
    *,
    source_path: Path,
    source_kind: str = "github_fixture",
) -> dict[str, object]:
    """Build candidate records that link issue/PR text to accepted repo refs."""

    source = source_path.expanduser().resolve()
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("issue/PR source must be a JSON object")

    repository = _mapping(raw.get("repository"))
    full_name = _required_str(repository, "full_name")
    owner, name = _repo_parts(full_name)
    license_info = _mapping(repository.get("license"))
    issues = {
        _required_int(issue, "number"): issue
        for issue in _mapping_list(raw.get("issues"))
    }
    pull_requests = _mapping_list(raw.get("pull_requests"))

    records: list[dict[str, object]] = []
    for pull_request in pull_requests:
        if not _is_merged_pull_request(pull_request):
            continue
        for issue_number in _linked_issue_numbers(pull_request):
            issue = issues.get(issue_number)
            if issue is None:
                continue
            records.append(
                _issue_pr_transition_record(
                    repository=repository,
                    owner=owner,
                    name=name,
                    license_info=license_info,
                    issue=issue,
                    pull_request=pull_request,
                    source_path=source,
                    source_sha256=_sha256_file(source),
                    source_kind=source_kind,
                    retrieved_at=_optional_str(raw, "retrieved_at"),
                )
            )

    records.sort(key=lambda record: str(record["id"]))
    return {
        "schema_version": ISSUE_PR_TRANSITION_MANIFEST_SCHEMA_VERSION,
        "record_kind": "issue_pr_transition_manifest",
        "source": {
            "kind": source_kind,
            "path": str(source),
            "sha256": _sha256_file(source),
            "retrieved_at": _optional_str(raw, "retrieved_at"),
            "live_api_access_required": False,
        },
        "repository": {
            "provider": "github",
            "owner": owner,
            "name": name,
            "full_name": full_name,
            "html_url": _optional_str(repository, "html_url"),
            "default_branch": _optional_str(repository, "default_branch"),
            "license": {
                "spdx_id": _optional_str(license_info, "spdx_id") or "UNKNOWN",
                "url": _optional_str(license_info, "url"),
                "metadata_source": "source.repository.license",
            },
        },
        "license_and_terms": _license_and_terms(repository, license_info),
        "records": records,
        "totals": {
            "issues_seen": len(issues),
            "pull_requests_seen": len(pull_requests),
            "candidate_records": len(records),
        },
        "notes": [
            "Prototype consumes fixture/export JSON and does not fetch GitHub live.",
            "Records are unreviewed candidates until issue text, PR text, refs, "
            "license, and redistribution terms are manually checked.",
            "Generated corpus manifests should stay out of git when they contain "
            "large harvested issue/PR text.",
        ],
    }


def _first_parent(repo: Path, commit: str) -> str | None:
    parents = _git_lines(repo, ["rev-list", "--parents", "-n", "1", commit])
    if not parents:
        return None
    parts = parents[0].split()
    if len(parts) < 2:
        return None
    return parts[1]


def _changed_python_files(repo: Path, parent: str, commit: str) -> list[str]:
    files = _git_lines(
        repo,
        ["diff", "--name-only", "--diff-filter=AM", parent, commit, "--", "*.py"],
    )
    return [file for file in files if file.endswith(".py")]


def _show_text(repo: Path, spec: str) -> str | None:
    result = subprocess.run(
        ["git", "show", spec],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    text = _git_text(repo, args)
    return [line for line in text.splitlines() if line]


def _git_text(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _issue_pr_transition_record(
    *,
    repository: dict[str, Any],
    owner: str,
    name: str,
    license_info: dict[str, Any],
    issue: dict[str, Any],
    pull_request: dict[str, Any],
    source_path: Path,
    source_sha256: str,
    source_kind: str,
    retrieved_at: str | None,
) -> dict[str, object]:
    issue_number = _required_int(issue, "number")
    pr_number = _required_int(pull_request, "number")
    row_id = f"{owner}__{name}-issue-{issue_number}-pr-{pr_number}"
    split, bucket = _stable_split(row_id)
    base = _mapping(pull_request.get("base"))
    head = _mapping(pull_request.get("head"))
    base_sha = _optional_str(base, "sha")
    merge_commit_sha = _required_str(pull_request, "merge_commit_sha")
    full_name = f"{owner}/{name}"
    compare_url = (
        f"https://github.com/{full_name}/compare/{base_sha}...{merge_commit_sha}"
        if base_sha
        else None
    )

    return {
        "schema_version": ISSUE_PR_TRANSITION_RECORD_SCHEMA_VERSION,
        "id": row_id,
        "repo": full_name,
        "split": split,
        "stable_split": {
            "method": "sha256(id) % 100",
            "bucket": bucket,
            "train": "0-79",
            "validation": "80-89",
            "test": "90-99",
        },
        "prompt_source": {
            "kind": "issue_and_pull_request_text",
            "issue_title": _required_str(issue, "title"),
            "issue_body": _optional_str(issue, "body") or "",
            "pull_request_title": _required_str(pull_request, "title"),
            "pull_request_body": _optional_str(pull_request, "body") or "",
        },
        "issue": {
            "number": issue_number,
            "url": _required_str(issue, "html_url"),
            "state": _optional_str(issue, "state"),
            "author_association": _optional_str(issue, "author_association"),
            "created_at": _optional_str(issue, "created_at"),
            "closed_at": _optional_str(issue, "closed_at"),
        },
        "pull_request": {
            "number": pr_number,
            "url": _required_str(pull_request, "html_url"),
            "state": _optional_str(pull_request, "state"),
            "merged_at": _required_str(pull_request, "merged_at"),
            "base_ref": _optional_str(base, "ref"),
            "head_ref": _optional_str(head, "ref"),
            "changed_files": _string_list(pull_request.get("changed_files")),
        },
        "repo_before_ref": {
            "kind": "pull_request_base_commit",
            "sha": base_sha,
            "ref": _optional_str(base, "ref"),
        },
        "repo_after_ref": {
            "kind": "pull_request_merge_commit",
            "sha": merge_commit_sha,
            "ref": _optional_str(repository, "default_branch"),
        },
        "links": {
            "repository": _optional_str(repository, "html_url"),
            "issue": _required_str(issue, "html_url"),
            "pull_request": _required_str(pull_request, "html_url"),
            "diff": _optional_str(pull_request, "diff_url"),
            "patch": _optional_str(pull_request, "patch_url"),
            "compare": compare_url,
        },
        "provenance": {
            "source_kind": source_kind,
            "source_path": str(source_path),
            "source_sha256": source_sha256,
            "retrieved_at": retrieved_at,
            "review_status": "unreviewed_candidate",
            "manual_review_required": True,
            "linked_issue_source": "pull_request.linked_issues",
        },
        "license_and_terms": _license_and_terms(repository, license_info),
        "candidate_notes": [
            "Accepted change inferred from merged pull request.",
            "Issue/PR text may include discussion noise and requires review before "
            "normalizing into trainable prompt rows.",
            "Repo refs identify before/after commits; source snapshots are not "
            "embedded in this manifest.",
        ],
    }


def _is_merged_pull_request(pull_request: dict[str, Any]) -> bool:
    merged = pull_request.get("merged")
    return bool(merged) and bool(_optional_str(pull_request, "merge_commit_sha"))


def _linked_issue_numbers(pull_request: dict[str, Any]) -> list[int]:
    linked = pull_request.get("linked_issues", [])
    if not isinstance(linked, list):
        return []
    numbers: list[int] = []
    for value in linked:
        if isinstance(value, int):
            numbers.append(value)
        elif isinstance(value, str) and value.isdigit():
            numbers.append(int(value))
    return sorted(set(numbers))


def _stable_split(row_id: str) -> tuple[str, int]:
    bucket = int(hashlib.sha256(row_id.encode("utf-8")).hexdigest(), 16) % 100
    if bucket < 80:
        return "train", bucket
    if bucket < 90:
        return "validation", bucket
    return "test", bucket


def _license_and_terms(
    repository: dict[str, Any],
    license_info: dict[str, Any],
) -> dict[str, object]:
    terms_url = _optional_str(repository, "terms_url") or (
        "https://docs.github.com/site-policy/github-terms/"
        "github-terms-of-service"
    )
    return {
        "repo_license_spdx": _optional_str(license_info, "spdx_id") or "UNKNOWN",
        "repo_license_url": _optional_str(license_info, "url"),
        "source_terms_url": terms_url,
        "notes": [
            "Repository license metadata is copied from the issue/PR export and "
            "must be verified against the repo before redistribution.",
            "Issue and pull request text may be governed by hosting-site terms in "
            "addition to the repository code license.",
            "This manifest is a candidate index, not a reviewed training dataset.",
        ],
    }


def _repo_parts(full_name: str) -> tuple[str, str]:
    parts = full_name.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"repository full_name must be owner/name: {full_name}")
    return parts[0], parts[1]


def _required_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string field: {key}")
    return value


def _optional_str(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) and value else None


def _required_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise ValueError(f"missing required integer field: {key}")
    return value


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _sha256_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()
