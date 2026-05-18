# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: planning-system migration complete; ready to assign the
  first evidence and baseline tasks.
- Current product gate stance: transition ranking remains shadow-only until a
  full matrix decision says otherwise.

## Active Tasks

### `TRANS-001`: Run full transition shadow matrix

- Owner: worker Parfit (`019e3949-895a-7111-93a4-6218aba860fb`)
- Status: active
- Write scope: generated outputs under `/tmp`, `plans/progress.md`,
  `plans/active.md`; small bug fixes only if the runner fails.
- Acceptance: matrix summary, residual report, evidence bundle, and
  guarded-trial decision recorded with exact commands and gate result.
- Tests: matrix command, residual command, bundle command, guarded decision.

## Ready Queue

These are good next assignments after the current active tasks complete:

1. `DATA-001`: audit expanded prompt corpus quality.
2. `OPS-002`: add a lightweight plan consistency check.
3. `GS7-002`: add five non-calculator request-to-repo fixtures.

Run at most two of these in parallel at first. `TRANS-001` is mostly generated
output and progress notes; `GS7-001` or `DATA-001` can run beside it if their
write scopes stay separate.

## Paused Or Blocked

- `TRANS-002`: blocked until full matrix evidence exists.
- `TRANS-003`: blocked until matrix runtime and residuals are known.
- `DATA-004`: blocked until issue/PR mining and schema validation exist.
- `MODEL-002`: blocked until evidence review identifies concrete residuals.

## Coordinator Review Triggers

Review before assigning more work if:

- `TRANS-001` reports a gate worse than expected
- `GS7-001` reveals missing actions rather than simple ranking failures
- `DATA-001` shows prompt split leakage or weak schema consistency
- two workers need the same files
- the next useful task is unclear

## Recently Completed

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
