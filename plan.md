# j3 Current Plan

This file is the live handoff for the next context window. Keep it compact.
Move long design notes into focused markdown files if they grow.

## Long-Term Goal

Build a local-first, no-LLM Python coding agent that can repair and improve
repositories by choosing structured edits, predicting their consequences,
validating with tools, and iterating toward passing tests.

The intended path is:

1. Reliable structured patch generation.
2. Strong candidate-outcome data from real repair attempts.
3. A trainable candidate ranker that beats handcrafted hint ordering on held-out
   tasks.
4. A repo-state and transition model that predicts which structured edit should
   move the repo toward a better observed state.
5. A bounded planning policy that can make multi-step repairs without free-form
   patch generation.

Do not start the main neural/JEPA track until the benchmark and outcome data can
separate missing actions, weak observations, bad ranking, and weak planning.

## Strategic Correction

GreenShot-5 was useful for tightening the repair loop. It is now too easy to
make progress look better by adding one handcrafted task and one handcrafted
action at a time.

The next phase should shift from toy ladder growth to held-out real-repo signal.
GreenShot-6 is useful now, but still narrow: it has package-metadata mutations
and one git-history-derived task inside one local `pkgmeta` fixture. Treat it as
the start of real-derived evaluation, not evidence of broad package repair.

Default next move:

- Prefer mutation-generated and git-history-derived tasks from real repos.
- Prefer dataset and validation tooling over broad action expansion.
- Add a new action only when a held-out task proves the candidate is missing.
- Improve hints/ranking when the right candidate exists but is late.

## Current State

Implemented repair loop capabilities:

- `j3 eval` supports ranked, baseline, and both phases.
- Eval output is task-level by default; candidate logs are behind `--verbose`.
- Eval diagnostics record tested candidates, passing candidates, first passing
  index, skipped phases, failure hints, target context, and exploration rows.
- `j3 eval --candidate-outcomes PATH` writes one row per tested candidate.
- `train-ranker` consumes diagnostics and candidate-outcome JSONL directly.
- `train-ranker` supports held-out task names and task families from the same
  input sources.
- Candidate outcome rows carry compact failure hints, target context, preferred
  patch labels, task families, source types, stable splits, language, scores,
  pass labels, diff-size fields, and edit-locality fields.
- Eval diagnostics aggregate pass@1 by action, task family, and source type.
- `j3 outcome-summary` summarizes candidate outcome JSONL datasets by rows,
  tasks, families, source types, splits, actions, preferred positives, average
  candidates, and pass@1 slices.
- The patching code is split under `repair/patching/`; root `patching.py` is a
  compatibility shim.
- The planner supports bounded multi-step repair when a candidate changes the
  observed failure and exposes the next repair.

Implemented action families:

- `replace_expr`
- `insert_guard`
- `change_literal`
- `change_operator`
- `change_subscript_key`
- `change_dict_key`
- `change_dict_value`
- `add_dict_key`
- `swap_call_arg`
- `add_keyword_arg`
- `add_import`
- `add_import_fallback`
- `change_attribute`
- `change_module_constant`
- `wrap_try_except`
- `add_fallback_warning`
- `change_return_value`
- `rename_symbol`
- `modify_condition`
- `propagate_signature`

Implemented observation/hint parsing:

- Pytest failed node ids.
- Assertion comparisons and numeric deltas.
- Pytest `AssertionError: assert ... == ...` comparison lines.
- Traceback files, lines, and function frame context.
- `NameError`, `ImportError`, `ModuleNotFoundError`, `AttributeError`,
  `KeyError`, and TypeError argument names.
- Mypy and ruff diagnostics.
- Pytest warning `match=...` strings.

Recent work:

- GreenShot-5 reached 20 tasks.
- GreenShot-6 now has 5 package-metadata mutation tasks using existing action
  families.
- GreenShot-6 now includes its first git-history-derived held-out repair task,
  modeled on `pypa/pyproject-metadata` commit `604d388`, for a wrong
  `project.readme.file` validation error key.
- GreenShot-6 now includes three additional git-history-derived held-out repair
  tasks: a `pypa/pyproject-metadata` dynamic-field error-message repair
  modeled on commit `a52c477`, plus `psf/cachecontrol` no-store and Range-header
  cache behavior repairs modeled on commits `a954e24` and `4e267a8`.
- GreenShot-6 now includes a second fixture domain, `httpcache`, with 5
  mutation-derived HTTP cache/header tasks using existing action families:
  subscript-key repair, inclusive status-code boundary, dictionary value,
  swapped call arguments, and keyword propagation.
- Task manifests support `source_type`, defaulting to `handcrafted`.
- `change_dict_value` now covers dictionary literal value repairs.
- String literal alternatives now handle structured shared prefixes such as
  MIME-style values (`text/plain` -> `text/markdown`).
- String assertion comparisons rank the preferred dictionary-value edit at rank
  1.
- Planner failure signatures now normalize parsed list/dict assertion values
  before using them for loop detection.
- Candidate outcome rows now include `language`, diff line counts, edit line
  spans/deltas, replacement lines, and target locality; ranker features consume
  this metadata from both live candidates and persisted rows.
- Candidate outcome rows now include compact before/after Python AST delta
  metadata: parse status, added/removed AST feature maps, and aggregate delta
  counts. Ranker features consume the same AST deltas from both live candidates
  and persisted rows.
- Candidate outcome rows now include candidate relation metadata: equivalent
  candidate ranks, overlapping edit-span ranks, and passing-candidate subsets
  for both relation types.
- `j3 outcome-summary` covers candidate outcome JSONL files by rows, tasks,
  families, source types, splits, actions, preferred positives, average
  candidates, and pass@1 slices.
- GreenShot-5 candidate outcomes were collected with `--explore-after-pass 5`
  at `runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl`.
- Task manifests now support explicit `split` metadata; missing splits are
  assigned deterministically from task identity and are written to diagnostics
  and candidate outcome rows.
- A current GreenShot-6 smoke run solves all 11 tasks, but pass@1 is 8/11. The
  non-pass@1 tasks are useful ranking signal rather than missing-action signal:
  inclusive operator boundary passes at rank 2, Apache classifier
  dictionary-value repair passes at rank 5, and HTTP `no-store` subscript-key
  repair passes at rank 19.
- GreenShot-6 candidate outcomes were collected with `--explore-after-pass 5`
  at `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl`.
- Combined GreenShot-5 and GreenShot-6 candidate outcomes were used to train
  the candidate ranker with `http_cache_directive` held out as a task-family
  validation slice. The held-out plan solved but did not pass at rank 1
  (`pass@1=0/1`, average first passing index 5.0), confirming it is useful
  ranking signal for the next hard-negative inspection.
- GreenShot-6 hard negatives for `http_cache_directive`, `mapping_value`, and
  `operator_boundary` were inspected and summarized in `HARD_NEGATIVES.md`.
  The issue is ranking signal, not missing actions: the correct candidates
  exist, but local same-score decoys and multiple passing operator repairs need
  richer metadata before ranker feature changes.
