# MAT-023 Click #3434 Source-Region Candidate

Task: `MAT-023`

Date: 2026-05-19

## Result

MAT-023 materialized and live-validated the held-out `pallets/click#3434`
usage formatter candidate using reusable action records:

- `replace_function_region`
- `insert_pytest_function_after_anchor`

No action kind contains the repo name, issue number, or PR number. The
candidate changed only the accepted source/test paths:

- `src/click/formatting.py`
- `tests/test_formatting.py`

The accepted PR also changes `CHANGES.rst`, so full accepted-diff parity is
intentionally separate from source/test scoped parity.

## Pinned Refs

- Base ref: `7c99ebe23b931f27562d926814423cce85fd9766`
- PR head ref: `0551bf53588ae87f462d336f24f853a156fefe3a`
- Accepted merge commit: `3bb230dcd5d751f8605b46e9df5a541639d5fd4e`

## Parity

The final candidate matched the accepted PR source/test diff after normalizing
Git hunk context labels:

- Full accepted-diff parity: `false`
- Source/test scoped parity: `true`
- Accepted changed files:
  `["CHANGES.rst", "src/click/formatting.py", "tests/test_formatting.py"]`
- Candidate changed files:
  `["src/click/formatting.py", "tests/test_formatting.py"]`
- Mutation scope: only the two accepted source/test files changed.

Candidate-after metadata records source/test diffs, diff summaries, AST parse
success, source signature preservation, file hashes, and mutation scope in
`candidate.json`.

## Validation

Live materialization was run over a fresh checkout at the pinned base ref:

```bash
PYTHONPATH=/Users/aa/os/j3 python -m j3.heldout_source_region_candidate \
  --candidate click-3434 \
  --repo-path /tmp/j3-mat-023-click-3434/base \
  --accepted-diff /tmp/j3-mat-023-click-3434/final/accepted.diff \
  --out /tmp/j3-mat-023-click-3434/final/candidate.json \
  --report /tmp/j3-mat-023-click-3434/final/report.md \
  --diff-out /tmp/j3-mat-023-click-3434/final/candidate.diff \
  --validate \
  --validation-timeout-seconds 60
```

Validation used checkout-local source:

```bash
PYTHONPATH=src python -m pytest \
  tests/test_formatting.py::test_help_formatter_write_usage \
  tests/test_formatting.py::test_help_formatter_write_usage_without_args_styled_prefix \
  tests/test_formatting.py::test_command_write_usage_no_args -q
```

Result: `passed` in `0.02s` with `8 passed`.

## Artifacts

- `/tmp/j3-mat-023-click-3434/final/candidate.json`
- `/tmp/j3-mat-023-click-3434/final/report.md`
- `/tmp/j3-mat-023-click-3434/final/candidate.diff`
- `/tmp/j3-mat-023-click-3434/final/accepted.diff`

## Verdict

`click-3434` is a constrained source/test materialization win with exact
source/test scoped parity and live focused validation. The full accepted diff
is not equal because the accepted PR includes the non-source/test companion
file `CHANGES.rst`, which MAT-023 intentionally did not materialize.
