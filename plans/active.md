# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: continuous loop mode. The active set may be empty only
  while the coordinator is recording the next assignments; ready work should be
  dispatched rather than leaving the board idle.
- Current product gate stance: targeted `greenshot_6_subset` transition
  evidence now supports a narrow guarded opt-in trial; the 2026-05-18
  `TRANS-001` full matrix, `TRANS-004` targeted subset, and 2026-05-19
  `TRANS-005` post-scorer matrix decisions were `remain_shadow_only`.
  `TRANS-005` reran the standard matrix after
  `MODEL-003` through `MODEL-005`: 56 tasks, 55 ranked solved, 8 matrix
  residuals, 17 residual-report examples, one `candidate_generation_gap`, 16
  `scorer_ranking_gap` examples, and zero hosted usage. `TRANS-006` made
  existing diff/AST metadata visible as candidate-after evidence in residual
  reporting without changing those residual counts or the shadow-only gate.
  `TRANS-007` reran only `greenshot_6_subset` after the candidate-after and
  GreenShot-6 ranking fixes: 12 tasks, 12 ranked solved, 9,696 candidates, 7
  held-out groups, 4 matrix residuals, 2 baseline residuals, 5 residual-report
  examples, no `candidate_generation_gap`, and no
  `candidate_after_unavailable` label. `MODEL-007` fixed the deterministic
  V1/advice ordering for the `project_urls_header_dict_key` residual, and
  `TRANS-008` recorded the targeted matrix rerun: the subset still covers 12
  tasks, 12 ranked solved tasks, 9,696 candidates, and 7 held-out groups, but
  now has 1 matrix residual, 2 baseline residuals, and 1 residual-report
  example. The mapping-key residual is resolved, no V1/advice residual remains
  in the report, and the suite gate improved to `ready_for_shadow_mode`.
  Guarded decision remains `remain_shadow_only`. `MODEL-008` now addresses
  the remaining `apache_license_classifier_dict_value` V3 residual's public
  assertion-diff evidence, and `TRANS-009` recorded the targeted subset
  rerun: 12 tasks, 12 ranked solved tasks, 9,696 candidates, 7 held-out
  groups, 0 matrix residuals, 2 baseline residuals, and 0 residual-report
  examples. The Apache mapping-value residual is resolved, no missing-feature
  labels remain because no residual examples remain, the suite gate reaches
  `ready_for_guarded_opt_in`, and guarded decision is
  `guarded_opt_in_trial`. That targeted result temporarily unblocked
  coordinator review for standard matrix expansion; transition advice rows
  remain shadow-only/not wired to production routing unless a guarded opt-in
  follow-up explicitly scopes that integration. `TRANS-010` then refreshed the
  full standard matrix before any manifest expansion: 5 suites, 56 tasks, 56
  ranked solved tasks, 12,413 candidates, 19 held-out groups, 4 matrix
  residuals, 4 baseline residuals, 11 residual-report examples, all
  `scorer_ranking_gap`, and zero hosted usage. `MODEL-009` added V3 local
  structural evidence for the four `TRANS-010` `v3_top_candidate_failed`
  residuals. `TRANS-011` reran the full standard matrix after `MODEL-009`: 5
  suites, 56 tasks, 56 ranked solved tasks, 12,413 candidates, 19 held-out
  groups, 0 matrix residuals, 4 baseline residuals, 7 residual-report
  examples, and zero hosted usage. `greenshot_3` improved to
  `ready_for_shadow_mode`; `greenshot_5_subset` improved to
  `ready_for_guarded_opt_in`; `greenshot_6_subset` remains
  `ready_for_guarded_opt_in`. The full standard guarded decision remains
  `remain_shadow_only` because not all suite gates are
  `ready_for_guarded_opt_in`, but the V3 matrix residual blocker is gone and
  `TRANS-003` can resume coordinator-reviewed standard matrix manifest
  expansion. `TRANS-003` then expanded only `greenshot_5_subset` from 8 to
  12 tasks in manifest/test/docs, preserving suites and runner parameters;
  `TRANS-012` reran the expanded standard matrix: 5 suites, 60 tasks, 60
  ranked solved tasks, 12,753 candidates, 19 held-out groups, 0 matrix
  residuals, 4 baseline residuals, 8 residual-report examples, and zero
  hosted usage. `greenshot_5_subset` remains `ready_for_guarded_opt_in` after
  moving from 8 to 12 tasks. The guarded decision remains
  `remain_shadow_only` because not all suite gates are
  `ready_for_guarded_opt_in`. Shadow-advice-only residual-report examples
  remain separate from matrix residuals and suite gates.
  Tests-only wedge guarded opt-in also remains
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
  production file changes, and hidden-like checks do not disagree. `VAL-003`
  separates behavior-observable issue/PR hard negatives from coverage-gap
  product blockers. Behavior-negative-only issue/PR ranking is
  `ranked_shadow_only` at `pass@1 = 1.0` and `pass@k = 1.0`, but strict
  issue/PR ranking remains blocked because two pass-pass coverage-gap product
  blockers depend on decoy labels or accepted-test structure rather than
  observable validation failure evidence. `VAL-004` now exposes that policy as
  a reusable shadow gate: strict readiness is `blocked`,
  behavior-negative-only readiness is `ranked_shadow_only` with
  `pass@1 = 1.0` and `pass@k = 1.0`, leakage risk is `blocked_high`, and the
  production decision is `remain_shadow_only`. `MAT-014` materializes and
  live-validates `psf/requests#7437` in the pure typed-builder layer using
  reusable `type_annotation_update` and `assignment_type_ignore_update`
  actions; `statement_block_replace` was not needed. `MAT-015` materializes
  and live-validates `pallets/flask#5808` in the pure typed-builder layer
  using reusable `function_signature_update`; `statement_block_replace` was
  not needed. `MAT-016` materializes and live-validates `pallets/flask#5903`
  in a reusable filesystem idiom builder layer using
  `makedirs_exist_ok_rewrite` for both the tutorial docs code block and Python
  source file; `statement_block_replace` was not needed. `MAT-017`
  materializes and live-validates `pallets/click#3430` in a reusable helper
  extraction / duplicate call-site replacement builder layer using
  `helper_function_insert`, `local_assignment_replace`,
  `keyword_argument_value_replace`, and `text_block_insert_after`;
  `statement_block_replace` was not needed. `MAT-018` refreshed the coverage
  panel: all seven original MAT-007 `general_typed_builder` rows are now
  accounted for, with four pure typed-builder rows, one broader general-AST row,
  one filesystem-idiom row, and one helper-extraction/call-replacement row.
  `MAT-019` then reconciled the constrained source/test panel: MAT-008
  (`requests-7427`) and MAT-009 (`pytest-14475`) already cover two of the
  original seven constrained held-out rows, while DATA-029 and DATA-035 remain
  validated reference rows outside the held-out count. The post-MAT-019
  remaining MAT-007 constrained held-out count was 5. `MAT-020` materialized
  `psf/requests#7433` with exact source/test accepted-diff parity using
  reusable `replace_function_region` and
  `insert_pytest_function_after_anchor` records; live validation reached the
  local `pytest-httpbin` redirect endpoint but timed out under the bounded
  run, so the row is recorded with `candidate_validation_timeout` rather than
  as a validation pass. `MAT-021` isolated that timeout as a local
  validation setup issue: the original command imported the ambient
  site-packages `requests`, while the same candidate and accepted head both
  pass when the checkout source is imported via `PYTHONPATH=src` or the
  DATA-008 editable-venv recipe. Count `requests-7433` as live-validated by
  the MAT-021 corrected-harness evidence; the original MAT-020 artifact remains
  an accurate record of the first invalid import-path timeout. Remaining
  non-materialized MAT-007 counts were then `current_structured_action = 4`,
  `general_typed_builder = 0`, `repo_convention_builder = 4`,
  `constrained_local_generator = 4`, and `not_currently_expressible = 2`.
  `MAT-022` now materializes and live-validates the compact remaining Requests
  row, `psf/requests#7328`, with exact accepted-diff parity under
  checkout-local `PYTHONPATH=src` validation. Remaining non-materialized
  MAT-007 counts are now `current_structured_action = 4`,
  `general_typed_builder = 0`, `repo_convention_builder = 4`,
  `constrained_local_generator = 3`, and `not_currently_expressible = 2`.
  `MAT-023` now materializes and live-validates the next formatter-family
  constrained row, `pallets/click#3434`. The candidate changes only
  `src/click/formatting.py` and `tests/test_formatting.py`; full accepted-diff
  parity is false because the accepted PR also changes `CHANGES.rst`, while
  source/test scoped parity is true. Remaining non-materialized MAT-007 counts
  are now `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 4`, `constrained_local_generator = 2`, and
  `not_currently_expressible = 2`. `MAT-024` now materializes and
  live-validates the smaller remaining Click row, `pallets/click#3364`, with
  exact full accepted-diff parity across source, docs, changelog/config docs,
  and tests. `MAT-025` then materializes and live-validates the final
  remaining constrained row from the MAT-019 panel, `pallets/click#3420`,
  with exact full accepted-diff parity across changelog, source, and tests.
  Remaining non-materialized MAT-007 counts are now
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 4`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. `MAT-026` refreshed that closure coverage:
  all seven original constrained held-out rows are accounted for, DATA-029
  `pytest-14466` and DATA-035 `scrapy-7351` remain reference rows outside the
  held-out count, and the next recommended bounded workstream is
  `repo_convention_builder`, starting with `requests-7423`. `MAT-027` now
  materializes and live-validates `psf/requests#7423` with exact accepted-diff
  parity using reusable `insert_pytest_fixture_after_anchor` convention
  records. Remaining non-materialized MAT-007 counts are now
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 3`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. `MAT-028` now materializes and
  live-validates `psf/requests#7315` with exact accepted-diff parity using
  reusable bounded source deletion, pytest function rename, and pytest
  assertion expectation update records. `MAT-029` now materializes and
  live-validates `pytest-dev/pytest#14429` with source/test scoped parity
  using reusable bounded source replacement and pytest parser-fixture test
  insertion records; full accepted-diff parity is false because the accepted
  PR also adds `changelog/13817.bugfix.rst`. `MAT-030` now materializes and
  live-validates `pallets/click#3405` with exact accepted-diff parity using
  reusable bounded source replacement and pytest mark-decorator insertion
  records. Remaining non-materialized MAT-007 counts are now
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 0`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. `MAT-032` now materializes and
  live-validates `pallets/click#3423` with exact accepted-diff parity using a
  reusable `replace_delimited_region` source-only action for the deprecated
  option-help separator expression. Remaining non-materialized MAT-007 counts
  are now `current_structured_action = 3`, `general_typed_builder = 0`,
  `repo_convention_builder = 0`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. `MAT-033` now materializes and
  live-validates `pallets/flask#6013` with exact full accepted-diff parity
  using reusable source-region and bounded text insertion records for the
  autoescape suffix expression, changelog entry, and method docstring note.
  Remaining non-materialized MAT-007 counts are now
  `current_structured_action = 2`, `general_typed_builder = 0`,
  `repo_convention_builder = 0`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. `MAT-034` now materializes and
  live-validates `pytest-dev/pytest#14472` with exact full accepted-diff parity
  across `AUTHORS`, `changelog/14456.bugfix.rst`, and
  `src/_pytest/python_api.py`, using reusable `replace_function_region`,
  `insert_text_around_anchor`, and `create_text_file` records for the
  array-interface receiver fix and accepted text updates. Remaining
  non-materialized MAT-007 counts are now `current_structured_action = 1`,
  `general_typed_builder = 0`, `repo_convention_builder = 0`,
  `constrained_local_generator = 0`, and `not_currently_expressible = 2`.
  `MAT-035` now materializes and live-validates `pallets/flask#5898` with
  exact full accepted-diff parity across `CHANGES.rst`, `docs/api.rst`,
  `src/flask/helpers.py`, and `src/flask/sansio/app.py`, using reusable
  source-region default-literal replacements plus bounded text insertion and
  replacement records. Remaining non-materialized MAT-007 counts are now
  `current_structured_action = 0`, `general_typed_builder = 0`,
  `repo_convention_builder = 0`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`.

## Active Tasks

No active worker task is currently assigned. The coordinator should review
`MAT-035` and then decide whether to record MAT-007 closure coverage or move to
the separate shadow-advice-only residual workstream.

## Ready Queue

No queued worker task remains. The original MAT-007 materializable panel is
closed; only the two `not_currently_expressible` rows remain parked. The
shadow-advice-only residual examples remain a separate workstream and should
not be mixed into MAT-007 held-out materialization counts.

Run at most two tasks in parallel unless write scopes are plainly disjoint.

## Paused Or Blocked

- Shadow-advice-only residual-report examples from `greenshot_bugs`,
  `greenshot_4`, and three `greenshot_5_subset` tasks remain visible for a
  separate scorer/advice follow-up, but they are not matrix residuals in
  `TRANS-012`.
- `MODEL-002`: superseded by bounded scorer subtasks in the backlog, beginning
  with `MODEL-003` through `MODEL-009`.

## Coordinator Review Triggers

Review before assigning more work if:

- `TRANS-001` reports a gate worse than expected
- `GS7-001` reveals missing actions rather than simple ranking failures
- `DATA-001` shows prompt split leakage or weak schema consistency
- two workers need the same files
- the next useful task is unclear

## Recently Completed

### `MAT-035`: Held-out Flask redirect-default current action candidate

- Status: completed by worker MAT-035 on 2026-05-19.
- Result: materialized and live-validated `pallets/flask#5898` from base
  `eb58d862cc4a8f31a369b6e9ad1724e9e642f13f` to accepted head
  `eca5fd1dfdc614c2df876cc32018a7d71f84ea82`. Candidate changed
  `CHANGES.rst`, `docs/api.rst`, `src/flask/helpers.py`, and
  `src/flask/sansio/app.py`, matched the full accepted diff exactly, and
  passed the focused redirect default validation command.