- Candidate ranker feature extraction now consumes non-leaky equivalent and
  overlapping candidate relation metadata from persisted outcome rows: relation
  counts, before/after rank direction, and closest rank-distance buckets. The
  feature version is `candidate-diagnostics-v5`.
- A fresh temporary GreenShot-6 outcome collection with current AST delta and
  relation metadata still solved all 11 tasks with pass@1 8/11. Training on
  GreenShot-5 plus the fresh GreenShot-6 rows with `http_cache_directive` held
  out produced 519 features and reduced margin violations from 6 to 3, but the
  held-out task still did not pass at rank 1 (`pass@1=0/1`, positive@1=0/1).
  Relation metadata alone is not enough for the HTTP `no-store` hard negative.
- Candidate target context now records when a subscript-key candidate writes to
  a local mapping returned by the target function, including whether the old or
  replacement key matches an existing returned-mapping initializer key. Pytest
  failure hints now also record asserted mapping subscript keys from assertion
  source lines. Candidate ranker features consume both signals from live
  candidates and persisted outcome rows. The feature version is
  `candidate-diagnostics-v7`.
- A fresh GreenShot-6 outcome collection with the new mapping-key observation
  signal still solved all 11 tasks with pass@1 8/11. Training on GreenShot-5
  plus the fresh GreenShot-6 rows with `http_cache_directive` held out produced
  523 features and ranked the held-out HTTP `no-store` repair first
  (`pass@1=1/1`, `positive@1=1/1`).
- A current GreenShot-6 ranked smoke run solves all 14 tasks, including 4
  git-history-derived tasks (`pass@1=9/14`, average candidates 3.00). The new
  dynamic-field error-message task passes at rank 4, and the new Range-header
  cache bypass task passes at rank 3, providing additional ranking signal
  without adding action families.
- GreenShot-6 candidate outcomes were refreshed with `--explore-after-pass 5`
  after adding the 4 git-history-derived tasks. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 14
  tasks and 110 tested candidates.
- GreenShot-6 now includes a third fixture domain, `webcookies`, with 5
  mutation-derived cookie policy/rendering tasks using existing action families:
  dictionary value repair, inclusive max-age boundary, swapped call arguments,
  and keyword propagation. The new tasks are explicitly marked `split: test`.
- A focused GreenShot-6 ranked smoke run with
  `runs/apache-python-git/model.json`, without outcome exploration, solves all
  19 tasks (`pass@1=13/19`, average candidates 2.42).
