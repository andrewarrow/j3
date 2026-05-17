# GreenShot-6 Hard Negatives

Inspection source:

```bash
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
```

This pass inspected the GreenShot-6 families called out before ranker feature
work: `http_cache_directive`, `mapping_value`, and `operator_boundary`.

## Summary

GreenShot-6 still solves all tasks in these families, so the current issue is
ranking, not missing actions.

| Family | Tasks | Pass@1 | Hard-negative shape |
| --- | ---: | ---: | --- |
| `http_cache_directive` | 1 | 0/1 | Many same-score local mapping and operator edits outrank the correct subscript-key repair. |
| `mapping_value` | 4 | 3/4 | One classifier repair ties several wrong same-dict value edits before the correct key/value pair. |
| `operator_boundary` | 2 | 1/2 | One API-level call-argument candidate outranks the correct helper-level operator boundary edit. |

## Task Notes

### `http_no_store_directive_subscript_key`

- Family: `http_cache_directive`
- Preferred passing candidate: rank 14, `change_subscript_key` in
  `httpcache/policy.py`, changing `directives["no-store"]` to
  `directives["no_store"]`.
- The first 13 candidates are all plausible from local string evidence:
  dictionary value changes, added keys, comparison operator changes,
  dictionary-key changes, and the wrong subscript-key repair for `no-cache`.
- The failure contains both a value expectation and a negative key expectation:
  `directives["no_store"] is True` and `"no-store" not in directives`.
- Useful next signal: features that connect a subscript write to a returned
  mapping key should distinguish the correct candidate from edits that mutate
  initial defaults or unrelated cache-control directives.

### `apache_license_classifier_dict_value`

- Family: `mapping_value`
- Preferred passing candidate: rank 5, `change_dict_value` in
  `pkgmeta/metadata.py`, changing the `Apache-2.0` value to
  `License :: OSI Approved :: Apache Software License`.
- Ranks 1-4 all edit the `MIT` entry in the same dictionary. They tie the
  preferred candidate on hint score because the expected string is nearby but
  the assertion also names the input key through the tested API call.
- Useful next signal: before/after AST delta and candidate-target context
  should capture which dictionary key is being edited, not only that a nearby
  dictionary value can become the expected string.

### `minimum_python_version_operator_boundary`

- Family: `operator_boundary`
- Preferred passing candidate: rank 2, `change_operator` in
  `pkgmeta/metadata.py`, changing `>` to `>=`.
- Rank 1 is a public-API `swap_call_arg` candidate in `pkgmeta/api.py`.
- There are multiple passing candidates after the preferred edit because `<=`
  also satisfies this single boundary assertion.
- Useful next signal: equivalent/overlapping candidate metadata should separate
  genuinely preferred boundary repairs from broader or accidentally passing
  operator mutations.

### `http_304_cacheable_operator_boundary`

- Family: `operator_boundary`
- Preferred passing candidate: rank 1, `change_operator` in
  `httpcache/policy.py`, changing `<` to `<=`.
- Three candidates pass: the preferred `<=`, an over-broad `>=`, and a literal
  boundary change from `304` to `305`.
- Useful next signal: equivalent/overlapping candidate metadata should mark
  these as multiple passing but behaviorally different repairs.

## Implications For Next Work

- Add before/after AST delta features before tuning handcrafted feature weights.
- Record equivalent or overlapping candidates so pass labels can distinguish
  exact repairs from accidental passes.
- Keep `http_cache_directive` as a held-out validation slice after adding those
  metadata fields, because it is the clearest current hard-negative case.

## GreenShot-6 Test-Slice Holdout

Inspection source:

```bash
runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
```

Held-out validation command:

```bash
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
```

Result:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 5/7 | 4/7 | 1.29 |

Training used 220 non-held-out rows from the refreshed GreenShot-5 and
GreenShot-6 outcome datasets, with 45 passing rows, 32 plans, 186 training
pairs, 542 features, and 4 margin violations.

### Held-Out Task Notes

- `apache_license_classifier_dict_value` is no longer a held-out pass@1 miss:
  the trained ranker moves the preferred `change_dict_value` candidate from
  original rank 5 to rank 1.
- `cookie_default_secure_flag_dict_value` misses at rank 1 after training. The
  preferred `change_dict_value` candidate was originally rank 1, but a false
  `change_dict_key` candidate in the same `default_cookie_attributes` mapping is
  promoted above it.
- `cookie_scope_include_path_keyword` remains a held-out pass@1 miss. The
  passing repair is the original rank-2 `modify_condition` candidate in
  `normalize_scope`; a false `swap_call_arg` candidate in `cookie_scope_key`
  stays above it.
- `http_no_store_response_with_etag` passes at rank 1 after training, but not
  with the preferred positive. The ranker promotes an accidentally passing
  `swap_call_arg` candidate above the preferred `change_operator` repair.

### GreenShot-6 Miss Concentration

The refreshed GreenShot-6 outcome rows solve all 19 tasks with 13/19 pass@1.
The six original pass@1 misses are:

| Task | Family | Source | Split | First passing rank |
| --- | --- | --- | --- | ---: |
| `apache_license_classifier_dict_value` | `mapping_value` | `mutation` | `test` | 5 |
| `cookie_scope_include_path_keyword` | `keyword_propagation` | `mutation` | `test` | 2 |
| `dynamic_field_error_message` | `exception_message` | `git_history` | `train` | 8 |
| `http_no_store_directive_subscript_key` | `http_cache_directive` | `mutation` | `train` | 14 |
| `http_range_request_bypasses_cache` | `http_cache_range` | `git_history` | `train` | 2 |
| `minimum_python_version_operator_boundary` | `operator_boundary` | `mutation` | `validation` | 2 |

