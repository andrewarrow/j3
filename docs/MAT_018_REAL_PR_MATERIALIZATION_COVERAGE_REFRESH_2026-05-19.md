# MAT-018 Real PR Materialization Coverage Refresh

Task: `MAT-018`

Date: 2026-05-19

## Question

After `MAT-014` through `MAT-017`, are any MAT-013 unresolved
`general_typed_builder` rows still unaccounted for, and what materialization
work should come next?

Short answer: no `general_typed_builder` rows remain unresolved from the
MAT-007 held-out panel. All seven original rows now materialize and
live-validate with accepted-diff parity. The risk picture is mixed: four rows
are pure typed-builder coverage, one is broader general-AST coverage using
`statement_block_replace`, one is reusable filesystem-idiom coverage, and one
is reusable helper-extraction/call-replacement coverage.

## Artifacts

- JSONL rows:
  `docs/MAT_018_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-19.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-018-real-pr-materialization-refresh/MAT_018_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-19.jsonl`

## Coverage Delta

The source panel is still the 24-row MAT-007 held-out refresh. MAT-018 overlays
the MAT-010 through MAT-017 materialization evidence and does not re-score
unrelated current-action, repo-convention, constrained-generator, or
not-currently-expressible rows.

| MAT-007 bucket | Original held-out count | Covered pure typed builders | Covered broader general-AST | Covered filesystem idiom | Covered helper extraction / call replacement | Remaining count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_structured_action` | 4 | 0 | 0 | 0 | 0 | 4 |
| `general_typed_builder` | 7 | 4 | 1 | 1 | 1 | 0 |
| `repo_convention_builder` | 4 | 0 | 0 | 0 | 0 | 4 |
| `constrained_local_generator` | 7 | 0 | 0 | 0 | 0 | 7 |
| `not_currently_expressible` | 2 | 0 | 0 | 0 | 0 | 2 |

The remaining non-materialized MAT-007 held-out buckets are therefore:

- `current_structured_action`: 4 rows remain expressible by smaller existing
  actions, but they are not new MAT-010..017 replay evidence.
- `general_typed_builder`: 0 rows remain unresolved.
- `repo_convention_builder`: 4 rows remain.
- `constrained_local_generator`: 7 rows remain.
- `not_currently_expressible`: 2 rows remain intentionally outside one bounded
  materializer.

## Covered Rows

| Row | Original MAT-007 label | Evidence task | Coverage family | Action kinds | Parity and validation | Risk interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| `click-3422` | `general_typed_builder` | MAT-010 | Pure typed builder | `class_scope_annotation_move`, `return_annotation_update`, `type_annotation_update` | Full accepted-diff parity; `python -m py_compile src/click/utils.py` passed. | Low risk: one Python source file, annotation movement and return annotations only. |
| `requests-7441` | `general_typed_builder` | MAT-011 | Pure typed builder | `type_alias_update`, `import_member_remove`, `type_annotation_update` | Full accepted-diff parity; `python -m py_compile src/requests/_types.py src/requests/models.py` passed. | Low to moderate risk: typed alias/import cleanup across two source files. |
| `click-3396` | `general_typed_builder` | MAT-012 | Broader general-AST | `assignment_annotation_update`, `function_signature_update`, `boolean_condition_insert`, `statement_block_replace` | Full accepted-diff parity; `python -m py_compile src/click/_utils.py src/click/core.py src/click/parser.py` passed. | Moderate risk: covered, but not pure typed-builder evidence because bounded statement-suite replacement can express broader source edits. |
| `requests-7437` | `general_typed_builder` | MAT-014 | Pure typed builder | `type_annotation_update`, `assignment_type_ignore_update` | Full accepted-diff parity; `python -m py_compile src/requests/models.py` passed. | Low to moderate risk: one source file, type annotation plus scoped type-ignore placement. |
| `flask-5808` | `general_typed_builder` | MAT-015 | Pure typed builder | `function_signature_update` | Full accepted-diff parity; `python -m py_compile src/flask/sansio/app.py` passed. | Low risk: one source-file method annotation update. |
| `flask-5903` | `general_typed_builder` | MAT-016 | Filesystem-idiom builder | `makedirs_exist_ok_rewrite` | Full accepted-diff parity across source and tutorial docs; source-scoped Python parity for `examples/tutorial/flaskr/__init__.py`; `python -m py_compile examples/tutorial/flaskr/__init__.py` passed. | Reusable materializer coverage, but not pure typed-builder coverage; the layer rewrites a specific filesystem idiom in Python and RST code examples. |
| `click-3430` | `general_typed_builder` | MAT-017 | Helper extraction / call replacement | `helper_function_insert`, `local_assignment_replace`, `keyword_argument_value_replace`, `text_block_insert_after` | Full accepted-diff parity across source and changelog; source-scoped Python parity for `src/click/core.py`; `python -m py_compile src/click/core.py` passed. | Reusable materializer coverage, but not pure typed-builder coverage; the layer adds helpers, replaces duplicate call-site expressions, and records auxiliary text insertion separately. |

## Source-Scoped Vs Full-Diff Parity

For `click-3422`, `requests-7441`, `click-3396`, `requests-7437`, and
`flask-5808`, source-scoped parity and full-diff parity are the same because
the accepted diffs touched only Python source files.

For `flask-5903` and `click-3430`, source-scoped parity is not enough to claim
full accepted replay. Both rows also reproduced non-Python companion files:
`flask-5903` updated `docs/tutorial/factory.rst`, and `click-3430` updated
`CHANGES.rst`. The artifacts record expected non-Python AST parse failures for
those RST files plus diff/hash metadata, so the source materializer evidence
and auxiliary full-diff parity remain distinguishable.

## Risk Classes

The pure typed-builder layer now has four validated rows:

- `click-3422`
- `requests-7441`
- `requests-7437`
- `flask-5808`

The broader reusable materializer layer has three validated rows:

- `click-3396`: broader general-AST coverage with bounded
  `statement_block_replace`.
- `flask-5903`: filesystem-idiom coverage with `makedirs_exist_ok_rewrite`.
- `click-3430`: helper extraction and call-site replacement coverage with
  helper insertion, local assignment replacement, keyword argument value
  replacement, and anchored text insertion.

`flask-5903` and `click-3430` should be counted as reusable materializer
coverage, but not as pure typed-builder coverage. They resolved rows that
MAT-007 originally placed in `general_typed_builder`, yet the successful
materialization layers are filesystem idiom and helper-extraction/call-site
replacement rather than annotation, import, type-alias, or signature builders.

## Validation Status

All seven original MAT-007 `general_typed_builder` rows have:

- accepted changed-file allowlists respected;
- normalized accepted-diff parity;
- candidate-after diff/hash metadata;
- Python AST parse metadata for touched source files;
- focused `py_compile` validation passing for touched source files;
- no fallback to PR-named action kinds.

`statement_block_replace` was used only by `click-3396`. It was not needed for
`requests-7437`, `flask-5808`, `flask-5903`, or `click-3430`.

## Next Workstream

The next materialization workstream should move out of the now-covered typed
bucket and attack the largest remaining MAT-007 blocker:
`constrained_local_generator = 7`.

The recommended first bounded row is `psf/requests#7427`, with
`pytest-dev/pytest#14475` as the next alternative. The acceptance bar should be
the same as the typed refresh: reusable action records, source-scoped and
full-diff parity called out separately, focused validation, and an explicit
blocker if the row requires PR-specific source generation.

Repo-convention builders remain important, but the constrained-source/test
bucket is larger and tests whether the project can materialize behavior logic
without falling back to one bespoke action family per PR.

## Verdict

MAT-014 through MAT-017 close the four MAT-013 unresolved typed/general rows:
`requests-7437`, `flask-5808`, `flask-5903`, and `click-3430`. Across
MAT-010 through MAT-017, the original MAT-007 `general_typed_builder = 7`
bucket is fully accounted for with validated reusable materialization
evidence. The broader MAT-007 panel still has 17 non-materialized rows across
current structured actions, repo conventions, constrained local generation, and
not-currently-expressible migrations, so this refresh does not justify a broad
product gate. It does justify moving the next materialization probe to
constrained source/test generation.
