# Today Plan: Productize Transition Scoring Without Fooling Ourselves

The last completed slice made `j3` more interesting to JEPA developers:

- `inspect-transition-assets` inventories local prompt/demo/mined/candidate
  artifacts.
- `demo-transition-bench` normalizes transition rows and action-choice groups.
- `transition-bench-v1`, `transition-action-choice-v1`, and
  `transition-action-scoring-eval-v1` are checked-in, tested schemas.
- The fixture demo runs locally with zero hosted LLM/API calls and zero hosted
  repo-context bytes.
- `docs/TRANSITION_BENCH.md` explains checked-in fixtures, ignored local data,
  and future release packaging.

That is good demo infrastructure, but it is not yet a product path. The next
work should make the benchmark honest on real local data and connect it to
actual repair planning in shadow mode before any production routing switch.

## Current Reality

Fresh local checks on May 17, 2026:

```bash
python cli.py inspect-transition-assets
```

Reported:

- prompt corpus present with 320 rows
- mined git transitions: 31 files, 1,842 rows
- candidate outcomes: 2 files, 642 rows
- prototype models: 1 file
- missing ignored assets are normal

Fixture bench:

```bash
python cli.py demo-transition-bench \
  --embedding-dim 8 \
  --top-k 1 \
  --out /tmp/j3-transition-bench-report.json
```

Result:

- 4 transition bench rows
- 1 action-choice group
- 2 candidates
- future scorer pass@1: 1/1
- existing-rank-order pass@1: 0/1
- zero hosted usage

Candidate-only local bench:

```bash
python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json
```

Result:

- 642 transition bench rows
- 88 action-choice groups
- 642 candidates
- future scorer pass@1: 30/88
- existing-rank-order pass@1: 65/88
- deterministic-random-order pass@1: 21/88
- zero hosted usage

Full local bench with mined transitions currently fails because three mined
rows have empty `after_source`:

- `data/transitions/apache-python/Netflix__metaflow.jsonl` row 46
- `data/transitions/apache-python/Netflix__metaflow.jsonl` row 47
- `data/transitions/apache-python/treeverse__dvc.jsonl` row 46

These facts are useful. They show the repo has real evidence, but also that the
current scorer and ingestion path are not ready to drive product behavior.

## Goal For The Next 24 Hours

Turn the transition bench from a demo into a product-readiness gate:

```text
real local rows
  -> robust normalization
  -> honest action-choice metrics
  -> calibrated scorer
  -> shadow planner advice
  -> guarded opt-in routing only after metrics pass
```

The product goal is not to make a prettier report. The product goal is to make
`j3 patch` and eventually `j3 fix` cheaper and more reliable by validating the
right candidate earlier, while preserving the current deterministic safety
boundary.

## Strategic Decision

Do not wire the current future scorer into production ranking yet.

Why:

- It loses badly to existing rank order on the local candidate outcome set:
  30/88 pass@1 vs 65/88.
- The full local bench can still crash on real mined rows with empty sources.
- A real coding agent must be robust on messy local artifacts and honest about
  when its learned or JEPA-shaped scorer is worse than the current heuristic.

The right next step is productization through shadow mode and gates:

- harden ingestion
- make scoring regressions visible
- train or calibrate a V2 scorer from candidate outcomes
- log scorer recommendations during real repair planning without changing the
  selected candidate
- enable opt-in ranking only when the scorer beats the existing baseline on a
  held-out benchmark

## Non-Goals

- Do not generate more prompts in this slice.
- Do not commit ignored `data/` or `runs/` artifacts.
- Do not publish a release zip until the bench survives local real data.
- Do not make transition scoring the default path for `patch` or `fix`.
- Do not hide weak metrics behind the fixture demo.
- Do not call hosted LLM, embedding, or repo-context APIs.

## Step-By-Step Work Plan

### Step 1: Harden Real-Data Normalization

Deliverable:

- update transition-bench normalization so mined git rows with empty
  `before_source` or `after_source` do not crash the full report
- choose an explicit behavior:
  - represent empty source as a valid empty-file transition, or
  - skip the row with a structured `skipped_rows` report
- include source path, row index, reason, repo, file path, and commit for every
  skipped row
- make `demo-transition-bench` report normalized row counts and skipped row
  counts by source kind
- add focused tests for empty before/after source rows

Verification:

```bash
pytest tests/test_transition_bench.py -q
pytest tests/test_transition_bench_demo.py -q
python cli.py demo-transition-bench \
  --embedding-dim 256 \
  --top-k 3 \
  --mined-transitions data/transitions/apache-python/*.jsonl \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-report.json
python -m json.tool /tmp/j3-transition-bench-local-report.json >/dev/null
```

### Step 2: Add Product-Readiness Gates To The Bench

Deliverable:

