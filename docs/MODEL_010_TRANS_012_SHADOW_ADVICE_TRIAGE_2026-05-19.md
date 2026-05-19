# MODEL-010 TRANS-012 Shadow-Advice Residual Triage

Task: `MODEL-010`

Date: 2026-05-19

## Scope

This is an evidence-only triage of the advisory `TRANS-012`
`shadow_scorer_top_candidate_failed` examples. It does not change scorer
implementation, ranker behavior, candidate generation, matrix manifests, or
product routing.

Primary artifacts:

- `/tmp/j3-trans-012-expanded-standard-residual-report.json`
- `/tmp/j3-trans-012-expanded-standard/suite/*/shadow-scorer-v3-report.json`
- `/tmp/j3-trans-012-expanded-standard/suite/*/advice-summary.json`
- `/tmp/j3-trans-011-standard-after-model009-residual-report.json`
- `docs/TRANS_012_EXPANDED_STANDARD_MATRIX_EVIDENCE_2026-05-19.md`
- `docs/TRANS_011_STANDARD_AFTER_MODEL009_EVIDENCE_2026-05-19.md`

Generated triage artifacts:

- `/tmp/j3-model-010-trans-012-shadow-advice-triage/residual-examples.json`
- `/tmp/j3-model-010-trans-012-shadow-advice-triage/residual-examples.jsonl`

## Summary

`TRANS-012` has eight residual-report examples. All eight are
`shadow_scorer_top_candidate_failed` / `scorer_ranking_gap` examples. None are
matrix residuals, none are `v3_top_candidate_failed`, and product routing must
remain shadow-only.

Compared with `TRANS-011`, seven examples are carried forward and one is new:
`greenshot_5_subset/receipt_label_nested_module_import_decoy`.

Every example reports the same missing feature labels:
`source_embedding_unavailable` and `candidate_after_embedding_unavailable`.

## Residual Examples