- Commit: `a43a8db` implementation/evidence.
- Push: implementation/evidence commit pushed successfully to `origin/main`;
  push-result metadata recorded in follow-up commit.
- Artifacts:
  `docs/MAT_035_FLASK_5898_REDIRECT_DEFAULT_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-035-flask-5898-live/final/candidate.json`,
  `/tmp/j3-mat-035-flask-5898-live/final/report.md`, and
  `/tmp/j3-mat-035-flask-5898-live/final/candidate.diff`.

### `MAT-034`: Held-out pytest array-interface current action candidate

- Status: completed by worker MAT-034 on 2026-05-19.
- Result: materialized and live-validated `pytest-dev/pytest#14472` from base
  `7df5d80ff3a98714a1d3cdbe82941229e511f4b3` to accepted head
  `8bae589cfba6aa7f17e621e5d89b05004303b0b8`. Candidate changed `AUTHORS`,
  `changelog/14456.bugfix.rst`, and `src/_pytest/python_api.py`, matched the
  full accepted diff exactly, and passed the focused `_as_numpy_array`
  `__array_interface__` validation command.
- Commit: `8947557` implementation/evidence.
- Push: implementation/evidence commit pushed successfully to `origin/main`;
  push-result metadata recorded in follow-up commit.
- Artifacts:
  `docs/MAT_034_PYTEST_14472_ARRAY_INTERFACE_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-034-pytest-14472-live/final/candidate.json`,
  `/tmp/j3-mat-034-pytest-14472-live/final/report.md`, and
  `/tmp/j3-mat-034-pytest-14472-live/final/candidate.diff`.

### `MAT-033`: Held-out Flask autoescape current action candidate

- Status: completed by worker MAT-033 on 2026-05-19.
- Result: materialized and live-validated `pallets/flask#6013` from base
  `06ea505ce2b2042af26e96d35ebf159af7c0869d` to accepted head
  `9368fb3f3c52d74534d14c1bef03c79c103356cd`. Candidate changed
  `CHANGES.rst` and `src/flask/sansio/app.py`, matched the full accepted
  diff exactly, and passed the focused `Flask.select_jinja_autoescape`
  validation command.
