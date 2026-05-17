# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: evidence matrix and guarded product trial.
- Completed iterations for this reset: 0.
- Latest relevant commits:
  - `c6dbe26` closed the shadow suite loop.
  - `aedb04a` documented the transition shadow suite workflow.
  - `1c47171` improved transition scorer change features.
  - `23f37ac` added the transition residual report.
  - `0aae784` added the transition shadow suite command.
  - `2664a95` documented shadow-to-gate evidence.
- Current blocker: the checked-in shadow suite reports
  `ready_for_shadow_mode`, not `ready_for_guarded_opt_in`; guarded production
  ranking remains blocked unless broader matrix evidence passes product gates.
- Next task: define a checked-in transition shadow matrix manifest.

## Active Task Queue

- [x] Recreate `plans/today.md` and `plans/today.progress.md`.
- [ ] Define a checked-in shadow matrix manifest.
- [ ] Add a matrix runner over standard shadow suites.
- [ ] Add cross-suite residual reporting.
- [ ] Produce a release-quality matrix evidence bundle.
- [ ] Decide guarded trial eligibility from matrix gates.
- [ ] Update docs and README only if needed.

## Current Facts

- The user deleted `plans/today.md` and `plans/today.progress.md`; they have
  been recreated with the next active slice rather than restored to the
  completed shadow-suite queue.
- The completed shadow-suite queue added:
  - `run-transition-shadow-suite`
  - `report-transition-residuals`
  - bounded `change_context` feature metadata for V3 scoring
  - shadow suite product docs
- `inspect-transition-assets` reports:
  - prompt corpus present with 320 rows
  - mined git transitions: 31 files, 1,842 rows
  - candidate outcomes: 2 files, 642 rows
  - prototype models: 1 file
- Candidate-only transition bench still shows:
  - 642 transition bench rows
  - 88 action-choice groups
  - 642 candidates
  - V1 pass@1: 30/88
  - V2 pass@1: 78/88
  - existing-rank-order pass@1: 65/88
  - V2 validation gate:
    `not_ready_underperforms_existing_rank_order`
- Current shadow suite smoke over `examples/greenshot_bugs` reports:
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

## Checks Run During Plan Recreation

```bash
python cli.py run-transition-shadow-suite \
  --tasks examples/greenshot_bugs \
  --out /tmp/j3-transition-shadow-suite-current \
  --force

python -m json.tool /tmp/j3-transition-shadow-suite-current/evidence/manifest.json >/dev/null
shasum -a 256 -c /tmp/j3-transition-shadow-suite-current/evidence/checksums.sha256

python cli.py report-transition-residuals \
  --shadow-outcomes /tmp/j3-transition-shadow-suite-current/transition-shadow-outcomes.jsonl \
  --shadow-scorer-report /tmp/j3-transition-shadow-suite-current/shadow-scorer-v3-report.json \
  --candidate-outcomes /tmp/j3-transition-shadow-suite-current/candidate-outcomes.jsonl \
  --json
```

## Worker Iteration Template

Use this shape for each worker handoff:

```md
### Iteration N: <task>

- Worker:
- Goal:
- Files changed:
- Tests run:
- Result:
- Commit:
- Push:
- Next:
- Blockers:
```

## 2026-05-17

### Reset: Evidence matrix and guarded product trial

- Worker: local planner
- Goal: recreate deleted `plans/today.md` and `plans/today.progress.md` with
  the next work after the completed shadow-suite queue.
- Files changed: `plans/today.md`, `plans/today.progress.md`
- Result: new plan prioritizes a multi-suite shadow evidence matrix,
  cross-suite residuals, release-quality matrix evidence, and guarded trial
  eligibility only when product gates pass.
- Tests run: `git diff --check` passed.
- Next: implement Step 2, the checked-in matrix manifest.
- Blockers: guarded ranking remains blocked until product gates pass.
