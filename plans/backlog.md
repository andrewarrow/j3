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

### GS7-010: Materialize held-out humanize tests-only candidate

- Status: done
- Why: after h11, the tests-only gate still needs another held-out repo before
  guarded opt-in can be considered.
- Write scope: `j3/real_repo_tests_planner.py`,
  `tests/test_real_repo_tests_planner.py`, optional generated outputs under
  `/tmp`, and plan updates.
- Acceptance: for `humanize-tests-naturalsize-negative-strings`, select
  `tests/test_filesize.py` from repo-state and local-knowledge evidence;
  materialize pytest coverage for negative numeric strings, GNU suffixes, and
  binary suffixes; preserve production files; emit candidate-after,
  mutation-scope, validation-command, residual, and knowledge-use metadata; and
  live-validate the pinned checkout if setup succeeds. If the repo exposes a
  materialization, API, or validation blocker, record it precisely.
- Tests: focused planner/materializer tests,
  `pytest tests/test_plan_consistency.py -q`, `git diff --check`, and a live
  `python -m pytest tests/test_filesize.py -q --benchmark-disable` candidate
  check when available.
- Completion note: added the second held-out tests-only materializer for
  `humanize-tests-naturalsize-negative-strings`. The planner selects
  `tests/test_filesize.py` from repo-state plus local-knowledge evidence,
  appends pytest coverage for negative numeric strings, GNU suffixes, and
  binary suffixes, preserves production hashes, and emits candidate-after,
  mutation-scope, validation-command, residual, and knowledge-use metadata.
  Live validation against the pinned humanize checkout passed with
  `79 passed in 0.03s`, changing only `tests/test_filesize.py`.

### GS7-011: Materialize held-out boltons tests-only candidate

- Status: done
- Why: the tests-only gate needs broad held-out evidence and boltons is the
  remaining ladder repo whose baseline has not yet been exercised by candidate
  scoring.
- Write scope: `j3/real_repo_tests_planner.py`,
  `tests/test_real_repo_tests_planner.py`, optional generated outputs under
  `/tmp`, and plan updates.
- Acceptance: for `boltons-tests-slugify-delimiter`, select
  `tests/test_strutils.py` from repo-state and local-knowledge evidence;
  materialize pytest coverage for custom delimiters, empty strings, ascii
  output, and `lower=False`; preserve production files; emit candidate-after,
  mutation-scope, validation-command, residual, and knowledge-use metadata; and
  live-validate the pinned checkout if setup succeeds. If setup or validation
  fails, classify environment versus agent failure.
- Tests: focused planner/materializer tests,
  `pytest tests/test_plan_consistency.py -q`, `git diff --check`, and a live
  `python -m pytest tests/test_strutils.py -q` candidate check when available.
- Completion note: added the remaining held-out tests-only materializer for
  `boltons-tests-slugify-delimiter`. The planner selects
  `tests/test_strutils.py` from repo-state plus local-knowledge evidence,
  appends pytest-discoverable coverage for custom delimiters, empty strings,
  ascii bytes output, and `lower=False`, preserves production hashes, and emits
  candidate-after, mutation-scope, validation-command, residual, and
  knowledge-use metadata. Live validation against the pinned boltons checkout
  passed with `20 passed in 0.03s`, changing only `tests/test_strutils.py`.

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

- Status: done
- Why: identifier, attribute, signature, and wrapper residuals need evidence
  that a candidate changes the failing behavior rather than a nearby name or
  import.
- Write scope: candidate observation/scorer feature prototype and focused
  residual tests.
- Acceptance: scorer inputs expose candidate-after or AST-delta signals for
  the residual families without enabling production ranking by default.
- Tests: focused transition action scoring/ranking tests.
- Completion note: added `j3.candidate_observation` to normalize nested
  candidate-after, candidate-diff, and AST-delta metadata into flat shadow
  scorer inputs. Transition action-choice records now carry nested
  candidate-after change context without requiring candidate-after embeddings,
  and persisted candidate-ranker records expose `candidate_after_available`,
  diff-size, and AST-delta features for issue/PR candidate attempts. No
  production ranking or guarded-use decision changed.

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

- Status: done
- Why: tests-only wins do not answer the biggest `MAT-001` gap: turning a
  predicted repo-after behavior into bounded source edits for a real Python
  library.
- Write scope: a focused source materialization probe for
  `h11-feature-bytesify-object-message`, focused tests, optional docs, and
  plan updates.
- Acceptance: attempt the pinned h11 one-file feature task with a bounded
  source-region or typed-builder action; preserve the one-production-file
  constraint; record candidate-after diff/AST metadata, mutation scope,
  validation result, runtime, and the first blocker if the edit cannot be
  expressed.
- Tests: focused materializer tests, plan consistency, `git diff --check`, and
  a live targeted validation command when the candidate is materialized.
- Completion note: added `j3.real_repo_feature_materializer` for the held-out
  `h11-feature-bytesify-object-message` task. It materializes one bounded
  source-region edit in `h11/_util.py`, appends focused pytest coverage in
  `h11/tests/test_util.py`, records source/test diff and AST metadata,
  production file hashes, mutation scope, validation result/runtime, and zero
  hosted usage. Live validation against `/tmp/j3-mat-003-live/h11` passed with
  `7 passed in 0.01s`, changing only `h11/_util.py` among production files.

### MAT-004: Second real one-file feature materialization probe

- Status: done
- Why: one h11 source-region success is useful but not enough to prove the
  materialization thesis across real repos.
- Write scope: a focused materializer for one remaining one-file feature ladder
  task, focused tests, optional docs, generated outputs under `/tmp`, and plan
  updates.
- Acceptance: attempt one additional pinned real one-file feature task with a
  bounded source-region or typed-builder action; preserve the production-file
  constraint; record candidate-after diff/AST metadata, mutation scope,
  validation result, runtime, zero hosted usage, and the first blocker if the
  edit cannot be expressed.
- Tests: focused materializer tests, plan consistency, `git diff --check`, and
  a live targeted validation command when a candidate is materialized.
- Completion note: added support for `iniconfig-feature-section-default` to
  `j3.real_repo_feature_materializer`. The probe inserts one bounded delimited
  source region into `src/iniconfig/__init__.py`, appends focused tests for a
  missing-section default, unchanged missing-section `__getitem__` KeyError,
  and existing-section iteration order, records source/test diff and AST
  metadata, protects production hashes, and live-validates the pinned checkout
  under `/tmp/j3-mat-004-live/iniconfig` with `51 passed in 0.03s`.

### MAT-005: Held-out humanize one-file feature materialization probe

- Status: done
- Why: h11 plus calibration iniconfig are not enough to prove source
  materialization on held-out library edits; humanize tests whether the
  source-region approach handles a different API shape and optional-argument
  semantics.
- Write scope: a focused materializer for
  `humanize-feature-naturalsize-zero-format`, focused tests, optional docs,
  generated outputs under `/tmp`, and plan updates.
- Acceptance: attempt the pinned humanize one-file feature task with a bounded
  source-region or typed-builder action; preserve the production-file
  constraint for `src/humanize/filesize.py`; add focused tests in
  `tests/test_filesize.py`; record candidate-after diff/AST metadata,
  mutation scope, validation result, runtime, zero hosted usage, and the first
  blocker if the edit cannot be expressed.
- Tests: focused materializer tests, plan consistency, `git diff --check`, and
  live targeted validation when a candidate is materialized.
- Completion note: added support for
  `humanize-feature-naturalsize-zero-format` to
  `j3.real_repo_feature_materializer`. The probe uses one bounded source-region
  edit in `src/humanize/filesize.py` to add the optional `zero_format`
  argument and return it only when the absolute byte value is zero, appends
  focused tests for `0`, `-0.0`, unchanged calls without `zero_format`, and
  nonzero values ignoring `zero_format`, records source/test diff and AST
  metadata, protects production hashes, and live-validates the pinned checkout
  under `/tmp/j3-mat-005-live.WXA9PU/humanize` with `73 passed in 0.03s`.

