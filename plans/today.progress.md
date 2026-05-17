# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: productize transition scoring without fooling ourselves.
- Completed iterations for this reset: 6.
- Latest relevant commits:
  - `106e1ed` documented transition bench product modes.
  - `882f9c4` added guarded, non-default transition-scorer ranking with product
    gate enforcement for patch/eval planning.
  - `6cdd621` added shadow transition-scorer advice for patch/eval planning.
  - `6cd413e` calibrates a V2 transition action scorer from candidate
    outcomes.
  - `86ce6c2` added transition bench product-readiness gates.
  - `26cca1d` removed the old today plan files.
  - `4cca638` documented transition bench reproduction.
  - `760c1fe` added the transition bench demo.
  - `534545d` added the transition action scorer.
  - `3eb9c38` added transition action-choice groups.
  - `d95ebc7` defined the transition bench schema.
  - `7e3df39` added transition asset inventory.
- Current blocker: V2 beats V1 on the full local candidate bench, but the
  held-out validation gate still underperforms existing rank order and is not
  ready for guarded opt-in.
- Next task: update product docs for demo, benchmark, shadow, and guarded
  modes.

## Active Task Queue

- [x] Harden real-data normalization for empty mined source rows.
- [x] Add product-readiness gates to transition bench reports.
- [x] Calibrate a V2 action scorer from candidate outcomes.
- [x] Add shadow transition-scorer advice to real patch/eval planning.
- [x] Add guarded, non-default opt-in ranking with gate enforcement.
- [x] Update product docs for demo, benchmark, shadow, and guarded modes.

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
  - product readiness gate:
    `not_ready_underperforms_existing_rank_order`
  - V1 future scorer residual count: 58
  - V2 calibrated future scorer pass@1: 78/88
  - V2 calibrated future scorer MRR: 0.925004919323
  - V2 held-out validation split: task_family, 60 train groups, 28 validation
    groups, gate `not_ready_underperforms_existing_rank_order`
  - zero hosted token/context usage
- full local bench with mined transitions used to fail with
  `ValueError: git_transition.after_source must be a non-empty string`; this
  is now fixed by structured skipped-row accounting.
- Empty `after_source` rows found:
  - `data/transitions/apache-python/Netflix__metaflow.jsonl` row 46
  - `data/transitions/apache-python/Netflix__metaflow.jsonl` row 47
  - `data/transitions/apache-python/treeverse__dvc.jsonl` row 46
- Full local bench now skips those three rows with structured skipped-row
  accounting and completes successfully.

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

### Iteration 1: Harden real-data normalization for empty mined source rows

- Worker: Codex Worker Iteration 1
- Goal: skip invalid mined git transition rows with empty `before_source` or
  `after_source`, report structured skipped-row details, and expose normalized
  and skipped counts by source kind in `demo-transition-bench`.
- Files changed: `j3/transition_bench.py`, `j3/transition_bench_demo.py`,
  `tests/test_transition_bench.py`, `tests/test_transition_bench_demo.py`,
  `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_transition_bench.py -q` passed, 5 tests.
  - `pytest tests/test_transition_bench_demo.py -q` passed, 4 tests.
  - `python cli.py demo-transition-bench --embedding-dim 256 --top-k 3 --mined-transitions data/transitions/apache-python/*.jsonl --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl --out /tmp/j3-transition-bench-local-report.json` passed with 2,485 normalized rows and 3 skipped rows.
  - `python -m json.tool /tmp/j3-transition-bench-local-report.json >/dev/null`
    passed.
- Result: mined git rows with empty sources are skipped instead of crashing;
  skipped rows include source path, row index, reason, repo, file path, and
  commit; demo reports input, normalized, and skipped counts by source kind.
- Commit: `1859e9c` (`Harden transition bench normalization`)
- Push: succeeded to `main` (`6c8eccf..1859e9c`)
- Next: add product-readiness gates to transition bench reports.
- Blockers: none for this slice; V1 future scorer still underperforms existing
  rank order.

### Iteration 2: Add product-readiness gates to transition bench reports

- Worker: Codex Worker Iteration 2
- Goal: add an honest `product_readiness` section to
  `transition-bench-demo-report-v1` comparing the V1 future scorer to existing
  rank order on solved groups.
- Files changed: `j3/transition_action_scoring.py`,
  `j3/transition_bench_demo.py`, `tests/test_transition_action_scoring.py`,
  `tests/test_transition_bench_demo.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_transition_action_scoring.py -q` passed, 8 tests.
  - `pytest tests/test_transition_bench_demo.py -q` passed, 4 tests.
  - `python cli.py demo-transition-bench --no-fixtures --embedding-dim 256 --top-k 3 --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl --out /tmp/j3-transition-bench-candidates-report.json` passed with product gate `not_ready_underperforms_existing_rank_order` and 58 residuals.
  - `python -m json.tool /tmp/j3-transition-bench-candidates-report.json >/dev/null`
    passed.
- Result: reports now include solved-group pass@1, top-k, MRR, average
  candidates validated before first pass, residual counts, and a gate result.
  The 88-group candidate bench remains blocked from guarded opt-in because V1
  underperforms existing rank order.
- Commit: `86ce6c2` (`Add transition bench readiness gates`)
- Push: succeeded to `main` (`b37a0a7..86ce6c2`)
- Next: calibrate a V2 action scorer from candidate outcomes.
- Blockers: none for this slice; the product gate correctly records the V1
  scorer as not ready for guarded opt-in.

### Iteration 3: Calibrate a V2 action scorer from candidate outcomes

- Worker: Codex Worker Iteration 3
- Goal: add an evaluation-only `transition-action-future-scorer-v2` calibrated
  from candidate outcome/action-choice groups and compare it with V1, existing
  rank order, stable lexical order, and deterministic random order.
