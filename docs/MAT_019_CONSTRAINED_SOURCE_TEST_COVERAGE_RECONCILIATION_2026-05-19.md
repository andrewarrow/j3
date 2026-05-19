# MAT-019 Constrained Source/Test Coverage Reconciliation

Task: `MAT-019`

Date: 2026-05-19

## Question

After `MAT-018`, which constrained source/test rows from the MAT-007 held-out
panel are still genuinely uncovered, and what should the next implementation
row be?

Short answer: `MAT-018` correctly closed the original
`general_typed_builder` bucket, but its constrained-source recommendation was
stale. `psf/requests#7427` and `pytest-dev/pytest#14475` were already
materialized and live-validated by `MAT-008` and `MAT-009`. The MAT-007
held-out constrained bucket is now 2 covered rows and 5 remaining rows, while
DATA-029 and DATA-035 remain separate validated reference rows rather than
held-out wins.

## Artifacts

- JSONL rows:
  `docs/MAT_019_CONSTRAINED_SOURCE_TEST_COVERAGE_RECONCILIATION_2026-05-19.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-019-constrained-source-test-coverage/MAT_019_CONSTRAINED_SOURCE_TEST_COVERAGE_RECONCILIATION_2026-05-19.jsonl`

## Coverage Delta

The source panel remains the 24-row MAT-007 held-out refresh. MAT-019 overlays
only the constrained source/test evidence that predates the stale MAT-018 next
recommendation:

- `MAT-008`: `psf/requests#7427`, held-out constrained row, materialized and
  live-validated.
- `MAT-009`: `pytest-dev/pytest#14475`, held-out constrained row,
  materialized and live-validated.
- `DATA-029`: `pytest-dev/pytest#14466`, validated reference row, not counted
  as held-out generalization by MAT-007.
- `DATA-035`: `scrapy/scrapy#7351`, validated reference row for issue 7293,
  not counted as held-out generalization by MAT-007.

| MAT-007 bucket | Original held-out count | Covered by MAT-010..018 | Covered by MAT-008/009 | Remaining held-out count |
| --- | ---: | ---: | ---: | ---: |
| `current_structured_action` | 4 | 0 | 0 | 4 |
| `general_typed_builder` | 7 | 7 | 0 | 0 |
| `repo_convention_builder` | 4 | 0 | 0 | 4 |
| `constrained_local_generator` | 7 | 0 | 2 | 5 |
| `not_currently_expressible` | 2 | 0 | 0 | 2 |

The total remaining non-materialized MAT-007 held-out panel is therefore 15
rows: 4 current-action rows, 4 repo-convention rows, 5 constrained-generator
rows, and 2 not-currently-expressible rows.

## Covered Constrained Held-Out Rows

| Row | Evidence task | Scope | Parity and validation | Interpretation |
| --- | --- | --- | --- | --- |
| `requests-7427` | MAT-008 | `src/requests/utils.py`, `tests/test_utils.py` | Full accepted-diff parity after hunk-label normalization; focused pytest passed. | Held-out constrained source/test win using reusable `replace_function_region` and `insert_pytest_function_after_anchor`. |
| `pytest-14475` | MAT-009 | `src/_pytest/mark/expression.py`, `testing/test_mark_expression.py` | Source/test scoped accepted-diff parity; focused local expression validation passed. Full diff parity is false only because the accepted PR also added a changelog fragment. | Held-out constrained source/test win using the same reusable source-region and pytest insertion action shapes. |

## Reference Rows Kept Separate

DATA-029 and DATA-035 are real validated source/test materialization evidence,
but MAT-007 explicitly recorded them as reference rows outside the 24-row
held-out count. They should remain visible as mechanism-shape evidence without
inflating held-out pass counts.

| Row | Evidence task | MAT-007 role | Interpretation |
| --- | --- | --- | --- |
| `pytest-14466` | DATA-029 | `validated_candidate_reference_not_held_out_count` | Exact accepted pytest source/test diff materialized and validated, but action labels remained pytest-approx specific. |
| `scrapy-7351` | DATA-035 | `validated_candidate_reference_not_held_out_count` | Exact accepted Scrapy source/test diff materialized and validated for issue 7293, but action labels remained Scrapy slot-rotation specific. |

## Remaining Constrained Held-Out Rows

| Row | Repo | MAT-007 reason | Recommendation status |
| --- | --- | --- | --- |
| `click-3434` | `pallets/click` | Small `HelpFormatter.write_usage` source branch plus parameterized output tests. | Still uncovered; useful after one more compact source/test row because it introduces Click formatter output expectations. |
| `click-3420` | `pallets/click` | ANSI-aware wrapping requires synthesized local text-measurement behavior and broad formatter tests. | Still uncovered; larger blast radius, so not the first post-reconciliation row. |
| `click-3364` | `pallets/click` | Default-map splitting needs a bounded semantic branch plus local tests and docs. | Still uncovered; good later row because it includes docs and test placement in addition to source behavior. |
| `requests-7433` | `psf/requests` | Stream-wrapper detection requires a local data-flow predicate and a focused redirect/body regression test. | Recommended next row: compact two-file source/test replay that can reuse MAT-008 Requests setup and generic source-region/test insertion records while testing a new predicate family. |
| `requests-7328` | `psf/requests` | Redirect history mutation ordering depends on aliasing semantics and paired behavior tests. | Still uncovered; compact alternate if `requests-7433` exposes setup or target-selection blockers. |

## Stale MAT-018 Recommendation

The MAT-018 next-workstream section said to start constrained source/test
generation with `psf/requests#7427` and use `pytest-dev/pytest#14475` as the
alternate. That recommendation is now explicitly corrected:

- `requests-7427` is not a next row; it is already covered by `MAT-008`.
- `pytest-14475` is not an alternate next row; it is already covered by
  `MAT-009`.
- The constrained held-out bucket should be reported as 5 remaining rows, not
  7 remaining rows, when MAT-008 and MAT-009 are included.

## Next Row

Recommend `psf/requests#7433` as the next implementation row.

Reason: it is the smallest genuinely uncovered constrained source/test row
that still tests new capability. It keeps the accepted replay to two files,
can reuse the Requests checkout/test conventions already exercised by
MAT-008, and should reuse generic `replace_function_region` plus
`insert_pytest_function_after_anchor` records rather than adding a PR-named
materializer. The new proof is whether a local data-flow predicate for stream
wrapper detection can be synthesized inside a bounded source region and paired
with the accepted regression test.

`requests-7328` is the best compact alternate. The Click rows should remain in
the queue, but `click-3420` and `click-3364` have broader file/test/doc
surfaces, and `click-3434` is a better formatter-family follow-up after one
more small Requests constrained row confirms the source/test mechanism is not
stale.

## Verdict

The constrained source/test materialization panel now has two validated
held-out wins from the original MAT-007 count and five uncovered held-out rows.
DATA-029 and DATA-035 remain separate validated references. The next
coordinator assignment should not duplicate `requests-7427` or
`pytest-14475`; it should target `requests-7433` under the same reusable-action
and focused-validation bar.