### MAT-006: Remaining boltons one-file feature materialization probe

- Status: done
- Why: the one-file feature gate now passes at `3/4`, but the remaining
  `boltons-feature-slugify-max-length` blocker is the direct test of whether
  the source-region approach can finish the held-out feature ladder instead of
  stopping at the first passing gate.
- Write scope: a focused materializer for
  `boltons-feature-slugify-max-length`, focused tests, optional docs,
  generated outputs under `/tmp`, and plan updates.
- Acceptance: attempt the pinned boltons one-file feature task with a bounded
  source-region or typed-builder action; preserve the production-file
  constraint for `boltons/strutils.py`; add focused tests in
  `tests/test_strutils.py`; record candidate-after diff/AST metadata,
  mutation scope, validation result, runtime, zero hosted usage, and the first
  blocker if the edit cannot be expressed.
- Tests: focused materializer tests, plan consistency, `git diff --check`, and
  live targeted validation when a candidate is materialized.
- Completion note: materialized `boltons-feature-slugify-max-length` with one
  bounded `slugify` source-region edit in `boltons/strutils.py` and focused
  coverage in `tests/test_strutils.py` for `max_length` truncation, avoiding a
  trailing configured delimiter, unchanged default behavior without
  `max_length`, and the existing public `from boltons import strutils` import
  style. Live validation against the pinned boltons checkout passed with
  `45 passed in 0.03s`; candidate record:
  `/tmp/j3-mat-006-live.3KJIUG/candidate.json`.

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

### KNOW-004: Click replay local knowledge records

- Status: done
- Why: `DATA-007` shows the Click #3298 issue/PR replay row cannot move to
  candidate generation until local knowledge exists for Click default handling,
  type conversion, non-string defaults, and repo test conventions.
- Write scope: `j3/local_knowledge.py`, focused tests, optional example/report
  files, generated outputs under `/tmp`, and plan updates.
- Acceptance: emit compact, provenance-bearing local-knowledge records for the
  Click #3298 row: repo changed-file context, repo test pattern, focused
  validation recipe, Click parameter default handling, type-conversion
  semantics, non-string default handling, empty-string check semantics, and
  third-party `semver.Version` reproduction context. Add the smallest schema
  extension if these categories cannot be represented honestly.
- Tests: focused local-knowledge tests, plan consistency, `git diff --check`,
  and a smoke command or fixture proving records can be emitted.
- Completion note: added `library_idiom_record` and
  `repo_changed_file_context_record` as the smallest schema extension for
  issue/PR replay knowledge, plus a Click #3298 extractor and CLI smoke path.
  The live `/tmp` run emitted eight compact records for
  `pallets__click-issue-3298-pr-3299`: changed-file context, repo test
  pattern, focused validation recipe, Click parameter default handling, type
  conversion semantics, non-string default handling, empty-string check
  semantics, and third-party `semver.Version` reproduction context.

### KNOW-005: Requests replay local knowledge records

- Status: done
- Why: `DATA-008` turned the Requests replay blocker from validation setup into
  candidate readiness. The row still needs local knowledge for body
  preparation, file-wrapper behavior, redirect rewind semantics, repo tests,
  and fixture setup before ranking or materialization can be meaningful.
- Write scope: `j3/local_knowledge.py`, `tests/test_local_knowledge.py`,
  optional compact report, generated outputs under `/tmp`, and plan updates.
- Acceptance: emit compact, provenance-bearing local-knowledge records for
  `psf__requests-issue-7432-pr-7433`: changed-file context for
  `src/requests/models.py` and `tests/test_requests.py`, the DATA-008 focused
  validation recipe, request-body preparation and stream-detection semantics,
  `__getattr__`-based file-wrapper behavior, redirect/rewind body semantics,
  pytest/httpbin fixture setup, and ranking-relevant changed/test patterns.
  Add only the smallest schema extension needed, with no raw source blobs and
  no hosted LLM use.
- Tests: focused local-knowledge tests, plan consistency, `git diff --check`,
  and a smoke command or fixture proving records can be emitted.
- Completion note: added a narrow Requests #7432/#7433 extractor and CLI smoke
  path. The live DATA-008 repo-before checkout emitted seven compact records:
  changed-file context, focused validation recipe, prepare-body stream
  detection, `__getattr__` file-wrapper behavior, redirect/rewind body
  semantics, pytest-httpbin/trustme fixture setup, and ranking-relevant
  changed/test patterns. Smoke artifact:
  `/tmp/j3-know-005-requests-records.jsonl`.

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

- Status: done
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
- Completion note: the scorer now accepts checkout paths, materializes the
  `iniconfig-tests-parse-comments` calibration candidate through the GS7-008
  planner surface, and optionally validates materialized candidates. The live
  `/tmp/j3-real-006-shadow-score` run scored `pass@1 = 1/4` and
  `pass@3 = 1/4`; `iniconfig` passed at rank 1 with `54 passed in 0.03s`,
  zero production-file changes, zero writes outside the allowlist, hidden-like
  agreement, and zero hosted usage. Held-out rows remained explicit
  `test_case_materialization_gap` blockers, so the gate stayed
  `remain_shadow_only`.

### REAL-007: Held-out tests-only score after first h11 materializer

- Status: done
- Why: once `GS7-009` either passes or fails, the evidence needs a score that
  separates calibration progress from held-out generalization.
- Write scope: shadow-score command/report updates, generated outputs under
  `/tmp`, compact docs if useful, and plan updates.
- Acceptance: rerun or extend the tests-only score after the h11 result,
  counting both `iniconfig-tests-parse-comments` and
  `h11-tests-bytesify-memoryview` through materialized candidates, reporting
  calibration pass rate, held-out pass rate, total pass@1/pass@3, runtime,
  mutation-scope violations, hidden-like agreement, and whether the product
  wedge remains shadow-only.
- Tests: focused shadow-score tests, plan consistency, `git diff --check`, and
  the score/report smoke command.
- Completion note: reran the tests-only shadow score with the GS7-008
  `iniconfig` calibration materializer and the GS7-009 held-out `h11`
  materializer both counted through the real-repo tests planner surface. The
  live `/tmp/j3-real-007-shadow-score` run against pinned checkouts scored
  `pass@1 = 2/4`, `pass@3 = 2/4`, calibration pass@3 `1/1`, and held-out
  pass@3 `1/3`; iniconfig and h11 both passed candidate validation with first
  passing rank 1, zero production-file changes, zero writes outside allowlists,
  hidden-like agreement, and zero hosted usage. `humanize` and `boltons`
  remain explicit `test_case_materialization_gap` blockers, so the gate stays
  `remain_shadow_only`.

### REAL-008: Tests-only gate after next held-out materializer batch

- Status: done
- Why: `REAL-007` can count h11, but the guarded tests-only gate requires at
  least three passing tasks. The gate should be rerun after the next held-out
  materializer batch instead of inferred from standalone live checks.
- Write scope: shadow-score command/report updates, generated outputs under
  `/tmp`, compact docs if useful, and plan updates.
- Acceptance: rerun the tests-only gate with the `iniconfig`, `h11`, and
  `humanize` materialized candidates counted; report calibration versus
  held-out pass rates, pass@1/pass@3, first passing ranks, runtime,
  mutation-scope violations, hidden-like agreement, zero hosted usage, and the
  guarded-use decision. Leave boltons as an explicit blocker unless the
  materializer is already available.
- Tests: focused shadow-score tests, plan consistency, `git diff --check`, and
  the score/report smoke command.
