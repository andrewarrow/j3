# DATA-007 Issue/PR Replay Blocker Drilldown

Pre-edit replay preflight only; no candidate code edits were attempted.

## Summary

- Rows: `3`
- Status counts: `{"blocked":3}`
- Blocker labels: `{"local_knowledge_required":1,"prompt_spec_ambiguous_or_incomplete":1,"validation_baseline_failed":1}`
- Residual categories: `{"local_knowledge":1,"prompt_spec":1,"validation":1}`
- Runtime seconds: `16.035`
- Command stages reached: `{"baseline_validation":3,"checkout_clone":3,"checkout_ref":3,"checkout_verify":3,"setup":3}`
- First failed stages: `{"baseline_validation":1,"none":2}`
- Deferred agent residual labels: `{"materialization_gap":1,"ranking_gap":3}`
- Failure families: `{"dependency_fixture_setup_failure":1,"local_knowledge_missing":1,"prompt_spec_incomplete":1}`
- Missing prompt fields: `{"acceptance_test_shape":1,"affected_api_symbol":1,"default_map_mutation_timing":1,"expected_behavior":1,"input_shape":1,"minimal_reproduction":1,"multi_value_parameter_shape":1,"observed_behavior":1,"string_splitting_semantics":1}`
- Required knowledge categories: `{"click_empty_string_check_semantics":1,"click_non_string_default_handling":1,"click_parameter_default_handling":1,"click_type_conversion_semantics":1,"focused_validation_recipe":1,"repo_changed_file_context":1,"repo_test_pattern":1,"third_party_semver_version_reproduction":1}`

## Rows

| Replay | Repo | Status | Blockers | Residual | First failed stage | Runtime |
| --- | --- | --- | --- | --- | --- | ---: |
| `psf__requests-issue-7432-pr-7433` | `psf/requests` | `blocked` | `validation_baseline_failed` | `validation` | `baseline_validation` | `11.291` |
| `pallets__click-issue-2745-pr-3364` | `pallets/click` | `blocked` | `prompt_spec_ambiguous_or_incomplete` | `prompt_spec` | `none` | `2.318` |
| `pallets__click-issue-3298-pr-3299` | `pallets/click` | `blocked` | `local_knowledge_required` | `local_knowledge` | `none` | `2.426` |

## Blocker Drilldown

### `psf__requests-issue-7432-pr-7433` - `validation_baseline_failed`

- Family: `dependency_fixture_setup_failure`
- Evidence stage: `baseline_validation`
- Evidence: `E       recursive dependency involving fixture 'httpbin' detected`
- Next: Fix or replace the baseline validation recipe so it is hermetic before candidate generation. Evidence: E       recursive dependency involving fixture 'httpbin' detected
- Next: If the upstream test module depends on external pytest fixtures, install/configure those fixtures or select a focused test subset that does not fail during fixture setup.

### `pallets__click-issue-2745-pr-3364` - `prompt_spec_ambiguous_or_incomplete`

- Family: `prompt_spec_incomplete`
- Missing prompt fields: `["minimal_reproduction","observed_behavior","expected_behavior","affected_api_symbol","input_shape","acceptance_test_shape","default_map_mutation_timing","multi_value_parameter_shape","string_splitting_semantics"]`
- Next: Fetch or read the issue and PR metadata for issue #2745 / PR #3364, then convert the prompt into a structured spec with these missing fields: minimal_reproduction, observed_behavior, expected_behavior, affected_api_symbol, input_shape, acceptance_test_shape, default_map_mutation_timing, multi_value_parameter_shape, string_splitting_semantics.
- Next: Do not generate candidates until the spec names the affected API, reproduction input, expected behavior, and focused acceptance test.

### `pallets__click-issue-3298-pr-3299` - `local_knowledge_required`

- Family: `local_knowledge_missing`
- Required knowledge: `["repo_changed_file_context","repo_test_pattern","focused_validation_recipe","click_parameter_default_handling","click_type_conversion_semantics","click_non_string_default_handling","click_empty_string_check_semantics","third_party_semver_version_reproduction"]`
- Next: Acquire local knowledge records for repo_changed_file_context, repo_test_pattern, focused_validation_recipe, click_parameter_default_handling, click_type_conversion_semantics, click_non_string_default_handling, click_empty_string_check_semantics, third_party_semver_version_reproduction using the replay row's repo-before checkout and changed-file context: src/click/core.py, tests/test_options.py.
- Next: Record provenance and split labels for those knowledge records before candidate generation or ranking uses this row.


## Artifacts

- JSONL: `/private/tmp/j3-data-007-blocker-drilldown/outcomes.jsonl`
