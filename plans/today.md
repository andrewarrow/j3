# Today Plan: Evidence Matrix And Guarded Product Trial

The shadow-suite loop is complete:

- `run-transition-shadow-suite` writes candidate outcomes, shadow advice,
  normalized shadow outcomes, a V3 report, residual-ready artifacts, and an
  evidence bundle in one run.
- `report-transition-residuals` turns held-out misses and shadow disagreements
  into grouped engineering evidence.
- `transition-action-shadow-features-v4` preserves bounded change-context
  metadata from diff/edit/AST-delta fields.
- docs explain the repeatable suite, residual report, evidence bundle, zero
  hosted usage, and guarded-ranking policy.

That is a strong local workflow, but it is still too small as product evidence.
The checked-in smoke suite has 5 tasks and the current V3 validation report has
only 1 held-out group. It reports `ready_for_shadow_mode`, not
`ready_for_guarded_opt_in`. The next slice should broaden the evidence into a
multi-suite matrix and use that matrix to decide whether any narrow guarded
trial is justified.

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

Candidate-only transition bench still shows why gates matter:

- 642 transition bench rows
- 88 action-choice groups
- 642 candidates
- V1 pass@1: 30/88
- V2 pass@1: 78/88
- existing-rank-order pass@1: 65/88
- V2 validation gate:
  `not_ready_underperforms_existing_rank_order`

Current shadow suite smoke:

```bash
python cli.py run-transition-shadow-suite \
  --tasks examples/greenshot_bugs \
  --out /tmp/j3-transition-shadow-suite-current \
  --force
```

Reported:

- tasks: 5
- ranked solved: 5
- advice rows: 5
- advice candidates: 185
- known validation rows: 4
- scorer/production agreement: 4/5
- held-out V3 gate: `ready_for_shadow_mode`
- residual failures: 0
- evidence checksums verify
- zero hosted token/context usage

This is good engineering hygiene, not enough product evidence. A JEPA developer
will want to see held-out behavior across task families, residuals where the
world-model scorer fails, and a clear decision about guarded ranking.

## Goal For The Next 24 Hours

Build a multi-suite evidence matrix:

```text
GreenShot task suites
  -> one shadow suite run per task family
  -> matrix summary across gates and metrics
  -> cross-suite residual report
  -> release evidence bundle
  -> guarded trial only where gates pass
```

The product goal is to make transition scoring trustworthy enough for a narrow
guarded trial, or to clearly prove why it should remain shadow-only. The JEPA
goal is to show a real local latent-state/action scoring loop evaluated across
more than one tiny fixture.

## Strategic Decision

Prioritize a benchmark matrix over another scorer version.

Why:

- The repo already has V1, V2, V3, shadow outcomes, residual reports, and
  evidence bundles.
- The current gap is not the lack of a scorer. It is the lack of broad,
  repeatable held-out evidence.
- A matrix over GreenShot suites gives product and JEPA readers a clearer
  picture of where transition scoring works, where it regresses, and whether
  guarded routing is justified.

Defaults remain conservative. Do not make transition scoring default in
`patch`, `fix`, `eval`, `implement`, or `change`.

## Non-Goals

- Do not generate more prompt rows.
- Do not commit generated suite outputs, JSONL artifacts, or evidence bundles.
- Do not bypass a failed product gate.
- Do not treat full-set wins as product readiness when held-out gates fail.
- Do not call hosted LLM, embedding, or repo-context APIs.

## Step-By-Step Work Plan

### Step 1: Recreate The Plan Files

Deliverable:

- restore `plans/today.md`
- restore `plans/today.progress.md`
- record that the shadow-suite queue is complete
- set the next active task to the multi-suite evidence matrix

Verification:

```bash
git diff --check
```

### Step 2: Define A Checked-In Matrix Manifest

Deliverable:

- add a small checked-in manifest, for example
  `examples/transition_shadow_matrix.json`
- include standard local suites:
  - `examples/greenshot_bugs`
  - `examples/greenshot_3`
  - `examples/greenshot_4`
  - selected bounded subsets of `examples/greenshot_5` and
    `examples/greenshot_6` if full runs are too slow
- include per-suite parameters:
  - max candidates
  - explore-after-pass
  - timeout
  - split key
  - validation fraction
- keep the manifest small enough for local development

Why this matters:

- another developer should know exactly what "the standard shadow evidence
  suite" means
- product gates need stable inputs

Verification:

```bash
pytest tests/test_transition_shadow_matrix.py -q
```

### Step 3: Add A Matrix Runner

Deliverable:

- add a command such as `run-transition-shadow-matrix`
- read the matrix manifest
- run `run-transition-shadow-suite` for each suite into a subdirectory
- write:

```text
matrix-manifest.json
matrix-summary.json
suite/<suite-id>/...
evidence/
```

- aggregate:
  - task count
  - solved count
  - advice rows
  - candidate count
  - held-out group count
  - V3 gate per suite
  - V3 vs existing-rank-order deltas
  - residual counts
  - zero hosted usage
- support `--only` or equivalent for one-suite debugging

Why this matters:

- this turns one-off suite runs into a repeatable product evidence matrix

Verification:

```bash
pytest tests/test_transition_shadow_matrix.py -q
pytest tests/test_cli.py -q
python cli.py run-transition-shadow-matrix \
  --matrix examples/transition_shadow_matrix.json \
  --out /tmp/j3-transition-shadow-matrix \
  --only greenshot_bugs
python -m json.tool /tmp/j3-transition-shadow-matrix/matrix-summary.json >/dev/null
```

### Step 4: Add Cross-Suite Residual Reporting

Deliverable:

- extend `report-transition-residuals` or add a matrix residual command
- consume one matrix output directory
- group residuals across suites by:
  - suite id
  - task family
  - action kind
  - source file
  - gate result
  - generation gap vs ranking gap
  - missing feature evidence
- include bounded examples from each failing suite
- include zero hosted usage totals

Why this matters:

- residuals are how this becomes product engineering rather than benchmark
  decoration

Verification:

```bash
pytest tests/test_transition_residuals.py -q
python cli.py report-transition-residuals \
  --matrix /tmp/j3-transition-shadow-matrix \
  --json
```

If the command shape changes during implementation, update this plan and
record the reason in `plans/today.progress.md`.

### Step 5: Produce A Release-Quality Matrix Evidence Bundle

Deliverable:

- extend `build-transition-evidence-bundle` or add a matrix bundle command
- package:
  - matrix manifest
  - matrix summary
  - per-suite product gates
  - residual report
  - checksums
  - reproduction commands
  - zero hosted usage assertions
- do not include large generated JSONL by default unless explicitly requested
- make checksum verification work from any directory

Why this matters:

- JEPA developers need a portable artifact they can inspect without trusting
  local terminal output

Verification:

```bash
python cli.py build-transition-evidence-bundle \
  --matrix /tmp/j3-transition-shadow-matrix \
  --out /tmp/j3-transition-matrix-evidence
python -m json.tool /tmp/j3-transition-matrix-evidence/manifest.json >/dev/null
shasum -a 256 -c /tmp/j3-transition-matrix-evidence/checksums.sha256
```

### Step 6: Decide The Guarded Trial From Matrix Gates

Deliverable:

- if one or more suites report `ready_for_guarded_opt_in`, run a guarded trial
  only for those suites
- otherwise, record a clear blocked decision in the matrix summary:

```text
guarded_trial_decision: blocked_by_product_gate
```

- compare guarded trial results against shadow/baseline evidence when a trial
  is allowed:
  - solved count
  - pass@1
  - average candidates tested
  - regressions
  - runtime
  - zero hosted usage

Why this matters:

- this is the product boundary: evidence can permit a narrow trial, but failed
  gates must block routing

Verification:

```bash
pytest tests/test_evaluation.py -q
pytest tests/test_cli.py -q
```

### Step 7: Update Docs And README Only If Needed

Deliverable:

- update `docs/TRANSITION_BENCH.md` with matrix workflow
- keep `README.md` small
- if the matrix evidence is strong, add a short README line pointing to the
  matrix evidence workflow; otherwise leave README alone and keep details in
  docs

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- `plans/today.md` and `plans/today.progress.md` are restored.
- a checked-in matrix manifest defines the standard local shadow suites.
- a matrix runner can run at least one suite and write a valid summary.
- the matrix summary records gate results and zero hosted usage.
- generated suite and matrix artifacts stay out of git.

Strong success:

- the matrix runs multiple GreenShot suites locally.
- cross-suite residuals reveal at least one actionable failure family.
- evidence bundle packages the matrix summary and verifies checksums.
- guarded trial is either run only for passing suites or explicitly blocked by
  product gates.
- docs make the workflow reproducible for another developer.

## Testing Plan

Focused tests first:

```bash
pytest tests/test_transition_shadow_suite.py -q
pytest tests/test_transition_residuals.py -q
pytest tests/test_transition_evidence_bundle.py -q
pytest tests/test_cli.py -q
pytest tests/test_evaluation.py -q
git diff --check
```

Manual checks:

```bash
python cli.py run-transition-shadow-suite \
  --tasks examples/greenshot_bugs \
  --out /tmp/j3-transition-shadow-suite-current \
  --force

python cli.py report-transition-residuals \
  --shadow-outcomes /tmp/j3-transition-shadow-suite-current/transition-shadow-outcomes.jsonl \
  --shadow-scorer-report /tmp/j3-transition-shadow-suite-current/shadow-scorer-v3-report.json \
  --candidate-outcomes /tmp/j3-transition-shadow-suite-current/candidate-outcomes.jsonl \
  --json
```

Run full `pytest -q` only after broad shared changes or before an integration
gate.

## After This Slice

1. If matrix gates pass, prepare a narrow guarded-ranking release candidate.
2. If matrix gates fail, prioritize the top residual family over any routing
   change.
3. Publish or attach a matrix evidence bundle as a release artifact instead of
   committing generated JSONL data.
4. Use matrix residuals to decide whether the next improvement belongs in
   candidate generation, scorer features, or repo-state encoding.
