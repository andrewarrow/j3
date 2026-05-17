# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: productize transition scoring without fooling ourselves.
- Completed iterations for this reset: 0.
- Latest relevant commits:
  - `26cca1d` removed the old today plan files.
  - `4cca638` documented transition bench reproduction.
  - `760c1fe` added the transition bench demo.
  - `534545d` added the transition action scorer.
  - `3eb9c38` added transition action-choice groups.
  - `d95ebc7` defined the transition bench schema.
  - `7e3df39` added transition asset inventory.
- Current blocker: the full local transition bench crashes on mined rows with
  empty `after_source`; the current V1 future scorer also underperforms the
  existing rank order on local candidate outcomes.
- Next task: harden transition-bench normalization for real mined rows and add
  skipped/invalid-row accounting.

## Active Task Queue

- [ ] Harden real-data normalization for empty mined source rows.
- [ ] Add product-readiness gates to transition bench reports.
- [ ] Calibrate a V2 action scorer from candidate outcomes.
- [ ] Add shadow transition-scorer advice to real patch/eval planning.
- [ ] Add guarded, non-default opt-in ranking with gate enforcement.
- [ ] Update product docs for demo, benchmark, shadow, and guarded modes.

## Current Facts

- `plans/today.md` and `plans/today.progress.md` were deleted in commit
  `26cca1d` and have been recreated for the next slice.
- `inspect-transition-assets` runs locally and reports:
  - prompt corpus present with 320 rows
  - mined git transitions: 31 files, 1,842 rows
  - candidate outcomes: 2 files, 642 rows
  - prototype models: 1 file
- fixture `demo-transition-bench` runs locally:
  - 4 transition bench rows
  - 1 action-choice group
  - 2 candidates
  - future scorer pass@1: 1/1
  - existing-rank-order pass@1: 0/1
  - zero hosted token/context usage
- candidate-only local bench runs:
  - 642 transition bench rows
  - 88 action-choice groups
  - 642 candidates
  - V1 future scorer pass@1: 30/88
  - existing-rank-order pass@1: 65/88
  - deterministic-random-order pass@1: 21/88
  - stable-lexical-order pass@1: 13/88
  - zero hosted token/context usage
- full local bench with mined transitions currently fails with
  `ValueError: git_transition.after_source must be a non-empty string`.
- Empty `after_source` rows found:
  - `data/transitions/apache-python/Netflix__metaflow.jsonl` row 46
  - `data/transitions/apache-python/Netflix__metaflow.jsonl` row 47
  - `data/transitions/apache-python/treeverse__dvc.jsonl` row 46

## Checks Run During Plan Recreation

```bash
python cli.py inspect-transition-assets
python cli.py demo-transition-bench --embedding-dim 8 --top-k 1 --out /tmp/j3-transition-bench-report.json
python -m json.tool /tmp/j3-transition-bench-report.json >/dev/null
python cli.py demo-transition-bench --no-fixtures --embedding-dim 256 --top-k 3 --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl --out /tmp/j3-transition-bench-candidates-report.json
python -m json.tool /tmp/j3-transition-bench-candidates-report.json >/dev/null
```

The attempted full local bench failed as described above:

```bash
python cli.py demo-transition-bench --embedding-dim 256 --top-k 3 --mined-transitions data/transitions/apache-python/*.jsonl --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl --out /tmp/j3-transition-bench-local-report.json
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

### Reset: Productize transition scoring

- Worker: local planner
- Goal: recreate deleted `plans/today.md` and `plans/today.progress.md` with
  the next work after the completed transition bench demo.
- Files changed: `plans/today.md`, `plans/today.progress.md`
- Result: new plan prioritizes real-data robustness, product-readiness gates,
  V2 scorer calibration, shadow planner advice, guarded opt-in ranking, and
  product docs.
- Tests run: `git diff --check` passed.
- Next: implement Step 1, real-data normalization hardening.
- Blockers: none beyond the recorded full-bench crash.
