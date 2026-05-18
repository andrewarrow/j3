# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: continuous loop mode. The active set may be empty only
  while the coordinator is recording the next assignments; ready work should be
  dispatched rather than leaving the board idle.
- Current product gate stance: transition ranking remains shadow-only; the
  2026-05-18 `TRANS-001` full matrix and `TRANS-004` targeted subset decisions
  were `remain_shadow_only`. Tests-only wedge guarded opt-in also remains
  blocked after `REAL-003` scored `pass@3 = 0/4`; `GS7-008` now materializes
  and live-validates the `iniconfig` calibration candidate. `REAL-005` extends
  live baseline preflight to `h11` and `humanize`, so Gate A now has three
  baseline-passing repositories when combined with `REAL-004` `iniconfig`.
  `REAL-010` scores all four materialized tests-only ladder candidates at
  `pass@1 = 4/4` and `pass@3 = 4/4`; calibration pass rate is `1/1`,
  held-out pass rate is `3/3`, and guarded tests-only opt-in is allowed only
  for `iniconfig-tests-parse-comments`, `h11-tests-bytesify-memoryview`,
  `humanize-tests-naturalsize-negative-strings`, and
  `boltons-tests-slugify-delimiter` when candidate validation passes, writes
  stay inside task-allowlisted test files, production files remain unchanged,
  and hidden-like checks do not disagree. `MAT-003` materialized and
  live-validated the first real one-file source feature candidate on held-out
  `h11`; `MAT-004` now materializes and live-validates the second one-file
  source feature candidate for calibration `iniconfig`. `MAT-005` now
  materializes and live-validates the next held-out one-file source feature
  candidate for `humanize`. `MAT-006` materialized and live-validated the
  remaining held-out boltons one-file source feature candidate. `REAL-012`
  now scores all four one-file feature candidates at `pass@1 = 4/4` and
  `pass@3 = 4/4`; calibration pass@3 is `1/1`, held-out pass@3 is `3/3`,
  four distinct repos pass, candidate validation is `passed = 4`,
  hidden-like agreement is `4/4`, and guarded one-file feature opt-in is
  allowed only for `iniconfig-feature-section-default`,
  `h11-feature-bytesify-object-message`,
  `humanize-feature-naturalsize-zero-format`, and
  `boltons-feature-slugify-max-length` when candidate validation passes,
  writes stay inside task allowlists, only the task's single allowlisted
  production file changes, and hidden-like checks do not disagree.

## Active Tasks

### `DATA-038`: Issue/PR candidate-after snapshot bundle

- Status: active
- Owner: worker Kierkegaard (`019e3cc0-e4a0-7893-8bcf-e090084bf843`).
- Write scope: a focused candidate-after snapshot module and tests, optional
  integration with the DATA-037 ranking harness, generated artifacts under
  `/tmp`, optional compact docs/report, and planning updates. Avoid editing
  MAT-008-owned materialization code.
- Acceptance: for the validated DATA-029 pytest #14462 and DATA-035 Scrapy
  #7293 candidates, produce a sidecar candidate-after bundle with touched file
  paths, before/after hashes, full after-file snapshots or exact paths to
  stored snapshots, diff/AST metadata, validation status, and provenance. Then
  rerun or extend the DATA-037 ranking report enough to show the
  `full_candidate_after_unavailable` blocker is resolved or replaced by the
  next exact blocker. Do not change production ranking gates.

### `MAT-008`: Held-out requests source-region candidate

- Status: active
- Owner: worker Singer (`019e3cc1-1a8b-70e2-857b-213ff36ba524`).
- Write scope: a generic held-out source-region candidate module and tests,
  optional docs/report, generated artifacts under `/tmp`, and planning updates.
  Do not edit DATA-038-owned ranking or snapshot modules.
- Acceptance: attempt the MAT-007 recommended `psf/requests#7427`
  `should_bypass_proxies` domain-boundary edit using reusable action records
  such as `replace_function_region` plus repo-convention pytest insertion, not
  a `requests_7427` bespoke action kind. In a pinned live checkout at the
  MAT-001 base, change only the accepted source/test files when feasible,
  record candidate-after diff/AST metadata and mutation scope, compare against
  the accepted PR diff where practical, and run the focused validation command
  or record the exact materialization/validation blocker.

## Ready Queue

These are good next assignments for the next loop:

1. `KNOW-003`: broaden knowledge-use attribution where scoring shows missing
   local-knowledge evidence.
2. `MODEL-004`: distinguish mapping key and value targets.
3. `MODEL-003`: penalize add-keyword decoys after held-out validation proof.

Run at most two tasks in parallel unless write scopes are plainly disjoint.

## Paused Or Blocked

- `TRANS-003`: blocked until the `TRANS-002` generation and ranking residuals
  have focused fixes or regression evidence; do not expand the full matrix
  until targeted `TRANS-004` evidence is recorded.
- `MODEL-002`: superseded by bounded scorer subtasks in the backlog, beginning
  with `MODEL-003` through `MODEL-006`.

## Coordinator Review Triggers

Review before assigning more work if:

- `TRANS-001` reports a gate worse than expected
- `GS7-001` reveals missing actions rather than simple ranking failures
- `DATA-001` shows prompt split leakage or weak schema consistency
- two workers need the same files
- the next useful task is unclear

## Recently Completed

- `MAT-007`: refreshed real PR materialization coverage after the DATA-029 and
  DATA-035 validated candidate wins. The held-out panel contains 24 accepted
  Python PR diffs, excluding the two validated candidate reference rows.
  Counts remain challenging: `current_structured_action = 4`,
  `general_typed_builder = 7`, `repo_convention_builder = 4`,
  `constrained_local_generator = 7`, and `not_currently_expressible = 2`.
  The result confirms that DATA-029 and DATA-035 are real constrained-source
  wins, but they do not yet collapse the held-out constrained bucket because
  the implemented action labels remain domain-specific. Artifacts:
  `docs/MAT_007_REAL_PR_MATERIALIZATION_REFRESH_2026-05-18.md`,
  `docs/MAT_007_REAL_PR_MATERIALIZATION_REFRESH_2026-05-18.jsonl`, and
  `/tmp/j3-mat-007-real-pr-materialization-refresh/MAT_007_REAL_PR_MATERIALIZATION_REFRESH_2026-05-18.jsonl`.
- `DATA-037`: added a shadow-only real issue/PR ranking decoy harness for the
  validated DATA-029 pytest #14462 and DATA-035 Scrapy #7293 candidate records.
  Each row has one accepted validated candidate and four realistic decoys. The
  result is an honest blocker, not a ranking win: `rankable_rows = 0`,
  `pass@1 = blocked`, and `pass@k = blocked` because there is no guarded
  issue/PR ranker, decoys are not live-validated, full candidate-after file
  snapshots are unavailable, and current candidate-record features do not
  encode the issue-specific semantics needed to separate the accepted candidate
  from hard decoys. Artifacts:
  `/tmp/j3-data-037-issue-pr-ranking-decoys/ranking-report.json`,
  `/tmp/j3-data-037-issue-pr-ranking-decoys/decoy-candidates.jsonl`,
  `/tmp/j3-data-037-issue-pr-ranking-decoys/ranking-report.md`, and
  `docs/DATA_037_ISSUE_PR_RANKING_DECOY_HARNESS_2026-05-18.md`.
- `DATA-035`: added and reviewed a bounded source/test candidate attempt for
  exactly `scrapy__scrapy-issue-7293-pr-7351`. The materializer changes only
  `scrapy/pqueues.py` and `tests/test_pqueues.py`, adds
  `DownloaderAwarePriorityQueue._last_selected_slot`, inserts the bounded
  `_next_slot` helper, makes `pop` update rotation state, keeps `peek`
  non-mutating, and inserts the accepted Downloader import plus two
  `TestDownloaderAwarePriorityQueue` slot-rotation tests. Coordinator review
  fixed the worker's one blank-line parity mismatch; the regenerated real
  checkout candidate diff now matches the accepted PR diff byte-for-byte for
  the source/test paths. Focused live validation passed with `python -m
  py_compile scrapy/pqueues.py && pytest tests/test_pqueues.py -q` (`13`
  passed, `2` skipped, `2` warnings). Final artifacts:
  `/tmp/j3-data-035-scrapy-7293-source-test-final/candidate.json`,
  `/tmp/j3-data-035-scrapy-7293-source-test-final/report.md`,
  `/tmp/j3-data-035-scrapy-7293-source-test-final/candidate.diff`,
  `/tmp/j3-data-035-scrapy-7293-source-test-final/accepted.diff`, and
  `/tmp/j3-data-035-scrapy-7293-source-test-final/parity.diff`.
