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

- Status: done
- Why: calculator-only success is too narrow for product evidence.
- Write scope: `examples/greenshot_7`, GreenShot-7 tests, focused request-spec
  fixtures.
- Acceptance: fixtures cover one small library, one parser, one tests-only task,
  one existing-repo convention task, and one clarification task.
- Tests: `pytest tests/test_greenshot_7.py -q`.

### GS7-003: Add structured greenfield library builders

- Status: done
- Why: request-to-repo needs typed creation actions beyond calculator CLI files.
- Write scope: greenfield action planning/building modules and focused tests.
- Acceptance: can create a small module plus tests from a request spec without
  pasting arbitrary source blobs.
- Tests: focused greenfield tests and `pytest tests/test_greenshot_7.py -q`.
- Completion note: satisfied by `GS7-002` and the coordinator `implement` CLI
  integration fix, which added bounded slugify and key/value parser builders
  plus public CLI validation for non-calculator library creation.

### GS7-004: Implement clarification as a first-class outcome

- Status: done
- Why: Codex-like behavior requires asking when requirements are under-specified.
- Write scope: request spec parser/planner, GreenShot-7 clarification fixture,
  tests.
- Acceptance: ambiguous prompts produce a structured clarification action
  instead of editing files.
- Tests: `pytest tests/test_request_spec.py -q`,
  `pytest tests/test_greenshot_7.py -q`.

### GS7-005: Add tests-only existing-repo support for one-file libraries

- Status: done
- Why: `ACT-001` classified `slugify_tests_only_existing` as a request-to-repo
  action coverage gap, not a repair ranking problem.
- Write scope: existing-repo request planning/building for tests-only library
  support, fixtures, focused tests, and docs if needed.
- Acceptance: can inspect a one-file existing library, create a pytest file
  without changing implementation, validate it, and record a structured
  request-to-repo outcome.
- Tests: focused existing-repo/GreenShot tests and `git diff --check`.
- Completion note: added a tests-only slugify planner/materializer and
  structured outcome row. The GreenShot-7 fixture now validates by writing
  only `tests/test_slugify.py` while keeping `slugify.py` byte-for-byte
  unchanged.

### GS7-006: Add repo-state-aware library convention edits

- Status: done
- Why: `slugify_existing_src_convention` needs repo-state-aware planning for
  package layout and exports after `REPO-001` made repo coverage inspectable.
- Write scope: repo-state-driven existing-repo planning for a small library
  convention fixture, focused tests, and docs if needed.
- Acceptance: can plan and validate a minimal `src/` package export edit using
  repo-state coverage instead of hard-coded calculator assumptions.
- Tests: focused repo-state/existing-repo/GreenShot tests and
  `git diff --check`.
- Completion note: added a narrow src-package convention planner/materializer
  for the `slugify_existing_src_convention` fixture. It validates repo-state
  coverage for `src/acme_slug`, edits only `src/acme_slug/__init__.py`, protects
  `src/acme_slug/text.py`, runs targeted pytest, and records the repo-state
  evidence and source-edit scope in a structured outcome row.

### GS7-007: Generic real-repo tests-only planner

- Status: done
- Why: `REAL-003` scored `pass@3 = 0/4` because the current tests-only builder
  only supports a root `slugify.py` fixture and cannot target real package/test
  layouts.
- Write scope: a focused real-repo tests-only planner module/tests, optional
  integration with local knowledge records, and plan updates.
- Acceptance: for the `iniconfig-tests-parse-comments` calibration task, inspect
  repo-state and local knowledge to select `testing/test_iniconfig.py`,
  preserve production files, emit a structured tests-only candidate/action
  record with target test file, import style evidence, validation command,
  mutation scope, residual labels, and knowledge citations where available. If
  behavior-specific pytest case materialization is not ready, emit that exact
  blocker instead of pretending the task passes.
- Tests: focused planner tests, plan consistency, and `git diff --check`.
- Completion note: added a generic non-mutating planner/candidate record for
  the calibration `iniconfig-tests-parse-comments` task. It consumes repo-state
  coverage and local knowledge records to select `testing/test_iniconfig.py`,
  records import-style evidence, validation command, mutation scope, protected
  production hashes, residual labels, and knowledge citations, then blocks
  honestly on `test_case_materialization_gap` because behavior-specific pytest
  case materialization is not implemented yet.

### GS7-008: Materialize real-repo pytest cases for iniconfig

- Status: done
- Why: `GS7-007` selected the correct test file and import style but stopped at
  `test_case_materialization_gap`; the next proof is whether j3 can materialize
  concrete pytest cases for a real repo calibration task.
