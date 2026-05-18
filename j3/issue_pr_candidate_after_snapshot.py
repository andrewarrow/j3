"""Build sidecar candidate-after file snapshots for issue/PR candidates."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence


ISSUE_PR_CANDIDATE_AFTER_SCHEMA_VERSION = "issue-pr-candidate-after-snapshot-v1"
DEFAULT_PYTEST_CANDIDATE_PATH = Path(
    "/tmp/j3-data-029-pytest-14462-source-test/candidate.json"
)
DEFAULT_SCRAPY_CANDIDATE_PATH = Path(
    "/tmp/j3-data-035-scrapy-7293-source-test-final/candidate.json"
)
DEFAULT_OUT_DIR = Path("/tmp/j3-data-038-issue-pr-candidate-after-snapshots")


class IssuePrCandidateAfterSnapshotError(ValueError):
    """Raised when a candidate-after snapshot bundle cannot be built."""


def build_issue_pr_candidate_after_bundle(
    *,
    candidate_paths: Sequence[Path] = (
        DEFAULT_PYTEST_CANDIDATE_PATH,
        DEFAULT_SCRAPY_CANDIDATE_PATH,
    ),
    out_dir: Path = DEFAULT_OUT_DIR,
    after_roots: Mapping[str, Sequence[Path]] | None = None,
) -> dict[str, object]:
    """Build a sidecar bundle containing full after-file snapshots.

    ``after_roots`` may be keyed by replay id, candidate id, or candidate JSON
    path. When omitted, the builder searches known DATA-029/DATA-035 temporary
    workdirs and candidate-artifact siblings.
    """

    output = out_dir.expanduser().resolve()
    snapshot_root = output / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    records = [
        _candidate_snapshot_record(
            candidate_path=path.expanduser().resolve(),
            snapshot_root=snapshot_root,
            after_roots=after_roots or {},
        )
        for path in candidate_paths
    ]
    available = [record for record in records if record.get("status") == "available"]
    blockers = [
        blocker
        for record in records
        for blocker in _list_of_mappings(record.get("blockers"))
    ]
    return {
        "schema_version": ISSUE_PR_CANDIDATE_AFTER_SCHEMA_VERSION,
        "record_kind": "issue_pr_candidate_after_snapshot_bundle",
        "task_id": "DATA-038",
        "mode": "sidecar_snapshot_evidence",
        "production_ranking_gate_changed": False,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": all(
                _mapping(record.get("hosted_llm_usage")).get(
                    "zero_hosted_usage_confirmed"
                )
                is True
                for record in records
            ),
        },
        "summary": {
            "candidate_count": len(records),
            "available_candidate_count": len(available),
            "blocked_candidate_count": len(records) - len(available),
            "snapshot_file_count": sum(
                len(_list_of_mappings(record.get("snapshots"))) for record in records
            ),
            "touched_file_count": sum(
                len(_string_list(record.get("touched_file_paths"))) for record in records
            ),
            "blocker_reasons": _sorted_unique(
                str(blocker.get("reason", "")) for blocker in blockers
            ),
        },
        "candidates": records,
    }


def write_issue_pr_candidate_after_bundle(
    bundle: Mapping[str, object],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write bundle JSON, candidate JSONL, and markdown report artifacts."""

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle_json = output / "candidate-after-bundle.json"
    candidates_jsonl = output / "candidate-after-candidates.jsonl"
    report_md = output / "candidate-after-report.md"
    bundle_json.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    candidates = [
        candidate
        for candidate in bundle.get("candidates", [])
        if isinstance(candidate, Mapping)
    ]
    candidates_jsonl.write_text(
        "\n".join(json.dumps(candidate, sort_keys=True) for candidate in candidates)
        + ("\n" if candidates else ""),
        encoding="utf-8",
    )
    report_md.write_text(format_issue_pr_candidate_after_markdown(bundle), encoding="utf-8")
    return {
        "bundle_json": bundle_json,
        "candidates_jsonl": candidates_jsonl,
        "report_md": report_md,
    }


