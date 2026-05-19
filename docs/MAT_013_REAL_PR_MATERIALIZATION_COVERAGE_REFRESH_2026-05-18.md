# MAT-013 Real PR Materialization Coverage Refresh

Task: `MAT-013`

Date: 2026-05-18

## Question

After MAT-010 through MAT-012, how much of the MAT-007 held-out
`general_typed_builder` bucket is now covered by reusable materialization
actions, and does bounded `statement_block_replace` change the risk picture?

Short answer: three of the seven MAT-007 held-out typed/general-AST rows now
materialize and live-validate. Two are pure typed-builder wins. One is a broader
general-AST win because it required bounded `statement_block_replace`. That
improves coverage, but it should not be counted as the same risk class as the
pure annotation/import/type-alias builders.

## Artifacts

- JSONL rows:
  `docs/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-013-real-pr-materialization-refresh/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.jsonl`

## Coverage Delta

The source panel is the 24-row MAT-007 held-out refresh. MAT-013 overlays only
the MAT-010 through MAT-012 typed/general-AST evidence; it does not re-score
unrelated source-region, repo-convention, or broad migration rows.

| MAT-007 bucket | Original held-out count | Covered by MAT-010..012 pure typed builders | Covered by MAT-012 broader general-AST | Remaining count |
| --- | ---: | ---: | ---: | ---: |
| `current_structured_action` | 4 | 0 | 0 | 4 |
| `general_typed_builder` | 7 | 2 | 1 | 4 |
| `repo_convention_builder` | 4 | 0 | 0 | 4 |
| `constrained_local_generator` | 7 | 0 | 0 | 7 |
| `not_currently_expressible` | 2 | 0 | 0 | 2 |

The remaining materialization gap after this overlay is therefore:

- `general_typed_builder`: 4 unresolved rows.
- `repo_convention_builder`: 4 unresolved rows.
- `constrained_local_generator`: 7 unresolved rows.
- `not_currently_expressible`: 2 rows still intentionally outside one bounded
  materializer.
- `current_structured_action`: 4 rows remain expressible by existing smaller
  actions, but they are not new MAT-010..012 evidence.

## Rows Now Covered

| Row | Original MAT-007 label | Evidence task | Coverage family | Action kinds | Risk interpretation |
| --- | --- | --- | --- | --- | --- |
| `click-3422` | `general_typed_builder` | MAT-010 | Pure typed builder | `class_scope_annotation_move`, `return_annotation_update`, `type_annotation_update` | Lowest new risk among the three: annotation-only AST edits in one file, accepted-diff parity, py_compile pass. |
| `requests-7441` | `general_typed_builder` | MAT-011 | Pure typed builder | `type_alias_update`, `import_member_remove`, `type_annotation_update` | Still pure typed-builder coverage, but it required general expansions for type aliases and stale import cleanup. |
| `click-3396` | `general_typed_builder` | MAT-012 | Broader general-AST | `assignment_annotation_update`, `function_signature_update`, `boolean_condition_insert`, `statement_block_replace` | Covered, but not pure typed-builder evidence because statement-suite replacement can express more than annotation/import edits. |

## `statement_block_replace` Risk

`statement_block_replace` changes the risk classification for `click-3396`
only. MAT-007 originally placed the row in `general_typed_builder`; MAT-012
proved it can be materialized, but the proof is a broader general-AST action
family rather than a pure typed-builder family.

The action does not justify reclassifying any remaining MAT-007 row as covered.
It is bounded and reusable, but it still replaces a statement block after target
selection. That means the product risk is higher than annotation or import
builders and should keep stricter gates:

- exact file allowlist and AST anchor match;
- before/after parse checks;
- accepted-diff or candidate-diff normalization evidence in replay mode;
- focused validation on the touched files;
- no use as a catch-all source generator for behavior synthesis, docs, tests,
  or repo-convention placement.

The practical impact is positive but narrow: the reusable vocabulary now covers
one harder cross-file typed/general-AST row without adding a PR-named action,
while leaving the constrained local generator and repo-convention buckets
unchanged.

## Remaining Typed Rows

The unresolved MAT-007 `general_typed_builder` rows are:

- `click-3430`: helper extraction and duplicate call-site replacement.
- `flask-5903`: try/except/pass filesystem idiom rewrite.
- `flask-5808`: method annotation update.
- `requests-7437`: assignment annotation/type-ignore placement for
  `Response.reason`.

## Next Bounded Row

The next bounded materialization row should be `psf/requests#7437`. It is small,
still in the remaining typed bucket, and tests whether the newer
`assignment_annotation_update` surface can cover a pure typed-builder row
without invoking `statement_block_replace`. If it needs a statement-suite
replacement, record that as evidence that assignment/type-ignore placement is
not yet safely captured by the pure typed layer.

## Verdict

MAT-010 through MAT-012 reduce the MAT-007 held-out typed/general-AST gap from
seven rows to four unresolved rows. The strongest claim is that the project now
has two validated pure typed-builder rows plus one validated broader
general-AST row. The weaker claim, which should be avoided, is that
`statement_block_replace` makes the whole typed-builder bucket safe. It does
not; it is useful coverage with a higher-risk gate.