- Commit: `c971fa4` implementation/evidence.
- Push: implementation/evidence commit pushed successfully to `origin/main`.
- Artifacts:
  `docs/MAT_033_FLASK_6013_AUTOESCAPE_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-033-flask-6013-live/final/candidate.json`,
  `/tmp/j3-mat-033-flask-6013-live/final/report.md`, and
  `/tmp/j3-mat-033-flask-6013-live/final/candidate.diff`.

- `MAT-032`: materialized `pallets/click#3423` from base
  `fc6c7c47edd6110b6bd5a1a5297b2035214b0cd1` to accepted head
  `61acdcc4ce718f1f6e49e79625c0a6b088bc8189`. The candidate changed only
  `src/click/core.py`, recorded candidate-after diff/hash metadata plus
  source-only mutation scope, and used a reusable
  `replace_delimited_region` action record. Full accepted-diff parity,
  source-only scoped parity, and allowed mutation scope are true. Live focused
  validation passed with `PYTHONPATH=src python -c "import click; from
  click.testing import CliRunner; cmd = click.Command('cli',
  params=[click.Option(['--old'], help='Old option', deprecated=True)]);
  result = CliRunner().invoke(cmd, ['--help']); assert result.exit_code == 0,
  result.output; assert 'Old option (DEPRECATED)' in result.output,
  result.output; assert 'Old option(DEPRECATED)' not in result.output,
  result.output"`. Remaining non-materialized MAT-007 counts are
  `current_structured_action = 3`, `general_typed_builder = 0`,
  `repo_convention_builder = 0`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. Artifacts:
  `docs/MAT_032_CLICK_3423_DEPRECATED_HELP_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-032-click-3423-live/final/candidate.json`,
  `/tmp/j3-mat-032-click-3423-live/final/report.md`,
  `/tmp/j3-mat-032-click-3423-live/final/candidate.diff`, and
  `/tmp/j3-mat-032-click-3423-live/accepted.diff`.
- `MAT-031`: reconciled repo-convention closure coverage after `MAT-027`
  through `MAT-030`. All four original MAT-007 `repo_convention_builder` rows
  are now accounted for as materialized and live-validated:
  `requests-7423` (`MAT-027`), `requests-7315` (`MAT-028`),
  `pytest-14429` (`MAT-029`), and `click-3405` (`MAT-030`). DATA-029
  `pytest-14466` and DATA-035 `scrapy-7351` remain validated reference rows
  outside the held-out count. Remaining non-materialized MAT-007 counts are
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 0`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. Recommended next bounded row:
  `pallets/click#3423` from the `current_structured_action` panel. Artifacts:
  `docs/MAT_031_REPO_CONVENTION_CLOSURE_COVERAGE_2026-05-19.md`,
  `docs/MAT_031_REPO_CONVENTION_CLOSURE_COVERAGE_2026-05-19.jsonl`, and
  `/tmp/j3-mat-031-repo-convention-closure/MAT_031_REPO_CONVENTION_CLOSURE_COVERAGE_2026-05-19.jsonl`.
- `MAT-030`: materialized `pallets/click#3405` from base
  `98302ac4f49e443a48abd3fbb95c86202b89547d` to accepted head
  `b761eda3bad977ec2f485451d85fd8ec365f0bf4`. The candidate changed only
  `tests/test_termui.py`, recorded candidate-after diff/hash/convention
  metadata plus mutation scope, and used reusable
  `replace_exact_source_lines_after_anchor` and
  `insert_pytest_mark_decorator_before_function` action records. Full
  accepted-diff parity, repo-convention scoped parity, and source/test scoped
  parity are true; the accepted PR has no docs or changelog files. Live
  focused validation passed with `PYTHONPATH=src python -m pytest
  tests/test_termui.py::test_get_pager_file_with_real_pager_binary_stream
  tests/test_termui.py::test_echo_via_pager_real_pager_handles_ansi -q`.
  Remaining non-materialized MAT-007 counts are `current_structured_action =
  4`, `general_typed_builder = 0`, `repo_convention_builder = 0`,
  `constrained_local_generator = 0`, and `not_currently_expressible = 2`.
  Artifacts:
  `docs/MAT_030_CLICK_3405_PAGER_CONVENTION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-030-click-3405-live/final/candidate.json`,
  `/tmp/j3-mat-030-click-3405-live/final/report.md`,
  `/tmp/j3-mat-030-click-3405-live/final/candidate.diff`, and
  `/tmp/j3-mat-030-click-3405-live/accepted.diff`.
- `MAT-029`: materialized `pytest-dev/pytest#14429` from base
  `8f81c76744daf72d4f77cfc8423f4bdc60733d78` to accepted head
  `641a97b7695430f9fc4e9113b31d797447dc9654`. The candidate changed only
  `src/_pytest/config/argparsing.py` and `testing/test_parseopt.py`,
  recorded candidate-after diff/AST/hash/convention metadata plus mutation
  scope, and used reusable `replace_exact_source_lines_after_anchor` and
  `insert_pytest_function_after_anchor` action records. Full accepted-diff
  parity is false because the accepted PR also adds
  `changelog/13817.bugfix.rst`; repo-convention and source/test scoped parity
  are true. Live focused validation passed with a temporary
  setuptools-scm `_pytest._version` shim removed by the validation command:
  `2 passed in 0.02s`. Remaining non-materialized MAT-007 counts are
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 1`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. Artifacts:
  `docs/MAT_029_PYTEST_14429_PARSER_FIXTURE_CONVENTION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-029-pytest-14429/final/candidate.json`,
  `/tmp/j3-mat-029-pytest-14429/final/report.md`, and
  `/tmp/j3-mat-029-pytest-14429/final/candidate.diff`.
- `MAT-028`: materialized `psf/requests#7315` from base
  `e8d2c015eecda8273612dd4562425e00cd164ba5` to accepted head
  `fd628095d7b9ddbf3e987d8a4bf0e6062768916f`. The candidate changed only
  `src/requests/adapters.py` and `tests/test_adapters.py`, recorded
  candidate-after diff/AST/hash/convention metadata plus mutation scope, and
  used reusable `delete_exact_source_lines_after_anchor`,
  `rename_pytest_function`, and `replace_pytest_assertion_expected_literal`
  action records. Full accepted-diff parity and repo-convention scoped parity
  are true. Live focused validation imported checkout-local Requests with
  `PYTHONPATH=src`; the selected test
  `tests/test_adapters.py::test_request_url_handles_leading_path_separators`
  passed. Remaining non-materialized MAT-007 counts are
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 2`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. Artifacts:
  `docs/MAT_028_REQUESTS_7315_ADAPTER_CONVENTION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-028-requests-7315/final/candidate.json`,
  `/tmp/j3-mat-028-requests-7315/final/report.md`,
  `/tmp/j3-mat-028-requests-7315/final/candidate.diff`, and
  `/tmp/j3-mat-028-requests-7315/accepted.diff`.
- `MAT-027`: materialized `psf/requests#7423` from base
  `e8d2c015eecda8273612dd4562425e00cd164ba5` to accepted head
  `da905d0eb1de1184d323d39dfc2ce2b423df7bee`. The candidate changed only
  `tests/conftest.py`, recorded candidate-after diff/hash/convention metadata
  plus mutation scope, and used reusable
  `insert_pytest_fixture_after_anchor` action records. Full accepted-diff
  parity and repo-convention scoped parity are true. Live focused validation
  polluted `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` while importing
  checkout-local Requests with `PYTHONPATH=src`; the selected test
  `tests/test_requests.py::TestRequests::test_HTTP_200_OK_GET_ALTERNATIVE`
  passed. Remaining non-materialized MAT-007 counts are
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 3`, `constrained_local_generator = 0`, and
  `not_currently_expressible = 2`. Artifacts:
  `docs/MAT_027_REQUESTS_7423_CONFTEST_CONVENTION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-027-requests-7423/final/candidate.json`,
  `/tmp/j3-mat-027-requests-7423/final/report.md`,
  `/tmp/j3-mat-027-requests-7423/final/candidate.diff`, and
  `/tmp/j3-mat-027-requests-7423/accepted.diff`.
- `MAT-026`: refreshed constrained-source closure coverage after MAT-020
  through MAT-025. All seven original MAT-007/MAT-019 held-out
  `constrained_local_generator` rows are now materialized and live-validated:
  `requests-7427` (`MAT-008`), `pytest-14475` (`MAT-009`),
  `requests-7433` (`MAT-020`/`MAT-021`), `requests-7328` (`MAT-022`),
  `click-3434` (`MAT-023`), `click-3364` (`MAT-024`), and `click-3420`
  (`MAT-025`). DATA-029 `pytest-14466` and DATA-035 `scrapy-7351` remain
  validated reference rows outside the held-out count. Remaining
  non-materialized MAT-007 counts are `current_structured_action = 4`,
  `general_typed_builder = 0`, `repo_convention_builder = 4`,
  `constrained_local_generator = 0`, and `not_currently_expressible = 2`.
  Recommended next workstream: `repo_convention_builder`, starting with
  `requests-7423`. Artifacts:
  `docs/MAT_026_CONSTRAINED_SOURCE_CLOSURE_COVERAGE_2026-05-19.md`,
  `docs/MAT_026_CONSTRAINED_SOURCE_CLOSURE_COVERAGE_2026-05-19.jsonl`, and
  `/tmp/j3-mat-026-constrained-source-closure/MAT_026_CONSTRAINED_SOURCE_CLOSURE_COVERAGE_2026-05-19.jsonl`.
- `MAT-025`: materialized `pallets/click#3420` from base
  `d959898db264aaf07e70ad4eafa254286f9a5185` to accepted head
  `587e3cc7f4804a4fa62f3dab8839a6e1f8954d7c`. The candidate changed
  `CHANGES.rst`, `src/click/_textwrap.py`, `src/click/formatting.py`, and
  `tests/test_formatting.py`, recorded candidate-after diff/AST/hash metadata
  plus mutation scope, and used reusable `replace_delimited_region`,
  `replace_function_region`, `insert_pytest_function_after_anchor`, and
  `insert_text_around_anchor` action records. Full accepted-diff parity,
  source/test scoped parity, and source/docs/test scoped parity are all true.
  Live focused validation used checkout-local source with `PYTHONPATH=src` and
  passed:
  `tests/test_formatting.py::test_wrap_text_visible_width` and
  `tests/test_formatting.py::test_write_usage_styled_prefix_keeps_options_on_one_line`.
  Artifacts:
  `docs/MAT_025_CLICK_3420_ANSI_WRAPPING_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-025-click-3420/final/candidate.json`,
  `/tmp/j3-mat-025-click-3420/final/report.md`,
  `/tmp/j3-mat-025-click-3420/final/candidate.diff`,
  `/tmp/j3-mat-025-click-3420/final/accepted.diff`, and
  `/tmp/j3-mat-025-click-3420/final/accepted-files.txt`.
