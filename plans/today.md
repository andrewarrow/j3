# Today Plan: Prompt-JEPA Developer Demo And Corpus Scale-Up

This 24-hour plan replaces the now-complete Prompt-JEPA index implementation
slice with a developer-facing demo slice.

The right next move is not a deep Apache-source training run yet. The repo first
needs a compelling, reproducible story another developer can run in minutes:

```text
many coding-agent prompts
  -> local Prompt-JEPA context vectors
structured specs / actions / outcomes
  -> local target vectors
mixed labels + real outcome rows
  -> nearest evidence and dry-run planner proposals
demo report
  -> timings, index size, validation results, and hosted LLM API tokens = 0
```

Going deeper on Python source JEPA from `TRAINING.md` is still important, but it
should be the second move in this slice: add a thin source-embedding bridge to
the demo artifacts so prompt/spec/outcome rows start connecting to repo-state
vectors. Do not disappear into a long source-model experiment before the
prompt-to-repo demo is easy to understand.

## Goal For The Next 24 Hours

Build a fast, cheap, local Prompt-JEPA demo that makes the project direction
obvious:

- expand `../prompts` from the current 80-row seed into a larger tagged prompt
  corpus suitable for retrieval and held-out prompt evaluation
- keep generated prompt rows clearly marked by provenance
- build and validate a mixed Prompt-JEPA index from prompt labels and real
  `implement --record` / `change --record` outcome rows
- add a one-command demo/report path that prints:
  - corpus size and split counts
  - index build time, query latency, and index size
  - top-k evidence for representative prompts
  - dry-run planner proposal summaries
  - generated repo validation results for supported calculator prompts
  - hosted LLM API token usage: `0`
  - repo text sent to a hosted model: `0 bytes`
- add a small source-encoding sidecar for generated Python files using the
  existing `features.embed_python_source` path, without starting a large neural
  training run

## Strategic Decision

Prioritize the demo and corpus before deeper source training.

Why:

- external developers need to see the loop run, not only read a roadmap
- the current 80-row `../prompts` corpus is too small and sparse for compelling
  retrieval claims
- a local demo can show the concrete advantage: no hosted model call, no repo
  prompt stuffed into a context window, and structured output that is easy to
  inspect
- the Apache-source training path from `TRAINING.md` is valuable foundation, but
  its impact is less visible until connected to prompt/spec/outcome records

The source path should stay present as a bridge, not become the active rabbit
hole today.

## Existing Building Blocks

- `prompt_jepa.py` already supports:
  - separate context and target feature-hashed embeddings
  - persisted `j3.prompt-jepa-index.v1`
  - query
  - held-out retrieval eval
  - context-to-target predictor eval
  - mixed label/outcome indexing
  - evaluation-only planner proposals
- `examples/prompt_intents/greenshot_7_intents.jsonl` has focused calculator
  labels for supported, unsupported, and clarification paths.
- `../prompts/coding_agent_prompts_seed.jsonl` has 80 broader prompt rows.
- `j3 implement --record`, `j3 change --record`, and `j3 greenshot-7 --record`
  can produce real prompt/spec/action/outcome rows.
- `features.py` and `training.py` already provide deterministic Python source
  embeddings and a JEPA-shaped repair transition baseline.
- `TRAINING.md` documents the Apache-licensed Python corpus and existing
  source-transition training path.

## Non-Goals For Today

- No production switch from deterministic `implement` / `change` routing to
  retrieval-assisted routing.
- No hosted LLM, embedding API, GPU, or model download.
- No claim that synthetic prompt rows prove broad generalization.
- No broad source-model rewrite or long Apache corpus retraining as the first
  task.
- No untagged generated prompts; every generated row must be labeled by
  provenance and split policy.
- No new dependency unless the standard library is clearly insufficient.
- No edits to `plan.md` unless the strategic roadmap itself changes.

## Step-By-Step Work Plan

### Step 1: Expand The Prompt Corpus Deliberately

Deliverable:

- add a reproducible way to create a larger prompt corpus under `../prompts`
  without overwriting the hand-authored seed
- target roughly 250 to 300 total rows for this slice
- keep rows compatible with `load_prompt_intent_records`
- include stable `id`, `split`, `source_type`, `task_type`, `repo_mode`,
  `domain`, `prompt`, `expected`, and `tags`