- add a `product_readiness` section to `transition-bench-demo-report-v1`
- compare the future scorer to existing rank order on solved groups:
  - pass@1 delta
  - top-k delta
  - MRR delta
  - average candidates validated before first pass
  - residual count
- emit a clear gate result:
  - `not_ready_underperforms_existing_rank_order`
  - `ready_for_shadow_mode`
  - `ready_for_guarded_opt_in`
- keep the current local result honest: the existing scorer should fail the
  guarded opt-in gate on the 88-group candidate bench

Verification:

```bash
pytest tests/test_transition_action_scoring.py -q
pytest tests/test_transition_bench_demo.py -q
python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json
```

### Step 3: Calibrate A V2 Action Scorer From Candidate Outcomes

Deliverable:

- add an evaluation-only `transition-action-future-scorer-v2`
- train or fit it from candidate outcome rows using existing local features:
  - action kind
  - action params
  - target context
  - failure-hint features
  - existing model/ranker scores when present
  - source/after embedding availability
- support train/validation splits by task family or source file
- persist scorer metadata and metrics
- compare V2 against:
  - V1 future scorer
  - existing rank order
  - stable lexical order
  - deterministic random order

Verification:

```bash
pytest tests/test_transition_action_scoring.py -q
python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json
```

Acceptance target for this slice:

- V2 must beat V1 on pass@1 and MRR.
- V2 must not be wired into production routing unless it also beats existing
  rank order on a held-out split.

### Step 4: Add Shadow Advice To Real Patch Planning

Deliverable:

- add a shadow-only option to `patch` and/or `eval`, for example:

```bash
python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-transition-advice.jsonl
```

- run the transition scorer over the same candidate set already generated by
  the repair planner
- do not change candidate order or selected patch in shadow mode
- write one advice row per repair plan:
  - repo state summary
  - candidate count
  - existing selected candidate
  - scorer top candidate
  - whether scorer agreed with existing rank order
  - whether scorer would have improved or regressed after validation is known
  - zero hosted usage fields

Why this matters:

- it connects the JEPA-shaped scorer to a real product path without risking
  regressions
- it creates training data from actual planner decisions

Verification:

```bash
pytest tests/test_patching.py -q
pytest tests/test_cli.py -q
python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-transition-advice.jsonl
```

### Step 5: Add A Guarded Opt-In Ranking Path

Deliverable:

- add a non-default flag such as `--transition-scorer-rank`
- require an explicit scorer artifact or explicit `--allow-experimental-ranking`
  style flag
- refuse to rank if the scorer report says the product gate failed
- keep `patch` and `fix` defaults unchanged
- report the gate decision in CLI output

Verification:

```bash
pytest tests/test_patching.py -q
pytest tests/test_fixing.py -q
pytest tests/test_cli.py -q
```

### Step 6: Update Product Docs

Deliverable:

- update `docs/TRANSITION_BENCH.md`
- add or update a product-focused doc section explaining:
  - demo mode
  - benchmark mode
  - shadow mode
  - guarded opt-in mode
  - why default production routing remains conservative
- keep `README.md` short and only link to the focused doc if needed

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- `plans/today.md` and `plans/today.progress.md` are restored.
- full local transition bench no longer crashes on empty mined source rows.
- reports include skipped/invalid-row accounting or valid empty-file handling.
- candidate-only local bench has an explicit product-readiness gate.
- current V1 scorer weakness is visible in the report, not hidden.
- shadow advice can be emitted from a real `patch` or `eval` path without
  changing behavior.

Strong success:

- V2 scorer improves over V1 on the local candidate outcome set.
- V2 has held-out metrics by task family or source file.
- guarded opt-in ranking refuses to activate when the gate fails.
- shadow advice rows can become new training data.
- docs clearly explain why this is moving toward product behavior rather than
  remaining a standalone demo.

## Testing Plan

Focused checks:

```bash
pytest tests/test_transition_bench.py -q
pytest tests/test_transition_bench_demo.py -q
pytest tests/test_transition_action_scoring.py -q
pytest tests/test_transition_action_choice.py -q
pytest tests/test_cli.py -q
pytest tests/test_patching.py -q
git diff --check
```

Manual product-readiness checks:

```bash
python cli.py inspect-transition-assets

python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json

python cli.py demo-transition-bench \
  --embedding-dim 256 \
  --top-k 3 \
  --mined-transitions data/transitions/apache-python/*.jsonl \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-report.json
```

Run full `pytest -q` only after broad shared changes or before an integration
gate.

## After This Slice

1. Build a small release artifact only after the local bench survives real
   ignored data and includes product-readiness gates.
2. Use shadow advice rows to train the next scorer.
3. Expand beyond calculator and GreenShot repair tasks only after action
   selection beats existing rank order on held-out repair groups.
4. Replace deterministic scorer features with a learned local encoder only
   after the product loop and metrics are stable.
