"""Repeatable local transition shadow evidence suite."""

from __future__ import annotations

import json
import shlex
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation import EvalSummary, evaluate_tasks, write_candidate_outcomes
from evaluation import write_eval_diagnostics
from j3.transition_action_choice import build_transition_action_choice_groups_jsonl
from j3.transition_action_scoring import evaluate_transition_shadow_scorer_v3
from j3.transition_bench_demo import run_transition_bench_demo
from j3.transition_evidence_bundle import build_transition_evidence_bundle
from j3.transition_scorer_advice import summarize_transition_scorer_advice
from j3.transition_shadow_outcomes import (
    load_transition_shadow_outcomes,
    normalize_transition_shadow_outcomes,
    summarize_transition_shadow_outcomes,
    write_transition_shadow_outcomes_jsonl,
)


TRANSITION_SHADOW_SUITE_VERSION = "transition-shadow-suite-v1"
DEFAULT_TRANSITION_SHADOW_SUITE_TASKS = (Path("examples/greenshot_bugs"),)
DEFAULT_TRANSITION_SHADOW_SUITE_CHECKPOINT = Path("runs/apache-python-git/model.json")

SUITE_CANDIDATE_OUTCOMES = "candidate-outcomes.jsonl"
SUITE_TRANSITION_ADVICE = "transition-advice.jsonl"
SUITE_DIAGNOSTICS = "diagnostics.json"
SUITE_ADVICE_SUMMARY = "advice-summary.json"
SUITE_SHADOW_OUTCOMES = "transition-shadow-outcomes.jsonl"
SUITE_SHADOW_OUTCOME_SUMMARY = "transition-shadow-outcome-summary.json"
SUITE_BENCH_REPORT = "transition-bench-report.json"
SUITE_SHADOW_SCORER_REPORT = "shadow-scorer-v3-report.json"
SUITE_MANIFEST = "manifest.json"
SUITE_EVIDENCE_DIR = "evidence"

HOSTED_USAGE_FIELDS = (
    "hosted_llm_api_calls",
    "hosted_llm_prompt_tokens",
    "hosted_llm_completion_tokens",
    "hosted_api_tokens",
    "hosted_repo_context_bytes",
)


