# Today Progress

This file is the live progress log for `plans/today.md`. Keep
`plans/strategy.md` stable. Track ordinary day-to-day progress here.

## Status

- Current phase: shadow suite and residual-driven readiness.
- Completed iterations for this reset: 3.
- Latest relevant commits:
  - `23f37ac` added the transition residual report.
  - `f9ed963` recorded shadow suite completion.
  - `0aae784` added the transition shadow suite command.
  - `2664a95` documented shadow-to-gate evidence.
  - `a53b377` added transition evidence bundles.
  - `2f13892` added the held-out shadow V3 scorer.
  - `e65e38d` added transition shadow outcomes.
  - `a85b258` documented the real shadow eval loop.
  - `f4fdeb6` added transition advice summaries.
  - `f962018` closed the previous transition scoring queue.
- Current blocker: held-out V2/V3 product gates are still the product boundary.
  Guarded ranking must remain non-default and blocked unless evidence passes.
- Next task: run a narrow guarded trial only if held-out gates pass.

## Active Task Queue

- [x] Recreate `plans/today.md` and `plans/today.progress.md`.
- [x] Add a repeatable shadow eval suite command.
- [x] Add a V3/shadow residual report.
- [x] Improve one scorer feature or action-choice metadata path from residuals.
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

### Iteration 2: V3/shadow residual report

- Worker: Worker 2
- Goal: add `report-transition-residuals` for active Step 3.
- Files changed: `j3/transition_residuals.py`, `cli/parser.py`,
  `cli/handlers.py`, `cli/__init__.py`, `tests/test_transition_residuals.py`,
  `tests/test_cli.py`, `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_transition_residuals.py -q` passed.
  - `python -m py_compile j3/transition_residuals.py cli/handlers.py cli/parser.py cli/__init__.py` passed.
  - `pytest tests/test_cli.py -q` passed.
  - `python cli.py report-transition-residuals --shadow-outcomes /tmp/j3-transition-shadow-suite/transition-shadow-outcomes.jsonl --shadow-scorer-report /tmp/j3-transition-shadow-suite/shadow-scorer-v3-report.json --candidate-outcomes /tmp/j3-transition-shadow-suite/candidate-outcomes.jsonl --json` passed.
  - `git diff --check` passed.
- Result: command consumes normalized shadow outcomes, the V3 shadow scorer
  report, and candidate outcomes; groups residuals by task family, action kind,
  source file, scorer/production top disagreement, missing feature evidence,
  and generation-vs-ranking gap; includes bounded exact candidate summaries and
  zero hosted usage fields.
- Commit: `23f37ac` (`Add transition residual report`).
- Push: succeeded to `main`.
- Next: improve one scorer feature or action-choice metadata path from the
  residual report.
- Blockers: none.

### Iteration 3: Candidate change-context scorer features

- Worker: Worker 3
- Goal: improve one scorer feature or action-choice metadata path from active
  Step 4 residual evidence.
- Residual family chosen: missing candidate-after delta/source-change evidence.
  The small shadow residual report had zero failures, but real candidate rows
  carried `diff_*`, `edit_*`, and `ast_delta_*` fields while action-choice
  groups dropped them and reported unavailable candidate-after embeddings.
- Files changed: `j3/transition_action_choice.py`,
  `j3/transition_action_scoring.py`, `tests/test_transition_action_scoring.py`,
  `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_transition_action_scoring.py -q` passed.
  - `pytest tests/test_transition_shadow_scorer.py -q` passed.
  - `python -m py_compile j3/transition_action_choice.py j3/transition_action_scoring.py` passed.
  - `python cli.py run-transition-shadow-suite --tasks examples/greenshot_bugs --out /tmp/j3-transition-shadow-suite-after` passed.
  - `python cli.py report-transition-residuals --shadow-outcomes /tmp/j3-transition-shadow-suite-after/transition-shadow-outcomes.jsonl --shadow-scorer-report /tmp/j3-transition-shadow-suite-after/shadow-scorer-v3-report.json --candidate-outcomes /tmp/j3-transition-shadow-suite-after/candidate-outcomes.jsonl --json` passed.
  - `git diff --check` passed.
- Result: action-choice candidates now retain bounded non-label
  `change_context` metadata from existing row-level diff/edit/AST delta fields.
  V3 scorer features now include scaled change metrics and capped AST added/
  removed feature indicators. Production rank remains an explicit ablation only.
  Before suite: V3 feature version `transition-action-shadow-features-v3`, 35
  learned features, gate `ready_for_shadow_mode`, pass@1 1/1. After suite: V3
  feature version `transition-action-shadow-features-v4`, 41 learned features
  including `change_ast_*`, gate `ready_for_shadow_mode`, pass@1 1/1.
- Commit: pending.
- Push: pending.
- Next: because the gate remains shadow-mode only and guarded opt-in is still
  not eligible, skip guarded production use and update evidence/docs or choose
  another residual-driven feature slice.
- Blockers: no failing residuals were exposed by the small checked-in shadow
  suite; the improvement is based on missing non-label metadata observed in the
  same candidate outcomes.
