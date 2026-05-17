# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: shadow-to-gate transition scoring.
- Completed iterations for this reset: 3.
- Latest relevant commits:
  - `e65e38d` added the transition shadow outcome training surface.
  - `a85b258` documented and smoked the real shadow eval loop.
  - `f962018` closed the previous transition scoring queue.
  - `106e1ed` documented transition bench product modes.
  - `882f9c4` added guarded transition-scorer ranking.
  - `6cdd621` added shadow transition-scorer advice.
  - `6cd413e` calibrated transition action scorer V2.
  - `86ce6c2` added transition bench readiness gates.
  - `1859e9c` hardened transition bench normalization.
- Current blocker: V2 beats V1 on the full local candidate bench, but the
  held-out validation gate still underperforms existing rank order, so guarded
  opt-in remains blocked for normal local artifacts. V3 is now evaluation-only
  and must also pass held-out product gates before any guarded use.
- Next task: add a release-quality transition evidence bundle command.

## Active Task Queue

- [x] Recreate `plans/today.md` and `plans/today.progress.md`.
- [x] Add a shadow advice summary command.
- [x] Run and document a real shadow `eval` loop.
- [x] Normalize shadow advice plus candidate outcomes into a training surface.
- [x] Train/evaluate a held-out V3 scorer from shadow outcomes.
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
- Real shadow `eval` artifacts can be joined where advice exists by
  `task + phase + repair_plan_id`.

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
- Commit: `f4fdeb6` (`Add transition advice summary`).
- Push: pushed to `origin/main` (`f4fdeb6`).
- Next: run and document a real shadow `eval` loop.
- Blockers: none.

### Iteration 2: Run and document real shadow eval loop

- Worker: Worker 2.
- Goal: smoke `eval` with candidate outcomes and transition-scorer shadow
  advice enabled, document the command, and verify advice rows can be
  summarized and joined to candidate outcomes where possible.
- Files changed: `docs/TRANSITION_BENCH.md`, `evaluation/diagnostics.py`,
  `evaluation/runner.py`, `tests/test_cli.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_cli.py::test_eval_shadow_advice_can_join_candidate_outcomes tests/test_cli.py::test_eval_writes_candidate_outcomes_jsonl -q` passed.
  - `python cli.py eval --tasks examples/greenshot_bugs --candidate-outcomes /tmp/j3-shadow-candidate-outcomes.jsonl --transition-scorer-shadow --transition-advice-out /tmp/j3-shadow-transition-advice.jsonl --diagnostics /tmp/j3-shadow-diagnostics.json` passed.
  - `python cli.py summarize-transition-advice --advice /tmp/j3-shadow-transition-advice.jsonl --json` passed and wrote `/tmp/j3-shadow-transition-summary.json`.
  - `python -m json.tool /tmp/j3-shadow-diagnostics.json >/dev/null` passed.
  - `python -m json.tool /tmp/j3-shadow-transition-summary.json >/dev/null` passed.
  - `pytest tests/test_transition_scorer_advice.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `pytest tests/test_evaluation.py::test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate -q` passed.
- Result: documented the real shadow `eval` loop under `/tmp`; the smoke wrote
  5 candidate outcome rows and 5 advice rows. The advice summary reported 185
  total candidates, 5 advice rows, 3 known-validation rows, 3/5 scorer/top
  agreement, no known regressions, and zero hosted usage. Candidate outcomes
  now carry `repair_plan_id` when shadow advice exists, and ranked eval advice
  uses the same `ranked` phase label as candidate outcomes; all 5 smoke keys
  joined on `task + phase + repair_plan_id`.
- Commit: `a85b258` (`Document shadow eval loop`).
- Push: pushed to `origin/main` (`a85b258`).
- Next: normalize shadow advice plus candidate outcomes into a training
  surface.
- Blockers: none.

### Iteration 3: Normalize shadow advice plus candidate outcomes

- Worker: Worker 3.
- Goal: add a `transition-shadow-outcome-v1` training surface that joins
  `transition-scorer-advice-v1` rows with candidate outcome rows by
  `task + phase + repair_plan_id`, while preserving unjoined evidence with
  explicit reasons.
- Files changed: `j3/transition_shadow_outcomes.py`, `cli/parser.py`,
  `cli/handlers.py`, `cli/__init__.py`,
  `tests/test_transition_shadow_outcomes.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_transition_shadow_outcomes.py -q` passed.
  - `pytest tests/test_transition_scorer_advice.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `python cli.py eval --tasks examples/greenshot_3 --checkpoint runs/greenshot-1/model.json --timeout 10 --max-candidates 1 --candidate-outcomes /tmp/j3-worker3-shadow-candidate-outcomes.jsonl --transition-scorer-shadow --transition-advice-out /tmp/j3-worker3-shadow-transition-advice.jsonl --quiet` passed.
  - `python cli.py normalize-transition-shadow-outcomes --advice /tmp/j3-worker3-shadow-transition-advice.jsonl --candidate-outcomes /tmp/j3-worker3-shadow-candidate-outcomes.jsonl --out /tmp/j3-worker3-transition-shadow-outcomes.jsonl --json` passed and reported 4 joined rows, 4 known-validation rows, 4 same labels, and zero hosted usage.
  - `python - <<'PY' ... load_transition_shadow_outcomes([Path('/tmp/j3-worker3-transition-shadow-outcomes.jsonl')]) ... PY` passed and loaded 4 JSONL rows.
  - `python -m compileall -q j3/transition_shadow_outcomes.py tests/test_transition_shadow_outcomes.py cli/handlers.py cli/parser.py cli/__init__.py` passed.
  - `git diff --check` passed.
