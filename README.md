# j3

`j3` is a local-first bet on the next generation of coding agents.

The future is not a chatbot that keeps guessing bigger patches from longer
prompts. The future is a repo-world model: an agent that understands a codebase
as state, treats prompts and test failures as observations, predicts the
consequences of structured actions, and chooses the cheapest validated path
toward the desired target state.

This project is motivated by
[the Yann LeCun JEPA/world-model talk](https://www.youtube.com/watch?v=ngBraLDqzdI)

Capable agents need predictive models, planning in
abstract representation space, and objective-driven constraints. Language
remains useful as an interface, but the core editing loop should not depend on
autoregressive source generation.

The goal is simple and ambitious: turn user requests or failing observations
into structured repo actions by predicting useful transitions in latent space,
without asking an LLM to generate patches or source files first.

## Why This Exists

Most coding agents are language models wrapped in tools. They read files, guess
a patch, run tests, inspect the failure, and repeat. That can work, but it is
expensive, token-heavy, and often blind to the actual dynamics of a codebase.
It also puts the hardest part of the job in the least reliable place: free-form
generation.

`j3` treats a repository as a world:

- the current codebase is the state
- a prompt, test log, type check, stack trace, or runtime behavior is an
  observation
- a request spec or passing test suite describes the target state
- a patch, file creation, or clarification is a structured action

Instead of generating arbitrary source text token by token, `j3` starts with
structured specs and actions. The model chooses an action type, target, and
parameters. Deterministic builders and patch engines turn that decision into a
real repo change. That makes the loop inspectable, trainable, locally runnable,
and able to improve from concrete outcomes instead of only from better prompts.

## Current Progress: GreenShot-7 Prompt-JEPA

The active slice is GreenShot-7: request-to-repo work for a narrow calculator
CLI domain. The smallest useful path is:

```text
prompt
  -> request-spec-v1 or clarification
  -> structured create/change action
  -> generated repo or recorded blocked outcome
  -> validation record
```

There is now a persisted Prompt-JEPA index for this path:

```text
prompt / task context
  -> context embedding
request spec / action / outcome
  -> target embedding
context + target + metadata
  -> indexed row
new prompt
  -> nearest prompt/spec/action/outcome evidence
```

V0 uses deterministic feature hashing, not a neural encoder. The important part
is the JEPA-shaped artifact: context vectors and target vectors are separate,
dimensions are fixed and validated, rows preserve train/validation/test splits,
and real `implement --record` / `change --record` outcome rows can be indexed.

The developer demo now also emits Prompt+Repo transition artifacts:

```text
prompt + repo_before + structured action
  -> predicted repo_after / blocked target
  -> local transition evaluation metrics and residuals
```

Those rows use deterministic `repo-state-v1` Python repo-state records and are
evaluated by `prompt-repo-transition-predictor-v0`. This is still
evaluation-only; production `implement` and `change` routing remains
deterministic.

For the one-command developer demo, exact artifact inspection commands, and
current supported/retrieval/transition-only boundaries, see
[docs/PROMPT_JEPA_DEMO.md](docs/PROMPT_JEPA_DEMO.md).

Try the calculator prompt index:

```bash
python cli.py build-prompt-jepa-index \
  --labels examples/prompt_intents/greenshot_7_intents.jsonl \
  --out /tmp/j3-prompt-jepa-index.json

python cli.py query-prompt-jepa-index \
  --index /tmp/j3-prompt-jepa-index.json \
  --prompt "make me a simple cli calc" \
  --top-k 5
```

For the simple CLI calculator prompt, the nearest row is the direct
`emit_request_spec` calculator example. For prompts that ask for unsupported or
ambiguous calculator variants, nearest rows move toward `ask_clarification` or
blocked outcome evidence instead of pretending the request is supported.

The same artifact supports held-out retrieval evaluation and dry-run planner
evidence:

```bash
python cli.py eval-prompt-jepa-index \
  --labels examples/prompt_intents/greenshot_7_intents.jsonl \
  --mode compare

python cli.py propose-from-prompt-jepa \
  --index /tmp/j3-prompt-jepa-index.json \
  --prompt "make me a complex calc for spaceships" \
  --top-k 5
```

`propose-from-prompt-jepa` emits a `prompt-jepa-planner-proposal-v1` dry-run
record. It does not apply changes and production `implement` / `change` routing
is still deterministic while retrieval quality is measured. When the index is
built with `--records` from real `implement --record` and `change --record`
JSONL rows, the proposal evidence also carries outcome kind, status,
validation, pass/fail, and changed-file metadata.

## First Demo: GreenShot-1

The first milestone is intentionally narrow:

```text
Input:  a Python repo with one failing pytest failure
Output: one patch attempt, generated without an LLM
```

The intended flow:

```text
repo + failing test log
      -> encode repo state into latent space
      -> predict which structured edit moves the repo toward "tests pass"
      -> materialize the edit as a patch
      -> run the target test once
```

Example command shape:

```bash
j3 patch --repo ~/projects/example --test "pytest tests/test_parser.py::test_edge_case"
```

Example patch shapes:

```diff
- if value > limit:
+ if value >= limit:
```

```diff
- return items[0]
+ return items[-1]
```

```diff
+ from pathlib import Path
```

## What Makes This Different

`j3` is not trying to be another code completion model. The first useful system
should be a repo-world predictor and planner:

- predict the effect of a patch before running every possible test
- choose a first repair action from a constrained edit space
- learn from synthetic break/fix transitions generated locally
- cache compact repo embeddings instead of repeatedly sending large prompts
- run on developer hardware, starting with Apple silicon

In pure mode, the first demo uses no hosted LLM and no API tokens.

## Quick Start

This repo currently uses a flat Python module layout at the project root.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
j3 --help
```

Useful starter commands:

```bash
j3 actions
j3 actions --json
j3 implement \
  --prompt "make me a simple cli calc" \
  --out /tmp/j3-calc-demo
j3 build-prompt-jepa-index \
  --labels examples/prompt_intents/greenshot_7_intents.jsonl \
  --out /tmp/j3-prompt-jepa-index.json
j3 query-prompt-jepa-index \
  --index /tmp/j3-prompt-jepa-index.json \
  --prompt "make me a simple cli calc" \
  --top-k 5
j3 demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo
j3 eval-prompt-repo-transitions \
  --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl \
  --top-k 3
j3 train --data examples/greenshot_bug
j3 train --data ../Decepticon ../scientific-agent-skills ../CLI-Anything
j3 mine --repo ../some-python-project --out data/transitions/project.jsonl
j3 patch --repo examples/greenshot_bug --test "python -m pytest tests/test_calculator.py" --dry-run
j3 fix --repo examples/greenshot_bug --test "python -m pytest tests/test_calculator.py" --dry-run
j3 eval --tasks examples/greenshot_bugs
pytest
```

## Repository Layout

```text
.
├── cli.py          # root script wrapper
├── cli/            # command handlers and parser wiring
├── j3/             # core implementation package
│   ├── actions.py
│   ├── features.py
│   ├── prompt_jepa.py
│   ├── prompt_repo_transitions.py
│   ├── request_spec.py
│   ├── repo.py
│   ├── repo_state.py
│   ├── synth.py
│   └── training.py
├── docs/           # focused long-form docs
├── examples/       # small local repos for demos and smoke tests
├── plans/          # active plan, progress log, and strategy
├── tests/          # pytest suite
├── pyproject.toml  # packaging, CLI entry point, test config
└── README.md
```

## Current Training Output

The first `train` implementation is a pure-Python prototype. It does not yet
train a neural network. It creates a small JEPA-shaped baseline that proves the
local data loop:

1. scan a Python repository
2. generate synthetic broken versions with AST-level mutations
3. embed the broken and repaired source states
4. learn action-specific latent delta prototypes
5. write reproducible artifacts under `runs/`

```bash
j3 train --data examples/greenshot_bug
```

You can also train from more than one local repo:

```bash
j3 train --data ../Decepticon ../scientific-agent-skills ../CLI-Anything
```

Artifacts:

```text
runs/greenshot-1/
├── examples.jsonl    # synthetic break/fix transition records
├── metrics.json      # counts, dimensions, and action distribution
└── model.json        # prototype latent action model
```

This gives the next step something concrete to consume: `patch` can load
`model.json`, score candidate structured edits, and make the first patch attempt.

For the larger Apache-licensed Python corpus and reproduction commands, see
[docs/TRAINING.md](docs/TRAINING.md).

`j3 mine` can also extract real Python file transitions from git history:

```bash
j3 mine \
  --repo /Users/aa/os/python/psf__black \
  --out data/transitions/psf__black.jsonl \
  --max-commits 25
```

Those mined transitions can be included during training:

```bash
j3 train \
  --data /Users/aa/os/python/*__* \
  --transitions data/transitions \
  --out runs/apache-python-git \
  --max-examples 10000
```

## Example Failing Repo

`examples/greenshot_bug` is a tiny Python repo with one intentional bug and one
failing pytest test. It is the stable first target for `j3 patch`:

```bash
cd examples/greenshot_bug
pytest tests/test_calculator.py
```

Expected result today:

```text
1 failed, 1 passed
```

From the `j3` repo root, use it with:

```bash
j3 patch --repo examples/greenshot_bug --test "python -m pytest tests/test_calculator.py" --dry-run
```

Without `--dry-run`, `j3 patch` applies the first candidate that passes the
requested test in a temporary copy of the repo.

When `runs/greenshot-1/model.json` exists, `patch` uses it by default to rank
candidate edits by latent action-delta similarity before running tests. You can
also pass a model explicitly:

```bash
j3 patch \
  --repo examples/greenshot_bug \
  --test "python -m pytest tests/test_calculator.py" \
  --model runs/greenshot-1/model.json \
  --dry-run
```

## Human-Facing Fix Workflow

`j3 fix` is the first command meant to feel like a coding assistant workflow
instead of a low-level patch primitive:

```bash
j3 fix --repo . --test "python -m pytest"
```

It runs the test command, parses failing pytest targets, plans a patch for each
target, prints the diff, and asks before applying. Use `--dry-run` to preview
without changing files:

```bash
j3 fix \
  --repo examples/greenshot_bug \
  --test "python -m pytest tests/test_calculator.py" \
  --dry-run
```

Use `--yes` for non-interactive application after a candidate passes in a
temporary copy:

```bash
j3 fix \
  --repo examples/greenshot_bug \
  --test "python -m pytest tests/test_calculator.py" \
  --yes
```

This is still no-LLM mode. The human provides the executable target, and `j3`
handles structured patch planning, model-ranked search, test validation, and
review.

## GreenShot-2 Evaluation

`examples/greenshot_bugs` is a five-task repair benchmark covering:

- wrong return expression
- wrong comparison operator
- wrong literal constant
- wrong item access
- missing empty-input guard

Run it with:

```bash
j3 eval --tasks examples/greenshot_bugs
```

`eval` runs each task in an isolated temporary copy and compares unranked
candidate order against model-ranked candidate order. The current metrics are
small and local by design; they are meant to show whether the latent scorer is
reducing search, not to claim broad coding-agent capability yet.

## Initial Patch Action Space

The early action space is deliberately small:

- `replace_expr`
- `insert_guard`
- `change_literal`
- `change_operator`
- `swap_call_arg`
- `add_import`
- `change_attribute`
- `wrap_try_except`
- `change_return_value`
- `rename_symbol`
- `modify_condition`
- `propagate_signature`

This keeps the first model honest. It either learns to choose useful edits from
real repo signals, or it fails visibly.

## Local Training Plan

The first training set can be generated without scraping private code:

1. Start from passing Python projects.
2. Apply controlled mutations that create failing tests.
3. Store the failing repo state, pytest output, repair action, and repaired
   state.
4. Train a small JEPA-style model to predict the latent repaired state and rank
   useful actions.

The first target is not arbitrary SWE-bench performance. A useful early result
would be strong `pass@1` on held-out synthetic Python bugs, then a constrained
subset of generated software-engineering tasks.

## Developer Roadmap

The project should grow in this order:

1. Define structured patch actions and repo-state records.
2. Add a Python AST parser and target selector.
3. Add a deterministic patch materializer.
4. Generate synthetic break/fix transitions from small repos.
5. Train a compact local JEPA predictor.
6. Replace the current deterministic candidate scorer with the trained model.
7. Add a distributed node that contributes anonymized transition metrics,
   adapters, or public examples.

## Hardware Target

The first implementation should be practical on a Mac Studio-class machine with
Apple silicon, 48 GB unified memory, and local Python projects. The first model
should be small enough that iteration speed matters more than benchmark scale.

## Status

This repository is at the small working prototype stage. It can generate local
repair-training artifacts, find and apply structured repairs for bundled
failures, parse the first supported calculator CLI requests into
`request-spec-v1`, generate a working calculator repo, and build/query/evaluate a
Prompt-JEPA index over prompt/spec/action/outcome rows without using an LLM.

## FAQ

See [docs/FAQ.md](docs/FAQ.md).