By source type, misses are `git_history=2/4` and `mutation=4/15`. By split,
they are `test=2/7`, `train=3/9`, and `validation=1/3`. The new `webcookies`
tasks account for 1 of the 6 GreenShot-6 raw pass@1 misses, but 2 of the 7
held-out test-slice ranker misses after retraining. The remaining misses are
not concentrated only in the new cookie domain: existing HTTP/cache hard
negatives and git-history-derived literal/message repairs still provide the
stronger evidence for observation and target-context work.

## Test-Slice Miss Inspection Decision

Inspection date: 2026-05-16.

The immediate next narrow change should be observation/target-context metadata
for same-mapping value/key decoys. The clearest failure is
`cookie_default_secure_flag_dict_value`: the raw ranked order already puts the
preferred `change_dict_value` candidate first, but the trained ranker promotes a
false `change_dict_key` candidate above it. Both candidates edit the same
`default_cookie_attributes` mapping and both touch the asserted key string
`secure`; the current features do not distinguish preserving the asserted lookup
key and changing its value from renaming/removing that key.

Concrete observed ordering after applying the held-out test-slice ranker:

| Task | Trained rank 1 | Preferred / first valid repair | Decision |
| --- | --- | --- | --- |
| `cookie_default_secure_flag_dict_value` | false `change_dict_key`, `secure` -> `__Secure-` | rank 2, preferred `change_dict_value`, `secure: True` -> `False` | Add same-mapping key/value intent metadata first. |
| `cookie_scope_include_path_keyword` | false `swap_call_arg` in `cookie_scope_key` | rank 2 passing `modify_condition` in `normalize_scope`; preferred `add_keyword_arg(include_path=True)` is not present in the tested rows | Keep as call-target/locality follow-up; this is partly missing preferred-candidate signal. |
| `http_no_store_response_with_etag` | non-preferred passing `swap_call_arg` | rank 3, preferred `change_operator`, `not in` -> `in` | Defer accidental-pass distinction until after the cleaner same-mapping fix. |

The candidate rows already include `asserted_mapping_keys`, and the ranker
currently emits features such as `action_hint_asserted_mapping_key_matches_key`
for the preferred value edit and `action_hint_asserted_mapping_key_matches_from`
for the false key edit. The next implementation should make that distinction
explicit enough for learning, for example by recording whether a candidate
preserves, removes, or creates the asserted lookup key within the same mapping.
This is narrower and less ambiguous than call-target locality because
`cookie_scope_include_path_keyword` does not include the preferred keyword
candidate in the current outcome rows, and it is less label-sensitive than
trying to distinguish all accidental passing repairs in
`http_no_store_response_with_etag`.

## Same-Mapping Metadata Follow-Up

Implementation result: same-mapping asserted-key metadata is now recorded for
dictionary literal key/value candidates and consumed by ranker features from
both live candidates and persisted candidate-outcome rows. Focused tests around
`change_dict_value` versus `change_dict_key` on the same asserted key passed.

Validation result after refreshing GreenShot-6 outcomes and rerunning the
GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 5/7 | 4/7 | 1.29 |

Residual: `cookie_default_secure_flag_dict_value` still does not move to
preferred rank 1. The false same-mapping `change_dict_key` candidate
(`secure` -> `__Secure-`) remains above the preferred `change_dict_value`
candidate (`secure: True` -> `False`) after training. The next sequence should
inspect that pair's trained scores and feature differences before adding any
new task, action family, or broad ranker weighting.

### Residual Pair Inspection

Inspection date: 2026-05-16.

Inspection source:

```bash
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

The refreshed outcome rows do contain the same-mapping metadata for both
candidates, so this is not a missing-row or missing-context issue.

| Candidate | Original rank | Passed | Preferred | Failure hint | Trained score |
| --- | ---: | --- | --- | ---: | ---: |
| `change_dict_value`, `secure: True` -> `False` | 1 | yes | yes | 52.0 | 11.169924 |
| `change_dict_key`, `secure` -> `__Secure-` | 4 | no | no | 50.0 | 11.330538 |

The false key rename wins by only `0.160615`. The new same-mapping features are
present, but they are too weak and too sparsely trained to overcome broader
learned parameter-type and token-overlap features:

- Preferred value edit features include
  `same_mapping_asserted_key_value_changed`,
  `action_same_mapping_asserted_key_value_changed:change_dict_value`, and
  `hint_asserted_mapping_key_matches_key`. These contribute only `+0.75`
  combined in this trained model.
- False key-rename features include
  `same_mapping_asserted_key_renamed_or_removed`,
  `action_same_mapping_asserted_key_renamed_or_removed:change_dict_key`, and
  `hint_asserted_mapping_key_matches_from`, but those learned weights are `0.0`.
- The false key rename is helped by broad string-parameter features:
  `param_type:from:str` and `param_type:to:str` contribute `+2.5` combined.
  It also avoids the preferred value edit's boolean-parameter penalties:
  `param_type:from:bool` and `param_type:to:bool` are `-1.5` combined for the
  preferred edit.
- The preferred value edit is helped by relation features and its slightly
  higher hint score, but those do not fully offset the parameter-type gap.

Non-held-out training coverage explains why the new same-mapping signal did not
move the pair by itself:

| Feature | Non-held-out rows | Passing rows | Tasks |
| --- | ---: | ---: | ---: |
| `same_mapping_asserted_key_value_changed` | 5 | 1 | 2 |
| `same_mapping_asserted_key_renamed_or_removed` | 1 | 0 | 1 |
| `hint_asserted_mapping_key_matches_key` | 6 | 1 | 3 |
| `hint_asserted_mapping_key_matches_from` | 1 | 0 | 1 |

Smallest next ranking signal: record and consume an exact assertion-value match
for same-mapping dictionary value edits. In this task, the failure hint already
has assertion `actual=True`, `expected=False`, and asserted mapping key
`secure`; the preferred candidate changes the same mapping's `secure` value
from `True` to `False`, while the false key candidate leaves the value as
`True` and removes the asserted lookup key. A narrow feature such as
`same_mapping_asserted_key_value_matches_assertion_delta` would distinguish
this pair without adding tasks, action families, or broad handcrafted weights.

### Exact Assertion Delta Follow-Up

Implementation result: the exact same-mapping asserted-key assertion-value delta
feature was implemented for dictionary value edits. Candidate ranker features
now emit `same_mapping_asserted_key_value_matches_assertion_delta` when a
same-mapping asserted-key `change_dict_value` candidate changes its `from`
value from the observed assertion actual to the assertion expected value. The
feature is available for both live candidates and persisted outcome rows. The
feature version is `candidate-diagnostics-v9`.

Focused verification passed:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py::test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate -q
git diff --check
```

