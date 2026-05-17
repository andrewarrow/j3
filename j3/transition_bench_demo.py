"""One-command transition benchmark demo and report."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from j3.transition_action_choice import (
    build_transition_action_choice_groups_jsonl,
)
from j3.transition_action_scoring import (
    DEFAULT_TOP_K,
    TRANSITION_ACTION_SCORER_VERSION,
    evaluate_transition_action_choices,
)
from j3.transition_assets import inspect_transition_assets
from j3.transition_bench import (
    SOURCE_CANDIDATE_OUTCOME,
    SOURCE_MINED_GIT_TRANSITION,
    SOURCE_PROMPT_REPO_TRANSITION,
    normalize_transition_bench_jsonl,
)


TRANSITION_BENCH_DEMO_REPORT_VERSION = "transition-bench-demo-report-v1"
DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "examples" / "transition_bench"
DEFAULT_PROMPT_REPO_TRANSITIONS = DEFAULT_FIXTURE_ROOT / "prompt_repo_transitions.jsonl"
DEFAULT_MINED_GIT_TRANSITIONS = DEFAULT_FIXTURE_ROOT / "mined_git_transitions.jsonl"
DEFAULT_CANDIDATE_OUTCOMES = DEFAULT_FIXTURE_ROOT / "candidate_outcomes.jsonl"


def run_transition_bench_demo(
    *,
    repo_root: Path = Path("."),
    prompt_corpus: Path | None = None,
    prompt_repo_transitions: Sequence[Path] = (),
    mined_transitions: Sequence[Path] = (),
    candidate_outcomes: Sequence[Path] = (),
    include_fixtures: bool = True,
    top_k: int = DEFAULT_TOP_K,
    embedding_dim: int = 256,
    residual_limit: int = 10,
    out: Path | None = None,
) -> dict[str, object]:
    """Run a small local transition-bench demo and optionally write a report."""

    started = time.perf_counter()
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if residual_limit < 0:
        raise ValueError("residual_limit must be >= 0")

    prompt_paths = _source_paths(
        prompt_repo_transitions,
        default_path=DEFAULT_PROMPT_REPO_TRANSITIONS,
        include_fixtures=include_fixtures,
    )
    mined_paths = _source_paths(
        mined_transitions,
        default_path=DEFAULT_MINED_GIT_TRANSITIONS,
        include_fixtures=include_fixtures,
    )
    candidate_paths = _source_paths(
        candidate_outcomes,
        default_path=DEFAULT_CANDIDATE_OUTCOMES,
        include_fixtures=include_fixtures,
    )
    _validate_source_paths((*prompt_paths, *mined_paths, *candidate_paths))

    inventory = inspect_transition_assets(
        repo_root=repo_root,
        prompt_corpus=prompt_corpus,
    )
    bench_rows = [
        *(
            row
            for path in prompt_paths
            for row in normalize_transition_bench_jsonl(
                path,
                source_kind=SOURCE_PROMPT_REPO_TRANSITION,
                embedding_dim=embedding_dim,
            )
        ),
        *(
            row
            for path in mined_paths
            for row in normalize_transition_bench_jsonl(
                path,
                source_kind=SOURCE_MINED_GIT_TRANSITION,
                embedding_dim=embedding_dim,
            )
        ),
        *(
            row
            for path in candidate_paths
            for row in normalize_transition_bench_jsonl(
                path,
                source_kind=SOURCE_CANDIDATE_OUTCOME,
                embedding_dim=embedding_dim,
            )
        ),
    ]
    action_choice_groups = [
        group
        for path in candidate_paths
        for group in build_transition_action_choice_groups_jsonl(
            path,
            embedding_dim=embedding_dim,
        )
    ]
    scoring = evaluate_transition_action_choices(
        action_choice_groups,
        top_k=top_k,
        residual_limit=residual_limit,
    )
    source_counts = Counter(
        _mapping(row.get("source")).get("kind", "unknown") for row in bench_rows
    )
    report_path = str(out.expanduser().resolve()) if out is not None else None
    runtime_ms = round((time.perf_counter() - started) * 1000, 3)

    report: dict[str, object] = {
        "schema_version": TRANSITION_BENCH_DEMO_REPORT_VERSION,
        "decision": "evaluation_only_not_wired_to_production",
        "uses_checked_in_fixtures": include_fixtures,
        "report": report_path,
        "parameters": {
            "top_k": top_k,
            "embedding_dim": embedding_dim,
            "residual_limit": residual_limit,
        },
        "asset_inventory": _asset_inventory_context(inventory),
        "sources": {
            "prompt_repo_transition_files": _path_records(prompt_paths),
            "mined_git_transition_files": _path_records(mined_paths),
            "candidate_outcome_files": _path_records(candidate_paths),
        },
        "transition_bench": {
            "schema_version": "transition-bench-v1",
            "row_count": len(bench_rows),
            "source_counts": dict(sorted(source_counts.items())),
        },
        "action_choices": {
            "schema_version": "transition-action-choice-v1",
            "group_count": len(action_choice_groups),
            "candidate_count": sum(
                int(group.get("candidate_count", 0)) for group in action_choice_groups
            ),
            "solved_group_count": sum(
                1
                for group in action_choice_groups
                if group.get("passing_candidate_ranks")
            ),
        },
        "action_scoring": scoring,
        "runtime": {
            "local_runtime_ms": runtime_ms,
            "hosted_llm_api_calls": 0,
            "hosted_llm_prompt_tokens": 0,
            "hosted_llm_completion_tokens": 0,
            "hosted_api_tokens": 0,
            "hosted_repo_context_bytes": 0,
        },
    }
    if out is not None:
        write_transition_bench_demo_report(report, out)
    return report


def write_transition_bench_demo_report(
    report: Mapping[str, object],
    out_path: Path,
) -> Path:
    """Write the transition bench demo report as stable JSON."""

    resolved = out_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved


def format_transition_bench_demo_report(report: Mapping[str, object]) -> str:
    """Format the report for human CLI output."""

    action_choices = _mapping(report.get("action_choices"))
    transition_bench = _mapping(report.get("transition_bench"))
    scoring = _mapping(report.get("action_scoring"))
    runtime = _mapping(report.get("runtime"))
    metrics = _mapping(scoring.get("metrics"))
    lines = [
        "j3 demo-transition-bench complete",
        "mode: evaluation-only",
        f"transition bench rows: {transition_bench.get('row_count', 0)}",
        f"groups: {action_choices.get('group_count', 0)}",
        f"candidates: {action_choices.get('candidate_count', 0)}",
        f"top k: {scoring.get('top_k')}",
        "metrics:",
    ]
    for name in (TRANSITION_ACTION_SCORER_VERSION, *sorted(_baseline_names(metrics))):
        section = _mapping(metrics.get(name))
        if not section:
            continue
        lines.append(
            "  "
            f"{name}: "
            f"pass@1={section.get('pass_at_1_count')}/"
            f"{section.get('group_count')} "
            f"top-k={section.get('top_k_pass_count')}/"
            f"{section.get('group_count')} "
            f"mrr={_format_optional_float(section.get('mean_reciprocal_rank'))} "
            "avg_before_first_pass="
            f"{_format_optional_float(section.get('average_candidates_validated_before_first_pass'))}"
        )
    lines.extend(
        [
            f"local runtime ms: {_format_optional_float(runtime.get('local_runtime_ms'))}",
            f"hosted_llm_api_calls: {runtime.get('hosted_llm_api_calls', 0)}",
            f"hosted_llm_prompt_tokens: {runtime.get('hosted_llm_prompt_tokens', 0)}",
            f"hosted_llm_completion_tokens: {runtime.get('hosted_llm_completion_tokens', 0)}",
            f"hosted_repo_context_bytes: {runtime.get('hosted_repo_context_bytes', 0)}",
        ]
    )
    if report.get("report"):
        lines.append(f"report: {report['report']}")
    return "\n".join(lines)


def _source_paths(
    paths: Sequence[Path],
    *,
    default_path: Path,
    include_fixtures: bool,
) -> tuple[Path, ...]:
    result = [default_path] if include_fixtures else []
    result.extend(paths)
    return tuple(result)


def _validate_source_paths(paths: Sequence[Path]) -> None:
    for path in paths:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"transition bench source does not exist: {resolved}")
        if not resolved.is_file():
            raise IsADirectoryError(f"transition bench source is not a file: {resolved}")


def _path_records(paths: Sequence[Path]) -> list[dict[str, object]]:
    return [
        {
            "path": str(path.expanduser().resolve()),
            "rows": _count_jsonl_rows(path),
        }
        for path in paths
    ]


def _count_jsonl_rows(path: Path) -> int:
    rows = 0
    with path.expanduser().resolve().open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows += 1
    return rows


def _asset_inventory_context(inventory: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": inventory.get("schema_version"),
        "repo_root": inventory.get("repo_root"),
        "totals": _mapping(inventory.get("totals")),
        "notes": inventory.get("notes", []),
    }


def _baseline_names(metrics: Mapping[str, object]) -> list[str]:
    return [
        name
        for name in metrics
        if name != TRANSITION_ACTION_SCORER_VERSION
    ]


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _format_optional_float(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.6f}"
    return "none"
