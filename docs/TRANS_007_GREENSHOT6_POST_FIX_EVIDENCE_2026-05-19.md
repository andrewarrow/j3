# TRANS-007 GreenShot-6 Post-Fix Evidence

Task: `TRANS-007`

Date: 2026-05-19

## Question

After `TRANS-006`, `ACT-003`, and the `ACT-004` dictionary-value rank cleanup,
does the affected `greenshot_6_subset` matrix evidence still show the
`dynamic_field_error_message` generation gap or stale
`candidate_after_unavailable` missing-feature labels?

Short answer: both targeted fixes held, but the subset still fails the
transition gate. `TRANS-003` remains blocked, and a full matrix rerun is not
the next unblocking step from this subset evidence alone.

## Artifacts

- Matrix output: `/tmp/j3-trans-007-greenshot6-post-fix`
- Matrix summary:
  `/tmp/j3-trans-007-greenshot6-post-fix/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-007-greenshot6-post-fix/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-007-greenshot6-post-fix-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-007-greenshot6-post-fix-guarded-decision.json`

## Matrix Totals

| Metric | Count |
| --- | ---: |
| Suites | 1 |
| Tasks | 12 |
| Ranked solved | 12 |
| Candidates | 9,696 |
| Held-out groups | 7 |
| Matrix residuals | 4 |
| Baseline residuals | 2 |
| Hosted usage | 0 |

The suite gate remains `not_ready_underperforms_existing_rank_order`.
Guarded-trial decision: `remain_shadow_only`.

## Residual Report

The residual report has 5 examples. This differs from the matrix residual
count because the residual reporter includes shadow-scorer and V3 top-candidate
failures as separate report examples.

- `scorer_ranking_gap`: 5
- `candidate_generation_gap`: 0
- `v3_top_candidate_failed`: 4
- `shadow_scorer_top_candidate_failed`: 1

Residual task examples:

| Task | Gap | Failure kind | Family |
| --- | --- | --- | --- |
| `apache_license_classifier_dict_value` | `scorer_ranking_gap` | `v3_top_candidate_failed` | `mapping_value` |
| `http_no_store_directive_subscript_key` | `scorer_ranking_gap` | `v3_top_candidate_failed` | `http_cache_directive` |
| `minimum_python_version_operator_boundary` | `scorer_ranking_gap` | `v3_top_candidate_failed` | `operator_boundary` |
| `project_urls_header_dict_key` | `scorer_ranking_gap` | `shadow_scorer_top_candidate_failed` | `mapping_key` |
| `readme_markdown_content_type_dict_value` | `scorer_ranking_gap` | `v3_top_candidate_failed` | `mapping_value` |

`dynamic_field_error_message` is no longer a `candidate_generation_gap`. The
rerun generated and tested the `change_literal` candidate first; rank 1 passed
with the f-string fragment replacement from
` declared as dynamic in but is defined` to
` declared as dynamic in "project.dynamic" but is defined`.

`candidate_after_unavailable` is absent from residual missing-feature
evidence. The remaining missing feature labels are:

- `source_embedding_unavailable`: 5 examples
- `candidate_after_embedding_unavailable`: 5 examples

## Decision

`TRANS-003` remains blocked. The targeted subset now solves all 12 tasks in
the ranked run and no longer has a generation gap, but it still has 4 matrix
residuals, 5 residual-report examples, and a suite gate of
`not_ready_underperforms_existing_rank_order`. The next transition step should
address the remaining scorer-ranking residuals before paying for another full
standard matrix rerun.
