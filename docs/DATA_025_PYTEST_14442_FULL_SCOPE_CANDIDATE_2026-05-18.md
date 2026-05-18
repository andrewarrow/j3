# DATA-025 Pytest #14442 Full-Scope Candidate

Bounded full-scope candidate attempt for exactly
`pytest-dev__pytest-issue-14442-pr-14443`. It reuses the validated DATA-024
source/test candidate and adds deterministic auxiliary materializers for
`AUTHORS` and `changelog/14442.bugfix.rst`.

## Summary

- Repo-before ref: `8f81c76744daf72d4f77cfc8423f4bdc60733d78`
- Candidate JSON:
  `/tmp/j3-data-025-pytest-14442-full-scope/candidate.json`
- Generated report:
  `/tmp/j3-data-025-pytest-14442-full-scope/report.md`
- Live worktree:
  `/tmp/j3-data-025-pytest-14442-full-scope/repo-8f81c767-v3`
- Status: `validated`
- Live changed files:
  `AUTHORS`, `changelog/14442.bugfix.rst`,
  `src/_pytest/config/__init__.py`, `testing/test_config.py`,
  `testing/test_mark.py`
- Validation: `pytest testing/test_config.py testing/test_mark.py -q`
  passed in `6.083s`

## Candidate Actions

- `newline_delimited_sorted_unique_insert`: inserted `Hamza Mobeen` and
  `Praneeth Kodumagulla` into the `AUTHORS` contributors section using a
  deterministic accent-normalized casefold ordering.
- `towncrier_fragment_create`: created
  `changelog/14442.bugfix.rst` with the issue-specific pytest bugfix prose and
  Sphinx roles for `--strict-markers`, `--strict-config`, and `addopts`.
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

The full accepted edit is now expressible by the current bounded DATA-025 action
surface for this replay. The live mutation scope changed exactly the five
accepted paths and no other files.

Residual labels:

- `candidate_validation_passed`

Structured-action coverage labels:

- `newline_delimited_sorted_unique_insert_authors_covered`
- `towncrier_bugfix_fragment_create_covered`
- `python_from_import_insert_covered`
- `config_parse_addopts_override_source_region_covered`
- `pytest_parametrize_existing_test_refine_config_covered`
- `pytest_parametrize_existing_test_refine_mark_covered`
- `focused_validation_covered`

## Provenance

The candidate record cites DATA-018 validation preflight, DATA-021 prompt/spec
and local-knowledge evidence, DATA-022 readiness evidence, DATA-023
materialization-audit evidence, and the validated DATA-024 source/test
candidate shape.
