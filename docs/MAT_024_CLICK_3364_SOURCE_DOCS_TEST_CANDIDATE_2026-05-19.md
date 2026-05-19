# MAT-024 Click #3364 Source/Docs/Test Candidate

Task: `MAT-024`

Repo: `pallets/click`

PR: `https://github.com/pallets/click/pull/3364`

## Result

MAT-024 materialized and live-validated the held-out `pallets/click#3364`
default-map splitting row with exact accepted-diff parity.

Pinned refs:

- Base: `8bd8b4a074c55c03b6eb5666edc44a9c43df38a2`
- Accepted head: `94004f1b5a4a982e8e33ef8d5f00cfb0e1dabddd`

Accepted changed files:

- `CHANGES.rst`
- `docs/commands.md`
- `docs/conf.py`
- `src/click/core.py`
- `tests/test_defaults.py`

Candidate changed files are the same five files. Mutation scope stayed inside
the task allowlist.

## Actions

The row uses reusable action kinds only:

- `replace_delimited_region` for the bounded `default_map` branch in
  `Parameter.consume_value`
- `insert_pytest_function_after_anchor` for
  `tests/test_defaults.py::test_default_map_nargs`
- `insert_text_around_anchor` for `CHANGES.rst`, `docs/commands.md`, and
  `docs/conf.py`

No action kind is named for Click, PR 3364, or this MAT task.

## Parity

- Full accepted-diff parity: `true`
- Source/test scoped parity: `true`
- Source/docs/test scoped parity: `true`

This PR's accepted diff spans source, docs, changelog/config docs, and tests,
so the JSON artifact records full parity and explicit source/test plus
source/docs/test scope comparisons.

## Validation

Live focused validation command:

```bash
PYTHONPATH=src python -m pytest tests/test_defaults.py::test_default_map_nargs -q
```

Result: `5 passed in 0.02s`.

## Artifacts

Generated artifacts:

- `/tmp/j3-mat-024-click-3364/final/candidate.json`
- `/tmp/j3-mat-024-click-3364/final/report.md`
- `/tmp/j3-mat-024-click-3364/final/candidate.diff`
- `/tmp/j3-mat-024-click-3364/final/accepted.diff`
- `/tmp/j3-mat-024-click-3364/final/accepted-files.txt`

## Notes

The first live attempt using `replace_function_region` hit a real target
selection blocker because `consume_value` is ambiguous in the Click AST. The
final candidate uses the existing reusable `replace_delimited_region` action
with local markers around the `default_map` branch instead of changing the
shared source-region materializer.