- Completion note: reran the tests-only shadow score with the `GS7-008`
  `iniconfig` calibration materializer, the `GS7-009` held-out `h11`
  materializer, and the `GS7-010` held-out `humanize` materializer counted
  through the real-repo tests planner surface. The live
  `/tmp/j3-real-008-shadow-score-live` run against pinned checkouts scored
  `pass@1 = 3/4`, `pass@3 = 3/4`, calibration pass@3 `1/1`, held-out pass@3
  `2/3`, and first passing ranks `[1, 1, 1, null]`; iniconfig, h11, and
  humanize passed candidate validation with zero production-file changes, zero
  writes outside allowlists, zero target path violations, hidden-like
  agreement, and zero hosted usage. The manifest threshold is met, so guarded
  tests-only opt-in is allowed for materialized, validation-passing
  tests-only candidates within task allowlists. `boltons` remains an explicit
  `test_case_materialization_gap` blocker in this score and should be counted
  by `REAL-010` now that `GS7-011` has materialized it.

### REAL-010: Full tests-only gate after boltons materializer

- Status: done
- Why: `REAL-008` can decide whether the three-candidate threshold is reached,
  but boltons should be counted after `GS7-011` to prove or falsify full ladder
  coverage.
- Write scope: shadow-score command/report updates, generated outputs under
  `/tmp`, compact docs if useful, and plan updates.
- Acceptance: rerun the tests-only gate with every available materialized
  tests-only candidate, report calibration versus held-out pass rates, total
  pass@1/pass@3, first passing ranks, runtime, mutation-scope violations,
  hidden-like agreement, zero hosted usage, and whether guarded tests-only
  opt-in is allowed.
- Tests: focused shadow-score tests, plan consistency, `git diff --check`, and
  the score/report smoke command.
- Completion note: reran the tests-only gate with all four materialized
  tests-only candidates, including `boltons-tests-slugify-delimiter`. The live
  score against pinned `iniconfig`, `h11`, `humanize`, and `boltons` checkouts
  passed at `pass@1 = 4/4` and `pass@3 = 4/4`; calibration pass@3 is `1/1`,
  held-out pass@3 is `3/3`, first passing ranks are `[1, 1, 1, 1]`, candidate
  validation is `passed = 4`, mutation-scope violations are zero, hidden-like
  agreement is `4/4`, and zero hosted usage is confirmed. Guarded tests-only
  opt-in remains allowed for the four materialized, validation-passing
  tests-only task ids inside task allowlists.

### REAL-009: One-file feature shadow score after h11 materializer

- Status: done
- Why: `MAT-003` proved one live h11 source edit, but product evidence needs the
  ladder gate view: pass rates, distinct repos passing, mutation scope, and
  unsupported feature blockers.
- Write scope: focused one-file feature scorer code, focused tests, one compact
  report under `docs/` if useful, generated outputs under `/tmp`, and plan
  updates.
- Acceptance: score the four one-file feature ladder tasks with the h11
  candidate counted through `j3.real_repo_feature_materializer`; unsupported
  feature tasks remain explicit materialization blockers; report pass@1,
  pass@3, distinct repos passing, production-file constraint, runtime,
  mutation-scope violations, zero hosted usage, and the one-file feature gate
  decision.
- Tests: focused feature-score tests, plan consistency, `git diff --check`, and
  the score/report smoke command.
- Completion note: added `j3.real_repo_feature_shadow_score`, focused tests,
  and `docs/REAL_009_ONE_FILE_FEATURE_SHADOW_SCORE_2026-05-18.md`. The live
  `/tmp/j3-real-009-feature-shadow-score-live` run against the pinned h11
  checkout counted `h11-feature-bytesify-object-message` through
  `j3.real_repo_feature_materializer` and validated it with
  `7 passed in 0.02s`, scoring `pass@1 = 1/4`, `pass@3 = 1/4`, one distinct
  repo passing, preserved one-production-file constraint, zero writes outside
  allowlists, zero mutation-scope violations, and zero hosted usage. The
  one-file feature gate remains `remain_shadow_only` because unsupported
  `iniconfig`, `humanize`, and `boltons` feature tasks remain explicit
  `one_file_materialization_gap` blockers.

### REAL-011: One-file feature gate after iniconfig materializer

- Status: done
- Why: `MAT-004` added a second real source materializer, so the feature gate
  needs immediate scoring rather than assuming the materialization thesis is
  improving.
- Write scope: focused one-file feature scorer code, focused tests, one compact
  report under `docs/` if useful, generated outputs under `/tmp`, and plan
  updates.
- Acceptance: score the four one-file feature ladder tasks with both h11 and
  iniconfig candidates counted through `j3.real_repo_feature_materializer`;
  unsupported feature tasks remain explicit materialization blockers; report
  calibration versus held-out rates, pass@1, pass@3, distinct repos passing,
  production-file constraint, runtime, mutation-scope violations, hidden-like
  agreement, zero hosted usage, and the one-file feature gate decision.
- Tests: focused feature-score tests, plan consistency, `git diff --check`, and
  the live score/report smoke command.
- Completion note: reran the one-file feature gate after `MAT-004` and counted
  the concurrent `MAT-005` humanize materializer at integration time. The live
  score against pinned `iniconfig`, `h11`, and `humanize` checkouts passed at
  `pass@1 = 3/4` and `pass@3 = 3/4`; calibration pass@3 is `1/1`, held-out
  pass@3 is `2/3`, first passing ranks are `[1, 1, 1, null]`, candidate
  validation is `passed = 3` and `blocked = 1`, three distinct repos pass,
  mutation-scope violations are zero, hidden-like agreement is `3/3`, and zero
  hosted usage is confirmed. Guarded one-file feature opt-in is allowed only
  for `iniconfig-feature-section-default`,
  `h11-feature-bytesify-object-message`, and
  `humanize-feature-naturalsize-zero-format` inside task allowlists with one
  allowlisted production file changed, passing validation, and no hidden-like
  disagreement. `boltons-feature-slugify-max-length` remains an explicit
  `one_file_materialization_gap` blocker.

### REAL-012: Full one-file feature gate after boltons materializer

- Status: done
- Why: `MAT-006` removed the final one-file feature materialization blocker, so
  the gate must be rescored across all four real repos before broadening any
  guarded opt-in scope.
- Write scope: focused one-file feature scorer code, focused tests, one compact
  report under `docs/` if useful, generated outputs under `/tmp`, and plan
  updates.
- Acceptance: score the four one-file feature ladder tasks with iniconfig,
  h11, humanize, and boltons candidates counted through
  `j3.real_repo_feature_materializer`; report calibration versus held-out
  rates, pass@1, pass@3, distinct repos passing, production-file constraint,
  runtime, mutation-scope violations, hidden-like agreement, zero hosted
  usage, and the exact one-file feature guarded opt-in scope.
- Tests: focused feature-score tests, plan consistency, `git diff --check`, and
  the live score/report smoke command.

- Completion note: reran the full one-file feature gate after `MAT-006`,
  counting iniconfig, h11, humanize, and boltons through
  `j3.real_repo_feature_materializer`. The live score against all four pinned
  checkouts passed at `pass@1 = 4/4` and `pass@3 = 4/4`; calibration pass@3 is
  `1/1`, held-out pass@3 is `3/3`, first passing ranks are `[1, 1, 1, 1]`,
  candidate validation is `passed = 4`, four distinct repos pass,
  mutation-scope violations are zero, hidden-like agreement is `4/4`, and zero
  hosted usage is confirmed. Guarded one-file feature opt-in is allowed only
  for `iniconfig-feature-section-default`,
  `h11-feature-bytesify-object-message`,
  `humanize-feature-naturalsize-zero-format`, and
  `boltons-feature-slugify-max-length` inside task allowlists with one
  allowlisted production file changed, passing validation, and no hidden-like
  disagreement. Report:
  `docs/REAL_012_ONE_FILE_FEATURE_SHADOW_SCORE_2026-05-18.md`.

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

### DATA-006: Live issue/PR mini replay preflight batch