GreenShot-6 `split: test` held-out ranker validation result after the feature:

| Slice | Plans | Solved | Pass@1 | Positive@1 |
| --- | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 6/7 | 5/7 |

`cookie_default_secure_flag_dict_value` now ranks the preferred
`change_dict_value secure: True -> False` candidate first. The false
`change_dict_key secure -> __Secure-` candidate is now second for that task.

Remaining held-out issues:

- `cookie_scope_include_path_keyword` is still a pass@1 miss. The top-ranked
  candidate is a false `swap_call_arg` in `cookie_scope_key`; the passing repair
  is still rank 2, and the preferred `add_keyword_arg(include_path=True)` is not
  present in the tested rows.
- `http_no_store_response_with_etag` still ranks a non-preferred passing
  `swap_call_arg` candidate first; the preferred `change_operator` repair is
  rank 3. This should be treated as accidental-pass/preferred-repair ranking
  signal, not a missing-action problem.

Next inspection sequence: focus on these two residual held-out issues before
adding tasks, action families, or broad handcrafted weights. For
`cookie_scope_include_path_keyword`, determine whether the problem is missing
preferred-candidate signal or weak call-target/locality metadata. For
`http_no_store_response_with_etag`, inspect non-leaky metadata that can
distinguish the preferred local operator repair from a broader accidentally
passing call-argument edit.

### Residual Test-Slice Inspection

Inspection date: 2026-05-16.

Inspection source:

```bash
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/greenshot-6-explore-diagnostics.json
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

The remaining held-out issues have different causes.

#### `cookie_scope_include_path_keyword`

This is primarily missing preferred-candidate signal, with a secondary bad
ranking among the candidates that were tested.

The preferred manifest repair is an existing `add_keyword_arg` action at the
`cookie_scope_key` call site:

```text
normalize_scope(host, path) -> normalize_scope(host, path, include_path=True)
```

No tested row contains that preferred candidate. The only passing tested row is
an accidental helper-level `modify_condition` repair in `normalize_scope` that
changes `if include_path:` to `if not (include_path):`.

Trained ranking on the tested rows:

| Trained rank | Original rank | Passed | Preferred | Candidate | Score |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 1 | no | no | `swap_call_arg` in `cookie_scope_key`, args `0 <-> 1` | 11.606667 |
| 2 | 2 | yes | no | `modify_condition` in `normalize_scope`, `include_path` -> `not (include_path)` | 3.050271 |

Why the false swap wins:

- The failure hint names `cookie_scope_key`, so the swap gets exact-symbol
  features: `hint_symbol_match`, `hint_call_graph_distance:0`, and
  `target_is_hinted_symbol`.
- The passing helper edit is only one upstream call away from the hinted
  function. It gets useful `target_is_downstream_of_hint` and
  `hint_call_graph_distance:1` features, but those do not overcome the exact
  symbol match plus the learned generic swap-call features.
- The current target context records only symbol-level call graph locality. It
  does not record whether a `swap_call_arg` candidate preserves or breaks the
  callee signature's argument-name alignment. In this case the original call
  already maps `host -> host` and `path -> path`; the swap would map
  `path -> host` and `host -> path`.
- The existing `add_keyword_arg` generator only passes through an outer
  parameter with the same name as the callee parameter. `cookie_scope_key` has
  no `include_path` parameter, so the preferred constant keyword
  `include_path=True` is not represented in the tested rows.

Implemented non-leaky signal for ranking tested candidates: call-site
argument-role metadata for `swap_call_arg` now records whether the swap repairs,
preserves, or breaks name-to-parameter alignment against the known local/imported
callee signature. In this task, the false swap is marked as breaking alignment.
This does not create the preferred `include_path=True` candidate.

Smallest candidate-signal gap if this task is prioritized: extend the existing
`add_keyword_arg` family to synthesize narrow boolean default keywords from the
callee signature, such as adding `include_path=True` when a missing defaulted
boolean parameter gates the observed behavior. That is candidate-generation
work, not a ranker-only fix.

#### `http_no_store_response_with_etag`

This is not a missing-action problem. Every tested candidate passes, including
the preferred local operator repair, but the trained ranker puts an accidental
call-argument swap first.

Trained ranking on the tested rows:

| Trained rank | Original rank | Passed | Preferred | Candidate | Score |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 3 | yes | no | `swap_call_arg` in `should_store_response`, args `0 <-> 1` | 11.606667 |
| 2 | 5 | yes | no | `change_literal`, `"no-store"` -> `"no_store"` | 10.514705 |
| 3 | 1 | yes | yes | `change_operator`, `"no-store" not in cache_control` -> `"no-store" in cache_control` | 9.788554 |
| 4 | 6 | yes | no | `change_literal`, `"no-store"` -> `"max-age=0, no-store"` | 9.749080 |
| 5 | 2 | yes | no | `change_operator`, `"etag" in headers` -> `"etag" not in headers` | 9.242534 |
| 6 | 4 | yes | no | `modify_condition`, negate the no-store condition | 6.317404 |

Why the accidental swap wins:

- The top swap and preferred operator candidate both edit
  `should_store_response` and receive the same exact-symbol and call-graph
  features from the failure hint.
- The swap has no before/after AST delta, so it avoids the current negative
  learned weights on the preferred operator's added/removed `In`/`NotIn` AST
  delta features.
- The preferred operator is helped by overlap metadata and token overlap, but
  not enough to offset the swap's generic action/symbol features and the
  operator-specific negative weights learned from sparse data.
- Existing target context does not describe the call being swapped. The ranker
  cannot tell that the swap changes `headers.get("cache-control", "")` into
  `headers.get("", "cache-control")`, which accidentally makes the no-store
  branch pass by reading the wrong mapping key/default rather than repairing the
  predicate.

Implemented non-leaky metadata/ranker signal: `swap_call_arg` target context
now records mapping `.get` key/default role swaps when detectable, plus
signature-name alignment metadata for local/imported function calls. The feature
version is `candidate-diagnostics-v10`. This is narrower than broad action
weights, does not use pass/preferred labels, and also applies to the cookie
false-swap case.

Avoid treating this task as solved by pass@1 alone. It is a
multiple-passing-candidate case where preferred-positive rank remains the useful
signal.

### Call-Site Role Metadata Follow-Up

Implementation result: v10 call-site argument-role metadata was added for
`swap_call_arg` candidates and consumed by candidate-ranker features from both
live candidates and persisted candidate-outcome rows. Focused tests passed:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py::test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate tests/test_evaluation.py::test_write_candidate_outcomes_preserves_swap_call_role_metadata -q
```

