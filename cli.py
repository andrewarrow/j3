"""Command line interface for j3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from actions import PatchActionKind
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
            "Plan one patch attempt for a Python repository. The planner is a "
            "scaffold for GreenShot-1 and does not yet modify files."
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
        help="show the intended operation without changing files",
    )
    patch_parser.set_defaults(handler=handle_patch)

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
    train_parser.set_defaults(handler=handle_train)

    eval_parser = subparsers.add_parser(
        "eval",
        help="evaluate a checkpoint on repair tasks",
        description="Placeholder for pass@1 evaluation on synthetic Python repair tasks.",
    )
    eval_parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="model checkpoint to evaluate",
    )
    eval_parser.add_argument(
        "--tasks",
        type=Path,
        required=True,
        help="task directory or manifest",
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

    mode = "dry run" if args.dry_run else "plan"
    print(f"j3 patch ({mode})")
    print(f"repo: {repo}")
    print(f"test: {args.test}")
    print("status: planner scaffold is ready; patch materialization is not implemented yet")
    return 0


def handle_train(args: argparse.Namespace) -> int:
    result = train_from_paths(
        data_paths=args.data,
        out_dir=args.out,
        embedding_dim=args.embedding_dim,
        max_examples=args.max_examples,
    )
    print("j3 train complete")
    print("data:")
    for path in args.data:
        print(f"  {path.expanduser().resolve()}")
    print(f"out: {result.out_dir}")
    print(f"source files: {result.source_files}")
    print(f"synthetic transitions: {result.parsed_examples}")
    print("actions:")
    for action, count in result.action_counts.items():
        print(f"  {action}: {count}")
    print(f"model: {result.model_path}")
    print(f"metrics: {result.metrics_path}")
    print(f"examples: {result.examples_path}")
    return 0


def handle_eval(args: argparse.Namespace) -> int:
    print(f"eval scaffold: checkpoint={args.checkpoint} tasks={args.tasks}")
    print("status: pass@1 evaluation is not implemented yet")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
