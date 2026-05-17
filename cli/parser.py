"""Argument parser construction for the j3 CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.handlers import (
    handle_actions,
    handle_build_prompt_jepa_index,
    handle_change,
    handle_compare_diagnostics,
    handle_demo_prompt_jepa,
    handle_demo_transition_bench,
    handle_eval_prompt_jepa_index,
    handle_eval_prompt_repo_transitions,
    handle_eval,
    handle_fix,
    handle_greenshot_7,
    handle_implement,
    handle_inspect_prompt_corpus,
    handle_inspect_transition_assets,
    handle_mine,
    handle_outcome_summary,
    handle_patch,
    handle_propose_from_prompt_jepa,
    handle_query_prompt_jepa_index,
    handle_train,
    handle_train_prompt_intents,
    handle_train_ranker,
)

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

    implement_parser = subparsers.add_parser(
        "implement",
        help="create a repo from a supported coding-agent prompt",
        description=(
            "Parse a supported prompt into request-spec-v1, build a deterministic "
            "greenfield repo, and validate the generated project."
        ),
    )
    implement_parser.add_argument(
        "--prompt",
        required=True,
        help='coding-agent prompt, for example "make me a simple cli calc"',
    )
    implement_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output directory for the generated repo",
    )
    implement_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="write the repo without running its generated pytest validation",
    )
    implement_parser.add_argument(
        "--record",
        type=Path,
        help="append one prompt/spec/action/outcome JSONL row to this path",
    )
    implement_parser.set_defaults(handler=handle_implement)

    change_parser = subparsers.add_parser(
        "change",
        help="modify a supported existing repo from a prompt",
        description=(
            "Parse a supported existing-repo prompt into "
            "existing-repo-change-spec-v1, apply structured calculator actions, "
            "and validate the changed project."
        ),
    )
    change_parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="generated calculator repo to inspect and modify",
    )
    change_parser.add_argument(
        "--prompt",
        required=True,
        help='coding-agent change prompt, for example "add exponent support"',
    )
    change_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="apply the change without running the repo pytest validation",
    )
    change_parser.add_argument(
        "--record",
        type=Path,
        help="append one existing-repo prompt/spec/action/outcome JSONL row",
    )
    change_parser.set_defaults(handler=handle_change)

    greenshot_7_parser = subparsers.add_parser(
        "greenshot-7",
        help="run the bounded GreenShot-7 calculator fixtures",
        description=(
            "Run parser, planner, builder, generated pytest validation, and "
            "optional outcome recording for the calculator request-to-repo fixtures."
        ),
    )
    greenshot_7_parser.add_argument(
        "--tasks",
        type=Path,
        default=Path("examples/greenshot_7/tasks.json"),
        help="GreenShot-7 calculator fixture manifest",
    )
    greenshot_7_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output root for generated fixture repos",
    )
    greenshot_7_parser.add_argument(
        "--record",
        type=Path,
        help="append request-repo-attempt-v1 JSONL rows to this path",
    )
    greenshot_7_parser.set_defaults(handler=handle_greenshot_7)

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
    patch_parser.add_argument(
        "--max-steps",
        type=int,
        default=1,
        help="maximum sequential repair steps to plan (default: 1)",
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

    prompt_intents_parser = subparsers.add_parser(
        "train-prompt-intents",
        help="train and evaluate a learned prompt-intent baseline",
        description=(
            "Train a deterministic token-perceptron baseline for scalar "
            "prompt-intent fields. The command reports held-out metrics and "
            "does not wire the model into request-spec production behavior."
        ),
    )
    prompt_intents_parser.add_argument(
        "--labels",
        type=Path,
        default=Path("../prompts/coding_agent_prompts_seed.jsonl"),
        help="prompt-intent JSONL labels to train/evaluate",
    )
    prompt_intents_parser.add_argument(
        "--target",
        nargs="+",
        default=["expected_action", "repo_mode"],
        choices=(
            "repo_mode",
            "task_type",
            "domain",
            "expected_action",
            "requires_clarification",
            "primary_artifact",
            "unsupported_requirement",
            "unsupported_requirement_family",
        ),
        help="one or more scalar prompt-intent target fields",
    )
    prompt_intents_parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="deterministic perceptron training epochs (default: 10)",
    )
    prompt_intents_parser.add_argument(
        "--json",
        action="store_true",
        help="print full metrics and model weights as JSON",
    )
    prompt_intents_parser.add_argument(
        "--show-residuals",
        action="store_true",
        help="print misclassified examples for each evaluated split",
    )
    prompt_intents_parser.add_argument(
        "--residual-limit",
        type=int,
        default=20,
        help="maximum residual examples to print per split and target (default: 20)",
    )
    prompt_intents_parser.set_defaults(handler=handle_train_prompt_intents)

    inspect_prompt_corpus_parser = subparsers.add_parser(
        "inspect-prompt-corpus",
        help="profile and quality-check prompt-intent corpus labels",
        description=(
            "Inspect prompt-intent JSONL labels for split and target counts, "
            "duplicate normalized prompts, prompt-family split leakage, missing "
            "required fields, and unsupported scalar labels."
        ),
    )
    inspect_prompt_corpus_parser.add_argument(
        "--labels",
        type=Path,
        default=Path("../prompts/coding_agent_prompts_expanded_v0.jsonl"),
        help="prompt-intent JSONL labels to inspect",
    )
    inspect_prompt_corpus_parser.add_argument(
        "--json",
        action="store_true",
        help="print the full corpus profile as JSON",
    )
    inspect_prompt_corpus_parser.set_defaults(handler=handle_inspect_prompt_corpus)

    inspect_transition_assets_parser = subparsers.add_parser(
        "inspect-transition-assets",
        help="inventory local transition benchmark assets",
        description=(
            "Summarize local prompt, Prompt+Repo demo, mined transition, "
            "candidate outcome, and prototype model assets. Missing ignored "
            "data and run artifacts are reported as normal, not errors."
        ),
    )
    inspect_transition_assets_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="repository root to inspect (default: current directory)",
    )
    inspect_transition_assets_parser.add_argument(
        "--prompt-corpus",
        type=Path,
        default=Path("../prompts/coding_agent_prompts_expanded_v0.jsonl"),
        help="prompt corpus JSONL path to include in the inventory",
    )
    inspect_transition_assets_parser.add_argument(
        "--out",
        type=Path,
        help="optional JSON manifest path to write",
    )
    inspect_transition_assets_parser.add_argument(
        "--json",
        action="store_true",
        help="print the inventory manifest as JSON",
    )
    inspect_transition_assets_parser.set_defaults(
        handler=handle_inspect_transition_assets
    )

    transition_bench_demo_parser = subparsers.add_parser(
        "demo-transition-bench",
        help="run the local transition action-selection bench demo",
        description=(
            "Normalize checked-in and optional local transition fixtures, build "
            "candidate action-choice groups, evaluate the local future scorer "
            "against simple baselines, and report zero hosted LLM/API usage."
        ),
    )
    transition_bench_demo_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="repository root to inspect for local transition assets",
    )
    transition_bench_demo_parser.add_argument(
        "--prompt-corpus",
        type=Path,
        default=Path("../prompts/coding_agent_prompts_expanded_v0.jsonl"),
        help="prompt corpus JSONL path to include in asset inventory context",
    )
    transition_bench_demo_parser.add_argument(
        "--prompt-repo-transitions",
        type=Path,
        nargs="*",
        default=[],
        help="optional prompt-repo-transition-v1 JSONL files to include",
    )
    transition_bench_demo_parser.add_argument(
        "--mined-transitions",
        type=Path,
        nargs="*",
        default=[],
        help="optional mined git-transition JSONL files to include",
    )
    transition_bench_demo_parser.add_argument(
        "--candidate-outcomes",
        type=Path,
        nargs="*",
        default=[],
        help="optional candidate outcome JSONL files to group and score",
    )
    transition_bench_demo_parser.add_argument(
        "--no-fixtures",
        action="store_true",
        help="skip the tiny checked-in fixtures and use only explicit input paths",
    )
    transition_bench_demo_parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="candidate scoring cutoff for top-k pass rate (default: 3)",
    )
    transition_bench_demo_parser.add_argument(
        "--embedding-dim",
        type=int,
        default=256,
        help="hashed source embedding dimension for normalized rows (default: 256)",
    )
    transition_bench_demo_parser.add_argument(
        "--residual-limit",
        type=int,
        default=10,
        help="maximum residual action-choice examples to retain (default: 10)",
    )
    transition_bench_demo_parser.add_argument(
        "--out",
        type=Path,
        help="optional JSON report path to write",
    )
    transition_bench_demo_parser.add_argument(
        "--json",
        action="store_true",
        help="print the full demo report as JSON",
    )
    transition_bench_demo_parser.set_defaults(handler=handle_demo_transition_bench)

    prompt_jepa_demo_parser = subparsers.add_parser(
        "demo-prompt-jepa",
        help="run the local Prompt-JEPA developer demo",
        description=(
            "Build a Prompt-JEPA index, run held-out retrieval eval, query "
            "representative prompts, dry-run planner proposals, create and "
            "validate calculator artifacts, and write a local report. This "
            "does not call hosted LLM APIs or wire retrieval into production "
            "routing."
        ),
    )
    prompt_jepa_demo_parser.add_argument(
        "--labels",
        type=Path,
        required=True,
        help="prompt-intent JSONL labels to index and evaluate",
    )
    prompt_jepa_demo_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output directory for demo artifacts and report.json",
    )
    prompt_jepa_demo_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="retrieval/proposal cutoff for representative prompts (default: 5)",
    )
    prompt_jepa_demo_parser.add_argument(
        "--embedding-dim",
        type=int,
        default=256,
        help="hashed context/target embedding dimension (default: 256)",
    )
    prompt_jepa_demo_parser.set_defaults(handler=handle_demo_prompt_jepa)

    prompt_jepa_build_parser = subparsers.add_parser(
        "build-prompt-jepa-index",
        help="build a persisted Prompt-JEPA retrieval index",
        description=(
            "Build a persisted Prompt-JEPA index from prompt-intent labels, "
            "recorded prompt/spec/action/outcome rows, or both. This command "
            "writes a retrieval artifact only and does not wire retrieval into "
            "production request-spec or change-spec routing."
        ),
    )
    prompt_jepa_build_parser.add_argument(
        "--labels",
        type=Path,
        help="prompt-intent JSONL labels to index",
    )
    prompt_jepa_build_parser.add_argument(
        "--records",
        type=Path,
        help="prompt/spec/action/outcome JSONL rows from implement/change --record",
    )
    prompt_jepa_build_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output path for the Prompt-JEPA index JSON",
    )
    prompt_jepa_build_parser.add_argument(
        "--embedding-dim",
        type=int,
        default=256,
        help="hashed context/target embedding dimension (default: 256)",
    )
    prompt_jepa_build_parser.set_defaults(handler=handle_build_prompt_jepa_index)

    prompt_jepa_query_parser = subparsers.add_parser(
        "query-prompt-jepa-index",
        help="query a persisted Prompt-JEPA retrieval index",
        description=(
            "Query a persisted Prompt-JEPA index for nearest prompt-intent rows. "
            "Results are printed for inspection and are not used by production "
            "request-spec or change-spec routing."
        ),
    )
    prompt_jepa_query_parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="Prompt-JEPA index JSON path",
    )
    prompt_jepa_query_parser.add_argument(
        "--prompt",
        required=True,
        help="prompt text to query",
    )
    prompt_jepa_query_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="number of nearest rows to print (default: 5)",
    )
    prompt_jepa_query_parser.set_defaults(handler=handle_query_prompt_jepa_index)

    prompt_jepa_propose_parser = subparsers.add_parser(
        "propose-from-prompt-jepa",
        help="dry-run a retrieval-assisted planner proposal",
        description=(
            "Load a persisted Prompt-JEPA index and summarize nearest-neighbor "
            "outcome evidence as an evaluation-only planner proposal. This "
            "command does not call implement/change or write generated repos."
        ),
    )
    prompt_jepa_propose_parser.add_argument(
        "--index",
        type=Path,
        required=True,
        help="Prompt-JEPA index JSON path",
    )
    prompt_jepa_propose_parser.add_argument(
        "--prompt",
        required=True,
        help="prompt text to propose from",
    )
    prompt_jepa_propose_parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="number of nearest rows to use as evidence (default: 3)",
    )
    prompt_jepa_propose_parser.add_argument(
        "--json",
        action="store_true",
        help="print the dry-run proposal record as JSON",
    )
    prompt_jepa_propose_parser.set_defaults(handler=handle_propose_from_prompt_jepa)

    prompt_jepa_eval_parser = subparsers.add_parser(
        "eval-prompt-jepa-index",
        help="evaluate Prompt-JEPA retrieval on held-out prompt splits",
        description=(
            "Build a train-only Prompt-JEPA index from prompt-intent labels and "
            "evaluate validation/test prompts by nearest train rows. This "
            "command reports retrieval metrics only and does not wire retrieval "
            "into production request-spec or change-spec routing."
        ),
    )
    prompt_jepa_eval_parser.add_argument(
        "--labels",
        type=Path,
        required=True,
        help="prompt-intent JSONL labels to train/evaluate",
    )
    prompt_jepa_eval_parser.add_argument(
        "--embedding-dim",
        type=int,
        default=256,
        help="hashed context/target embedding dimension (default: 256)",
    )
    prompt_jepa_eval_parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="retrieval cutoff for top-k exact-match metrics (default: 3)",
    )
    prompt_jepa_eval_parser.add_argument(
        "--mode",
        choices=("context", "predicted-target", "compare"),
        default="context",
        help=(
            "evaluate context-neighbor retrieval or context-to-target "
            "prediction followed by target-space retrieval, or compare both "
            "residual sets (default: context)"
        ),
    )
    prompt_jepa_eval_parser.add_argument(
        "--target",
        nargs="+",
        default=[
            "expected_action",
            "repo_mode",
            "domain",
            "unsupported_requirement_family",
        ],
        choices=(
            "repo_mode",
            "task_type",
            "domain",
            "expected_action",
            "requires_clarification",
            "primary_artifact",
            "unsupported_requirement",
            "unsupported_requirement_family",
        ),
        help="one or more scalar target fields to score",
    )
    prompt_jepa_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="print retrieval metrics as JSON",
    )
    prompt_jepa_eval_parser.add_argument(
        "--show-misses",
        action="store_true",
        help="print representative nearest-neighbor misses",
    )
    prompt_jepa_eval_parser.add_argument(
        "--miss-limit",
        type=int,
        default=20,
        help="maximum miss examples to retain per split (default: 20)",
    )
    prompt_jepa_eval_parser.set_defaults(handler=handle_eval_prompt_jepa_index)

    prompt_repo_transition_eval_parser = subparsers.add_parser(
        "eval-prompt-repo-transitions",
        help="evaluate Prompt+Repo transition consequence prediction",
        description=(
            "Evaluate leave-one-out consequence prediction over "
            "prompt-repo-transition-v1 JSONL rows. Reports V0 predictor metrics, "
            "a prompt-only retrieval baseline, repo-after embedding distances, "
            "and representative residuals. This command is evaluation-only and "
            "does not wire prediction into production routing."
        ),
    )
    prompt_repo_transition_eval_parser.add_argument(
        "--transitions",
        type=Path,
        required=True,
        help="prompt-repo-transition-v1 JSONL rows to evaluate",
    )
    prompt_repo_transition_eval_parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="nearest-neighbor cutoff for top-k exact-match metrics (default: 3)",
    )
    prompt_repo_transition_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="print transition metrics as JSON",
    )
    prompt_repo_transition_eval_parser.add_argument(
        "--residual-limit",
        type=int,
        default=20,
        help="maximum residual examples to retain and print (default: 20)",
    )
    prompt_repo_transition_eval_parser.set_defaults(
        handler=handle_eval_prompt_repo_transitions
    )

    ranker_parser = subparsers.add_parser(
        "train-ranker",
        help="train a lightweight candidate ranker from eval diagnostics or outcomes",
        description=(
            "Train a small linear tie-breaker from diagnostics or candidate outcome "
            "JSONL produced by j3 eval. Positive examples are passing tested "
            "candidates; negatives are failed tested candidates."
        ),
    )
    ranker_parser.add_argument(
        "--diagnostics",
        type=Path,
        nargs="+",
        default=[],
        help="one or more diagnostics JSON files from j3 eval",
    )
    ranker_parser.add_argument(
        "--candidate-outcomes",
        type=Path,
        nargs="+",
        default=[],
        help="one or more candidate outcome JSONL files from j3 eval",
    )
    ranker_parser.add_argument(
        "--validation-diagnostics",
        type=Path,
        nargs="+",
        default=[],
        help="held-out diagnostics JSON files to score after training",
    )
    ranker_parser.add_argument(
        "--validation-candidate-outcomes",
        type=Path,
        nargs="+",
        default=[],
        help="held-out candidate outcome JSONL files to score after training",
    )
    ranker_parser.add_argument(
        "--holdout-task",
        dest="holdout_tasks",
        nargs="+",
        default=[],
        help="task names to exclude from training and score as held-out validation",
    )
    ranker_parser.add_argument(
        "--holdout-task-family",
        dest="holdout_task_families",
        nargs="+",
        default=[],
        help="task families to exclude from training and score as held-out validation",
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

    outcome_summary_parser = subparsers.add_parser(
        "outcome-summary",
        help="summarize candidate outcome JSONL datasets",
        description=(
            "Summarize candidate outcome JSONL files produced by j3 eval, "
            "including pass@1 by task family and source type."
        ),
    )
    outcome_summary_parser.add_argument(
        "--candidate-outcomes",
        type=Path,
        nargs="+",
        required=True,
        help="one or more candidate outcome JSONL files from j3 eval",
    )
    outcome_summary_parser.add_argument(
        "--phase",
        choices=("ranked", "baseline", "all"),
        default="ranked",
        help="phase to summarize (default: ranked)",
    )
    outcome_summary_parser.add_argument(
        "--json",
        action="store_true",
        help="print the summary as JSON",
    )
    outcome_summary_parser.set_defaults(handler=handle_outcome_summary)

    compare_parser = subparsers.add_parser(
        "compare-diagnostics",
        help="compare two eval diagnostics files",
        description=(
            "Compare two j3 eval diagnostics files and summarize rank movement, "
            "pass@1 changes, bad-ranking changes, and failed candidate reasons."
        ),
    )
    compare_parser.add_argument(
        "old",
        type=Path,
        help="earlier diagnostics JSON file",
    )
    compare_parser.add_argument(
        "new",
        type=Path,
        help="later diagnostics JSON file",
    )
    compare_parser.add_argument(
        "--phase",
        choices=("ranked", "baseline"),
        default="ranked",
        help="diagnostics phase to compare (default: ranked)",
    )
    compare_parser.add_argument(
        "--top-reasons",
        type=int,
        default=5,
        help="number of failed candidate reasons to show per file (default: 5)",
    )
    compare_parser.set_defaults(handler=handle_compare_diagnostics)

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
        "--max-steps",
        type=int,
        default=1,
        help="maximum sequential repair steps per task unless a task overrides it (default: 1)",
    )
    eval_parser.add_argument(
        "--explore-after-pass",
        type=int,
        default=0,
        help=(
            "test this many additional candidates after the first pass "
            "for diagnostics (default: 0)"
        ),
    )
    eval_parser.add_argument(
        "--phase",
        choices=("ranked", "both", "baseline"),
        default="ranked",
        help=(
            "eval phase to run: ranked for day-to-day work, "
            "both for benchmark refreshes (default: ranked)"
        ),
    )
    eval_parser.add_argument(
        "--diagnostics",
        type=Path,
        help="optional JSON file for per-task candidate ranking diagnostics",
    )
    eval_parser.add_argument(
        "--candidate-outcomes",
        type=Path,
        help="optional JSONL file with one row per tested candidate",
    )
    eval_parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-task progress logging",
    )
    eval_parser.add_argument(
        "--verbose",
        action="store_true",
        help="print per-candidate eval progress",
    )
    eval_parser.set_defaults(handler=handle_eval)

    return parser
