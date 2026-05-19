# TRANS-011 Standard Matrix After MODEL-009 Evidence

Task: `TRANS-011`

Date: 2026-05-19

## Question

After `MODEL-009` added V3 local structural evidence for the four saved
`TRANS-010` `v3_top_candidate_failed` cases, is the current full standard
transition shadow matrix clean enough for `TRANS-003` to resume standard
matrix manifest expansion?

Short answer: yes for manifest expansion, no for product opt-in. The full
standard matrix now has zero matrix residuals, so the `TRANS-010` V3 residual
blocker is resolved. The guarded decision remains `remain_shadow_only` because
not all suite gates are `ready_for_guarded_opt_in`. The residual report still
contains 7 shadow-advice-only examples; those are separate from the matrix
residual count and suite gates.

## Artifacts

- Matrix output: `/tmp/j3-trans-011-standard-after-model009`
- Matrix summary:
  `/tmp/j3-trans-011-standard-after-model009/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-011-standard-after-model009/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-011-standard-after-model009-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-011-standard-after-model009-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-010 | TRANS-011 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 56 | 56 |
| Ranked solved | 56 | 56 |
| Candidates | 12,413 | 12,413 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 4 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 11 | 7 |
| Hosted usage | 0 | 0 |

Compared with `TRANS-010`, the `MODEL-009` follow-up reduces matrix residuals
from 4 to 0 and residual-report examples from 11 to 7. The four resolved
`v3_top_candidate_failed` cases were:

- `greenshot_3/wrap_try_except`
- `greenshot_5_subset/express_shipping_boundary_preferred_helper`
- `greenshot_5_subset/free_shipping_threshold_module_constant`
- `greenshot_5_subset/quote_total_helper_discount`

## Suite Gates

| Suite | Tasks | Ranked solved | Candidates | Held-out groups | Matrix residuals | Baseline residuals | V3 gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `greenshot_bugs` | 5 | 5 | 185 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_3` | 4 | 4 | 16 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_4` | 27 | 27 | 1,836 | 7 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_5_subset` | 8 | 8 | 680 | 3 | 0 | 2 | `ready_for_guarded_opt_in` |
| `greenshot_6_subset` | 12 | 12 | 9,696 | 7 | 0 | 2 | `ready_for_guarded_opt_in` |

`greenshot_5_subset` improves from
`not_ready_underperforms_existing_rank_order` to `ready_for_guarded_opt_in`.
`greenshot_3` improves from `not_ready_underperforms_existing_rank_order` to
`ready_for_shadow_mode`. `greenshot_bugs` and `greenshot_4` remain
`ready_for_shadow_mode`; `greenshot_6_subset` remains
`ready_for_guarded_opt_in`.

## Residual Report

The residual report has 7 examples:

- `scorer_ranking_gap`: 7
- `candidate_generation_gap`: 0

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 7
- `v3_top_candidate_failed`: 0

Residual-report examples:

| Suite | Task | Failure kind | Family | Scorer comparison |
| --- | --- | --- | --- | --- |
| `greenshot_bugs` | `last_item` | `shadow_scorer_top_candidate_failed` | `unclassified` | `v3_same_shadow_differs` |
| `greenshot_bugs` | `missing_guard` | `shadow_scorer_top_candidate_failed` | `unclassified` | `v3_same_shadow_differs` |
| `greenshot_4` | `final_score_tail` | `shadow_scorer_top_candidate_failed` | `unclassified` | `v3_same_shadow_differs` |
| `greenshot_4` | `last_order_id_tail` | `shadow_scorer_top_candidate_failed` | `unclassified` | `v3_same_shadow_differs` |
| `greenshot_4` | `newest_event_tail` | `shadow_scorer_top_candidate_failed` | `unclassified` | `v3_same_shadow_differs` |
| `greenshot_5_subset` | `profile_signature_propagation` | `shadow_scorer_top_candidate_failed` | `signature_propagation` | `shadow_same_v3_differs` |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `shadow_scorer_top_candidate_failed` | `attribute_repair` | `shadow_same_v3_differs` |

Every residual-report example still reports `source_embedding_unavailable` and
`candidate_after_embedding_unavailable`. These examples are shadow-advice-only
scorer gaps and should not be counted as matrix residuals or suite-gate
failures.

## Decision

Guarded decision remains `remain_shadow_only`. The passing checks are matrix
schema, suite evidence, held-out groups, zero hosted usage, and no matrix
residuals. The failing check is `all_suite_gates_ready_for_guarded_opt_in`.

`TRANS-003` can resume coordinator-reviewed standard matrix manifest expansion
because the full current standard matrix has zero matrix residuals after
`MODEL-009`. Production transition ranking should remain shadow-only until the
suite-gate policy is satisfied or explicitly narrowed.
