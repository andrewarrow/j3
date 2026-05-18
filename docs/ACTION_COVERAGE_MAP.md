# Action Coverage Map

Date: 2026-05-18

Inputs:

- `docs/TRANSITION_MATRIX_RESIDUALS_2026-05-18.md`
- `plans/progress.md` entries for `TRANS-001`, `TRANS-002`, `ACT-002`,
  `TRANS-004`, and `GS7-002`
- GreenShot-7 classified fixtures in `examples/greenshot_7/tasks.json`
- Structured action definitions in `j3/actions.py`, `j3/greenfield.py`, and
  `j3/existing_repo_change.py`

## Supported Action Surfaces

| Surface | Current structured actions | Evidence status |
| --- | --- | --- |
| Repair patches | `replace_expr`, `insert_guard`, `change_literal`, `change_operator`, `change_subscript_key`, `change_dict_key`, `change_dict_value`, `add_dict_key`, `swap_call_arg`, `add_keyword_arg`, `add_import`, `add_import_fallback`, `change_attribute`, `change_module_constant`, `wrap_try_except`, `add_fallback_warning`, `change_return_value`, `rename_symbol`, `modify_condition`, `propagate_signature` | The 2026-05-18 matrix produced candidates for all current residual clusters after `ACT-002`; remaining transition failures are ranking/scorer gaps, not missing repair action kinds. |
| Greenfield creation | `create_file`, `add_import`, `add_function_def`, `add_operator_dispatch`, `add_cli_entrypoint`, `create_test_file`, `add_cli_behavior_tests`, `add_library_behavior_tests`, `add_parser_behavior_tests`, `ask_clarification` | GreenShot-7 now builds calculator CLIs, a slugify library, and a key/value parser. Ambiguous requests are represented as blocked clarification plans. |
| Existing-repo change | `inspect_repo`, `parse_existing_calculator`, `add_operator_aliases`, `add_operator_dispatch`, `add_cli_behavior_tests`, `validate` | Existing-repo support is deliberately narrow and calculator-specific. Non-calculator existing-repo requests are classified rather than edited. |

## Residual-To-Action Map

| Evidence | Examples | Classification | Action coverage decision | Recommended slice |
| --- | --- | --- | --- | --- |
| Transition candidate-generation gap from `TRANS-002` | `greenshot_6_subset/http_no_store_directive_subscript_key`, preferred `change_subscript_key` from `"no-store"` to `"no_store"` | Missing generation for an existing repair action family | Fixed by `ACT-002`. `TRANS-004` confirms zero `candidate_generation_gap` examples in the targeted `greenshot_6_subset` residual report; both production and shadow select the passing `change_subscript_key` candidate at rank 1. | No new action slice needed. Keep this task as a regression fixture for future candidate-cap and ranking changes. |
| Transition add-keyword decoy ranking | `greenshot_5_subset` shop helper tasks, `greenshot_6_subset/http_cache_key_argument_order`, and related `add_keyword_arg` decoys | Scorer/ranking gap plus insufficient validation confidence | Do not add a new action kind. `add_keyword_arg`, `swap_call_arg`, `change_literal`, and module-constant actions already exist; the issue is false priority for unvalidated or weakly supported candidates. | `MODEL-002A`: add residual fixtures/features that penalize unvalidated `add_keyword_arg` candidates unless failure hints identify a missing keyword path. |
| Transition mapping key/value confusion | `apache_license_classifier_dict_value`, `readme_markdown_content_type_dict_value`, `project_urls_header_dict_key`, plus historical cookie mapping hard negatives | Scorer/ranking gap with weak target observation | Do not add a new action kind. `change_dict_key`, `change_dict_value`, `add_dict_key`, and `change_subscript_key` exist; the scorer needs key identity, asserted key/value, and target-context signals. | `MODEL-002B`: add mapping-target features and held-out residual tests that distinguish key mutation from value mutation in the same mapping. |
| Transition boundary and literal ranking | `express_shipping_boundary_preferred_helper`, `free_shipping_threshold_module_constant`, `minimum_python_version_operator_boundary`, `dynamic_field_error_message` | Scorer/ranking gap | Do not add a new action kind. Existing `change_operator`, `change_literal`, `change_module_constant`, and `change_return_value` actions cover the edit surface. | `MODEL-002C`: add scorer features for preferred action family, symbol/file alignment, and equivalent/overlapping candidate metadata. |
| Transition identifier, attribute, signature, and wrapper decoys | `profile_signature_propagation`, `visible_balance_attribute_decoys`, `wrap_try_except` where an import or nearby symbol edit outranks the passing behavior change | Scorer/ranking gap with weak observation | Do not add a new action kind. `rename_symbol`, `change_attribute`, `propagate_signature`, `wrap_try_except`, and import actions exist. | `MODEL-002D`: materialize candidate-after or AST-delta features so ranking can see whether a candidate changes the failing behavior. |
| GreenShot-7 tests-only existing-repo request | `slugify_tests_only_existing` classified as `action_coverage` | Missing GreenShot request-to-repo action surface | Add a structured existing-repo tests-only planning path. This is not a repair-patch action; it needs repo inspection, behavior discovery, test-file creation, and validation actions for an existing project. | `GS7-005`: implement `add_existing_repo_tests` slice for one-file libraries, backed by a fixture repo and hidden-like pytest command. |
| GreenShot-7 non-calculator existing-repo convention request | `slugify_existing_src_convention` classified as `existing_repo_support` | Existing-repo support gap | Extend repo-state-aware existing-repo planning before adding broad edit actions. The current existing-repo action set only handles calculator power support and cannot safely infer `src/` package exports. | `REPO-002` then `GS7-006`: use repo-state coverage to plan `src` package export edits for a small library fixture. |
| GreenShot-7 ambiguous creation requests | `math_tool_unclear`, `calculator_scientific_unclear`, `file_converter_unclear` classified as `expected_clarification` | Prompt/spec outcome gap, not missing edit action coverage | Keep as clarification. `ask_clarification` exists in greenfield planning, but `GS7-004` should make clarification a first-class public outcome rather than a blocked build record. | `GS7-004`: emit a structured clarification response with questions and no filesystem writes. |