- Status: done
- Why: the real-repo ladder is still curated; issue/PR replay is the next
  pressure test for real user-like prompts, setup cost, validation trust, and
  local-knowledge blockers.
- Write scope: issue/PR replay preflight batch/report support, focused tests,
  one compact report under `docs/` if useful, generated outputs under `/tmp`,
  and plan updates.
- Acceptance: run at least a bounded first batch of `DATA-004` replay rows
  through checkout, setup, and focused validation before any edit attempt;
  record runtime, command outcomes, blocker labels, residual categories,
  deferred agent residuals, and what failed first. If live setup is too slow or
  incompatible, classify that as evidence rather than broadening scope.
- Tests: focused issue/PR preflight tests, plan consistency,
  `git diff --check`, and the live preflight/report smoke command when
  feasible.

- Completion note: added batch preflight/report support and ran the first
  three mini replay rows live under `/tmp/j3-data-006-live-preflight`.
  Checkout, setup, and focused baseline validation were reached for all three
  rows before any edit attempt. The batch produced
  `status_counts = {"blocked": 3}`, `blocker_label_counts =
  {"validation_baseline_failed": 1,
  "prompt_spec_ambiguous_or_incomplete": 1,
  "local_knowledge_required": 1}`, `residual_category_counts =
  {"validation": 1, "prompt_spec": 1, "local_knowledge": 1}`, and deferred
  agent residual counts `{"ranking_gap": 3, "materialization_gap": 1}`.
  Requests failed focused baseline validation on a recursive `httpbin` fixture
  dependency; the two Click rows passed baseline validation and remain blocked
  by prompt/spec and local-knowledge pre-edit residuals.

### DATA-007: Issue/PR replay blocker drilldown

- Status: done
- Why: `DATA-006` proved the issue/PR path blocks before edit quality on
  validation, prompt/spec, and local knowledge; the next proof is whether
  those blockers can be made actionable instead of becoming vague labels.
- Write scope: issue/PR preflight blocker-detail/report support, focused tests,
  one compact report under `docs/` if useful, generated outputs under `/tmp`,
  and plan updates.
- Acceptance: use the first DATA-006 batch to distinguish validation recipe
  failure from dependency/fixture setup failure for the Requests row, and
  record missing prompt/spec and local-knowledge fields for the two Click rows;
  do not attempt issue/PR code edits.
- Tests: focused issue/PR preflight tests, plan consistency,
  `git diff --check`, and a smoke command over the DATA-006 JSONL or a fresh
  bounded preflight when feasible.

- Completion note: added machine-readable blocker details to issue/PR
  preflight outcomes, plus JSONL reprocessing and compact report support.
  DATA-006's first batch now distinguishes the Requests baseline failure as a
  recursive `httpbin` dependency/fixture setup failure, records missing
  prompt/spec fields for the Click `default_map` row, and records required
  Click local-knowledge categories for the non-string `semver.Version` default
  row. Report: `docs/DATA_007_ISSUE_PR_BLOCKER_DRILLDOWN_2026-05-18.md`;
  enhanced JSONL: `/tmp/j3-data-007-blocker-drilldown/outcomes.jsonl`.

### DATA-008: Requests replay validation recipe isolation

- Status: done
- Why: `DATA-007` identifies the Requests row as a validation/dependency
  blocker, not an edit-quality signal. The replay path needs a hermetic
  focused validation recipe or an explicit reason the row must stay blocked.
- Write scope: `j3/issue_pr_preflight.py`, focused tests, one compact report
  under `docs/` if useful, generated outputs under `/tmp`, and plan updates.
- Acceptance: for `psf__requests-issue-7432-pr-7433`, try bounded validation
  recipe alternatives or setup fixes before any edit attempt; record every
  attempted command, setup delta, runtime, first failed stage, fixture or
  dependency evidence, and the recommended next validation action.
- Tests: focused issue/PR preflight tests, plan consistency,
  `git diff --check`, and the live validation-recipe smoke command when
  feasible.
- Completion note: isolated a hermetic focused validation recipe for
  `psf__requests-issue-7432-pr-7433`. The recursive `httpbin` failure was a
  setup recipe problem: `pytest` alone does not install Requests'
  `pytest-httpbin`/`httpbin` fixture dependencies. The passing recipe creates
  an in-checkout `.venv`, installs `-e .`, `pytest`,
  `pytest-httpbin==2.1.0`, `httpbin~=0.10.0`, and `trustme`, then runs
  `.venv/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or
  rewind_body or getattr_proxy_stream_follows_redirect'`. Repo-before smoke:
  `5 passed, 333 deselected`; accepted-merge diagnostic:
  `6 passed, 333 deselected`. Report:
  `docs/DATA_008_REQUESTS_VALIDATION_RECIPE_2026-05-18.md`; JSONL:
  `/tmp/j3-data-008-live/attempts.jsonl`.

### DATA-009: Click default_map prompt/spec normalization

- Status: done
- Why: `DATA-007` shows `pallets__click-issue-2745-pr-3364` is not ready for
  candidate generation because the replay row is missing the prompt/spec
  details needed to validate any edit.
- Write scope: prompt/spec extraction or normalization support for issue/PR
  replay rows, focused tests, optional compact report, and plan updates.
- Acceptance: build a structured spec for
  `pallets__click-issue-2745-pr-3364` that records minimal reproduction,
  observed behavior, expected behavior, affected API symbol, input shape,
  acceptance test shape, `default_map` mutation timing, multi-value parameter
  shape, string-splitting semantics, provenance, and any fields still blocked
  on unavailable source text. The task must not attempt candidate code edits.
- Tests: focused prompt/spec or issue/PR preflight tests, plan consistency,
  and `git diff --check`.
- Completion note: added `j3.issue_pr_prompt_spec` and focused tests for the
  Click #2745 default-map row. The emitted JSONL spec is normalized, has no
  missing required prompt fields, records no source blockers, and captures the
  minimal reproduction, observed and expected behavior, affected API, input
  and acceptance-test shape, callback-time `default_map` mutation, multi-value
  parameter shape, string-splitting semantics, and provenance. Candidate
  source edits were not attempted. Report:
  `docs/DATA_009_CLICK_DEFAULT_MAP_PROMPT_SPEC_2026-05-18.md`.

### DATA-010: Issue/PR candidate readiness gate

- Status: done
- Why: after `DATA-008`, `DATA-009`, `KNOW-004`, and `KNOW-005`, the replay
  path needs a binary gate that says which first-batch rows are ready for a
  candidate attempt and which hard blocker remains.
- Write scope: issue/PR replay readiness scoring, focused tests, compact
  report, and plan updates.
- Acceptance: consume validation recipe, prompt/spec, and local-knowledge
  evidence for the first DATA-006 rows; emit one readiness row per replay id
  with missing-evidence labels, allowed write scope, validation command,
  residual labels, and a clear candidate-attempt recommendation or blocker.
- Tests: focused issue/PR readiness tests, plan consistency, and
  `git diff --check`.
- Completion note: added `j3.issue_pr_readiness` with JSONL evidence loaders,
  readiness row/report output, and a CLI. The DATA-010 smoke over the first
  three DATA-006 rows consumed DATA-007 preflight evidence, DATA-008 Requests
  validation, DATA-009/DATA-011 prompt/spec records, and KNOW-004/KNOW-005
  local-knowledge JSONL. Requests #7432/#7433 and Click #2745/#3364 are ready
  for candidate attempts; Click #3298/#3299 remains blocked on exact
  `missing_prompt_spec` and missing prompt-field labels. Materialization and
  ranking gaps are recorded as next-stage challenges, not readiness blockers.
  Report: `docs/DATA_010_ISSUE_PR_READINESS_GATE_2026-05-18.md`; JSONL:
  `/tmp/j3-data-010-readiness.jsonl`.

### DATA-011: Requests prepare_body prompt/spec normalization