| Suite | Task | Family | Production top candidate | Shadow-scorer top candidate | V3 comparison | Passing ranks | Missing labels | New vs TRANS-011 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `greenshot_bugs` | `last_item` | `unclassified` | rank 1 `replace_expr` on `last_item`, `bugs.py`, `{"replacement": "items[-1]"}`, passed | rank 2 `change_literal` on `last_item`, `bugs.py`, `{"from": 0, "to": -2}`, failed | `v3_same_shadow_differs`; V3 rank 1 `replace_expr`, passed | `[1]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |
| `greenshot_bugs` | `missing_guard` | `unclassified` | rank 1 `insert_guard` on `average`, `bugs.py`, `{"condition": "not values", "return": 0}`, passed | rank 2 `change_operator` on `apply_discount`, `bugs.py`, `{"from": ">", "to": "<"}`, failed | `v3_same_shadow_differs`; V3 rank 1 `insert_guard`, passed | `[1]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |
| `greenshot_4` | `final_score_tail` | `unclassified` | rank 1 `replace_expr` on `final_score`, `bugs.py`, `{"replacement": "scores[-1]"}`, passed | rank 2 `change_literal` on `final_score`, `bugs.py`, `{"from": 0, "to": -2}`, failed | `v3_same_shadow_differs`; V3 rank 1 `replace_expr`, passed | `[1]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |
| `greenshot_4` | `last_order_id_tail` | `unclassified` | rank 1 `replace_expr` on `last_order_id`, `bugs.py`, `{"replacement": "order_ids[-1]"}`, passed | rank 2 `change_literal` on `last_order_id`, `bugs.py`, `{"from": 0, "to": -2}`, failed | `v3_same_shadow_differs`; V3 rank 1 `replace_expr`, passed | `[1]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |
| `greenshot_4` | `newest_event_tail` | `unclassified` | rank 1 `replace_expr` on `newest_event`, `bugs.py`, `{"replacement": "events[-1]"}`, passed | rank 2 `change_literal` on `newest_event`, `bugs.py`, `{"from": 0, "to": -2}`, failed | `v3_same_shadow_differs`; V3 rank 1 `replace_expr`, passed | `[1]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |
| `greenshot_5_subset` | `profile_signature_propagation` | `signature_propagation` | rank 1 `rename_symbol` on `render_profile`, `shop/profiles.py`, `{"from": "username", "scope": "call_site", "to": "name"}`, failed | rank 1 `rename_symbol` on `render_profile`, `shop/profiles.py`, `{"from": "username", "scope": "call_site", "to": "name"}`, failed | `shadow_same_v3_differs`; V3 rank 2 `propagate_signature`, passed | `[2]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |
| `greenshot_5_subset` | `receipt_label_nested_module_import_decoy` | `missing_import` | rank 1 `add_import` on `format_receipt_total`, `shop/reports/summary.py`, `{"import": "from shop.money import format_receipt_total", "module": "shop.money", "name": "format_receipt_total"}`, failed | rank 3 `change_literal` on `format_receipt_total`, `shop/reports/money.py`, `{"from": 100, "to": 98}`, failed | `scorers_and_production_disagree`; V3 rank 2 `add_import` from `shop.reports.money`, passed | `[2]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | yes |
| `greenshot_5_subset` | `visible_balance_attribute_decoys` | `attribute_repair` | rank 1 `change_attribute` on `account_balance`, `shop/accounts.py`, `{"from": "amount_cents", "to": "available_cents"}`, failed | rank 1 `change_attribute` on `account_balance`, `shop/accounts.py`, `{"from": "amount_cents", "to": "available_cents"}`, failed | `shadow_same_v3_differs`; V3 rank 2 `change_attribute` to `balance_cents`, passed | `[2]` | `source_embedding_unavailable`, `candidate_after_embedding_unavailable` | no |

## Clusters

### Tail-Index Literal Decoys

Examples:

- `greenshot_bugs/last_item`
- `greenshot_4/final_score_tail`
- `greenshot_4/last_order_id_tail`
- `greenshot_4/newest_event_tail`

Shape: the passing candidate replaces first-element access with explicit tail
access, such as `items[-1]`, while the advisory scorer prefers a nearby literal
candidate such as `0 -> -2`. V3 and production choose the passing
`replace_expr` candidate at rank 1 in all four cases.

This is the largest coherent cluster and has a narrow local feature: when a
task/test/failure context asks for last, newest, final, or tail behavior, a
candidate-after expression that indexes the same collection with `[-1]` should
outrank nearby negative literal decoys.

### Guard Versus Unrelated Operator Decoy

Example:

- `greenshot_bugs/missing_guard`

Shape: the passing candidate inserts an empty-sequence guard in `average`, but
the advisory scorer prefers an unrelated comparison-operator change in
`apply_discount`. This points to symbol/test alignment and guard-family
features rather than a broad ranking change.

### GreenShot-5 Semantic API Repair Decoys

Examples:

- `greenshot_5_subset/profile_signature_propagation`
- `greenshot_5_subset/visible_balance_attribute_decoys`

Shape: production and the advisory scorer select the same failing local edit,
while V3 promotes the passing semantic API repair at rank 2. These need
signature/attribute evidence from candidate-after behavior or richer local
structural signals before they are safe scorer/advice implementation targets.

### Nested Import Versus Literal Decoy

Example:

- `greenshot_5_subset/receipt_label_nested_module_import_decoy`

Shape: this is the only new `TRANS-012` example relative to `TRANS-011`. V3
selects the passing nested-module import at rank 2, production selects a
top-level import from the wrong module, and the advisory scorer selects a
literal decoy in the nested module. This is important, but as a single new case
it is weaker than the four-example tail-index cluster for the next bounded
implementation slice.

## Recommendation

Recommended next bounded task: `MODEL-011: Add shadow-advice tail-index decoy
scoring evidence`.

Likely write scope:

- `j3/transition_action_scoring.py`
- focused tests in `tests/test_transition_action_scoring.py`
- optional saved-artifact replay or evidence doc under `docs/MODEL_011_*`
- plan updates

Acceptance for that task:

- Add a shadow-advice/V1 scoring feature or prior that promotes passing
  tail-index `replace_expr` candidates over nearby negative literal decoys for
  the four tail-index residuals listed above.
- Re-run a focused saved-artifact replay or equivalent test proving the
  advisory scorer no longer picks the failing literal candidate for
  `last_item`, `final_score_tail`, `last_order_id_tail`, and
  `newest_event_tail`.
- Keep product routing shadow-only. Do not alter matrix manifests, candidate
  generation, ranker routing, or guarded-trial policy.

Focused tests:

- `pytest tests/test_transition_action_scoring.py -q`
- a focused residual/advice replay for the four tail-index examples, if one is
  already available or can be added without broad runner changes
- `pytest tests/test_plan_consistency.py -q`
- `git diff --check`

Blockers: none found in the inspected artifacts. The reports are consistent
with `TRANS-012`: zero matrix residuals, eight advisory-only residual-report
examples, and one new example relative to `TRANS-011`.