- use provenance such as `human_seed`, `synthetic_template_v0`, and
  `manual_reviewed_synthetic` rather than pretending all rows are human-written
- preserve train/validation/test splits by prompt family, not by near-duplicate
  paraphrase

Coverage priorities:

- calculator CLI create/change/clarification prompts
- general CLI apps: todo, notes, password generator, CSV tool, file renamer,
  expense tracker, timer, quiz, offline weather stub
- one-file Python libraries: strings, stats, validation, dates, cache, config,
  parsers, paths, money, collections
- existing-repo feature additions: CLI flags, API endpoints, serialization,
  pagination, logging, auth, config, export
- bugfix prompts with edge cases and preferred-patch hints
- tests-only prompts
- refactor prompts
- ambiguous prompts where `ask_clarification` is correct
- hard negatives where tempting domain inference would be wrong

Verification:

```bash
python cli.py train-prompt-intents \
  --labels ../prompts/coding_agent_prompts_seed.jsonl \
  --target expected_action repo_mode task_type domain requires_clarification \
  --show-residuals
```

After the expanded file exists, run the same command against it and record row
counts, split counts, and residual themes.

### Step 2: Add A Prompt Corpus Quality Gate

Deliverable:

- add a small profile/check path, such as `j3 inspect-prompt-corpus`, or extend
  existing prompt-intent tooling if that fits better
- report:
  - total rows
  - split counts
  - task type, repo mode, domain, expected action, and clarification counts
  - duplicate normalized prompts
  - near-duplicate family leakage across splits when a family field/tag exists
  - missing required fields
  - unsupported or unknown scalar labels
- JSON output for docs and regression tests

Verification:

```bash
pytest tests/test_prompt_intents.py -q
pytest tests/test_cli.py -q
python cli.py inspect-prompt-corpus \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --json
```

If the command name changes during implementation, update this plan and record
the reason in `plans/today.progress.md`.

### Step 3: Build The One-Command Prompt-JEPA Demo

Deliverable:

- add an evaluation/demo command or script, for example:

```bash
python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
```

- the demo should:
  - build a Prompt-JEPA index
  - run held-out retrieval eval
  - run representative queries
  - run dry-run planner proposals
  - create and validate at least one supported calculator repo
  - record blocked evidence for at least one unsupported/ambiguous prompt
  - print timings and artifact sizes
  - print `hosted_llm_api_tokens: 0`
  - print `hosted_repo_context_bytes: 0`

Representative prompts:

```text
make me a simple cli calc
make me a complex calc for spaceships
add exponent support
build a small todo cli where I can add tasks and mark them done
add auth
```

The non-calculator prompts can be retrieval/proposal-only until their structured
builders exist. The demo must be honest about what is supported, blocked, and
retrieval-only.

Verification:

```bash
pytest tests/test_prompt_jepa.py -q
pytest tests/test_cli.py -q
python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null
```

### Step 4: Build A Mixed Outcome Index For The Demo

Deliverable:

- generate real outcome rows in a temp demo directory:

```bash
python cli.py greenshot-7 \
  --out /tmp/j3-prompt-jepa-demo/greenshot-7 \
  --record /tmp/j3-prompt-jepa-demo/outcomes.jsonl

python cli.py implement \
  --prompt "make me a simple cli calc" \
  --out /tmp/j3-prompt-jepa-demo/simple-calc \
  --record /tmp/j3-prompt-jepa-demo/outcomes.jsonl

python cli.py change \
  --repo /tmp/j3-prompt-jepa-demo/simple-calc \
  --prompt "add exponent support" \
  --record /tmp/j3-prompt-jepa-demo/outcomes.jsonl
```

- build a mixed index from labels plus records:

```bash
python cli.py build-prompt-jepa-index \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --records /tmp/j3-prompt-jepa-demo/outcomes.jsonl \
  --out /tmp/j3-prompt-jepa-demo/index.json
```

- query/propose from the mixed index and show that real outcome metadata is
  present in the evidence