- Status: done
- Why: `DATA-008` and `KNOW-005` resolved validation and local-knowledge
  blockers for `psf__requests-issue-7432-pr-7433`, but the row still needs a
  normalized prompt/spec record before candidate attempts can be evaluated
  fairly.
- Write scope: `j3/issue_pr_prompt_spec.py`,
  `tests/test_issue_pr_prompt_spec.py`, optional compact report, and plan
  updates.
- Acceptance: build a structured spec for
  `psf__requests-issue-7432-pr-7433` that records minimal reproduction,
  observed behavior, expected behavior, affected API symbol, input shape,
  acceptance test shape, `__getattr__` file-wrapper behavior, stream detection
  semantics, redirect/rewind behavior, provenance, and any fields still
  blocked on unavailable source text. The task must not attempt candidate code
  edits.
- Tests: focused prompt/spec tests, plan consistency, `git diff --check`, and
  a CLI smoke proving the Requests spec can be emitted.
- Completion note: added `j3.issue_pr_prompt_spec` support for the Requests
  #7432/#7433 row. The emitted JSONL spec is normalized, has no missing
  required prompt fields, records no blocking source-text gaps, and captures
  the minimal reproduction, observed repo-before body-position gap, expected
  redirect-safe stream behavior, affected API, input and acceptance-test
  shape, `__getattr__` file-wrapper behavior, stream detection semantics,
  redirect/rewind behavior, and provenance. Candidate source edits were not
  attempted. Smoke artifacts:
  `/private/tmp/j3-data-011-requests-prepare-body-spec.jsonl` and
  `/private/tmp/j3-data-011-requests-prepare-body-spec.md`.

### DATA-012: First issue/PR candidate attempt

- Status: done
- Why: once `DATA-010` identifies a replay row that is ready for candidate
  attempts, the project must immediately test the hard materialization and
  ranking path on a real accepted issue/PR task.
- Write scope: a bounded issue/PR candidate-attempt runner or materializer,
  focused tests, compact report, generated outputs under `/tmp`, and plan
  updates.
- Acceptance: attempt exactly `psf__requests-issue-7432-pr-7433`, the narrower
  DATA-010 ready row with DATA-008 validation and KNOW-005 local knowledge.
  Record generated candidate actions, source/test materialization result,
  allowed-write-path checks, validation command/runtime, pass/fail, residual
  labels, and whether the existing structured-action surface covered the
  accepted edit. If materialization is not expressible, keep this honest with
  the exact action/materialization gap.
- Tests: focused candidate-attempt tests, plan consistency, `git diff
  --check`, and the live focused validation command when feasible.
- Completion note: added `j3.issue_pr_candidate_attempt`, a bounded runner for
  exactly `psf__requests-issue-7432-pr-7433`. The live `/tmp` attempt cloned
  the repo-before Requests checkout, materialized the accepted
  `prepare_body` stream-wrapper source edit and redirect regression test,
  changed only `src/requests/models.py` and `tests/test_requests.py`, ran the
  DATA-008 setup plus focused validation recipe, and passed with
  `6 passed, 333 deselected`. The attempt record captures candidate actions,
  source/test materialization, candidate diff, allowlist checks, validation
  runtime, residual label `candidate_validation_passed`, zero hosted LLM use,
  and bounded structured-action coverage. Artifacts:
  `/private/tmp/j3-data-012-live/candidate.json` and
  `/private/tmp/j3-data-012-live/report.md`.

### DATA-013: Click semver prompt/spec normalization

- Status: done
- Why: `DATA-010` blocked `pallets__click-issue-3298-pr-3299` only on missing
  prompt/spec evidence. KNOW-004 already acquired the required local
  knowledge, so the next blocker-removal step is a normalized spec.
- Write scope: `j3/issue_pr_prompt_spec.py`,
  `tests/test_issue_pr_prompt_spec.py`, optional compact report, and plan
  updates.
- Acceptance: build a structured spec for
  `pallets__click-issue-3298-pr-3299` that records minimal reproduction,
  observed behavior, expected behavior, affected API symbol, input shape,
  acceptance test shape, non-string default behavior, type-conversion
  semantics, empty-string check scope, third-party `semver.Version`
  reproduction context, provenance, and any fields still blocked on
  unavailable source text. The task must not attempt candidate code edits.
- Tests: focused prompt/spec tests, plan consistency, `git diff --check`, and
  a CLI smoke proving the Click semver spec can be emitted.
- Completion note: added a normalized `click_semver_non_string_default_help`
  prompt/spec record for `pallets__click-issue-3298-pr-3299` without
  candidate source edits. The record captures the semver `Version(1, 0, 0)`
  reproduction, observed `default_value == ""` failure, expected
  string-guarded empty-string check, affected `Option.get_help_extra` symbol,
  input and acceptance-test shapes, non-string default behavior,
  type-conversion semantics, empty-string check scope, third-party semver
  context, and provenance to issue #3298, PR #3299, the PR diff, and KNOW-004.
  CLI smoke emitted `/private/tmp/j3-data-013-click-semver-spec.jsonl` with
  `status_counts = {"normalized": 1}` and no missing prompt fields or source
  blockers.

### DATA-014: Second issue/PR candidate attempt

- Status: done
- Why: after `DATA-012`, the loop should immediately test whether the
  candidate-attempt surface generalizes to the other DATA-010 ready row instead
  of overfitting Requests.
- Write scope: `j3/issue_pr_candidate_attempt.py`,
  `tests/test_issue_pr_candidate_attempt.py`, optional compact report,
  generated outputs under `/tmp`, and plan updates.
- Acceptance: attempt exactly `pallets__click-issue-2745-pr-3364`, the other
  DATA-010 ready row. Record candidate actions, source/test materialization
  result, candidate diff or exact blocker, allowed-write-path checks,
  validation command/runtime, pass/fail, residual labels, and whether the
  existing structured-action surface covered the accepted edit. If the edit is
  not expressible, record the exact materialization/action gap.
- Tests: focused candidate-attempt tests, plan consistency, `git diff
  --check`, and live focused validation when feasible.
- Completion note: added a bounded Click default_map candidate-attempt path for
  exactly `pallets__click-issue-2745-pr-3364`. The live repo-before attempt
  materialized `src/click/core.py` with the existing delimited source-region
  action and inserted `tests/test_defaults.py::test_default_map_nargs` with a
  deterministic pytest-function insertion. Validation passed
  `pytest tests/test_defaults.py -q` with `39 passed in 0.03s`, changing only
  `src/click/core.py` and `tests/test_defaults.py` inside the DATA-010
  allowlist. The current surface covers the source/test behavior but not the
  full accepted edit because `CHANGES.rst`, `docs/commands.md`, and
  `docs/conf.py` require a changelog/docs/Sphinx config materialization action
  that does not exist yet.

### DATA-015: Issue/PR readiness refresh after Click semver spec

- Status: done
- Why: `DATA-013` removed the prompt/spec blocker for
  `pallets__click-issue-3298-pr-3299`; the readiness gate must be rerun with
  that evidence before assigning a candidate attempt.
- Write scope: readiness evidence/report generation, optional focused
  readiness tests if behavior changes, compact report under `docs/`, generated
  outputs under `/tmp`, and plan updates.
- Acceptance: rerun readiness over the first three DATA-006 replay rows with
  DATA-013 prompt/spec evidence included. Record which rows are ready, exact
  missing-evidence labels, validation commands, residual labels, and the next
  candidate-attempt recommendation. If Click #3298 is still blocked, preserve
  the exact blocker; if it is ready, make that explicit.
- Tests: focused readiness tests if code changes, plan consistency,
  `git diff --check`, and a CLI smoke over the first three replay rows.