- `MAT-024`: materialized `pallets/click#3364` from base
  `8bd8b4a074c55c03b6eb5666edc44a9c43df38a2` to accepted head
  `94004f1b5a4a982e8e33ef8d5f00cfb0e1dabddd`. The candidate changed
  `CHANGES.rst`, `docs/commands.md`, `docs/conf.py`, `src/click/core.py`, and
  `tests/test_defaults.py`, recorded candidate-after diff/hash metadata plus
  mutation scope, and used reusable `replace_delimited_region`,
  `insert_pytest_function_after_anchor`, and `insert_text_around_anchor`
  action records. Full accepted-diff parity, source/test scoped parity, and
  source/docs/test scoped parity are all true. Live focused validation used
  checkout-local source with `PYTHONPATH=src` and passed:
  `tests/test_defaults.py::test_default_map_nargs`. Artifacts:
  `docs/MAT_024_CLICK_3364_SOURCE_DOCS_TEST_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-024-click-3364/final/candidate.json`,
  `/tmp/j3-mat-024-click-3364/final/report.md`,
  `/tmp/j3-mat-024-click-3364/final/candidate.diff`,
  `/tmp/j3-mat-024-click-3364/final/accepted.diff`, and
  `/tmp/j3-mat-024-click-3364/final/accepted-files.txt`.
- `MAT-023`: materialized `pallets/click#3434` from base
  `7c99ebe23b931f27562d926814423cce85fd9766` to PR head
  `0551bf53588ae87f462d336f24f853a156fefe3a`. The candidate changed only
  `src/click/formatting.py` and `tests/test_formatting.py`, recorded
  candidate-after diff/AST/hash metadata plus mutation scope, and used
  reusable `replace_function_region` plus
  `insert_pytest_function_after_anchor` action records with a reusable
  insertion-spacing refinement. Full accepted-diff parity is false because the
  accepted PR also changes `CHANGES.rst`; source/test scoped parity is true.
  Live focused validation used checkout-local source with `PYTHONPATH=src` and
  passed eight formatter cases:
  `tests/test_formatting.py::test_help_formatter_write_usage`,
  `tests/test_formatting.py::test_help_formatter_write_usage_without_args_styled_prefix`,
  and `tests/test_formatting.py::test_command_write_usage_no_args`.
  Artifacts:
  `docs/MAT_023_CLICK_3434_SOURCE_REGION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-023-click-3434/final/candidate.json`,
  `/tmp/j3-mat-023-click-3434/final/report.md`,
  `/tmp/j3-mat-023-click-3434/final/candidate.diff`, and
  `/tmp/j3-mat-023-click-3434/final/accepted.diff`.
- `MAT-022`: materialized `psf/requests#7328` from base
  `cbce031327be4f1b4b5fd041ff4dcaa8efa2ce53` to PR head
  `3ee28b806f8bc414b29f7b4561e53c161924fe66`. The candidate changed only
  `src/requests/sessions.py` and `tests/test_requests.py`, matched the
  accepted source/test diff exactly after normalization, and recorded
  candidate-after diff/AST/hash metadata plus mutation scope. Live focused
  validation used checkout-local source with `PYTHONPATH=src` and passed:
  `tests/test_requests.py::TestRequests::test_redirect_history_no_self_reference`.
  Artifacts:
  `docs/MAT_022_REQUESTS_7328_SOURCE_REGION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-022-requests-7328/final/candidate.json`,
  `/tmp/j3-mat-022-requests-7328/final/report.md`,
  `/tmp/j3-mat-022-requests-7328/final/candidate.diff`, and
  `/tmp/j3-mat-022-requests-7328/final/accepted.diff`.
- `MAT-021`: classified the `MAT-020` `psf/requests#7433` validation timeout
  as a local setup/import-path issue, not a candidate regression or
  accepted-head behavior. Fresh `/tmp` checkouts showed the original ambient
  command imported `/Users/aa/.pyenv/versions/3.11.15/lib/python3.11/site-packages/requests/__init__.py`
  and timed out for both candidate and accepted head after reaching
  `POST /redirect-to?url=/post&status_code=307`. The same candidate and
  accepted head pass the focused node when the checkout source is imported
  with `PYTHONPATH=src`, and both pass under the DATA-008 editable-venv recipe.
  Base existing focused tests pass, while base plus only the accepted test
  times out, matching the pre-fix failure mode. Count `requests-7433` as
  live-validated by MAT-021 evidence; the original MAT-020 artifact remains a
  record of the invalid import-path timeout. Artifacts:
  `docs/MAT_021_REQUESTS_7433_VALIDATION_TIMEOUT_DRILLDOWN_2026-05-19.md` and
  `/tmp/j3-mat-021-requests-7433-drilldown/diagnostics.json`.
- `MAT-020`: materialized `psf/requests#7433` from base
  `0b401c76b6e80a4eecf3c690085b2553f6e261ca` to PR head
  `ea1c36c1b1a8364e234b6ad49ea05e3261636f8a`. The candidate changed only
  `src/requests/models.py` and `tests/test_requests.py`, matched the accepted
  source/test diff exactly after normalization, and recorded candidate-after
  diff/AST/hash metadata plus mutation scope. Live validation command
  `python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q`
  timed out after 30 seconds in the local `pytest-httpbin` redirect path, so
  the result is materialized with `candidate_validation_timeout`, not
  validated. Artifacts:
  `docs/MAT_020_REQUESTS_7433_SOURCE_REGION_CANDIDATE_2026-05-19.md`,
  `/tmp/j3-mat-020-requests-7433-final/candidate.json`,
  `/tmp/j3-mat-020-requests-7433-final/report.md`,
  `/tmp/j3-mat-020-requests-7433-final/candidate.diff`, and
  `/tmp/j3-mat-020-requests-7433-final/accepted.diff`.
