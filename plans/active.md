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

### `TRANS-002`: Diagnose matrix gate blockers

- Owner: worker Gauss (`019e3950-80f1-7ad1-b4f7-f39b67834c15`)
- Status: active
- Write scope: residual analysis docs, `plans/progress.md`,
  `plans/active.md`; targeted tests; small fixes only if directly supported by
  residual evidence.
- Acceptance: matrix blockers grouped as missing generation, bad ranking, weak
  observation, or insufficient validation, with recommended next actions.
- Tests: `pytest tests/test_transition_residuals.py -q`,
  `pytest tests/test_transition_shadow_matrix.py -q`, plus `git diff --check`.

### `DATA-001`: Audit expanded prompt corpus quality

- Owner: worker Pascal (`019e3950-8113-7cf3-ab6e-e813b4cd332f`)
- Status: active
- Write scope: prompt inspection command/report, `plans/progress.md`,
  `plans/active.md`; no large generated artifacts committed.
- Acceptance: report counts by source type, split, task type, domain,
  ambiguity, inferred defaults, and synthetic template family; flag leakage
  risks.
- Tests: focused prompt corpus tests or CLI smoke, plus `git diff --check`.

## Ready Queue

These are good next assignments after the current active tasks complete:

1. `OPS-002`: add a lightweight plan consistency check.
2. `GS7-002`: add five non-calculator request-to-repo fixtures.
3. `DATA-002`: add prompt/spec schema validation.

Run at most two tasks in parallel unless write scopes are plainly disjoint.

## Paused Or Blocked

- `TRANS-003`: blocked until `TRANS-002` diagnoses matrix blockers and proposes
  safe manifest expansion criteria.
- `DATA-004`: blocked until issue/PR mining and schema validation exist.
- `MODEL-002`: blocked until `TRANS-002` identifies concrete scorer/model
  residual fixes.

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
