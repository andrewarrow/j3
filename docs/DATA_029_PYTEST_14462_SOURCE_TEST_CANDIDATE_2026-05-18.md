# DATA-029 Pytest #14462 Source/Test Candidate

Candidate attempt for `pytest-dev__pytest-issue-14462-pr-14466`.
No hosted LLM source generation was used.

## Artifacts

- Candidate JSON:
  `/tmp/j3-data-029-pytest-14462-source-test/candidate.json`
- Candidate report:
  `/tmp/j3-data-029-pytest-14462-source-test/report.md`
- Live checkout:
  `/tmp/j3-data-029-pytest-14462-source-test/repo-fbab7c5d-exact2`

## Result

- Status: `validated`
- Residual labels: `["candidate_validation_passed"]`
- Changed files: `["src/_pytest/python_api.py", "testing/python/approx.py"]`
- Writes outside allowlist: `[]`
- Validation command:
  `python -m py_compile src/_pytest/python_api.py && pytest testing/python/approx.py -q`
- Validation result: `passed` in `2.601` seconds, with
  `130 passed in 0.21s` from the focused pytest module.

## Materialization

- Source materializer updated `ApproxBase._approx_scalar` to dispatch
  `datetime` and `timedelta` values inside containers to `ApproxTimedelta`.
- Source materializer updated `ApproxTimedelta.__init__` so timedelta `rel`
  accepts numeric fractions, rejects negative or NaN `rel`, rejects negative
  `abs`, computes `rel * abs(expected)`, and preserves datetime `rel`
  rejection.
- Test materializer refined only `TestApproxDatetime`, replacing the obsolete
  `rel=timedelta(...)` timedelta assertions and adding numeric `rel`
  validation, expected-value scaling, and sequence/mapping dispatch coverage.

## Coverage

- Structured action coverage: `accepted_edit_covered = true`
- Coverage labels:
  `python_dispatch_branch_insert_datetime_timedelta_covered`,
  `pytest_approx_timedelta_numeric_rel_source_region_covered`,
  `approx_datetime_timedelta_doc_region_covered`,
  `pytest_testapproxdatetime_method_refine_insert_covered`,
  `focused_validation_covered`
- Evidence provenance recorded DATA-018 preflight, DATA-026 prompt/spec and
  local knowledge, DATA-027 readiness, and DATA-028 materialization audit.
- Candidate diff matches accepted PR commit
  `2c555d62fa2c51ccb0c4c1cdd6243149ce4ffa97` for both touched paths.
  Numstat: `31 12 src/_pytest/python_api.py` and
  `95 5 testing/python/approx.py`.