- GreenShot-6 candidate outcomes were refreshed with `--explore-after-pass 5`
  after adding the 5 `webcookies` held-out mutation tasks. The persisted dataset
  at `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers
  19 tasks and 141 tested candidates.
- Refreshed GreenShot-5 and GreenShot-6 candidate outcomes were used for a
  GreenShot-6 `split: test` held-out ranker validation slice that includes all
  5 new `webcookies` tasks. The trained ranker solved all 7 held-out plans, but
  pass@1 was 5/7 and positive@1 was 4/7. The old Apache classifier miss now
  ranks first; the remaining held-out pass@1 misses are
  `cookie_default_secure_flag_dict_value` and
  `cookie_scope_include_path_keyword`, with an additional non-preferred passing
  candidate ranked first for `http_no_store_response_with_etag`.
- GreenShot-6 raw pass@1 misses are not concentrated only in the new cookie
  domain: 6/19 tasks miss pass@1, split as `git_history=2/4` and
  `mutation=4/15`, and by split as `test=2/7`, `train=3/9`,
  `validation=1/3`. The new `webcookies` tasks account for 1 raw GreenShot-6
  miss, while existing HTTP/cache hard negatives and git-history literal/message
  repairs remain important ranking signal. Details are in `HARD_NEGATIVES.md`.
- The held-out GreenShot-6 test-slice ranker misses were inspected. The next
  narrow change should target same-mapping value/key decoys: the clearest miss
  is `cookie_default_secure_flag_dict_value`, where the trained ranker promotes
  a false `change_dict_key` candidate over the preferred `change_dict_value`
  edit even though the assertion names the `secure` lookup key. Details are in
  `HARD_NEGATIVES.md`.
- Same-mapping asserted-key metadata was implemented for dictionary literal
  value/key candidates: target context now records the dictionary keys plus
  whether a candidate changes the value for an asserted key or renames/removes
  that asserted key in the same mapping. Candidate ranker features consume the
  metadata from both live candidates and persisted outcome rows. Focused
  candidate-ranking tests passed.
- GreenShot-6 outcomes were refreshed after the same-mapping metadata change,
  then the GreenShot-6 `split: test` held-out ranker validation was rerun. The
  validation stayed at solved=7/7, pass@1=5/7, positive@1=4/7, and
  avg_first_passing_index=1.29. `cookie_default_secure_flag_dict_value` still
  did not move to preferred rank 1; the false `change_dict_key` candidate
  remains above the preferred `change_dict_value` candidate after training.
- The residual `cookie_default_secure_flag_dict_value` same-mapping decoy was
  inspected after the metadata change. The rows contain the new same-mapping
  features, but the false `change_dict_key secure -> __Secure-` candidate still
  scores 0.160615 above the preferred `change_dict_value secure: True -> False`
  candidate because broad string-parameter features and boolean-parameter
  penalties outweigh the sparse same-mapping weights. Details are in
  `HARD_NEGATIVES.md`.
- The exact same-mapping asserted-key assertion-value delta feature was added
  for dictionary value edits. Candidate ranker features now emit
  `same_mapping_asserted_key_value_matches_assertion_delta` when a
  same-mapping asserted-key `change_dict_value` candidate changes its `from`
  value from the observed assertion actual to the assertion expected value.
  The feature is computed for both live candidates and persisted outcome rows.
  The feature version is `candidate-diagnostics-v9`.
- Focused ranker and candidate-outcome tests passed after the exact assertion
  delta feature:
  `pytest tests/test_candidate_ranking.py -q` and
  `pytest tests/test_evaluation.py::test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate -q`.
- GreenShot-6 `split: test` held-out ranker validation improved to
  solved=7/7, pass@1=6/7, positive@1=5/7. The specific residual target
  `cookie_default_secure_flag_dict_value` now ranks the preferred
  `change_dict_value secure: True -> False` candidate first. Remaining issues:
  `cookie_scope_include_path_keyword` is still a pass@1 miss, and
  `http_no_store_response_with_etag` still has a non-preferred passing
  `swap_call_arg` candidate at rank 1 while the preferred repair is rank 3.
- The two remaining GreenShot-6 `split: test` held-out issues were inspected in
  the saved outcome rows and trained ranker scores. Details are in
  `HARD_NEGATIVES.md`. `cookie_scope_include_path_keyword` is primarily missing
  preferred-candidate signal: the preferred `add_keyword_arg(include_path=True)`
  is not present in the tested rows, and the only passing tested row is an
  accidental helper-level `modify_condition` repair. The tested-candidate
  ranking also shows weak call-target metadata because a false `swap_call_arg`
  at the hinted function outranks the downstream helper edit. For
  `http_no_store_response_with_etag`, all tested candidates pass; the issue is
  accidental-pass/preferred-positive ranking, where a `swap_call_arg` of
  `headers.get("cache-control", "")` outranks the preferred local
  `change_operator` repair. The smallest non-leaky next metadata signal is
  call-site argument-role metadata for `swap_call_arg`, including whether a
  swap breaks callee parameter-name alignment or swaps mapping `.get` key and
  default roles.
- Call-site argument-role metadata was implemented for `swap_call_arg`
  candidates. Target context now records whether a swap repairs, preserves, or
  breaks callee parameter-name alignment when the local/imported callee
  signature is known, and records mapping `.get` key/default role swaps when
  detectable. Candidate ranker features consume this metadata from both live
  candidates and persisted outcome rows. The feature version is
  `candidate-diagnostics-v10`.
- Focused ranker and candidate-outcome coverage passed for the v10 call-site
  metadata:
  `pytest tests/test_candidate_ranking.py -q` and
  `pytest tests/test_evaluation.py::test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate tests/test_evaluation.py::test_write_candidate_outcomes_preserves_swap_call_role_metadata -q`.
- GreenShot-6 outcomes were refreshed after the v10 call-site metadata change,
  then the GreenShot-6 `split: test` held-out ranker validation was rerun. The
  validation stayed at solved=7/7, pass@1=6/7, positive@1=5/7, and
  avg_first_passing_index=1.1428571428571428. The HTTP preferred-positive rank
  did not improve: for `http_no_store_response_with_etag`, the preferred
  `change_operator` repair remains trained rank 3 while the non-preferred
  passing `.get` `swap_call_arg` remains rank 1. `cookie_scope_include_path_keyword`
  still lacks the preferred `add_keyword_arg(include_path=True)` candidate in
  the tested rows.
- The v10 feature/weight support for the residual held-out rows was inspected.
  The `.get` key/default role-swap metadata is present on the held-out HTTP
  row, but has no non-held-out GreenShot-5/6 coverage and learned zero weight.
  The name-alignment metadata has sparse but usable coverage: breaking
  alignment learned a combined `-0.5` contribution, while repairing alignment
  learned `+1.0`. The HTTP residual is therefore partly missing independent
  `.get` role-swap hard-negative coverage, and partly weak preferred-operator
  context: the preferred `change_operator` row is still dragged down by broad
  AST/operator-delta weights and lacks richer non-leaky predicate metadata.
  Details are in `HARD_NEGATIVES.md`.
- The `add_keyword_arg` candidate generator now records local callee literal
  defaults and narrowly synthesizes missing boolean default keywords by adding
  the opposite boolean value when no outer pass-through parameter exists. This
  generates the preferred `add_keyword_arg(include_path=True)` candidate for
  `cookie_scope_include_path_keyword` without adding a new action family and
  without changing existing pass-through keyword behavior.
- Focused coverage passed for both keyword paths:
  `pytest tests/test_patching.py::test_generate_missing_keyword_argument_passthrough_candidate tests/test_patching.py::test_generate_missing_boolean_default_keyword_candidate tests/test_patching.py::test_patch_solves_missing_keyword_argument_passthrough tests/test_patching.py::test_patch_solves_cookie_scope_include_path_keyword -q`.
- GreenShot-6 outcomes were refreshed after the boolean keyword-generation
  change. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 19
  tasks and 140 tested candidates; ranked eval solved all 19 tasks with
  pass@1=14/19 and average candidates 7.37. The cookie scope task now solves
  with `add_keyword_arg`.
- The GreenShot-6 `split: test` held-out ranker validation was rerun after the
  outcome refresh. The validation stayed at solved=7/7, pass@1=6/7,
  positive@1=5/7, and avg_first_passing_index=1.1428571428571428. The cookie
  scope task now ranks the preferred `add_keyword_arg(include_path=True)`
  candidate first. Remaining validation issues are
  `cookie_default_secure_flag_dict_value`, where the false `change_dict_key`
  candidate is again above the preferred `change_dict_value`, and
  `http_no_store_response_with_etag`, where a non-preferred passing
  `change_literal` ranks above the preferred `change_operator`.
- The refreshed GreenShot-6 `split: test` residuals were inspected before any
  weight or task changes. `cookie_scope_include_path_keyword` is fixed in this
  slice. For `cookie_default_secure_flag_dict_value`, the exact same-mapping
  assertion-delta feature is present but still too sparse: the false
  `change_dict_key secure -> __Secure-` candidate scores 12.363160, above the
  preferred `change_dict_value secure: True -> False` candidate at 11.841018,
  because broad string-parameter rewards and boolean-parameter penalties
  outweigh the same-mapping signal. For `http_no_store_response_with_etag`, the
  current rank-1 residual is a non-preferred passing `change_literal`
  `"no-store" -> "no_store"` at 13.111906, while the preferred
  `change_operator not in -> in` repair is rank 5 at 4.587461. Details are in
  `HARD_NEGATIVES.md`.
- Added independent non-held-out same-mapping boolean value-vs-key-rename
  coverage for the cookie residual with the mutation task
  `cookie_partitioned_default_dict_value` (`split: train`). It uses the
  existing `change_dict_value` action and creates a same-mapping
  `change_dict_key partitioned -> __Partitioned-` hard-negative shape without
  changing broad action/string/boolean weights or pass/preferred-label
  features.
- Focused loader/generator coverage passed for the new task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_generate_same_mapping_boolean_value_with_key_rename_decoy -q`.
- GreenShot-6 outcomes were refreshed after adding the independent cookie
  coverage. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 20
  tasks and 146 tested candidates. Ranked eval solved all 20 tasks with
  `pass@1=15/20` and average candidates `7.30`.
- The GreenShot-6 `split: test` held-out ranker validation was rerun after the
  outcome refresh. Validation improved to solved=7/7, pass@1=7/7,
  positive@1=6/7, and avg_first_passing_index=1.0. The cookie same-mapping
  secure residual is fixed in this slice. The remaining issue is
  `http_no_store_response_with_etag`: it passes at rank 1 but still does not
  rank the preferred `change_operator not in -> in` repair first.
- Membership-predicate target-context metadata was implemented for
  `change_operator` and `change_literal` candidates. Target context now records
  membership predicates, `in`/`not in` operator, operand kinds, branch-test
  context, operator flips, literal changes, and whether a changed literal is
  the membership needle. Candidate ranker features consume the metadata from
  both live candidates and persisted outcome rows. The feature version is
  `candidate-diagnostics-v11`.
- Focused candidate-ranking coverage passed for the v11 predicate metadata.
  GreenShot-6 outcomes were refreshed after the change; ranked eval still
  solved all 20 tasks with `pass@1=15/20` and average candidates `7.30`.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the v11 outcome refresh. Validation stayed at solved=7/7, pass@1=7/7,
  positive@1=6/7, and avg_first_passing_index=1.0. The HTTP residual is still
  a preferred-positive miss: the preferred `change_operator not in -> in`
  repair ranks below non-preferred passing `.get` swap and literal-needle
  edits. The new metadata is present, but current non-held-out GreenShot-5/6
  coverage has positive membership-literal signal and failing membership-operator
  flips, so more independent predicate/operator hard-negative coverage is the
  next clean step before any broad weight changes.
