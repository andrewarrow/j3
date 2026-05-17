# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: evidence matrix and guarded product trial.
- Completed iterations for this reset: 3.
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
- Next task: produce a release-quality matrix evidence bundle.

## Active Task Queue

- [x] Recreate `plans/today.md` and `plans/today.progress.md`.
- [x] Define a checked-in shadow matrix manifest.
- [x] Add a matrix runner over standard shadow suites.
- [x] Add cross-suite residual reporting.
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

### Iteration 1: Checked-in transition shadow matrix manifest

- Worker: Codex worker iteration 1
- Goal: define a small checked-in transition shadow matrix manifest and focused
  shape tests without implementing the runner.
- Files changed: `examples/transition_shadow_matrix.json`,
  `tests/test_transition_shadow_matrix.py`, `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_transition_shadow_matrix.py -q` passed.
  - `git diff --check` passed.
- Result: added `transition-shadow-matrix-v1` with full local core suites
  (`greenshot_bugs`, `greenshot_3`, `greenshot_4`) and conservative
  name-filtered subsets for `greenshot_5` and `greenshot_6`.
- Commit: `71a3a44` (`Add transition shadow matrix manifest`)
- Push: pushed to `origin/main`.
- Next: implement `run-transition-shadow-matrix` to read the manifest, apply
  optional `task_names` filters for large suites, and aggregate per-suite
  outputs.
- Blockers: none. The `task_names` subset field is the smallest coherent shape
  for bounded GreenShot-5/6 runs because the current suite runner accepts task
  manifests/directories but not subset slicing yet.

### Iteration 2: Transition shadow matrix runner

- Worker: Codex worker iteration 2
- Goal: add `run-transition-shadow-matrix` over the standard shadow suites with
  `--only`, filtered subset manifests, per-suite output directories, matrix
  summary/manifest, and a lightweight matrix evidence area.
- Files changed: `j3/transition_shadow_matrix.py`, `cli/handlers.py`,
  `cli/parser.py`, `cli/__init__.py`, `tests/test_transition_shadow_matrix.py`,
  `tests/test_cli.py`, `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_transition_shadow_matrix.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `python cli.py run-transition-shadow-matrix --matrix examples/transition_shadow_matrix.json --out /tmp/j3-transition-shadow-matrix --only greenshot_bugs --force` passed.
  - `python -m json.tool /tmp/j3-transition-shadow-matrix/matrix-summary.json >/dev/null` passed.
  - `python -m json.tool /tmp/j3-transition-shadow-matrix/matrix-manifest.json >/dev/null` passed.
  - `python -m json.tool /tmp/j3-transition-shadow-matrix/evidence/manifest.json >/dev/null` passed.
  - `shasum -a 256 -c /tmp/j3-transition-shadow-matrix/evidence/checksums.sha256` passed.
  - `git diff --check` passed.
- Result: matrix runner reads `examples/transition_shadow_matrix.json`, runs
  selected suites under `suite/<suite-id>/`, writes `matrix-manifest.json`,
  `matrix-summary.json`, `evidence/`, aggregates requested suite metrics where
  available, and preserves zero hosted usage totals.
- Commit: `6a07639` (`Add transition shadow matrix runner`)
- Push: pushed to `origin/main`.
- Next: add cross-suite residual reporting.
- Blockers: none.

### Iteration 3: Cross-suite transition residual reporting

- Worker: Codex worker iteration 3
- Goal: let `report-transition-residuals` consume one
  `run-transition-shadow-matrix` output directory and aggregate residual
  evidence across suites.
- Files changed: `j3/transition_residuals.py`, `cli/handlers.py`,
  `cli/parser.py`, `tests/test_transition_residuals.py`,
  `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_transition_residuals.py -q` passed.
  - `pytest tests/test_transition_shadow_matrix.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `python cli.py run-transition-shadow-matrix --matrix examples/transition_shadow_matrix.json --out /tmp/j3-transition-shadow-matrix --only greenshot_bugs --force` passed.
  - `python cli.py report-transition-residuals --matrix /tmp/j3-transition-shadow-matrix --json` passed.
  - `git diff --check` passed.
- Result: added `transition-residual-matrix-report-v1`, `--matrix` input
  support for `report-transition-residuals`, cross-suite grouping by suite id,
  task family, action kind, source file, gate result, scorer/production
  comparison, missing feature evidence, and generation/ranking gap type.
  Bounded failing examples include suite id and gate result. Hosted usage
  totals are copied from `matrix-summary.json` when available.
- Commit: pending.
- Push: pending.
- Next: produce a release-quality matrix evidence bundle.
- Blockers: none. The fresh `greenshot_bugs` smoke matrix had zero residual
  failures, so it produced no failing examples; the focused fixture covers
  bounded failing examples.
