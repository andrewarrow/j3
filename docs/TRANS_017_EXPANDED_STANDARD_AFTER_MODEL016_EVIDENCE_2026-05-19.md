# TRANS-017 Expanded Standard Evidence After MODEL-016

Task: `TRANS-017`

Date: 2026-05-19

## Question

After `MODEL-016` restored advice-side `PytestFailureHint` parity for
AttributeError `missing_attributes` and traceback locations, does the expanded
standard transition matrix confirm that `visible_balance_attribute_decoys`
leaves the residual report?

Short answer: yes. Matrix totals and suite gates are unchanged from
`TRANS-016`, but the residual report now has 0 examples. The generated
`transition-advice.jsonl` and `transition-shadow-outcomes.jsonl` rows for
`greenshot_5_subset/visible_balance_attribute_decoys` now top-rank the passing
`amount_cents -> balance_cents` candidate. The guarded decision remains
`remain_shadow_only` because not all suite gates are
`ready_for_guarded_opt_in`.

## Artifacts

- Matrix output:
  `/tmp/j3-trans-017-expanded-standard-after-model016`
- Matrix summary:
  `/tmp/j3-trans-017-expanded-standard-after-model016/matrix-summary.json`
- Matrix checksums:
  `/tmp/j3-trans-017-expanded-standard-after-model016/evidence/checksums.sha256`
- Residual report:
  `/tmp/j3-trans-017-expanded-standard-after-model016-residual-report.json`
- Guarded decision:
  `/tmp/j3-trans-017-expanded-standard-after-model016-guarded-decision.json`

## Verification

- `python cli.py run-transition-shadow-matrix --matrix examples/transition_shadow_matrix.json --out /tmp/j3-trans-017-expanded-standard-after-model016 --json`
  passed.
- `shasum -a 256 -c /tmp/j3-trans-017-expanded-standard-after-model016/evidence/checksums.sha256`
  passed.
- `python cli.py report-transition-residuals --matrix /tmp/j3-trans-017-expanded-standard-after-model016 --out /tmp/j3-trans-017-expanded-standard-after-model016-residual-report.json --json`
  passed with 0 residual-report examples.
- `python cli.py decide-transition-guarded-trial --matrix /tmp/j3-trans-017-expanded-standard-after-model016 --out /tmp/j3-trans-017-expanded-standard-after-model016-guarded-decision.json --json`
  passed with `remain_shadow_only`.
- `pytest tests/test_plan_consistency.py -q` passed with 6 tests.
- `git diff --check` passed.

## Matrix Totals

| Metric | TRANS-016 | TRANS-017 |
| --- | ---: | ---: |
| Suites | 5 | 5 |
| Tasks | 60 | 60 |
| Ranked solved | 60 | 60 |
| Candidates | 12,753 | 12,753 |
| Held-out groups | 19 | 19 |
| Matrix residuals | 0 | 0 |
| Baseline residuals | 4 | 4 |
| Residual-report examples | 1 | 0 |
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
groups are unchanged from `TRANS-016`.

## MODEL-016 Replay Check

`visible_balance_attribute_decoys` is gone from the residual report. The report
has no examples and no `scorer_ranking_gap` groups.

The full generated `transition-advice.jsonl` row for
`visible_balance_attribute_decoys` records:

- decision: `shadow_only_not_wired_to_routing`
- existing selected candidate: `change_attribute amount_cents -> balance_cents`
- scorer top candidate: `change_attribute amount_cents -> balance_cents`
- scorer top passed: `true`
- validation comparison: `would_have = improved`

The full advice row contains 85 candidates, so the focused three-candidate
regression order does not appear as the first three global ranks. Filtering the
full scorer order to the three validated attribute candidates still gives
`[2, 1, 3]`: the passing `balance_cents` candidate is ahead of the
`available_cents` and `pending_cents` decoys.

The corresponding `transition-shadow-outcomes.jsonl` row records:

- outcome label: `improved`
- scorer top candidate: `change_attribute amount_cents -> balance_cents`
- scorer top passed: `true`
- scorer first known passing position: `1`
- scorer first known passing rank index: `2`

## Residual Report

The residual report is empty:

- `failure_count`: 0
- `scorer_ranking_gap`: 0
- `candidate_generation_gap`: 0
- examples: 0

Compared with `TRANS-016`, the sole residual-report example
`greenshot_5_subset/visible_balance_attribute_decoys` is resolved. No new
residual-report examples were introduced.

## Decision

Guarded decision remains `remain_shadow_only`; trial scope is `shadow_only`.
The passing checks are matrix schema, suite evidence, held-out groups, zero
hosted usage, and no matrix residuals. The failing check remains
`all_suite_gates_ready_for_guarded_opt_in`.

Product routing remains shadow-only. This run did not change scorer code,
candidate generation, product routing, guarded-trial policy, matrix manifests,
local-knowledge records, materializer code, or `plans/strategy.md`.

## Next Coordinator Decision Point

`MODEL-016` resolved the last residual-report example in the expanded standard
matrix without changing suite gates or the guarded decision. The remaining
guarded-trial blocker is suite coverage: `greenshot_bugs`, `greenshot_3`, and
`greenshot_4` are still only `ready_for_shadow_mode`, while
`greenshot_5_subset` and `greenshot_6_subset` are
`ready_for_guarded_opt_in`.