- `MAT-019`: reconciled constrained source/test materialization coverage before
  the next implementation row. `requests-7427` and `pytest-14475` are already
  materialized/live-validated held-out constrained rows from `MAT-008` and
  `MAT-009`, so the MAT-007 constrained held-out remainder is 5 rows:
  `click-3434`, `click-3420`, `click-3364`, `requests-7433`, and
  `requests-7328`. DATA-029 `pytest-14466` and DATA-035 `scrapy-7351` remain
  validated reference rows and are not counted as held-out wins. The stale
  MAT-018 next recommendation naming `requests-7427`/`pytest-14475` is
  corrected; the next recommended row is `psf/requests#7433`, with
  `requests-7328` as the compact alternate. Artifacts:
  `docs/MAT_019_CONSTRAINED_SOURCE_TEST_COVERAGE_RECONCILIATION_2026-05-19.md`,
  `docs/MAT_019_CONSTRAINED_SOURCE_TEST_COVERAGE_RECONCILIATION_2026-05-19.jsonl`,
  and
  `/tmp/j3-mat-019-constrained-source-test-coverage/MAT_019_CONSTRAINED_SOURCE_TEST_COVERAGE_RECONCILIATION_2026-05-19.jsonl`.
- `MAT-018`: refreshed the real PR materialization coverage panel after
  `MAT-014` through `MAT-017`. All seven original MAT-007
  `general_typed_builder` rows are now accounted for: four pure typed-builder
  rows (`click-3422`, `requests-7441`, `requests-7437`, `flask-5808`), one
  broader general-AST row (`click-3396`), one filesystem-idiom row
  (`flask-5903`), and one helper-extraction/call-replacement row
  (`click-3430`). Remaining non-materialized MAT-007 counts are
  `current_structured_action = 4`, `general_typed_builder = 0`,
  `repo_convention_builder = 4`, `constrained_local_generator = 7`, and
  `not_currently_expressible = 2`. MAT-019 later corrected the constrained
  count to 5 after accounting for MAT-008/MAT-009. The next recommended
  materialization workstream is constrained source/test generation, starting with
  `psf/requests#7427` and `pytest-dev/pytest#14475` as the alternate; MAT-019
  supersedes those specific next-row names because both were already covered.
  Artifacts:
  `docs/MAT_018_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-19.md`,
  `docs/MAT_018_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-19.jsonl`,
  and
  `/tmp/j3-mat-018-real-pr-materialization-refresh/MAT_018_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-19.jsonl`.
- `MAT-017`: materialized and live-validated `pallets/click#3430` from base
  `63daae27b124b717cffa8b458e1a0a43525f2b34` to accepted head
  `843879880e94023317699ac2e85e5f7a44fb1b68`. The candidate changed
  `CHANGES.rst` and `src/click/core.py`, matched the accepted PR diff after
  normalization, and passed `python -m py_compile src/click/core.py` in
  `0.029s`. The row uses reusable `helper_function_insert`,
  `local_assignment_replace`, `keyword_argument_value_replace`, and
  `text_block_insert_after` action records in a helper extraction /
  call-site replacement builder layer; no `statement_block_replace` was used.
  `src/click/core.py` records Python AST parse/diff/hash metadata, while
  `CHANGES.rst` records expected non-Python AST parse failure plus diff/hash
  metadata. Artifacts:
  `/tmp/j3-mat-017-click-3430-final/candidate.json`,
  `/tmp/j3-mat-017-click-3430-final/report.md`,
  `/tmp/j3-mat-017-click-3430-final/candidate.diff`, and
  `/tmp/j3-mat-017-click-3430-final/accepted.diff`.
- `MAT-016`: materialized and live-validated `pallets/flask#5903` from base
  `407eb76b27884848383a37c7274654f0271e4bc4` to accepted head
  `3d03098a97ddc6a908aa4a50c2ef7381f8297d0a`. The candidate changed
  `docs/tutorial/factory.rst` and `examples/tutorial/flaskr/__init__.py`,
  matched the accepted PR diff after normalization, and passed
  `python -m py_compile examples/tutorial/flaskr/__init__.py` in `0.021s`.
  The row uses reusable `makedirs_exist_ok_rewrite` action records in a
  filesystem idiom builder layer; no `statement_block_replace` was used.
  The Python file has AST parse metadata, while the RST tutorial file records
  expected non-Python AST parse failure plus diff/hash metadata. Artifacts:
  `/tmp/j3-mat-016-flask-5903-final/candidate.json`,
  `/tmp/j3-mat-016-flask-5903-final/report.md`,
  `/tmp/j3-mat-016-flask-5903-final/candidate.diff`, and
  `/tmp/j3-mat-016-flask-5903-final/accepted.diff`.
- `MAT-015`: materialized and live-validated `pallets/flask#5808` from base
  `85793d6c223dd845e8f218403a5ced83041d37e1` to accepted head
  `dbd4c2882593f6118103120aa96fa9acdf7deedb`. The candidate changed only
  `src/flask/sansio/app.py`, matched the accepted PR diff after
  normalization, and passed `python -m py_compile src/flask/sansio/app.py` in
  `0.022s`. The row stays in the pure typed-builder layer using reusable
  `function_signature_update`; no `statement_block_replace` was used.
  Artifacts: `/tmp/j3-mat-015-flask-5808-final/candidate.json`,
  `/tmp/j3-mat-015-flask-5808-final/report.md`,
  `/tmp/j3-mat-015-flask-5808-final/candidate.diff`, and
  `/tmp/j3-mat-015-flask-5808-final/accepted.diff`.
- `TRANS-012`: reran the expanded standard transition matrix after
  `TRANS-003`. The run covered 5 suites, 60 tasks, 60 ranked solved tasks,
  12,753 candidates, and 19 held-out groups, with 0 matrix residuals, 4
  baseline residuals, 8 residual-report examples, and zero hosted usage.
  Compared with `TRANS-011`, the only suite expansion is
  `greenshot_5_subset`: 8 -> 12 tasks, 680 -> 1,020 candidates, 0 matrix
  residuals preserved, 2 baseline residuals preserved, and
  `ready_for_guarded_opt_in` preserved. The residual report adds one
  shadow-advice-only example,
  `receipt_label_nested_module_import_decoy`; no `v3_top_candidate_failed`
  examples remain. Guarded decision remains `remain_shadow_only`; product
  routing remains shadow-only.
- `TRANS-003`: expanded the standard matrix manifest's `greenshot_5_subset`
  from 8 to 12 selected GreenShot-5 tasks by adding
  `profile_badge_public_api_signature_propagation`,
  `return_window_policy_default`,
  `receipt_label_nested_module_import_decoy`, and
  `loyalty_points_wrapper_exception_handler` in the source order from
  `examples/greenshot_5/tasks.json`. Suites and runner parameters are
  unchanged, product routing remains shadow-only, and the expanded matrix run
  is explicitly deferred to `TRANS-012`.
- `TRANS-011`: reran the full current standard transition matrix after
  `MODEL-009`. The run covered 5 suites, 56 tasks, 56 ranked solved tasks,
  12,413 candidates, and 19 held-out groups, with 0 matrix residuals, 4
  baseline residuals, 7 residual-report examples, and zero hosted usage.
  `greenshot_3` improved to `ready_for_shadow_mode`, `greenshot_5_subset`
  improved to `ready_for_guarded_opt_in`, and `greenshot_6_subset` remains
  `ready_for_guarded_opt_in`. The residual report has 7
  `shadow_scorer_top_candidate_failed` examples and no
  `v3_top_candidate_failed` examples. Guarded decision remains
  `remain_shadow_only` because not all suite gates are
  `ready_for_guarded_opt_in`; `TRANS-003` can resume standard matrix
  manifest expansion under shadow-only product routing.
