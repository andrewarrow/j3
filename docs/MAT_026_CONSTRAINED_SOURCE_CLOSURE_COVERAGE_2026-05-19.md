# MAT-026 Constrained Source Closure Coverage

Task: `MAT-026`

Date: 2026-05-19

## Question

After `MAT-020` through `MAT-025`, are any of the original MAT-007 held-out
`constrained_local_generator` rows still uncovered, and what should the next
bounded materialization workstream be?

Short answer: no. All seven original constrained held-out rows from the
MAT-007/MAT-019 panel are now materialized and live-validated. DATA-029
`pytest-14466` and DATA-035 `scrapy-7351` remain validated reference rows
outside the held-out count. The remaining non-materialized MAT-007 panel is
now 10 rows: 4 `current_structured_action`, 4 `repo_convention_builder`, and
2 `not_currently_expressible`.

## Artifacts

- JSONL rows:
  `docs/MAT_026_CONSTRAINED_SOURCE_CLOSURE_COVERAGE_2026-05-19.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-026-constrained-source-closure/MAT_026_CONSTRAINED_SOURCE_CLOSURE_COVERAGE_2026-05-19.jsonl`

## Coverage Delta

The source panel remains the 24-row MAT-007 held-out refresh. MAT-018 closed
the original 7-row `general_typed_builder` bucket. MAT-019 reconciled the
first two constrained held-out wins, `requests-7427` and `pytest-14475`, and
left five constrained held-out rows. MAT-020 through MAT-025 then closed those
five rows.

| MAT-007 bucket | Original held-out count | Covered by MAT-010..018 | Covered constrained rows | Remaining count |
| --- | ---: | ---: | ---: | ---: |
| `current_structured_action` | 4 | 0 | 0 | 4 |
| `general_typed_builder` | 7 | 7 | 0 | 0 |
| `repo_convention_builder` | 4 | 0 | 0 | 4 |
| `constrained_local_generator` | 7 | 0 | 7 | 0 |
| `not_currently_expressible` | 2 | 0 | 0 | 2 |

The constrained bucket changed as follows:

- MAT-019 starting point: 2 covered, 5 remaining.
- MAT-021 reclassified `requests-7433` as live-validated by corrected
  checkout-local validation evidence after MAT-020's import-path timeout.
- MAT-022 closed `requests-7328`.
- MAT-023 closed `click-3434` with source/test scoped parity; full parity is
  false only because the accepted PR also changes `CHANGES.rst`.
- MAT-024 closed `click-3364` with full source/docs/test parity.
- MAT-025 closed `click-3420` with full source/docs/test parity.

## Closed Constrained Held-Out Rows

| Row | Evidence | Repo | Scope | Parity and validation |
| --- | --- | --- | --- | --- |
| `requests-7427` | MAT-008 | `psf/requests` | `src/requests/utils.py`, `tests/test_utils.py` | Full accepted-diff parity; focused pytest passed. |
| `pytest-14475` | MAT-009 | `pytest-dev/pytest` | `src/_pytest/mark/expression.py`, `testing/test_mark_expression.py` | Source/test scoped parity; focused expression validation passed. Full diff parity excludes the accepted changelog fragment. |
| `requests-7433` | MAT-020/MAT-021 | `psf/requests` | `src/requests/models.py`, `tests/test_requests.py` | Full accepted-diff parity; corrected checkout-local and editable-venv validation passed. |
| `requests-7328` | MAT-022 | `psf/requests` | `src/requests/sessions.py`, `tests/test_requests.py` | Full accepted-diff parity; checkout-local focused pytest passed. |
| `click-3434` | MAT-023 | `pallets/click` | `src/click/formatting.py`, `tests/test_formatting.py` | Source/test scoped parity; focused formatter pytest passed. Full diff parity excludes `CHANGES.rst`. |
| `click-3364` | MAT-024 | `pallets/click` | `CHANGES.rst`, `docs/commands.md`, `docs/conf.py`, `src/click/core.py`, `tests/test_defaults.py` | Full, source/test, and source/docs/test parity; focused pytest passed. |
| `click-3420` | MAT-025 | `pallets/click` | `CHANGES.rst`, `src/click/_textwrap.py`, `src/click/formatting.py`, `tests/test_formatting.py` | Full, source/test, and source/docs/test parity; focused pytest passed. |

## Reference Rows Kept Separate

DATA-029 and DATA-035 remain useful mechanism-shape evidence, but MAT-007
explicitly excluded them from the 24 held-out rows.

| Row | Evidence task | MAT-007 role | Counted as held-out win |
| --- | --- | --- | --- |
| `pytest-14466` | DATA-029 | validated reference row | No |
| `scrapy-7351` | DATA-035 | validated reference row | No |

## Remaining MAT-007 Panel

The remaining non-materialized rows are:

| Bucket | Rows | Count |
| --- | --- | ---: |
| `current_structured_action` | `click-3423`, `flask-6013`, `flask-5898`, `pytest-14472` | 4 |
| `repo_convention_builder` | `click-3405`, `requests-7423`, `requests-7315`, `pytest-14429` | 4 |
| `not_currently_expressible` | `flask-5812`, `flask-5727` | 2 |

The `current_structured_action` rows are still worth replaying, but they are
not the next missing capability layer. They mainly verify target selection and
small existing expression/default-value edits. The two
`not_currently_expressible` rows should stay parked until the project has a
multi-step migration planner.

## Next Workstream

Recommend moving to the `repo_convention_builder` bucket, starting with
`psf/requests#7423` as `MAT-027`.

Evidence:

- It is the smallest remaining convention-dependent row in the MAT-007 panel:
  `+9/-0`, one accepted file, `tests/conftest.py`.
- Its difficulty is the right kind of new capability: selecting and inserting
  an autouse pytest fixture in local Requests test conventions, not synthesizing
  a new source predicate.
- It can reuse Requests checkout and validation lessons from MAT-008,
  MAT-021, MAT-022, and MAT-020 while shifting the proof from source-region
  generation to repo-local pytest convention handling.
- The other repo-convention rows are broader: `click-3405` spans pager
  monkeypatch/skip/stream conventions, `requests-7315` combines a small source
  deletion with adapter expectation updates, and `pytest-14429` depends on
  pytest parser fixture conventions.

If the coordinator wants a low-risk sanity check before a new convention layer,
`click-3423` is the smallest remaining current-action row. It should not
displace `requests-7423` as the next capability-building row because the
repo-convention bucket is now the main remaining bounded materialization gap.

## Verdict

The constrained source/test bucket is closed for the original MAT-007 held-out
panel: 7 of 7 rows are materialized and live-validated, while the two DATA
reference rows remain outside the count. This does not justify a broad product
gate; it narrows the next evidence question. The next bounded proof should be
whether j3 can materialize repo-local pytest convention edits without adding a
row-specific materializer, starting with `requests-7423`.
