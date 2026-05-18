# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: `TRANS-002` and `DATA-001` follow-up evidence complete;
  ready to assign schema validation and the subscript-key generation fix.
- Current product gate stance: transition ranking remains shadow-only; the
  2026-05-18 `TRANS-001` matrix decision was `remain_shadow_only`.

## Active Tasks

### `DATA-002`: Add prompt/spec schema validation

- Owner: worker Lorentz (`019e395a-dda5-7662-a474-16d7e9945ce7`)
- Status: active
- Write scope: request-spec/prompt corpus schema validator, focused tests,
  concise docs if needed, `plans/progress.md`, `plans/active.md`.
- Acceptance: validates seed and expanded prompt rows with clear errors for
  missing fields, bad splits, unsupported labels, list-typed expected fields,
  synthetic provenance, and cross-split near-duplicate review.
- Tests: focused schema/profile tests plus `git diff --check`.

### `ACT-002`: Fix subscript-key generation gap from matrix residuals

- Owner: worker Noether (`019e395a-ddca-7a23-9907-647fcd5a5154`)
- Status: active
- Write scope: repair patching candidate generation/ranking around subscript
  keys, focused tests, `plans/progress.md`, `plans/active.md`.
- Acceptance: `greenshot_6_subset/http_no_store_directive_subscript_key`
  produces and validates a passing `change_subscript_key` candidate within the
  configured candidate cap without regressing candidate ranking.
- Tests: focused patching/candidate ranking tests plus single GreenShot-6 task
  smoke and `git diff --check`.

## Ready Queue

These are good next assignments after the current active tasks complete:

1. `OPS-002`: add a lightweight plan consistency check.
2. `GS7-002`: add five non-calculator request-to-repo fixtures.
3. `DATA-003`: prototype issue/PR mining manifest.

Run at most two tasks in parallel unless write scopes are plainly disjoint.

## Paused Or Blocked

- `TRANS-003`: blocked until the `TRANS-002` generation and ranking residuals
  have focused fixes or regression evidence; do not expand the matrix while the
  current standard gate remains nonzero.
- `DATA-004`: blocked until issue/PR mining and schema validation exist.
- `MODEL-002`: waiting for coordinator scoping into bounded scorer tasks based
  on the `TRANS-002` ranking clusters, especially add-keyword decoys and
  mapping key/value target features.

## Coordinator Review Triggers

Review before assigning more work if:

- `TRANS-001` reports a gate worse than expected
- `GS7-001` reveals missing actions rather than simple ranking failures
- `DATA-001` shows prompt split leakage or weak schema consistency
- two workers need the same files
- the next useful task is unclear

## Recently Completed

- `DATA-001`: expanded `inspect-prompt-corpus` into a repeatable prompt corpus
  quality audit. Current 320-row corpus has no exact normalized duplicates,
  no unsupported scalar labels, and no family split leakage, but it has 2
  cross-split near-duplicate prompt pairs and schema consistency gaps that
  `DATA-002` should validate.
- `TRANS-002`: diagnosed the 2026-05-18 transition matrix residuals. Result:
  14 residual-report failures split into 1 candidate-generation gap
  (`change_subscript_key` for `http_no_store_directive_subscript_key`) and 13
  scorer-ranking gaps concentrated in add-keyword decoys, mapping key/value
  target confusion, boundary/literal ranking, and identifier/signature decoys.
  Diagnosis recorded in `docs/TRANSITION_MATRIX_RESIDUALS_2026-05-18.md`.
- `TRANS-001`: ran the full transition shadow matrix on 2026-05-18. Gate
  result: `remain_shadow_only`; guarded opt-in trial eligibility `false`.
  Matrix totals: 5 suites, 56 tasks, 55 ranked solved, 7 matrix residuals,
  14 residual report failures, zero hosted usage. Evidence under
  `/tmp/j3-trans-001-shadow-matrix` and `/tmp/j3-trans-001-matrix-evidence`.
- `GS7-001`: refreshed the current GreenShot-7 baseline. Result: 10 fixture
  tasks, 8 built and validation-passed, 2 intentionally blocked for
  clarification, no prompt-spec failures, missing-action failures, ranking
  failures, or generated pytest failures observed. Verification: focused
  GreenShot-7 tests plus direct `implement` CLI smoke passed.
- `OPS-001`: migrated from the daily `today*` loop to persistent coordination
  files. Verification: `git diff --check` passed.
- Previous daily loop completed transition shadow suite, residual reports,
  matrix runner, matrix evidence bundle, guarded-trial decision, and matrix docs.
  Those results remain useful, but new work should be tracked here and in
  `plans/progress.md`.