def run_transition_shadow_suite(
    *,
    tasks: Sequence[Path] = DEFAULT_TRANSITION_SHADOW_SUITE_TASKS,
    out_dir: Path,
    repo_root: Path = Path("."),
    prompt_corpus: Path = Path("../prompts/coding_agent_prompts_expanded_v0.jsonl"),
    checkpoint: Path | None = DEFAULT_TRANSITION_SHADOW_SUITE_CHECKPOINT,
    ranker: Path | None = None,
    timeout_seconds: int = 30,
    max_candidates: int = 12,
    max_steps: int = 1,
    explore_after_pass: int = 1,
    top_k: int = 3,
    embedding_dim: int = 256,
    split_by: str = "order",
    validation_fraction: float = 0.25,
    epochs: int = 30,
    learning_rate: float = 0.1,
    margin: float = 1.0,
    residual_limit: int = 10,
    force: bool = False,
) -> dict[str, object]:
    """Run the local shadow evidence workflow and write all suite artifacts."""

    if not tasks:
        raise ValueError("at least one task path is required")
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    if explore_after_pass < 0:
        raise ValueError("explore_after_pass must be >= 0")

    started = time.perf_counter()
    repo = repo_root.expanduser().resolve()
    out = out_dir.expanduser().resolve()
    _prepare_suite_out(out, force=force)

    task_paths = [path.expanduser().resolve() for path in tasks]
    summaries = [
        evaluate_tasks(
            tasks_path=task_path,
            model_path=checkpoint,
            ranker_path=ranker,
            timeout_seconds=timeout_seconds,
            max_candidates=max_candidates,
            max_steps=max_steps,
            phase="ranked",
            explore_after_pass=explore_after_pass,
            transition_scorer_shadow=True,
            transition_scorer_rank=False,
            transition_ranking_gate=None,
            progress=None,
        )
        for task_path in task_paths
    ]
    summary = EvalSummary(
        tasks=[task for suite_summary in summaries for task in suite_summary.tasks]
    )

    candidate_outcomes = write_candidate_outcomes(summary, out / SUITE_CANDIDATE_OUTCOMES)
    diagnostics = write_eval_diagnostics(summary, out / SUITE_DIAGNOSTICS)
    transition_advice = _write_suite_transition_advice(
        summary,
        out / SUITE_TRANSITION_ADVICE,
    )
    advice_summary = summarize_transition_scorer_advice([transition_advice]).as_dict()
    _write_json(out / SUITE_ADVICE_SUMMARY, advice_summary)

    shadow_rows = normalize_transition_shadow_outcomes(
        advice_paths=[transition_advice],
        candidate_outcome_paths=[candidate_outcomes],
    )
    shadow_outcomes = write_transition_shadow_outcomes_jsonl(
        out / SUITE_SHADOW_OUTCOMES,
        shadow_rows,
    )
    shadow_outcome_summary = summarize_transition_shadow_outcomes(
        shadow_rows,
        advice_paths=[transition_advice],
        candidate_outcome_paths=[candidate_outcomes],
        out_path=shadow_outcomes,
    ).as_dict()
    _write_json(out / SUITE_SHADOW_OUTCOME_SUMMARY, shadow_outcome_summary)

    bench_report = run_transition_bench_demo(
        repo_root=repo,
        prompt_corpus=prompt_corpus,
        candidate_outcomes=[candidate_outcomes],
        include_fixtures=False,
        top_k=top_k,
        embedding_dim=embedding_dim,
        residual_limit=residual_limit,
        out=out / SUITE_BENCH_REPORT,
    )

    groups = build_transition_action_choice_groups_jsonl(
        candidate_outcomes,
        embedding_dim=embedding_dim,
    )
    loaded_shadow_rows = load_transition_shadow_outcomes([shadow_outcomes])
    shadow_scorer_report = evaluate_transition_shadow_scorer_v3(
        groups,
        loaded_shadow_rows,
        top_k=top_k,
        split_by=split_by,
        validation_fraction=validation_fraction,
        epochs=epochs,
        learning_rate=learning_rate,
        margin=margin,
        allow_production_rank_feature=False,
        residual_limit=residual_limit,
    )
    shadow_scorer_report = {
        **shadow_scorer_report,
        "report": str(out / SUITE_SHADOW_SCORER_REPORT),
    }
    _write_json(out / SUITE_SHADOW_SCORER_REPORT, shadow_scorer_report)

    evidence_summary = build_transition_evidence_bundle(
        bench_report=out / SUITE_BENCH_REPORT,
        out_dir=out / SUITE_EVIDENCE_DIR,
        repo_root=repo,
        prompt_corpus=prompt_corpus,
        advice_paths=[transition_advice],
        shadow_scorer_report=out / SUITE_SHADOW_SCORER_REPORT,
        force=True,
    )

    manifest = _manifest(
        out=out,
        repo_root=repo,
        task_paths=task_paths,
        prompt_corpus=prompt_corpus,
        checkpoint=checkpoint,
        ranker=ranker,
        parameters={
            "timeout_seconds": timeout_seconds,
            "max_candidates": max_candidates,
            "max_steps": max_steps,
            "explore_after_pass": explore_after_pass,
            "top_k": top_k,
            "embedding_dim": embedding_dim,
            "split_by": split_by,
            "validation_fraction": validation_fraction,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "margin": margin,
            "residual_limit": residual_limit,
            "allow_production_rank_feature": False,
        },
        artifacts={
            "candidate_outcomes": candidate_outcomes,
            "transition_advice": transition_advice,
            "diagnostics": diagnostics,
            "advice_summary": out / SUITE_ADVICE_SUMMARY,
            "transition_shadow_outcomes": shadow_outcomes,
            "transition_shadow_outcome_summary": out / SUITE_SHADOW_OUTCOME_SUMMARY,
            "transition_bench_report": out / SUITE_BENCH_REPORT,
            "shadow_scorer_v3_report": out / SUITE_SHADOW_SCORER_REPORT,
            "evidence": out / SUITE_EVIDENCE_DIR,
            "evidence_manifest": out / SUITE_EVIDENCE_DIR / "manifest.json",
        },
        eval_summary=summary,
        bench_report=bench_report,
        advice_summary=advice_summary,
        shadow_outcome_summary=shadow_outcome_summary,
        shadow_scorer_report=shadow_scorer_report,
        evidence_summary=evidence_summary,
        runtime_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    _write_json(out / SUITE_MANIFEST, manifest)
    return manifest


def format_transition_shadow_suite_summary(summary: Mapping[str, object]) -> str:
    """Format the shadow suite result for CLI output."""

    eval_summary = _mapping(summary.get("eval"))
    artifacts = _mapping(summary.get("artifacts"))
    gate = _mapping(
        _mapping(_mapping(summary.get("shadow_scorer_v3")).get("validation")).get(
            "product_readiness"
        )
    )
    lines = [
        "j3 run-transition-shadow-suite complete",
        f"out: {summary.get('out')}",
        f"tasks: {eval_summary.get('task_count', 0)}",
        f"ranked solved: {eval_summary.get('ranked_solved', 0)}",
        f"candidate outcomes: {artifacts.get('candidate_outcomes')}",
        f"transition advice: {artifacts.get('transition_advice')}",
        f"diagnostics: {artifacts.get('diagnostics')}",
        f"advice summary: {artifacts.get('advice_summary')}",
        f"transition shadow outcomes: {artifacts.get('transition_shadow_outcomes')}",
        f"shadow scorer V3 report: {artifacts.get('shadow_scorer_v3_report')}",
        f"evidence manifest: {artifacts.get('evidence_manifest')}",
        f"zero hosted usage: {str(summary.get('zero_hosted_usage')).lower()}",
    ]
    if gate:
        lines.append(f"held-out V3 gate: {gate.get('gate_result')}")
    return "\n".join(lines)


def _prepare_suite_out(out: Path, *, force: bool) -> None:
    allowed = {
        SUITE_CANDIDATE_OUTCOMES,
        SUITE_TRANSITION_ADVICE,
        SUITE_DIAGNOSTICS,
        SUITE_ADVICE_SUMMARY,
        SUITE_SHADOW_OUTCOMES,
        SUITE_SHADOW_OUTCOME_SUMMARY,
        SUITE_BENCH_REPORT,
        SUITE_SHADOW_SCORER_REPORT,
        SUITE_MANIFEST,
        SUITE_EVIDENCE_DIR,
    }
    if out.exists() and not out.is_dir():
        raise NotADirectoryError(f"shadow suite output path is not a directory: {out}")
    if out.exists():
        entries = list(out.iterdir())
        if entries and not force:
            raise FileExistsError(
                f"shadow suite output directory is not empty: {out}; pass --force to overwrite suite files"
            )
        unknown = [entry for entry in entries if entry.name not in allowed]
        if unknown:
            raise FileExistsError(
                "shadow suite output directory contains unknown files: "
                + ", ".join(str(path) for path in unknown)
            )
        for entry in entries:
            if entry.is_dir():
                if entry.name != SUITE_EVIDENCE_DIR:
                    raise FileExistsError(f"shadow suite output contains a directory: {entry}")
                for child in entry.iterdir():
                    if child.is_file():
                        child.unlink()
                    else:
                        raise FileExistsError(
                            f"shadow suite evidence output contains a directory: {child}"
                        )
                entry.rmdir()
            elif entry.is_file():
                entry.unlink()
    out.mkdir(parents=True, exist_ok=True)


def _write_suite_transition_advice(summary: EvalSummary, path: Path) -> Path:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in summary.tasks:
        for plan in (task.baseline, task.ranked):
            if plan is not None and plan.transition_advice is not None:
                rows.append(plan.transition_advice)
    resolved.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return resolved


def _manifest(
    *,
    out: Path,
    repo_root: Path,
    task_paths: Sequence[Path],
    prompt_corpus: Path,
    checkpoint: Path | None,
    ranker: Path | None,
    parameters: Mapping[str, object],
    artifacts: Mapping[str, Path],
    eval_summary: EvalSummary,
    bench_report: Mapping[str, object],
    advice_summary: Mapping[str, object],
    shadow_outcome_summary: Mapping[str, object],
    shadow_scorer_report: Mapping[str, object],
    evidence_summary: Mapping[str, object],
    runtime_ms: float,
) -> dict[str, object]:
    usage = _usage_totals(
        [
            bench_report,
            advice_summary,
            shadow_outcome_summary,
            shadow_scorer_report,
            evidence_summary,
        ]
    )
    artifact_records = {name: str(path) for name, path in artifacts.items()}
    return {
        "schema_version": TRANSITION_SHADOW_SUITE_VERSION,
        "out": str(out),
        "repo_root": str(repo_root),
        "tasks": [str(path) for path in task_paths],
        "parameters": {
            **dict(parameters),
            "checkpoint": str(checkpoint.expanduser().resolve()) if checkpoint else None,
            "ranker": str(ranker.expanduser().resolve()) if ranker else None,
            "prompt_corpus": str(prompt_corpus.expanduser().resolve()),
        },
        "artifacts": artifact_records,
        "commands": _commands(
            out=out,
            repo_root=repo_root,
            task_paths=task_paths,
            prompt_corpus=prompt_corpus,
            checkpoint=checkpoint,
            ranker=ranker,
            parameters=parameters,
            artifacts=artifacts,
        ),
        "eval": {
            "task_count": eval_summary.total,
            "ranked_solved": eval_summary.ranked_solved,
            "ranked_pass_at_1": eval_summary.ranked_pass_at_1,
            "ranked_avg_candidates_tested": eval_summary.ranked_avg_candidates_tested,
            "phase": "ranked",
        },
        "transition_bench": {
            "row_count": _mapping(bench_report.get("transition_bench")).get("row_count"),
            "product_readiness": bench_report.get("product_readiness"),
        },
        "advice_summary": {
            "advice_row_count": advice_summary.get("advice_row_count"),
            "candidate_count": advice_summary.get("candidate_count"),
            "known_validation": advice_summary.get("known_validation"),
        },
        "transition_shadow_outcomes": {
            "rows": shadow_outcome_summary.get("rows"),
            "joined_rows": shadow_outcome_summary.get("joined_rows"),
            "known_validation_rows": shadow_outcome_summary.get(
                "known_validation_rows"
            ),
            "labels": shadow_outcome_summary.get("labels"),
        },
        "shadow_scorer_v3": {
            "available": shadow_scorer_report.get("available"),
            "split": shadow_scorer_report.get("split"),
            "validation": shadow_scorer_report.get("validation"),
        },
        "evidence_bundle": evidence_summary,
        "usage": usage,
        "zero_hosted_usage": all(value == 0 for value in usage.values()),
        "runtime": {
            "local_runtime_ms": runtime_ms,
            **usage,
        },
    }


def _commands(
    *,
    out: Path,
    repo_root: Path,
    task_paths: Sequence[Path],
    prompt_corpus: Path,
    checkpoint: Path | None,
    ranker: Path | None,
    parameters: Mapping[str, object],
    artifacts: Mapping[str, Path],
) -> dict[str, object]:
    eval_command = [
        "python",
        "cli.py",
        "eval",
        "--tasks",
        "<each --tasks path>",
        "--phase",
        "ranked",
        "--transition-scorer-shadow",
        "--transition-advice-out",
        str(artifacts["transition_advice"]),
        "--candidate-outcomes",
        str(artifacts["candidate_outcomes"]),
        "--diagnostics",
        str(artifacts["diagnostics"]),
        "--timeout",
        str(parameters["timeout_seconds"]),
        "--max-candidates",
        str(parameters["max_candidates"]),
        "--max-steps",
        str(parameters["max_steps"]),
        "--explore-after-pass",
        str(parameters["explore_after_pass"]),
        "--quiet",
    ]
    if checkpoint is not None:
        eval_command.extend(["--checkpoint", str(checkpoint.expanduser().resolve())])
    if ranker is not None:
        eval_command.extend(["--ranker", str(ranker.expanduser().resolve())])
    return {
        "schema_version": "transition-shadow-suite-commands-v1",
        "working_directory": str(repo_root),
        "hosted_usage_expectation": "all commands are local and require no hosted APIs",
        "run_suite": [_shell_join(_suite_command(out, repo_root, task_paths, prompt_corpus, checkpoint, ranker, parameters))],
        "component_commands": {
            "eval_shadow_evidence_template": [_shell_join(eval_command)],
            "summarize_transition_advice": [
                _shell_join(
                    [
                        "python",
                        "cli.py",
                        "summarize-transition-advice",
                        "--advice",
                        str(artifacts["transition_advice"]),
                        "--json",
                    ]
                )
            ],
            "normalize_transition_shadow_outcomes": [
                _shell_join(
                    [
                        "python",
                        "cli.py",
                        "normalize-transition-shadow-outcomes",
                        "--advice",
                        str(artifacts["transition_advice"]),
                        "--candidate-outcomes",
                        str(artifacts["candidate_outcomes"]),
                        "--out",
                        str(artifacts["transition_shadow_outcomes"]),
                        "--json",
                    ]
                )
            ],
            "evaluate_transition_shadow_scorer": [
                _shell_join(
                    [
                        "python",
                        "cli.py",
                        "evaluate-transition-shadow-scorer",
                        "--shadow-outcomes",
                        str(artifacts["transition_shadow_outcomes"]),
                        "--candidate-outcomes",
                        str(artifacts["candidate_outcomes"]),
                        "--split-by",
                        str(parameters["split_by"]),
                        "--validation-fraction",
                        str(parameters["validation_fraction"]),
                        "--top-k",
                        str(parameters["top_k"]),
                        "--embedding-dim",
                        str(parameters["embedding_dim"]),
                        "--epochs",
                        str(parameters["epochs"]),
                        "--learning-rate",
                        str(parameters["learning_rate"]),
                        "--margin",
                        str(parameters["margin"]),
                        "--residual-limit",
                        str(parameters["residual_limit"]),
                        "--out",
                        str(artifacts["shadow_scorer_v3_report"]),
                        "--json",
                    ]
                )
            ],
            "build_transition_evidence_bundle": [
                _shell_join(
                    [
                        "python",
                        "cli.py",
                        "build-transition-evidence-bundle",
                        "--bench-report",
                        str(artifacts["transition_bench_report"]),
                        "--out",
                        str(artifacts["evidence"]),
                        "--repo-root",
                        str(repo_root),
                        "--prompt-corpus",
                        str(prompt_corpus.expanduser().resolve()),
                        "--advice",
                        str(artifacts["transition_advice"]),
                        "--shadow-scorer-report",
                        str(artifacts["shadow_scorer_v3_report"]),
                        "--force",
                    ]
                )
            ],
            "verify_json": [
                f"python -m json.tool {artifacts['shadow_scorer_v3_report']} >/dev/null",
                f"python -m json.tool {artifacts['evidence_manifest']} >/dev/null",
            ],
        },
    }


def _suite_command(
    out: Path,
    repo_root: Path,
    task_paths: Sequence[Path],
    prompt_corpus: Path,
    checkpoint: Path | None,
    ranker: Path | None,
    parameters: Mapping[str, object],
) -> list[object]:
    command: list[object] = [
        "python",
        "cli.py",
        "run-transition-shadow-suite",
        "--tasks",
        *task_paths,
        "--out",
        out,
        "--repo-root",
        repo_root,
        "--prompt-corpus",
        prompt_corpus.expanduser().resolve(),
        "--timeout",
        parameters["timeout_seconds"],
        "--max-candidates",
        parameters["max_candidates"],
        "--max-steps",
        parameters["max_steps"],
        "--explore-after-pass",
        parameters["explore_after_pass"],
        "--top-k",
        parameters["top_k"],
        "--embedding-dim",
        parameters["embedding_dim"],
        "--split-by",
        parameters["split_by"],
        "--validation-fraction",
        parameters["validation_fraction"],
        "--epochs",
        parameters["epochs"],
        "--learning-rate",
        parameters["learning_rate"],
        "--margin",
        parameters["margin"],
        "--residual-limit",
        parameters["residual_limit"],
    ]
    if checkpoint is None:
        command.append("--no-checkpoint")
    else:
        command.extend(["--checkpoint", checkpoint.expanduser().resolve()])
    if ranker is not None:
        command.extend(["--ranker", ranker.expanduser().resolve()])
    return command


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _usage_totals(reports: Sequence[object]) -> dict[str, int]:
    totals = {field: 0 for field in HOSTED_USAGE_FIELDS}
    for report in reports:
        for key, value in _hosted_usage_values(report):
            if key in totals and isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    return totals


def _hosted_usage_values(value: object) -> list[tuple[str, object]]:
    values: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in HOSTED_USAGE_FIELDS:
                values.append((key_text, item))
            values.extend(_hosted_usage_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_hosted_usage_values(item))
    return values


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _shell_join(parts: Sequence[object]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)