- `DATA-036`: continued the DATA-032 pip validation recipe isolation for
  exactly `pypa__pip-issue-12018-pr-13886` with no candidate edits. The setup
  command `python -m pip install -e . installer scripttest` explicitly adds
  `scripttest` to the prior `installer` recipe and reaches the bounded
  repo-before validation command `pytest tests/functional/test_install_reqs.py
  -q` on checkout `8df7b668b3766e1d4a71246509d64aeec47a805b`. Checkout, ref
  verification, and setup passed; validation still failed before tests ran
  because pytest rejected pip's configured socket options
  `--disable-socket --allow-unix-socket --allow-hosts=localhost`. The next
  explicit fixture/tooling dependency is `pytest-socket`; the row remains
  `blocked_on_validation_recipe` with command classification
  `dependency_fixture_setup_failure`, not ready for prompt/spec/local-knowledge
  acquisition. Artifacts:
  `/tmp/j3-data-036-pip-validation-scripttest/attempts-data-036.jsonl`,
  `/tmp/j3-data-036-pip-validation-scripttest/report-data-036.md`, and
  `docs/DATA_036_PIP_VALIDATION_RECIPE_SCRIPTTEST_PROBE_2026-05-18.md`.
- `DATA-034`: added a machine-readable materialization coverage audit for
  exactly `scrapy__scrapy-issue-7293-pr-7351` with no candidate edits. Both
  accepted paths, `scrapy/pqueues.py` and `tests/test_pqueues.py`, require
  constrained local generator/source-region action coverage before candidate
  generation; no path is covered by the current structured-action surface.
  The audit records manifest, DATA-030, and DATA-031 provenance; accepted diff
  stats (`30`/`2` and `49`/`0`); validation costs; likely failure modes; and
  smallest next falsifiable materializer tasks. Artifacts:
  `/tmp/j3-data-034-scrapy-materialization-audit/audit.jsonl`,
  `/tmp/j3-data-034-scrapy-materialization-audit/report.md`, and
  `docs/DATA_034_SCRAPY_7293_MATERIALIZATION_COVERAGE_AUDIT_2026-05-18.md`.
- `DATA-033`: refreshed candidate-readiness for exactly
  `scrapy__scrapy-issue-7293-pr-7351` using DATA-030 preflight evidence and
  DATA-031 prompt/spec plus local-knowledge evidence. The row is
  `ready_for_candidate_attempt` with no missing-evidence labels, validation
  command `pytest tests/test_pqueues.py -q`, evidence counts
  `{"prompt_spec":1,"validation":1,"local_knowledge":6}`, and residual labels
  `materialization_gap` and `ranking_gap`. Allowed write scope is exactly
  `scrapy/pqueues.py` and `tests/test_pqueues.py`, with no auxiliary paths.
  Artifacts: `/tmp/j3-data-033-scrapy-readiness/readiness.jsonl` and
  `/tmp/j3-data-033-scrapy-readiness/report.md`.
- `DATA-031`: added normalized prompt/spec and local-knowledge evidence for
  exactly `scrapy__scrapy-issue-7293-pr-7351` with no candidate edits. The
  prompt/spec row covers the `_active_downloads` issue framing, observed versus
  expected queue behavior, affected `DownloaderAwarePriorityQueue` and
  `DownloaderInterface` surface, reproduction input shape, acceptance-test
  shape, downloader-aware slot tie-breaking, active-download count semantics,
  and priority queue ordering reproduction. The local-knowledge JSONL emits
  six records covering changed-file context for `scrapy/pqueues.py` and
  `tests/test_pqueues.py`, the DATA-030 focused validation recipe, Scrapy
  downloader-aware priority queue behavior, slot active-download accounting,
  pqueue test patterns, provenance, validation split labels, and remaining
  readiness blockers. Artifacts:
  `/tmp/j3-data-031-scrapy-7293-evidence/spec.jsonl`,
  `/tmp/j3-data-031-scrapy-7293-evidence/spec.md`,
  `/tmp/j3-data-031-scrapy-7293-evidence/knowledge.jsonl`, and
  `docs/DATA_031_SCRAPY_7293_PROMPT_SPEC_KNOWLEDGE_2026-05-18.md`.
- `DATA-032`: isolated the pip validation-split blocker for exactly
  `pypa__pip-issue-12018-pr-13886` with no candidate edits. The bounded
  recipe attempt used setup `python -m pip install -e . installer`, explicitly
  adding `installer`, then reran `pytest tests/functional/test_install_reqs.py
  -q` against repo-before checkout `8df7b668b3766e1d4a71246509d64aeec47a805b`.
  Checkout, ref verification, and setup passed, but validation still failed
  while importing `tests/conftest.py`: `scripttest` is the next missing module.
  Runtime was `5.141s`; first failed stage is `validation`, command
  classification is `dependency_fixture_setup_failure`, evidence acquisition
  status is `blocked_on_validation_recipe`, and the row remains blocked rather
  than ready for prompt/spec/local-knowledge acquisition. Artifacts:
  `/tmp/j3-data-032-pip-validation-recipe/attempts-data-032.jsonl`,
  `/tmp/j3-data-032-pip-validation-recipe/report-data-032.md`, and
  `docs/DATA_032_PIP_VALIDATION_RECIPE_ISOLATION_2026-05-18.md`.
- `DATA-029`: added a bounded source/test candidate attempt for exactly
  `pytest-dev__pytest-issue-14462-pr-14466`. The live pinned pytest checkout
  at `fbab7c5dfe63a22f545207e8dc163ed61ad51d98` changed only
  `src/_pytest/python_api.py` and `testing/python/approx.py`; the generated
  diff matches accepted PR commit
  `2c555d62fa2c51ccb0c4c1cdd6243149ce4ffa97` for both touched paths
  (`31`/`12` and `95`/`5`). Focused validation passed with
  `python -m py_compile src/_pytest/python_api.py && pytest
  testing/python/approx.py -q` in `2.601s` (`130 passed`). Candidate JSON
  records actions, candidate diff, mutation scope, DATA-018/026/027/028
  provenance, residual label `candidate_validation_passed`, structured-action
  coverage, and `accepted_edit_covered = true`. Artifacts:
  `/tmp/j3-data-029-pytest-14462-source-test/candidate.json`,
  `/tmp/j3-data-029-pytest-14462-source-test/report.md`, and
  `docs/DATA_029_PYTEST_14462_SOURCE_TEST_CANDIDATE_2026-05-18.md`.
- `DATA-030`: ran validation-split issue/PR preflight for
  `pypa__pip-issue-12018-pr-13886` and
  `scrapy__scrapy-issue-7293-pr-7351` with no candidate edits. Pip checkout
  and setup passed, but baseline validation failed on missing `installer`
  during `tests/conftest.py` import, so the row is blocked on validation
  recipe/dependency setup rather than edit quality. Scrapy checkout, setup,
  and baseline validation passed (`11 passed, 2 skipped`) and is the next
  validation-split row ready for prompt/spec and local-knowledge acquisition.
  Artifacts:
  `/tmp/j3-data-030-validation-preflight/outcomes-data-030.jsonl`,
  `/tmp/j3-data-030-validation-preflight/report-data-030.md`, and
  `docs/DATA_030_VALIDATION_SPLIT_PREFLIGHT_2026-05-18.md`.
