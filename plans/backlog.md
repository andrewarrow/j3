# j3 Persistent Backlog

This backlog is not a 24-hour plan. It is the durable task inventory for moving
j3 from a repair prototype toward a serious local Python coding agent.

## Direction

Near-term realistic target:

- serious narrow Python authoring for CLIs, small libraries, tests, configs, and
  repo-local feature additions
- structured prompt/spec/action/outcome data
- hidden-like validation and subprocess checks
- retrieval, ranking, residual reports, and conservative gates

Long-term target:

- general GPT-5.5 xhigh-level Python coding without asking a hosted LLM to write
  candidate patches
- broad language/code pretraining, library familiarity, algorithm synthesis,
  flexible generation, long-horizon planning, and strong local validation

## Task Status Values

- `ready`: bounded enough for a worker
- `active`: assigned or in progress
- `blocked`: waiting on evidence, design, or dependency
- `done`: completed and recorded in `plans/progress.md`
- `parked`: intentionally deferred

## Workstream A: Coordination And Evidence Discipline

### OPS-001: Migrate from daily plans to persistent coordination

- Status: done
- Why: the old `today.md` loop created churn and erased useful continuity.
- Write scope: `AGENTS.md`, `plans/operating-model.md`, `plans/active.md`,
  `plans/backlog.md`, `plans/progress.md`, legacy `plans/today*` redirects.
- Acceptance: fresh agents know to use active/backlog/progress instead of daily
  plan files.
- Tests: `git diff --check` passed on 2026-05-18.

### OPS-002: Add a lightweight plan consistency check

- Status: done
- Why: stale task IDs and forgotten active entries will accumulate as parallel
  work grows.
- Write scope: a small checker command or test around `plans/active.md` and
  `plans/backlog.md`.
- Acceptance: focused test catches missing task IDs, invalid statuses, and
  active tasks not present in backlog, plus active/done drift between active
  board and backlog.
- Tests: `pytest tests/test_plan_consistency.py -q`; `git diff --check`.

### OPS-003: Make the coordinator loop continuous

- Status: done
- Why: the previous operating instructions allowed the coordinator to stop after
  review checkpoints even when ready work remained.
- Write scope: `AGENTS.md`, `plans/operating-model.md`, `plans/active.md`,
  `plans/progress.md`.
- Acceptance: instructions say reviews are checkpoints inside a continuous loop
  and the coordinator should dispatch the next ready tasks unless explicitly
  stopped or concretely blocked.
- Tests: `git diff --check`.

## Workstream B: GreenShot-7 Request-To-Repo

### GS7-001: Refresh current GreenShot-7 baseline

- Status: done
- Why: before adding tasks, confirm what the current request-to-repo runner can
  actually solve.
- Write scope: generated output under `/tmp`, progress notes only unless a small
  bug is found.
- Acceptance: recorded command output for current GreenShot-7 tasks, including
  pass/fail, missing action, and ranking or prompt-spec failures.
- Tests: `pytest tests/test_request_spec.py -q`,
  `pytest tests/test_greenfield_calculator.py -q`,
  `pytest tests/test_greenshot_7.py -q`, plus direct CLI smoke if available.

### GS7-002: Add five non-calculator request-to-repo fixtures

- Status: active
- Why: calculator-only success is too narrow for product evidence.
- Write scope: `examples/greenshot_7`, GreenShot-7 tests, focused request-spec
  fixtures.
- Acceptance: fixtures cover one small library, one parser, one tests-only task,
  one existing-repo convention task, and one clarification task.
- Tests: `pytest tests/test_greenshot_7.py -q`.

### GS7-003: Add structured greenfield library builders

- Status: ready
- Why: request-to-repo needs typed creation actions beyond calculator CLI files.
- Write scope: greenfield action planning/building modules and focused tests.
- Acceptance: can create a small module plus tests from a request spec without
  pasting arbitrary source blobs.
