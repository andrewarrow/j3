# TRANS-015 Expanded Standard Evidence After MODEL-014

Task: `TRANS-015`

Date: 2026-05-19

## Question

After `MODEL-014` fixed the signature-propagation shadow-advice residual in
direct replay, does the expanded standard transition matrix confirm the fix
without changing product-gate behavior?

Short answer: yes. The matrix totals, suite gates, matrix residuals, baseline
residuals, and guarded decision are unchanged from `TRANS-014`. The residual
report narrowed from 2 examples to 1, and `profile_signature_propagation` is
gone in full replay. Guarded decision remains `remain_shadow_only` because not
all suite gates are `ready_for_guarded_opt_in`.

## Artifacts

- Matrix output:
  `/tmp/j3-trans-015-expanded-standard-after-model014`
- Matrix summary:
  `/tmp/j3-trans-015-expanded-standard-after-model014/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-015-expanded-standard-after-model014/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-015-expanded-standard-after-model014-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-015-expanded-standard-after-model014-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-014 | TRANS-015 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 60 | 60 |
| Ranked solved | 60 | 60 |
| Candidates | 12,753 | 12,753 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 0 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 2 | 1 |
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
groups are unchanged from `TRANS-014`.

## MODEL-014 Replay Check

`profile_signature_propagation` no longer appears in the residual report. In
the full TRANS-015 replay, the shadow scorer top candidate is the passing
signature propagation:

`propagate_signature` on `shop/profiles.py::render_profile`, `name -> username`

The shadow outcome for that task is `improved`: the scorer's first known
passing position is 1, while the existing production first passing index is 2.
The previously top-ranked failing call-site `rename_symbol` candidate and the
unrelated `user_badge_label` propagation remain failed candidates.

## Residual Report

The residual report now has 1 example:

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
`candidate_after_embedding_unavailable`. It is a shadow-advice-only example, not
a matrix residual or suite-gate failure.

## Decision

Guarded decision remains `remain_shadow_only`; trial scope is `shadow_only`.
The passing checks are matrix schema, suite evidence, held-out groups, zero
hosted usage, and no matrix residuals. The failing check remains
`all_suite_gates_ready_for_guarded_opt_in`.

Product routing remains shadow-only. This run did not change scorer logic,
candidate generation, product routing, guarded-trial policy, matrix manifests,
local-knowledge records, materializer code, or `plans/strategy.md`.

## Next Bounded Task

Recommended next task: `MODEL-015`, a bounded attribute-repair shadow-advice
scorer slice for `greenshot_5_subset/visible_balance_attribute_decoys`.

The concrete evidence is an `AttributeError` in `shop/accounts.py` on
`amount_cents`, with public test/function context naming `visible_balance`.
The passing candidate changes `amount_cents` to `balance_cents`; the failing
decoys change it to `available_cents` and `pending_cents`. All three share the
same location, action kind, and failure-hint score, so the task should stay
narrow: promote the candidate whose target attribute is supported by local
public API/test-name evidence for the visible balance behavior, and avoid a
broad attribute-repair rule without source or candidate-after semantic evidence.
