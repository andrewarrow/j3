"""Command line interface for j3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from actions import PatchActionKind
from candidate_ranking import train_candidate_ranker
from evaluation import evaluate_tasks, write_eval_diagnostics
from fixing import run_fix_workflow
from mining import mine_git_transitions
from patching import plan_and_maybe_apply_patch
from training import train_from_paths


DESCRIPTION = (
    "j3 is a local-first JEPA coding agent for planning structured Python "
    "patches without LLM-generated patch candidates."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="j3",
        description=DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="j3 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    actions_parser = subparsers.add_parser(
        "actions",
        help="list the structured patch actions j3 can choose",
        description="List the structured edit actions available to the first repair model.",
    )
    actions_parser.add_argument(
        "--json",
        action="store_true",
        help="print action names as JSON",
    )
    actions_parser.set_defaults(handler=handle_actions)

    patch_parser = subparsers.add_parser(
        "patch",
        help="plan one structured patch for a failing pytest target",
        description=(
            "Plan one patch attempt for a Python repository. Candidates are "
            "tested in temporary copies before any file is changed."
        ),
    )
    patch_parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="repository root to inspect (default: current directory)",
    )
    patch_parser.add_argument(
        "--test",
        required=True,
        help='pytest command or target, for example "pytest tests/test_parser.py::test_edge_case"',
    )
    patch_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="find and show a passing candidate without changing files",
    )
    patch_parser.add_argument(
        "--model",
        type=Path,
        default=Path("runs/greenshot-1/model.json"),
        help="prototype model used to rank patch candidates (default: runs/greenshot-1/model.json)",
    )
    patch_parser.add_argument(
        "--ranker",
        type=Path,
        help="optional diagnostics-trained candidate ranker",
    )
    patch_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="seconds to allow each test run (default: 30)",
    )
    patch_parser.add_argument(
        "--max-candidates",
        type=int,
        default=80,
        help="maximum candidate patches to test (default: 80)",
    )
    patch_parser.set_defaults(handler=handle_patch)

    fix_parser = subparsers.add_parser(
        "fix",
        help="run tests, plan fixes for failing pytest targets, and review patches",
        description=(
            "Run a test command, identify failing pytest targets, then plan and "
            "optionally apply structured patches with human review."
        ),
    )
    fix_parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="repository root to inspect (default: current directory)",
    )
    fix_parser.add_argument(
        "--test",
        required=True,
        help='test command to run, for example "python -m pytest"',
    )
    fix_parser.add_argument(
        "--model",
        type=Path,
        default=Path("runs/greenshot-1/model.json"),
        help="prototype model used to rank patch candidates (default: runs/greenshot-1/model.json)",
    )
    fix_parser.add_argument(
        "--ranker",
        type=Path,
        help="optional diagnostics-trained candidate ranker",
    )
    fix_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show patch plans without applying them",
    )
    fix_parser.add_argument(
        "--yes",
        action="store_true",
        help="apply passing patches without prompting",
    )
    fix_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="seconds to allow each test run (default: 30)",
    )
    fix_parser.add_argument(
        "--max-candidates",
        type=int,
        default=80,
        help="maximum candidate patches to test per failure (default: 80)",
    )
    fix_parser.set_defaults(handler=handle_fix)

    mine_parser = subparsers.add_parser(
        "mine",
        help="mine real Python file transitions from git history",
        description="Extract before/after Python file transitions from recent git commits.",
    )
    mine_parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="git repository to mine",
    )
    mine_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="JSONL output path",
    )
    mine_parser.add_argument(
        "--max-commits",
        type=int,
        default=50,
        help="maximum recent Python-changing commits to scan (default: 50)",
    )
    mine_parser.add_argument(
        "--max-files-per-commit",
        type=int,
        default=20,
        help="maximum Python files to record from each commit (default: 20)",
    )
    mine_parser.set_defaults(handler=handle_mine)

    train_parser = subparsers.add_parser(
        "train",
        help="train a local JEPA predictor from transition records",
        description=(
            "Train the first local prototype over synthetic break/fix transitions "
            "generated from a Python repository."
        ),
    )
    train_parser.add_argument(
        "--data",
        type=Path,
        required=True,
        nargs="+",
        help="one or more Python repo paths to use as training data",
    )
    train_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/greenshot-1"),
        help="directory for checkpoints and metrics",
    )
    train_parser.add_argument(
        "--embedding-dim",
        type=int,
        default=256,
        help="hashed latent vector dimension (default: 256)",
    )
    train_parser.add_argument(
        "--max-examples",
        type=int,
        default=500,
        help="maximum synthetic transitions to generate (default: 500)",
    )
    train_parser.add_argument(
        "--transitions",
        type=Path,
        nargs="*",
        default=[],
        help="mined git-transition JSONL files or directories to include",
    )
    train_parser.set_defaults(handler=handle_train)

    ranker_parser = subparsers.add_parser(
        "train-ranker",
        help="train a lightweight candidate ranker from eval diagnostics",
        description=(
            "Train a small linear tie-breaker from diagnostics produced by j3 eval. "
            "Positive examples are passing tested candidates; negatives are failed "
            "candidates tested before them."
        ),
    )
    ranker_parser.add_argument(
        "--diagnostics",
        type=Path,
        required=True,
        nargs="+",
        help="one or more diagnostics JSON files from j3 eval",
    )
    ranker_parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/candidate-ranker"),
        help="directory for ranker artifacts",
    )
    ranker_parser.add_argument(
        "--epochs",
        type=int,
        default=8,
        help="pairwise perceptron training epochs (default: 8)",
    )
    ranker_parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.25,
        help="pairwise perceptron learning rate (default: 0.25)",
    )
    ranker_parser.set_defaults(handler=handle_train_ranker)

    eval_parser = subparsers.add_parser(
        "eval",
        help="evaluate a checkpoint on repair tasks",
        description="Evaluate model-ranked patching against unranked candidate order.",
    )
    eval_parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("runs/greenshot-1/model.json"),
        help="model checkpoint to evaluate (default: runs/greenshot-1/model.json)",
    )
    eval_parser.add_argument(
        "--ranker",
        type=Path,
        help="optional diagnostics-trained candidate ranker",
    )
    eval_parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        help="task directory or manifest",
    )
    eval_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="seconds to allow each test run (default: 30)",
    )
    eval_parser.add_argument(
        "--max-candidates",
        type=int,
        default=80,
        help="maximum candidate patches to test per task (default: 80)",
    )
    eval_parser.add_argument(
        "--diagnostics",
        type=Path,
        help="optional JSON file for per-task candidate ranking diagnostics",
    )
    eval_parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-task progress logging",
    )
    eval_parser.set_defaults(handler=handle_eval)

    return parser


def handle_actions(args: argparse.Namespace) -> int:
    names = [kind.value for kind in PatchActionKind]
    if args.json:
        print(json.dumps(names, indent=2))
    else:
        for name in names:
            print(name)
    return 0


def handle_patch(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f"repo does not exist: {repo}")
    if not repo.is_dir():
        raise SystemExit(f"repo is not a directory: {repo}")

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=args.test,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        max_candidates=args.max_candidates,
        model_path=args.model,
        ranker_path=args.ranker,
    )

    mode = "dry run" if args.dry_run else "apply"
    print(f"j3 patch ({mode})")
    print(f"repo: {repo}")
    print(f"test: {args.test}")
    print(f"baseline exit code: {result.baseline_exit_code}")
    if result.model_path:
        print(f"model: {result.model_path}")
    if result.ranker_path:
        print(f"ranker: {result.ranker_path}")

    if result.baseline_exit_code == 0:
        print("status: test already passes; no patch generated")
        return 0

    print(f"candidates generated: {result.candidates_generated}")
    print(f"candidates tested: {result.candidates_tested}")

    if result.selected is None:
        print("status: no candidate patch made the test pass")
        return 1

    print(f"status: {'applied' if result.applied else 'found'} passing patch")
    print(f"action: {result.selected.action.kind.value}")
    print(f"file: {result.selected.file_path}")
    print(f"reason: {result.selected.reason}")
    if result.selected.model_score is not None:
        print(f"model score: {result.selected.model_score:.4f}")
    if result.selected.ranker_score is not None:
        print(f"ranker score: {result.selected.ranker_score:.4f}")
    print("diff:")
    print(result.selected.diff(), end="" if result.selected.diff().endswith("\n") else "\n")
    return 0


def handle_fix(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f"repo does not exist: {repo}")
    if not repo.is_dir():
        raise SystemExit(f"repo is not a directory: {repo}")

    result = run_fix_workflow(
        repo=repo,
        test_command=args.test,
        model_path=args.model,
        ranker_path=args.ranker,
        yes=args.yes,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        max_candidates=args.max_candidates,
        confirm=_confirm,
    )

    mode = "dry run" if args.dry_run else "review"
    if args.yes and not args.dry_run:
        mode = "apply"

    print(f"j3 fix ({mode})")
    print(f"repo: {result.repo}")
    print(f"test: {result.test_command}")
    print(f"baseline exit code: {result.baseline_exit_code}")

    if result.baseline_exit_code == 0:
        print("status: tests already pass")
        return 0

    print(f"failing targets: {len(result.failing_targets)}")
    for target in result.failing_targets:
        print(f"  {target}")

    if not result.attempts:
        print("status: no patch attempts were made")
        return 1

    for attempt in result.attempts:
        print("")
        print(f"target: {attempt.target}")
        print(f"target test: {attempt.test_command}")
        print(f"candidates generated: {attempt.plan.candidates_generated}")
        print(f"candidates tested: {attempt.plan.candidates_tested}")
        if attempt.plan.selected is None:
            print("status: no passing patch found")
            continue

        print(f"status: {'applied' if attempt.applied else 'planned'} passing patch")
        print(f"action: {attempt.plan.selected.action.kind.value}")
        print(f"file: {attempt.plan.selected.file_path}")
        print(f"reason: {attempt.plan.selected.reason}")
        if attempt.plan.selected.model_score is not None:
            print(f"model score: {attempt.plan.selected.model_score:.4f}")
        if attempt.plan.selected.ranker_score is not None:
            print(f"ranker score: {attempt.plan.selected.ranker_score:.4f}")
        print("diff:")
        print(
            attempt.plan.selected.diff(),
            end="" if attempt.plan.selected.diff().endswith("\n") else "\n",
        )

    return 0 if result.solved else 1


def handle_train(args: argparse.Namespace) -> int:
    result = train_from_paths(
        data_paths=args.data,
        out_dir=args.out,
        embedding_dim=args.embedding_dim,
        max_examples=args.max_examples,
        transition_paths=args.transitions,
    )
    print("j3 train complete")
    print("data:")
    for path in args.data:
        print(f"  {path.expanduser().resolve()}")
    print(f"out: {result.out_dir}")
    print(f"source files: {result.source_files}")
    print(f"examples: {result.parsed_examples}")
    print(f"mined transitions: {result.mined_examples}")
    print("actions:")
    for action, count in result.action_counts.items():
        print(f"  {action}: {count}")
    print(f"model: {result.model_path}")
    print(f"metrics: {result.metrics_path}")
    print(f"examples: {result.examples_path}")
    return 0


def handle_train_ranker(args: argparse.Namespace) -> int:
    result = train_candidate_ranker(
        diagnostics_paths=args.diagnostics,
        out_dir=args.out,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    print("j3 train-ranker complete")
    print("diagnostics:")
    for path in result.diagnostics_paths:
        print(f"  {path}")
    print(f"out: {result.out_dir}")
    print(f"plans: {result.plans}")
    print(f"training pairs: {result.training_pairs}")
    print(f"features: {result.features}")
    print(f"mistakes: {result.mistakes}")
    print(f"ranker: {result.ranker_path}")
    print(f"metrics: {result.metrics_path}")
    return 0


def handle_mine(args: argparse.Namespace) -> int:
    result = mine_git_transitions(
        repo=args.repo,
        out_path=args.out,
        max_commits=args.max_commits,
        max_files_per_commit=args.max_files_per_commit,
    )
    print("j3 mine complete")
    print(f"repo: {result.repo}")
    print(f"out: {result.out_path}")
    print(f"commits scanned: {result.commits_scanned}")
    print(f"transitions written: {result.transitions_written}")
    return 0


def handle_eval(args: argparse.Namespace) -> int:
    progress = None if args.quiet else _progress
    if progress is not None:
        progress("j3 eval starting")
        progress(f"tasks: {args.tasks.expanduser().resolve()}")
        progress(f"checkpoint: {args.checkpoint.expanduser().resolve()}")
        progress(f"timeout per test run: {args.timeout}s")
        progress(f"max candidates per phase: {args.max_candidates}")
    summary = evaluate_tasks(
        tasks_path=args.tasks,
        model_path=args.checkpoint,
        ranker_path=args.ranker,
        timeout_seconds=args.timeout,
        max_candidates=args.max_candidates,
        progress=progress,
    )
    diagnostics_path = write_eval_diagnostics(summary, args.diagnostics) if args.diagnostics else None

    print("j3 eval complete")
    print(f"tasks: {summary.total}")
    print(f"checkpoint: {args.checkpoint.expanduser().resolve()}")
    if args.ranker:
        print(f"ranker: {args.ranker.expanduser().resolve()}")
    print(
        "baseline: "
        f"solved={summary.baseline_solved}/{summary.total} "
        f"pass@1={summary.baseline_pass_at_1}/{summary.total} "
        f"avg_candidates={summary.baseline_avg_candidates_tested:.2f}"
    )
    print(
        "model-ranked: "
        f"solved={summary.ranked_solved}/{summary.total} "
        f"pass@1={summary.ranked_pass_at_1}/{summary.total} "
        f"avg_candidates={summary.ranked_avg_candidates_tested:.2f}"
    )
    print("tasks:")
    for task in summary.tasks:
        baseline_status = "solved" if task.baseline_solved else "failed"
        ranked_status = "solved" if task.ranked_solved else "failed"
        ranked_action = task.ranked.selected.action.kind.value if task.ranked.selected else "-"
        print(
            f"  {task.task.name}: "
            f"baseline={baseline_status}/{task.baseline.candidates_tested} "
            f"model={ranked_status}/{task.ranked.candidates_tested} "
            f"action={ranked_action}"
        )
    if diagnostics_path:
        print(f"diagnostics: {diagnostics_path}")
    return 0 if summary.ranked_solved == summary.total else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    return args.handler(args)


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _progress(message: str) -> None:
    print(f"[eval] {message}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