- Tests: focused greenfield tests and `pytest tests/test_greenshot_7.py -q`.

### GS7-004: Implement clarification as a first-class outcome

- Status: ready
- Why: Codex-like behavior requires asking when requirements are under-specified.
- Write scope: request spec parser/planner, GreenShot-7 clarification fixture,
  tests.
- Acceptance: ambiguous prompts produce a structured clarification action
  instead of editing files.
- Tests: `pytest tests/test_request_spec.py -q`,
  `pytest tests/test_greenshot_7.py -q`.

## Workstream C: Prompt Corpus And Intent Data

### DATA-001: Audit expanded prompt corpus quality

- Status: done
- Why: the current 320 rows are useful bootstrap data, not generalization proof.
- Write scope: prompt inspection command/report and progress notes.
- Acceptance: report counts by source type, split, task type, domain, ambiguity,
  inferred defaults, and synthetic template family; flag leakage risks.
- Tests: focused prompt corpus tests or CLI smoke.

### DATA-002: Add prompt/spec schema validation

- Status: done
- Why: learned prompt and transition models need stable fields.
- Write scope: request-spec schema docs, validator, tests.
- Acceptance: validates seed and expanded prompt rows with clear errors for
  missing fields, bad splits, and unsupported labels.
- Tests: focused schema tests.

### DATA-003: Prototype issue/PR mining manifest

- Status: done
- Why: serious intent data requires issue/PR text linked to accepted repo
  changes, not just commit diffs.
- Write scope: docs and a small mining/manifest prototype; no large generated
  artifacts committed.
- Acceptance: one Apache corpus repo can produce candidate issue/PR records with
  provenance, links, repo-before/repo-after refs, and license/terms notes.
- Tests: focused unit tests with fixture JSON.

### DATA-004: Normalize first 25 real prompt/repo transition examples

- Status: blocked
- Blocker: depends on reviewed real issue/PR export rows; DATA-003 provides the
  manifest prototype and DATA-002 provides schema validation.
- Why: trainable prompt understanding needs real user-like task text.
- Write scope: versioned local data file or external manifest; docs with
  provenance.
- Acceptance: 25 reviewed rows with stable splits and validation commands.
- Tests: schema validation and summary command.

## Workstream D: Transition Evidence And Guarded Product Gates

### TRANS-001: Run full transition shadow matrix

- Status: done
- Why: current evidence is smoke-scale and remains shadow-only.
- Write scope: generated outputs under `/tmp`, progress notes, small bug fixes
  only if the runner fails.
- Acceptance: matrix summary, residual report, evidence bundle, guarded-trial
  decision recorded with exact commands and gate result.
- Tests: matrix command, residual command, bundle command, guarded decision.

### TRANS-002: Diagnose matrix gate blockers

- Status: done
- Blocker: none; `TRANS-001` matrix evidence exists under `/tmp`.
- Why: next scorer/action work should follow residual evidence.
- Write scope: residual analysis docs, targeted tests, small fixes only if
  directly supported by residuals.
- Acceptance: grouped blockers labeled as missing generation, bad ranking,
  weak observation, or insufficient validation.
- Tests: relevant focused tests from the blocker area.

### TRANS-003: Expand standard matrix manifest cautiously

- Status: blocked
- Blocker: depends on targeted post-`ACT-002` evidence and remaining ranking
  residual fixes.
- Why: product gates need broader held-out suites without making local runs
  impractical.
- Write scope: `examples/transition_shadow_matrix.json`, tests, docs.
- Acceptance: manifest balances runtime, suite diversity, and held-out evidence.
- Tests: `pytest tests/test_transition_shadow_matrix.py -q`.

### TRANS-004: Rerun targeted matrix evidence after subscript-key fix

- Status: done
- Why: `ACT-002` fixed the single `TRANS-002` candidate-generation gap, but the
  matrix evidence still records the pre-fix residual count.