- Write scope: `j3/real_repo_tests_planner.py`,
  `tests/test_real_repo_tests_planner.py`, optional generated outputs under
  `/tmp`, and plan updates.
- Acceptance: materialize behavior-specific pytest cases into
  `testing/test_iniconfig.py` for comment-only lines, inline section comments,
  and duplicate keys; preserve production files; emit candidate-after mutation
  scope, validation command, knowledge citations, and residual labels. If the
  live pinned repo reveals incompatible APIs, record that exact blocker instead
  of claiming a pass.
- Tests: focused planner/materializer tests, plan consistency, and
  `git diff --check`.
- Completion note: added narrow materialization for the calibration
  `iniconfig-tests-parse-comments` task. The planner appends pytest cases for
  comment-only lines, inline section comments, and duplicate key error
  reporting to `testing/test_iniconfig.py`, records candidate-after diff/hash
  metadata plus actual mutation scope, preserves production file hashes, cites
  local knowledge, and leaves validation as an explicit deferred residual until
  the selected command is run. A live cloned pinned checkout passed
  `python -m pytest testing/test_iniconfig.py -q` with `54 passed in 0.03s`.

### GS7-009: Materialize first held-out tests-only candidate for h11

- Status: done
- Why: the iniconfig candidate is calibration evidence only. The next proof is
  whether the same planner/action surface can handle a held-out repo without
  repo-name shortcuts or fixture-shaped assumptions.
- Write scope: `j3/real_repo_tests_planner.py`,
  `tests/test_real_repo_tests_planner.py`, optional generated outputs under
  `/tmp`, and plan updates.
- Acceptance: for `h11-tests-bytesify-memoryview`, select
  `h11/tests/test_util.py` from repo-state and local-knowledge evidence;
  materialize pytest coverage for bytearray, memoryview, ASCII str, non-ASCII
  str, and int TypeError behavior; preserve production files; emit
  candidate-after, mutation-scope, validation-command, residual, and
  knowledge-use metadata; and live-validate the pinned `h11` checkout if setup
  succeeds. If the held-out repo exposes a materialization, API, or validation
  blocker, record the exact blocker instead of broadening scope silently.
- Tests: focused planner/materializer tests,
  `pytest tests/test_plan_consistency.py -q`, `git diff --check`, and a live
  `python -m pytest h11/tests/test_util.py -q` candidate check when available.
- Completion note: added the first held-out tests-only materializer for
  `h11-tests-bytesify-memoryview`. The planner selects
  `h11/tests/test_util.py` from repo-state plus manifest/local-knowledge
  evidence, appends pytest coverage for bytearray, memoryview, ASCII str,
  non-ASCII str, and int TypeError behavior, preserves production hashes, and
  emits candidate-after, mutation-scope, validation-command, residual, and
  knowledge-use metadata. Live validation against the pinned h11 checkout
  passed with `11 passed in 0.02s`, changing only `h11/tests/test_util.py`.

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

- Status: done
- Why: trainable prompt understanding needs real user-like task text.
- Write scope: versioned local data file or external manifest; docs with
  provenance.
- Acceptance: mini replay of 10 real issue/PR examples with prompt text,
  repo_before ref, accepted diff or PR ref, validation command when available,
  provenance/license notes, stable split, and initial residual labels. The goal
  is to see what breaks first, not to solve all 10.
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

- Status: done
- Why: greenfield and transition planning need explicit repo representation.
- Write scope: repo encoder docs/tests or a small inspection command.
- Acceptance: reports files, packages, imports, functions/classes, tests,
  configs, entrypoints, and docs for a fixture repo.
- Tests: focused repo-state tests.

### ACT-001: Create action coverage map from residuals

- Status: done
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

- Status: done
- Why: prompt-intent progress needs held-out domain evidence and residuals.
- Write scope: model/eval commands and focused tests, not broad architecture.
- Acceptance: report exact-field accuracy, ambiguity accuracy, inferred-default
  precision/recall, and residual groups on current prompt corpus.
- Tests: prompt intent eval tests or CLI smoke.

### MODEL-002: Start new scorer/model work only after evidence review

- Status: parked
- Blocker: superseded by bounded subtasks `MODEL-003` through `MODEL-006`
  based on `docs/ACTION_COVERAGE_MAP.md`.
- Why: new scorer versions should respond to concrete residuals.
- Write scope: TBD after review.
- Acceptance: TBD after review.
- Tests: TBD after review.

### MODEL-003: Penalize add-keyword decoys

- Status: ready
- Why: `ACT-001` and `TRANS-002` show unvalidated `add_keyword_arg` candidates
  outranking passing candidates in several residual clusters.