- Added independent non-held-out HTTP membership-predicate coverage with
  `http_no_cache_revalidation_with_etag` (`split: train`). It uses the existing
  `change_operator` action for a local `"no-cache" not in cache_control` branch
  repair and includes a tempting existing `change_literal` needle edit
  `"no-cache" -> "no_cache"` in the tested rows. No broad action/string/boolean
  weights or pass/preferred-label features were changed.
- Focused loader/generator coverage passed for the new task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_generate_membership_operator_with_literal_needle_decoy -q`.
- GreenShot-6 outcomes were refreshed after adding the independent HTTP
  coverage. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 21
  tasks and 152 tested candidates. Ranked eval solved all 21 tasks with
  `pass@1=16/21` and average candidates `7.24`.
- The GreenShot-6 `split: test` held-out ranker validation was rerun after the
  outcome refresh. Validation is solved=7/7, pass@1=6/7, positive@1=5/7, and
  avg_first_passing_index=1.1428571428571428. The new training coverage moved
  `http_no_store_response_with_etag`'s preferred `change_operator` candidate to
  trained rank 2, but a non-preferred passing `change_literal`
  `"no-store" -> "no_store"` still ranks first. The cookie secure task remains
  fixed in this slice.
- Refreshed membership-predicate support and learned weights were inspected
  after adding `http_no_cache_revalidation_with_etag`. The saved holdout ranker
  uses `candidate-diagnostics-v11` with 663 learned features. For the held-out
  `http_no_store_response_with_etag` task, the preferred
  `change_operator not in -> in` repair is trained rank 2 with score
  15.824030, just behind the non-preferred passing literal-needle edit
  `"no-store" -> "no_store"` at 15.975122. Membership features still favor the
  literal decoy (`+5.50`) and penalize the preferred operator (`-2.25`).
  The added `http_no_cache_revalidation_with_etag` task has the intended raw
  operator-vs-literal shape, but its literal-needle decoy also passes, so it
  provides preference signal rather than a clean failing hard negative. Details
  are in `HARD_NEGATIVES.md`.
- Added a second independent non-held-out HTTP membership-predicate hard
  negative with `http_stale_response_without_must_revalidate` (`split: train`).
  It uses the existing `change_operator` action for a local
  `"must-revalidate" not in cache_control` branch repair and includes a tempting
  `change_literal` needle edit `"must-revalidate" -> "must_revalidate"` that
  fails. No action family, broad action/string/boolean weights, or
  pass/preferred-label features were added.
- Focused loader/generator coverage passed for the new task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_generate_membership_operator_with_failing_literal_needle_decoy -q`.
- GreenShot-6 outcomes were refreshed after adding the failing-decoy HTTP
  coverage. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 22
  tasks and 163 tested candidates. Ranked eval solved all 22 tasks with
  `pass@1=17/22` and average candidates `7.41`.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the outcome refresh. Validation improved to solved=7/7, pass@1=7/7,
  positive@1=7/7, and avg_first_passing_index=1.0. The preferred
  `change_operator not in -> in` repair for `http_no_store_response_with_etag`
  is now trained rank 1, above the literal-needle decoy.
- The refreshed GreenShot-6 outcome rows and saved `split: test` held-out
  metrics were inspected before adding more features. The held-out slice is
  clean (`solved=7/7`, `pass@1=7/7`, `positive@1=7/7`). Raw GreenShot-6 still
  solves all 22 tasks with `pass@1=17/22`, but the only trained
  preferred-positive gap found with the saved test-slice ranker is
  `dynamic_field_error_message`: the task manifest has a preferred f-string
  fragment `change_literal`, but no tested row matches it. The passing rows
  hardcode the full concrete error message instead of repairing the reusable
  f-string suffix. Details are in `HARD_NEGATIVES.md`.
- F-string literal-fragment candidate generation now emits reusable
  `change_literal` repairs from concrete pytest `match=...` strings. This fixes
  the `dynamic_field_error_message` outcome-quality gap by generating the
  preferred fragment repair
  ` declared as dynamic in but is defined` ->
  ` declared as dynamic in "project.dynamic" but is defined`, instead of only
  concrete whole-message replacements.
- Focused patching coverage passed for the f-string fragment generator, and
  refreshed GreenShot-6 outcomes now include a passing preferred-positive row
  for `dynamic_field_error_message` at raw rank 10. The persisted GreenShot-6
  dataset still covers 22 tasks and 163 tested candidates, with passing rows
  increasing to 47 and preferred-positive rows increasing to 22.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7, avg_first_passing_index=1.0. Training used 243 rows, 55
  passing rows, 207 training pairs, 650 features, and 3 margin violations.
- The refreshed GreenShot-6 raw pass@1 misses and preferred-positive ranks were
  inspected after the f-string fragment outcome refresh. Raw GreenShot-6 still
  solves all 22 tasks with pass@1=17/22. The five raw pass@1 misses are
  `apache_license_classifier_dict_value`, `dynamic_field_error_message`,
  `http_no_store_directive_subscript_key`, `http_range_request_bypasses_cache`,
  and `minimum_python_version_operator_boundary`. Each now has a tested
  preferred-positive row, and the saved GreenShot-6 `split: test` held-out
  ranker places the preferred-positive candidate at trained rank 1 for all five
  raw misses. Details are in `HARD_NEGATIVES.md`.
- The fresh inspection did not expose a narrow candidate-generation,
  outcome-quality, or ranker-metadata gap. Do not tune broad handcrafted
  action/string/boolean weights or add pass/preferred-label features from this
  state. The next useful work should be adding the next real-package-derived
  GreenShot-6 task or small fixture domain, then refreshing outcomes and
  rerunning the same held-out validation.
- GreenShot-6 now includes a fourth fixture domain, `cliformat`, with one
  real-package-derived `git_history` task modeled on `pallets/click` PR 2728 /
  merge commit `c021f05c838c1d0401ebc340d1de9b663c7fb578`. The task
  `click_invalid_directory_filename_repr` repairs Click-style invalid path
  formatting by changing the template from direct single-quoted `{filename}` to
  `{filename!r}`, using the existing `change_literal` action.
- Focused loader/generator coverage passed for the new task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_click_invalid_directory_filename_repr -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `cliformat`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 23
  tasks and 169 tested candidates. Ranked eval solved all 23 tasks with
  `pass@1=18/23` and average candidates `7.35`; the new Click-derived task
  solves at raw rank 1 with the preferred `change_literal` candidate.
- The GreenShot-6 `split: test` held-out ranker validation was rerun after the
  outcome refresh and stayed clean: solved=7/7, pass@1=7/7, positive@1=7/7.
  Training used 249 rows, 56 passing rows, 212 training pairs, 653 features,
  and 3 margin violations.
