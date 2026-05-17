# j3

`j3` is a local-first experiment in the future of coding agents: not a chatbot
that keeps guessing patches, but a repo-world model that predicts useful code
transitions before it acts.

## JEPA, In One Page

JEPA means Joint Embedding Predictive Architecture. The core idea is simple and
powerful: do not predict every raw token, pixel, or byte. Encode the important
state into an embedding, then predict the next useful embedding.

That matters because real intelligence is not memorizing surface detail. It is
tracking state, understanding action, and predicting consequence. In world-model
terms:

```text
current state + action -> predicted next state
```

For robots, the state might be a room. For video, it might be motion and object
relationships. For coding agents, the state is a repository.

The article
[What is JEPA?](https://medium.com/@tahirbalarabe2/what-is-jepa-085ca776013a)
frames JEPA as prediction in latent space: compress raw input into meaningful
representations, predict how those representations evolve, and use that for
planning. `j3` applies that idea to software engineering.

## Why Coding Agents Need This

Most coding agents still work like this:

```text
prompt + giant repo context -> generate patch tokens -> run tests -> retry
```

`j3` is building toward this instead:

```text
prompt / test failure
  -> structured goal
  -> repo-state embedding
  -> structured candidate action
  -> predicted repo-after state
  -> validation
```

That is the interesting future: coding agents that can reason about repository
state, compare possible edits, ask for clarification when the target is wrong,
and learn from real transition records. Less token guessing. More local
prediction, planning, and evidence.

## What Works Now

The current demo is intentionally narrow and concrete: a calculator CLI domain.
It already turns natural-language coding requests into structured specs,
generated repos, transition rows, a tiny predictor, and evaluation artifacts.

Run a real greenfield implementation:

```bash
python cli.py implement \
  --prompt "make me a simple cli calc" \
  --out /tmp/j3-calc-demo
```

Current output:

```text
j3 implement complete
task type: create_app
status: built
domain: calculator
features: add, subtract, multiply, divide
files written:
  calculator.py
  tests/test_calculator_cli.py
  request-spec.json
validation: passed
```

The generated repo works:

```bash
python /tmp/j3-calc-demo/calculator.py 8 '*' 7
python /tmp/j3-calc-demo/calculator.py 9 / 3
python -m pytest /tmp/j3-calc-demo/tests -q
```

Example results:

```text
56
3
2 passed
```

## The Prompt+Repo JEPA Demo

Run the full local demo:

```bash
python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
```

It produces a compact world-model-shaped artifact set:

```text
report.json              # summary, timings, metrics, zero hosted usage
index.json               # mixed prompt/spec/action/outcome Prompt-JEPA index
labels-index.json        # label-only Prompt-JEPA index
outcomes.jsonl           # real implement/change/blocked outcome rows
source-embeddings.json   # deterministic Python source embeddings
transitions.jsonl        # prompt-repo-transition-v1 rows
transition-model.json    # prompt-repo-transition-predictor-v0
transition-eval.json     # prompt-repo-transition-eval-v1 metrics/residuals
repos/simple-calc/       # generated calculator repo
```

The demo currently records:

```text
corpus rows: 320
mixed index rows: 323
transition rows: 3
hosted_llm_api_tokens: 0
hosted_repo_context_bytes: 0
```

Representative prompt behavior:

```text
"make me a simple cli calc"
  -> supported create-repo path, validation passed

"add exponent support"
  -> supported existing-repo change path, validation passed

"add auth"
  -> blocked clarification path, validation not run

"make me a complex calc for spaceships"
  -> retrieval-only evidence, not blindly implemented
```

Evaluate consequence prediction directly:

```bash
python cli.py eval-prompt-repo-transitions \
  --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl \
  --top-k 3 \
  --json
```

This compares a V0 transition predictor against a prompt-only nearest-neighbor
baseline and emits outcome-kind accuracy, validation-status accuracy,
repo-after embedding distance, source-change vs blocked splits, and residual
examples.

## Current Schemas

`j3` is deliberately inspectable. The important records are plain JSON:

```text
request-spec-v1
existing-repo-change-spec-v1
repo-state-v1
prompt-repo-transition-v1
prompt-repo-transition-predictor-v0
prompt-repo-transition-eval-v1
```

The current predictor is evaluation-only. Production `implement` and `change`
paths are still deterministic. That boundary is intentional: first make the
state/action/target loop measurable, then let learned models replace the rules.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python cli.py --help
```

More detail:
[docs/PROMPT_JEPA_DEMO.md](docs/PROMPT_JEPA_DEMO.md) and
[docs/TRANSITION_BENCH.md](docs/TRANSITION_BENCH.md).

## Why This Is Exciting

The compelling coding agent will not just autocomplete files. It will maintain
a compact model of the repo, predict what an edit will do, rank candidate
futures, and validate the cheapest path to the goal.

`j3` is a small repo, but it now has the shape of that system:

```text
prompt + repo_before + structured action
  -> predicted repo_after or blocked target
  -> measured against real validation outcomes
```

That is the loop coding agents need.