- `MODEL-009`: added V3 local structural evidence and a V3-only local evidence
  prior for the four `TRANS-010` top-candidate failures. The scorer now
  recognizes exception-wrapper candidates that match public failure exception
  hints, demotes add-import candidates without missing-import evidence, demotes
  swap-call candidates that break argument name alignment, promotes helper
  expression edits that reach the failing public API assertion, promotes
  numeric boundary literals in boundary tasks, and promotes named
  module-constant assertion deltas while demoting literal changes that move an
  expected value away. Focused tests replay
  `greenshot_3/wrap_try_except`,
  `greenshot_5_subset/express_shipping_boundary_preferred_helper`,
  `greenshot_5_subset/free_shipping_threshold_module_constant`, and
  `greenshot_5_subset/quote_total_helper_discount`. Saved-artifact V3
  evaluator replays show `greenshot_3` residual count 0 for the held-out wrap
  group and `greenshot_5_subset` V3 pass@1 3/3 with residual count 0 on its
  held-out validation groups. Production routing, matrix runner behavior,
  repair candidate generation, manifest contents, and V3 product-gate policy
  remain unchanged.
- `TRANS-010`: reran the full current standard transition matrix after
  `MODEL-007`, `MODEL-008`, and the clean `TRANS-009` subset. The run covered
  5 suites, 56 tasks, 56 ranked solved tasks, 12,413 candidates, and 19
  held-out groups, with 4 matrix residuals, 4 baseline residuals, 11
  residual-report examples, and zero hosted usage. `greenshot_6_subset`
  remains clean and `ready_for_guarded_opt_in`; `greenshot_3` has 1 matrix
  residual and `greenshot_5_subset` has 3 matrix residuals, both with
  `not_ready_underperforms_existing_rank_order` gates. The residual report has
  11 `scorer_ranking_gap` examples: 7
  `shadow_scorer_top_candidate_failed` and 4 `v3_top_candidate_failed`.
  Guarded decision: `remain_shadow_only`; `TRANS-003` should return to
  residual work before manifest expansion.
- `TRANS-009`: reran targeted `greenshot_6_subset` transition evidence after
  `MODEL-008`. The subset covered 12 tasks, 12 ranked solved tasks, 9,696
  candidates, and 7 held-out groups, with 0 matrix residuals, 2 baseline
  residuals, and 0 residual-report examples. The previous
  `apache_license_classifier_dict_value` V3 residual is resolved: the scorer
  top candidate changes `Apache-2.0` from `Apache License` to
  `Apache Software License`, validates as passing, and moves the first known
  passing candidate to scorer position 1. No missing-feature labels remain
  because no residual examples remain. Suite gate:
  `ready_for_guarded_opt_in`; guarded decision: `guarded_opt_in_trial`;
  trial scope: `narrow_opt_in_transition_ranking`. `TRANS-003` can move back
  to ready for coordinator-reviewed standard matrix expansion.
- `MODEL-008`: fixed the Apache mapping-value scorer/advice evidence gap. The
  scorer now treats public pytest assertion diff lines as mapping-value
  `actual` -> `expected` evidence when parsed assertion fields are truncated.
  Focused action-choice fixtures rank the rank-5
  `Apache-2.0: Apache License -> Apache Software License` candidate first over
  the nearby `MIT` decoys, advice preserves `assertion_diff_lines` and
  expected strings in failure-hint records, and a focused V3 scorer replay uses
  the diff-line feature to rank the Apache candidate first. Production
  routing, matrix runner behavior, and V3 product-gate policy remain
  unchanged and shadow-only.
- `TRANS-008`: reran targeted `greenshot_6_subset` transition evidence after
  `MODEL-007`. The subset covered 12 tasks, 12 ranked solved tasks, 9,696
  candidates, and 7 held-out groups, with 1 matrix residual and 2 baseline
  residuals. The residual report has 1 `scorer_ranking_gap` example,
  `apache_license_classifier_dict_value`, with failure kind
  `v3_top_candidate_failed`. `project_urls_header_dict_key` is resolved in the
  rerun: `change_dict_key Project_URL -> Project-URL` is rank 1 and passes,
  while `add_dict_key Project-URL = None` is rank 2 and fails. No V1/advice
  residuals remain in the report. V3 no longer underperforms the existing rank
  order on this subset, and the suite gate improved to `ready_for_shadow_mode`,
  but the guarded-trial decision remains `remain_shadow_only` because the
  suite is not `ready_for_guarded_opt_in` and the residual count is nonzero.
- `MODEL-007`: fixed the GreenShot-6 `project_urls_header_dict_key`
  deterministic V1/advice residual. The scorer now recognizes a
  `change_dict_key` candidate that renames an existing same-mapping key to a
  public missing key and demotes the competing `add_dict_key` `None`
  placeholder in that shape. Focused action-choice and advice fixtures rank
  `Project_URL -> Project-URL` above `Project-URL = None`; a direct replay of
  the two `TRANS-007` candidates now ranks `[1, 2]`. Production routing and
  V3 product-gate policy remain unchanged and shadow-only.
- `TRANS-007`: reran targeted post-fix `greenshot_6_subset` transition matrix
  evidence after `TRANS-006`, `ACT-003`, and `ACT-004`. The subset covered 12
  tasks, 12 ranked solved tasks, 9,696 candidates, and 7 held-out groups, with
  4 matrix residuals and 2 baseline residuals. The residual report has 5
  examples, all `scorer_ranking_gap`; `dynamic_field_error_message` is no
  longer a `candidate_generation_gap`, and `candidate_after_unavailable` is
  absent from missing-feature evidence. Remaining labels are
  `source_embedding_unavailable` and
  `candidate_after_embedding_unavailable`. Suite gate:
  `not_ready_underperforms_existing_rank_order`; guarded decision:
  `remain_shadow_only`.
- `ACT-003`: promoted exception-message literal fragment candidates using
  pytest failure-hint `match=` expected strings. The
  `greenshot_6_subset/dynamic_field_error_message` preferred
  `change_literal` candidate now ranks first and passes within
  `max_candidates=8`; the one-row GreenShot-6 smoke solved it with one tested
  ranked candidate. The change uses public failure-hint evidence, not preferred
  labels, and leaves transition ranking gates unchanged and shadow-only.
- `TRANS-006`: surfaced candidate-after metadata from transition outcome rows.
  Action-choice candidate records now treat root diff summaries, flattened
  diff counts, root AST deltas, and flattened AST-delta metadata as available
  candidate-after evidence without inventing embeddings. Nested
  `candidate_after` records, repo-after records, patched source, and actual
  after embeddings remain preferred when present. Rerunning the residual
  reporter against the `TRANS-005` matrix kept 17 failures and the same gap
  classifications, but removed `candidate_after_unavailable` from missing
  feature evidence; `candidate_after_embedding_unavailable` remains.
- `TRANS-005`: reran the standard transition shadow matrix after `MODEL-003`
  through `MODEL-005`. The run covered 5 suites, 56 tasks, 55 ranked solved
  tasks, 12,413 candidates, 19 held-out groups, 8 matrix residuals, and zero
  hosted usage. The residual report has 17 examples: 16
  `scorer_ranking_gap` and 1 `candidate_generation_gap`. Suite gates remain
  `ready_for_shadow_mode` for `greenshot_bugs` and `greenshot_4`, and
  `not_ready_underperforms_existing_rank_order` for `greenshot_3`,
  `greenshot_5_subset`, and `greenshot_6_subset`. Guarded-trial decision:
  `remain_shadow_only`; `TRANS-003` remains blocked.
- `SCALE-003`: added `j3.training_manifest`, a small durable training/eval
  manifest row validator aligned with `docs/TRAINING_DATA_POLICY.md`. The
  schema skeleton defines artifact, source, split, redistribution, retention,
  review, and exclusion classes; validates common provenance fields,
  source-kind-specific fields for repo code, docs, issue/PR rows, candidates,
  synthetic prompts, validations, teacher labels, and local knowledge; enforces
  SHA-256 checksum shape and durable-row checksum requirements; and requires
  split/leakage metadata for future overlap checks. Focused tests cover valid
  rows, missing fields, source-kind errors, invalid classes/checksums, and
  excluded/local-only handling.