Validation result after refreshing GreenShot-6 outcomes and rerunning the
GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 6/7 | 5/7 | 1.1428571428571428 |

Residuals:

- `http_no_store_response_with_etag` did not improve on preferred-positive
  rank. The preferred `change_operator` repair remains trained rank 3, while
  the non-preferred passing `.get` `swap_call_arg` remains rank 1. The refreshed
  row now carries `swap_call_mapping_get_key_default_swapped`, but current
  non-held-out training signal does not move it below the preferred operator
  repair.
- `cookie_scope_include_path_keyword` still lacks the preferred
  `add_keyword_arg(include_path=True)` candidate in the tested rows. The
  remaining pass@1 miss should be treated first as missing preferred-candidate
  signal, not only as a ranker problem.

Recommended next inspection:

1. Inspect v10 feature support and learned weights for
   `swap_call_mapping_get_key_default_swapped`,
   `swap_call_breaks_name_alignment`, and
   `swap_call_repairs_name_alignment` across the non-held-out GreenShot-5/6
   rows. Do not add broad `swap_call_arg` weights or pass/preferred-label
   features.
2. Decide whether the HTTP residual needs more independent non-held-out
   `.get` key/default role-swap coverage or richer non-leaky predicate/context
   metadata for the preferred operator repair.
3. For `cookie_scope_include_path_keyword`, consider a narrow extension of the
   existing `add_keyword_arg` family to synthesize boolean default keywords from
   local callee signatures, specifically enough to generate
   `include_path=True`, rather than adding a new action family.

### v10 Feature/Weight Inspection

Inspection date: 2026-05-16.

Inspection source:

```bash
runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

The refreshed rows and trained ranker both use
`candidate-diagnostics-v10`. The v10 target-context features are present in the
residual held-out rows, but only the name-alignment features have non-held-out
training coverage.

Non-held-out GreenShot-5/6 coverage:

| Feature | Rows | Passing rows | Preferred rows | Tasks |
| --- | ---: | ---: | ---: | --- |
| `swap_call_mapping_get_key_default_swapped` | 0 | 0 | 0 | none |
| `swap_call_breaks_name_alignment` | 5 | 0 | 0 | `core_metadata_version_dict_value`, `dynamic_field_error_message`, `minimum_python_version_operator_boundary`, `project_urls_header_dict_key`, `readme_missing_file_exception_key` |
| `swap_call_repairs_name_alignment` | 1 | 1 | 1 | `http_cache_key_argument_order` |

Held-out coverage:

| Feature | Rows | Passing rows | Preferred rows | Tasks |
| --- | ---: | ---: | ---: | --- |
| `swap_call_mapping_get_key_default_swapped` | 1 | 1 | 0 | `http_no_store_response_with_etag` |
| `swap_call_breaks_name_alignment` | 1 | 0 | 0 | `cookie_scope_include_path_keyword` |
| `swap_call_repairs_name_alignment` | 1 | 1 | 1 | `cookie_pair_argument_order` |

Learned weights in the GreenShot-6 `split: test` holdout model:

| Feature | Weight |
| --- | ---: |
| `swap_call_mapping_get_key_default_swapped` | 0.0 |
| `action_swap_call_mapping_get_key_default_swapped:swap_call_arg` | 0.0 |
| `swap_call_breaks_name_alignment` | -0.25 |
| `action_swap_call_breaks_name_alignment:swap_call_arg` | -0.25 |
| `swap_call_repairs_name_alignment` | 0.5 |
| `action_swap_call_repairs_name_alignment:swap_call_arg` | 0.5 |

Residual held-out scoring after v10:

| Task | Candidate | Trained rank | Original rank | Passed | Preferred | Score | v10 contribution |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| `http_no_store_response_with_etag` | `.get` `swap_call_arg` key/default swap | 1 | 3 | yes | no | 11.606667 | 0.0 |
| `http_no_store_response_with_etag` | `change_operator`, `not in` -> `in` | 3 | 1 | yes | yes | 9.788554 | 0.0 |
| `cookie_scope_include_path_keyword` | `swap_call_arg` breaking name alignment | 1 | 1 | no | no | 10.106667 | -0.5 |
| `cookie_scope_include_path_keyword` | helper `modify_condition` accidental pass | 2 | 2 | yes | no | 3.050271 | 0.0 |
| `cookie_pair_argument_order` | `swap_call_arg` repairing name alignment | 1 | 1 | yes | yes | 14.606667 | +1.0 |

Decision:

- The HTTP residual is partly a coverage gap: there is no non-held-out row for
  `.get` key/default swaps, so the new
  `swap_call_mapping_get_key_default_swapped` features cannot learn a penalty.
- Independent non-held-out coverage for this exact role-swap shape would be
  useful, especially if paired against a preferred local predicate/operator
  repair. The current held-out HTTP row is a multiple-passing case, so
  preferred-positive rank remains the right validation signal.
- The preferred HTTP operator repair still looks under-described. The
  accidental swap beats it by 1.818113, and the operator row is dragged down by
  negative learned AST/operator-delta weights while receiving only generic
  symbol/locality and overlap help. Even with `.get` role-swap coverage, richer
  non-leaky predicate/context metadata may be needed to identify the local
  branch condition as the intended repair.
- `cookie_scope_include_path_keyword` should not be treated as a ranker-only
  issue. The false swap now receives the expected v10 name-alignment penalty,
  but the preferred `add_keyword_arg(include_path=True)` candidate is still
  absent from the tested rows.

Next handoff:

1. If staying on the HTTP residual, add independent non-held-out coverage for a
   `.get` key/default swap hard negative before changing ranker weights. Keep
   the feature non-leaky and validate on preferred-positive rank, not pass@1
   alone.
2. In parallel or after that, inspect candidate-context metadata for local
   predicate/operator repairs so the preferred `change_operator` row can be
   described by behavior-relevant context instead of only broad AST deltas.
3. If switching to the cookie scope gap, implement the already-planned narrow
   `add_keyword_arg` extension to synthesize boolean default keywords from
   local callee signatures, enough to generate
   `include_path=True`. Do not add a new action family for this.

### Refreshed Test-Slice Residual Inspection

Inspection date: 2026-05-16.

Inspection source:

```bash
runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

