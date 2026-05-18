# DATA-017 Click Auxiliary Materialization Gap Audit

Machine-readable audit over the DATA-014 accepted auxiliary paths. No candidate source edits were attempted.

## Summary

- Rows: `3`
- Classification counts: `{"covered_by_small_proposed_deterministic_action":2,"requiring_constrained_local_generator":1}`
- Current structured-action covered paths: `0`
- Accepted auxiliary paths fully expressible now: `false`

## Path Audit

| Path | Classification | Current action | Proposed action | Validation cost |
| --- | --- | --- | --- | --- |
| `CHANGES.rst` | `covered_by_small_proposed_deterministic_action` | `none` | `rst_changelog_unreleased_bullet_insert_v1` | `cheap` |
| `docs/commands.md` | `requiring_constrained_local_generator` | `none` | `click_default_map_docs_section_generator_v1 + myst_markdown_section_insert_v1` | `moderate` |
| `docs/conf.py` | `covered_by_small_proposed_deterministic_action` | `none` | `sphinx_conf_scalar_assignment_insert_v1` | `cheap` |

## Findings

### `CHANGES.rst`

- Accepted diff summary: `{"added_line_count":3,"anchor":"Version 8.4.0 / Unreleased","change_kind":"rst_changelog_entry_insert","git_numstat":{"added":3,"removed":0},"removed_line_count":0,"semantic_payload":"release-note bullet for splitting string default_map values for multi-value parameters"}`
- Likely failure mode: wrong release-section anchor, duplicate release note, or malformed RST issue/pr role references
- Smallest next task: `DATA-017-next-changelog-materializer`
- Probe: one three-line bullet is inserted under Version 8.4.0 / Unreleased and no source or test files change

### `docs/commands.md`

- Accepted diff summary: `{"added_line_count":29,"anchor":"before '## Context Defaults'","change_kind":"myst_markdown_section_insert","git_numstat":{"added":29,"removed":0},"removed_line_count":0,"semantic_payload":"new Multi-value parameters subsection with prose, an options.md anchor link, and two Python examples"}`
- Likely failure mode: generic or inaccurate docs prose, broken MyST roles or links, invalid examples, or insertion under the wrong command-doc section
- Smallest next task: `DATA-017-next-docs-section-generator`
- Probe: the generated section has the expected heading, mentions nargs > 1 and Tuple behavior, includes one whitespace-split example, and passes a docs build

### `docs/conf.py`

- Accepted diff summary: `{"added_line_count":1,"anchor":"after intersphinx_mapping","change_kind":"sphinx_config_assignment_insert","git_numstat":{"added":1,"removed":0},"removed_line_count":0,"semantic_payload":"myst_heading_anchors = 3"}`
- Likely failure mode: duplicate setting, insertion in a non-import-safe location, or silently stale docs behavior if the Markdown heading anchors are not built
- Smallest next task: `DATA-017-next-sphinx-conf-assignment`
- Probe: exactly one myst_heading_anchors = 3 assignment is inserted and docs/conf.py compiles

## Artifacts

- JSONL: `/private/tmp/j3-data-017-aux-gap/audit.jsonl`
