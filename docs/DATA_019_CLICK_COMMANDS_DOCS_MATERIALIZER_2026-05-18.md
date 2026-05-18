# DATA-019 Click Commands Docs Materializer

Bounded materializer spike for the DATA-017 `docs/commands.md` auxiliary gap in
`pallets__click-issue-2745-pr-3364`.

## Summary

- Replay: `pallets__click-issue-2745-pr-3364`
- Target path: `docs/commands.md`
- Action family:
  `click_default_map_docs_section_generator_v1+myst_markdown_section_insert_v1`
- Generated section heading: `### Multi-value parameters`
- Contract checks: mentions `nargs > 1`, mentions the `{class}` role for
  `Tuple`, includes the whitespace-splitting example `"point": "3 4"`, and
  inserts before `## Context Defaults`
- Candidate status: `blocked` only because docs validation failed; the docs
  section materialized successfully
- Hosted LLM usage: none

## Mutation Scope

- Live checkout:
  `/tmp/j3-data-019-live/click` at
  `8a2b48901a08b3d2ec3a9bbd151948a9765368c6`
- Files changed by the materializer: `["docs/commands.md"]`
- Writes outside `docs/commands.md`: `[]`
- Source/test/changelog/config files changed: none
- Non-target accepted paths intentionally not materialized in this slice:
  `CHANGES.rst`, `docs/conf.py`, `src/click/core.py`, and
  `tests/test_defaults.py`

The full candidate diff is recorded in
`/tmp/j3-data-019-live/candidate.json` and
`/tmp/j3-data-019-live/report.md`. The diff inserts a 29-line
`Multi-value parameters` subsection before `## Context Defaults` and preserves
the surrounding command docs content.

## Validation

- Setup run:
  `python -m venv .venv-docs && .venv-docs/bin/python -m pip install -q --upgrade pip setuptools wheel && .venv-docs/bin/python -m pip install -q -e . sphinx myst-parser pallets-sphinx-themes sphinx-tabs sphinxcontrib-log-cabinet`
- Docs validation command:
  `.venv-docs/bin/python -m sphinx -W -b dirhtml docs /tmp/j3-data-019-live/docs-dirhtml`
- Runtime: `2.887s`
- Result: `blocked`
- Residual labels:
  `["docs_commands_section_materialized","docs_validation_blocked","docs_reference_resolution_failure"]`
- Exact blocker:
  `/private/tmp/j3-data-019-live/click/docs/commands.md:356: WARNING: local id not found in doc 'options': 'multiple-options-from-environment-values' [myst.xref_missing]`

The blocker is consistent with DATA-017: the accepted PR also changed
`docs/conf.py` with `myst_heading_anchors = 3`, but DATA-019 was deliberately
constrained to writing only `docs/commands.md`.

## Provenance

- Manifest evidence:
  `examples/issue_pr_mini_replay/manifest.json`
- DATA-014 candidate evidence:
  `/tmp/j3-data-014-live/candidate.json`
- DATA-017 auxiliary-gap evidence:
  `docs/DATA_017_CLICK_AUXILIARY_MATERIALIZATION_GAP_2026-05-18.md` and
  `/tmp/j3-data-017-aux-gap/audit.jsonl`
- DATA-019 artifacts:
  `/tmp/j3-data-019-live/candidate.json` and
  `/tmp/j3-data-019-live/report.md`
