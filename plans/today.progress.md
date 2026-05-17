# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: shadow-to-gate transition scoring.
- Completed iterations for this reset: 1.
- Latest relevant commits:
  - `f962018` closed the previous transition scoring queue.
  - `106e1ed` documented transition bench product modes.
  - `882f9c4` added guarded transition-scorer ranking.
  - `6cdd621` added shadow transition-scorer advice.
  - `6cd413e` calibrated transition action scorer V2.
  - `86ce6c2` added transition bench readiness gates.
  - `1859e9c` hardened transition bench normalization.
- Current blocker: V2 beats V1 on the full local candidate bench, but the
  held-out validation gate still underperforms existing rank order, so guarded
  opt-in remains blocked for normal local artifacts.
- Next task: run and document a real shadow `eval` loop.

## Active Task Queue

- [x] Recreate `plans/today.md` and `plans/today.progress.md`.
- [x] Add a shadow advice summary command.
- [ ] Run and document a real shadow `eval` loop.
- [ ] Normalize shadow advice plus candidate outcomes into a training surface.
- [ ] Train/evaluate a held-out V3 scorer from shadow outcomes.
- [ ] Add a release-quality transition evidence bundle command.
- [ ] Update product docs for shadow-to-gate evidence.

## Current Facts

- The user deleted `plans/today.md` and `plans/today.progress.md`; they have
  been recreated with the next active slice rather than restored to the
  completed queue.
- `inspect-transition-assets` runs locally and reports:
  - prompt corpus present with 320 rows
  - mined git transitions: 31 files, 1,842 rows
  - candidate outcomes: 2 files, 642 rows
  - prototype models: 1 file
- candidate-only local bench runs:
  - 642 transition bench rows
  - 88 action-choice groups
  - 642 candidates
  - V1 pass@1: 30/88
  - V2 pass@1: 78/88
  - existing-rank-order pass@1: 65/88
  - V2 held-out validation gate:
    `not_ready_underperforms_existing_rank_order`
  - zero hosted token/context usage
- full local bench with mined transitions runs:
  - 2,485 normalized transition bench rows
  - 3 skipped mined source rows
  - 89 action-choice groups
  - 644 candidates
  - V1 pass@1: 31/89
  - V2 pass@1: 81/89
  - existing-rank-order pass@1: 65/89
  - V2 held-out validation gate:
    `not_ready_underperforms_existing_rank_order`
  - zero hosted token/context usage
- `patch` and `eval` support shadow advice and guarded ranking flags, but
  default routing remains unchanged.

## Checks Run During Plan Recreation

```bash
python cli.py inspect-transition-assets

python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json

python cli.py demo-transition-bench \
  --embedding-dim 256 \
  --top-k 3 \
  --mined-transitions data/transitions/apache-python/*.jsonl \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-report.json

python -m json.tool /tmp/j3-transition-bench-candidates-report.json >/dev/null
python -m json.tool /tmp/j3-transition-bench-local-report.json >/dev/null
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

### Reset: Shadow-to-gate transition scoring

- Worker: local planner
- Goal: recreate deleted `plans/today.md` and `plans/today.progress.md` with
  the next work after the completed productization queue.
- Files changed: `plans/today.md`, `plans/today.progress.md`
- Result: new plan prioritizes shadow advice summarization, real shadow eval
  data, joined shadow outcomes, held-out V3 scorer work, evidence bundles, and
  product docs. Defaults remain conservative until held-out gates pass.
- Tests run: `git diff --check` passed.
- Next: implement Step 2, the shadow advice summary command.
- Blockers: none beyond the held-out V2 gate failure recorded above.

### Iteration 1: Add shadow advice summary command

- Worker: Worker 1.
- Goal: add `summarize-transition-advice` for one or more
  `transition-scorer-advice-v1` JSONL files with human and `--json` output.
- Files changed: `j3/transition_scorer_advice.py`, `cli/parser.py`,
  `cli/handlers.py`, `cli/__init__.py`, `tests/test_cli.py`,
  `tests/test_transition_scorer_advice.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_transition_scorer_advice.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `python cli.py patch --repo examples/greenshot_bug --test tests/test_calculator.py --transition-scorer-shadow --transition-advice-out /tmp/j3-transition-advice.jsonl` passed and wrote one advice row; the verification-applied example repair was restored afterward.
  - `python cli.py summarize-transition-advice --advice /tmp/j3-transition-advice.jsonl --json` passed and reported one advice row, 24 candidates, and zero hosted token/context usage.
  - `git diff --check` passed.
- Result: summary schema `transition-scorer-advice-summary-v1` reports row
  count, total candidates, scorer/production agreement, known
  improve/regress/no-change counts, production-selected and scorer-top
  pass@1, average candidates saved/lost when validation is known, and zero
  hosted usage totals.
- Commit: pending in this worker iteration.
- Push: pending in this worker iteration.
- Next: run and document a real shadow `eval` loop.
- Blockers: none.
