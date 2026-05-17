# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: shadow suite and residual-driven readiness.
- Completed iterations for this reset: 0.
- Latest relevant commits:
  - `2664a95` documented shadow-to-gate evidence.
  - `a53b377` added transition evidence bundles.
  - `2f13892` added the held-out shadow V3 scorer.
  - `e65e38d` added transition shadow outcomes.
  - `a85b258` documented the real shadow eval loop.
  - `f4fdeb6` added transition advice summaries.
  - `f962018` closed the previous transition scoring queue.
- Current blocker: held-out V2/V3 product gates are still the product boundary.
  Guarded ranking must remain non-default and blocked unless evidence passes.
- Next task: add a repeatable shadow eval suite command or equivalent tested
  workflow that produces advice, shadow outcomes, V3 report, and evidence
  bundle in one run.

## Active Task Queue

- [x] Recreate `plans/today.md` and `plans/today.progress.md`.
- [ ] Add a repeatable shadow eval suite command.
- [ ] Add a V3/shadow residual report.
- [ ] Improve one scorer feature or action-choice metadata path from residuals.
- [ ] Run a narrow guarded trial only if held-out gates pass.
- [ ] Update evidence and product docs for the shadow suite.

## Current Facts

- The user deleted `plans/today.md` and `plans/today.progress.md`; they have
  been recreated with the next active slice rather than restored to the
  completed shadow-to-gate queue.
- The completed shadow-to-gate queue added:
  - `summarize-transition-advice`
  - `normalize-transition-shadow-outcomes`
  - `evaluate-transition-shadow-scorer`
  - `build-transition-evidence-bundle`
  - shadow advice for `patch` / `eval`
  - guarded, non-default transition ranking
  - product docs for the evidence loop
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
  - V2 validation gate:
    `not_ready_underperforms_existing_rank_order`
  - zero hosted token/context usage
- A local shadow `patch` smoke wrote advice rows and left default routing
  unchanged except for the normal example repair application; the verification
  side effect was restored before this plan was finalized.
- `summarize-transition-advice` over `/tmp/j3-transition-advice.jsonl` reports:
  - 2 advice rows
  - 48 total candidates
  - 0 scorer/production agreements
  - no known validation rows in that advice file
  - zero hosted token/context usage

## Checks Run During Plan Recreation

```bash
python cli.py inspect-transition-assets

python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json

python -m json.tool /tmp/j3-transition-bench-candidates-report.json >/dev/null

python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-transition-advice.jsonl

python cli.py summarize-transition-advice \
  --advice /tmp/j3-transition-advice.jsonl \
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

### Reset: Shadow suite and residual-driven readiness

- Worker: local planner
- Goal: recreate deleted `plans/today.md` and `plans/today.progress.md` with
  the next work after the completed shadow-to-gate queue.
- Files changed: `plans/today.md`, `plans/today.progress.md`
- Result: new plan prioritizes a repeatable shadow suite, residual reports,
  residual-driven scorer or feature improvements, and a narrow guarded trial
  only if held-out gates pass.
- Tests run: `git diff --check` passed.
- Next: implement Step 2, the repeatable shadow eval suite.
- Blockers: none beyond held-out gate readiness policy.

### Iteration 1: Repeatable shadow eval suite command

- Worker: Worker 1
- Goal: add `run-transition-shadow-suite` for active Step 2.
- Files changed: `j3/transition_shadow_suite.py`, `cli/parser.py`,
  `cli/handlers.py`, `cli/__init__.py`, `tests/test_transition_shadow_suite.py`,
  `tests/test_cli.py`, `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_transition_shadow_suite.py -q` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `python -m py_compile j3/transition_shadow_suite.py cli/handlers.py cli/parser.py cli/__init__.py` passed.
  - `python cli.py run-transition-shadow-suite --tasks examples/greenshot_bugs --out /tmp/j3-transition-shadow-suite` passed.
  - `python -m json.tool /tmp/j3-transition-shadow-suite/shadow-scorer-v3-report.json >/dev/null` passed.
  - `python -m json.tool /tmp/j3-transition-shadow-suite/evidence/manifest.json >/dev/null` passed.
  - `git diff --check` passed.
- Result: command writes candidate outcomes, transition advice, diagnostics,
  advice summary, normalized shadow outcomes, V3 held-out report, transition
  bench report, evidence bundle, and a suite manifest under the caller-provided
  output directory. The default checked-in task path `examples/greenshot_bugs`
  exists and is used.
- Commit: `0aae784` (`Add transition shadow suite command`).
- Push: succeeded to `main`.
- Next: add a V3/shadow residual report.
- Blockers: none.
