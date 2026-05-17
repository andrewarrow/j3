# Today Plan: Shadow Suite And Residual-Driven Readiness

The shadow-to-gate infrastructure is now complete:

- `summarize-transition-advice` summarizes shadow advice rows.
- `normalize-transition-shadow-outcomes` joins advice to candidate outcomes.
- `evaluate-transition-shadow-scorer` trains and evaluates the held-out V3
  scorer.
- `build-transition-evidence-bundle` packages reproducible local evidence.
- `patch` and `eval` support shadow advice.
- `patch` and `eval` support guarded, non-default ranking, but failed product
  gates refuse ranking.
- `docs/TRANSITION_BENCH.md` explains demo, benchmark, shadow, V3, bundle, and
  guarded modes.

That is enough infrastructure for JEPA developers to inspect a real
state/action/consequence loop. The next slice should make the evidence stronger
and more product-real: run a repeatable shadow evaluation suite, study held-out
residuals, improve the scorer or candidate features where it is weak, and only
then attempt a narrow guarded trial.

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

Candidate-only transition bench:

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
- V2 validation gate:
  `not_ready_underperforms_existing_rank_order`
- zero hosted token/context usage

The shadow-to-gate queue added V3, but V2/V3 evidence must pass held-out gates
before guarded ranking is allowed for ordinary product use. That is the right
product boundary.

## Goal For The Next 24 Hours

Build a repeatable shadow evaluation suite and use its residuals to improve
product readiness:

```text
standard repair task suite
  -> candidate outcomes + shadow advice
  -> shadow outcomes
  -> held-out V3 report
  -> residual report
  -> evidence bundle
  -> narrow guarded trial only if gates pass
```

The outcome should be an evidence-producing workflow that a JEPA developer can
run locally and a product engineer can trust. It should answer:

- where does the transition scorer beat the existing rank order?
- where does it regress?
- which features or action generators need work?
- does held-out evidence justify any guarded trial?

## Strategic Decision

Prioritize repeatable held-out evidence over new model machinery.

Why:

- The repo already has V1/V2/V3 scorers and multiple artifact schemas.
- The product blocker is evidence quality, not another command name.
- A coding agent becomes real when it improves the candidate actually
  validated first, under repeatable held-out conditions.
- JEPA developers will trust residuals, gates, and reproducible evidence more
  than a larger pile of prompt rows.

Defaults stay conservative. Do not make transition scoring default in `patch`,
`fix`, `eval`, `implement`, or `change` during this slice.

## Non-Goals

- Do not generate more prompt labels.
- Do not commit generated `data/`, `runs`, `/tmp` artifacts, shadow advice, or
  evidence bundles.
- Do not bypass failed V2/V3 product gates.
- Do not publish benchmark claims without held-out split details.
- Do not call hosted LLM, embedding, or repo-context APIs.

## Step-By-Step Work Plan

### Step 1: Recreate The Plan Files

Deliverable:

- restore `plans/today.md`
- restore `plans/today.progress.md`
- record the completed shadow-to-gate queue
- set the next active task to a repeatable shadow suite

Verification:

```bash
git diff --check
```

### Step 2: Add A Repeatable Shadow Eval Suite Command

Deliverable:

- add a command such as `run-transition-shadow-suite`
- run a standard local task set with:
  - candidate outcomes
  - diagnostics
  - transition scorer shadow advice
  - shadow advice summary
  - normalized shadow outcomes
  - held-out V3 report
  - evidence bundle
- write everything under a caller-provided ignored directory, for example:

```text
runs/transition-shadow-suite/<timestamp>/
  candidate-outcomes.jsonl
  transition-advice.jsonl
  diagnostics.json
  advice-summary.json
  transition-shadow-outcomes.jsonl
  shadow-scorer-v3-report.json
  evidence/
```

- default to checked-in examples small enough for local use
- accept explicit task paths for broader local runs
- record exact commands and zero hosted usage

Why this matters:

- developers should not have to manually stitch six commands together to
  reproduce the product evidence loop
- product readiness needs repeatable runs, not one-off `/tmp` artifacts

Verification:

```bash
pytest tests/test_transition_shadow_suite.py -q
pytest tests/test_cli.py -q
python cli.py run-transition-shadow-suite \
  --tasks examples/greenshot_bugs \
  --out /tmp/j3-transition-shadow-suite
python -m json.tool /tmp/j3-transition-shadow-suite/shadow-scorer-v3-report.json >/dev/null
python -m json.tool /tmp/j3-transition-shadow-suite/evidence/manifest.json >/dev/null
```

### Step 3: Add A Residual Report For V3 And Shadow Outcomes

Deliverable:

