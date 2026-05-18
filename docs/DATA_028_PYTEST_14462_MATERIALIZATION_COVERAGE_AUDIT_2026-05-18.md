# DATA-028 Pytest #14462 Materialization Coverage Audit

Audit-only classification for `pytest-dev__pytest-issue-14462-pr-14466`.
No candidate source edits were attempted.

## Artifacts

- JSONL:
  `/tmp/j3-data-028-pytest-14462-materialization-audit/audit.jsonl`
- Report:
  `/tmp/j3-data-028-pytest-14462-materialization-audit/report.md`

## Result

- Rows: `2`
- Classification counts:
  `{"requiring_constrained_local_generator_or_source_region_action":2}`
- Current structured-action covered paths: `0`
- Accepted paths fully expressible now: `false`
- Provenance includes manifest metadata, DATA-018 preflight, DATA-026
  prompt/spec evidence, and DATA-026 local-knowledge evidence.

## Path Classifications

| Path | Classification | Proposed action | Validation |
| --- | --- | --- | --- |
| `src/_pytest/python_api.py` | `requiring_constrained_local_generator_or_source_region_action` | `pytest_approx_timedelta_source_region_update_v1 + python_dispatch_branch_insert_v1` | `python -m py_compile src/_pytest/python_api.py`; `pytest testing/python/approx.py -q` |
| `testing/python/approx.py` | `requiring_constrained_local_generator_or_source_region_action` | `pytest_existing_class_method_refine_and_insert_v1` | `pytest testing/python/approx.py -q` |

## Accepted Diff Stats

- `src/_pytest/python_api.py`: accepted numstat `31` added, `12` removed;
  git-derived hunk count `6`. The accepted edit spans
  `ApproxBase._approx_scalar`, `ApproxTimedelta.__init__`, and the
  datetime/timedelta `approx` documentation.
- `testing/python/approx.py`: accepted numstat `95` added, `5` removed;
  git-derived hunk count `5`. The accepted edit refines existing
  `TestApproxDatetime` timedelta relative-tolerance tests and adds validation,
  expected-value scaling, sequence, and mapping coverage.

## Failure Modes

- Source materialization can fail by accepting `rel` for datetime, continuing
  to treat timedelta `rel` as an absolute `timedelta`, missing sequence/mapping
  dispatch, missing negative/NaN validation, or computing relative tolerance
  from the actual value instead of `abs(expected)`.
- Test materialization can fail by adding generic timedelta cases without
  expected-value scaling, forgetting container dispatch, preserving the obsolete
  `rel=timedelta(...)` expectation, or placing tests outside
  `TestApproxDatetime` conventions.

## Smallest Next Falsifiable Tasks

- `DATA-028-next-approx-timedelta-source-region`: materialize only the accepted
  `ApproxBase._approx_scalar` dispatch branch plus `ApproxTimedelta.__init__`
  tolerance update in the repo-before checkout.
- `DATA-028-next-approx-test-class-refiner`: implement a constrained
  `TestApproxDatetime` refiner that changes the two existing rel tests and
  appends representative numeric-rel validation, scaling, and container cases.
