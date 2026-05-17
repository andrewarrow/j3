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
