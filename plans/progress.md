# j3 Progress Log

This is the persistent chronological progress log. Append concise entries after
meaningful work. Do not replace this file with a daily reset.

## 2026-05-18

### 2026-05-18 - OPS-001 - Persistent planning migration

- Owner: coordinator
- Files changed: `AGENTS.md`, `plans/operating-model.md`,
  `plans/backlog.md`, `plans/active.md`, `plans/progress.md`,
  `plans/today.md`, `plans/today.progress.md`
- Tests: `git diff --check` passed
- Result: replaced the old 24-hour `today.md` loop with a persistent
  coordinator/backlog/progress model. Added explicit rules for bounded parallel
  workers, coordinator reviews, disjoint write scopes, and evidence-led task
  selection.
- Commit: none
- Push: none
- Next: begin with `TRANS-001`, `GS7-001`, or `DATA-001` from the ready queue.
- Blockers: none

### 2026-05-18 - OPS-001 - Model selection policy

- Owner: coordinator
- Files changed: `AGENTS.md`, `plans/operating-model.md`,
  `plans/progress.md`
- Tests: `git diff --check` passed
- Result: documented that the coordinator should run at `xhigh`, default
  workers at `high`, mechanical workers at `medium`, and hard
  architecture/research workers at `xhigh`.
- Commit: none
- Push: none
- Next: commit the planning migration, then start the agent loop from fresh
  context.
- Blockers: none

### 2026-05-18 - GS7-001 - GreenShot-7 baseline refresh

- Owner: worker GS7-001
- Files changed: `plans/active.md`, `plans/progress.md`
- Tests: `pytest tests/test_request_spec.py -q` -> 6 passed;
  `pytest tests/test_greenfield_calculator.py -q` -> 6 passed;
  `pytest tests/test_greenshot_7.py -q` -> 1 passed;
  `python cli.py greenshot-7 --out /tmp/j3-gs7-001-baseline --record
  /tmp/j3-gs7-001-records.jsonl` -> 10 tasks, 8 built, 2 blocked, 8 validation
  passed, 0 validation failed, 10 records written;
  `python cli.py implement --prompt "make me a simple cli calc" --out
  /tmp/j3-calc-demo` -> built and validation passed after clearing a
  pre-existing generated `/tmp/j3-calc-demo`; `python
  /tmp/j3-calc-demo/calculator.py 2 + 3` -> `5`; `python -m pytest
  /tmp/j3-calc-demo/tests -q` -> 2 passed.
- Result: current GreenShot-7 request-to-repo baseline solves all supported
  calculator build fixtures. Passing tasks: `calculator_basic_etc`,
  `calculator_short_calc`, `calculator_add_only`, `calculator_operator_params`,
  `calculator_named_ops`, `calculator_symbol_example`, `calculator_aliases`,
  `calculator_ambiguous`. Blocked tasks: `math_tool_unclear` and
  `calculator_scientific_unclear`, both expected `ask_clarification` outcomes
  with `blocking_clarification` records. No missing action failures, ranking
  failures, prompt-spec mismatches, or generated pytest failures were visible in
  the current fixture run.
- Commit: abae85d80120304bf5126b328ae0ba3aa196e0ab
- Push: succeeded
- Next: use this as the baseline before `GS7-002`; new non-calculator fixtures
  should expose whether gaps are action coverage, prompt/spec parsing, or
  ranking rather than calculator generation.
- Blockers: none

### 2026-05-18 - TRANS-001 - Transition shadow matrix evidence

- Owner: worker TRANS-001
- Files changed: `plans/active.md`, `plans/progress.md`; generated artifacts
  under `/tmp/j3-trans-001-shadow-matrix`,
  `/tmp/j3-trans-001-matrix-evidence`,
  `/tmp/j3-trans-001-residual-report.json`, and
  `/tmp/j3-trans-001-guarded-decision.json`.
- Tests: `pytest tests/test_transition_shadow_matrix.py -q` -> 6 passed;
  `pytest tests/test_transition_residuals.py -q` -> 4 passed;
  `pytest tests/test_transition_evidence_bundle.py -q` -> 7 passed;
  `pytest tests/test_transition_guarded_trial.py -q` -> 4 passed.
- Commands: `python cli.py run-transition-shadow-matrix --matrix
  examples/transition_shadow_matrix.json --out
  /tmp/j3-trans-001-shadow-matrix --force --json`; `python -m json.tool
  /tmp/j3-trans-001-shadow-matrix/matrix-summary.json >/dev/null`; `shasum -a
  256 -c /tmp/j3-trans-001-shadow-matrix/evidence/checksums.sha256`;
  `python cli.py report-transition-residuals --matrix
  /tmp/j3-trans-001-shadow-matrix --out
  /tmp/j3-trans-001-residual-report.json --json`; `python cli.py
  build-transition-evidence-bundle --matrix
  /tmp/j3-trans-001-shadow-matrix --out
  /tmp/j3-trans-001-matrix-evidence --force --json`; `shasum -a 256 -c
  /tmp/j3-trans-001-matrix-evidence/checksums.sha256`; `python cli.py
  decide-transition-guarded-trial --matrix
  /tmp/j3-trans-001-shadow-matrix --out
  /tmp/j3-trans-001-guarded-decision.json --json`.
- Result: matrix summary is current and remains shadow-only. Totals: 5 suites,
  56 tasks, 55 ranked solved, 12,413 candidates, 19 held-out groups, 4 baseline
  residuals, 7 matrix residuals, zero hosted usage. Suite gates:
  `greenshot_bugs` and `greenshot_4` were `ready_for_shadow_mode`;
  `greenshot_3`, `greenshot_5_subset`, and `greenshot_6_subset` were
  `not_ready_underperforms_existing_rank_order`. Residual report found 14
  failures: 13 `scorer_ranking_gap` and 1 `candidate_generation_gap`.
  Evidence bundle checksums passed. Guarded-trial decision:
  `remain_shadow_only`, `eligible_for_guarded_opt_in_trial: false`; blockers
  are that all suite V3 gates must be `ready_for_guarded_opt_in` and matrix plus
  per-suite residual counts must be zero.
- Commit: 1a614fb415a007af9a83d55bb6d0904d51c3bbac
- Push: succeeded
- Next: start `TRANS-002` to diagnose the matrix blockers, prioritizing the 13
  scorer-ranking gaps in `greenshot_3`, `greenshot_5_subset`, and
  `greenshot_6_subset`, plus the one generation gap.
- Blockers: guarded transition ranking remains blocked by the recorded matrix
  gate; no workflow command blockers.
