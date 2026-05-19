# TRANS-014 Expanded Standard Evidence After MODEL-013

Task: `TRANS-014`

Date: 2026-05-19

## Question

After `MODEL-013` fixed the nested-package missing-import shadow-advice
residual in direct replay, does the expanded standard transition matrix confirm
the fix without changing product-gate behavior?

Short answer: yes. The matrix totals, suite gates, matrix residuals, baseline
residuals, and guarded decision are unchanged from `TRANS-013`. The residual
report narrowed from 3 examples to 2, and
`receipt_label_nested_module_import_decoy` is gone in full replay. Guarded
decision remains `remain_shadow_only` because not all suite gates are
`ready_for_guarded_opt_in`.

## Artifacts

- Matrix output:
  `/tmp/j3-trans-014-expanded-standard-after-model013`
- Matrix summary:
  `/tmp/j3-trans-014-expanded-standard-after-model013/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-014-expanded-standard-after-model013/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-014-expanded-standard-after-model013-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-014-expanded-standard-after-model013-guarded-decision.json`

## Matrix Totals

| Metric | TRANS-013 | TRANS-014 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 60 | 60 |
| Ranked solved | 60 | 60 |
| Candidates | 12,753 | 12,753 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 0 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 3 | 2 |
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
groups are unchanged from `TRANS-013`.

## MODEL-013 Replay Check

`receipt_label_nested_module_import_decoy` no longer appears in the residual
report. In the full TRANS-014 replay, the shadow scorer top candidate is the
passing nested import:

`from shop.reports.money import format_receipt_total`

The wrong top-level `shop.money` import remains a failed candidate, and the
nearby `100 -> 98` literal edit remains a failed candidate. The task is
therefore resolved in full expanded-standard replay, not only in the direct
saved-artifact replay from `MODEL-013`.

## Residual Report

The residual report now has 2 examples:

- `scorer_ranking_gap`: 2
- `candidate_generation_gap`: 0

Failure kinds:

- `shadow_scorer_top_candidate_failed`: 2
- `v3_top_candidate_failed`: 0

Residual-report examples:

| Suite | Task | Failure kind | Family | Scorer comparison | Passing rank | Shadow top | V3 top |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| `greenshot_5_subset` | `profile_signature_propagation` | `shadow_scorer_top_candidate_failed` | `signature_propagation` | `shadow_same_v3_differs` | 2 | `rename_symbol` | `propagate_signature` |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `shadow_scorer_top_candidate_failed` | `attribute_repair` | `shadow_same_v3_differs` | 2 | `change_attribute` | `change_attribute` |

Both remaining examples still report `source_embedding_unavailable` and
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

The remaining examples should stay separate unless a later scorer task exposes
shared source or candidate-after semantic evidence.

Recommended next task: `MODEL-014`, a bounded signature-propagation
shadow-advice scorer slice for
`greenshot_5_subset/profile_signature_propagation`. The concrete evidence is a
`TypeError` with `type_error_names: ["username"]`; the passing candidate is
`propagate_signature` on `shop/profiles.py::render_profile` from `name` to
`username`, while the failing shadow top candidate rewrites one call keyword
from `username` to `name`. The task should promote only symbol-aligned
`propagate_signature` candidates when the new parameter matches the TypeError
name and failure context names the same source file or function, while guarding
against unrelated signature propagation such as `user_badge_label`.

Keep `visible_balance_attribute_decoys` as a separate follow-up. Its candidates
are three same-location `change_attribute` edits with identical failure-hint
scores, and the useful signal is the expected public attribute name
`balance_cents` versus decoys `available_cents` and `pending_cents`.