- `DATA-028`: added a materialization coverage audit for exactly
  `pytest-dev__pytest-issue-14462-pr-14466`. Both accepted paths,
  `src/_pytest/python_api.py` and `testing/python/approx.py`, require
  constrained local generator/source-region action coverage before candidate
  generation; no path is covered by the current structured-action surface.
  The audit records manifest, DATA-018, and DATA-026 provenance, accepted
  diff stats (`31`/`12` and `95`/`5`), validation costs, likely failure
  modes, and smallest next falsifiable materializer tasks. Artifacts:
  `/tmp/j3-data-028-pytest-14462-materialization-audit/audit.jsonl`,
  `/tmp/j3-data-028-pytest-14462-materialization-audit/report.md`, and
  `docs/DATA_028_PYTEST_14462_MATERIALIZATION_COVERAGE_AUDIT_2026-05-18.md`.
- `DATA-027`: refreshed candidate-readiness for exactly
  `pytest-dev__pytest-issue-14462-pr-14466` using DATA-018 preflight and
  DATA-026 prompt/spec/local-knowledge evidence. The row is
  `ready_for_candidate_attempt` with no missing-evidence labels, validation
  command `pytest testing/python/approx.py -q`, evidence counts
  `{"prompt_spec":1,"validation":1,"local_knowledge":6}`, and residual labels
  `materialization_gap` and `ranking_gap`. Allowed write scope is exactly
  `src/_pytest/python_api.py` and `testing/python/approx.py`, with no
  auxiliary paths; materialization and ranking remain the next-stage
  challenges before any candidate attempt. Artifacts:
  `/tmp/j3-data-027-pytest-14462-readiness/readiness.jsonl` and
  `/tmp/j3-data-027-pytest-14462-readiness/report.md`.
- `DATA-025`: added deterministic pytest #14442 auxiliary materializers and a
  full-scope candidate mode. The live pinned pytest checkout at
  `8f81c76744daf72d4f77cfc8423f4bdc60733d78` changed exactly `AUTHORS`,
  `changelog/14442.bugfix.rst`, `src/_pytest/config/__init__.py`,
  `testing/test_config.py`, and `testing/test_mark.py`. Focused validation
  passed with `pytest testing/test_config.py testing/test_mark.py -q` in
  `6.083s`; py_compile passed for the touched Python files. Candidate JSON
  records auxiliary actions, candidate diff, mutation scope, DATA-021/023/024
  provenance, residual label `candidate_validation_passed`, structured-action
  coverage, and `accepted_edit_covered = true`. Artifacts:
  `/tmp/j3-data-025-pytest-14442-full-scope/candidate.json`,
  `/tmp/j3-data-025-pytest-14442-full-scope/report.md`, and
  `docs/DATA_025_PYTEST_14442_FULL_SCOPE_CANDIDATE_2026-05-18.md`.
- `DATA-026`: added normalized prompt/spec and local-knowledge evidence for
  exactly `pytest-dev__pytest-issue-14462-pr-14466`. The prompt/spec row covers
  minimal reproduction, observed behavior, expected behavior, affected
  `pytest.approx` / `_pytest.python_api.ApproxTimedelta` surface, input shape,
  acceptance test shape, relative tolerance semantics, and datetime/timedelta
  comparison behavior. The local-knowledge JSONL emits six rows covering
  changed-file context for `src/_pytest/python_api.py` and
  `testing/python/approx.py`, the DATA-018 focused validation recipe,
  `ApproxTimedelta` tolerance behavior, datetime/timedelta comparison behavior,
  repo test patterns, provenance, and remaining readiness blockers. Artifacts:
  `/tmp/j3-data-026-pytest-14462-evidence/spec.jsonl`,
  `/tmp/j3-data-026-pytest-14462-evidence/spec.md`,
  `/tmp/j3-data-026-pytest-14462-evidence/knowledge.jsonl`, and
  `docs/DATA_026_PYTEST_14462_PROMPT_SPEC_KNOWLEDGE_2026-05-18.md`. Remaining
  blockers are materialization and ranking evidence before a candidate attempt.
- `DATA-024`: added a bounded source/test-only pytest #14442 candidate attempt
  for exactly `pytest-dev__pytest-issue-14442-pr-14443`. The live pinned
  pytest checkout at `8f81c76744daf72d4f77cfc8423f4bdc60733d78` changed only
  `src/_pytest/config/__init__.py`, `testing/test_config.py`, and
  `testing/test_mark.py`, with no `AUTHORS` or
  `changelog/14442.bugfix.rst` writes. The candidate record includes actions,
  candidate diff, mutation scope, DATA-018/021/022/023 provenance, validation
  command/runtime/pass-fail, and structured-action coverage. Focused live
  validation passed with `pytest testing/test_config.py testing/test_mark.py
  -q` after installing the checkout, while full accepted-edit coverage remains
  false with residual `accepted_auxiliary_paths_not_materialized`. Artifacts:
  `/tmp/j3-data-024-pytest-14442-source-test/candidate.json`,
  `/tmp/j3-data-024-pytest-14442-source-test/report.md`, and
  `docs/DATA_024_PYTEST_14442_SOURCE_TEST_CANDIDATE_2026-05-18.md`.
- `MODEL-006`: added a shadow-only candidate-change observation normalizer and
  wired nested candidate-after / AST-delta metadata into transition
  action-choice change context and persisted candidate-ranker record features.
  Issue/PR candidate records with `candidate_diff` summaries and nested
  source/test candidate-after AST deltas now expose diff-size,
  `candidate_after_available`, and AST-delta scorer inputs. Focused tests cover
  wrapper/behavior residual-style candidates and issue/PR candidate records.
- `DATA-023`: added a machine-readable materialization coverage audit for the
  accepted `pytest-dev__pytest-issue-14442-pr-14443` diff. All five accepted
  paths were classified before any candidate edit: `AUTHORS` is covered by a
  small proposed deterministic sorted-entry inserter, while
  `changelog/14442.bugfix.rst`, `src/_pytest/config/__init__.py`,
  `testing/test_config.py`, and `testing/test_mark.py` require constrained
  local generator/source-region or pytest-test refiner actions. The audit
  records manifest, DATA-018, DATA-021 prompt/spec, DATA-021 local-knowledge,
  accepted diff stats, validation cost, likely failure mode, and the smallest
  next falsifiable materializer task for each path. Artifacts:
  `/tmp/j3-data-023-pytest-14442-materialization-audit/audit.jsonl`,
  `/tmp/j3-data-023-pytest-14442-materialization-audit/report.md`, and
  `docs/DATA_023_PYTEST_14442_MATERIALIZATION_COVERAGE_AUDIT_2026-05-18.md`.
- `DATA-022`: refreshed candidate-readiness for exactly
  `pytest-dev__pytest-issue-14442-pr-14443` using DATA-018 preflight evidence
  and DATA-021 prompt/spec plus local-knowledge evidence. The row is
  `ready_for_candidate_attempt` with no missing-evidence labels, validation
  command `pytest testing/test_config.py testing/test_mark.py -q`, evidence
  counts `{"prompt_spec":1,"validation":1,"local_knowledge":7}`, and residual
  labels `materialization_gap` and `ranking_gap`. It explicitly records that
  source/test candidate scope covers `src/_pytest/config/__init__.py`,
  `testing/test_config.py`, and `testing/test_mark.py`, while full
  accepted-edit scope also includes `AUTHORS` and
  `changelog/14442.bugfix.rst`; the next-stage materialization challenge is
  auxiliary materializers or an explicit source/test-only scope decision, plus
  ranking against decoys. Artifacts:
  `/tmp/j3-data-022-readiness-refresh/readiness.jsonl`,
  `/tmp/j3-data-022-readiness-refresh/report.md`, and
  `docs/DATA_022_PYTEST_ISSUE_PR_READINESS_REFRESH_2026-05-18.md`.
