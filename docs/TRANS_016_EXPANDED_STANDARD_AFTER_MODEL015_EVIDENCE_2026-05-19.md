# TRANS-016 Expanded Standard Evidence After MODEL-015

Task: `TRANS-016`

Date: 2026-05-19

## Question

After `MODEL-015` fixed the visible-balance attribute-repair residual in direct
replay, does the expanded standard transition matrix confirm that
`visible_balance_attribute_decoys` leaves the residual report?

Short answer: no. Matrix totals, suite gates, matrix residuals, baseline
residuals, and guarded decision are unchanged from `TRANS-015`, but the
residual report is not empty. It still contains 1 shadow-advice-only example:
`greenshot_5_subset/visible_balance_attribute_decoys`. Guarded decision remains
`remain_shadow_only` because not all suite gates are
`ready_for_guarded_opt_in`.

## Artifacts

- Matrix output:
  `/tmp/j3-trans-016-expanded-standard-after-model015`
- Matrix summary:
  `/tmp/j3-trans-016-expanded-standard-after-model015/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-016-expanded-standard-after-model015/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-016-expanded-standard-after-model015-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-016-expanded-standard-after-model015-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-015 | TRANS-016 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 60 | 60 |
| Ranked solved | 60 | 60 |
| Candidates | 12,753 | 12,753 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 0 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 1 | 1 |
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
groups are unchanged from `TRANS-015`.

## MODEL-015 Replay Check

`visible_balance_attribute_decoys` is not gone in full replay. The residual
report still includes it as a `shadow_scorer_top_candidate_failed` example.

In the TRANS-016 residual report, V3 selects the passing candidate:

`change_attribute` in `shop/accounts.py::account_balance`,
`amount_cents -> balance_cents`

The shadow-scorer top candidate recorded by the residual report remains the
failing decoy:

`change_attribute` in `shop/accounts.py::account_balance`,
`amount_cents -> available_cents`

The report therefore did not become empty after `MODEL-015`.

## Residual Report

The residual report still has 1 example:

- `scorer_ranking_gap`: 1
- `candidate_generation_gap`: 0

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 1
- `v3_top_candidate_failed`: 0

Residual-report example:

| Suite | Task | Failure kind | Family | Scorer comparison | Passing rank | Shadow top | V3 top |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `shadow_scorer_top_candidate_failed` | `attribute_repair` | `shadow_same_v3_differs` | 2 | `change_attribute amount_cents -> available_cents` | `change_attribute amount_cents -> balance_cents` |

The remaining example still reports `source_embedding_unavailable` and
`candidate_after_embedding_unavailable`. It remains a shadow-advice-only
example, not a matrix residual or suite-gate failure.

## Decision

Guarded decision remains `remain_shadow_only`; trial scope is `shadow_only`.
The passing checks are matrix schema, suite evidence, held-out groups, zero
hosted usage, and no matrix residuals. The failing check remains
`all_suite_gates_ready_for_guarded_opt_in`.

Product routing remains shadow-only. This run did not change scorer logic,
candidate generation, product routing, guarded-trial policy, matrix manifests,
local-knowledge records, materializer code, or `plans/strategy.md`.

## Next Coordinator Decision Point

Do not invent a broader attribute-repair scoring task from this evidence alone.
The exact next decision point is to review why the direct `MODEL-015` replay
top-ranked `balance_cents` while the full TRANS-016 residual report still
records `available_cents` as the shadow-scorer top candidate.

A bounded follow-up should first determine whether this is a matrix/residual
report integration gap, stale advice-feature input in the standard matrix
pipeline, or expected separation between the direct replay path and the full
shadow-scorer report. Only after that should the coordinator decide whether
another implementation slice is needed.
