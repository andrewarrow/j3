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

No worker tasks are active at this moment.

## Ready Queue

These are good next assignments after `OPS-001` is verified:

1. `TRANS-001`: run the full transition shadow matrix and record the gate
   result.
2. `GS7-001`: refresh current GreenShot-7 baseline.
3. `DATA-001`: audit expanded prompt corpus quality.

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

- `OPS-001`: migrated from the daily `today*` loop to persistent coordination
  files. Verification: `git diff --check` passed.
- Previous daily loop completed transition shadow suite, residual reports,
  matrix runner, matrix evidence bundle, guarded-trial decision, and matrix docs.
  Those results remain useful, but new work should be tracked here and in
  `plans/progress.md`.