- Write scope: transition scorer fixtures/features/tests for add-keyword
  decoy ranking only.
- Acceptance: focused residual fixtures reduce false priority for unvalidated
  `add_keyword_arg` candidates unless failure hints name a missing keyword path.
- Tests: focused transition action scoring/ranking tests.

### MODEL-004: Distinguish mapping key and value targets

- Status: ready
- Why: remaining residuals confuse mapping key mutation with value mutation
  despite existing structured actions.
- Write scope: transition scorer fixtures/features/tests for mapping
  key/value target evidence only.
- Acceptance: scorer evidence distinguishes `change_dict_key`,
  `change_dict_value`, `add_dict_key`, and `change_subscript_key` when the same
  mapping appears in competing candidates.
- Tests: focused transition action scoring/ranking tests.

### MODEL-005: Improve boundary and literal action ranking

- Status: ready
- Why: transition residuals still include boundary/literal and module-constant
  candidates where equivalent-looking edits outrank the passing action family.
- Write scope: transition scorer fixtures/features/tests for boundary/literal
  action-family and file/symbol alignment.
- Acceptance: focused residual fixtures improve ranking for boundary/literal
  examples without adding new repair action kinds.
- Tests: focused transition action scoring/ranking tests.

### MODEL-006: Add candidate-after or AST-delta observation

- Status: ready
- Why: identifier, attribute, signature, and wrapper residuals need evidence
  that a candidate changes the failing behavior rather than a nearby name or
  import.
- Write scope: candidate observation/scorer feature prototype and focused
  residual tests.
- Acceptance: scorer inputs expose candidate-after or AST-delta signals for
  the residual families without enabling production ranking by default.
- Tests: focused transition action scoring/ranking tests.

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

## Workstream G: Hard Feasibility Proofs

### REAL-001: Real repo eval ladder spike

- Status: done
- Why: the project must prove it generalizes outside j3-owned fixtures before
  optimizing more GreenShot progress.
- Write scope: `docs/REAL_REPO_EVAL_LADDER.md`, a small real-repo eval
  manifest under `examples/` if useful, optional checker/tests, and plan
  updates.
- Acceptance: pick 3 to 5 small permissively licensed Python repos with stable
  tests; define tests-only and one-file feature tasks; record checkout refs,
  validation commands, task split rules, runtime limits, pass/fail metrics, and
  first expected failure modes. No implementation heroics.
- Tests: plan consistency, focused manifest/checker tests if code is added, and
  `git diff --check`.

### MAT-001: Code materialization audit

- Status: done
- Why: the biggest technical gap is turning predicted repo-after intent into
  actual source when current structured actions are insufficient.
- Write scope: `docs/CODE_MATERIALIZATION_GAP.md`, optional small
  materialization classification fixture/checker, and plan updates.
- Acceptance: classify 25 real accepted Python PR diffs as expressible by
  current structured actions, a general typed builder, a repo-convention
  builder, a constrained local generator, or not currently expressible; include
  counts and the smallest executable probe that would reduce the biggest gap.
- Tests: plan consistency, focused checker tests if code is added, and
  `git diff --check`.

### MAT-002: Constrained source-region materialization probe

- Status: done
- Why: `MAT-001` found that the largest normal-PR bucket is bounded local source
  generation, not one-line structured repair or full architectural work.
- Write scope: `j3/source_region_materializer.py`,
  `tests/test_source_region_materializer.py`, optional docs under `docs/`, and
  plan updates.
- Acceptance: add an executable materialization probe that replaces a bounded
  region inside one named function while enforcing AST parsing, signature
  preservation, changed-line budget, default no-import-change constraints, and
  candidate-after diff metadata. Include a fixture shaped like the
  `psf/requests#7427` `should_bypass_proxies` domain-boundary edit so the probe
  directly tests the biggest `MAT-001` gap.
- Tests: focused source-region tests, plan consistency, and `git diff --check`.

### MAT-003: Real one-file feature materialization probe

- Status: ready
- Why: tests-only wins do not answer the biggest `MAT-001` gap: turning a
  predicted repo-after behavior into bounded source edits for a real Python
  library.
- Write scope: a focused source materialization probe for one real
  one-file-feature ladder task, focused tests, optional docs, and plan updates.
- Acceptance: attempt one pinned real-repo one-file feature task with a bounded
  source-region or typed-builder action; preserve the maximum-production-file
  constraint; record candidate-after diff/AST metadata, validation result,
  runtime, and the first blocker if the edit cannot be expressed.
- Tests: focused materializer tests, plan consistency, `git diff --check`, and
  a live targeted validation command when the candidate is materialized.