- `MODEL-005`: added boundary/literal and module-constant evidence to the
  shadow transition scorer. V1/V2/V3 feature surfaces now expose failure-hint
  file, symbol, and target-name alignment; task-family alignment for
  boundary-operator, module-constant, and literal/message actions; literal or
  module-constant assertion-delta matches; module-constant name alignment; and
  same-file/symbol competitor counts. Focused fixtures now rank the passing
  boundary operator, module constant, and literal/message candidates above
  equivalent-looking decoys. Existing `MODEL-003` add-keyword and `MODEL-004`
  mapping-target behavior remains intact, and production ranking gates remain
  unchanged and shadow-only.
- `SCALE-002`: added `docs/TRAINING_DATA_POLICY.md` and linked it from
  `docs/TRAINING.md`. The policy builds on `SCALE-001` and defines artifact
  classes for scratch corpora, checked-in examples, release archives,
  synthetic rows, issue/PR mining, generated artifacts, and external repo
  snapshots; mandatory provenance fields for raw code, docs, issues/PRs,
  generated candidates, synthetic prompts, validations, and teacher-assisted
  labels; checksum and split/leakage controls; retention and redistribution
  classes; release exclusions; and a manifest readiness checklist for a future
  durable training manifest task.
- `MODEL-004`: added mapping target evidence to the shadow transition scorer
  for `change_dict_key`, `change_dict_value`, `add_dict_key`, and
  `change_subscript_key`. The V1/V2/V3 feature surfaces now expose mapping
  target role, same-mapping competition, assertion-delta value matches,
  missing-key add/subscript matches, and key-renaming decoy signals. Advice
  scoring now passes candidate records into the group so real shadow advice can
  observe same-mapping competitors. Production ranking gates remain unchanged
  and shadow-only.
- `SCALE-001`: added
  `docs/SCALE_001_LOCAL_PRETRAINING_FEASIBILITY_INVENTORY_2026-05-19.md`,
  which separates near-term local encoder and small-model work from
  frontier-scale language/code pretraining. The inventory ties current
  repo-local prompt/spec, deterministic encoder, transition, real-repo,
  issue/PR, materialization, local-knowledge, Apache corpus, hard-negative, and
  validation artifacts to concrete data, objective, compute, evaluation, and
  data-policy gaps. Next scale step is `SCALE-002` data provenance and release
  policy.
- `MODEL-003`: added an explicit scorer feature and penalty for unvalidated
  `add_keyword_arg` candidates when failure hints do not name the candidate
  keyword path. Failure hint records now preserve missing-name, missing-key,
  asserted-key, and type-error-name fields for transition-scorer advice.
  Focused fixtures show add-keyword decoys demoted without a matching keyword
  hint and kept when the hint names the missing keyword path. Production
  ranking gates remain unchanged and shadow-only.
- `MAT-014`: materialized and live-validated `psf/requests#7437` from base
  `0b401c76b6e80a4eecf3c690085b2553f6e261ca` to accepted head
  `dfe9ab8143fb71c72673738f25f0571347226b63`. The candidate changed only
  `src/requests/models.py`, matched the accepted PR diff after normalization,
  and passed `python -m py_compile src/requests/models.py` in `0.024s`. The
  row stays in the pure typed-builder layer using reusable
  `type_annotation_update` and `assignment_type_ignore_update`; no
  `statement_block_replace` was used. Artifacts:
  `/tmp/j3-mat-014-requests-7437-final/candidate.json`,
  `/tmp/j3-mat-014-requests-7437-final/report.md`,
  `/tmp/j3-mat-014-requests-7437-final/candidate.diff`, and
  `/tmp/j3-mat-014-requests-7437-final/accepted.diff`.
- `KNOW-006`: added citeable local knowledge for package-relative test import
  style and wired tests-only attribution to cite it. The held-out
  `h11-tests-bytesify-memoryview` row now records `import_style` attribution
  for `from .._util import bytesify`; `missing_purposes` is empty,
  residual labels do not include `missing_knowledge`, and
  `REQUIRED_KNOWLEDGE_PURPOSES` remains `test_location`, `import_style`,
  `validation`. The existing no-knowledge and partial-knowledge planner tests
  still report attribution gaps.
- `VAL-004`: added a reusable behavior-negative-only issue/PR shadow gate over
  VAL-003-style policy rows. Strict issue/PR ranking remains `blocked` because
  two coverage-gap product blockers depend on decoy labels;
  behavior-negative-only issue/PR ranking is `ranked_shadow_only` with
  `pass@1 = 1.0` and `pass@k = 1.0`, six behavior-observable negatives, two
  product blockers, leakage risk `blocked_high`, and production decision
  `remain_shadow_only`.
  Behavior-negative-only metrics are not production-eligible and do not change
  production ranking. Artifacts:
  `/tmp/j3-val-004-behavior-shadow-gate/val-004-shadow-gate.json`,
  `/tmp/j3-val-004-behavior-shadow-gate/val-004-shadow-gate.md`, and
  `/tmp/j3-val-004-behavior-shadow-gate/val-004-shadow-gate-rows.jsonl`.
- `MAT-013`: refreshed the MAT-007 real PR materialization coverage panel using
  MAT-010 through MAT-012 evidence. Three of the seven held-out
  `general_typed_builder` rows are now materialized and live-validated:
  `click-3422` and `requests-7441` by pure typed-builder actions, and
  `click-3396` by broader general-AST actions. Remaining counts after this
  overlay are `current_structured_action = 4`, `general_typed_builder = 4`,
  `repo_convention_builder = 4`, `constrained_local_generator = 7`, and
  `not_currently_expressible = 2`. Bounded `statement_block_replace` changes
  only the `click-3396` risk classification: covered, but higher risk than the
  pure typed-builder rows and not a reason to reclassify any remaining row as
  covered. Next bounded materialization row: `psf/requests#7437`. Artifacts:
  `docs/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.md`,
  `docs/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.jsonl`,
  and
  `/tmp/j3-mat-013-real-pr-materialization-refresh/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.jsonl`.
- `VAL-003`: added a shadow-only coverage-gap decoy policy probe over DATA-039,
  DATA-040, and VAL-002 artifacts. Strict issue/PR ranking remains `blocked`
  because two coverage-gap product blockers are not behavior-observable hard
  negatives and their classification depends on decoy labels or accepted-test
  structure. Behavior-negative-only issue/PR ranking is `ranked_shadow_only`
  with `pass@1 = 1.0`, `pass@k = 1.0`, six behavior-observable negatives, two
  product blockers, and leakage risk `blocked_high`. Artifacts:
  `/tmp/j3-val-003-coverage-gap-policy-probe/val-003-policy-report.json`,
  `/tmp/j3-val-003-coverage-gap-policy-probe/val-003-policy-report.md`, and
  `/tmp/j3-val-003-coverage-gap-policy-probe/val-003-decoy-policy-records.jsonl`.
- `MAT-012`: materialized and live-validated held-out `pallets/click#3396`
  from base `fed9049f7a07550d560a91b30c5b0b3e17d54981` to accepted head
  `3df4d601a5f1d1db50cbf0b33e5b0816189bc5a8`. The candidate changed only
  `src/click/_utils.py`, `src/click/core.py`, and `src/click/parser.py`,
  matched the accepted PR diff after normalization, and passed
  `python -m py_compile src/click/_utils.py src/click/core.py
  src/click/parser.py` in `0.031s`. The action vocabulary stayed general but
  expanded with reusable `assignment_annotation_update`,
  `function_signature_update`, `boolean_condition_insert`, and bounded
  `statement_block_replace` actions. Artifacts:
  `/tmp/j3-mat-012-click-3396-analysis/candidate.json`,
  `/tmp/j3-mat-012-click-3396-analysis/report.md`,
  `/tmp/j3-mat-012-click-3396-analysis/candidate.diff`, and
  `/tmp/j3-mat-012-click-3396-analysis/accepted.diff`.
