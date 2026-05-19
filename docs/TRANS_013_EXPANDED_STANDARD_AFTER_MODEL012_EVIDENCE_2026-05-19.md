# TRANS-013 Expanded Standard Evidence After MODEL-012

Task: `TRANS-013`

Date: 2026-05-19

## Question

After `MODEL-011` and `MODEL-012` fixed five saved shadow-advice residual
examples, does the full expanded standard transition matrix confirm those
fixes without changing product-gate behavior?

Short answer: yes. The expanded standard matrix still has 0 matrix residuals,
4 baseline residuals, and zero hosted usage. The residual report narrowed from
8 shadow-advice examples to 3, and all five targeted examples are gone in full
replay. Guarded decision remains `remain_shadow_only` because not all suite
gates are `ready_for_guarded_opt_in`.

## Artifacts

- Matrix output:
  `/tmp/j3-trans-013-expanded-standard-after-model012`
- Matrix summary:
  `/tmp/j3-trans-013-expanded-standard-after-model012/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-013-expanded-standard-after-model012/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-013-expanded-standard-after-model012-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-013-expanded-standard-after-model012-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-012 | TRANS-013 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 60 | 60 |
| Ranked solved | 60 | 60 |
| Candidates | 12,753 | 12,753 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 0 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 8 | 3 |
| Hosted usage | 0 | 0 |

## Suite Gates

| Suite | Tasks | Ranked solved | Candidates | Held-out groups | Matrix residuals | Baseline residuals | V3 gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `greenshot_bugs` | 5 | 5 | 185 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_3` | 4 | 4 | 16 | 1 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_4` | 27 | 27 | 1,836 | 7 | 0 | 0 | `ready_for_shadow_mode` |
| `greenshot_5_subset` | 12 | 12 | 1,020 | 3 | 0 | 2 | `ready_for_guarded_opt_in` |
| `greenshot_6_subset` | 12 | 12 | 9,696 | 7 | 0 | 2 | `ready_for_guarded_opt_in` |

Suite gates, matrix residuals, baseline residuals, candidates, and held-out
groups are unchanged from `TRANS-012`.

## Targeted Residual Fixes

These `TRANS-012` shadow-advice examples no longer appear in the `TRANS-013`
residual report:

| Suite | Task | TRANS-012 issue | TRANS-013 result |
| --- | --- | --- | --- |
| `greenshot_bugs` | `last_item` | shadow scorer preferred failing `change_literal`; V3 selected passing tail `replace_expr` | gone |
| `greenshot_4` | `final_score_tail` | shadow scorer preferred failing `change_literal`; V3 selected passing tail `replace_expr` | gone |
| `greenshot_4` | `last_order_id_tail` | shadow scorer preferred failing `change_literal`; V3 selected passing tail `replace_expr` | gone |
| `greenshot_4` | `newest_event_tail` | shadow scorer preferred failing `change_literal`; V3 selected passing tail `replace_expr` | gone |
| `greenshot_bugs` | `missing_guard` | shadow scorer preferred failing `change_operator`; V3 selected passing `insert_guard` | gone |

The four tail-index residuals fixed by `MODEL-011` and the `missing_guard`
residual fixed by `MODEL-012` are resolved in full replay, not just direct
saved-artifact replay.

## Residual Report

The residual report now has 3 examples:

- `scorer_ranking_gap`: 3
- `candidate_generation_gap`: 0

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 3
- `v3_top_candidate_failed`: 0

Residual-report examples:

| Suite | Task | Failure kind | Family | Scorer comparison | Passing rank | Shadow top | V3 top |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| `greenshot_5_subset` | `profile_signature_propagation` | `shadow_scorer_top_candidate_failed` | `signature_propagation` | `shadow_same_v3_differs` | 2 | `rename_symbol` | `propagate_signature` |
| `greenshot_5_subset` | `receipt_label_nested_module_import_decoy` | `shadow_scorer_top_candidate_failed` | `missing_import` | `scorers_and_production_disagree` | 2 | `change_literal` | `add_import` |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `shadow_scorer_top_candidate_failed` | `attribute_repair` | `shadow_same_v3_differs` | 2 | `change_attribute` | `change_attribute` |

All three remaining examples still report `source_embedding_unavailable` and
`candidate_after_embedding_unavailable`. They are shadow-advice-only examples,
not matrix residuals or suite-gate failures.

## Decision

Guarded decision remains `remain_shadow_only`; trial scope is `shadow_only`.
The passing checks are matrix schema, suite evidence, held-out groups, zero
hosted usage, and no matrix residuals. The failing check remains
`all_suite_gates_ready_for_guarded_opt_in`.

Product routing remains shadow-only. This run did not change scorer logic,
candidate generation, product routing, guarded-trial policy, matrix manifests,
local-knowledge records, materializer code, or `plans/strategy.md`.

## Next Bounded Task

The remaining GreenShot-5 advisory examples do not share one precise scorer
shape. The next bounded scorer/advice task should start with the most concrete
candidate-after/source-tree signal:

`MODEL-013`: add narrow shadow-advice evidence for nested-package missing
imports, using `receipt_label_nested_module_import_decoy` as the replay case.
It should promote the passing `add_import` candidate whose module path points
to the existing nested package file over non-import literal decoys and wrong
top-level package imports, with focused scorer tests and saved-artifact replay.

The signature-propagation and attribute-repair examples should stay separate
unless `MODEL-013` exposes shared candidate-after semantic evidence. Without
candidate-after/source semantic evidence, a single broad GreenShot-5 API
scorer tweak would be under-specified.