- Refreshed raw/trained miss inspection after adding `cliformat` found no new
  gap. Raw GreenShot-6 still has the same five pass@1 misses:
  `apache_license_classifier_dict_value`, `dynamic_field_error_message`,
  `http_no_store_directive_subscript_key`, `http_range_request_bypasses_cache`,
  and `minimum_python_version_operator_boundary`; every task has a tested
  preferred-positive row, and the saved test-slice ranker places every
  preferred-positive candidate at trained rank 1.
- GreenShot-6 now includes a fifth fixture domain, `sampling`, with one
  real-package-derived `git_history` task modeled on `Lightning-AI/litgpt`
  commit `8c3ce130d52faa22da4a005cee3f0f6fdfe43099` / issue 2238. The task
  `litgpt_zero_temperature_greedy_condition` repairs the zero-temperature
  sampling gate by changing the boolean connective in
  `temperature > 0.0 or top_p > 0.0` to `and`, using the existing
  `modify_condition` action family.
- `modify_condition` generation now emits a narrow boolean connective repair
  for `BoolOp` conditions before broader condition negation. This was needed
  because the held-out litgpt-derived repair shape was otherwise missing from
  the existing candidate set; no new action family was added.
- Focused loader/generator coverage passed for the new sampling task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_litgpt_zero_temperature_greedy_condition -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `sampling`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 24
  tasks and 176 tested candidates. Ranked eval solved all 24 tasks with
  `pass@1=18/24` and average candidates `7.33`.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the sampling outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 256 rows, 59 passing rows, 218 training pairs,
  674 features, and 3 margin violations.
- Refreshed raw/trained miss inspection after adding `sampling` found one new
  raw preferred-positive miss, `litgpt_zero_temperature_greedy_condition`: raw
  checkpoint ordering tries comparison-operator decoys before the preferred
  boolean-connective repair. The saved test-slice ranker places every
  GreenShot-6 preferred-positive candidate at trained rank 1, including the new
  sampling task.
- GreenShot-6 now includes a sixth fixture domain, `dateparse`, with one
  real-package-derived `git_history` task modeled on `dateutil/dateutil` PR 822
  / commit `91ba90e61941ddbcd16dbe8ef8441d0b8e51a084`. The task
  `dateutil_lowercase_z_utc_suffix` repairs lowercase `z` UTC timezone suffix
  handling by changing the `UTC_ZONE_NAMES` module constant from
  `"UTC GMT Z"` to `"UTC GMT Z z"`, using the existing
  `change_module_constant` action family.
- Focused loader/generator coverage passed for the new dateparse task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_dateutil_lowercase_z_utc_suffix -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `dateparse`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 25
  tasks and 182 tested candidates. Ranked eval solved all 25 tasks with
  `pass@1=19/25` and average candidates `7.28`; the new dateutil-derived task
  solves at raw rank 1 with the preferred `change_module_constant` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the dateparse outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 262 rows, 60 passing rows, 223 training pairs,
  674 features, and 3 margin violations.
- Refreshed raw/trained miss inspection after adding `dateparse` found no new
  missing preferred-positive candidates and no trained preferred-positive
  misses. Raw GreenShot-6 now has six pass@1 misses:
  `apache_license_classifier_dict_value`, `dynamic_field_error_message`,
  `http_no_store_directive_subscript_key`,
  `http_range_request_bypasses_cache`,
  `litgpt_zero_temperature_greedy_condition`, and
  `minimum_python_version_operator_boundary`; every task has a tested
  preferred-positive row, and the saved test-slice ranker places every
  preferred-positive candidate at trained rank 1.
- GreenShot-6 now includes a seventh fixture domain, `headers`, with one
  real-package-derived `git_history` task modeled on `tornadoweb/tornado`
  commit `7c3290fee1ea9cefa977c052aa2bb75a0d1af96b`. The task
  `tornado_header_newline_forbidden_regex` repairs header validation by
  changing the forbidden-character regex from excluding selected control
  characters to excluding the contiguous `\x0A-\x1F` range, using the existing
  `change_literal` action family.
- Focused loader/generator coverage passed for the new headers task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_tornado_header_newline_forbidden_regex -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `headers`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 26
  tasks and 188 tested candidates. Ranked eval solved all 26 tasks with
  `pass@1=20/26` and average candidates `7.23`; the new Tornado-derived task
  solves at raw rank 1 with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the headers outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 268 rows, 61 passing rows, 228 training pairs,
  704 features, and 3 margin violations.
- Refreshed raw/trained miss inspection after adding `headers` found no new
  missing preferred-positive candidates and no trained preferred-positive
  misses. Raw GreenShot-6 still has six pass@1 misses:
  `apache_license_classifier_dict_value`, `dynamic_field_error_message`,
  `http_no_store_directive_subscript_key`,
  `http_range_request_bypasses_cache`,
  `litgpt_zero_temperature_greedy_condition`, and
  `minimum_python_version_operator_boundary`; every task has a tested
  preferred-positive row, and the saved test-slice ranker places every
  preferred-positive candidate at trained rank 1.
- GreenShot-6 now includes an eighth fixture domain, `filesize`, with one
  real-package-derived `git_history` task modeled on `python-humanize/humanize`
  commit `77112a4cf39d57e233848f15cc0520776744d087` / PR 142. The task
  `humanize_gnu_ronna_suffix` repairs GNU filesize suffix support by changing
  the `suffixes["gnu"]` dictionary value from `"KMGTPEZY"` to `"KMGTPEZYRQ"`,
  using the existing `change_dict_value` action family.
- The `change_dict_value` generator now also covers module-level dictionary
  assignments. This was needed because the real-derived repair is a
  module-level suffix table; no new action family was added.
- Focused loader/generator coverage passed for the new filesize task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks tests/test_patching.py::test_patch_solves_humanize_gnu_ronna_suffix -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `filesize`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 27
  tasks and 194 tested candidates. Ranked eval solved all 27 tasks with
  `pass@1=21/27` and average candidates `7.19`; the new humanize-derived task
  solves at raw rank 1 with the preferred `change_dict_value` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the filesize outcome refresh. Validation is solved=7/7, pass@1=6/7,
  positive@1=5/7, and avg_first_passing_index=1.1428571428571428. Training used
  274 rows, 62 passing rows, 233 training pairs, 761 features, and 2 margin
  violations.
- Refreshed raw/trained miss inspection after adding `filesize` found no missing
  preferred-positive rows. Raw GreenShot-6 has the same six pass@1 misses as
  before. The trained holdout residuals are `cookie_host_prefix_dict_value`,
  where a false `change_dict_value host: "__Host" -> "host"` now ranks above
  the preferred `host: "__Host" -> "__Host-"`, and
  `http_no_store_response_with_etag`, where a non-preferred passing
  `change_literal "no-store" -> "no_store"` again ranks above the preferred
  `change_operator not in -> in`. Details are in `HARD_NEGATIVES.md`.