- `DATA-021`: added normalized prompt/spec evidence and pytest local-knowledge
  extraction for exactly `pytest-dev__pytest-issue-14442-pr-14443`. The
  prompt/spec row covers minimal reproduction, observed behavior, expected
  behavior, affected API/surface, input shape, acceptance test shape, strict
  addopts behavior, and strict markers/config semantics. The local-knowledge
  JSONL emits seven records covering changed-file context for `AUTHORS`,
  `changelog/14442.bugfix.rst`, `src/_pytest/config/__init__.py`,
  `testing/test_config.py`, and `testing/test_mark.py`, plus DATA-018 focused
  validation, repo test patterns, changelog/AUTHORS conventions, provenance,
  and split. No candidate source edits were attempted. Artifacts:
  `/tmp/j3-data-021-pytest-14442-spec.jsonl`,
  `/tmp/j3-data-021-pytest-14442-spec.md`,
  `/tmp/j3-data-021-pytest-14442-knowledge.jsonl`, and
  `docs/DATA_021_PYTEST_STRICT_ADDOPTS_EVIDENCE_2026-05-18.md`. Remaining
  blockers are candidate-readiness refresh, ranking evidence, and deciding
  whether a future attempt is source/test-only or includes auxiliary
  materializers for `AUTHORS` and `changelog/14442.bugfix.rst`.
- `DATA-020`: added the integrated Click docs materializer for exactly
  `pallets__click-issue-2745-pr-3364`. It materialized the DATA-019
  `docs/commands.md` section together with the DATA-017 `docs/conf.py`
  `myst_heading_anchors = 3` assignment, with duplicate detection and compile
  validation for the config edit. The live pinned checkout changed only
  `docs/commands.md` and `docs/conf.py`; Sphinx docs validation passed in
  `3.068s` with residual labels
  `docs_commands_section_materialized`,
  `sphinx_conf_assignment_materialized`, and `docs_validation_passed`.
  Artifacts: `/tmp/j3-data-020-live/candidate.json`,
  `/tmp/j3-data-020-live/report.md`, and
  `docs/DATA_020_CLICK_DOCS_CONF_INTEGRATED_VALIDATION_2026-05-18.md`.
- `DATA-019`: added a bounded Click command-docs materializer for exactly
  `pallets__click-issue-2745-pr-3364`. It generated and inserted only the
  `docs/commands.md` `### Multi-value parameters` section before
  `## Context Defaults`, mentioned `nargs > 1` and the `{class}` role for
  `Tuple`, included a whitespace-splitting example, preserved unrelated docs
  content, and changed no source, test, changelog, or config files in the live
  pinned checkout. Docs validation was attempted with Sphinx after installing
  docs dependencies and blocked in `2.887s` with
  `docs_reference_resolution_failure` because the `options.md` heading link
  requires the separate DATA-017 `docs/conf.py` `myst_heading_anchors = 3`
  auxiliary edit. Artifacts: `/tmp/j3-data-019-live/candidate.json`,
  `/tmp/j3-data-019-live/report.md`, and
  `docs/DATA_019_CLICK_COMMANDS_DOCS_MATERIALIZER_2026-05-18.md`.
- `DATA-018`: ran the next-batch pytest issue/PR replay preflight with no
  candidate edits for `pytest-dev__pytest-issue-14442-pr-14443`,
  `pytest-dev__pytest-issue-14462-pr-14466`, and
  `pytest-dev__pytest-issue-14381-pr-14382`. All three rows checked out,
  installed with `python -m pip install -e . pytest`, and passed baseline
  validation; first failed stage is `none` for every row. The remaining
  blockers are pre-edit evidence gaps: local knowledge for #14442/#14443 and
  #14462/#14466, and prompt/spec normalization for #14381/#14382. Artifacts:
  `/tmp/j3-data-018-pytest-preflight/outcomes.jsonl`,
  `/tmp/j3-data-018-pytest-preflight/report.md`, and checked-in report
  `docs/DATA_018_PYTEST_ISSUE_PR_PREFLIGHT_2026-05-18.md`. First next row:
  normalize/acquire local knowledge for
  `pytest-dev__pytest-issue-14442-pr-14443`; no pytest row is candidate-ready
  yet.
- `DATA-016`: added a bounded Click semver/non-string default candidate-attempt
  path for exactly `pallets__click-issue-3298-pr-3299`. The live `/tmp`
  attempt on repo-before `04ef3a6f473deb2499721a8d11f92a7d2c0912f2`
  materialized the accepted source guard in `src/click/core.py` with the
  source-region action and replaced
  `tests/test_options.py::test_show_default_with_empty_string` with the
  accepted `_StrictEq` parametrized regression. The candidate changed only
  `src/click/core.py` and `tests/test_options.py`, stayed inside the
  DATA-015/DATA-010 allowlist, cited DATA-013 prompt/spec evidence, DATA-015
  readiness evidence, and eight KNOW-004 local-knowledge records, ran
  `python -m pip install -e . pytest` plus `pytest tests/test_options.py -q`,
  and passed with recorded validation runtime `1.296s`. Structured-action
  coverage marks the accepted source/test edit covered with no materialization
  gap, limited to this bounded DATA-016 surface. Artifacts:
  `/tmp/j3-data-016-live/candidate.json` and
  `/tmp/j3-data-016-live/report.md`.
- `DATA-017`: added a machine-readable auxiliary materialization-gap audit for
  the DATA-014 Click #2745 accepted auxiliary paths. The audit rows classify
  `CHANGES.rst` and `docs/conf.py` as covered by small proposed deterministic
  actions, classify `docs/commands.md` as requiring a constrained local
  generator, record manifest and DATA-014 candidate provenance, validation
  cost, likely failure mode, and the smallest next falsifiable materializer
  task for each path. Artifacts: `/tmp/j3-data-017-aux-gap/audit.jsonl` and
  `/tmp/j3-data-017-aux-gap/report.md`; checked-in report:
  `docs/DATA_017_CLICK_AUXILIARY_MATERIALIZATION_GAP_2026-05-18.md`.
- `DATA-014`: added a bounded Click default_map candidate-attempt path for
  exactly `pallets__click-issue-2745-pr-3364`. The live `/tmp` attempt on
  repo-before `8a2b48901a08b3d2ec3a9bbd151948a9765368c6` materialized the
  source insertion in `src/click/core.py` with the existing delimited
  source-region action and inserted
  `tests/test_defaults.py::test_default_map_nargs` with a deterministic
  pytest-function insertion. The candidate changed only `src/click/core.py`
  and `tests/test_defaults.py`, stayed inside the DATA-010 allowlist, ran
  `python -m pip install -e . pytest` plus `pytest tests/test_defaults.py -q`,
  and passed with `39 passed in 0.03s` and `1.106s` total recorded validation
  runtime. The source/test behavior is covered, but the full accepted edit is
  not: `CHANGES.rst`, `docs/commands.md`, and `docs/conf.py` remain an
  explicit `accepted_auxiliary_paths_not_materialized` gap because the current
  structured-action surface has no changelog/docs/Sphinx config materializer.
  Artifacts: `/tmp/j3-data-014-live/candidate.json` and
  `/tmp/j3-data-014-live/report.md`.