- Write scope: generated outputs under `/tmp`, progress notes only unless a
  local runner bug appears.
- Acceptance: rerun `greenshot_6_subset` with the standard matrix runner,
  record whether `http_no_store_directive_subscript_key` is solved within the
  matrix cap, and update residual/gate counts for that subset.
- Tests: targeted matrix command with `--only greenshot_6_subset`,
  `report-transition-residuals --matrix`, guarded decision if applicable, and
  focused transition tests if command behavior changes.

## Workstream E: Repo State, Actions, And Models

### REPO-001: Summarize repo-state encoder coverage

- Status: ready
- Why: greenfield and transition planning need explicit repo representation.
- Write scope: repo encoder docs/tests or a small inspection command.
- Acceptance: reports files, packages, imports, functions/classes, tests,
  configs, entrypoints, and docs for a fixture repo.
- Tests: focused repo-state tests.

### ACT-001: Create action coverage map from residuals

- Status: ready
- Why: action expansion should be evidence-led.
- Write scope: docs or command that maps tasks/residuals to supported and
  missing structured actions.
- Acceptance: shows which failures need new actions versus better ranking.
- Tests: focused tests with small residual fixtures.

### ACT-002: Fix subscript-key generation gap from matrix residuals

- Status: done
- Why: `TRANS-002` found one candidate-generation gap:
  `greenshot_6_subset/http_no_store_directive_subscript_key` needs the
  `change_subscript_key` candidate from `"no-store"` to `"no_store"` to enter
  the tested evidence set.
- Write scope: repair patching candidate generation/ranking around subscript
  keys and focused tests.
- Acceptance: the focused GreenShot-6 task produces and validates a passing
  `change_subscript_key` candidate within the configured candidate cap, without
  regressing existing candidate ranking tests.
- Tests: focused patching/candidate ranking tests plus the single GreenShot-6
  task smoke.

### MODEL-001: Re-evaluate learned prompt intent baseline

- Status: ready
- Why: prompt-intent progress needs held-out domain evidence and residuals.
- Write scope: model/eval commands and focused tests, not broad architecture.
- Acceptance: report exact-field accuracy, ambiguity accuracy, inferred-default
  precision/recall, and residual groups on current prompt corpus.
- Tests: prompt intent eval tests or CLI smoke.

### MODEL-002: Start new scorer/model work only after evidence review

- Status: blocked
- Blocker: depends on TRANS-001/TRANS-002 and GS7 baseline evidence.
- Why: new scorer versions should respond to concrete residuals.
- Write scope: TBD after review.
- Acceptance: TBD after review.
- Tests: TBD after review.

## Workstream F: Long-Term Training Scale

### SCALE-001: Draft local pretraining feasibility inventory

- Status: ready
- Why: the frontier target needs a sober estimate of data, compute, objectives,
  and model shapes.
- Write scope: focused doc under `docs/`, with links to current local data
  sources.
- Acceptance: separates near-term local encoders from frontier-scale
  language/code pretraining; lists what data exists and what is missing.
- Tests: `git diff --check`.

### SCALE-002: Define data provenance and release policy

- Status: ready
- Why: larger corpora need license, terms, split, and checksum discipline.
- Write scope: `docs/TRAINING.md` or a focused companion doc.
- Acceptance: policy covers local scratch corpora, checked-in examples, release
  archives, synthetic rows, issue/PR mining, and generated artifacts.
- Tests: `git diff --check`.

## Next Recommended Queue

Start with these unless fresh evidence changes the order:

1. `GS7-002`: add five non-calculator request-to-repo fixtures.
2. `REPO-001`: summarize repo-state encoder coverage.
3. `ACT-001`: create action coverage map from residuals.
4. `MODEL-001`: re-evaluate learned prompt intent baseline.
5. Coordinator review: choose between GreenShot-7 fixture expansion, scorer
   ranking work, reviewed issue/PR normalization, or broader data provenance
   work based on the targeted rerun and schema validation.