After the boolean default keyword candidate-generation refresh,
`cookie_scope_include_path_keyword` is no longer a held-out residual: the
preferred `add_keyword_arg(include_path=True)` candidate is present and trained
rank 1. The remaining GreenShot-6 `split: test` issues are the cookie
same-mapping secure decoy and the HTTP preferred-positive miss.

#### `cookie_default_secure_flag_dict_value`

The preferred candidate still exists at original rank 1 and passes, but the
trained held-out ranker again promotes the false same-mapping key rename above
it.

| Trained rank | Original rank | Passed | Preferred | Candidate | Score |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 4 | no | no | `change_dict_key`, `secure` -> `__Secure-` | 12.363160 |
| 2 | 1 | yes | yes | `change_dict_value`, `secure: True` -> `False` | 11.841018 |

The false key rename wins by `0.522142`. The exact assertion-delta feature is
present on the preferred value edit, but the refreshed training mix gives it
only a small learned contribution:

- Preferred value edit support:
  `same_mapping_asserted_key_value_changed`,
  `same_mapping_asserted_key_value_matches_assertion_delta`,
  and their `change_dict_value` action-specific forms contribute `+1.0`
  combined.
- False key-rename support:
  `same_mapping_asserted_key_renamed_or_removed` is present, but its learned
  weight remains `0.0`; the action-specific form is also `0.0`.
- Broad parameter weights dominate the pair: the false string-key edit gets
  `param_type:from:str` and `param_type:to:str` for `+2.5`, while the preferred
  boolean-value edit gets `param_type:from:bool` and `param_type:to:bool` for
  `-1.5`.
- The preferred value edit is helped by overlap metadata, the asserted-key
  match, and slightly higher failure hint score, but those do not offset the
  `4.0` string-vs-bool parameter gap.

Non-held-out coverage for the exact same-mapping signal is still sparse:

| Feature | Weight | Non-held-out rows | Passing rows | Preferred rows | Tasks |
| --- | ---: | ---: | ---: | ---: | --- |
| `same_mapping_asserted_key_value_matches_assertion_delta` | 0.25 | 2 | 1 | 1 | `http_no_store_directive_subscript_key`, `http_response_policy_max_age_dict_value` |
| `same_mapping_asserted_key_value_changed` | 0.25 | 5 | 1 | 1 | `http_no_store_directive_subscript_key`, `http_response_policy_max_age_dict_value` |
| `same_mapping_asserted_key_renamed_or_removed` | 0.0 | 1 | 0 | 0 | `http_no_store_directive_subscript_key` |

Smallest next signal: add independent non-held-out coverage for the exact
same-mapping boolean value-vs-key-rename shape before changing broad boolean,
string, or action weights. The useful distinction is not another action family:
it is that a candidate preserves the asserted lookup key and changes its value
from assertion actual to expected, while a key rename removes that asserted
lookup key and leaves the original value behavior intact.

#### `http_no_store_response_with_etag`

The current HTTP residual is no longer the `.get` swap as rank 1. All tested
candidates pass, but the trained ranker now promotes string-literal edits above
the preferred operator repair.

| Trained rank | Original rank | Passed | Preferred | Candidate | Score |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 5 | yes | no | `change_literal`, `"no-store"` -> `"no_store"` | 13.111906 |
| 2 | 6 | yes | no | `change_literal`, `"no-store"` -> `"max-age=0, no-store"` | 11.596281 |
| 3 | 3 | yes | no | `.get` `swap_call_arg`, args `0 <-> 1` | 11.125833 |
| 4 | 4 | yes | no | `modify_condition`, negate the no-store condition | 5.525140 |
| 5 | 1 | yes | yes | `change_operator`, `"no-store" not in cache_control` -> `"no-store" in cache_control` | 4.587461 |
| 6 | 2 | yes | no | `change_operator`, `"etag" in headers` -> `"etag" not in headers` | -0.397357 |