- Completion note: reran the readiness gate over the first three DATA-006 replay
  rows with DATA-013 semver prompt/spec evidence included. Requests #7432/#7433,
  Click #2745/#3364, and Click #3298/#3299 are all
  `ready_for_candidate_attempt`; missing-evidence labels are empty for all
  three rows. Validation commands are the DATA-008 Requests focused command,
  `pytest tests/test_defaults.py -q`, and `pytest tests/test_options.py -q`.
  Residual labels remain `materialization_gap` and `ranking_gap` for all three
  rows. Report:
  `docs/DATA_015_ISSUE_PR_READINESS_REFRESH_2026-05-18.md`; smoke JSONL:
  `/private/tmp/j3-data-015-readiness-smoke.jsonl`.

### DATA-016: Third issue/PR candidate attempt

- Status: done
- Why: after `DATA-014` and `DATA-015`, the loop should either attempt Click
  #3298 if it is readiness-approved or record why the candidate-attempt
  surface cannot yet cover it.
- Write scope: `j3/issue_pr_candidate_attempt.py`,
  `tests/test_issue_pr_candidate_attempt.py`, compact report if useful,
  generated outputs under `/tmp`, and plan updates.
- Acceptance: attempt exactly `pallets__click-issue-3298-pr-3299`; record
  candidate actions, materialization result, allowlist checks, validation
  runtime, pass/fail, residual labels, local-knowledge evidence use, and
  structured-action coverage or exact materialization blocker.
- Tests: focused candidate-attempt tests, plan consistency, `git diff
  --check`, and live focused validation when feasible.
- Completion note: added a bounded Click semver/non-string default candidate
  path for `pallets__click-issue-3298-pr-3299`. The live pinned checkout
  materialized the accepted one-line `Option.get_help_extra` string guard and
  replaced the empty-string default help test with the accepted `_StrictEq`
  parametrized regression in `tests/test_options.py`. It changed only
  `src/click/core.py` and `tests/test_options.py`, stayed inside the
  DATA-015/DATA-010 allowlist, used DATA-013, DATA-015, and KNOW-004 evidence,
  and passed `pytest tests/test_options.py -q` with no materialization gap for
  the accepted source/test edit.

### DATA-017: Click auxiliary materialization gap audit

- Status: done
- Why: `DATA-014` passed source/test validation but did not cover the full
  accepted PR because `CHANGES.rst`, `docs/commands.md`, and `docs/conf.py`
  have no current materializer. This is a direct test of whether structured
  actions can cover enough real Python edits or whether auxiliary repo edits
  become a persistent coverage hole.
- Write scope: `j3/issue_pr_auxiliary_gap_audit.py`,
  `tests/test_issue_pr_auxiliary_gap_audit.py`,
  `docs/DATA_017_CLICK_AUXILIARY_MATERIALIZATION_GAP_2026-05-18.md`,
  generated outputs under `/tmp`, and plan updates. Do not edit
  `j3/issue_pr_candidate_attempt.py`.
- Acceptance: classify the DATA-014 accepted auxiliary paths
  `CHANGES.rst`, `docs/commands.md`, and `docs/conf.py` as covered by current
  structured actions, covered by a small proposed deterministic action,
  requiring a constrained local generator, or not currently expressible.
  Record the provenance, action-family recommendation, validation cost,
  failure mode if attempted, and the smallest next falsifiable materializer
  task.
- Tests: focused audit tests, plan consistency, `git diff --check`, and a CLI
  smoke that emits machine-readable audit rows plus the compact report.
- Completion note: added a DATA-017 auxiliary-gap audit module and report for
  Click #2745/#3364. The audit emits one JSONL row each for `CHANGES.rst`,
  `docs/commands.md`, and `docs/conf.py`, including manifest provenance,
  DATA-014 candidate provenance, accepted-diff stats, current/proposed action
  family, validation cost, likely failure mode, and smallest next falsifiable
  materializer task. It classifies the changelog and Sphinx config paths as
  covered by small proposed deterministic actions, while the command docs
  section requires a constrained local generator.

### DATA-018: Pytest issue/PR replay preflight batch

- Status: done
- Why: the first three issue/PR candidates are now either validated or have a
  precise auxiliary gap, but they are still a small Requests/Click comfort
  zone. The next falsification pressure is whether the same replay pipeline can
  even reach candidate readiness on new pytest rows with different repo setup,
  validation shape, changelog paths, and source/test surfaces.
- Write scope: issue/PR preflight generated outputs under `/tmp`,
  `docs/DATA_018_PYTEST_ISSUE_PR_PREFLIGHT_2026-05-18.md`, optional focused
  `j3/issue_pr_preflight.py` and `tests/test_issue_pr_preflight.py` fixes if
  the existing runner cannot express the bounded batch, and plan updates.
- Acceptance: run pre-edit replay preflight for
  `pytest-dev__pytest-issue-14442-pr-14443`,
  `pytest-dev__pytest-issue-14462-pr-14466`, and
  `pytest-dev__pytest-issue-14381-pr-14382` without attempting candidate
  edits. Record checkout/setup/baseline validation status, runtime, command
  output classification, prompt/spec gaps, local-knowledge requirements,
  materialization/ranking residuals, and the first pytest row that is ready
  for prompt/spec normalization or candidate attempt. If setup or validation
  blocks, classify it as environment/setup/validation rather than edit quality.
- Tests: focused preflight tests if code changes, plan consistency,
  `git diff --check`, and the live bounded preflight command or an exact
  blocker if live preflight cannot complete.
- Completion note: live preflight ran for all three pytest rows under
  `/tmp/j3-data-018-pytest-preflight` with no candidate edits. Checkout,
  setup, and baseline validation passed for every row:
  #14442/#14443 passed `353 passed, 2 xfailed`, #14462/#14466 passed
  `102 passed, 18 skipped`, and #14381/#14382 passed `12 passed`.
  Remaining blockers are pre-edit evidence gaps, not setup or validation:
  local knowledge for #14442/#14443 and #14462/#14466, prompt/spec
  normalization for #14381/#14382, plus manifest materialization/ranking
  residuals where recorded. The first next row for prompt/spec normalization
  and local-knowledge acquisition is
  `pytest-dev__pytest-issue-14442-pr-14443`; no pytest row is candidate-ready
  yet. Report:
  `docs/DATA_018_PYTEST_ISSUE_PR_PREFLIGHT_2026-05-18.md`.

### DATA-019: Constrained Click command-docs materializer spike

- Status: done
- Why: DATA-017 identified `docs/commands.md` as the largest accepted-edit
  coverage hole for the validated Click #2745 source/test candidate. The hard
  question is whether a local constrained generator can produce useful repo
  docs without a frontier LLM runtime, not whether deterministic config or
  changelog inserts are easy.
- Write scope: `j3/issue_pr_docs_materializer.py`,
  `tests/test_issue_pr_docs_materializer.py`, generated outputs under `/tmp`,
  optional compact report under `docs/`, and plan updates. Do not edit
  `j3/issue_pr_candidate_attempt.py`.
- Acceptance: for `pallets__click-issue-2745-pr-3364`, generate and insert
  only the bounded `docs/commands.md` Multi-value parameters section identified
  by DATA-017. The generated section must have the expected heading, mention
  `nargs > 1` and `Tuple` behavior, include at least one whitespace-splitting
  example, preserve unrelated docs content, and record candidate diff,
  mutation scope, validation command/runtime, residual labels, provenance, and
  whether a docs build passes. If docs build or content generation blocks,
  record the exact blocker.
- Tests: focused docs materializer tests, plan consistency, `git diff
  --check`, and a live pinned Click checkout smoke with docs validation when
  feasible.
