# DATA-024 Pytest #14442 Source/Test Candidate Attempt

Bounded candidate attempt for exactly
`pytest-dev__pytest-issue-14442-pr-14443` in explicit source/test-only scope.
No hosted LLM source generation was used.

## Summary

- Repo-before ref: `8f81c76744daf72d4f77cfc8423f4bdc60733d78`
- Candidate JSON:
  `/tmp/j3-data-024-pytest-14442-source-test/candidate.json`
- Generated report:
  `/tmp/j3-data-024-pytest-14442-source-test/report.md`
- Status: `validated`
- Live changed files:
  `src/_pytest/config/__init__.py`, `testing/test_config.py`,
  `testing/test_mark.py`
- Validation: `pytest testing/test_config.py testing/test_mark.py -q`
  passed in `4.574s`; setup plus validation runtime was `6.598s`

## Candidate Actions

- `python_from_import_insert`: inserted
  `from .findpaths import parse_override_ini`.
- `config_parse_addopts_override_source_region`: after the addopts
  `parse_known_args` call, update `_inicfg` from parsed `override_ini` values
  and clear `_inicache` once.
- `pytest_parametrize_existing_test_refine`: extended
  `TestParseIni.test_strict_config_ini_option` with
  `addopts = --strict-config`.
- `pytest_parametrize_existing_test_refine`: extended
  `test_strict_prohibits_unregistered_markers` with
  `addopts = --strict-markers`.

## Scope And Residuals

The source/test behavior slice is covered and validated. Full accepted-edit
coverage remains false because `AUTHORS` and `changelog/14442.bugfix.rst` were
explicitly out of scope for DATA-024.

Residual labels:

- `candidate_validation_passed`
- `accepted_auxiliary_paths_not_materialized`

Structured-action coverage labels:

- `python_from_import_insert_covered`
- `config_parse_addopts_override_source_region_covered`
- `pytest_parametrize_existing_test_refine_config_covered`
- `pytest_parametrize_existing_test_refine_mark_covered`
- `focused_validation_covered`
- `accepted_auxiliary_paths_not_covered`

## Provenance

The candidate record cites DATA-018 validation preflight, DATA-021 prompt/spec
and local-knowledge evidence, DATA-022 readiness evidence, and DATA-023
materialization-audit evidence. Evidence counts in the candidate record are:
`{"readiness":1,"prompt_spec":1,"validation":1,"local_knowledge":7,"materialization_audit":5}`.