- Result: deterministic normalizer, writer, loader, validator, summary
  formatter, and `normalize-transition-shadow-outcomes` CLI are implemented.
  Joined rows carry repo/task identity, production selected candidate, scorer
  top candidate, candidate ranking, validation outcome, agreement and
  improve/regress/same labels, source traceability, and zero hosted usage
  fields. Advice-only and outcome-only groups are retained with explicit
  unjoined reasons.
- Commit: `e65e38d` (`Add transition shadow outcomes`).
- Push: pushed to `origin/main` (`e65e38d`).
- Next: train/evaluate a held-out V3 scorer from shadow outcomes.
- Blockers: none.

### Iteration 4: Train/evaluate held-out V3 scorer from shadow outcomes

- Worker: Worker 4.
- Goal: add evaluation-only `transition-action-future-scorer-v3` training and
  held-out reporting from `transition-shadow-outcome-v1` rows joined to
  action-choice groups, without making transition scoring default.
- Files changed: `j3/transition_action_scoring.py`, `cli/parser.py`,
  `cli/handlers.py`, `cli/__init__.py`,
  `tests/test_transition_shadow_scorer.py`, `plans/today.progress.md`.
- Tests run:
  - `pytest tests/test_transition_shadow_scorer.py -q` passed.
  - `pytest tests/test_transition_action_scoring.py tests/test_transition_shadow_outcomes.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `pytest tests/test_transition_bench_demo.py -q` passed.
  - `python -m compileall -q j3/transition_action_scoring.py cli/handlers.py cli/parser.py cli/__init__.py tests/test_transition_shadow_scorer.py` passed.
  - `python cli.py evaluate-transition-shadow-scorer --shadow-outcomes /tmp/j3-worker4-v3-smoke/transition-shadow-outcomes.jsonl --candidate-outcomes /tmp/j3-worker4-v3-smoke/candidate-outcomes.jsonl --split-by order --validation-fraction 0.34 --top-k 1 --embedding-dim 8 --epochs 6 --out /tmp/j3-worker4-v3-smoke/report.json --json` passed and reported a held-out V3 product gate plus zero hosted usage.
  - `python -m json.tool /tmp/j3-worker4-v3-smoke/report.json >/dev/null` passed.
  - `python cli.py demo-transition-bench --no-fixtures --embedding-dim 256 --top-k 3 --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl --out /tmp/j3-worker4-transition-bench-candidates-report.json` passed with the existing V2 held-out gate still `not_ready_underperforms_existing_rank_order`.
  - `python -m json.tool /tmp/j3-worker4-transition-bench-candidates-report.json >/dev/null` passed.
  - `git diff --check` passed.
- Result: added deterministic `evaluate-transition-shadow-scorer` CLI and V3
  report schema `transition-action-future-scorer-v3-report-v1`. The report
  trains a local pairwise V3 scorer from matched shadow outcomes and
  action-choice groups, supports held-out splits by task family, source file,
  repo, or order, compares V3 against V2, V1, existing rank order, stable
  lexical order, and deterministic random order, records the product gate, and
  preserves zero hosted token/context usage. Production rank features are
  excluded by default and available only through an explicit ablation flag.
  Patch/fix/eval defaults remain unchanged.
- Commit: `2f13892` (`Add held-out shadow V3 scorer`).
- Push: pending.
- Next: add a release-quality transition evidence bundle command.
- Blockers: none.
