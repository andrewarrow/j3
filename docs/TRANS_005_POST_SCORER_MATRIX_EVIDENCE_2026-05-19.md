# TRANS-005 Post-Scorer Transition Matrix Evidence

Task: `TRANS-005`

Date: 2026-05-19

## Question

After `MODEL-003`, `MODEL-004`, and `MODEL-005`, did the focused shadow scorer
residual fixes change the standard transition matrix enough to unblock
`TRANS-003` or guarded transition ranking?

Short answer: no. The standard matrix still fails the guarded-trial gate and
`TRANS-003` should remain blocked. Production transition ranking remains
shadow-only.

## Artifacts

- Matrix output: `/tmp/j3-trans-005-post-scorer-matrix`
- Matrix summary:
  `/tmp/j3-trans-005-post-scorer-matrix/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-005-post-scorer-matrix/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-005-post-scorer-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-005-post-scorer-guarded-decision.json`

## Matrix Totals

| Metric | Count |
| --- | ---: |
| Suites | 5 |
| Tasks | 56 |
| Ranked solved | 55 |
| Candidates | 12,413 |
| Held-out groups | 19 |
| Matrix residuals | 8 |
| Baseline residuals | 5 |
| Hosted usage | 0 |

Compared with `TRANS-001`, task count, candidate count, ranked solved count,
and held-out group count are unchanged. Matrix residuals are worse by one
(`7 -> 8`). The residual report expanded from 14 examples to 17 examples.

## Suite Gates

| Suite | Tasks | Ranked solved | Matrix residuals | Baseline residuals | V3 gate |
| --- | ---: | ---: | ---: | ---: | --- |
| `greenshot_bugs` | 5 | 5 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_3` | 4 | 4 | 1 | 0 | `not_ready_underperforms_existing_rank_order` |
| `greenshot_4` | 27 | 27 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_5_subset` | 8 | 8 | 3 | 2 | `not_ready_underperforms_existing_rank_order` |
| `greenshot_6_subset` | 12 | 11 | 4 | 3 | `not_ready_underperforms_existing_rank_order` |

No suite is eligible for guarded opt-in. The guarded decision is
`remain_shadow_only` because all suite V3 gates must be
`ready_for_guarded_opt_in` and matrix/per-suite residual counts must be zero.

## Residual Report

The residual report has 17 examples:

- `scorer_ranking_gap`: 16
- `candidate_generation_gap`: 1

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 8
- `v3_top_candidate_failed`: 8
- `no_passing_candidate_generated`: 1

Residual task examples:

| Suite | Task | Gap | Family | Notes |
| --- | --- | --- | --- | --- |
| `greenshot_bugs` | `last_item` | `scorer_ranking_gap` | `unclassified` | Shadow scorer preferred a failing literal change over the passing expression replacement. |
| `greenshot_bugs` | `missing_guard` | `scorer_ranking_gap` | `unclassified` | Shadow scorer preferred a failing operator change over the passing guard insertion. |
| `greenshot_3` | `wrap_try_except` | `scorer_ranking_gap` | `unclassified` | V3 preferred a failing import over the passing wrapper. |
| `greenshot_4` | `final_score_tail` | `scorer_ranking_gap` | `unclassified` | Shadow scorer preferred a failing literal change over the passing expression replacement. |
| `greenshot_4` | `last_order_id_tail` | `scorer_ranking_gap` | `unclassified` | Shadow scorer preferred a failing literal change over the passing expression replacement. |
| `greenshot_4` | `newest_event_tail` | `scorer_ranking_gap` | `unclassified` | Shadow scorer preferred a failing literal change over the passing expression replacement. |
| `greenshot_5_subset` | `express_shipping_boundary_preferred_helper` | `scorer_ranking_gap` | `operator_boundary` | V3 still did not put a passing candidate first. |
| `greenshot_5_subset` | `free_shipping_threshold_module_constant` | `scorer_ranking_gap` | `module_constant` | V3 preferred a failing literal change over the passing module constant. |
| `greenshot_5_subset` | `profile_signature_propagation` | `scorer_ranking_gap` | `signature_propagation` | V3 selected the passing propagation candidate, but shadow scorer still preferred a failing rename. |
| `greenshot_5_subset` | `quote_total_helper_discount` | `scorer_ranking_gap` | `expression_helper` | V3 still did not put a passing candidate first. |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `scorer_ranking_gap` | `attribute_repair` | V3 selected the passing attribute candidate, but shadow scorer still preferred a failing attribute decoy. |
| `greenshot_6_subset` | `apache_license_classifier_dict_value` | `scorer_ranking_gap` | `mapping_value` | V3 still did not put a passing candidate first. |
| `greenshot_6_subset` | `dynamic_field_error_message` | `candidate_generation_gap` | `exception_message` | No passing candidate was generated in the matrix run. |
| `greenshot_6_subset` | `http_no_store_directive_subscript_key` | `scorer_ranking_gap` | `http_cache_directive` | The passing `change_subscript_key` candidate exists, but V3 preferred a failing dict-value candidate. |
| `greenshot_6_subset` | `minimum_python_version_operator_boundary` | `scorer_ranking_gap` | `operator_boundary` | V3 still did not put a passing candidate first. |
| `greenshot_6_subset` | `project_urls_header_dict_key` | `scorer_ranking_gap` | `mapping_key` | V3 selected the passing key change, but shadow scorer still preferred a failing key add. |
| `greenshot_6_subset` | `readme_markdown_content_type_dict_value` | `scorer_ranking_gap` | `mapping_value` | Shadow scorer selected the passing value change, but V3 preferred a failing neighboring value change. |

All 17 examples still report missing source/candidate-after evidence:
`source_embedding_unavailable`, `candidate_after_unavailable`, and
`candidate_after_embedding_unavailable`.

## Decision

`TRANS-003` remains blocked. The scorer fixes improved focused fixtures, but
they did not produce a passing standard matrix gate. The next transition work
should address remaining scorer-ranker residuals plus candidate-after/AST-delta
observation before expanding the standard matrix manifest.
