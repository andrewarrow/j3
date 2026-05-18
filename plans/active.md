# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: planning-system migration complete; `TRANS-001` and
  `GS7-001` evidence runs complete; ready for follow-up triage.
- Current product gate stance: transition ranking remains shadow-only; the
  2026-05-18 `TRANS-001` matrix decision was `remain_shadow_only`.

## Active Tasks

No worker tasks are active at this moment.

## Ready Queue

These are good next assignments after the completed `TRANS-001` and `GS7-001`
evidence runs:

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
