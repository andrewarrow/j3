# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: continuous loop mode. The active set may be empty only
  while the coordinator is recording the next assignments; ready work should be
  dispatched rather than leaving the board idle.
- Current product gate stance: transition ranking remains shadow-only; the
  2026-05-18 `TRANS-001` matrix decision was `remain_shadow_only`.

## Active Tasks

### `TRANS-004`: Rerun targeted matrix evidence after subscript-key fix

- Owner: worker Herschel (`019e3b15-7b18-7e51-af93-2c64da4243b8`)
- Status: active
- Write scope: generated outputs under `/tmp`, `plans/progress.md`,
  `plans/active.md`; small runner bug fixes only if local and necessary.
- Acceptance: rerun `greenshot_6_subset` with the standard matrix runner,
  record whether `http_no_store_directive_subscript_key` is solved within the
  matrix cap, and update residual/gate counts for that subset.
- Tests: targeted matrix command with `--only greenshot_6_subset`,
  `report-transition-residuals --matrix`, guarded decision if applicable, and
  focused transition tests if command behavior changes.

### `OPS-002`: Add a lightweight plan consistency check

- Owner: worker Chandrasekhar (`019e3b15-7b3a-7461-9dc5-4db9b20d168e`)
- Status: active
- Write scope: small checker command or test around `plans/active.md` and
  `plans/backlog.md`, plus `plans/progress.md` and `plans/active.md`.
- Acceptance: focused test catches missing task IDs, invalid statuses, active
  tasks missing from backlog, and completed/active status drift.
- Tests: new focused test plus `git diff --check`.

## Ready Queue

These are good next assignments for the next loop:

1. `GS7-002`: add five non-calculator request-to-repo fixtures.
2. `DATA-003`: prototype issue/PR mining manifest.
3. `REPO-001`: summarize repo-state encoder coverage.
4. `ACT-001`: create action coverage map from residuals.

Run at most two tasks in parallel unless write scopes are plainly disjoint.

## Paused Or Blocked

- `TRANS-003`: blocked until the `TRANS-002` generation and ranking residuals
  have focused fixes or regression evidence; do not expand the full matrix
  until targeted `TRANS-004` evidence is recorded.
- `DATA-004`: blocked until issue/PR mining exists; schema validation now
  exists from `DATA-002`.
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

- `DATA-002`: added repeatable prompt/spec corpus schema validation on top of
  the `inspect-prompt-corpus` profile path. The validator accepts the seed,
  expanded, and GreenShot-7 intent corpora with zero errors while reporting
  legacy seed expected-action gaps and cross-split near-duplicates as review
  warnings.
- `ACT-002`: fixed the subscript-key candidate cap gap for
  `greenshot_6_subset/http_no_store_directive_subscript_key`. The passing
  `change_subscript_key` candidate from `"no-store"` to `"no_store"` now ranks
  first and validates under `--max-candidates 8`; focused candidate ranking and
  patching tests passed.
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