The top literal decoy beats the preferred operator by `8.524445`. The gap is
mostly learned feature shape, not missing candidate signal:

- The literal edit gets positive one-node AST-delta count features:
  `ast_delta_added_count:1` and `ast_delta_removed_count:1` contribute `+2.0`
  combined.
- The preferred operator gets the broader two-node delta buckets
  `ast_delta_added_count:2_3` and `ast_delta_removed_count:2_3` for `-1.25`
  combined, plus operator/action-specific overlap and exact-symbol penalties.
- The literal edit also gets stronger action-specific token-overlap support,
  while the preferred operator gets only generic token-overlap and failure hint
  support.
- Both candidates edit the hinted `should_store_response` function. Current
  target context does not describe whether the edit changes the predicate
  operator of the boolean branch or changes the string membership needle and
  thereby disables the branch accidentally.

Smallest next ranker signal: inspect and add non-leaky predicate-context
metadata for membership predicates before changing weights. For this residual,
the useful distinction is between a `change_operator` that flips the membership
predicate governing the boolean assertion and a `change_literal` that changes
the membership literal inside the same predicate. Keep validation on
preferred-positive rank, because pass@1 alone is misleading when every tested
candidate passes.

### Same-Mapping Boolean Coverage Follow-Up

Implementation result: added independent non-held-out coverage for the cookie
same-mapping boolean value-vs-key-rename shape with
`cookie_partitioned_default_dict_value` (`split: train`). The task uses the
existing `change_dict_value` action and creates the same hard-negative shape as
the held-out secure-cookie miss: preserving the asserted lookup key and changing
its boolean value is preferred, while a same-mapping string key rename removes
the asserted lookup key.

Focused verification passed:

```bash
pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q
pytest tests/test_patching.py::test_generate_same_mapping_boolean_value_with_key_rename_decoy -q
```

Validation result after refreshing GreenShot-6 outcomes and rerunning the same
GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 7/7 | 6/7 | 1.0 |

The cookie same-mapping secure residual is fixed in this slice. The remaining
held-out issue is `http_no_store_response_with_etag`: it passes at rank 1, but
still ranks a non-preferred passing repair above the preferred
`change_operator not in -> in` repair. Continue with the membership-predicate
context metadata path and validate preferred-positive rank, not pass@1 alone.

### Membership-Predicate Metadata Follow-Up

Implementation result: v11 membership-predicate target-context metadata was
added for `change_operator` and `change_literal` candidates. The context records
whether the target is an `in`/`not in` membership predicate, whether it appears
in a branch test, the membership operator, operand kinds, operator flips,
literal changes, and whether a changed literal is the membership needle. The
ranker consumes the metadata from both live candidates and persisted outcome
rows.

Validation result after refreshing GreenShot-6 outcomes and rerunning the same
GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 7/7 | 6/7 | 1.0 |

The HTTP preferred-positive rank did not improve. The new metadata is present
on the `http_no_store_response_with_etag` candidates, but the current
non-held-out GreenShot-5/6 coverage gives positive signal to membership literal
edits and negative signal to membership operator flips. The next clean step is
independent non-held-out coverage for the same predicate/operator hard-negative
shape before changing broad action, string, boolean, or pass/preferred-label
weights.

### Independent HTTP Membership Coverage Follow-Up

Implementation result: added independent non-held-out coverage for the HTTP
membership-predicate hard-negative shape with
`http_no_cache_revalidation_with_etag` (`split: train`). The task uses the
existing `change_operator` action for a local
`"no-cache" not in cache_control` branch repair and includes a tempting
`change_literal` candidate changing the membership needle
`"no-cache" -> "no_cache"`, which disables the branch accidentally.

Focused verification passed:

```bash
pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q
pytest tests/test_patching.py::test_generate_membership_operator_with_literal_needle_decoy -q
```

GreenShot-6 outcome refresh:

| Slice | Tasks | Solved | Pass@1 | Avg candidates | Rows | Preferred-positive rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 ranked explore | 21 | 21/21 | 16/21 | 7.24 | 152 | 20 |

Validation result after refreshing GreenShot-6 outcomes and rerunning the same
GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 6/7 | 5/7 | 1.1428571428571428 |

The new training task has the intended raw candidate shape:

| Candidate | Original rank | Passed | Preferred |
| --- | ---: | --- | --- |
| `change_operator`, `"no-cache" not in cache_control` -> `"no-cache" in cache_control` | 1 | yes | yes |
| `change_literal`, `"no-cache" -> "no_cache"` | 5 | yes | no |

The held-out HTTP residual improved but is not fixed:

| Trained rank | Original rank | Passed | Preferred | Candidate |
| ---: | ---: | --- | --- | --- |
| 1 | 5 | yes | no | `change_literal`, `"no-store" -> "no_store"` |
| 2 | 1 | yes | yes | `change_operator`, `"no-store" not in cache_control` -> `"no-store" in cache_control` |

Continue to treat this as preferred-positive ranking signal, not pass@1. The
next clean step is to inspect the refreshed membership feature weights and then
choose a narrow non-leaky signal; do not change broad action, string, boolean,
or pass/preferred-label weights.

### Refreshed Membership Feature Inspection

Inspection date: 2026-05-16.

Inspection source:

```bash
runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

The saved holdout ranker uses `candidate-diagnostics-v11` with 663 learned
features. The held-out HTTP residual is now a narrow preferred-positive miss,
not a pass@1 miss: all tested candidates pass, and the preferred operator
repair is trained rank 2 behind the literal-needle edit.

| Trained rank | Original rank | Passed | Preferred | Candidate | Score | Membership contribution |
| ---: | ---: | --- | --- | --- | ---: | ---: |
| 1 | 5 | yes | no | `change_literal`, `"no-store"` -> `"no_store"` | 15.975122 | +5.50 |
| 2 | 1 | yes | yes | `change_operator`, `"no-store" not in cache_control` -> `"no-store" in cache_control` | 15.824030 | -2.25 |
| 3 | 6 | yes | no | `change_literal`, `"no-store"` -> `"max-age=0, no-store"` | 14.209497 | +5.50 |

The independent `http_no_cache_revalidation_with_etag` training task added the
intended raw candidate shape, but its literal-needle decoy also passes. That
means it supplies preferred-positive ordering signal, not clean failing-negative
signal:

| Candidate | Original rank | Passed | Preferred | Membership contribution |
| --- | ---: | --- | --- | ---: |
| `change_operator`, `"no-cache" not in cache_control` -> `"no-cache" in cache_control` | 1 | yes | yes | -2.25 |
| `change_literal`, `"no-cache"` -> `"no_cache"` | 5 | yes | no | +5.50 |

Non-held-out membership support after the refresh still explains the residual:

| Feature group | Non-held-out rows | Passing rows | Preferred rows | Learned direction |
| --- | ---: | ---: | ---: | --- |
| membership literal changed / needle changed | 2 | 2 | 1 | positive, `+0.50` generic and `+0.50` action-specific |
| membership operator changed / flipped | 5 | 2 | 1 | negative, `-0.50` generic and `-0.50` action-specific |
| `action_membership_predicate_operator:change_operator:not_in` | 2 | 1 | 1 | positive, `+0.50` |
| `action_membership_predicate_operator:change_literal:not_in` | 1 | 1 | 0 | weak negative, `-0.25` |

Feature-delta inspection for the held-out pair shows that the literal decoy's
lead is now small (`0.151092`) but membership features still favor the wrong
candidate by `7.75` points. The preferred operator is kept close by overlap
metadata, higher failure-hint score, and explicit `not in -> in` parameter
features. The current metadata does not distinguish a literal needle edit that
preserves behavior from one that makes the guarded branch unreachable.

Decision: add another independent non-held-out HTTP membership-predicate hard
negative before tuning weights or adding branch-effect metadata. The new task
should keep the existing `change_operator` preferred repair, but its
literal-needle edit should fail, not merely pass as a non-preferred repair.
That gives the current v11 membership features a clean negative example for
the exact tempting literal-needle shape. If that still leaves the held-out
preferred rank below the literal decoy, then add richer branch-effect metadata
to distinguish flipping the membership predicate from changing the membership
needle to make the branch unreachable. Continue validating preferred-positive
rank for `http_no_store_response_with_etag`; pass@1 alone is misleading here.

### Failing Literal-Needle Coverage Follow-Up

Implementation result: added `http_stale_response_without_must_revalidate`
(`split: train`) as independent non-held-out HTTP membership-predicate
coverage. The preferred repair is the existing `change_operator` action for a
local `"must-revalidate" not in cache_control` branch. The tempting
`change_literal` needle edit `"must-revalidate" -> "must_revalidate"` is
generated and fails, giving the v11 membership features a clean failing
literal-needle hard negative.

Focused verification passed:

```bash
pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q
pytest tests/test_patching.py::test_generate_membership_operator_with_failing_literal_needle_decoy -q
```

GreenShot-6 outcome refresh:

| Slice | Tasks | Solved | Pass@1 | Avg candidates | Rows | Preferred-positive rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 ranked explore | 22 | 22/22 | 17/22 | 7.41 | 163 | 21 |

Validation result after refreshing GreenShot-6 outcomes and rerunning the same
GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 7/7 | 7/7 | 1.0 |

The held-out HTTP residual is fixed in this slice. Trained ranking for
`http_no_store_response_with_etag` now puts the preferred operator repair first:

| Trained rank | Original rank | Passed | Preferred | Candidate | Score |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 1 | yes | yes | `change_operator`, `"no-store" not in cache_control` -> `"no-store" in cache_control` | 19.576717 |
| 2 | 5 | yes | no | `change_literal`, `"no-store"` -> `"no_store"` | 11.020788 |
| 3 | 6 | yes | no | `change_literal`, `"no-store"` -> `"max-age=0, no-store"` | 9.255163 |

The new non-held-out training task has the intended failing-decoy shape:

| Candidate | Original rank | Passed | Preferred |
| --- | ---: | --- | --- |
| `change_operator`, `"must-revalidate" not in cache_control` -> `"must-revalidate" in cache_control` | 1 | yes | yes |
| `change_literal`, `"must-revalidate"` -> `"must_revalidate"` | 4 | no | no |

Do not move to branch-effect metadata for this residual unless a fresh
inspection shows the preferred HTTP repair falling behind a literal decoy again.

### Post-Holdout Fresh Inspection

Inspection date: 2026-05-16.

Inspection source:

```bash
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker-metrics.json
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

The refreshed GreenShot-6 `split: test` held-out validation is clean after the
failing literal-needle HTTP coverage:

| Slice | Plans | Solved | Pass@1 | Positive@1 | Avg first passing index |
| --- | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 7/7 | 7/7 | 1.0 |

The raw GreenShot-6 outcome rows still solve all 22 tasks with `pass@1=17/22`
and 21 preferred-positive rows. The remaining raw pass@1 misses are useful
inspection targets, but scoring the rows with the saved test-slice ranker leaves
only one trained preferred-positive gap: `dynamic_field_error_message`.

#### `dynamic_field_error_message`

This is now the clearest next hard negative because it is a git-history-derived
task and exposes an outcome-quality/candidate-signal gap rather than a broad
ranker-weight problem.

Raw ranked order:

| Original rank | Passed | Preferred | Candidate |
| ---: | --- | --- | --- |
| 1 | no | no | `change_operator`, `field in project` -> `field not in project` |
| 2-7 | no | no | `change_literal` decoys around `project.` and the message prefix |
| 8 | yes | no | `change_literal`, `Field "project.` -> full concrete expected message |
| 9 | yes | no | `change_literal`, `" declared as dynamic in but is defined` -> full concrete expected message |