- Completion note: added a bounded Click commands docs materializer for exactly
  `pallets__click-issue-2745-pr-3364`. The materializer generates the
  `### Multi-value parameters` section, mentions `nargs > 1` and
  the `{class}` role for `Tuple`, includes a whitespace-splitting example, and
  inserts only into `docs/commands.md` before `## Context Defaults`. The live
  pinned checkout changed only `docs/commands.md`; no source, test, changelog,
  or config files changed. Sphinx docs validation was attempted after
  installing docs dependencies and blocked in `2.887s` on
  `docs_reference_resolution_failure` because the new `options.md` heading
  link needs the separate DATA-017 `docs/conf.py` `myst_heading_anchors = 3`
  auxiliary edit, which DATA-019 was not allowed to materialize. Report:
  `docs/DATA_019_CLICK_COMMANDS_DOCS_MATERIALIZER_2026-05-18.md`; artifacts:
  `/tmp/j3-data-019-live/candidate.json` and
  `/tmp/j3-data-019-live/report.md`.

### DATA-020: Click docs conf assignment and integrated docs validation

- Status: done
- Why: DATA-019 proved the hardest Click docs section can be generated, but
  docs validation failed on a discovered cross-path dependency: the accepted
  PR's `docs/conf.py` `myst_heading_anchors = 3` edit. The next proof is
  whether a small deterministic config action closes the validation loop when
  combined with the generated docs section.
- Write scope: `j3/issue_pr_docs_materializer.py`,
  `tests/test_issue_pr_docs_materializer.py`, generated outputs under `/tmp`,
  optional compact report under `docs/`, and plan updates.
- Acceptance: in a live pinned Click checkout for
  `pallets__click-issue-2745-pr-3364`, materialize the DATA-019
  `docs/commands.md` section plus exactly one `docs/conf.py`
  `myst_heading_anchors = 3` assignment. Record actions, candidate diff,
  mutation scope, validation command/runtime, residual labels, provenance to
  DATA-017 and DATA-019, and whether the Sphinx docs build passes. If it still
  fails, record the exact remaining blocker.
- Tests: focused docs materializer tests, plan consistency, `git diff
  --check`, and a live pinned Click docs validation smoke when feasible.
- Completion note: added the integrated Click docs materializer path for
  `docs/commands.md` plus `docs/conf.py`. The live pinned checkout changed
  only those two files, inserted exactly one `myst_heading_anchors = 3`
  assignment with duplicate detection and compile validation, and passed the
  Sphinx `dirhtml` docs build in `3.068s`. Artifacts:
  `/tmp/j3-data-020-live/candidate.json`,
  `/tmp/j3-data-020-live/report.md`, and
  `docs/DATA_020_CLICK_DOCS_CONF_INTEGRATED_VALIDATION_2026-05-18.md`.

### DATA-021: Pytest #14442 prompt/spec and local knowledge evidence

- Status: done
- Why: DATA-018 showed pytest checkout/setup/baseline validation works, but no
  pytest row is candidate-ready because prompt/spec and local knowledge are
  missing. The first row, #14442/#14443, is a direct test of local knowledge
  acquisition for pytest config parsing, strict markers/config behavior, repo
  tests, changelog fragments, and AUTHORS convention.
- Write scope: focused issue/PR prompt/spec and/or local-knowledge modules and
  tests, generated outputs under `/tmp`, optional compact report under
  `docs/`, and plan updates. Do not attempt candidate source edits.
- Acceptance: emit machine-readable evidence for
  `pytest-dev__pytest-issue-14442-pr-14443`: normalized prompt/spec fields,
  changed-file context for `AUTHORS`, `changelog/14442.bugfix.rst`,
  `src/_pytest/config/__init__.py`, `testing/test_config.py`, and
  `testing/test_mark.py`, focused validation recipe from DATA-018, strict
  `addopts` behavior, strict markers/config semantics, repo test patterns,
  auxiliary path conventions, provenance, and remaining readiness blockers.
- Tests: focused prompt/spec/local-knowledge tests, plan consistency,
  `git diff --check`, and CLI smoke that emits the evidence rows.
- Completion note: added a pytest #14442/#14443 prompt/spec normalizer and a
  narrow local-knowledge extractor. The emitted prompt/spec row is normalized
  and covers the required reproduction, behavior, affected surface, input, and
  acceptance-test fields. The local-knowledge smoke emits seven records for
  changed-file context, DATA-018 validation, strict addopts behavior, strict
  marker/config semantics, repo test patterns, changelog convention, and
  AUTHORS convention. No candidate source edits were attempted. Artifacts:
  `/tmp/j3-data-021-pytest-14442-spec.jsonl`,
  `/tmp/j3-data-021-pytest-14442-spec.md`,
  `/tmp/j3-data-021-pytest-14442-knowledge.jsonl`, and
  `docs/DATA_021_PYTEST_STRICT_ADDOPTS_EVIDENCE_2026-05-18.md`. Remaining
  blockers are candidate-readiness refresh, ranking evidence, and deciding
  whether the accepted auxiliary paths are in scope for a future candidate.

### DATA-022: Pytest #14442 readiness refresh

- Status: done
- Why: DATA-021 supplied the missing prompt/spec and local-knowledge evidence
  for the first DATA-018 pytest row. The next gate must say whether
  `pytest-dev__pytest-issue-14442-pr-14443` is candidate-ready, and if not,
  exactly which hard blocker remains.
- Write scope: `j3/issue_pr_readiness.py`,
  `tests/test_issue_pr_readiness.py`, generated outputs under `/tmp`,
  optional compact report under `docs/`, and plan updates.
- Acceptance: consume DATA-018 preflight evidence, DATA-021 prompt/spec
  evidence, and DATA-021 local-knowledge evidence for exactly
  `pytest-dev__pytest-issue-14442-pr-14443`. Emit one readiness row with
  missing-evidence labels, allowed write scope, validation command, residual
  labels, and recommendation. If the row is ready, make the source/test versus
  full accepted-edit scope decision explicit; if it is blocked, record the
  concrete evidence gap.
- Tests: focused readiness tests, plan consistency, `git diff --check`, and a
  CLI smoke for the single pytest row.
- Completion note: refreshed readiness for exactly
  `pytest-dev__pytest-issue-14442-pr-14443` using DATA-018 preflight evidence
  plus DATA-021 prompt/spec and local-knowledge JSONL. The row is
  `ready_for_candidate_attempt` with no missing-evidence labels, validation
  command `pytest testing/test_config.py testing/test_mark.py -q`, seven
  local-knowledge evidence records, and residual labels `materialization_gap`
  and `ranking_gap`. The row explicitly separates source/test candidate scope
  (`src/_pytest/config/__init__.py`, `testing/test_config.py`,
  `testing/test_mark.py`) from full accepted-edit scope, which also includes
  `AUTHORS` and `changelog/14442.bugfix.rst`. Artifacts:
  `/tmp/j3-data-022-readiness-refresh/readiness.jsonl`,
  `/tmp/j3-data-022-readiness-refresh/report.md`, and
  `docs/DATA_022_PYTEST_ISSUE_PR_READINESS_REFRESH_2026-05-18.md`.

### DATA-023: Pytest #14442 materialization coverage audit

- Status: done
- Why: before attempting a pytest candidate, the loop needs an honest answer
  to whether the accepted diff can be expressed by the current structured
  action surface or only by new materializers/generators. This directly tests
  the structured-action coverage thesis on a repo beyond Requests/Click.
- Write scope: a focused issue/PR materialization audit module and tests,
  generated outputs under `/tmp`, optional compact report under `docs/`, and
  plan updates. Do not attempt candidate source edits.
- Acceptance: inspect the accepted #14442/#14443 diff against the repo-before
  checkout and classify each accepted path (`AUTHORS`,
  `changelog/14442.bugfix.rst`, `src/_pytest/config/__init__.py`,
  `testing/test_config.py`, and `testing/test_mark.py`) as covered by current
  structured actions, covered by a small proposed deterministic action,
  requiring a constrained local generator/source-region action, or not
  currently expressible. Record provenance, action-family recommendation,
  validation cost, likely failure mode, and the smallest next falsifiable
  materializer task for each path.
- Tests: focused audit tests, plan consistency, `git diff --check`, and a CLI
  smoke that emits machine-readable audit rows plus a compact report.