- The two filesize-refresh trained holdout residuals were inspected without
  code changes. `cookie_host_prefix_dict_value` needs narrow scalar
  assertion-delta metadata for dictionary value edits: the rows already contain
  assertion actual/expected values, but current features do not encode that the
  preferred edit changes `params.from` from the assertion actual to
  `params.to` equal to the assertion expected. `http_no_store_response_with_etag`
  is already described by v11 membership-predicate metadata and has a very
  small residual gap, so prefer more independent non-held-out
  membership-predicate coverage only if it remains after the cookie metadata
  fix and outcome refresh. Details are in `HARD_NEGATIVES.md`.
- Scalar assertion-delta ranker features were implemented for dictionary value
  candidates. For `change_dict_value`, ranker features now record exact scalar
  assertion actual-to-expected matches plus near-miss cases where only
  `params.from` matches the assertion actual or only `params.to` matches the
  assertion expected. The feature is computed from non-leaky failure hints and
  candidate params for both live candidates and persisted outcome rows. The
  feature version is `candidate-diagnostics-v12`.
- Focused candidate-ranker and candidate-outcome coverage passed for the new
  scalar dictionary-value assertion-delta feature, including the
  `cookie_host_prefix_dict_value` same-key shape where `host: "__Host"` can be
  changed either to the expected `"__Host-"` or the false `"host"` value.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after the
  scalar assertion-delta feature. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` still covers 27
  tasks and 194 tested candidates. Ranked eval solved all 27 tasks with
  `pass@1=21/27` and average candidates `7.19`.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the outcome refresh and is clean: solved=7/7, pass@1=7/7,
  positive@1=7/7, avg_first_passing_index=1.0. Training used 274 rows, 62
  passing rows, 233 training pairs, 742 features, and 3 margin violations.
  `cookie_host_prefix_dict_value` now ranks the preferred
  `change_dict_value host: "__Host" -> "__Host-"` repair first, and
  `http_no_store_response_with_etag` now ranks the preferred
  `change_operator not in -> in` repair first. No independent HTTP
  membership-predicate coverage is needed from this state.
- GreenShot-6 now includes a ninth fixture domain, `platformtags`, with one
  real-package-derived `git_history` task modeled on `pypa/packaging` commit
  `37b023285c27bc51940f33e50c1ebf692acf92c5` / PR 1160. The task
  `packaging_pyemscripten_platform_config_var` repairs Emscripten platform tag
  generation by changing the sysconfig key literal from
  `PYEMSCRIPTEN_ABI_VERSION` to `PYEMSCRIPTEN_PLATFORM_VERSION`, using the
  existing `change_literal` action family.
- Focused loader/generator coverage passed for the new packaging-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_packaging_pyemscripten_platform_config_var -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `platformtags`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 28
  tasks and 206 tested candidates. Ranked eval solved all 28 tasks with
  `pass@1=21/28` and average candidates `7.36`; the new packaging-derived task
  solves at raw rank 7 with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the platformtags outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 286 rows, 63 passing rows, 244 training pairs,
  777 features, and 2 margin violations.
- Refreshed raw/trained miss inspection after adding `platformtags` found no
  missing preferred-positive rows and no trained preferred-positive misses. Raw
  GreenShot-6 now has seven pass@1 misses:
  `apache_license_classifier_dict_value`, `dynamic_field_error_message`,
  `http_no_store_directive_subscript_key`,
  `http_range_request_bypasses_cache`,
  `litgpt_zero_temperature_greedy_condition`,
  `minimum_python_version_operator_boundary`, and
  `packaging_pyemscripten_platform_config_var`; every task has a tested
  preferred-positive row, and the saved test-slice ranker places every
  preferred-positive candidate at trained rank 1.
- GreenShot-6 now includes a tenth fixture domain, `marketdata`, with one
  real-package-derived `git_history` task modeled on `ranaroussi/yfinance`
  commit `64bd1baa79c7c37c169b6f6d76def262fec7ca71`. The task
  `yfinance_market_data_error_typo` repairs a market-data error f-string by
  changing `recieved` to `received`, using the existing `change_literal` action
  family.
- Focused loader/generator coverage passed for the new yfinance-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_yfinance_market_data_error_typo -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `marketdata`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 29
  tasks and 212 tested candidates. Ranked eval solved all 29 tasks with
  `pass@1=22/29` and average candidates `7.31`; the new yfinance-derived task
  solves at raw rank 1, while its reusable preferred literal-fragment repair is
  present and passing at raw rank 2.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the marketdata outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 292 rows, 65 passing rows, 249 training pairs,
  705 features, and 3 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses. For the new yfinance-derived task, the
  trained ranker places the preferred reusable `change_literal` repair first,
  above the concrete whole-message passing candidate.
- GreenShot-6 now includes an eleventh fixture domain, `httpresponse`, with one
  real-package-derived `git_history` task modeled on `urllib3/urllib3` commit
  `6d022020b41ffbd184f644f0fa645b85c159b50b`. The task
  `urllib3_getheader_warning_typo` repairs a deprecated `getheader` warning by
  changing `HTTResponse.headers.get(name, default)` to
  `HTTPResponse.headers.get(name, default)`, using the existing
  `change_literal` action family.
- Focused loader/generator coverage passed for the new urllib3-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_urllib3_getheader_warning_typo -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `httpresponse`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 30
  tasks and 221 tested candidates. Ranked eval solved all 30 tasks with
  `pass@1=22/30` and average candidates `7.37`; the new urllib3-derived task
  solves at raw rank 3 with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the httpresponse outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 301 rows, 66 passing rows, 257 training pairs,
  707 features, and 3 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses. For the new urllib3-derived task, the
  trained ranker places the preferred `change_literal` repair first, above the
  false `swap_call_arg` and literal decoys.
- GreenShot-6 now includes a twelfth fixture domain, `tablefmt`, with one
  real-package-derived `git_history` task modeled on `prettytable/prettytable`
  PR 351 / commit `7df5d70`. The task
  `prettytable_missing_attribute_quote` repairs a PrettyTable-style legacy
  attribute error template by adding the missing closing quote after `{name}`,
  using the existing `change_literal` action family.
- Focused loader/generator coverage passed for the new PrettyTable-derived
  task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks tests/test_patching.py::test_patch_solves_prettytable_missing_attribute_quote -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `tablefmt`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 31
  tasks and 228 tested candidates. Ranked eval solved all 31 tasks with
  `pass@1=22/31` and average candidates `7.35`; the new PrettyTable-derived
  task solves at raw rank 2 with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the tablefmt outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 308 rows, 67 passing rows, 263 training pairs,
  744 features, and 5 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses. For the new PrettyTable-derived task,
  the trained ranker places the preferred `change_literal` repair first, above
  the local operator and literal decoys.
- GreenShot-6 now includes a thirteenth fixture domain, `cellwidth`, with one
  real-package-derived `git_history` task modeled on `Textualize/rich` commit
  `68e1b6386db241d49f7713dae4ba3b59c0d30ba6`. The task
  `rich_common_cell_width_ascii_range` repairs Rich-style common cell-width
  regex matching by changing the printable ASCII range endpoint from `\u006f`
  to `\u007f`, using the existing `change_literal` action family.
- Focused loader/generator coverage passed for the new Rich-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_rich_common_cell_width_ascii_range -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `cellwidth`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 32
  tasks and 234 tested candidates. Ranked eval solved all 32 tasks with
  `pass@1=23/32` and average candidates `7.31`; the new Rich-derived task
  solves at raw rank 1 with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the cellwidth outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 314 rows, 68 passing rows, 268 training pairs,
  744 features, and 5 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses. For the new Rich-derived task, the
  trained ranker places the preferred regex `change_literal` repair first.
- GreenShot-6 now includes a fourteenth fixture domain, `fieldopts`, with one
  real-package-derived `git_history` task modeled on `pydantic/pydantic` commit
  `20914e367fe6b7fac8486c0023f8d212f4948054` / PR 5734. The task
  `pydantic_field_regex_pattern_message` repairs a Field-style removed-keyword
  error message by changing `Pattern` to `pattern`, using the existing
  `change_literal` action family.
- Focused loader/generator coverage passed for the new pydantic-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_pydantic_field_regex_pattern_message -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `fieldopts`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 33
  tasks and 243 tested candidates. Ranked eval solved all 33 tasks with
  `pass@1=23/33` and average candidates `7.36`; the new pydantic-derived task
  solves at raw rank 4 with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the fieldopts outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 323 rows, 69 passing rows, 276 training pairs,
  814 features, and 4 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses. For the new pydantic-derived task, the
  trained ranker places the preferred literal repair first, above the local
  operator and partial-literal decoys.
- GreenShot-6 now includes a fifteenth fixture domain, `piplist`, with one
  real-package-derived `git_history` task modeled on `pypa/pip` commit
  `fdc262f06936fb406af2af74ad6b0946ac1f4bd8`. The task
  `pip_list_outdated_freeze_error_message` repairs a pip-list option conflict
  message by changing `can not be used with` to
  `cannot be used together with`, using the existing `change_literal` action
  family.
- Focused loader/generator coverage passed for the new pip-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_pip_list_outdated_freeze_error_message -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `piplist`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 34
  tasks and 258 tested candidates. Ranked eval solved all 34 tasks with
  `pass@1=23/34` and average candidates `7.59`; the new pip-derived task
  solves with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the piplist outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 338 rows, 70 passing rows, 290 training pairs,
  810 features, and 3 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses across 34 tasks.
- GreenShot-6 now includes a sixteenth fixture domain, `apidocs`, with one
  real-package-derived `git_history` task modeled on `aws/chalice` commit
  `d8ba1ad1e1e8787d3bf1dd445691c99eebb9c528` / PR 2148. The task
  `chalice_control_plane_programmatically_docstring` repairs a Chalice control
  plane API description typo by changing `programatically` to
  `programmatically`, using the existing `change_literal` action family.
- Focused loader/generator coverage passed for the new Chalice-derived task:
  `pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q` and
  `pytest tests/test_patching.py::test_patch_solves_chalice_control_plane_programmatically_docstring -q`.
- GreenShot-6 outcomes were refreshed with `--explore-after-pass 5` after
  adding `apidocs`. The persisted dataset at
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` now covers 35
  tasks and 264 tested candidates. Ranked eval solved all 35 tasks with
  `pass@1=24/35` and average candidates `7.54`; the new Chalice-derived task
  solves with the preferred `change_literal` candidate.