Verification:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/index.json >/dev/null
python cli.py propose-from-prompt-jepa \
  --index /tmp/j3-prompt-jepa-demo/index.json \
  --prompt "add power operator to the calculator" \
  --top-k 5
```

### Step 5: Add A Thin Python Source Encoding Bridge

Deliverable:

- for generated demo repos, encode Python files with `features.embed_python_source`
- store source-embedding metadata in the demo report or a sidecar JSON artifact:
  - feature version
  - embedding dimension
  - file path
  - vector dimension
  - vector norm or compact checksum
  - before/after availability when a change action was applied
- do not store huge vectors in README output
- do not retrain the Apache corpus model in this slice unless all demo work is
  already done

Why this matters:

- it visibly connects Prompt-JEPA to the source-transition machinery documented
  in `TRAINING.md`
- it creates the first bridge from prompt/spec/action/outcome records to
  repo-state representations
- it sets up the later model track:

```text
prompt context embedding
  + repo source embedding
  + structured action
  -> predicted target repo-state embedding
```

Verification:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/source-embeddings.json >/dev/null
```

### Step 6: Document The Demo In A Developer-Facing Way

Deliverable:

- add or update a focused demo document, such as `docs/PROMPT_JEPA_DEMO.md` if a
  docs directory is introduced, or a compact README section if not
- include:
  - exact run commands
  - sample output
  - what is real today
  - what is retrieval-only
  - why token/API cost is zero
  - why this is JEPA-shaped despite using deterministic V0 encoders
  - next source-JEPA step

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- expanded prompt corpus exists under `../prompts` and validates
- corpus profile/check output is available
- Prompt-JEPA build/query/eval works on the expanded corpus
- demo command or script produces a JSON report with timings, row counts,
  selected evidence, and `hosted_llm_api_tokens: 0`
- demo records at least one successful calculator repo build and one blocked or
  clarification outcome
- mixed labels+records index works
- production `implement` / `change` routing remains deterministic

Strong success:

- around 250 to 300 prompt rows with clear provenance and stable splits
- demo completes from a clean temp directory in under a minute on the local
  machine
- representative queries show sensible nearest evidence across supported,
  unsupported, ambiguous, and existing-repo prompts
- source-embedding sidecar connects generated Python files to `features.py`
- README or focused docs make the value proposition obvious to a developer:
  local, inspectable, cheap, no hosted token spend, no free-form patch sampling

## Testing Plan

Run focused checks first:

```bash
pytest tests/test_prompt_intents.py -q
pytest tests/test_prompt_jepa.py -q
pytest tests/test_cli.py -q
pytest tests/test_greenshot_7.py -q
python -m py_compile \
  prompt_intents.py prompt_jepa.py features.py \
  cli/handlers.py cli/parser.py cli/__init__.py
git diff --check
```

Manual smoke after implementation:

```bash
python cli.py train-prompt-intents \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --target expected_action repo_mode task_type domain requires_clarification \
  --show-residuals

python cli.py eval-prompt-jepa-index \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --mode compare

python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
```

Run full `pytest -q` only after broad shared changes or before a final
integration gate.

## Open Decisions

1. Expanded corpus filename:
   - Proposed: `../prompts/coding_agent_prompts_expanded_v0.jsonl`.

2. Generated prompt provenance:
   - Proposed: `synthetic_template_v0` for raw generated rows and
     `manual_reviewed_synthetic` only after human review.

3. Demo command name:
   - Proposed: `demo-prompt-jepa`.

4. Cost metric wording:
   - Proposed: report exact local facts, not speculative savings:
     `hosted_llm_api_tokens: 0`, `hosted_repo_context_bytes: 0`, index size,
     row count, build time, query time, and validation time.

5. Source work depth:
   - Proposed: add source-embedding sidecar only. Defer Apache corpus retraining
     until the demo is runnable and documented.

## After This Slice

1. Add the next non-calculator greenfield builder from the expanded corpus,
   likely a tiny one-file library or todo CLI.
2. Connect prompt/repo/action records to source-transition examples from
   `TRAINING.md`.
3. Build a small repo-state index over generated and mined Python examples.
4. Compare retrieval-assisted planner proposals against deterministic parser
   routes on held-out prompts.
5. Only then start a deeper source-JEPA training pass over the Apache corpus.
