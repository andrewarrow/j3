"""Run transition shadow suites from a checked-in matrix manifest."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from j3.transition_shadow_suite import HOSTED_USAGE_FIELDS, run_transition_shadow_suite


TRANSITION_SHADOW_MATRIX_VERSION = "transition-shadow-matrix-run-v1"
MATRIX_MANIFEST = "matrix-manifest.json"
MATRIX_SUMMARY = "matrix-summary.json"
MATRIX_SUITE_DIR = "suite"
MATRIX_TASK_SUBSET_DIR = "task-subsets"
MATRIX_EVIDENCE_DIR = "evidence"
MATRIX_EVIDENCE_MANIFEST = "manifest.json"
MATRIX_EVIDENCE_CHECKSUMS = "checksums.sha256"


def run_transition_shadow_matrix(
    *,
    matrix_path: Path,
    out_dir: Path,
    only: str | None = None,
    force: bool = False,
) -> dict[str, object]:
    """Run each suite in a transition shadow matrix manifest."""

    started = time.perf_counter()
    matrix_file = matrix_path.expanduser().resolve()
    matrix = _load_matrix(matrix_file)
    out = out_dir.expanduser().resolve()
    _prepare_matrix_out(out, force=force)

    suites = _selected_suites(matrix, only=only)
    suite_manifests = []
    for suite in suites:
        suite_id = _suite_id(suite)
        suite_out = out / MATRIX_SUITE_DIR / suite_id
        tasks = _tasks_for_suite(suite, out=out)
        parameters = _runner_parameters(matrix, suite)
        suite_manifest = run_transition_shadow_suite(
            tasks=tasks,
            out_dir=suite_out,
            repo_root=Path(str(parameters["repo_root"])),
            prompt_corpus=Path(str(parameters["prompt_corpus"])),
            checkpoint=(
                Path(str(parameters["checkpoint"]))
                if parameters.get("checkpoint") is not None
                else None
            ),
            ranker=(
                Path(str(parameters["ranker"]))
                if parameters.get("ranker") is not None
                else None
            ),
            timeout_seconds=int(parameters["timeout_seconds"]),
            max_candidates=int(parameters["max_candidates"]),
            max_steps=int(parameters["max_steps"]),
            explore_after_pass=int(parameters["explore_after_pass"]),
            top_k=int(parameters["top_k"]),
            embedding_dim=int(parameters["embedding_dim"]),
            split_by=str(parameters["split_by"]),
            validation_fraction=float(parameters["validation_fraction"]),
            epochs=int(parameters["epochs"]),
            learning_rate=float(parameters["learning_rate"]),
            margin=float(parameters["margin"]),
            residual_limit=int(parameters["residual_limit"]),
            force=force,
        )
        suite_manifests.append({"suite": dict(suite), "manifest": suite_manifest})

    summary = _matrix_summary(
        matrix_file=matrix_file,
        out=out,
        matrix=matrix,
        only=only,
        suite_manifests=suite_manifests,
        runtime_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    summary = {
        **summary,
        "artifacts": {
            **_mapping(summary.get("artifacts")),
            "evidence_manifest": str(out / MATRIX_EVIDENCE_DIR / MATRIX_EVIDENCE_MANIFEST),
            "evidence_checksums": str(out / MATRIX_EVIDENCE_DIR / MATRIX_EVIDENCE_CHECKSUMS),
        },
        "evidence": {
            "schema_version": "transition-shadow-matrix-evidence-summary-v1",
            "manifest": str(out / MATRIX_EVIDENCE_DIR / MATRIX_EVIDENCE_MANIFEST),
            "checksums": str(out / MATRIX_EVIDENCE_DIR / MATRIX_EVIDENCE_CHECKSUMS),
        },
    }
    matrix_manifest = _matrix_manifest(
        matrix_file=matrix_file,
        out=out,
        matrix=matrix,
        only=only,
        summary=summary,
        suite_manifests=suite_manifests,
    )
    _write_json(out / MATRIX_MANIFEST, matrix_manifest)
    _write_json(out / MATRIX_SUMMARY, summary)
    evidence = _write_matrix_evidence(out, summary=summary, manifest=matrix_manifest)
    summary = {
        **summary,
        "evidence": evidence,
    }
    _write_json(out / MATRIX_SUMMARY, summary)
    _write_matrix_evidence(out, summary=summary, manifest=matrix_manifest)
    return summary


def format_transition_shadow_matrix_summary(summary: Mapping[str, object]) -> str:
    """Format a matrix run summary for CLI output."""

    totals = _mapping(summary.get("totals"))
    lines = [
        "j3 run-transition-shadow-matrix complete",
        f"out: {summary.get('out')}",
        f"suites: {totals.get('suite_count', 0)}",
        f"tasks: {totals.get('task_count', 0)}",
        f"ranked solved: {totals.get('ranked_solved', 0)}",
        f"advice rows: {totals.get('advice_rows', 0)}",
        f"advice candidates: {totals.get('candidate_count', 0)}",
        f"held-out groups: {totals.get('held_out_group_count', 0)}",
        f"zero hosted usage: {str(summary.get('zero_hosted_usage')).lower()}",
        f"matrix summary: {_mapping(summary.get('artifacts')).get('summary')}",
    ]
    for suite in _list(summary.get("suites")):
        suite_record = _mapping(suite)
        lines.append(
            "suite "
            f"{suite_record.get('id')}: gate={suite_record.get('v3_gate')} "
            f"tasks={suite_record.get('task_count')} "
            f"solved={suite_record.get('ranked_solved')}"
        )
    return "\n".join(lines)


def _load_matrix(matrix_file: Path) -> dict[str, object]:
    if not matrix_file.exists():
        raise FileNotFoundError(f"transition shadow matrix does not exist: {matrix_file}")
    if not matrix_file.is_file():
        raise IsADirectoryError(f"transition shadow matrix path is not a file: {matrix_file}")
    matrix = json.loads(matrix_file.read_text(encoding="utf-8"))
    if not isinstance(matrix, dict):
        raise ValueError("transition shadow matrix must be a JSON object")
    if matrix.get("schema_version") != "transition-shadow-matrix-v1":
        raise ValueError("unsupported transition shadow matrix schema")
    if not isinstance(matrix.get("suites"), list) or not matrix["suites"]:
        raise ValueError("transition shadow matrix requires at least one suite")
    return matrix


def _prepare_matrix_out(out: Path, *, force: bool) -> None:
    allowed = {
        MATRIX_MANIFEST,
        MATRIX_SUMMARY,
        MATRIX_SUITE_DIR,
        MATRIX_TASK_SUBSET_DIR,
        MATRIX_EVIDENCE_DIR,
    }
    if out.exists() and not out.is_dir():
        raise NotADirectoryError(f"matrix output path is not a directory: {out}")
    if out.exists():
        entries = list(out.iterdir())
        if entries and not force:
            raise FileExistsError(
                f"matrix output directory is not empty: {out}; pass --force to overwrite matrix files"
            )
        unknown = [entry for entry in entries if entry.name not in allowed]
        if unknown:
            raise FileExistsError(
                "matrix output directory contains unknown files: "
                + ", ".join(str(path) for path in unknown)
            )
        for entry in entries:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    out.mkdir(parents=True, exist_ok=True)


def _selected_suites(
    matrix: Mapping[str, object],
    *,
    only: str | None,
) -> list[Mapping[str, object]]:
    suites = [_mapping(suite) for suite in _list(matrix.get("suites"))]
    if only is None:
        return suites
    selected = [suite for suite in suites if suite.get("id") == only]
    if not selected:
        known = ", ".join(str(suite.get("id")) for suite in suites)
        raise ValueError(f"unknown transition shadow matrix suite: {only}; known suites: {known}")
    return selected


def _tasks_for_suite(suite: Mapping[str, object], *, out: Path) -> list[Path]:
    tasks_path = Path(str(suite["tasks"]))
    task_names = suite.get("task_names")
    if task_names is None:
        return [tasks_path]
    names = [str(name) for name in _list(task_names)]
    if not names:
        raise ValueError(f"suite {suite.get('id')} task_names must not be empty")
    subset_dir = out / MATRIX_TASK_SUBSET_DIR / _suite_id(suite)
    subset_dir.mkdir(parents=True, exist_ok=True)
    manifest = tasks_path / "tasks.json" if tasks_path.is_dir() else tasks_path
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"suite {suite.get('id')} tasks manifest must be a list")
    by_name = {
        str(row.get("name")): dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("name") is not None
    }
    missing = [name for name in names if name not in by_name]
    if missing:
        raise ValueError(
            f"suite {suite.get('id')} task_names missing from manifest: {', '.join(missing)}"
        )
    filtered = []
    for name in names:
        row = dict(by_name[name])
        row["repo"] = str((manifest.parent / str(row.get("repo", "."))).resolve())
        filtered.append(row)
    _write_json(subset_dir / "tasks.json", filtered)
    return [subset_dir]


def _runner_parameters(
    matrix: Mapping[str, object],
    suite: Mapping[str, object],
) -> dict[str, object]:
    defaults = _mapping(matrix.get("defaults"))
    parameters = _mapping(suite.get("parameters"))
    return {
        "repo_root": defaults.get("repo_root", "."),
        "prompt_corpus": defaults.get(
            "prompt_corpus", "../prompts/coding_agent_prompts_expanded_v0.jsonl"
        ),
        "checkpoint": defaults.get("checkpoint", "runs/apache-python-git/model.json"),
        "ranker": defaults.get("ranker"),
        "max_steps": defaults.get("max_steps", 1),
        "top_k": defaults.get("top_k", 3),
        "embedding_dim": defaults.get("embedding_dim", 256),
        "epochs": defaults.get("epochs", 30),
        "learning_rate": defaults.get("learning_rate", 0.1),
        "margin": defaults.get("margin", 1.0),
        "residual_limit": defaults.get("residual_limit", 10),
        "timeout_seconds": parameters.get("timeout_seconds", 30),
        "max_candidates": parameters.get("max_candidates", 12),
        "explore_after_pass": parameters.get("explore_after_pass", 1),
        "split_by": parameters.get("split_by", "order"),
        "validation_fraction": parameters.get("validation_fraction", 0.25),
    }


def _matrix_summary(
    *,
    matrix_file: Path,
    out: Path,
    matrix: Mapping[str, object],
    only: str | None,
    suite_manifests: Sequence[Mapping[str, object]],
    runtime_ms: float,
) -> dict[str, object]:
    suite_records = [
        _suite_summary_record(record["suite"], record["manifest"])
        for record in suite_manifests
    ]
    usage = _usage_totals([record["manifest"] for record in suite_manifests])
    totals = {
        "suite_count": len(suite_records),
        "task_count": sum(_int(record.get("task_count")) for record in suite_records),
        "ranked_solved": sum(_int(record.get("ranked_solved")) for record in suite_records),
        "advice_rows": sum(_int(record.get("advice_rows")) for record in suite_records),
        "candidate_count": sum(_int(record.get("candidate_count")) for record in suite_records),
        "held_out_group_count": sum(
            _int(record.get("held_out_group_count")) for record in suite_records
        ),
        "residual_count": sum(_int(record.get("residual_count")) for record in suite_records),
        "baseline_residual_count": sum(
            _int(record.get("baseline_residual_count")) for record in suite_records
        ),
    }
    return {
        "schema_version": TRANSITION_SHADOW_MATRIX_VERSION,
        "matrix": str(matrix_file),
        "matrix_schema_version": matrix.get("schema_version"),
        "description": matrix.get("description"),
        "out": str(out),
        "only": only,
        "suites": suite_records,
        "totals": totals,
        "usage": usage,
        "zero_hosted_usage": all(value == 0 for value in usage.values()),
        "artifacts": {
            "manifest": str(out / MATRIX_MANIFEST),
            "summary": str(out / MATRIX_SUMMARY),
            "suite_dir": str(out / MATRIX_SUITE_DIR),
            "evidence": str(out / MATRIX_EVIDENCE_DIR),
        },
        "runtime": {
            "local_runtime_ms": runtime_ms,
            **usage,
        },
    }


def _suite_summary_record(
    suite: Mapping[str, object],
    manifest: Mapping[str, object],
) -> dict[str, object]:
    eval_summary = _mapping(manifest.get("eval"))
    advice = _mapping(manifest.get("advice_summary"))
    validation = _mapping(_mapping(manifest.get("shadow_scorer_v3")).get("validation"))
    readiness = _mapping(validation.get("product_readiness"))
    split = _mapping(_mapping(manifest.get("shadow_scorer_v3")).get("split"))
    deltas = _mapping(readiness.get("metrics"))
    return {
        "id": _suite_id(suite),
        "tasks": suite.get("tasks"),
        "task_names": suite.get("task_names"),
        "out": manifest.get("out"),
        "manifest": _mapping(manifest.get("artifacts")).get("manifest")
        or str(Path(str(manifest.get("out"))) / "manifest.json"),
        "task_count": eval_summary.get("task_count", 0),
        "ranked_solved": eval_summary.get("ranked_solved", 0),
        "advice_rows": advice.get("advice_row_count", 0),
        "candidate_count": advice.get("candidate_count", 0),
        "held_out_group_count": split.get(
            "validation_group_count", validation.get("group_count", 0)
        ),
        "v3_gate": readiness.get("gate_result"),
        "eligible_for_shadow_mode": readiness.get("eligible_for_shadow_mode"),
        "eligible_for_guarded_opt_in": readiness.get("eligible_for_guarded_opt_in"),
        "v3_vs_existing_rank_order": {
            "pass_at_1_delta": _mapping(deltas.get("pass_at_1")).get("delta"),
            "top_k_delta": _mapping(deltas.get("top_k")).get("delta"),
            "mean_reciprocal_rank_delta": _mapping(
                deltas.get("mean_reciprocal_rank")
            ).get("delta"),
            "average_candidates_before_first_pass_delta": _mapping(
                deltas.get("average_candidates_validated_before_first_pass")
            ).get("delta"),
        },
        "residual_count": readiness.get("residual_count", 0),
        "baseline_residual_count": readiness.get("baseline_residual_count", 0),
        "zero_hosted_usage": manifest.get("zero_hosted_usage") is True,
        "usage": manifest.get("usage"),
    }


def _matrix_manifest(
    *,
    matrix_file: Path,
    out: Path,
    matrix: Mapping[str, object],
    only: str | None,
    summary: Mapping[str, object],
    suite_manifests: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": TRANSITION_SHADOW_MATRIX_VERSION,
        "matrix": str(matrix_file),
        "out": str(out),
        "only": only,
        "source_manifest": matrix,
        "suite_manifests": [
            {
                "id": _suite_id(record["suite"]),
                "manifest": str(Path(str(record["manifest"].get("out"))) / "manifest.json"),
                "out": record["manifest"].get("out"),
            }
            for record in suite_manifests
        ],
        "summary": {
            "path": str(out / MATRIX_SUMMARY),
            "totals": summary.get("totals"),
            "zero_hosted_usage": summary.get("zero_hosted_usage"),
        },
        "commands": {
            "schema_version": "transition-shadow-matrix-commands-v1",
            "run_matrix": [
                "python cli.py run-transition-shadow-matrix "
                f"--matrix {matrix_file} --out {out}"
                + (f" --only {only}" if only else "")
            ],
            "verify_json": [
                f"python -m json.tool {out / MATRIX_SUMMARY} >/dev/null",
                f"python -m json.tool {out / MATRIX_MANIFEST} >/dev/null",
                f"python -m json.tool {out / MATRIX_EVIDENCE_DIR / MATRIX_EVIDENCE_MANIFEST} >/dev/null",
            ],
        },
    }


def _write_matrix_evidence(
    out: Path,
    *,
    summary: Mapping[str, object],
    manifest: Mapping[str, object],
) -> dict[str, object]:
    evidence = out / MATRIX_EVIDENCE_DIR
    evidence.mkdir(parents=True, exist_ok=True)
    evidence_manifest = {
        "schema_version": "transition-shadow-matrix-evidence-v1",
        "matrix_manifest": str(out / MATRIX_MANIFEST),
        "matrix_summary": str(out / MATRIX_SUMMARY),
        "suite_evidence_manifests": [
            str(Path(str(suite.get("out"))) / "evidence" / "manifest.json")
            for suite in _list(summary.get("suites"))
        ],
        "zero_hosted_usage": summary.get("zero_hosted_usage") is True,
        "totals": summary.get("totals"),
    }
    _write_json(evidence / MATRIX_EVIDENCE_MANIFEST, evidence_manifest)
    checksum_records = _checksum_records(
        [
            out / MATRIX_MANIFEST,
            out / MATRIX_SUMMARY,
            evidence / MATRIX_EVIDENCE_MANIFEST,
            *[
                Path(str(suite.get("out"))) / "evidence" / "manifest.json"
                for suite in _list(summary.get("suites"))
            ],
        ]
    )
    (evidence / MATRIX_EVIDENCE_CHECKSUMS).write_text(
        "\n".join(
            f"{record['sha256']}  {record['path']}" for record in checksum_records
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "transition-shadow-matrix-evidence-summary-v1",
        "manifest": str(evidence / MATRIX_EVIDENCE_MANIFEST),
        "checksums": str(evidence / MATRIX_EVIDENCE_CHECKSUMS),
        "artifact_count": len(checksum_records),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _usage_totals(reports: Sequence[object]) -> dict[str, int]:
    totals = {field: 0 for field in HOSTED_USAGE_FIELDS}
    for report in reports:
        usage = _mapping(_mapping(report).get("usage"))
        for field in HOSTED_USAGE_FIELDS:
            value = usage.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                totals[field] += value
    return totals


def _checksum_records(paths: Sequence[Path]) -> list[dict[str, object]]:
    records = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        records.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _suite_id(suite: Mapping[str, object]) -> str:
    suite_id = str(suite.get("id", "")).strip()
    if not suite_id:
        raise ValueError("matrix suite id must not be empty")
    return suite_id


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