Trained order with the saved `split: test` ranker:

| Trained rank | Original rank | Passed | Preferred | Candidate | Score |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 9 | yes | no | `change_literal`, `" declared as dynamic in but is defined` -> full concrete expected message | 22.064 |
| 2 | 8 | yes | no | `change_literal`, `Field "project.` -> full concrete expected message | 20.022 |

The task manifest has a preferred patch:

```text
change_literal:
  from:  declared as dynamic in but is defined
  to:    declared as dynamic in "project.dynamic" but is defined
```

No tested row matches it. The passing candidates hardcode the observed concrete
message `Field "project.version" declared as dynamic in "project.dynamic" but is
defined`, which satisfies this single test but is weaker than the intended
general f-string fragment repair:

```text
f'Field "project.{field}" declared as dynamic in "project.dynamic" but is defined'
```

Decision: make the next implementation about candidate/outcome quality for
f-string literal-fragment repairs. The narrow goal is to generate and label the
preferred `change_literal` candidate that inserts the missing
`"project.dynamic"` fragment into the existing f-string suffix, instead of only
generating concrete whole-message replacements from the pytest `match=...`
string. Do not tune broad `change_literal`, string-parameter, boolean-parameter,
or pass/preferred-label weights for this.

Useful focused checks after that change:

```bash
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py::test_load_greenshot_6_tasks -q
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

### F-String Fragment Candidate Follow-Up

Implementation result: f-string literal-fragment candidate generation now
emits the preferred reusable `change_literal` repair for
`dynamic_field_error_message`:

```text
from:  declared as dynamic in but is defined
to:    declared as dynamic in "project.dynamic" but is defined
```

This fixes the outcome-quality gap where tested passing candidates only
hardcoded the concrete pytest `match=...` message
`Field "project.version" declared as dynamic in "project.dynamic" but is
defined`.

Focused verification passed:

```bash
pytest tests/test_patching.py::test_generate_fstring_fragment_literal_candidate_from_concrete_message tests/test_evaluation.py::test_load_greenshot_6_tasks -q
pytest tests/test_patching.py -q
```

GreenShot-6 outcome refresh:

| Slice | Tasks | Solved | Pass@1 | Rows | Passing rows | Preferred-positive rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GreenShot-6 ranked explore | 22 | 22/22 | 17/22 | 163 | 47 | 22 |

Validation result after rerunning the same GreenShot-6 `split: test` holdout:

| Slice | Plans | Solved | Pass@1 | Positive@1 |
| --- | ---: | ---: | ---: | ---: |
| GreenShot-6 `split: test` holdout | 7 | 7/7 | 7/7 | 7/7 |

Residual: raw ranking for `dynamic_field_error_message` still puts concrete
whole-message `change_literal` candidates before the preferred reusable
f-string fragment candidate. This is now a raw ranking/hard-negative inspection
target, not a missing preferred-positive row.

Next recommendation: inspect the refreshed GreenShot-6 raw pass@1 misses and
preferred-positive ranks before adding more features or tasks. Keep the clean
`split: test` holdout as a guardrail, and do not tune broad action/string/
boolean weights or add pass/preferred-label features without a fresh
hard-negative finding.

### Refreshed Raw Miss Inspection

Inspection date: 2026-05-17.

Inspection source:

```bash
runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl
runs/apache-python-git/ranker-holdout-greenshot-6-test-slice/candidate-ranker.json
```

The refreshed GreenShot-6 outcome rows still solve all 22 tasks with raw
`pass@1=17/22`, 47 passing rows, and 22 preferred-positive rows. The saved
GreenShot-6 `split: test` held-out ranker remains clean and uses
`candidate-diagnostics-v11`.

Raw pass@1 misses:

| Task | Source | Split | Raw first pass | Raw preferred-positive rank |
| --- | --- | --- | ---: | ---: |
| `apache_license_classifier_dict_value` | `mutation` | `test` | 5 | 5 |
| `dynamic_field_error_message` | `git_history` | `train` | 8 | 10 |
| `http_no_store_directive_subscript_key` | `mutation` | `train` | 19 | 19 |
| `http_range_request_bypasses_cache` | `git_history` | `train` | 2 | 2 |
| `minimum_python_version_operator_boundary` | `mutation` | `validation` | 2 | 2 |

Applying the saved test-slice ranker to the refreshed GreenShot-6 rows puts the
preferred-positive candidate first for all five raw misses:

| Task | Trained preferred-positive rank | Preferred repair |
| --- | ---: | --- |
| `apache_license_classifier_dict_value` | 1 | `change_dict_value`, `Apache-2.0` classifier value |
| `dynamic_field_error_message` | 1 | `change_literal`, reusable f-string suffix fragment |
| `http_no_store_directive_subscript_key` | 1 | `change_subscript_key`, `no-store` -> `no_store` |
| `http_range_request_bypasses_cache` | 1 | `change_literal`, `Content-Range` -> `Range` |
| `minimum_python_version_operator_boundary` | 1 | `change_operator`, `>` -> `>=` |

Decision: this inspection does not expose a narrow candidate-generation,
outcome-quality, or ranker-metadata gap. The raw misses are still useful
evidence that hint-only ordering is weak, but the current trained ranker already
handles them without broad action/string/boolean weight tuning.

Next immediate work should therefore be dataset growth: add the next
real-package-derived GreenShot-6 task or a small new fixture domain from a real
git-history repair, using existing action families where possible. Prefer a
new held-out source shape over another handcrafted ranking feature. After adding
the task/domain, refresh GreenShot-6 outcomes and rerun the same `split: test`
holdout before deciding whether there is a new hard negative.
