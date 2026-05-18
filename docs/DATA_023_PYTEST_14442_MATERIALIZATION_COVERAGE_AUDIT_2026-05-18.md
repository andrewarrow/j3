# DATA-023 Pytest #14442 Materialization Coverage Audit

Machine-readable audit over the accepted pytest #14442/#14443 changed paths.
No candidate source edits were attempted.

## Summary

- Replay: `pytest-dev__pytest-issue-14442-pr-14443`
- Repo-before ref: `8f81c76744daf72d4f77cfc8423f4bdc60733d78`
- Accepted merge ref: `a481f264d70ac3d053d5f7408f4ac1ec439d0c2f`
- JSONL: `/tmp/j3-data-023-pytest-14442-materialization-audit/audit.jsonl`
- Generated report:
  `/tmp/j3-data-023-pytest-14442-materialization-audit/report.md`
- Classification counts:
  `{"covered_by_small_proposed_deterministic_action":1,"requiring_constrained_local_generator_or_source_region_action":4}`
- Current structured-action covered paths: `0`
- Accepted paths fully expressible now: `false`

## Path Audit

| Path | Classification | Proposed action | Accepted diff stats |
| --- | --- | --- | --- |
| `AUTHORS` | `covered_by_small_proposed_deterministic_action` | `newline_delimited_sorted_unique_insert_v1` | `+2/-0`, 2 hunks |
| `changelog/14442.bugfix.rst` | `requiring_constrained_local_generator_or_source_region_action` | `pytest_bugfix_changelog_fragment_generator_v1 + towncrier_fragment_create_v1` | `+3/-0`, 1 hunk |
| `src/_pytest/config/__init__.py` | `requiring_constrained_local_generator_or_source_region_action` | `python_from_import_insert_v1 + config_parse_addopts_override_source_region_v1` | `+7/-0`, 2 hunks |
| `testing/test_config.py` | `requiring_constrained_local_generator_or_source_region_action` | `pytest_parametrize_existing_test_refine_v1` | `+10/-5`, 2 hunks |
| `testing/test_mark.py` | `requiring_constrained_local_generator_or_source_region_action` | `pytest_parametrize_existing_test_refine_v1` | `+13/-8`, 5 hunks |

## Findings

`AUTHORS` is the only accepted path covered by a small proposed deterministic
action: a sorted, unique newline-entry inserter. The materializer still needs
explicit contributor-name evidence; DATA-021 local knowledge only captured one
expected entry, while the accepted diff adds two names.

`changelog/14442.bugfix.rst` needs a deterministic issue-numbered fragment
creator plus a constrained changelog-text generator. The path and suffix are
deterministic, but the RST prose and pytest docs roles are semantic content.

`src/_pytest/config/__init__.py` needs a deterministic import insertion plus a
bounded source-region action inside `Config.parse`. The existing
`source_region_replace_v1` surface is not enough by itself because the accepted
edit is non-contiguous.

`testing/test_config.py` and `testing/test_mark.py` need a constrained
existing-pytest-test refiner. Existing deterministic pytest replacement helpers
are replay-specific; this accepted diff modifies parametrized tests and branch
shape in existing pytest files.

## Next Falsifiable Materializer Tasks

- `DATA-023-next-authors-inserter`: prove sorted unique insertion of the two
  accepted `AUTHORS` names without touching behavior files.
- `DATA-023-next-pytest-changelog-fragment`: generate the issue-numbered
  `.bugfix.rst` fragment from DATA-021 prompt/spec fields.
- `DATA-023-next-config-parse-region`: materialize the accepted import plus
  `Config.parse` override update and run focused strict-addopts validation.
- `DATA-023-next-test-config-parametrize-refine`: refine
  `test_strict_config_ini_option` with the accepted `addopts` strict-config
  case.
- `DATA-023-next-test-mark-parametrize-refine`: refine
  `test_strict_prohibits_unregistered_markers` with the accepted `addopts`
  strict-markers case.

## Provenance

The audit rows include manifest provenance, DATA-018 preflight outcome
provenance, DATA-021 prompt/spec provenance, DATA-021 local-knowledge
provenance, and accepted diff stats from the DATA-018 repo-before checkout.
