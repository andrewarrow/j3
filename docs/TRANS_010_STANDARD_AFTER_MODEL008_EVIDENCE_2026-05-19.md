# TRANS-010 Standard Matrix After MODEL-008 Evidence

Task: `TRANS-010`

Date: 2026-05-19

## Question

After `MODEL-007`, `MODEL-008`, and the clean `TRANS-009`
`greenshot_6_subset` rerun, is the current full standard transition shadow
matrix clean enough to proceed with `TRANS-003` manifest expansion?

Short answer: no. The full matrix improved substantially from `TRANS-005`, and
`greenshot_6_subset` stays clean, but the full standard gate still returns
`remain_shadow_only`. `TRANS-003` should return to residual work before any
manifest expansion.

## Artifacts

- Matrix output: `/tmp/j3-trans-010-standard-after-model008`
- Matrix summary:
  `/tmp/j3-trans-010-standard-after-model008/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-010-standard-after-model008/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-010-standard-after-model008-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-010-standard-after-model008-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-005 | TRANS-009 | TRANS-010 |
| --- | ---: | ---: | ---: |
| Suites | 5 | 1 | 5 |
| Tasks | 56 | 12 | 56 |
| Ranked solved | 55 | 12 | 56 |
| Candidates | 12,413 | 9,696 | 12,413 |
| Held-out groups | 19 | 7 | 19 |
| Matrix residuals | 8 | 0 | 4 |
| Baseline residuals | 5 | 2 | 4 |
| Residual-report examples | 17 | 0 | 11 |
| Hosted usage | 0 | 0 | 0 |

Compared with `TRANS-005`, ranked solved improves by one, matrix residuals drop
from 8 to 4, baseline residuals drop from 5 to 4, and residual-report examples
drop from 17 to 11. Candidate count and held-out group count are unchanged.

Compared with the targeted `TRANS-009` subset, the full matrix confirms that
`greenshot_6_subset` remains at 0 matrix residuals and
`ready_for_guarded_opt_in`, but other suites still block the full standard
gate.

## Suite Gates

| Suite | Tasks | Ranked solved | Candidates | Held-out groups | Matrix residuals | Baseline residuals | V3 gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `greenshot_bugs` | 5 | 5 | 185 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_3` | 4 | 4 | 16 | 1 | 1 | 0 | `not_ready_underperforms_existing_rank_order` |
| `greenshot_4` | 27 | 27 | 1,836 | 7 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_5_subset` | 8 | 8 | 680 | 3 | 3 | 2 | `not_ready_underperforms_existing_rank_order` |
| `greenshot_6_subset` | 12 | 12 | 9,696 | 7 | 0 | 2 | `ready_for_guarded_opt_in` |

Only `greenshot_6_subset` is eligible for guarded opt-in. The full matrix
decision remains `remain_shadow_only` because not all suite gates are
`ready_for_guarded_opt_in` and matrix residual counts are nonzero.

## Residual Report

The residual report has 11 examples:

- `scorer_ranking_gap`: 11
- `candidate_generation_gap`: 0

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 7
- `v3_top_candidate_failed`: 4

Residual task examples:

| Suite | Task | Failure kind | Family | Notes |
| --- | --- | --- | --- | --- |
| `greenshot_bugs` | `last_item` | `shadow_scorer_top_candidate_failed` | `unclassified` | V3 matches production, but the shadow scorer prefers a failing literal decoy. |
| `greenshot_bugs` | `missing_guard` | `shadow_scorer_top_candidate_failed` | `unclassified` | V3 matches production, but the shadow scorer prefers a failing operator decoy. |
| `greenshot_3` | `wrap_try_except` | `v3_top_candidate_failed` | `unclassified` | V3 prefers a failing import over the passing wrapper. |
| `greenshot_4` | `final_score_tail` | `shadow_scorer_top_candidate_failed` | `unclassified` | V3 matches production, but the shadow scorer prefers a failing literal decoy. |
| `greenshot_4` | `last_order_id_tail` | `shadow_scorer_top_candidate_failed` | `unclassified` | V3 matches production, but the shadow scorer prefers a failing literal decoy. |
| `greenshot_4` | `newest_event_tail` | `shadow_scorer_top_candidate_failed` | `unclassified` | V3 matches production, but the shadow scorer prefers a failing literal decoy. |
| `greenshot_5_subset` | `express_shipping_boundary_preferred_helper` | `v3_top_candidate_failed` | `operator_boundary` | V3 prefers a failing swapped-argument candidate. |
| `greenshot_5_subset` | `free_shipping_threshold_module_constant` | `v3_top_candidate_failed` | `module_constant` | V3 still misses the passing module-constant candidate. |
| `greenshot_5_subset` | `profile_signature_propagation` | `shadow_scorer_top_candidate_failed` | `signature_propagation` | V3 selects the passing propagation candidate, but the shadow scorer prefers a failing rename. |
| `greenshot_5_subset` | `quote_total_helper_discount` | `v3_top_candidate_failed` | `expression_helper` | V3 prefers a failing swapped-argument candidate over the passing helper expression. |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `shadow_scorer_top_candidate_failed` | `attribute_repair` | V3 selects the passing attribute candidate, but the shadow scorer prefers a failing attribute decoy. |

Every residual example reports `source_embedding_unavailable` and
`candidate_after_embedding_unavailable`. `candidate_after_unavailable` is no
longer reported, and no `greenshot_6_subset` residual examples remain.

## Decision

`TRANS-003` should not proceed to manifest expansion yet. The full current
standard matrix still has 4 matrix residuals, 11 residual-report examples, and
a guarded decision of `remain_shadow_only`. The next transition work should
return to residual repair for `greenshot_3` and `greenshot_5_subset`, with the
shadow-scorer advice gaps in `greenshot_bugs` and `greenshot_4` kept visible
for follow-up ranking evidence.