- Completion note: added a DATA-023 materialization coverage audit module and
  compact report for all accepted `pytest-dev__pytest-issue-14442-pr-14443`
  paths. `AUTHORS` is covered by a small proposed deterministic
  `newline_delimited_sorted_unique_insert_v1`; `changelog/14442.bugfix.rst`
  needs a constrained changelog-fragment generator; `src/_pytest/config/__init__.py`
  needs a deterministic import inserter plus bounded `Config.parse` source
  region; and `testing/test_config.py` plus `testing/test_mark.py` need a
  constrained existing-pytest-test refiner. Artifacts:
  `/tmp/j3-data-023-pytest-14442-materialization-audit/audit.jsonl`,
  `/tmp/j3-data-023-pytest-14442-materialization-audit/report.md`, and
  `docs/DATA_023_PYTEST_14442_MATERIALIZATION_COVERAGE_AUDIT_2026-05-18.md`.

### DATA-024: Pytest #14442 source/test candidate attempt

- Status: done
- Why: DATA-022 says pytest #14442 is candidate-ready and DATA-023 says full
  accepted-edit parity is not currently expressible. The hard next proof is
  whether the current stack can materialize and validate the behavior-changing
  source/test slice in a new repo while preserving the auxiliary gap honestly.
- Write scope: a bounded pytest issue/PR candidate-attempt path and tests,
  generated outputs under `/tmp`, optional compact report under `docs/`, and
  plan updates.
- Acceptance: attempt exactly `pytest-dev__pytest-issue-14442-pr-14443` in
  explicit source/test-only scope. Materialize only
  `src/_pytest/config/__init__.py`, `testing/test_config.py`, and
  `testing/test_mark.py`; do not write `AUTHORS` or
  `changelog/14442.bugfix.rst`. Record actions, candidate diff, mutation
  scope, validation command/runtime/pass-fail, residual labels,
  DATA-018/021/022/023 provenance, and structured-action coverage. Run live
  focused validation with `pytest testing/test_config.py testing/test_mark.py
  -q` when feasible. If materialization or validation blocks, record the exact
  blocker.
- Tests: focused candidate-attempt tests, plan consistency, `git diff
  --check`, and live validation when feasible.
- Completion note: added the DATA-024 source/test-only pytest #14442 candidate
  attempt path. The live pinned pytest checkout changed only
  `src/_pytest/config/__init__.py`, `testing/test_config.py`, and
  `testing/test_mark.py`; `AUTHORS` and `changelog/14442.bugfix.rst` remained
  untouched and are recorded as explicit auxiliary residuals. The candidate
  record includes actions, candidate diff, mutation scope, validation
  command/runtime/pass-fail, DATA-018/021/022/023 provenance, and structured
  action coverage. Live validation passed with `pytest testing/test_config.py
  testing/test_mark.py -q` after installing the checkout; full accepted-edit
  coverage remains false only because the auxiliary paths are excluded from
  this slice. Artifacts:
  `/tmp/j3-data-024-pytest-14442-source-test/candidate.json`,
  `/tmp/j3-data-024-pytest-14442-source-test/report.md`, and
  `docs/DATA_024_PYTEST_14442_SOURCE_TEST_CANDIDATE_2026-05-18.md`.

### DATA-025: Pytest #14442 auxiliary materializers and full-scope candidate

- Status: done
- Why: DATA-024 validated the source/test behavior but preserved
  `accepted_auxiliary_paths_not_materialized`. DATA-023 says `AUTHORS` is a
  small deterministic insertion and the changelog fragment needs a constrained
  generator. The next proof is whether auxiliary path materializers can close
  full accepted-edit parity without breaking validation.
- Write scope: a focused pytest auxiliary materializer module/tests, generated
  outputs under `/tmp`, optional compact report under `docs/`, and plan
  updates.
- Acceptance: in a live pinned pytest checkout, materialize the DATA-024
  source/test candidate plus accepted auxiliary paths `AUTHORS` and
  `changelog/14442.bugfix.rst`. Record actions, candidate diff, mutation
  scope, validation command/runtime/pass-fail, residual labels,
  DATA-021/022/023/024 provenance, and structured-action coverage. The live
  checkout may change exactly the five accepted paths and must validate with
  `pytest testing/test_config.py testing/test_mark.py -q` when feasible. If
  AUTHORS/changelog content is blocked, record the exact blocker.
- Tests: focused auxiliary materializer tests, plan consistency, `git diff
  --check`, and live validation when feasible.
- Completion note: added deterministic DATA-025 auxiliary materializers for
  pytest #14442/#14443 and integrated them with the validated DATA-024
  source/test candidate. The live pinned checkout at
  `8f81c76744daf72d4f77cfc8423f4bdc60733d78` changed exactly `AUTHORS`,
  `changelog/14442.bugfix.rst`, `src/_pytest/config/__init__.py`,
  `testing/test_config.py`, and `testing/test_mark.py`, passed `pytest
  testing/test_config.py testing/test_mark.py -q` in `6.083s`, and records
  full accepted-edit coverage as expressible for this bounded replay. Artifacts:
  `/tmp/j3-data-025-pytest-14442-full-scope/candidate.json`,
  `/tmp/j3-data-025-pytest-14442-full-scope/report.md`, and
  `docs/DATA_025_PYTEST_14442_FULL_SCOPE_CANDIDATE_2026-05-18.md`.

### DATA-026: Pytest #14462 prompt/spec and local knowledge evidence

- Status: done
- Why: DATA-018 proved pytest #14462 has working checkout/setup/baseline
  validation, but it still needs normalized prompt/spec and local knowledge
  before candidate generation. This pushes the pytest replay path beyond a
  single issue and tests local knowledge acquisition for datetime/timedelta
  `approx` semantics.
- Write scope: focused issue/PR prompt/spec and local-knowledge modules/tests,
  generated outputs under `/tmp`, optional compact report under `docs/`, and
  plan updates. Do not attempt candidate source edits.
- Acceptance: emit machine-readable evidence for
  `pytest-dev__pytest-issue-14462-pr-14466`: normalized prompt/spec fields for
  timedelta `approx` relative tolerance, changed-file context for
  `src/_pytest/python_api.py` and `testing/python/approx.py`, DATA-018
  focused validation recipe, `ApproxTimedelta` tolerance semantics,
  datetime/timedelta comparison behavior, repo test patterns, provenance, and
  remaining readiness blockers.
- Tests: focused prompt/spec/local-knowledge tests, plan consistency,
  `git diff --check`, and CLI smoke that emits the evidence rows.
- Completion note: added normalized prompt/spec evidence plus six
  local-knowledge rows for `pytest-dev__pytest-issue-14462-pr-14466`.
  Prompt/spec covers timedelta `approx` relative tolerance, observed repo-before
  behavior, expected `rel * abs(expected)` semantics, affected
  `_pytest.python_api.ApproxTimedelta` surface, input shape, acceptance tests,
  and datetime/timedelta comparison policy. Local knowledge covers
  `src/_pytest/python_api.py`, `testing/python/approx.py`, DATA-018 validation,
  `ApproxTimedelta` tolerance behavior, repo test patterns, provenance, and
  remaining readiness blockers. Artifacts:
  `/tmp/j3-data-026-pytest-14462-evidence/spec.jsonl`,
  `/tmp/j3-data-026-pytest-14462-evidence/spec.md`,
  `/tmp/j3-data-026-pytest-14462-evidence/knowledge.jsonl`, and
  `docs/DATA_026_PYTEST_14462_PROMPT_SPEC_KNOWLEDGE_2026-05-18.md`.

## Next Recommended Queue

Start with these unless fresh evidence changes the order:

1. `KNOW-003`: broaden knowledge-use attribution where scoring shows missing
   local-knowledge evidence.
2. `MODEL-003`: penalize add-keyword decoys after held-out validation proof.
