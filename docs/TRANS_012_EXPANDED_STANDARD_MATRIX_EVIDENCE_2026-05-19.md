# TRANS-012 Expanded Standard Matrix Evidence

Task: `TRANS-012`

Date: 2026-05-19

## Question

After `TRANS-003` expanded `greenshot_5_subset` from 8 to 12 tasks, does the
full standard transition shadow matrix still preserve the zero-matrix-residual
`TRANS-011` baseline?

Short answer: yes for matrix residuals, no for product routing. The expanded
standard matrix still has 0 matrix residuals and zero hosted usage. Guarded
decision remains `remain_shadow_only` because `greenshot_bugs`, `greenshot_3`,
and `greenshot_4` are still only `ready_for_shadow_mode`.

## Artifacts

- Matrix output: `/tmp/j3-trans-012-expanded-standard`
- Matrix summary:
  `/tmp/j3-trans-012-expanded-standard/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-012-expanded-standard/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-012-expanded-standard-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-012-expanded-standard-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-011 | TRANS-012 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 56 | 60 |
| Ranked solved | 56 | 60 |
| Candidates | 12,413 | 12,753 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 0 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 7 | 8 |
| Hosted usage | 0 | 0 |

The only matrix expansion is `greenshot_5_subset`, which moved from 8 to 12
tasks. It adds 4 ranked-solved tasks and 340 candidates, while preserving 0
matrix residuals, 2 baseline residuals, 3 held-out groups, and
`ready_for_guarded_opt_in`.

## Suite Gates

| Suite | Tasks | Ranked solved | Candidates | Held-out groups | Matrix residuals | Baseline residuals | V3 gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `greenshot_bugs` | 5 | 5 | 185 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_3` | 4 | 4 | 16 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_4` | 27 | 27 | 1,836 | 7 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_5_subset` | 12 | 12 | 1,020 | 3 | 0 | 2 | `ready_for_guarded_opt_in` |
| `greenshot_6_subset` | 12 | 12 | 9,696 | 7 | 0 | 2 | `ready_for_guarded_opt_in` |

## GreenShot-5 Expansion

`TRANS-003` added these tasks to `greenshot_5_subset`:

- `profile_badge_public_api_signature_propagation`
- `return_window_policy_default`
- `receipt_label_nested_module_import_decoy`
- `loyalty_points_wrapper_exception_handler`

The expanded subset preserves the `TRANS-011` GreenShot-5 gate:
`ready_for_guarded_opt_in`. The subset still has 0 matrix residuals and 2
baseline residuals. The residual report now includes one new
shadow-advice-only GreenShot-5 example,
`receipt_label_nested_module_import_decoy`; V3 ranks the passing nested import
candidate first, while the report records a shadow-scorer gap.

## Residual Report

The residual report has 8 examples:

- `scorer_ranking_gap`: 8
- `candidate_generation_gap`: 0

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 8
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
| `greenshot_5_subset` | `receipt_label_nested_module_import_decoy` | `shadow_scorer_top_candidate_failed` | `missing_import` | `scorers_and_production_disagree` |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `shadow_scorer_top_candidate_failed` | `attribute_repair` | `shadow_same_v3_differs` |

Every residual-report example still reports `source_embedding_unavailable` and
`candidate_after_embedding_unavailable`. These are shadow-advice-only scorer
examples, not matrix residuals or suite-gate failures. The new residual work
exposed by the expansion is the GreenShot-5 nested import decoy shadow-scorer
example.

## Decision

Guarded decision remains `remain_shadow_only`; trial scope is `shadow_only`.
The passing checks are matrix schema, suite evidence, held-out groups, zero
hosted usage, and no matrix residuals. The failing check is still
`all_suite_gates_ready_for_guarded_opt_in`.

Product routing remains shadow-only. This run did not change scorer, ranker,
candidate generation, product routing, guarded-trial policy, tests, or the
matrix manifest.
