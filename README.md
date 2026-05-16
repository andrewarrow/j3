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
j3 mine --repo ../some-python-project --out data/transitions/project.jsonl
j3 patch --repo examples/greenshot_bug --test "python -m pytest tests/test_calculator.py" --dry-run
j3 fix --repo examples/greenshot_bug --test "python -m pytest tests/test_calculator.py" --dry-run
j3 eval --tasks examples/greenshot_bugs
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

For the larger MIT Python corpus and reproduction commands, see
[TRAINING.md](TRAINING.md).

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
  --out runs/mit-python-git \
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

## FAQ

### Will j3 eventually have a Codex-like terminal UI?

That is a good target, but `j3` should not pretend to be a chat model. The
terminal UI should make the code-world planner easy to use:

```text
j3> fix failing tests
j3 found 3 failing tests.

Candidate patch:
  action: replace_expr
  file: pricing.py
  tests: pass

Apply? [y/n/show diff]
```

The useful product is a local coding engine that can inspect a repo, plan
structured edits, test those edits in temporary copies, and ask the human before
changing files.

### If there is no LLM, how can a human say "change this program to do x"?

In no-LLM mode, `j3` needs an executable or structured target. Examples:

```bash
j3 patch --repo . --test "python -m pytest tests/test_pricing.py"
j3 fix --repo . --failing-tests
j3 patch --repo . --goal discount_final_price --test "python -m pytest tests/test_pricing.py"
```

The key point is that the test, type error, lint error, benchmark failure, or
named structured goal tells `j3` what "better" means. The model can then search
for edits that move the repo toward that target state.

### How would no-LLM mode parse "make discounts return final price"?

It would not understand that sentence the way a language model does. A no-LLM
parser would be deliberately limited and transparent. It could use:

- keyword matching: `discount`, `final price`, `return`
- repo symbols: functions like `apply_discount`, files like `pricing.py`
- test names: `test_discount_returns_remaining_price`
- error output: assertion values such as `50.0 == 150`
- a small goal registry: `discount_final_price -> prefer final-price formulas`

For example, the phrase:

```text
make discounts return final price
```

could be converted into a structured hint:

```json
{
  "goal": "discount_final_price",
  "symbols": ["discount", "price"],
  "preferred_actions": ["replace_expr"],
  "requires_test": true
}
```

That hint can help rank candidates, but it is not enough by itself. In no-LLM
mode, `j3` should still require a test or another executable signal before it
applies a patch. Otherwise it is guessing from English, which is exactly the
behavior this project is trying to avoid.

### Should j3 use an LLM at all?

For open-ended human requests, yes, optionally. The clean architecture is:

```text
human request
  -> intent adapter
  -> j3 planner
  -> structured patch candidates
  -> tests/typechecks/runtime validation
  -> patch or human review
```

The intent adapter can be an LLM, a rule-based parser, or a future local
language model. Its job is to translate messy human language into structured
objectives, test ideas, file hints, and constraints.

`j3` remains the patch planner and verifier. The LLM does not need to generate
the final patch.

### What does the LLM-assisted version look like?

A human might type:

```text
add CSV export to reports and reject empty filenames
```

An intent adapter could turn that into:

```json
{
  "files_hint": ["reports.py", "export.py"],
  "tests_to_add": [
    "CSV export writes a header row",
    "empty filename raises ValueError"
  ],
  "constraints": [
    "preserve existing JSON export",
    "do not change the public API unless required"
  ]
}
```

Then `j3` can work against those executable targets. The important distinction
is that the LLM handles language and task decomposition; `j3` handles repo-state
prediction, structured edit ranking, and validation.

### What is the honest long-term claim?

`j3` should be able to repair code against executable signals without any LLM.
For natural human language, an LLM is useful as an optional intent adapter.

The project claim should stay precise:

> LLMs are optional for language. They are not the patch engine.