- `DATA-015`: reran the first-three issue/PR readiness gate with DATA-013
  Click semver prompt/spec evidence included. All three rows are now
  `ready_for_candidate_attempt` with no missing-evidence labels. Validation
  commands are the DATA-008 Requests focused command, `pytest
  tests/test_defaults.py -q` for Click #2745, and `pytest
  tests/test_options.py -q` for Click #3298. Residual labels remain
  `materialization_gap` and `ranking_gap` for all three rows, so the next
  recommended candidate attempt is `pallets__click-issue-3298-pr-3299` after
  DATA-014 is reviewed. Report:
  `docs/DATA_015_ISSUE_PR_READINESS_REFRESH_2026-05-18.md`; smoke JSONL:
  `/tmp/j3-data-015-readiness-smoke.jsonl`.
- `DATA-012`: added a bounded Requests issue/PR candidate-attempt runner for
  exactly `psf__requests-issue-7432-pr-7433`. The live `/tmp` attempt
  materialized the accepted source-region edit in `src/requests/models.py`,
  inserted the redirect regression test in `tests/test_requests.py`, changed
  only DATA-010 allowlisted paths, ran the DATA-008 setup plus focused
  validation recipe, and passed with `6 passed, 333 deselected` in `7.224s`
  total recorded validation runtime. The candidate record reports
  `candidate_validation_passed`, no hosted LLM use, no writes outside the
  allowlist, and accepted-edit coverage by the bounded source-region plus
  deterministic pytest-method insertion surface. Artifacts:
  `/tmp/j3-data-012-live/candidate.json` and
  `/tmp/j3-data-012-live/report.md`.
- `DATA-013`: added machine-readable prompt/spec normalization for
  `pallets__click-issue-3298-pr-3299` without candidate source edits. The
  record captures the semver `Version(1, 0, 0)` minimal reproduction,
  observed help-rendering failure from comparing a non-string default to `""`,
  expected string-guarded empty-string behavior, affected
  `click.core.Option.get_help_extra` surface, input shape, acceptance test
  shape with `_StrictEq`, non-string default behavior, type-conversion
  semantics, empty-string check scope, third-party semver context, and
  provenance back to issue #3298, PR #3299, the PR diff, and KNOW-004 local
  knowledge. JSONL: `/private/tmp/j3-data-013-click-semver-spec.jsonl`;
  report: `/private/tmp/j3-data-013-click-semver-spec.md`.
- `DATA-010`: added an issue/PR candidate-readiness gate that consumes
  DATA-007 preflight evidence, DATA-008 validation, DATA-009/DATA-011
  prompt/spec records, and KNOW-004/KNOW-005 local-knowledge JSONL. The first
  three replay rows now emit one readiness row each with evidence ids/sources,
  missing-evidence labels, allowed write scope, validation command, residual
  labels, and a recommendation. Current smoke result: Requests #7432/#7433 and
  Click #2745/#3364 are `ready_for_candidate_attempt`; Click #3298/#3299
  remains blocked on missing prompt/spec fields. Materialization and ranking
  remain explicit next-stage challenges for all three rows. Report:
  `docs/DATA_010_ISSUE_PR_READINESS_GATE_2026-05-18.md`; JSONL:
  `/tmp/j3-data-010-readiness.jsonl`.
- `DATA-011`: added machine-readable prompt/spec normalization for
  `psf__requests-issue-7432-pr-7433` without candidate source edits. The
  `issue_pr_prompt_spec` record captures the minimal reproduction, observed
  repo-before `_body_position` gap, expected redirect-safe stream behavior,
  affected `requests.PreparedRequest.prepare_body` surface, input shape,
  acceptance test shape, `__getattr__` file-wrapper behavior, stream detection
  semantics, redirect/rewind behavior, field provenance, and nonblocking
  unavailable source-text gaps for the unchecked-in issue body and PR
  conversation. JSONL: `/private/tmp/j3-data-011-requests-prepare-body-spec.jsonl`;
  report: `/private/tmp/j3-data-011-requests-prepare-body-spec.md`.
- `KNOW-005`: added a narrow Requests replay local-knowledge extractor and CLI
  smoke path for `psf__requests-issue-7432-pr-7433`. The emitted records cover
  changed-file context for `src/requests/models.py` and
  `tests/test_requests.py`, the DATA-008 focused validation recipe,
  `PreparedRequest.prepare_body` stream detection and body-position tracking,
  `__getattr__`-based file-wrapper behavior, redirect/rewind semantics through
  `resolve_redirects` and `rewind_body`, pytest-httpbin/trustme fixture setup,
  and ranking-relevant source/test patterns. Smoke artifact:
  `/tmp/j3-know-005-requests-records.jsonl`.
- `DATA-009`: added machine-readable prompt/spec normalization for
  `pallets__click-issue-2745-pr-3364` without candidate source edits. The
  `issue_pr_prompt_spec` record captures the minimal reproduction, observed
  Click 8 error, expected environment-variable-style splitting behavior,
  affected `click.Context.default_map` / `click.core.Option.consume_value`
  surface, input shape, acceptance test shape, callback-time `default_map`
  mutation, multi-value parameter forms, string-splitting semantics, and
  provenance back to issue #2745, PR #3364, and the PR diff. JSONL:
  `/private/tmp/j3-data-009-click-default-map-spec.jsonl`; report:
  `docs/DATA_009_CLICK_DEFAULT_MAP_PROMPT_SPEC_2026-05-18.md`.
- `DATA-008`: isolated a hermetic Requests validation recipe for
  `psf__requests-issue-7432-pr-7433` without candidate code edits. The
  recursive `httpbin` failure came from the DATA-006 setup command missing
  Requests' `pytest-httpbin`/`httpbin` fixture dependencies. The final
  candidate-free recipe creates an in-checkout `.venv`, installs `-e .`,
  `pytest`, `pytest-httpbin==2.1.0`, `httpbin~=0.10.0`, and `trustme`, then
  runs `.venv/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body
  or rewind_body or getattr_proxy_stream_follows_redirect'`. The repo-before
  smoke passed with `5 passed, 333 deselected`; the accepted merge diagnostic
  passed with `6 passed, 333 deselected`, proving the selector includes the
  issue-specific test once present. Report:
  `docs/DATA_008_REQUESTS_VALIDATION_RECIPE_2026-05-18.md`; JSONL:
  `/tmp/j3-data-008-live/attempts.jsonl`.
- `KNOW-004`: added a narrow Click replay local-knowledge extractor and CLI
  smoke path for `pallets__click-issue-3298-pr-3299`. The emitted records cover
  repo changed-file context, repo test pattern, focused validation recipe,
  Click parameter default handling, type-conversion semantics, non-string
  default handling, empty-string check semantics, and third-party
  `semver.Version` reproduction context, all linked to the replay row with
  provenance hashes and split `train`. Smoke artifact:
  `/tmp/j3-know-004-click-records.jsonl`.
- `REAL-012`: reran the full one-file feature shadow score after `MAT-006`,
  counting `iniconfig-feature-section-default`,
  `h11-feature-bytesify-object-message`,
  `humanize-feature-naturalsize-zero-format`, and
  `boltons-feature-slugify-max-length` through
  `j3.real_repo_feature_materializer`. The live `/tmp` run against all four
  pinned checkouts scored `pass@1 = 4/4` and `pass@3 = 4/4`; calibration
  pass@3 is `1/1`, held-out pass@3 is `3/3`, first passing ranks are
  `[1, 1, 1, 1]`, candidate validation is `passed = 4`, four distinct repos
  pass, mutation-scope violations are zero, hidden-like agreement is `4/4`,
  and zero hosted usage is confirmed. The guarded one-file feature opt-in
  scope is limited to those four task ids under task allowlists, one
  allowlisted production file, passing validation, and no hidden-like
  disagreement. Report:
  `docs/REAL_012_ONE_FILE_FEATURE_SHADOW_SCORE_2026-05-18.md`.
- `DATA-007`: added issue/PR replay blocker drilldown support to the preflight
  outcome schema, JSONL reprocessing mode, summary counts, and compact report.
  The DATA-006 first batch now classifies Requests
  `psf__requests-issue-7432-pr-7433` as
  `dependency_fixture_setup_failure` with recursive `httpbin` fixture evidence,
  Click `pallets__click-issue-2745-pr-3364` as
  `prompt_spec_incomplete` with missing reproduction, expected/observed
  behavior, affected API, input shape, acceptance test, and `default_map`
  multi-value fields, and Click `pallets__click-issue-3298-pr-3299` as
  `local_knowledge_missing` with required Click default/type-conversion,
  non-string default, empty-string check, repo test-pattern, validation, and
  changed-file context categories. Report:
  `docs/DATA_007_ISSUE_PR_BLOCKER_DRILLDOWN_2026-05-18.md`; enhanced JSONL:
  `/tmp/j3-data-007-blocker-drilldown/outcomes.jsonl`.
- `MAT-006`: materialized the remaining held-out one-file source feature
  candidate for `boltons-feature-slugify-max-length`. The feature materializer
  now supports a bounded `slugify` source-region edit in `boltons/strutils.py`,
  appends focused validation coverage to `tests/test_strutils.py` for
  `max_length` truncation, avoiding trailing configured delimiters, and
  unchanged behavior without `max_length`, records source/test candidate-after
  diff and AST metadata, production hashes, mutation scope, validation runtime,
  and zero hosted usage. Live validation against the pinned boltons checkout
  under `/tmp/j3-mat-006-live.3KJIUG/boltons` passed with
  `45 passed in 0.03s`, changing only `boltons/strutils.py` among production
  files and writing nothing outside the task allowlist. Candidate record:
  `/tmp/j3-mat-006-live.3KJIUG/candidate.json`.