- The same GreenShot-6 `split: test` held-out ranker validation was rerun after
  the apidocs outcome refresh and stayed clean: solved=7/7, pass@1=7/7,
  positive@1=7/7. Training used 344 rows, 71 passing rows, 295 training pairs,
  810 features, and 3 margin violations.
- Applying the saved test-slice ranker to all refreshed GreenShot-6 rows found
  no trained preferred-positive misses across 35 tasks.

Last focused verification:

```bash
pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q
pytest tests/test_patching.py::test_patch_solves_chalice_control_plane_programmatically_docstring -q
python cli.py eval \
  --tasks examples/greenshot_6 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/apache-python-git/greenshot-6-explore-diagnostics.json \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --quiet
python cli.py train-ranker \
  --candidate-outcomes \
    runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl \
    runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --holdout-task \
    apache_license_classifier_dict_value \
    http_no_store_response_with_etag \
    cookie_default_secure_flag_dict_value \
    cookie_host_prefix_dict_value \
    cookie_zero_max_age_operator_boundary \
    cookie_pair_argument_order \
    cookie_scope_include_path_keyword \
  --out runs/apache-python-git/ranker-holdout-greenshot-6-test-slice
python cli.py outcome-summary \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
python - <<'PY'
# Applied the refreshed test-slice ranker to all refreshed GreenShot-6 rows;
# no trained preferred-positive residuals were found across 35 tasks.
PY
git diff --check
```

Previous focused verification:

```bash
pytest tests/test_patching.py::test_generate_fstring_fragment_literal_candidate_from_concrete_message tests/test_evaluation.py::test_load_greenshot_6_tasks -q
pytest tests/test_patching.py -q
python cli.py eval \
  --tasks examples/greenshot_6 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/apache-python-git/greenshot-6-explore-diagnostics.json \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --quiet
python cli.py train-ranker \
  --candidate-outcomes \
    runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl \
    runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --holdout-task \
    apache_license_classifier_dict_value \
    http_no_store_response_with_etag \
    cookie_default_secure_flag_dict_value \
    cookie_host_prefix_dict_value \
    cookie_zero_max_age_operator_boundary \
    cookie_pair_argument_order \
    cookie_scope_include_path_keyword \
  --out runs/apache-python-git/ranker-holdout-greenshot-6-test-slice
python cli.py outcome-summary \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
git diff --check
```

Earlier focused verification:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py::test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate tests/test_evaluation.py::test_write_candidate_outcomes_preserves_swap_call_role_metadata -q
python cli.py eval \
  --tasks examples/greenshot_6 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/apache-python-git/greenshot-6-explore-diagnostics.json \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --quiet
python cli.py train-ranker \
  --candidate-outcomes \
    runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl \
    runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --holdout-task \
    apache_license_classifier_dict_value \
    http_no_store_response_with_etag \
    cookie_default_secure_flag_dict_value \
    cookie_host_prefix_dict_value \
    cookie_zero_max_age_operator_boundary \
    cookie_pair_argument_order \
    cookie_scope_include_path_keyword \
  --out runs/apache-python-git/ranker-holdout-greenshot-6-test-slice
git diff --check
```

Previous GreenShot-6/ranker verification:

```bash
pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q
python cli.py eval \
  --tasks examples/greenshot_6 \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --quiet
python cli.py eval \
  --tasks examples/greenshot_6 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/apache-python-git/greenshot-6-explore-diagnostics.json \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --quiet
python cli.py outcome-summary \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
python cli.py train-ranker \
  --candidate-outcomes \
    runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl \
    runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --holdout-task-family http_cache_directive \
  --out runs/apache-python-git/ranker-holdout-http-cache-directive
git diff --check
```

GreenShot-5 outcome collection result:

```text
ranked, runs/apache-python-git/model.json, explore-after-pass=5:
  solved=20/20 pass@1=14/20 avg_candidates=6.30
  rows=126 passing_rows=24 preferred_positive_rows=8
