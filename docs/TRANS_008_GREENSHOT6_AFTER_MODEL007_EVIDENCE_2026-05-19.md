# TRANS-008 GreenShot-6 After MODEL-007 Evidence

Task: `TRANS-008`

Date: 2026-05-19

## Question

After `MODEL-007` fixed the deterministic V1/advice ordering for
`project_urls_header_dict_key`, does the targeted `greenshot_6_subset` still
show that mapping-key residual, any V1/advice residuals, or V3 underperformance
against the existing deterministic rank order?

Short answer: the `MODEL-007` target is resolved in the matrix rerun. The
subset improved from 4 matrix residuals and 5 residual-report examples in
`TRANS-007` to 1 matrix residual and 1 residual-report example. V3 no longer
underperforms the existing rank order on aggregate for this subset, but the
guarded-trial decision remains `remain_shadow_only` because the suite is only
`ready_for_shadow_mode`, not `ready_for_guarded_opt_in`, and one residual
remains.

## Artifacts

- Matrix output: `/tmp/j3-trans-008-greenshot6-after-model007`
- Matrix summary:
  `/tmp/j3-trans-008-greenshot6-after-model007/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-008-greenshot6-after-model007/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-008-greenshot6-after-model007-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-008-greenshot6-after-model007-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-007 | TRANS-008 |
| --- | ---: | ---: |
| Suites | 1 | 1 |
| Tasks | 12 | 12 |
| Ranked solved | 12 | 12 |
| Candidates | 9,696 | 9,696 |
| Held-out groups | 7 | 7 |
| Matrix residuals | 4 | 1 |
| Baseline residuals | 2 | 2 |
| Residual-report examples | 5 | 1 |
| Hosted usage | 0 | 0 |

Suite gate changed from `not_ready_underperforms_existing_rank_order` to
`ready_for_shadow_mode`. Guarded-trial decision remains `remain_shadow_only`.

V3 versus existing rank order for `TRANS-008`:

- `pass_at_1_delta`: `0.142857142857`
- `mean_reciprocal_rank_delta`: `0.071428571428`
- `average_candidates_before_first_pass_delta`: `-0.142857142857`
- `top_k_delta`: `0.0`

## Resolved Residual

`project_urls_header_dict_key` is resolved in the targeted rerun.

- Existing selected candidate: `change_dict_key Project_URL -> Project-URL`
- Scorer top candidate: `change_dict_key Project_URL -> Project-URL`
- Rank: 1
- Validation: passed
- Competing decoy: `add_dict_key Project-URL = None`
- Decoy rank: 2
- Decoy validation: failed

The transition advice row reports `would_have = same`, with the scorer first
known passing position at 1. No `project_urls_header_dict_key` example appears
in the residual report.

## Residual Report

The residual report has 1 example:

| Task | Gap | Failure kind | Family |
| --- | --- | --- | --- |
| `apache_license_classifier_dict_value` | `scorer_ranking_gap` | `v3_top_candidate_failed` | `mapping_value` |

V1/advice residuals do not remain in this report. The only failure kind is
`v3_top_candidate_failed`; `shadow_scorer_top_candidate_failed` is absent.

The remaining missing-feature labels are unchanged from `TRANS-007`:

- `source_embedding_unavailable`: 1 example
- `candidate_after_embedding_unavailable`: 1 example

The report still has no `candidate_generation_gap` and no
`candidate_after_unavailable` label.

## Decision

`TRANS-003` remains blocked, but the blocker is narrower than before
`MODEL-007`. The next useful transition task is to review or address the
remaining `apache_license_classifier_dict_value` V3 mapping-value residual,
then decide whether a broader standard matrix rerun is worth the runtime cost.
