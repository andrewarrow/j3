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
from pathlib import Path
from typing import Any, Mapping, Sequence

from existing_repo_change import (
    append_existing_repo_change_attempt,
    apply_existing_repo_change,
    parse_existing_repo_change_to_spec,
    plan_existing_repo_change,
)
from greenfield import build_calculator_repo, plan_calculator_repo
from prompt_intents import load_prompt_intent_records, predict_prompt_intent
from prompt_jepa import (
    build_prompt_jepa_index_from_sources,
    evaluate_prompt_jepa_retrieval,
    propose_from_prompt_jepa,
    save_prompt_jepa_index,
)
from request_outcomes import append_request_repo_attempt
from request_spec import parse_request_to_spec


PROMPT_JEPA_DEMO_SCHEMA_VERSION = "prompt-jepa-demo-report-v1"
DEMO_OUTPUT_MARKER = ".j3-prompt-jepa-demo"
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
    generated_results = _record_demo_outcomes(records_path=records_path, out_dir=out)
    timings["generate_and_validate_calculator_seconds"] = _elapsed(started)

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
) -> dict[str, object]:
    repos_dir = out_dir / "repos"
    simple_repo = repos_dir / "simple-calc"
    blocked_auth_repo = repos_dir / "blocked-auth"

    simple_result = _record_implement(
        prompt="make me a simple cli calc",
        repo_dir=simple_repo,
        records_path=records_path,
    )
    blocked_result = _record_implement(
        prompt="add auth",
        repo_dir=blocked_auth_repo,
        records_path=records_path,
    )
    change_result = _record_change(
        prompt="add exponent support",
        repo_dir=simple_repo,
        records_path=records_path,
    )

    return {
        "records": str(records_path),
        "supported": [simple_result, change_result],
        "blocked": [blocked_result],
    }


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


def _elapsed(started: float) -> float:
    return round(time.perf_counter() - started, 6)