- `KNOW-003`: tests-only candidate rows now carry explicit knowledge
  attribution with retrieved record IDs, cited purposes, required purposes,
  missing purposes, and machine-readable `knowledge_not_used` or
  `missing_knowledge` residuals. Knowledge-use records are emitted even when
  no local knowledge was cited, so missing attribution is structured rather
  than prose-only.
- `VAL-002`: ran cross-row label-safe behavior probes against every passing
  decoy from DATA-039 and DATA-040. Accepted candidates passed all recipes;
  `scrapy_mutating_peek` converted from passing decoy to behavior failure;
  `scrapy_missing_tests` and `pytest_missing_invalid_tolerance_tests` remained
  passing coverage-gap decoys. The issue/PR ranking gate remains shadow-only
  with blocker
  `coverage_gap_decoy_indistinguishable_without_accepted_label_leakage`.
  Artifacts:
  `/tmp/j3-val-002-validation-strength-probe/validation-strength-report.json`,
  `/tmp/j3-val-002-validation-strength-probe/validation-strength-report.md`,
  and
  `docs/VAL_002_CROSS_ROW_VALIDATION_STRENGTH_PROBE_2026-05-18.md`.
- `MAT-011`: materialized and live-validated the held-out `psf/requests#7441`
  typed-builder row from base `b7b549b54571d03950b16afd2d01bc6ff0348224` to
  accepted head `412f581d7e7c27bfee4f042fcac89bae9a804afe`. The candidate
  changed only `src/requests/_types.py` and `src/requests/models.py`, matched
  the accepted PR diff after normalization, and passed `python -m py_compile
  src/requests/_types.py src/requests/models.py` in `0.024s`. MAT-010's
  `type_annotation_update` generalized after expansion to existing annotation
  updates; the row also required general parameterized `type_alias_update` and
  `import_member_remove` actions. Artifacts:
  `/tmp/j3-mat-011-requests-7441-final/candidate.json`,
  `/tmp/j3-mat-011-requests-7441-final/report.md`,
  `/tmp/j3-mat-011-requests-7441-final/candidate.diff`,
  `/tmp/j3-mat-011-requests-7441-final/accepted.diff`, and
  `docs/MAT_011_REQUESTS_7441_TYPED_BUILDER_CANDIDATE_2026-05-18.md`.
- `MAT-010`: materialized and live-validated the held-out
  `pallets/click#3422` typed-builder row using reusable
  `class_scope_annotation_move`, `return_annotation_update`, and
  `type_annotation_update` action records. The final fresh checkout at
  `fc6c7c47edd6110b6bd5a1a5297b2035214b0cd1` changed only
  `src/click/utils.py`, matched the accepted PR diff after normalization, and
  passed `python -m py_compile src/click/utils.py` in `0.022s`. Artifacts:
  `/tmp/j3-mat-010-click-3422-final/candidate.json`,
  `/tmp/j3-mat-010-click-3422-final/report.md`,
  `/tmp/j3-mat-010-click-3422-final/candidate.diff`,
  `/tmp/j3-mat-010-click-3422-final/accepted.diff`, and
  `docs/MAT_010_CLICK_3422_TYPED_BUILDER_CANDIDATE_2026-05-18.md`.
- `DATA-040`: materialized and live-validated four realistic decoys for the
  validated `pytest-dev/pytest#14462/#14466` issue/PR replay. The pytest row
  now has live decoy validation outcomes and candidate-after snapshots for all
  four decoys, so `decoys_not_live_validated` and
  `decoy_candidate_after_unavailable` are removed for that row. Three decoys
  failed and one passed, creating the honest blocker
  `decoy_validation_outcomes_include_passing_candidates`; pass@1/pass@k remain
  blocked and the ranking harness remains shadow-only. Artifacts:
  `/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-bundle.json`,
  `/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-candidates.jsonl`,
  `/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-report.md`,
  `/tmp/j3-data-040-ranking-with-live-decoys/ranking-report.json`,
  `/tmp/j3-data-040-ranking-with-live-decoys/ranking-report.md`, and
  `docs/DATA_040_LIVE_PYTEST_DECOY_VALIDATION_2026-05-18.md`.
- `DATA-039`: materialized and live-validated four realistic decoys for the
  validated `scrapy/scrapy#7293/#7351` issue/PR replay. The Scrapy row now has
  live decoy validation outcomes and candidate-after snapshots for all four
  decoys, so `decoys_not_live_validated` and
  `decoy_candidate_after_unavailable` are removed for that row. Two decoys
  failed and two passed, creating the honest blocker
  `decoy_validation_outcomes_include_passing_candidates`; pass@1/pass@k remain
  blocked and the ranking harness remains shadow-only. Artifacts:
  `/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-bundle.json`,
  `/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-candidates.jsonl`,
  `/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-report.md`,
  `/tmp/j3-data-039-ranking-with-live-decoys/ranking-report.json`,
  `/tmp/j3-data-039-ranking-with-live-decoys/ranking-report.md`, and
  `docs/DATA_039_LIVE_ISSUE_PR_DECOY_VALIDATION_2026-05-18.md`.
- `MAT-009`: materialized and live-validated the held-out
  `pytest-dev/pytest#14475` mark-expression scanner source/test candidate
  using reusable `replace_function_region` and
  `insert_pytest_function_after_anchor` action records. The final fresh
  checkout at `7df5d80ff3a98714a1d3cdbe82941229e511f4b3` changed only
  `src/_pytest/mark/expression.py` and `testing/test_mark_expression.py`.
  Full accepted-diff parity is false because the PR also adds
  `changelog/14474.bugfix.rst`; source/test scoped accepted-diff parity is
  true. Focused validation passed in `0.078s` with `PYTHONPATH=src` forced to
  the candidate checkout. Artifacts:
  `/tmp/j3-mat-009-pytest-14475-final/candidate.json`,
  `/tmp/j3-mat-009-pytest-14475-final/report.md`,
  `/tmp/j3-mat-009-pytest-14475-final/candidate.diff`,
  `/tmp/j3-mat-009-pytest-14475-final/accepted.diff`, and
  `docs/MAT_009_PYTEST_14475_SOURCE_REGION_CANDIDATE_2026-05-18.md`.
- `MAT-008`: materialized and live-validated the held-out
  `psf/requests#7427` no-proxy domain-boundary source/test candidate using
  reusable action records, not a PR-named action kind. The final fresh checkout
  at `b684dcb9bbf3aa557d1238e72062c4a29737dd1c` changed only
  `src/requests/utils.py` and `tests/test_utils.py`, matched the accepted PR
  diff after normalizing Git hunk context labels, and passed `python -m pytest
  tests/test_utils.py::test_should_bypass_proxies_no_proxy_domain_boundary -q`
  in `0.383s`. Artifacts:
  `/tmp/j3-mat-008-requests-7427-final/candidate.json`,
  `/tmp/j3-mat-008-requests-7427-final/report.md`,
  `/tmp/j3-mat-008-requests-7427-final/candidate.diff`,
  `/tmp/j3-mat-008-requests-7427-final/accepted.diff`, and
  `docs/MAT_008_REQUESTS_7427_SOURCE_REGION_CANDIDATE_2026-05-18.md`.
- `DATA-038`: added sidecar full-file candidate-after snapshots for the
  validated DATA-029 pytest #14462 and DATA-035 Scrapy #7293 issue/PR
  candidates, covering all four touched files with before/after hashes, stored
  after snapshots, diff/AST metadata, validation status, and provenance. The
  DATA-037 ranking rerun now marks accepted candidates as having
  candidate-after evidence and replaces `full_candidate_after_unavailable`
  with `decoy_candidate_after_unavailable`; ranking remains blocked on missing
  live/materialized decoy evidence, no guarded issue/PR ranker, and weak
  issue-specific semantic features. Artifacts:
  `/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-bundle.json`,
  `/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-candidates.jsonl`,
  `/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-report.md`,
  `/tmp/j3-data-038-ranking-with-snapshots/ranking-report.json`, and
  `docs/DATA_038_ISSUE_PR_CANDIDATE_AFTER_SNAPSHOTS_2026-05-18.md`.
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
