# j3

`j3` is an experiment in building a local-first JEPA coding agent.

The goal is simple and ambitious: repair Python repositories by predicting the
consequences of code edits in latent repo space, without asking an LLM to
generate patch candidates first.

## Why This Exists

Most coding agents are language models wrapped in tools. They read files, guess
a patch, run tests, inspect the failure, and repeat. That can work, but it is
expensive, token-heavy, and often blind to the actual dynamics of a codebase.

`j3` treats a repository as a world:

- the current codebase is the state
- a patch is an action
- tests, type checks, stack traces, and runtime behavior are observations
- a passing test suite is a target state

Instead of generating arbitrary source text token by token, `j3` starts with a
structured patch action space. The model chooses an edit type, target, and
parameters. A deterministic patch engine turns that decision into a real diff.

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
j3 train --data examples/greenshot_bug
j3 train --data ../Decepticon ../scientific-agent-skills ../CLI-Anything
j3 patch --repo examples/greenshot_bug --test "python -m pytest tests/test_calculator.py" --dry-run
pytest
```

## Repository Layout

```text
.
├── actions.py        # structured patch actions and targets
├── cli.py            # command line interface
├── examples/         # small local repos for demos and smoke tests
├── features.py       # deterministic AST hashing encoder
├── repo.py           # repository discovery helpers
├── synth.py          # synthetic break/fix transition generation
├── training.py       # prototype local trainer
├── tests/            # pytest suite
├── pyproject.toml    # packaging, CLI entry point, test config
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

This repository is at the first working prototype stage. It can generate local
training artifacts, find a passing structured patch for the bundled failing
example, and apply that patch without using an LLM.