- Files changed: `j3/transition_action_scoring.py`,
  `j3/transition_bench_demo.py`, `tests/test_transition_action_scoring.py`,
  `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_transition_action_scoring.py -q` passed, 10 tests.
  - `pytest tests/test_transition_bench_demo.py -q` passed, 4 tests.
  - `python cli.py demo-transition-bench --no-fixtures --embedding-dim 256 --top-k 3 --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl --out /tmp/j3-transition-bench-candidates-report.json` passed with V2 pass@1 `78/88`, V2 MRR `0.925004919323`, V1 pass@1 `30/88`, V1 MRR `0.510515059653`, and held-out V2 gate `not_ready_underperforms_existing_rank_order`.
  - `python -m json.tool /tmp/j3-transition-bench-candidates-report.json >/dev/null`
    passed.
- Result: V2 now fits deterministic pairwise weights from local features,
  supports task-family and source-file validation splits, persists calibration
  metadata/model/validation metrics inside the demo report, and remains
  evaluation-only. V2 beats V1 on the full local candidate bench, but held-out
  validation does not beat existing rank order, so guarded opt-in remains
  blocked.
- Commit: `6cd413e` (`Calibrate transition action scorer v2`)
- Push: succeeded to `main` (`646442a..6cd413e`)
- Next: add shadow transition-scorer advice to real patch/eval planning.
- Blockers: guarded opt-in remains blocked until a held-out scorer beats
  existing rank order.

### Iteration 4: Add shadow transition-scorer advice to real patch/eval planning

- Worker: Codex Worker Iteration 4
- Goal: add shadow-only transition scorer advice to real repair planning without
  changing candidate order, selected candidates, or production routing.
- Files changed: `j3/transition_scorer_advice.py`,
  `repair/patching/planner.py`, `repair/patching/types.py`, `cli/parser.py`,
  `cli/handlers.py`, `evaluation/runner.py`, `tests/test_patching.py`,
  `tests/test_cli.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_patching.py -q` passed, 93 tests.
  - `pytest tests/test_cli.py -q` passed, 43 tests.
  - `python cli.py patch --repo examples/greenshot_bug --test tests/test_calculator.py --transition-scorer-shadow --transition-advice-out /tmp/j3-transition-advice.jsonl` passed and wrote one `transition-scorer-advice-v1` JSONL row with 24 candidates and zero hosted usage fields.
  - `git diff --check` passed.
- Result: `patch` and `eval` accept `--transition-scorer-shadow` plus
  `--transition-advice-out`; the planner scores the already generated
  production-ordered candidate set in shadow mode, records selected/top scorer
  candidates, agreement, validation comparison, repo/task context, and zero
  hosted usage, and leaves routing unchanged.
- Commit: `6cdd621` (`Add shadow transition scorer advice`)
- Push: succeeded to `main` (`e814bab..6cdd621`)
- Next: add guarded, non-default opt-in ranking with gate enforcement.
- Blockers: guarded opt-in remains blocked until a held-out scorer beats
  existing rank order.

### Iteration 5: Add guarded opt-in ranking with gate enforcement

- Worker: Codex Worker Iteration 5
- Goal: add non-default transition-scorer ranking for `patch` and `eval`,
  require a scorer report or explicit experimental override, refuse failed
  product gates, preserve patch/fix defaults, and print the gate decision.
- Files changed: `j3/transition_ranking.py`,
  `j3/transition_scorer_advice.py`, `repair/patching/planner.py`,
  `repair/patching/types.py`, `cli/parser.py`, `cli/handlers.py`,
  `evaluation/runner.py`, `tests/test_patching.py`, `tests/test_fixing.py`,
  `tests/test_cli.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_patching.py -q` passed, 96 tests.
  - `pytest tests/test_fixing.py -q` passed, 3 tests.
  - `pytest tests/test_cli.py -q` passed, 46 tests.
  - `git diff --check` passed.
- Result: `patch` and `eval` now accept `--transition-scorer-rank` with either
  `--transition-scorer-report` or `--allow-experimental-ranking`; failed
  product gates refuse ranking before planning; successful opt-in prints the
  gate, report, and mode; default `patch` and `fix` behavior stays unchanged.
- Commit: `882f9c4` (`Add guarded transition ranking`)
- Push: succeeded to `main` (`c0ea575..882f9c4`)
- Next: update product docs for demo, benchmark, shadow, and guarded modes.
- Blockers: guarded opt-in remains blocked for normal local V2 artifacts until
  the held-out product gate beats existing rank order.

### Iteration 6: Update transition bench product docs

- Worker: Codex Worker Iteration 6
- Goal: document demo, benchmark, shadow, and guarded opt-in modes for the
  transition bench product path while keeping README unchanged.
- Files changed: `docs/TRANSITION_BENCH.md`, `plans/today.progress.md`.
- Tests run:
  - `git diff --check` passed.
- Result: `docs/TRANSITION_BENCH.md` now explains the four product modes,
  conservative default routing, skipped-row accounting, product-readiness
  gates, V2 calibration and held-out validation, shadow advice flags, guarded
  `--transition-scorer-rank` enforcement, and zero hosted usage.
- Commit: `106e1ed` (`Document transition bench product modes`)
- Push: succeeded to `main` (`8f0fa51..106e1ed`)
- Next: no queued task remains in `plans/today.progress.md`; watcher should
  choose the next slice from the current plan or refresh the plan.
- Blockers: none for this documentation slice; guarded opt-in remains blocked
  for normal local V2 artifacts until the held-out product gate beats existing
  rank order.