### KNOW-001: Local knowledge inventory for the wedge

- Status: done
- Why: j3 needs pytest, packaging, small-library, and convention knowledge as
  local data rather than frontier-LLM runtime intuition.
- Write scope: focused doc under `docs/`, optional small source inventory
  manifest, and plan updates.
- Acceptance: choose the wedge knowledge scope, list required concepts, map
  each to candidate sources such as docs, READMEs, issue/PRs, tests, and
  outcomes, and define how each becomes data instead of hardcoded rules.
- Tests: plan consistency and `git diff --check`.

### KNOW-002: Extract first wedge knowledge records

- Status: done
- Why: `KNOW-001` defined the local knowledge shape, but the product wedge
  needs pytest, packaging, import, and validation records that builders can
  cite instead of hardcoded assumptions.
- Write scope: a small extractor or manifest for calibration repo knowledge
  records, focused tests, docs if needed, and plan updates.
- Acceptance: emit compact JSONL records for test layout, package layout,
  public imports, validation recipe, and at least one pytest pattern from a
  calibration repo, with provenance hashes, split labels, and an example
  knowledge-use link suitable for tests-only planning.
- Tests: focused extractor or schema tests, plan consistency, and
  `git diff --check`.

### KNOW-003: Wire knowledge-use attribution into tests-only planning

- Status: ready
- Why: `KNOW-002` created citeable records, but wedge candidates must record
  whether they actually used layout, import, and validation knowledge.
- Write scope: tests-only planning/outcome attribution, focused tests, and plan
  updates.
- Acceptance: tests-only candidate/outcome rows cite retrieved knowledge record
  ids by purpose, and missing citations produce a machine-readable
  `knowledge_not_used` or `missing_knowledge` residual rather than prose only.
- Tests: focused existing-repo/local-knowledge tests, plan consistency, and
  `git diff --check`.

### WEDGE-001: Product wedge decision

- Status: done
- Why: the first usable product must be narrower than "Codex replacement" and
  must force the hard repo understanding, validation, and materialization work.
- Write scope: focused product decision doc and plan updates.
- Acceptance: choose the first product path, likely tests-only edits plus
  conservative small-library maintenance; define user promise, non-goals,
  guarded rollout gates, and failure criteria for pivoting.
- Tests: plan consistency and `git diff --check`.

### REAL-002: Real repo eval ladder preflight runner

- Status: done
- Why: `REAL-001` is only a contract until a runner proves pinned repos can be
  checked out and validated cheaply.
- Write scope: real-repo ladder runner code, focused tests, docs if needed, and
  plan updates.
- Acceptance: clone or materialize one pinned repo to `/tmp`, run setup and
  baseline validation with timeouts, enforce allowed write paths for a dummy
  candidate, and emit JSONL outcome rows with environment versus agent failure
  labels.
- Tests: focused runner tests with mocked subprocess or a tiny local fixture,
  plan consistency, and `git diff --check`.

### REAL-003: Run first tests-only wedge shadow score

- Status: done
- Why: the wedge should move to guarded opt-in only after held-out real-repo
  shadow scoring proves tests-only generalization, validation runtime, and
  hidden-like agreement.
- Write scope: eval command/report docs, generated outputs under `/tmp`, small
  harness fixes only if directly required, and plan updates.
- Acceptance: run the tests-only tasks from the real-repo ladder with max three
  candidates, record `pass@1`, `pass@3`, first passing rank, runtime, mutation
  scope, hidden-like agreement, residual labels, zero hosted usage, and a
  gate decision against `docs/PRODUCT_WEDGE_DECISION.md`.
- Tests: shadow-score command, plan consistency, and `git diff --check`.
- Completion note: first shadow score recorded `pass@1 = 0/4`,
  `pass@3 = 0/4`, no generated candidates, no first passing ranks, hidden-like
  checks not run, zero hosted usage, and `remain_shadow_only`. The current
  tests-only builder cannot target the real-repo ladder beyond the one-file
  `slugify.py` fixture shape, so generic repo-state test placement and pytest
  authoring is the next repair target.

### REAL-004: Live real-repo baseline preflight

- Status: done
- Why: `REAL-002` proved orchestration with mocked command runners, but cheap
  validation is not trustworthy until at least one pinned repo is checked out
  and baseline-validated for real.
- Write scope: real-repo preflight CLI/subset support if needed, a compact
  report under `docs/`, generated output under `/tmp`, focused tests, and plan
  updates.
- Acceptance: run the preflight against `iniconfig` from
  `examples/real_repo_eval_ladder.json`, record checkout/setup/baseline command
  results, runtime, network policy, and blocker label. If live validation
  fails, classify it as environment, setup, or validation instead of an agent
  failure.
