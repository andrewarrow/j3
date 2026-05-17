"""Inventory local transition assets without requiring ignored data."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "transition-asset-inventory-v1"
DEFAULT_PROMPT_CORPUS = Path("../prompts/coding_agent_prompts_expanded_v0.jsonl")
PROMPT_REPO_DEMO_REPORT_SCHEMA = "prompt-jepa-demo-report-v1"
PROMPT_REPO_DEMO_ARTIFACTS = (
    "report.json",
    "index.json",
    "labels-index.json",
    "outcomes.jsonl",
    "source-embeddings.json",
    "transitions.jsonl",
    "transition-model.json",
    "transition-eval.json",
)


def inspect_transition_assets(
    *,
    repo_root: Path = Path("."),
    prompt_corpus: Path | None = None,
) -> dict[str, object]:
    """Return a reproducible manifest of local transition-related assets."""

    root = repo_root.expanduser().resolve()
    corpus_path = _resolve_path(prompt_corpus or DEFAULT_PROMPT_CORPUS, base=root)
    prompt_summary = _summarize_jsonl_file(corpus_path, root=root)
    mined_summary = _summarize_jsonl_collection(
        sorted((root / "data" / "transitions").rglob("*.jsonl"))
        if (root / "data" / "transitions").exists()
        else [],
        root=root,
    )
    candidate_summary = _summarize_jsonl_collection(
        sorted((root / "runs").rglob("*candidate-outcomes.jsonl"))
        if (root / "runs").exists()
        else [],
        root=root,
    )
    demo_summary = _summarize_prompt_repo_demo_artifacts(root)
    model_summary = _summarize_prototype_models(root)

    return {
        "schema_version": SCHEMA_VERSION,
        "repo_root": str(root),
        "prompt_corpus": prompt_summary,
        "prompt_repo_demo_artifacts": demo_summary,
        "mined_git_transitions": mined_summary,
        "candidate_outcomes": candidate_summary,
        "prototype_models": model_summary,
        "totals": {
            "prompt_corpus_rows": prompt_summary["rows"] if prompt_summary["present"] else 0,
            "prompt_repo_demo_directories": demo_summary["directory_count"],
            "mined_git_transition_files": mined_summary["file_count"],
            "mined_git_transition_rows": mined_summary["total_rows"],
            "candidate_outcome_files": candidate_summary["file_count"],
            "candidate_outcome_rows": candidate_summary["total_rows"],
            "prototype_model_files": model_summary["model_count"],
        },
        "notes": [
            "Missing data/ and runs/ assets are normal in a clean checkout.",
            "Generated JSONL datasets and large run artifacts should stay out of git.",
        ],
    }


def write_transition_asset_manifest(
    manifest: dict[str, object],
    out_path: Path,
) -> Path:
    """Write an inventory manifest as stable JSON."""

    resolved = out_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved


def format_transition_asset_inventory(manifest: dict[str, object]) -> str:
    """Format an inventory manifest for human CLI output."""

    prompt = _dict(manifest.get("prompt_corpus"))
    demos = _dict(manifest.get("prompt_repo_demo_artifacts"))
    mined = _dict(manifest.get("mined_git_transitions"))
    candidates = _dict(manifest.get("candidate_outcomes"))
    models = _dict(manifest.get("prototype_models"))

    lines = ["j3 inspect-transition-assets complete"]
    lines.append(f"repo root: {manifest.get('repo_root')}")
    lines.append(
        "prompt corpus: "
        f"{_present_label(prompt)} rows={prompt.get('rows', 0) or 0} "
        f"path={prompt.get('relative_path')}"
    )
    lines.append(
        "Prompt+Repo demo artifacts: "
        f"directories={demos.get('directory_count', 0)} "
        f"files={demos.get('artifact_count', 0)}"
    )
    lines.append(
        "mined git transitions: "
        f"files={mined.get('file_count', 0)} rows={mined.get('total_rows', 0)}"
    )
    lines.append(
        "candidate outcomes: "
        f"files={candidates.get('file_count', 0)} rows={candidates.get('total_rows', 0)}"
    )
    lines.append(f"prototype models: files={models.get('model_count', 0)}")
    lines.append("missing ignored assets: normal")
    return "\n".join(lines)


def _summarize_prompt_repo_demo_artifacts(root: Path) -> dict[str, object]:
    runs = root / "runs"
    if not runs.exists():
        return {
            "present": False,
            "directory_count": 0,
            "artifact_count": 0,
            "directories": [],
        }

    candidate_dirs = {
        path.parent
        for name in ("report.json", "transitions.jsonl", "transition-model.json")
        for path in runs.rglob(name)
    }
    directories: list[dict[str, object]] = []
    artifact_count = 0

    for directory in sorted(candidate_dirs):
        artifacts = [
            _summarize_maybe_jsonl_or_json_file(directory / name, root=root)
            for name in PROMPT_REPO_DEMO_ARTIFACTS
            if (directory / name).is_file()
        ]
        if not artifacts:
            continue
        report_metadata = _read_json_metadata(directory / "report.json")
        if not _looks_like_prompt_repo_demo(directory, report_metadata):
            continue
        artifact_count += len(artifacts)
        directories.append(
            {
                "path": str(directory),
                "relative_path": _relative_path(directory, root),
                "artifact_count": len(artifacts),
                "artifacts": artifacts,
                "report_metadata": report_metadata,
            }
        )

    return {
        "present": bool(directories),
        "directory_count": len(directories),
        "artifact_count": artifact_count,
        "directories": directories,
    }


def _summarize_prototype_models(root: Path) -> dict[str, object]:
    runs = root / "runs"
    model_paths = sorted(runs.rglob("model.json")) if runs.exists() else []
    models = []
    for path in model_paths:
        models.append(
            {
                "file": _summarize_file(path, root=root),
                "metadata": _read_json_metadata(path),
            }
        )
    return {
        "present": bool(models),
        "model_count": len(models),
        "models": models,
    }


def _summarize_jsonl_collection(paths: list[Path], *, root: Path) -> dict[str, object]:
    files = [_summarize_jsonl_file(path, root=root) for path in paths if path.is_file()]
    return {
        "present": bool(files),
        "file_count": len(files),
        "total_rows": sum(int(file["rows"]) for file in files),
        "files": files,
    }


def _summarize_maybe_jsonl_or_json_file(path: Path, *, root: Path) -> dict[str, object]:
    if path.suffix == ".jsonl":
        return _summarize_jsonl_file(path, root=root)
    return _summarize_file(path, root=root)


def _summarize_jsonl_file(path: Path, *, root: Path) -> dict[str, object]:
    summary = _summarize_file(path, root=root)
    if not summary["present"]:
        summary["rows"] = None
        return summary
    checksum = hashlib.sha256()
    rows = 0
    with path.open("rb") as handle:
        for line in handle:
            checksum.update(line)
            if line.strip():
                rows += 1
    summary["sha256"] = checksum.hexdigest()
    summary["rows"] = rows
    return summary


def _summarize_file(path: Path, *, root: Path) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    summary: dict[str, object] = {
        "path": str(resolved),
        "relative_path": _relative_path(resolved, root),
        "present": resolved.is_file(),
    }
    if not resolved.is_file():
        summary.update({"size_bytes": None, "sha256": None})
        return summary

    stat = resolved.stat()
    summary.update(
        {
            "size_bytes": stat.st_size,
            "sha256": _sha256_file(resolved),
        }
    )
    return summary


def _read_json_metadata(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {"json_readable": False}
    if not isinstance(raw, dict):
        return {"json_readable": False}

    metadata: dict[str, object] = {"json_readable": True}
    for key in (
        "schema_version",
        "format",
        "decision",
        "created_at",
        "feature_version",
        "embedding_dim",
        "top_k",
        "examples",
        "synthetic_examples",
        "mined_examples",
        "train_rows",
        "rows",
        "hosted_llm_api_tokens",
        "hosted_repo_context_bytes",
    ):
        value = raw.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata[key] = value
    for key in ("sources", "transition_sources", "train_row_ids"):
        value = raw.get(key)
        if isinstance(value, list):
            metadata[f"{key}_count"] = len(value)
    action_counts = raw.get("action_counts")
    if isinstance(action_counts, dict):
        metadata["action_counts"] = {
            str(key): value
            for key, value in sorted(action_counts.items())
            if isinstance(value, int)
        }
    artifacts = raw.get("artifacts")
    if isinstance(artifacts, dict):
        metadata["artifact_keys"] = sorted(str(key) for key in artifacts)
    return metadata


def _looks_like_prompt_repo_demo(
    directory: Path,
    report_metadata: dict[str, object],
) -> bool:
    if report_metadata.get("schema_version") == PROMPT_REPO_DEMO_REPORT_SCHEMA:
        return True
    return (directory / "transitions.jsonl").is_file() and (
        directory / "transition-model.json"
    ).is_file()


def _sha256_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return os.path.relpath(path, root)


def _resolve_path(path: Path, *, base: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (base / expanded).resolve()


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _present_label(summary: dict[str, Any]) -> str:
    return "present" if summary.get("present") else "missing"
