# Today Plan: Shadow-To-Gate Transition Scoring

The previous slice made transition scoring more than a standalone demo:

- full local transition-bench ingestion is robust to malformed mined rows
- `transition-bench-demo-report-v1` includes product-readiness gates
- `transition-action-future-scorer-v2` is calibrated from candidate outcomes
- `patch` and `eval` can emit transition-scorer shadow advice
- `patch` and `eval` have guarded, non-default transition-scorer ranking
- failed product gates refuse guarded ranking before candidate generation
- docs explain demo, benchmark, shadow, and guarded opt-in modes

That is a real product boundary, but the product is not ready to let transition
scoring drive default repair behavior. The next slice should turn shadow advice
and held-out evaluation into the evidence loop that can eventually justify a
default ranking change.

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
- V1 pass@1: 30/88
- V2 pass@1: 78/88
- existing-rank-order pass@1: 65/88
- V2 held-out validation gate:
  `not_ready_underperforms_existing_rank_order`
- zero hosted token/context usage

Full local bench with mined transitions:

```bash
python cli.py demo-transition-bench \
  --embedding-dim 256 \
  --top-k 3 \
  --mined-transitions data/transitions/apache-python/*.jsonl \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-report.json
```

Result:

- 2,485 normalized transition bench rows
- 3 skipped mined source rows
- 89 action-choice groups
- 644 candidates
- V1 pass@1: 31/89
- V2 pass@1: 81/89
- existing-rank-order pass@1: 65/89
- V2 held-out validation gate:
  `not_ready_underperforms_existing_rank_order`
- zero hosted token/context usage

The important fact is not that V2 looks good on the full set. The important
fact is that held-out validation still blocks guarded opt-in. That is the right
failure mode for a product: the scorer can be studied, but it cannot silently
take over repair routing.

## Goal For The Next 24 Hours

Build the shadow-to-gate loop:

```text
real patch/eval candidate set
  -> shadow transition advice
  -> joined advice + validation outcomes
  -> held-out scorer training/evaluation
  -> product gate decision
  -> guarded ranking only when evidence passes
```

The work should make `j3` more compelling to JEPA developers by showing a real
state/action/consequence learning loop over candidate futures. It should also
make the product more real by using the same candidates the repair planner
actually validates, preserving conservative defaults until held-out evidence
passes.

## Strategic Decision

Prioritize held-out shadow data over more demos or prompt generation.

Why:

- The prompt and transition demos already prove the artifact shape.
- The current product blocker is not lack of a CLI flag; the flag exists.
- The current product blocker is insufficient held-out evidence that transition
  scoring beats the existing rank order.
- Shadow advice is the safest source of new product data because it observes
  real planner decisions without changing behavior.

Do not make transition scoring default in `patch` or `fix` during this slice.
Use shadow mode, reports, and strict gates.

## Non-Goals

- Do not expand the synthetic prompt corpus.
- Do not commit generated `data/`, `runs/`, reports, or advice JSONL files.
- Do not weaken product gates just to enable guarded ranking.
- Do not use hosted LLM, embedding, or repo-context APIs.
- Do not change default `implement`, `change`, `patch`, or `fix` behavior.

## Step-By-Step Work Plan

### Step 1: Recreate The Plan Files

Deliverable:

- restore `plans/today.md`
- restore `plans/today.progress.md`
- record that the previous productization queue completed
- set the next active task to shadow-to-gate data collection

Verification:

```bash
git diff --check
```

### Step 2: Add A Shadow Advice Summary Command

Deliverable:

- add a command such as `summarize-transition-advice`
- read one or more `transition-scorer-advice-v1` JSONL files
- report:
  - advice row count
  - candidate count
  - scorer/production agreement rate
  - known improve/regress/no-change counts
  - pass@1 implied by production selected candidate
  - pass@1 implied by scorer top candidate when validation is known
  - average candidates saved or lost when validation is known
  - zero hosted token/context fields
- support `--json`

Why this matters:

- shadow advice becomes a measurable product artifact, not just debug output
- developers can inspect whether the scorer would have helped before enabling
  any ranking

Verification:

```bash
pytest tests/test_transition_scorer_advice.py -q
pytest tests/test_cli.py -q
python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-transition-advice.jsonl
python cli.py summarize-transition-advice \
  --advice /tmp/j3-transition-advice.jsonl \
  --json
```

### Step 3: Run A Real Shadow Eval Loop

Deliverable:

- document and smoke a command that runs `eval` with both candidate outcomes
  and transition advice enabled
- write ignored local artifacts under `/tmp` or `runs/`, not git:

```text
candidate-outcomes.jsonl
transition-advice.jsonl
diagnostics.json
summary.json
```

- ensure the resulting advice rows can be summarized and joined to candidate
  outcomes

Why this matters:

- the scorer must be tested against real repair planning, not only historical
  candidate rows

Verification:

