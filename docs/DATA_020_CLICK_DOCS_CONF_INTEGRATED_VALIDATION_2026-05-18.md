# DATA-020 Click Docs Conf Integrated Validation

Bounded integrated materialization for the Click #2745/#3364 auxiliary docs
validation blocker found in DATA-019.

## Summary

- Replay: `pallets__click-issue-2745-pr-3364`
- Live checkout:
  `/tmp/j3-data-020-live/click` at
  `8a2b48901a08b3d2ec3a9bbd151948a9765368c6`
- Status: `validated`
- Files changed in the live checkout:
  `["docs/commands.md","docs/conf.py"]`
- Writes outside those two paths: `[]`
- Action family:
  `click_default_map_docs_section_generator_v1+myst_markdown_section_insert_v1+sphinx_conf_scalar_assignment_insert_v1`
- Config assignment: exactly one `myst_heading_anchors = 3`
- Sphinx docs build: passed
- Validation runtime: `3.068s`
- Residual labels:
  `["docs_commands_section_materialized","sphinx_conf_assignment_materialized","docs_validation_passed"]`
- Blockers: none

## Artifacts

- Candidate record: `/tmp/j3-data-020-live/candidate.json`
- Report: `/tmp/j3-data-020-live/report.md`
- Docs build output: `/tmp/j3-data-020-live/docs-dirhtml`

## Provenance

- DATA-017 auxiliary-gap audit:
  `docs/DATA_017_CLICK_AUXILIARY_MATERIALIZATION_GAP_2026-05-18.md` and
  `/tmp/j3-data-017-aux-gap/audit.jsonl`
- DATA-019 command-docs materializer:
  `docs/DATA_019_CLICK_COMMANDS_DOCS_MATERIALIZER_2026-05-18.md` and
  `/tmp/j3-data-019-live/candidate.json`