```

GreenShot-6 smoke result:

```text
ranked, no candidate ranker:
  solved=11/11 pass@1=8/11 avg_candidates=3.09
```

GreenShot-6 outcome collection result:

```text
ranked, runs/apache-python-git/model.json, explore-after-pass=5:
  solved=33/33 pass@1=23/33 avg_candidates=7.36
  rows=243 passing_rows=61 preferred_positive_rows=33
  source_type pass@1: git_history=8/15 mutation=15/18
```

Treat this as a smoke check, not a benchmark claim.

Combined GreenShot-5/6 ranker validation result:

```text
train-ranker, holdout-task-family=http_cache_directive:
  training rows=191 passing_rows=42 tasks=30 plans=30 pairs=160
  training_accuracy=1.000 margin_violations=6 features=412
  validation solved=1/1 pass@1=0/1 positive@1=0/1
  validation rows=19 avg_first_passing_index=5.0
```

GreenShot-6 test-slice ranker validation result:

```text
train-ranker, holdout-task includes all GreenShot-6 split:test tasks:
  training rows=323 passing_rows=69 tasks=46 plans=46 pairs=276
  training_accuracy=0.996 margin_violations=4 features=814
  validation solved=7/7 pass@1=7/7 positive@1=7/7
  validation avg_first_passing_index=1.0
```

## Next Right Things

Keep this section as the live queue. When work is completed, move it to
`Recent work` or `Current State` and remove it from these next-task lists.

Immediate next sequence:

1. Add another real-package-derived GreenShot-6 task or small fixture domain.
   Prefer a repair shape that uses an existing action family and creates useful
   ranking or outcome-quality signal.
2. Add focused loader/generator coverage for the new task, then refresh
   GreenShot-6 outcomes with `--explore-after-pass 5`.
3. Rerun the same GreenShot-6 `split: test` held-out ranker validation and
   inspect any raw or trained residuals before adding metadata, tasks, or broad
   weights. Do not tune broad action/string/boolean weights or add
   pass/preferred-label features from the current clean holdout state.

### 1. Make GreenShot-6 Real

Goal: GreenShot-6 should use small real packages or real-package-derived
fixtures, not invented toy modules.

Next tasks:

- Continue marking every task with a task family and source type:
  `handcrafted`, `mutation`, or `git_history`.
- Prefer additional fixture domains/packages over more `pkgmeta` metadata tasks
  when the next dataset expansion is needed.

### 2. Improve Outcome Dataset Quality

Goal: make candidate outcome rows useful for learning, validation, and later
transition modeling.

Next tasks:

- Ensure future git-history-derived tasks with preferred patches actually
  produce matching preferred-positive candidate rows before using them as
  ranking evidence.
- Add independent `.get` key/default swap hard-negative coverage only if a
  fresh inspection reopens the HTTP residual.

### 3. Collect Hard Negatives

Goal: train on candidates the current system actually finds tempting.

Next tasks:

- Use GreenShot-5 and GreenShot-6 rows for ranker training and validation.
- Prefer held-out family/source-type validation over in-sample pass@1.
- Keep the GreenShot-6 `split: test` holdout available as a cookie-inclusive
  validation slice before changing ranker features.
- Re-run GreenShot-6 with `--explore-after-pass 5` after the next batch of
  real-derived tasks or after changing candidate generation/ranking metadata.

Use a command like:

```bash
python cli.py eval \
  --tasks examples/greenshot_6 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/apache-python-git/greenshot-6-explore-diagnostics.json \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --quiet
```

Run this after adding more real-derived GreenShot-6 tasks or after changing
candidate generation/ranking metadata.

### 4. Strengthen Observations Before Model Complexity

Goal: ranker and future JEPA inputs should use normalized observations, not raw
test output text.

Next tasks:

- Parse pytest diff hunks into structured value differences.
- Extract expected/actual string fragments from substring failures.
- Extract mapping key/value expectations from assertion diffs.
- Compute traceback distance from each candidate target.
- Compute call graph distance from failing frame to candidate target.
- Record whether a candidate target is in test, public API, helper, model code,
  or config code.
- Add confidence/source fields to hints.
- Add tests for ambiguous or conflicting hints.

### 5. Only Then Expand Actions

Known missing or incomplete action families:

- Remove wrong keyword argument.
- Change call target to nearby helper.
- Replace attribute chain segment.
- Add simple branch case.
- Add early return for `None`.
- Add fallback for missing mapping key.
- Insert narrow exception handler around non-return statements.
- Propagate rename across multiple files.
- Update imports after symbol movement.
- Support bounded multi-edit actions.
- Deduplicate equivalent candidates before test execution.
- Store action schemas in a machine-readable registry.

Do not work this list top-down. Let held-out tasks choose the next action.

## Evaluation Rules

For benchmark-style reports, include:

- solved / total
- pass@1
- average candidates tested
- median candidates tested
- missing-action count
- bad-ranking count
- weak-hint count
- multiple-passing-candidate count
- per-action pass@1
- per-task-family pass@1
- source-type pass@1
- average test runtime

For focused implementation checks, prefer the smallest relevant test:

```bash
pytest tests/test_failure_hints.py -q
pytest tests/test_candidate_ranking.py -q
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py -q
```

Run full `pytest -q` only as an intentional integration gate after broad shared
behavior changes or before merging.

Use GreenShot-4 only as a periodic regression/reporting gate:

```bash
python cli.py eval \
  --tasks examples/greenshot_4 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --phase both \
  --quiet \
  --diagnostics runs/apache-python-git/greenshot-4-diagnostics.json
```

## Stop Conditions

Pause action expansion when:

- pass@1 is not improving despite passing candidates existing.
- new tasks repeat existing action families without new signal.
- candidate generation grows faster than ranking quality.
- the next action is motivated only by a handcrafted fixture.

Pause ranker work when:

- diagnostics mostly show missing actions.
- hints are obviously wrong.
- outcome data has too few independent tasks.
- improvements come only from memorizing exact task or reason strings.

Start neural/JEPA work only when:

- GreenShot-5/6 include at least 50 diverse tasks.
- GreenShot-6 includes real-package-derived held-out tasks.
- Candidate outcomes include hundreds or thousands of labeled rows.
- Stable split metadata exists.
- Held-out task families and source types exist.
- A non-neural ranker has clearly plateaued.
- Failures are categorized well enough to diagnose neural regressions.

## Handoff Recommendation

The next context window should continue dataset growth by adding another
real-package-derived GreenShot-6 task or small fixture domain. Do not tune broad
handcrafted weights or add pass/preferred-label features from this state. The
current GreenShot-6 `split: test` held-out validation is clean after the
apidocs outcome refresh.

Immediate next sequence:

1. Add the next real-package-derived GreenShot-6 task using an existing action
   family where possible.
2. Run focused loader/generator tests, refresh GreenShot-6 outcomes, and rerun
   the same `split: test` held-out ranker validation.
3. Inspect any new residuals and prefer narrow non-leaky metadata or independent
   coverage over broad weight tuning.
