# MAT-036 Current-Action Closure Coverage

Task: `MAT-036`

Date: 2026-05-19

## Question

After `MAT-032` through `MAT-035`, are any original MAT-007 held-out
`current_structured_action` rows still uncovered?

Short answer: no. The four original current-action rows are all materialized
and live-validated. DATA reference rows remain separate and are not counted as
held-out wins.

## Artifacts

- JSONL rows:
  `docs/MAT_036_CURRENT_ACTION_CLOSURE_COVERAGE_2026-05-19.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-036-current-action-closure/MAT_036_CURRENT_ACTION_CLOSURE_COVERAGE_2026-05-19.jsonl`

The source evidence artifacts from the four materialization tasks also parsed
successfully during this closure check:

- `/tmp/j3-mat-032-click-3423-live/final/candidate.json`
- `/tmp/j3-mat-033-flask-6013-live/final/candidate.json`
- `/tmp/j3-mat-034-pytest-14472-live/final/candidate.json`
- `/tmp/j3-mat-035-flask-5898-live/final/candidate.json`

## Closed Current-Action Held-Out Rows

| Row | Evidence | Repo / PR | Candidate status | Changed files | Parity scopes | Validation | Reusable action kinds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `click-3423` | MAT-032 | `pallets/click#3423` | `validated` | `src/click/core.py` | Full accepted diff, source-only, and source/docs/test parity. | Passed focused deprecated option-help rendering validation with checkout-local `PYTHONPATH=src`. | `replace_delimited_region` |
| `flask-6013` | MAT-033 | `pallets/flask#6013` | `validated` | `CHANGES.rst`, `src/flask/sansio/app.py` | Full accepted diff, source-only, and source/docs/test parity. | Passed focused `Flask.select_jinja_autoescape` uppercase suffix validation with checkout-local `PYTHONPATH=src`. | `replace_function_region`, `insert_text_around_anchor` |
| `pytest-14472` | MAT-034 | `pytest-dev/pytest#14472` | `validated` | `AUTHORS`, `changelog/14456.bugfix.rst`, `src/_pytest/python_api.py` | Full accepted diff, source-only, and source/docs/test parity. | Passed focused `_as_numpy_array` `__array_interface__` receiver validation with checkout-local `PYTHONPATH=src`. | `replace_function_region`, `insert_text_around_anchor`, `create_text_file` |
| `flask-5898` | MAT-035 | `pallets/flask#5898` | `validated` | `CHANGES.rst`, `docs/api.rst`, `src/flask/helpers.py`, `src/flask/sansio/app.py` | Full accepted diff, source-only, source/docs/test, and changed-file parity. | Passed focused redirect default validation with checkout-local `PYTHONPATH=src`. | `replace_function_region`, `insert_text_around_anchor`, `replace_text_span` |

None of these action kinds is named after the repository, PR, issue, or task.
They are reusable bounded source-region, delimited-region, text insertion,
text replacement, and text-file creation actions over known target files.

## Reference Rows Kept Separate

DATA rows remain useful evidence for constrained source/test mechanism shape,
but they are not part of the MAT-007 held-out win count.

| Row | Evidence task | Role | Counted as held-out win |
| --- | --- | --- | --- |
| `pytest-14466` | DATA-029 | validated reference row | No |
| `scrapy-7351` | DATA-035 | validated reference row | No |

## Coverage Delta

| MAT-007 bucket | Count before MAT-032 | Covered by MAT-032..035 | Remaining count |
| --- | ---: | ---: | ---: |
| `current_structured_action` | 4 | 4 | 0 |
| `general_typed_builder` | 0 | 0 | 0 |
| `repo_convention_builder` | 0 | 0 | 0 |
| `constrained_local_generator` | 0 | 0 | 0 |
| `not_currently_expressible` | 2 | 0 | 2 |

Remaining non-materialized MAT-007 counts are therefore:

- `current_structured_action = 0`
- `general_typed_builder = 0`
- `repo_convention_builder = 0`
- `constrained_local_generator = 0`
- `not_currently_expressible = 2`

## Remaining Parked Rows

| Bucket | Rows | Count | Status |
| --- | --- | ---: | --- |
| `not_currently_expressible` | `flask-5812`, `flask-5727` | 2 | Parked behind planner capability, not ordinary one-slice materialization rows. |

`flask-5812` remains a broad app/request context architecture merge across
source, docs, and tests. `flask-5727` remains a tooling and lockfile migration
across requirements, CI, configuration, docs, and generated lock state. Neither
has a concrete bounded materializer task comparable to the now-closed
current-action, repo-convention, constrained-source, or typed-builder rows.

## Recommended Next Task

Recommend moving to the separate `TRANS-012` shadow-advice-only residual
workstream, or explicitly recording a migration-planner blocker for
`flask-5812` and `flask-5727`. Do not assign either parked Flask row as an
ordinary one-slice materializer task until the coordinator can name a bounded
planner capability such as multi-step architecture migration planning or
tooling/lockfile migration planning with acceptance criteria independent of a
single PR-shaped replay.

## Verdict

The materializable MAT-007 held-out panel is closed. All 22 materializable
held-out rows are now accounted for across the typed/general-AST,
constrained-source, repo-convention, and current-action closure records. The
only remaining MAT-007 rows are the two deliberately parked
`not_currently_expressible` examples. This is accounting evidence for the
held-out panel, not a new product gate or transition-routing change.
