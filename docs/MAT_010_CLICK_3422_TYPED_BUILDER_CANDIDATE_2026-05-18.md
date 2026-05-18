# MAT-010 Click #3422 Typed-Builder Candidate

Task: `MAT-010`

Date: 2026-05-18

## Result

MAT-010 materialized and live-validated the held-out
`pallets/click#3422` typed-builder row using reusable action records:

- `class_scope_annotation_move`
- `return_annotation_update`
- `type_annotation_update`

No action kind contains the repo name, issue number, or PR number. The final
candidate changed only:

- `src/click/utils.py`

The candidate diff matched the accepted PR diff after normalization.

## Validation

Focused validation passed on a fresh checkout pinned to
`fc6c7c47edd6110b6bd5a1a5297b2035214b0cd1`:

```bash
python -m py_compile src/click/utils.py
```

The run completed in `0.022s`.

## Evidence

Artifacts:

- `/tmp/j3-mat-010-click-3422-final/candidate.json`
- `/tmp/j3-mat-010-click-3422-final/report.md`
- `/tmp/j3-mat-010-click-3422-final/candidate.diff`
- `/tmp/j3-mat-010-click-3422-final/accepted.diff`

This is the first held-out `general_typed_builder` win after MAT-007. It does
not solve the whole typed-builder bucket, but it proves the annotation/import
middle layer is not inherently blocked on free-form source generation for this
class of edits.