- `DATA-006`: added issue/PR replay batch preflight, JSONL summary, Markdown
  report support, and command runtime/stage accounting. The live first batch
  under `/tmp/j3-data-006-live-preflight` ran the first three
  `DATA-004` rows pre-edit only; all reached baseline validation, with status
  counts `{"blocked": 3}`, blocker labels
  `{"validation_baseline_failed": 1,
  "prompt_spec_ambiguous_or_incomplete": 1,
  "local_knowledge_required": 1}`, residual categories
  `{"validation": 1, "prompt_spec": 1, "local_knowledge": 1}`, command-stage
  counts showing checkout, setup, and baseline validation reached for all
  three rows, and deferred agent residual labels
  `{"ranking_gap": 3, "materialization_gap": 1}`. JSONL:
  `/tmp/j3-data-006-live-preflight/outcomes.jsonl`; compact report:
  `docs/DATA_006_ISSUE_PR_PREFLIGHT_2026-05-18.md`.
- `REAL-011`: reran the one-file feature shadow score after `MAT-004` and
  integrated the concurrent `MAT-005` humanize materializer. The live `/tmp`
  run against pinned iniconfig, h11, and humanize checkouts scored
  `pass@1 = 3/4`, `pass@3 = 3/4`, calibration pass@3 `1/1`, held-out pass@3
  `2/3`, first passing ranks `[1, 1, 1, null]`, candidate validation
  `passed = 3` and `blocked = 1`, three distinct repos passing, zero writes
  outside allowlists, zero production-file constraint violations, hidden-like
  agreement for all three passing rows, and zero hosted usage. The manifest
  gate decision is `allow_guarded_one_file_feature_opt_in` only for
  `iniconfig-feature-section-default`, `h11-feature-bytesify-object-message`,
  and `humanize-feature-naturalsize-zero-format` under task allowlists,
  one-production-file scope, passing validation, and no hidden-like
  disagreement. Boltons remains an explicit `one_file_materialization_gap`
  blocker.
- `MAT-005`: materialized the next held-out one-file source feature candidate
  for `humanize-feature-naturalsize-zero-format`. The feature materializer now
  supports a bounded `naturalsize` source-region edit in
  `src/humanize/filesize.py`, appends focused validation coverage to
  `tests/test_filesize.py` for custom zero output on `0` and `-0.0`, unchanged
  default zero output, and ignored `zero_format` on nonzero values, records
  source/test candidate-after diff and AST metadata, production hashes,
  mutation scope, validation runtime, and zero hosted usage. Live validation
  against the pinned humanize checkout under
  `/tmp/j3-mat-005-live.WXA9PU/humanize` passed with `73 passed in 0.03s`,
  changing only `src/humanize/filesize.py` among production files and writing
  nothing outside the task allowlist. Candidate record:
  `/tmp/j3-mat-005-live.WXA9PU/candidate.json`.
- `MAT-004`: materialized the second real one-file source feature candidate for
  `iniconfig-feature-section-default`. The existing feature materializer now
  supports the calibration iniconfig task with one bounded delimited source
  region in `src/iniconfig/__init__.py`, appends focused validation coverage
  to `testing/test_iniconfig.py`, records source/test candidate-after diff and
  AST metadata, production hashes, mutation scope, validation runtime, and zero
  hosted usage. Live validation against the pinned iniconfig checkout under
  `/tmp/j3-mat-004-live/iniconfig` passed with `51 passed in 0.03s`, changing
  only `src/iniconfig/__init__.py` among production files and writing nothing
  outside the task allowlist. Candidate record:
  `/tmp/j3-mat-004-live/candidate.json`.
- `REAL-010`: reran the tests-only shadow score after `GS7-011`, counting
  `iniconfig-tests-parse-comments`, `h11-tests-bytesify-memoryview`,
  `humanize-tests-naturalsize-negative-strings`, and
  `boltons-tests-slugify-delimiter` through the real-repo tests planner
  surface. The live `/tmp` run against pinned checkouts scored
  `pass@1 = 4/4`, `pass@3 = 4/4`, calibration pass@3 `1/1`, held-out pass@3
  `3/3`, first passing ranks `[1, 1, 1, 1]`, candidate validation
  `passed = 4`, zero production-file modifications, zero writes outside
  allowlists, zero candidate target path violations, hidden-like agreement for
  all four passing rows, and zero hosted usage. The gate decision remains
  `allow_guarded_tests_only_opt_in` for the four materialized,
  validation-passing tests-only task ids inside task allowlists.
- `REAL-008`: reran the tests-only shadow score after `GS7-010`, counting
  `iniconfig-tests-parse-comments`, `h11-tests-bytesify-memoryview`, and
  `humanize-tests-naturalsize-negative-strings` through the real-repo tests
  planner surface. The live `/tmp` run against pinned checkouts scored
  `pass@1 = 3/4`, `pass@3 = 3/4`, calibration pass@3 `1/1`, held-out pass@3
  `2/3`, first passing ranks `[1, 1, 1, null]`, candidate validation
  `passed = 3` and `blocked = 1`, zero production-file modifications, zero
  writes outside allowlists, zero candidate target path violations,
  hidden-like agreement for all three passing rows, and zero hosted usage.
  The gate decision is `allow_guarded_tests_only_opt_in` for materialized,
  validation-passing tests-only candidates within task allowlists; boltons
  remains an explicit `test_case_materialization_gap` blocker in this score.
- `GS7-011`: materialized the remaining held-out tests-only candidate for
  `boltons-tests-slugify-delimiter`. The planner selects
  `tests/test_strutils.py` from repo-state plus local-knowledge evidence,
  requires the selected test file to import public `strutils` from `boltons`,
  appends pytest-discoverable coverage for custom delimiters, empty strings,
  ascii bytes output, and `lower=False`, records candidate-after metadata and
  validation command, emits residual and knowledge-use records, and preserves
  production files byte-for-byte. Live validation against the pinned boltons
  checkout under `/tmp/j3-gs7-011-boltons-live.VrqnqZ/boltons` passed with
  `20 passed in 0.03s`, changing only `tests/test_strutils.py` and no
  production files.
- `REAL-009`: scored the `MAT-003` h11 one-file feature candidate against the
  full one-file feature ladder with the new
  `j3.real_repo_feature_shadow_score` command. The live `/tmp` run against the
  pinned h11 checkout counted `h11-feature-bytesify-object-message` through
  `j3.real_repo_feature_materializer`, validated it with
  `python -m pytest h11/tests/test_util.py -q`, and scored
  `pass@1 = 1/4`, `pass@3 = 1/4`, one distinct repo passing, one production
  file changed within the one-file constraint, zero writes outside allowlists,
  zero mutation-scope violations, hidden-like agreement for h11, and zero
  hosted usage. The unsupported `iniconfig`, `humanize`, and `boltons`
  feature tasks remain explicit `one_file_materialization_gap` blockers, so
  the one-file feature gate remains `remain_shadow_only`.
- `GS7-010`: materialized the next held-out tests-only candidate for
  `humanize-tests-naturalsize-negative-strings`. The planner selects
  `tests/test_filesize.py` from repo-state plus local-knowledge evidence,
  requires the selected test file to import the public `humanize` module,
  appends pytest coverage for negative numeric strings, GNU suffix mode, and
  binary suffix mode, records candidate-after metadata and validation command,
  emits residual and knowledge-use records, and preserves production files
  byte-for-byte. Live validation against the pinned humanize checkout under
  `/tmp/j3-gs7-010-humanize-live.GzeTMj/humanize` passed with
  `79 passed in 0.03s`, changing only `tests/test_filesize.py` and no
  production files.
