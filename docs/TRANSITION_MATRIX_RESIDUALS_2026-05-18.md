# 2026-05-18 Transition Matrix Residual Diagnosis

Evidence inputs:

- `/tmp/j3-trans-001-shadow-matrix`
- `/tmp/j3-trans-001-residual-report.json`
- `/tmp/j3-trans-001-matrix-evidence`
- `/tmp/j3-trans-001-guarded-decision.json`

The guarded transition ranking gate should remain shadow-only. The matrix
decision was `remain_shadow_only` because not all suite V3 gates reached
`ready_for_guarded_opt_in` and matrix/per-suite residual counts were nonzero.
The run covered 5 suites, 56 tasks, 12,413 candidates, and 19 held-out groups
with zero hosted usage. The matrix had 7 V3 residuals; the residual report
expanded the actionable failure set to 14 examples.

## Gate Blockers

| Suite | Tasks | Candidates | Held-out groups | Baseline residuals | V3 residuals | V3 gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `greenshot_bugs` | 5 | 185 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_3` | 4 | 16 | 1 | 0 | 1 | `not_ready_underperforms_existing_rank_order` |
| `greenshot_4` | 27 | 1,836 | 7 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_5_subset` | 8 | 680 | 3 | 2 | 3 | `not_ready_underperforms_existing_rank_order` |
| `greenshot_6_subset` | 12 | 9,696 | 7 | 2 | 3 | `not_ready_underperforms_existing_rank_order` |

Blocker classification:

- Missing generation: 1 residual. `greenshot_6_subset` task
  `http_no_store_directive_subscript_key` expects a `change_subscript_key`
  candidate from `"no-store"` to `no_store`, but no passing candidate was
  generated.
- Bad ranking: 13 residuals. A passing candidate was generated, but production,
  V3, or shadow scorer order put a failing or unvalidated candidate ahead of
  it. First passing rank distribution was 6 at rank 1, 5 at rank 2, 1 at rank
  5, and 1 at rank 8.
- Weak observation: all 14 residual examples report
  `source_embedding_unavailable`, `candidate_after_unavailable`, and
  `candidate_after_embedding_unavailable`. The scorer is ranking from shallow
  action metadata and failure-hint features without seeing the resulting patch
  or semantic source context.
- Insufficient validation: joins were complete, but scorer-top validation was
  not always known. `greenshot_5_subset` had 4 `unknown` shadow labels and
  `greenshot_6_subset` had 3. Several residuals promote unvalidated
  `add_keyword_arg` candidates, which should not be eligible for guarded
  ranking confidence.

## Residual Clusters

| Cluster | Evidence | Diagnosis | Follow-up |
| --- | --- | --- | --- |
| Single generation gap | `greenshot_6_subset/http_no_store_directive_subscript_key`, family `http_cache_directive`, preferred action `change_subscript_key`; generated candidates only tried dict value/key additions. | Missing generation/action coverage. This is not a scorer issue. | Add a `change_subscript_key` structured action and candidate builder, then rerun the one task and matrix subset. |
| Add-keyword decoy ranking | `greenshot_5_subset` shop helper tasks and `greenshot_6_subset/http_cache_key_argument_order`; shadow often elevated `add_keyword_arg` over known passing `swap_call_arg`, `change_literal`, or module-constant candidates. | Bad ranking plus insufficient validation. The scorer overvalues high model-score pass-through keyword candidates, including unvalidated ones. | Add a residual fixture that penalizes unvalidated `add_keyword_arg` decoys unless the failure hint/test names a missing keyword path. |
| Mapping key/value confusion | `apache_license_classifier_dict_value`, `readme_markdown_content_type_dict_value`, `project_urls_header_dict_key`; passing candidates exist but key/value target selection is wrong or a key-add decoy wins. | Bad ranking with weak observation. The scorer does not distinguish the intended mapping key/value from nearby plausible literals. | Add mapping-target features from key identity, literal equality, failure text, and preferred action family; train/evaluate on mapping key/value held-out groups. |
| Boundary and literal target ranking | `express_shipping_boundary_preferred_helper`, `free_shipping_threshold_module_constant`, `minimum_python_version_operator_boundary`, `dynamic_field_error_message`. | Bad ranking. Correct candidates are in the set, but ranking favors nearby wrong literals/operators or unrelated call swaps. | Add scorer features that prefer preferred action family and symbol/file alignment over generic numeric-neighbor candidates. |
| Identifier/attribute/signature decoys | `profile_signature_propagation`, `visible_balance_attribute_decoys`, plus `wrap_try_except` where V3 preferred `add_import` over the passing exception wrapper. | Bad ranking with weak observation. The scorer cannot tell whether the edit changes the failing behavior or only a nearby name/import. | Add patch-after/AST-delta features and residual tests for signature propagation, attribute decoys, and exception-wrapper intent. |

## Recommended Next Tasks

1. Assign an action-generation task for `change_subscript_key` using
   `http_no_store_directive_subscript_key` as the acceptance fixture. This is
   the only candidate-generation blocker in the 14-failure report.
2. Assign scorer work on the 13 ranking gaps, starting with the repeated
   unvalidated `add_keyword_arg` decoy pattern and mapping key/value target
   features. Acceptance should require the focused residual tasks to improve
   without regressing `greenshot_bugs` or `greenshot_4`.
3. Assign an observation/validation task to materialize candidate-after or
   AST-delta features for shadow outcomes and to prevent unvalidated scorer-top
   candidates from counting as guarded-ranking evidence.

Do not expand the standard matrix manifest yet. `TRANS-003` should wait until
the single generation gap has a local fix and at least the add-keyword/mapping
ranking clusters have residual tests or scorer evidence.
