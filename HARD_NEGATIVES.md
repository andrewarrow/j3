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