- `MAT-003`: materialized the first real one-file source feature candidate for
  `h11-feature-bytesify-object-message`. The new
  `j3.real_repo_feature_materializer` applies one bounded source-region edit to
  `h11/_util.py`, appends a focused object-message pytest case to
  `h11/tests/test_util.py`, records candidate-after diff/AST metadata for both
  files, preserves the one-production-file constraint, and confirms zero
  hosted usage. Live validation against the pinned h11 checkout under
  `/tmp/j3-mat-003-live/h11` passed with `7 passed in 0.01s`; the candidate
  record is `/tmp/j3-mat-003-live/candidate.json`.
- `REAL-007`: reran the tests-only shadow score after `GS7-009`, counting both
  `iniconfig-tests-parse-comments` and `h11-tests-bytesify-memoryview` through
  the real-repo tests planner surface. The live `/tmp` run against pinned
  checkouts scored `pass@1 = 2/4`, `pass@3 = 2/4`, calibration pass@3 `1/1`,
  and held-out pass@3 `1/3`; first passing ranks were `[1, 1, null, null]`.
  Candidate validation passed for iniconfig and h11, with zero production-file
  changes, zero writes outside allowlists, hidden-like agreement for both
  passing candidates, and zero hosted usage. `humanize` and `boltons` remain
  explicit `test_case_materialization_gap` blockers, so the gate remains
  `remain_shadow_only`.
- `REAL-006`: reran the tests-only shadow score through the GS7-008
  materialized candidate surface. The live `/tmp` run scored
  `iniconfig-tests-parse-comments` as a rank-1 passing candidate with
  candidate validation `54 passed in 0.03s`, changed only
  `testing/test_iniconfig.py`, changed zero production files, wrote nothing
  outside the allowlist, recorded hidden-like agreement, and confirmed zero
  hosted usage. Held-out `h11`, `humanize`, and `boltons` rows remained
  explicit `test_case_materialization_gap` blockers for this scorer run, so
  the gate stayed `remain_shadow_only` at `pass@1 = 1/4` and `pass@3 = 1/4`.
- `GS7-009`: materialized the first held-out tests-only candidate for
  `h11-tests-bytesify-memoryview`. The planner selects
  `h11/tests/test_util.py` from repo-state plus manifest/local-knowledge
  evidence, requires the existing `bytesify` import from `.._util`, appends
  pytest coverage for bytearray, memoryview, ASCII str, non-ASCII str, and int
  TypeError behavior, emits candidate-after/mutation-scope/validation/residual
  and knowledge-use metadata, and preserves production files byte-for-byte.
  Live validation against a cloned pinned checkout under
  `/tmp/j3-gs7-009-h11-live.HVzhOM/h11` passed with `11 passed in 0.02s`,
  changing only `h11/tests/test_util.py` and no production files.
- `GS7-008`: materialized the `iniconfig-tests-parse-comments` calibration
  candidate into `testing/test_iniconfig.py` with pytest cases for
  comment-only lines, inline section comments, and duplicate key error
  reporting. The candidate record now includes candidate-after diff/hash
  metadata, actual mutation scope, validation command, knowledge citations,
  residual labels, and protected production hashes. Live validation against a
  cloned pinned checkout under `/tmp/j3-gs7-008-iniconfig.TdMlTU/iniconfig`
  passed with `54 passed in 0.03s`, changing only `testing/test_iniconfig.py`.
- `REAL-005`: ran live baseline preflight for held-out `h11` and `humanize`.
  Checkout, setup, baseline validation, and allowed-write preflight checks all
  passed for 4 task rows in 8.047 seconds with `blocker_label = none`; JSONL is
  under `/tmp/j3-real-005-gate-a-preflight/outcomes.jsonl` and the compact
  report is `docs/REAL_005_GATE_A_PREFLIGHT_2026-05-18.md`. Combined with
  `REAL-004` `iniconfig`, Gate A now has three repositories passing baseline
  validation. `boltons` remains untested by this run because the threshold was
  already met.
- `GS7-007`: added `j3/real_repo_tests_planner.py` and a synthetic
  manifest-derived `iniconfig` checkout test. The planner consumes repo-state
  coverage plus local knowledge records to select `testing/test_iniconfig.py`,
  records import-style evidence from `from iniconfig import IniConfig,
  ParseError`, protects `src/iniconfig/__init__.py` with before hashes, emits
  the targeted validation command, cites pytest layout, public API, validation,
  and pytest pattern knowledge, and honestly blocks on
  `test_case_materialization_gap` instead of claiming a passing candidate.
- `REAL-004`: added minimal `iniconfig` subset/CLI support for
  `j3.real_repo_preflight`, ran the live preflight against the pinned
  `pytest-dev/iniconfig` checkout, and recorded
  `docs/REAL_004_LIVE_PREFLIGHT_2026-05-18.md`. Result: 2 task rows, checkout,
  setup, and baseline validation all passed, runtime 3.119 seconds,
  `blocker_label = none`, JSONL at
  `/tmp/j3-real-004-live-preflight/outcomes.jsonl`. The evidence proves the
  live path for one calibration repo but not the full Gate A requirement of at
  least three baseline-passing repos.
- `GS7-006`: added `j3/existing_repo_conventions.py` for the narrow shadow
  source-convention slice. The `slugify_existing_src_convention` GreenShot-7
  task now materializes a tiny `src/acme_slug` fixture, uses repo-state
  coverage to confirm package files, imports, tests, configs, and the
  `slugify` function, edits only `src/acme_slug/__init__.py`, validates the
  package-level export with targeted pytest, and emits a structured
  `greenshot_7_existing_repo_convention_attempt` row with changed files,
  validation commands, repo-state evidence, and source-edit scope.
- `REAL-003`: added `j3/real_repo_shadow_score.py`, focused tests, and
  `docs/REAL_003_TESTS_ONLY_SHADOW_SCORE_2026-05-18.md`. The first tests-only
  wedge shadow score used the four `REAL-001` tests-only ladder tasks with max
  three candidates and recorded `pass@1 = 0/4`, `pass@3 = 0/4`, no first
  passing ranks, no candidate validation runtime because no candidates were
  generated, zero production-file modifications, zero actual writes outside
  allowlists, hidden-like checks not run, zero hosted usage, and a
  `remain_shadow_only` gate decision. The falsifiable residual is that the
  current `GS7-005` tests-only builder is still a root `slugify.py` fixture
  slice and cannot target real-repo package/test layouts.
- `KNOW-002`: added `j3/local_knowledge.py` and focused tests for compact
  local knowledge records. The extractor emits JSONL-ready pytest layout,
  packaging layout, public API/import, validation recipe, and AST-backed pytest
  pattern records from a calibration checkout or fixture, including provenance
  hashes, split labels, source references, extractor/version fields, task and
  outcome links where available, and an example `knowledge_use_record` for
  tests-only planning citations.
- `GS7-005`: added `j3/existing_repo_tests.py` for a narrow existing-repo
  tests-only slugify action. The `slugify_tests_only_existing` GreenShot-7
  task now materializes a one-file existing repo fixture, inspects `slugify.py`,
  writes only `tests/test_slugify.py`, validates with targeted pytest, records
  target test files, changed files, production file hashes, and zero
  production-file modifications, and emits a structured
  `greenshot_7_existing_repo_tests_attempt` row.
- `DATA-005`: added `j3/issue_pr_preflight.py` and focused mocked-runner
  tests. The preflight loads a `DATA-004` mini replay row by id, clones and
  checks out `repo_before_ref` through an injectable subprocess runner, verifies
  the checked-out SHA, runs setup and baseline validation commands, classifies
  environment, validation, prompt/spec, and local-knowledge blockers before any
  edit attempt, defers ranking/materialization labels as agent-stage residuals,
  and emits deterministic JSONL outcome rows.
- `REAL-002`: added `j3/real_repo_preflight.py` and focused mocked-runner
  tests. The preflight loads the `REAL-001` manifest, clones and checks out
  pinned refs through an injectable command runner, runs setup and baseline
  validation with timeout fields, checks dummy candidate writes against task
  allowlists, and emits one JSONL outcome row per repo task with separate
  environment and allowed-write blocker labels.
