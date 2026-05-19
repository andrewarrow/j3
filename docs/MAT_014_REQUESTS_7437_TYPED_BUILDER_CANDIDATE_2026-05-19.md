# MAT-014 Requests #7437 Typed-Builder Candidate

## Scope

- Repo: `psf/requests`
- Reference PR: `https://github.com/psf/requests/pull/7437`
- Base ref: `0b401c76b6e80a4eecf3c690085b2553f6e261ca`
- Accepted head ref: `dfe9ab8143fb71c72673738f25f0571347226b63`
- Candidate id: `mat-014-requests-response-reason-typing`

## Result

The candidate stays in the pure typed-builder layer.

- Action kinds: `type_annotation_update`, `assignment_type_ignore_update`
- `statement_block_replace`: not used
- Changed files: `src/requests/models.py`
- Accepted changed files: `src/requests/models.py`
- Writes outside allowlist: none
- Accepted diff normalized match: true
- Candidate AST parse: true
- Candidate diff summary: 2 added lines, 2 removed lines
- Validation: `python -m py_compile src/requests/models.py` passed in `0.024s`

## Materialized Diff

The candidate changes `Response.reason` from `str | None` to `str` and places
the accepted `# type: ignore[assignment]` comment on the constructor
initialization of `self.reason`. That type-ignore placement is represented by
the reusable `assignment_type_ignore_update` action using scoped AST target
parameters rather than a source-block replacement.

## Artifacts

- `/tmp/j3-mat-014-requests-7437-final/candidate.json`
- `/tmp/j3-mat-014-requests-7437-final/report.md`
- `/tmp/j3-mat-014-requests-7437-final/candidate.diff`
- `/tmp/j3-mat-014-requests-7437-final/accepted.diff`