## New-Action Needs

1. `add_existing_repo_tests`: a request-to-repo action family for adding tests to
   an existing Python module without changing implementation. The smallest
   fixture should inspect `slugify.py`, create `tests/test_slugify.py`, and run
   pytest. This directly covers `slugify_tests_only_existing`.
2. Existing-repo library convention actions, after repo-state support is
   explicit: inspect package layout, add or update module exports, add behavior
   tests, and validate. This covers `slugify_existing_src_convention`, but
   should wait for `REPO-001`/a follow-up repo-state report because the current
   existing-repo path is calculator-specific.

No additional repair-patch action kind is currently justified by the
2026-05-18 transition residuals. The only repair generation gap found by
`TRANS-002` was resolved by `ACT-002`.

## Ranking And Observation Gaps

The transition matrix should stay shadow-only for ranking reasons:

- `TRANS-001`: 56 tasks, 55 ranked solved, 7 matrix residuals, 14 residual
  report failures, and a guarded decision of `remain_shadow_only`.
- `TRANS-002`: the 14 residual-report failures split into 1 candidate-generation
  gap and 13 scorer-ranking gaps.
- `TRANS-004`: after the `change_subscript_key` fix, the targeted
  `greenshot_6_subset` residual report has zero candidate-generation gaps and 8
  scorer-ranking gaps.

The next ranking work should prioritize:

1. unvalidated `add_keyword_arg` decoys
2. mapping key/value target confusion
3. boundary/literal action-family and file/symbol alignment
4. candidate-after or AST-delta observation for identifier, attribute,
   signature, and wrapper decoys

## Prompt/Spec And Existing-Repo Gaps

GreenShot-7 gaps should not be folded into repair-action expansion:

- `expected_clarification` examples need a first-class clarification outcome.
- `existing_repo_support` examples need repo-state-aware planning and package
  convention support.
- `action_coverage` on `slugify_tests_only_existing` needs a tests-only
  existing-repo action surface.

Keeping these categories separate prevents ranking work from being blamed for
unsupported request-to-repo capabilities, and prevents broad new actions from
being added when residual evidence only asks for better scorer features.