- `MAT-002`: added `j3/source_region_materializer.py` and focused source-region
  tests for a structured `replace_function_region` action. The probe replaces a
  bounded region inside `should_bypass_proxies`, enforces AST parsing, function
  signature preservation, changed-line budgets, and default no-import-change
  constraints, and returns candidate-after changed-line, touched-region, diff,
  and AST-delta metadata.
- `WEDGE-001`: added `docs/PRODUCT_WEDGE_DECISION.md`, choosing guarded local
  tests-only maintenance for small existing Python libraries as the first
  product path. Conservative one-file source maintenance remains shadow-only
  until `MAT-002`, `GS7-006`, and `REAL-001` one-file feature gates pass. The
  decision defines the user promise, non-goals, rollout metrics, failure
  criteria, and next proof queue.
- `KNOW-001`: added `docs/LOCAL_KNOWLEDGE_INVENTORY.md`, choosing the first
  local-knowledge wedge as pytest authoring and validation, Python packaging
  and import layout, and small-library maintenance conventions. The inventory
  maps required concepts to local sources, JSONL record families, provenance
  and split rules, extraction rules, evaluation hooks, and the first three
  acquisition commands for real-repo preflight records, pytest pattern
  extraction, and issue/PR replay knowledge residual rows.
- `DATA-004`: added `docs/ISSUE_PR_MINI_REPLAY.md`,
  `examples/issue_pr_mini_replay/manifest.json`, and a schema test for 10
  curated issue/PR replay rows from Requests, Click, pytest, Poetry, pip, and
  Scrapy. The manifest records prompt text, repo-before refs, accepted PR refs,
  focused validation commands where inferable, provenance/license notes,
  stable splits, and residual labels for local knowledge, materialization,
  validation, ranking, and prompt/spec parsing blockers.
- `MAT-001`: added `docs/CODE_MATERIALIZATION_GAP.md`, classifying 25 merged
  Python PR diffs by the weakest materialization layer needed. Result: 4 fit
  current structured actions, 7 need general typed builders, 4 need
  repo-convention builders, 8 need constrained local generation, and 2 are
  out of current scope. The audit concludes the structured-action thesis is
  useful for tiny local repairs but cracking at source materialization unless
  typed builders and bounded local generators are added.
- `REAL-001`: added `docs/REAL_REPO_EVAL_LADDER.md`,
  `examples/real_repo_eval_ladder.json`, and a manifest schema test. The ladder
  pins four permissively licensed Python repos, defines tests-only and one-file
  feature tasks, records validation commands, split/leakage rules, runtime
  limits, pass/fail gates, and explicit falsifiers for real-repo
  generalization.
- `MODEL-001`: added a compact learned prompt-intent baseline report helper and
  recorded the 2026-05-18 current-corpus metrics in
  `docs/MODEL_001_PROMPT_INTENT_BASELINE_2026-05-18.md`. Current expanded
  corpus evaluation: validation exact-field 10/42 and test exact-field 9/72;
  clarification accuracy remains high at 40/42 validation and 68/72 test;
  inferred-default precision/recall is 0.000 on held-out splits because the
  positive labels are sparse and include a test-only unseen default.
- `GS7-004`: added a first-class `clarification-response-v1` outcome for
  ambiguous request-to-repo prompts. Blocked GreenShot plans, build results,
  JSONL attempt rows, and public `implement` output now carry structured
  questions while continuing to write no generated repo files.
- `REPO-001`: added an inspectable repo-state coverage section alongside the
  deterministic embedding record. Fixture coverage now reports all discovered
  files with roles, Python packages, imports, top-level functions and classes,
  pytest files, config files, likely entrypoints, docs, and parse errors while
  keeping the existing embedding metadata and aggregate fields stable.
- `ACT-001`: added `docs/ACTION_COVERAGE_MAP.md`, separating current
  transition residuals and GreenShot-7 classified gaps into supported repair
  actions, new request-to-repo action needs, ranking/scorer gaps, and
  prompt/spec or existing-repo support gaps. The map recommends tests-only
  existing-repo support and repo-state-aware library convention slices as new
  action work, while keeping transition repair residuals focused on scorer and
  observation improvements.
- `GS7-002`: added five non-calculator request-to-repo fixtures. The small
  slugify library and key/value parser now build and validate through bounded
  greenfield builders; tests-only and existing-repo convention requests are
  classified as `action_coverage` and `existing_repo_support`; the converter
  prompt is classified as `expected_clarification`.
- `DATA-003`: added a deterministic issue/PR transition manifest prototype
  backed by a small `apache/airflow` fixture. The manifest records issue/PR
  text provenance, links, before/after commit refs, stable split buckets, and
  license/terms notes without committing large harvested artifacts.
- `OPS-002`: added a lightweight plan consistency parser and focused pytest
  check for `plans/active.md` and `plans/backlog.md`. The check catches
  malformed task headings, invalid status values, active tasks missing from
  backlog, and active/backlog status drift.
- `TRANS-004`: reran targeted `greenshot_6_subset` transition matrix evidence
  after the `ACT-002` subscript-key fix. The
  `http_no_store_directive_subscript_key` production and shadow candidates now
  solve within the matrix cap at rank 1 via `change_subscript_key`, eliminating
  the candidate-generation gap. Targeted subset totals: 12 tasks, 12 ranked
  solved, 4 matrix residuals, 8 residual-report failures, all
  `scorer_ranking_gap`; targeted guarded decision remains
  `remain_shadow_only`.
- `DATA-002`: added repeatable prompt/spec corpus schema validation on top of
  the `inspect-prompt-corpus` profile path. The validator accepts the seed,
  expanded, and GreenShot-7 intent corpora with zero errors while reporting
  legacy seed expected-action gaps and cross-split near-duplicates as review
  warnings.
- `ACT-002`: fixed the subscript-key candidate cap gap for
  `greenshot_6_subset/http_no_store_directive_subscript_key`. The passing
  `change_subscript_key` candidate from `"no-store"` to `"no_store"` now ranks
  first and validates under `--max-candidates 8`; focused candidate ranking and
  patching tests passed.
- `DATA-001`: expanded `inspect-prompt-corpus` into a repeatable prompt corpus
  quality audit. Current 320-row corpus has no exact normalized duplicates,
  no unsupported scalar labels, and no family split leakage, but it has 2
  cross-split near-duplicate prompt pairs and schema consistency gaps that
  `DATA-002` should validate.
- `TRANS-002`: diagnosed the 2026-05-18 transition matrix residuals. Result:
  14 residual-report failures split into 1 candidate-generation gap
  (`change_subscript_key` for `http_no_store_directive_subscript_key`) and 13
  scorer-ranking gaps concentrated in add-keyword decoys, mapping key/value
  target confusion, boundary/literal ranking, and identifier/signature decoys.
  Diagnosis recorded in `docs/TRANSITION_MATRIX_RESIDUALS_2026-05-18.md`.
- `TRANS-001`: ran the full transition shadow matrix on 2026-05-18. Gate
  result: `remain_shadow_only`; guarded opt-in trial eligibility `false`.
  Matrix totals: 5 suites, 56 tasks, 55 ranked solved, 7 matrix residuals,
  14 residual report failures, zero hosted usage. Evidence under
  `/tmp/j3-trans-001-shadow-matrix` and `/tmp/j3-trans-001-matrix-evidence`.
- `GS7-001`: refreshed the current GreenShot-7 baseline. Result: 10 fixture
  tasks, 8 built and validation-passed, 2 intentionally blocked for
  clarification, no prompt-spec failures, missing-action failures, ranking
  failures, or generated pytest failures observed. Verification: focused
  GreenShot-7 tests plus direct `implement` CLI smoke passed.
- `OPS-001`: migrated from the daily `today*` loop to persistent coordination
  files. Verification: `git diff --check` passed.
- Previous daily loop completed transition shadow suite, residual reports,
  matrix runner, matrix evidence bundle, guarded-trial decision, and matrix docs.
  Those results remain useful, but new work should be tracked here and in
  `plans/progress.md`.
