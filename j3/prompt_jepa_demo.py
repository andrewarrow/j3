"""One-command Prompt-JEPA demo orchestration.

The demo is intentionally local and evaluation-only. It builds retrieval
artifacts, records real calculator outcomes, and writes a report without
wiring retrieval into production request/change routing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from j3.existing_repo_change import (
    append_existing_repo_change_attempt,
    apply_existing_repo_change,
    parse_existing_repo_change_to_spec,
    plan_existing_repo_change,
)
from j3.features import FEATURE_VERSION as PYTHON_SOURCE_FEATURE_VERSION
from j3.features import embed_python_source
from j3.greenfield import build_calculator_repo, plan_calculator_repo
from j3.prompt_intents import load_prompt_intent_records, predict_prompt_intent
from j3.prompt_jepa import (
    build_prompt_jepa_index_from_sources,
    evaluate_prompt_jepa_retrieval,
    propose_from_prompt_jepa,
    save_prompt_jepa_index,
)
from j3.prompt_repo_transitions import (
    TRANSITION_ARTIFACT,
    PromptRepoOutcomeState,
    build_prompt_repo_transition_rows,
    write_prompt_repo_transitions_jsonl,
)
from j3.repo_state import encode_repo_state_record
from j3.request_outcomes import append_request_repo_attempt
from j3.request_spec import parse_request_to_spec


PROMPT_JEPA_DEMO_SCHEMA_VERSION = "prompt-jepa-demo-report-v1"
SOURCE_EMBEDDING_SIDECAR_SCHEMA_VERSION = "prompt-jepa-demo-source-embeddings-v1"
DEMO_OUTPUT_MARKER = ".j3-prompt-jepa-demo"
SOURCE_EMBEDDING_ARTIFACT = "source-embeddings.json"
REPRESENTATIVE_PROMPTS = (
    "make me a simple cli calc",
    "make me a complex calc for spaceships",
    "add exponent support",
    "build a small todo cli where I can add tasks and mark them done",
    "add auth",
)
VALIDATION_COMMAND = "python -m pytest tests/test_calculator_cli.py -q"


def run_prompt_jepa_demo(
    *,
    labels_path: Path,
    out_dir: Path,
    top_k: int = 5,
    embedding_dim: int = 256,
) -> dict[str, object]:
    """Build a local Prompt-JEPA demo and return the report record."""

    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    labels = labels_path.expanduser().resolve()
    out = out_dir.expanduser().resolve()
    _prepare_demo_out_dir(out)

    timings: dict[str, float] = {}
    labels_index_path = out / "labels-index.json"
    mixed_index_path = out / "index.json"
    records_path = out / "outcomes.jsonl"
    transitions_path = out / TRANSITION_ARTIFACT
    report_path = out / "report.json"

    started = time.perf_counter()
    records = load_prompt_intent_records(labels)
    timings["load_labels_seconds"] = _elapsed(started)

    started = time.perf_counter()
    labels_index = build_prompt_jepa_index_from_sources(
        labels_path=labels,
        embedding_dim=embedding_dim,
    )
    save_prompt_jepa_index(labels_index, labels_index_path)
    timings["build_labels_index_seconds"] = _elapsed(started)

    started = time.perf_counter()
    retrieval_eval = evaluate_prompt_jepa_retrieval(
        records,
        embedding_dim=embedding_dim,
        top_k=top_k,
        miss_limit=5,
        source_path=labels,
    )
    timings["held_out_retrieval_eval_seconds"] = _elapsed(started)

    started = time.perf_counter()
    generated_results, outcome_states = _record_demo_outcomes(
        records_path=records_path,
        out_dir=out,
        embedding_dim=embedding_dim,
    )
    timings["generate_and_validate_calculator_seconds"] = _elapsed(started)

    started = time.perf_counter()
    outcome_rows = _load_jsonl_objects(records_path)
    transition_rows = build_prompt_repo_transition_rows(
        outcome_rows,
        outcome_states,
        embedding_dim=embedding_dim,
    )
    write_prompt_repo_transitions_jsonl(transition_rows, transitions_path)
    timings["build_prompt_repo_transition_rows_seconds"] = _elapsed(started)

    started = time.perf_counter()
    source_embeddings = _write_source_embedding_sidecar(
        generated_results=generated_results,
        out_dir=out,
        embedding_dim=embedding_dim,
    )
    timings["embed_generated_python_source_seconds"] = _elapsed(started)

    started = time.perf_counter()
    mixed_index = build_prompt_jepa_index_from_sources(
        labels_path=labels,
        records_path=records_path,
        embedding_dim=embedding_dim,
    )
    save_prompt_jepa_index(mixed_index, mixed_index_path)
    timings["build_mixed_index_seconds"] = _elapsed(started)

    started = time.perf_counter()
    representative_queries = [
        {
            "prompt": prompt,
            "behavior": _representative_behavior(prompt),
            "top_results": [
                result.to_record() for result in mixed_index.query(prompt, top_k=top_k)
            ],
        }
        for prompt in REPRESENTATIVE_PROMPTS
    ]
    timings["representative_query_seconds"] = _elapsed(started)

    started = time.perf_counter()
    dry_run_proposals = [
        propose_from_prompt_jepa(mixed_index, prompt, top_k=top_k).to_record()
        for prompt in REPRESENTATIVE_PROMPTS
    ]
    timings["dry_run_proposal_seconds"] = _elapsed(started)

    report: dict[str, object] = {
        "schema_version": PROMPT_JEPA_DEMO_SCHEMA_VERSION,
        "decision": "demo_only_retrieval_not_wired_to_production",
        "labels": str(labels),
        "out": str(out),
        "top_k": top_k,
        "embedding_dim": embedding_dim,
        "corpus": _corpus_summary(records),
        "indexes": {
            "labels_index": str(labels_index_path),
            "mixed_index": str(mixed_index_path),
            "labels_index_rows": len(labels_index.rows),
            "mixed_index_rows": len(mixed_index.rows),
        },
        "held_out_retrieval_eval": retrieval_eval.to_record(),
        "generated_calculator_results": generated_results,
        "source_embeddings": source_embeddings,
        "transitions": {
            "artifact": str(transitions_path),
            "rows": len(transition_rows),
            "schema_version": "prompt-repo-transition-v1",
        },
        "representative_queries": representative_queries,
        "dry_run_proposals": dry_run_proposals,
        "artifact_sizes_bytes": _artifact_sizes(out),
        "timings_seconds": timings,
        "hosted_llm_api_tokens": 0,
        "hosted_repo_context_bytes": 0,
        "report": str(report_path),
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _prepare_demo_out_dir(out_dir: Path) -> None:
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"demo output path is not a directory: {out_dir}")
    marker = out_dir / DEMO_OUTPUT_MARKER
    if out_dir.exists() and any(out_dir.iterdir()) and not marker.exists():
        raise ValueError(
            "refusing to reuse non-empty directory without "
            f"{DEMO_OUTPUT_MARKER}: {out_dir}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    for child in list(out_dir.iterdir()):
        if child.name == DEMO_OUTPUT_MARKER:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    marker.write_text("Prompt-JEPA demo output directory\n", encoding="utf-8")


def _record_demo_outcomes(
    *,
    records_path: Path,
    out_dir: Path,
    embedding_dim: int,
) -> tuple[dict[str, object], tuple[PromptRepoOutcomeState, ...]]:
    repos_dir = out_dir / "repos"
    simple_repo = repos_dir / "simple-calc"
    blocked_auth_repo = repos_dir / "blocked-auth"
    outcome_states: list[PromptRepoOutcomeState] = []

    simple_repo.mkdir(parents=True, exist_ok=True)
    simple_before = encode_repo_state_record(simple_repo, embedding_dim=embedding_dim)
    simple_result = _record_implement(
        prompt="make me a simple cli calc",
        repo_dir=simple_repo,
        records_path=records_path,
    )
    simple_after = encode_repo_state_record(simple_repo, embedding_dim=embedding_dim)
    outcome_states.append(
        PromptRepoOutcomeState(repo_before=simple_before, repo_after=simple_after)
    )

    blocked_auth_repo.mkdir(parents=True, exist_ok=True)
    blocked_before = encode_repo_state_record(
        blocked_auth_repo,
        embedding_dim=embedding_dim,
    )
    blocked_result = _record_implement(
        prompt="add auth",
        repo_dir=blocked_auth_repo,
        records_path=records_path,
    )
    blocked_after = encode_repo_state_record(
        blocked_auth_repo,
        embedding_dim=embedding_dim,
    )
    outcome_states.append(
        PromptRepoOutcomeState(repo_before=blocked_before, repo_after=blocked_after)
    )

    change_before = encode_repo_state_record(simple_repo, embedding_dim=embedding_dim)
    change_result = _record_change(
        prompt="add exponent support",
        repo_dir=simple_repo,
        records_path=records_path,
    )
    change_after = encode_repo_state_record(simple_repo, embedding_dim=embedding_dim)
    outcome_states.append(
        PromptRepoOutcomeState(repo_before=change_before, repo_after=change_after)
    )

    return (
        {
            "records": str(records_path),
            "supported": [simple_result, change_result],
            "blocked": [blocked_result],
        },
        tuple(outcome_states),
    )


def _record_implement(
    *,
    prompt: str,
    repo_dir: Path,
    records_path: Path,
) -> dict[str, object]:
    intent = predict_prompt_intent(prompt)
    spec = parse_request_to_spec(prompt, intent=intent)
    plan = plan_calculator_repo(spec)
    build_result = build_calculator_repo(plan, repo_dir)

    files_written: list[str] = []
    if spec.clarifications_needed:
        validation = _blocked_validation()
    else:
        spec_artifact = repo_dir / "request-spec.json"
        spec_artifact.write_text(
            json.dumps(spec.to_record(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files_written = [*build_result.files_written, spec_artifact.name]
        validation = _run_generated_repo_validation(repo_dir)
        _remove_validation_cache(repo_dir)

    append_request_repo_attempt(
        records_path,
        raw_prompt=prompt,
        spec=spec,
        plan=plan,
        build_result=build_result,
        validation=validation,
        out_dir=repo_dir,
        files_written=files_written,
        source="j3 demo-prompt-jepa",
    )

    return {
        "prompt": prompt,
        "repo": str(repo_dir),
        "kind": "implement",
        "status": build_result.status,
        "domain": spec.domain,
        "features": list(spec.features),
        "files_written": files_written,
        "validation": _validation_summary(validation),
        "clarifications_needed": [dict(item) for item in spec.clarifications_needed],
    }


def _record_change(
    *,
    prompt: str,
    repo_dir: Path,
    records_path: Path,
) -> dict[str, object]:
    intent = predict_prompt_intent(prompt)
    spec = parse_existing_repo_change_to_spec(prompt, intent=intent)
    plan = plan_existing_repo_change(spec, repo_dir)
    result = apply_existing_repo_change(plan, repo_dir, validate=True)
    _remove_validation_cache(repo_dir)
    append_existing_repo_change_attempt(
        records_path,
        raw_prompt=prompt,
        spec=spec,
        plan=plan,
        result=result,
        source="j3 demo-prompt-jepa",
    )
    return {
        "prompt": prompt,
        "repo": str(repo_dir),
        "kind": "change",
        "status": result.status,
        "domain": spec.domain,
        "features_added": list(spec.features_to_add),
        "files_changed": list(result.files_changed),
        "validation": _validation_summary(result.validation),
    }


def _run_generated_repo_validation(repo_dir: Path) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_ADDOPTS"] = (
        f"{env.get('PYTEST_ADDOPTS', '')} -p no:cacheprovider"
    ).strip()
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_calculator_cli.py", "-q"],
        cwd=repo_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": VALIDATION_COMMAND,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _blocked_validation() -> dict[str, object]:
    return {
        "status": "not_run",
        "command": None,
        "exit_code": None,
        "reason": "blocked_clarification",
    }


def _remove_validation_cache(repo_dir: Path) -> None:
    cache_dir = repo_dir / ".pytest_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    for pycache in repo_dir.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)


def _validation_summary(validation: Mapping[str, object]) -> dict[str, object]:
    return {
        "status": validation.get("status"),
        "command": validation.get("command"),
        "exit_code": validation.get("exit_code"),
    }


def _representative_behavior(prompt: str) -> dict[str, object]:
    if prompt == "make me a simple cli calc":
        return {
            "category": "supported",
            "production_path": "implemented_and_validated_in_demo",
        }
    if prompt == "add exponent support":
        return {
            "category": "supported",
            "production_path": "changed_existing_calculator_and_validated_in_demo",
        }
    if prompt == "add auth":
        return {
            "category": "blocked",
            "production_path": "blocked_by_request_spec_clarification",
        }
    return {
        "category": "retrieval_only",
        "production_path": "no_structured_builder_wired_for_this_prompt",
    }


def _corpus_summary(records: Sequence[object]) -> dict[str, object]:
    split_counts = Counter(getattr(record, "split") for record in records)
    source_counts = Counter(getattr(record, "source_type") for record in records)
    task_counts = Counter(getattr(record.target, "task_type") for record in records)
    domain_counts = Counter(getattr(record.target, "domain") for record in records)
    return {
        "rows": len(records),
        "split_counts": dict(sorted(split_counts.items())),
        "source_type_counts": dict(sorted(source_counts.items())),
        "task_type_counts": dict(sorted(task_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
    }


def _artifact_sizes(out_dir: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    total = 0
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.name == DEMO_OUTPUT_MARKER:
            continue
        size = path.stat().st_size
        total += size
        sizes[str(path.relative_to(out_dir))] = size
    sizes["total_demo_artifact_bytes"] = total
    return sizes


def _load_jsonl_objects(path: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"demo outcome row {line_index} must be an object")
            rows.append(row)
    return tuple(rows)


def _write_source_embedding_sidecar(
    *,
    generated_results: Mapping[str, object],
    out_dir: Path,
    embedding_dim: int,
) -> dict[str, object]:
    artifact_path = out_dir / SOURCE_EMBEDDING_ARTIFACT
    repo_dirs = _supported_generated_repo_dirs(generated_results)

    files: list[dict[str, object]] = []
    repos: list[dict[str, object]] = []
    aggregate_hasher = sha256()
    total_bytes = 0

    for repo_dir in repo_dirs:
        repo_files: list[dict[str, object]] = []
        for source_path in sorted(repo_dir.rglob("*.py")):
            if not source_path.is_file():
                continue
            source_bytes = source_path.read_bytes()
            source_text = source_bytes.decode("utf-8")
            digest = sha256(source_bytes).hexdigest()
            embedding = embed_python_source(source_text, dim=embedding_dim)
            relative_path = source_path.relative_to(out_dir).as_posix()
            repo_relative_path = source_path.relative_to(repo_dir).as_posix()
            total_bytes += len(source_bytes)
            aggregate_hasher.update(relative_path.encode("utf-8"))
            aggregate_hasher.update(b"\0")
            aggregate_hasher.update(digest.encode("ascii"))
            aggregate_hasher.update(b"\0")
            file_record = {
                "path": relative_path,
                "repo": repo_dir.relative_to(out_dir).as_posix(),
                "repo_relative_path": repo_relative_path,
                "bytes": len(source_bytes),
                "sha256": digest,
                "embedding_length": len(embedding),
                "embedding": embedding,
            }
            repo_files.append(file_record)
            files.append(file_record)

        repo_hasher = sha256()
        repo_bytes = 0
        for file_record in repo_files:
            repo_hasher.update(str(file_record["repo_relative_path"]).encode("utf-8"))
            repo_hasher.update(b"\0")
            repo_hasher.update(str(file_record["sha256"]).encode("ascii"))
            repo_hasher.update(b"\0")
            repo_bytes += int(file_record["bytes"])
        repos.append(
            {
                "path": repo_dir.relative_to(out_dir).as_posix(),
                "file_count": len(repo_files),
                "python_source_bytes": repo_bytes,
                "source_sha256": repo_hasher.hexdigest() if repo_files else None,
            }
        )

    embedding_lengths = sorted(
        {int(file_record["embedding_length"]) for file_record in files}
    )
    source_digest = aggregate_hasher.hexdigest() if files else None
    sidecar = {
        "schema_version": SOURCE_EMBEDDING_SIDECAR_SCHEMA_VERSION,
        "artifact": str(artifact_path),
        "out": str(out_dir),
        "embedding_feature_version": PYTHON_SOURCE_FEATURE_VERSION,
        "embedding_dim": embedding_dim,
        "repo_count": len(repo_dirs),
        "file_count": len(files),
        "python_source_bytes": total_bytes,
        "source_sha256": source_digest,
        "repos": repos,
        "files": files,
    }
    artifact_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": SOURCE_EMBEDDING_SIDECAR_SCHEMA_VERSION,
        "artifact": str(artifact_path),
        "embedding_feature_version": PYTHON_SOURCE_FEATURE_VERSION,
        "embedding_dim": embedding_dim,
        "embedding_lengths": embedding_lengths,
        "repo_count": len(repo_dirs),
        "file_count": len(files),
        "python_source_bytes": total_bytes,
        "source_sha256": source_digest,
    }


def _supported_generated_repo_dirs(generated_results: Mapping[str, object]) -> list[Path]:
    seen: set[Path] = set()
    repo_dirs: list[Path] = []
    supported = generated_results.get("supported", [])
    if not isinstance(supported, list):
        return repo_dirs
    for item in supported:
        if not isinstance(item, Mapping):
            continue
        repo = item.get("repo")
        if not isinstance(repo, str):
            continue
        repo_dir = Path(repo).resolve()
        if repo_dir in seen or not repo_dir.is_dir():
            continue
        seen.add(repo_dir)
        repo_dirs.append(repo_dir)
    return repo_dirs


def _elapsed(started: float) -> float:
    return round(time.perf_counter() - started, 6)