def format_issue_pr_candidate_after_markdown(bundle: Mapping[str, object]) -> str:
    summary = _mapping(bundle.get("summary"))
    hosted = _mapping(bundle.get("hosted_llm_usage"))
    lines = [
        "# DATA-038 Issue/PR Candidate-After Snapshot Bundle",
        "",
        f"- Candidates: {summary.get('candidate_count')}",
        f"- Available candidates: {summary.get('available_candidate_count')}",
        f"- Blocked candidates: {summary.get('blocked_candidate_count')}",
        f"- Snapshot files: {summary.get('snapshot_file_count')}",
        f"- Hosted LLM usage: {str(hosted.get('used') is True).lower()}",
        f"- Zero hosted usage confirmed: {str(hosted.get('zero_hosted_usage_confirmed') is True).lower()}",
        "",
        "| Replay | Candidate | Status | Touched files | Validation | Snapshot root | Blockers |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for candidate in _list_of_mappings(bundle.get("candidates")):
        blockers = ", ".join(
            str(blocker.get("reason", ""))
            for blocker in _list_of_mappings(candidate.get("blockers"))
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(candidate.get("replay_id", "")),
                    str(candidate.get("candidate_id", "")),
                    str(candidate.get("status", "")),
                    str(len(_string_list(candidate.get("touched_file_paths")))),
                    str(candidate.get("validation_status", "")),
                    str(candidate.get("snapshot_root", "")),
                    blockers,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Snapshot Files",
            "",
            "| Replay | Path | Before hash | After hash | Snapshot | AST parse |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for candidate in _list_of_mappings(bundle.get("candidates")):
        for snapshot in _list_of_mappings(candidate.get("snapshots")):
            ast_metadata = _mapping(snapshot.get("ast_metadata"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(candidate.get("replay_id", "")),
                        str(snapshot.get("path", "")),
                        _short_hash(snapshot.get("sha256_before")),
                        _short_hash(snapshot.get("sha256_after")),
                        str(snapshot.get("after_snapshot_path", "")),
                        str(ast_metadata.get("ast_parse_ok", "")),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def load_candidate_after_bundle_index(bundle_path: Path) -> dict[tuple[str, str], dict[str, object]]:
    """Load a DATA-038 bundle keyed by ``(replay_id, candidate_id)``."""

    payload = json.loads(bundle_path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrCandidateAfterSnapshotError(
            f"candidate-after bundle must be a JSON object: {bundle_path}"
        )
    index: dict[tuple[str, str], dict[str, object]] = {}
    for candidate in _list_of_mappings(payload.get("candidates")):
        if candidate.get("status") != "available":
            continue
        replay_id = str(candidate.get("replay_id", ""))
        candidate_id = str(candidate.get("candidate_id", ""))
        candidate_after = _mapping(candidate.get("candidate_after"))
        if replay_id and candidate_id and candidate_after.get("available") is True:
            index[(replay_id, candidate_id)] = dict(candidate_after)
    return index


def _candidate_snapshot_record(
    *,
    candidate_path: Path,
    snapshot_root: Path,
    after_roots: Mapping[str, Sequence[Path]],
) -> dict[str, object]:
    record = _load_candidate_record(candidate_path)
    replay_id = str(record.get("replay_id", ""))
    candidate_id = str(record.get("candidate_id", ""))
    touched_files = _touched_files(record)
    blockers: list[dict[str, str]] = []
    if not touched_files:
        blockers.append(
            {
                "field": "candidate_diff.changed_files",
                "reason": "touched_files_unavailable",
                "message": "The candidate record does not expose touched file paths.",
            }
        )
    candidate_roots = _candidate_after_roots(
        candidate_path=candidate_path,
        record=record,
        after_roots=after_roots,
    )
    selected_root = _select_after_root(
        roots=candidate_roots,
        record=record,
        touched_files=touched_files,
    )
    if selected_root is None:
        blockers.append(
            {
                "field": "after_root",
                "reason": "matching_after_root_unavailable",
                "message": (
                    "No candidate-after checkout contained every touched file "
                    "with hashes matching the candidate record."
                ),
            }
        )
    snapshots: list[dict[str, object]] = []
    if selected_root is not None:
        candidate_snapshot_root = snapshot_root / _safe_id(replay_id)
        for touched_file in touched_files:
            materialization = _materialization_for_path(record, touched_file)
            after_path = selected_root / touched_file
            if not after_path.is_file():
                blockers.append(
                    {
                        "field": touched_file,
                        "reason": "after_file_missing",
                        "message": f"Missing after-file snapshot source: {after_path}",
                    }
                )
                continue
            after_bytes = after_path.read_bytes()
            after_hash = _sha256_bytes(after_bytes)
            expected_after = str(materialization.get("sha256_after") or "")
            if expected_after and after_hash != expected_after:
                blockers.append(
                    {
                        "field": touched_file,
                        "reason": "after_hash_mismatch",
                        "message": (
                            f"After hash {after_hash} did not match candidate "
                            f"record hash {expected_after}."
                        ),
                    }
                )
                continue
            snapshot_path = candidate_snapshot_root / touched_file
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_bytes(after_bytes)
            snapshots.append(
                _snapshot_file_record(
                    touched_file=touched_file,
                    source_after_path=after_path,
                    snapshot_path=snapshot_path,
                    after_bytes=after_bytes,
                    materialization=materialization,
                )
            )
    status = "available" if touched_files and len(snapshots) == len(touched_files) and not blockers else "blocked"
    candidate_after = _candidate_after_record(
        candidate_id=candidate_id,
        replay_id=replay_id,
        snapshots=snapshots,
        status=status,
    )
    return {
        "schema_version": ISSUE_PR_CANDIDATE_AFTER_SCHEMA_VERSION,
        "record_kind": "issue_pr_candidate_after_snapshot",
        "candidate_id": candidate_id,
        "replay_id": replay_id,
        "repo": str(record.get("repo", "")),
        "repo_before_ref": str(record.get("repo_before_ref", "")),
        "source_candidate_path": str(candidate_path),
        "source_after_root": str(selected_root) if selected_root is not None else None,
        "snapshot_root": str((snapshot_root / _safe_id(replay_id)).resolve()),
        "status": status,
        "validation_status": str(_mapping(record.get("validation")).get("status", "")),
        "validation": _json_copy(record.get("validation", {})),
        "touched_file_paths": touched_files,
        "snapshots": snapshots,
        "candidate_after": candidate_after,
        "provenance": {
            "candidate_artifact": str(candidate_path),
            "candidate_schema_version": str(record.get("schema_version", "")),
            "candidate_record_kind": str(record.get("record_kind", "")),
            "action_family": str(record.get("action_family", "")),
            "source_candidate_status": str(record.get("status", "")),
            "evidence": _json_copy(record.get("evidence", {})),
        },
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": record.get("zero_hosted_usage_confirmed")
            is True,
        },
        "blockers": blockers,
    }


def _candidate_after_record(
    *,
    candidate_id: str,
    replay_id: str,
    snapshots: Sequence[Mapping[str, object]],
    status: str,
) -> dict[str, object]:
    files = {
        str(snapshot.get("path", "")): {
            "path": str(snapshot.get("path", "")),
            "sha256_before": snapshot.get("sha256_before"),
            "sha256_after": snapshot.get("sha256_after"),
            "after_snapshot_path": snapshot.get("after_snapshot_path"),
            "diff_summary": _json_copy(snapshot.get("diff_summary", {})),
            "ast_delta": _json_copy(snapshot.get("ast_delta", {})),
            "ast_metadata": _json_copy(snapshot.get("ast_metadata", {})),
        }
        for snapshot in snapshots
    }
    return {
        "available": status == "available",
        "kind": "full_file_snapshot_bundle" if status == "available" else "unavailable",
        "schema_version": ISSUE_PR_CANDIDATE_AFTER_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "replay_id": replay_id,
        "touched_file_paths": [str(snapshot.get("path", "")) for snapshot in snapshots],
        "file_count": len(snapshots),
        "files": files,
        "embedding_available": False,
        "embedding": None,
    }


def _snapshot_file_record(
    *,
    touched_file: str,
    source_after_path: Path,
    snapshot_path: Path,
    after_bytes: bytes,
    materialization: Mapping[str, object],
) -> dict[str, object]:
    after_hash = _sha256_bytes(after_bytes)
    before_hash = materialization.get("sha256_before")
    diff_summary = _mapping(materialization.get("diff_summary"))
    ast_delta = _mapping(materialization.get("ast_delta"))
    return {
        "path": touched_file,
        "source_after_path": str(source_after_path),
        "after_snapshot_path": str(snapshot_path.resolve()),
        "sha256_before": before_hash,
        "sha256_after": after_hash,
        "candidate_record_sha256_after": materialization.get("sha256_after"),
        "snapshot_sha256": after_hash,
        "size_bytes": len(after_bytes),
        "diff_summary": _json_copy(diff_summary),
        "diff_available": bool(materialization.get("diff")),
        "ast_delta": _json_copy(ast_delta),
        "ast_metadata": _python_ast_metadata(after_bytes, touched_file),
        "provenance": {
            "hash_source": "candidate_materialization_record",
            "snapshot_source": "candidate_after_checkout_file",
        },
    }


def _load_candidate_record(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise IssuePrCandidateAfterSnapshotError(f"candidate artifact missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrCandidateAfterSnapshotError(
            f"candidate artifact must be a JSON object: {path}"
        )
    required = ["candidate_id", "replay_id", "repo", "candidate_diff", "validation"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise IssuePrCandidateAfterSnapshotError(
            f"candidate artifact {path} is missing required keys: {', '.join(missing)}"
        )
    return payload


def _touched_files(record: Mapping[str, object]) -> list[str]:
    candidate_diff = _mapping(record.get("candidate_diff"))
    changed_files = _string_list(candidate_diff.get("changed_files"))
    if changed_files:
        return changed_files
    mutation_scope = _mapping(record.get("mutation_scope"))
    files_changed = _string_list(mutation_scope.get("files_changed"))
    if files_changed:
        return files_changed
    return _string_list(record.get("allowed_write_paths"))


def _candidate_after_roots(
    *,
    candidate_path: Path,
    record: Mapping[str, object],
    after_roots: Mapping[str, Sequence[Path]],
) -> list[Path]:
    keys = [
        str(record.get("replay_id", "")),
        str(record.get("candidate_id", "")),
        str(candidate_path),
    ]
    roots: list[Path] = []
    for key in keys:
        roots.extend(after_roots.get(key, ()))
    roots.extend(_default_after_roots(candidate_path, record))
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _default_after_roots(candidate_path: Path, record: Mapping[str, object]) -> list[Path]:
    replay_id = str(record.get("replay_id", ""))
    parent = candidate_path.parent
    roots = [
        parent / "repo-fbab7c5d-exact2",
        parent / "repo-fbab7c5d-exact",
        parent / "repo-fbab7c5d",
    ]
    if replay_id == "scrapy__scrapy-issue-7293-pr-7351":
        tmp = Path("/private/tmp")
        roots.extend(sorted(tmp.glob("j3-data-035-scrapy-parity-*"), reverse=True))
        roots.extend(sorted(tmp.glob("j3-data-035-accepted-inspect-*"), reverse=True))
        roots.append(
            tmp
            / "j3-data-035-scrapy-7293-source-test"
            / "repos"
            / "scrapy__scrapy-scrapy__scrapy-issue-7293-pr-7351-final"
        )
    return roots


def _select_after_root(
    *,
    roots: Sequence[Path],
    record: Mapping[str, object],
    touched_files: Sequence[str],
) -> Path | None:
    for root in roots:
        if not root.is_dir():
            continue
        matched = True
        for touched_file in touched_files:
            after_path = root / touched_file
            if not after_path.is_file():
                matched = False
                break
            materialization = _materialization_for_path(record, touched_file)
            expected_after = str(materialization.get("sha256_after") or "")
            if expected_after and _sha256_bytes(after_path.read_bytes()) != expected_after:
                matched = False
                break
        if matched:
            return root
    return None


def _materialization_for_path(
    record: Mapping[str, object],
    touched_file: str,
) -> Mapping[str, object]:
    for key in ("source_materialization", "test_materialization", "auxiliary_materialization"):
        value = record.get(key)
        if isinstance(value, Mapping):
            if _materialization_matches(value, touched_file):
                return value
            for nested in value.values():
                if isinstance(nested, Mapping) and _materialization_matches(
                    nested,
                    touched_file,
                ):
                    return nested
    return {}


def _materialization_matches(value: Mapping[str, object], touched_file: str) -> bool:
    path_fields = ("target_source_file", "target_test_file", "target_file")
    if any(str(value.get(field, "")) == touched_file for field in path_fields):
        return True
    return touched_file in _string_list(value.get("planned_changed_files"))


def _python_ast_metadata(after_bytes: bytes, path: str) -> dict[str, object]:
    if not path.endswith(".py"):
        return {"ast_parse_ok": None, "reason": "not_python"}
    try:
        text = after_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {
            "ast_parse_ok": False,
            "error": f"utf8_decode_error:{exc.__class__.__name__}",
        }
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        return {
            "ast_parse_ok": False,
            "error": f"syntax_error:{exc.lineno}:{exc.offset}",
        }
    nodes = list(ast.walk(tree))
    return {
        "ast_parse_ok": True,
        "node_count": len(nodes),
        "function_count": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes),
        "class_count": sum(isinstance(node, ast.ClassDef) for node in nodes),
        "import_count": sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in nodes),
    }


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def _short_hash(value: object) -> str:
    text = str(value or "")
    return text[:12] if text else ""


def _sorted_unique(values: object) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        action="append",
        type=Path,
        dest="candidates",
        help=(
            "Candidate JSON artifact. May be supplied more than once. "
            "Defaults to the DATA-029 and DATA-035 candidate artifacts."
        ),
    )
    parser.add_argument(
        "--after-root",
        action="append",
        default=[],
        help=(
            "Optional replay_id=PATH, candidate_id=PATH, or candidate_json=PATH "
            "root containing after-state files. May be supplied more than once."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for snapshot files and bundle reports.",
    )
    args = parser.parse_args(argv)

    candidate_paths = args.candidates or [
        DEFAULT_PYTEST_CANDIDATE_PATH,
        DEFAULT_SCRAPY_CANDIDATE_PATH,
    ]
    bundle = build_issue_pr_candidate_after_bundle(
        candidate_paths=candidate_paths,
        out_dir=args.out_dir,
        after_roots=_parse_after_roots(args.after_root),
    )
    artifacts = write_issue_pr_candidate_after_bundle(bundle, out_dir=args.out_dir)
    print(json.dumps({name: str(path) for name, path in artifacts.items()}, sort_keys=True))
    return 0


def _parse_after_roots(values: Sequence[str]) -> dict[str, list[Path]]:
    parsed: dict[str, list[Path]] = {}
    for value in values:
        if "=" not in value:
            raise IssuePrCandidateAfterSnapshotError(
                f"after-root must be KEY=PATH, got: {value}"
            )
        key, raw_path = value.split("=", 1)
        if not key:
            raise IssuePrCandidateAfterSnapshotError(
                f"after-root key must not be empty: {value}"
            )
        parsed.setdefault(key, []).append(Path(raw_path))
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