```bash
python cli.py eval \
  --tasks examples/greenshot_bugs \
  --candidate-outcomes /tmp/j3-shadow-candidate-outcomes.jsonl \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-shadow-transition-advice.jsonl \
  --diagnostics /tmp/j3-shadow-diagnostics.json

python cli.py summarize-transition-advice \
  --advice /tmp/j3-shadow-transition-advice.jsonl \
  --json
```

If the exact `eval` flags differ, update this plan and record why in
`plans/today.progress.md`.

### Step 4: Normalize Shadow Advice Into A Training Surface

Deliverable:

- add a schema such as `transition-shadow-outcome-v1`
- join shadow advice rows with candidate outcome rows by task/phase/plan id
  where possible
- preserve unjoined rows with explicit reasons
- represent:
  - repo/task identity
  - production selected candidate
  - scorer top candidate
  - candidate ranking list
  - validation outcome when known
  - agreement/improvement/regression labels
  - zero hosted usage fields
- add deterministic writer/loader/validator helpers

Why this matters:

- this is the product-learning loop: what the world model would have done
  versus what the planner actually did, with validation evidence attached

Verification:

```bash
pytest tests/test_transition_shadow_outcomes.py -q
```

### Step 5: Train A Held-Out V3 Scorer From Shadow Outcomes

Deliverable:

- add `transition-action-future-scorer-v3` as evaluation-only
- train from action-choice groups plus shadow outcome rows
- add richer but local features:
  - action kind and parameter signatures
  - failure hint match features
  - source file / task family split features
  - candidate source/after embedding deltas when available
  - production rank as a feature only when explicitly allowed in an ablation
- evaluate with held-out splits:
  - by task family
  - by source file or repo
  - by time/order when possible
- compare V3 against:
  - V2
  - existing rank order
  - stable lexical order
  - deterministic random order

Why this matters:

- JEPA developers get a stronger local consequence-prediction experiment
- product gets a clear answer about whether the scorer can beat the current
  heuristic without overfitting the same candidate rows

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

### Step 6: Add A Release-Quality Evidence Bundle Command

Deliverable:

- add a command such as `build-transition-evidence-bundle`
- generate a local directory or zip with:
  - manifest
  - checksums
  - transition asset inventory
  - transition bench report
  - shadow advice summary
  - product readiness gate result
  - reproduction commands
- keep generated artifacts out of git
- make the bundle verifiable without hosted APIs

Why this matters:

- this gives JEPA developers something concrete to inspect and reproduce
- it avoids committing large JSONL data while making the evidence portable

Verification:

```bash
pytest tests/test_transition_evidence_bundle.py -q
python cli.py build-transition-evidence-bundle \
  --bench-report /tmp/j3-transition-bench-candidates-report.json \
  --out /tmp/j3-transition-evidence
python -m json.tool /tmp/j3-transition-evidence/manifest.json >/dev/null
shasum -a 256 -c /tmp/j3-transition-evidence/checksums.sha256
```

### Step 7: Update Product Documentation

Deliverable:

- update `docs/TRANSITION_BENCH.md` or add
  `docs/TRANSITION_SCORING_PRODUCT.md`
- explain:
  - shadow advice collection
  - advice summary metrics
  - shadow outcome joining
  - V3 held-out scoring
  - evidence bundles
  - why defaults remain conservative
- keep `README.md` small

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- deleted `plans/today.md` and `plans/today.progress.md` are recreated
- shadow advice has a summary command and focused tests
- a real `eval` shadow run writes advice rows and candidate outcomes
- the plan records whether shadow evidence helps or regresses
- generated data remains ignored or under `/tmp`
- default production routing remains unchanged

Strong success:

- shadow advice can be joined to candidate outcomes into a stable schema
- V3 improves over V2 on at least one held-out split
- guarded opt-in remains blocked unless held-out product gates pass
- evidence bundle command creates a portable local report for JEPA developers
- docs clearly distinguish demo evidence, benchmark evidence, shadow evidence,
  and production readiness

## Testing Plan

Focused tests first:

```bash
pytest tests/test_transition_scorer_advice.py -q
pytest tests/test_transition_action_scoring.py -q
pytest tests/test_transition_bench_demo.py -q
pytest tests/test_cli.py -q
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py -q
git diff --check
```

Manual checks:

```bash
python cli.py inspect-transition-assets

python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json

python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-transition-advice.jsonl
```

Run full `pytest -q` only after broad shared changes or before an integration
gate.

## After This Slice

1. If V3 passes held-out gates, enable guarded ranking in a narrow documented
   benchmark run, still not by default.
2. If V3 fails held-out gates, mine the residuals and add features or action
   generators where the scorer lacks signal.
3. Once shadow evidence is stable, publish a release evidence bundle instead
   of committing large generated data.
4. Only consider default routing changes after repeated held-out wins and a
   clean audit trail.
