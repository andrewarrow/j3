# MAT-031 Repo-Convention Closure Coverage

Task: `MAT-031`

Date: 2026-05-19

## Question

After `MAT-027` through `MAT-030`, are any original MAT-007 held-out
`repo_convention_builder` rows still uncovered?

Short answer: no. The four original repo-convention rows are all
materialized and live-validated. DATA reference rows remain separate and are
not counted as held-out wins.

## Artifacts

- JSONL rows:
  `docs/MAT_031_REPO_CONVENTION_CLOSURE_COVERAGE_2026-05-19.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-031-repo-convention-closure/MAT_031_REPO_CONVENTION_CLOSURE_COVERAGE_2026-05-19.jsonl`

The source evidence artifacts from the four materialization tasks also parsed
successfully during this closure check:

- `/tmp/j3-mat-027-requests-7423/final/candidate.json`
- `/tmp/j3-mat-028-requests-7315/final/candidate.json`
- `/tmp/j3-mat-029-pytest-14429/final/candidate.json`
- `/tmp/j3-mat-030-click-3405-live/final/candidate.json`

## Closed Repo-Convention Held-Out Rows

| Row | Evidence | Repo / PR | Candidate status | Changed files | Parity scopes | Validation | Reusable action kinds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `requests-7423` | MAT-027 | `psf/requests#7423` | `validated` | `tests/conftest.py` | Full accepted diff and repo-convention parity. | Passed focused pytest with polluted proxy environment and checkout-local `PYTHONPATH=src`. | `insert_pytest_fixture_after_anchor` |
| `requests-7315` | MAT-028 | `psf/requests#7315` | `validated` | `src/requests/adapters.py`, `tests/test_adapters.py` | Full accepted diff and repo-convention parity. | Passed focused adapter pytest with checkout-local `PYTHONPATH=src`. | `delete_exact_source_lines_after_anchor`, `rename_pytest_function`, `replace_pytest_assertion_expected_literal` |
| `pytest-14429` | MAT-029 | `pytest-dev/pytest#14429` | `validated` | `src/_pytest/config/argparsing.py`, `testing/test_parseopt.py` | Repo-convention and source/test scoped parity. Full accepted-diff parity is false only because the accepted PR also adds `changelog/13817.bugfix.rst`. | Passed focused parser tests with a temporary `_pytest._version` validation shim removed by the command trap. | `replace_exact_source_lines_after_anchor`, `insert_pytest_function_after_anchor` |
| `click-3405` | MAT-030 | `pallets/click#3405` | `validated` | `tests/test_termui.py` | Full accepted diff, repo-convention, and source/test parity. | Passed focused pager pytest with checkout-local `PYTHONPATH=src`. | `replace_exact_source_lines_after_anchor`, `insert_pytest_mark_decorator_before_function` |

None of these action kinds is named after the repository, PR, issue, or task.
They are reusable bounded source, test, pytest fixture, and pytest decorator
actions with repo-local convention checks.

## Reference Rows Kept Separate

DATA rows remain useful evidence for constrained source/test mechanism shape,
but they are not part of the MAT-007 held-out win count.

| Row | Evidence task | Role | Counted as held-out win |
| --- | --- | --- | --- |
| `pytest-14466` | DATA-029 | validated reference row | No |
| `scrapy-7351` | DATA-035 | validated reference row | No |

## Coverage Delta

| MAT-007 bucket | Count before MAT-027 | Covered by MAT-027..030 | Remaining count |
| --- | ---: | ---: | ---: |
| `current_structured_action` | 4 | 0 | 4 |
| `general_typed_builder` | 0 | 0 | 0 |
| `repo_convention_builder` | 4 | 4 | 0 |
| `constrained_local_generator` | 0 | 0 | 0 |
| `not_currently_expressible` | 2 | 0 | 2 |

Remaining non-materialized MAT-007 counts are therefore:

- `current_structured_action = 4`
- `general_typed_builder = 0`
- `repo_convention_builder = 0`
- `constrained_local_generator = 0`
- `not_currently_expressible = 2`

## Remaining Panel

| Bucket | Rows | Count |
| --- | --- | ---: |
| `current_structured_action` | `click-3423`, `flask-6013`, `flask-5898`, `pytest-14472` | 4 |
| `not_currently_expressible` | `flask-5812`, `flask-5727` | 2 |

The two `not_currently_expressible` rows should stay parked until there is a
multi-step migration or architecture planner. The next bounded materialization
work should come from `current_structured_action`.

## Recommended Next Task

Recommend starting the remaining `current_structured_action` panel with
`pallets/click#3423`. It is the smallest remaining held-out row: one file and
a targeted option-help expression replacement. It should verify target
selection and existing small-source action routing without opening a new
materializer family.

If the coordinator instead prioritizes broader product risk, the
shadow-advice-only residual examples from `TRANS-012` are a separate
workstream; they should not be mixed into MAT-007 held-out materialization
counts.

## Verdict

The original MAT-007 `repo_convention_builder` bucket is closed: 4 of 4 rows
are materialized and live-validated, with DATA reference rows kept outside the
held-out count. This is accounting evidence for the held-out panel, not a new
product gate or transition-routing change.
