# MAT-017 Click #3430 Helper-Extraction Candidate

## Scope

- Repo: `pallets/click`
- Reference PR: `https://github.com/pallets/click/pull/3430`
- Base ref: `63daae27b124b717cffa8b458e1a0a43525f2b34`
- Accepted head ref: `843879880e94023317699ac2e85e5f7a44fb1b68`
- Candidate id: `mat-017-click-deprecated-helper-extraction`

## Result

The row is covered by reusable helper extraction and call-site replacement
actions, not by `statement_block_replace`.

- Action kinds: `text_block_insert_after`, `helper_function_insert`,
  `local_assignment_replace`, `keyword_argument_value_replace`
- `statement_block_replace`: not used
- Changed files: `CHANGES.rst`, `src/click/core.py`
- Accepted changed files: `CHANGES.rst`, `src/click/core.py`
- Writes outside allowlist: none
- Accepted diff normalized match: true
- Candidate diff summary: 30 added lines, 32 removed lines
- Python AST parse: true for `src/click/core.py`
- Changelog AST parse: false for `CHANGES.rst`, expected because it is RST
- Validation: `python -m py_compile src/click/core.py` passed in `0.029s`

## Materialization Notes

The Python source edit inserts `_format_deprecated_label` and
`_format_deprecated_suffix` after `_check_nested_chain`, then replaces repeated
local deprecated-label and warning-suffix computations in `Command`,
`Parameter`, and `Option` scopes. The changelog edit is recorded separately as
an anchored text insertion so the source helper parity and auxiliary docs
parity remain visible.

The helper/call-site action family is parameterized by target file, function or
class scope, helper names, insert anchor, local assignment names, old values,
replacement statements, and keyword argument value replacements. It is reusable
for similar helper extractions and duplicate call-site replacements without a
PR-named action kind.

## Artifacts

- `/tmp/j3-mat-017-click-3430-final/candidate.json`
- `/tmp/j3-mat-017-click-3430-final/report.md`
- `/tmp/j3-mat-017-click-3430-final/candidate.diff`
- `/tmp/j3-mat-017-click-3430-final/accepted.diff`