- Tests: focused preflight tests, plan consistency, and `git diff --check`.
- Completion note: live `iniconfig` preflight passed from a pinned checkout at
  `77db208ab4ae0cd2061d909fe222a1db72867850`. The run emitted 2 task rows to
  `/tmp/j3-real-004-live-preflight/outcomes.jsonl`, recorded checkout, setup,
  baseline validation, network policy, runtime 3.119 seconds, and
  `blocker_label = none`. Full Gate A still requires at least three baseline
  repositories to pass.

### REAL-005: Extend live baseline preflight toward Gate A

- Status: done
- Why: `REAL-004` proved one calibration repo only; Gate A requires at least
  three repositories passing baseline validation before real-repo scoring is
  trustworthy.
- Write scope: compact report under `docs/`, generated output under `/tmp`,
  small preflight runner fixes only if directly required, focused tests if code
  changes, and plan updates.
- Acceptance: run live preflight for at least two of `h11`, `humanize`, and
  `boltons`; record checkout/setup/baseline command results, runtime, network
  policy, blocker labels, and whether Gate A has enough passing repos when
  combined with `REAL-004`. Classify failures as environment, setup, or
  validation, not agent failures.
- Tests: live command/report smoke, plan consistency, and `git diff --check`.
- Completion note: live `h11` and `humanize` preflight passed from pinned
  checkouts. The run emitted 4 task rows to
  `/tmp/j3-real-005-gate-a-preflight/outcomes.jsonl`, recorded checkout, setup,
  baseline validation, network policy, runtime 8.047 seconds, and
  `blocker_label = none`. Combined with `REAL-004` `iniconfig`, Gate A now has
  three baseline-passing repositories.

### REAL-006: Rerun tests-only shadow score with candidate materialization

- Status: active
- Why: `REAL-003` scored `pass@3 = 0/4` before `GS7-008` could materialize a
  real-repo candidate. The next gate decision must measure the candidate
  surface directly, not infer progress from a standalone live check.
- Write scope: `j3/real_repo_shadow_score.py`,
  `tests/test_real_repo_shadow_score.py`, one compact `docs/REAL_006_*.md`
  report if useful, generated outputs under `/tmp`, and plan updates.
- Acceptance: rerun the tests-only shadow score so the `iniconfig` calibration
  task receives a scored materialized candidate while unsupported held-out
  repos remain explicit residuals; record pass@1, pass@3, first passing rank,
  candidate validation status, runtime, mutation scope, hidden-like agreement,
  residual labels, zero hosted usage, and the guarded-use gate decision.
- Tests: `pytest tests/test_real_repo_shadow_score.py -q`,
  `pytest tests/test_plan_consistency.py -q`, `git diff --check`, and the
  shadow-score command/report smoke.

### REAL-007: Held-out tests-only score after first h11 materializer

- Status: ready
- Why: once `GS7-009` either passes or fails, the evidence needs a score that
  separates calibration progress from held-out generalization.
- Write scope: shadow-score command/report updates, generated outputs under
  `/tmp`, compact docs if useful, and plan updates.
- Acceptance: rerun or extend the tests-only score after the h11 result,
  reporting calibration pass rate, held-out pass rate, runtime, mutation-scope
  violations, hidden-like agreement, and whether the product wedge remains
  shadow-only.
- Tests: focused shadow-score tests, plan consistency, `git diff --check`, and
  the score/report smoke command.

### DATA-005: Issue/PR replay preflight runner

- Status: done
- Why: `DATA-004` records compact real rows, but validation and setup may break
  before edit quality can be measured.
- Write scope: replay preflight runner code, focused tests, docs if needed, and
  plan updates.
- Acceptance: check out or simulate one `repo_before_ref`, run dependency/setup
  and focused validation preflight without edits, and classify failures as
  environment, validation, prompt/spec, ranking, materialization, or local
  knowledge blockers.
- Tests: focused preflight tests with mocked subprocess or tiny fixtures, plan
  consistency, and `git diff --check`.

## Next Recommended Queue

Start with these unless fresh evidence changes the order:

1. `REAL-007`: rerun/extend shadow scoring after the first held-out
   materializer result, separating calibration from held-out evidence.
2. `MAT-003`: attempt one bounded real one-file feature materialization probe.
3. `KNOW-003`: broaden knowledge-use attribution where scoring shows missing
   local-knowledge evidence.
4. `MODEL-006`: candidate-after or AST-delta observation for ranking evidence.
5. `MODEL-003`: penalize add-keyword decoys after held-out validation proof.
