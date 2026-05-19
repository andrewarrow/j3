# TRANS-009 GreenShot-6 After MODEL-008 Evidence

Task: `TRANS-009`

Date: 2026-05-19

## Question

After `MODEL-008` made public pytest `assertion_diff_lines` usable as
mapping-value actual-to-expected evidence, does the targeted
`greenshot_6_subset` still have the
`apache_license_classifier_dict_value` V3 residual or any residual examples?

Short answer: no. The targeted rerun has zero matrix residuals and zero
residual-report examples. The Apache mapping-value candidate is now the scorer
top candidate, passes validation, and improves over the existing rank order.
The suite gate reaches `ready_for_guarded_opt_in`, and the guarded-trial
decision is `guarded_opt_in_trial`.

## Artifacts

- Matrix output: `/tmp/j3-trans-009-greenshot6-after-model008`
- Matrix summary:
  `/tmp/j3-trans-009-greenshot6-after-model008/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-009-greenshot6-after-model008/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-009-greenshot6-after-model008-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-009-greenshot6-after-model008-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-008 | TRANS-009 |
| --- | ---: | ---: |
| Suites | 1 | 1 |
| Tasks | 12 | 12 |
| Ranked solved | 12 | 12 |
| Candidates | 9,696 | 9,696 |
| Held-out groups | 7 | 7 |
| Matrix residuals | 1 | 0 |
| Baseline residuals | 2 | 2 |
| Residual-report examples | 1 | 0 |
| Hosted usage | 0 | 0 |

Suite gate changed from `ready_for_shadow_mode` to
`ready_for_guarded_opt_in`. Guarded-trial decision changed from
`remain_shadow_only` to `guarded_opt_in_trial`.

V3 versus existing rank order for `TRANS-009`:

- `pass_at_1_delta`: `0.285714285714`
- `mean_reciprocal_rank_delta`: `0.185714285714`
- `average_candidates_before_first_pass_delta`: `-0.714285714286`
- `top_k_delta`: `0.142857142857`

## Resolved Residual

`apache_license_classifier_dict_value` is resolved in the targeted rerun.

- Scorer top candidate:
  `change_dict_value Apache-2.0: Apache License -> Apache Software License`
- Existing rank index: 5
- Scorer first known passing position: 1
- Validation: passed
- Comparison: `would_have = improved`

No `apache_license_classifier_dict_value` example appears in the residual
report.

## Residual Report

The residual report has no examples:

- Failure count: 0
- Gap types: none
- Missing-feature labels: none
- Failure kinds: none

The previous `TRANS-008` labels `source_embedding_unavailable` and
`candidate_after_embedding_unavailable` are absent because no residual examples
remain.

## Decision

The targeted subset no longer blocks guarded transition-ranking evidence.
`TRANS-003` can move out of blocked status and become ready for cautious
standard matrix manifest expansion. That follow-up should still be reviewed by
the coordinator before broadening `examples/transition_shadow_matrix.json`.
