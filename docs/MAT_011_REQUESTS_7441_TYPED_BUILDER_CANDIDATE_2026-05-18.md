# MAT-011 Requests #7441 Typed-Builder Candidate

Task: `MAT-011`

Date: 2026-05-18

## Result

MAT-011 materialized and live-validated the held-out `psf/requests#7441`
typed-builder row on a fresh checkout.

- Repo: `psf/requests`
- Base ref: `b7b549b54571d03950b16afd2d01bc6ff0348224`
- Accepted head ref: `412f581d7e7c27bfee4f042fcac89bae9a804afe`
- Reference PR: <https://github.com/psf/requests/pull/7441>
- Candidate status: `validated`
- Changed files: `src/requests/_types.py`, `src/requests/models.py`
- Accepted changed files: `src/requests/_types.py`, `src/requests/models.py`
- Accepted diff normalized match: `true`
- Writes outside allowlist: none

## Reusable Actions

The candidate used general typed-builder actions, not a PR-named action kind:

- `type_alias_update`
- `import_member_remove`
- `type_annotation_update`

MAT-010's `type_annotation_update` family generalized after expansion from
insert-only class annotations to updating an existing class annotation. The row
also required two general typed-builder expansions: a parameterized TypeAlias
value update and a parameterized import-member removal for stale typing imports.

## Candidate-After Metadata

Candidate diff summary:

- Added lines: `2`
- Removed lines: `3`
- Changed lines: `5`
- Hunks: `3`

Per-file AST metadata:

- `src/requests/_types.py`: AST parse passed; one `MutableMapping` name was
  replaced with `Mapping`.
- `src/requests/models.py`: AST parse passed; the stale `MutableMapping`
  import node and alias were removed, and the `headers` annotation now uses
  `Mapping`.

## Validation

Focused validation passed on the fresh checkout:

```bash
python -m py_compile src/requests/_types.py src/requests/models.py
```

Runtime: `0.024s`.

## Artifacts

- `/tmp/j3-mat-011-requests-7441-final/candidate.json`
- `/tmp/j3-mat-011-requests-7441-final/report.md`
- `/tmp/j3-mat-011-requests-7441-final/candidate.diff`
- `/tmp/j3-mat-011-requests-7441-final/accepted.diff`

## Verdict

This is the second positive held-out `general_typed_builder` materialization
after MAT-007. It is not a pure reuse result: MAT-010's class annotation family
generalized, but requests #7441 also needed general, parameterized expansions
for TypeAlias assignment updates and stale import cleanup.