- add a residual report command or module, for example
  `report-transition-residuals`
- consume:
  - `transition-shadow-outcome-v1`
  - V3 report
  - candidate outcomes
- group failures by:
  - task family
  - action kind
  - source file
  - scorer top candidate vs production candidate
  - missing feature evidence
  - candidate-generation gap vs scorer-ranking gap
- list bounded examples with exact candidate summaries
- include zero hosted usage fields

Why this matters:

- residuals turn JEPA evidence into engineering work
- product improvements should come from concrete failure modes, not generic
  "train harder" claims

Verification:

```bash
pytest tests/test_transition_residuals.py -q
python cli.py report-transition-residuals \
  --shadow-outcomes /tmp/j3-transition-shadow-suite/transition-shadow-outcomes.jsonl \
  --shadow-scorer-report /tmp/j3-transition-shadow-suite/shadow-scorer-v3-report.json \
  --json
```

### Step 4: Improve The Scorer Or Features From Residuals

Deliverable:

- pick one bounded residual family from the report
- improve the local feature representation or action-choice metadata
- examples of acceptable changes:
  - better failure-hint alignment features
  - richer action parameter signatures
  - source-context features that do not leak validation labels
  - candidate-after delta features where already available
- rerun the shadow suite and compare V3 against the previous report
- keep production rank as an ablation only, not a default feature

Why this matters:

- this is where the repo becomes a product: measured residuals produce a
  specific improvement, and gates decide whether it is useful

Verification:

```bash
pytest tests/test_transition_action_scoring.py -q
pytest tests/test_transition_shadow_scorer.py -q
python cli.py run-transition-shadow-suite \
  --tasks examples/greenshot_bugs \
  --out /tmp/j3-transition-shadow-suite-after
```

### Step 5: Add A Narrow Guarded Trial Only If Gates Pass

Deliverable:

- if and only if held-out product gates pass, add or document a guarded trial
  command over the same task suite:

```bash
python cli.py eval \
  --tasks examples/greenshot_bugs \
  --transition-scorer-rank \
  --transition-scorer-report /tmp/j3-transition-shadow-suite-after/shadow-scorer-v3-report.json \
  --candidate-outcomes /tmp/j3-guarded-candidate-outcomes.jsonl \
  --diagnostics /tmp/j3-guarded-diagnostics.json
```

- compare against the baseline eval:
  - solved tasks
  - pass@1
  - average candidates tested
  - regressions
  - runtime
  - zero hosted usage
- if gates do not pass, record the blocker and skip the trial

Why this matters:

- the first product use should be explicit, narrow, and reversible
- a failed gate is a useful result, not a reason to weaken the gate

Verification:

```bash
pytest tests/test_evaluation.py -q
pytest tests/test_cli.py -q
```

### Step 6: Update Evidence And Product Docs

Deliverable:

- update `docs/TRANSITION_BENCH.md` or add a focused
  `docs/TRANSITION_SHADOW_SUITE.md`
- explain:
  - the one-command shadow suite
  - residual reports
  - before/after scorer comparison
  - guarded trial requirements
  - when to stop and mine residuals instead of routing
- keep `README.md` small

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- `plans/today.md` and `plans/today.progress.md` are restored.
- a repeatable shadow suite command exists or the equivalent scripted workflow
  is documented and tested.
- advice, shadow outcomes, V3 report, and evidence bundle are produced in one
  run.
- residuals identify at least one concrete scorer or feature weakness.
- default product routing remains unchanged.

Strong success:

- one residual-driven scorer or feature improvement is implemented.
- V3 improves on a held-out split without using production rank as a default
  feature.
- evidence bundle includes before/after product gates.
- a guarded trial is run only if gates pass; otherwise the failed gate is
  documented as the product blocker.

## Testing Plan

Focused tests first:

```bash
pytest tests/test_transition_scorer_advice.py -q
pytest tests/test_transition_shadow_outcomes.py -q
pytest tests/test_transition_shadow_scorer.py -q
pytest tests/test_transition_evidence_bundle.py -q
pytest tests/test_cli.py -q
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

python cli.py summarize-transition-advice \
  --advice /tmp/j3-transition-advice.jsonl \
  --json
```

Run full `pytest -q` only after broad shared changes or before an integration
gate.

## After This Slice

1. If held-out gates pass repeatedly, document a narrow guarded ranking release
   candidate.
2. If held-out gates fail, use residuals to improve candidate generation,
   feature extraction, or the scorer.
3. Package a release evidence bundle for external JEPA developers once the
   shadow suite is repeatable.
4. Consider default routing only after repeated held-out wins and clean
   guarded-trial evidence.
