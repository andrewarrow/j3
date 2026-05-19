# MAT-022 Requests #7328 Source-Region Candidate

Task: `MAT-022`

Date: 2026-05-19

## Result

MAT-022 materialized and live-validated the held-out `psf/requests#7328`
redirect-history candidate using reusable action records:

- `replace_function_region`
- `insert_pytest_function_after_anchor`

No action kind contains the repo name, issue number, or PR number. The
candidate changed only the accepted source/test paths:

- `src/requests/sessions.py`
- `tests/test_requests.py`

## Pinned Refs

- Base ref: `cbce031327be4f1b4b5fd041ff4dcaa8efa2ce53`
- PR head ref: `3ee28b806f8bc414b29f7b4561e53c161924fe66`
- Accepted merge commit: `ef439eb779c1eba7cbdeeeb302b11e1e061b4b7d`

## Parity

The final candidate matched the accepted PR source/test diff after normalizing
Git hunk context labels:

- Full accepted-diff parity: `true`
- Source/test scoped parity: `true`
- Accepted changed files:
  `["src/requests/sessions.py", "tests/test_requests.py"]`
- Mutation scope: only the two accepted files changed.

Candidate-after metadata records source/test diffs, diff summaries, AST parse
success, source signature preservation, file hashes, and mutation scope in
`candidate.json`.

## Validation

Live materialization was run over a fresh checkout at the pinned base ref:

```bash
PYTHONPATH=/Users/aa/os/j3 python -m j3.heldout_source_region_candidate \
  --candidate requests-7328 \
  --repo-path /tmp/j3-mat-022-requests-7328/base \
  --accepted-diff /tmp/j3-mat-022-requests-7328/final/accepted.diff \
  --out /tmp/j3-mat-022-requests-7328/final/candidate.json \
  --report /tmp/j3-mat-022-requests-7328/final/report.md \
  --diff-out /tmp/j3-mat-022-requests-7328/final/candidate.diff \
  --validate \
  --validation-timeout-seconds 30
```

Validation used checkout-local source, not ambient site-packages:

```bash
PYTHONPATH=src python -m pytest \
  tests/test_requests.py::TestRequests::test_redirect_history_no_self_reference -q
```

Result: `passed` in `0.979s` with `1 passed in 0.62s`.

## Artifacts

- `/tmp/j3-mat-022-requests-7328/final/candidate.json`
- `/tmp/j3-mat-022-requests-7328/final/report.md`
- `/tmp/j3-mat-022-requests-7328/final/candidate.diff`
- `/tmp/j3-mat-022-requests-7328/final/accepted.diff`

## Verdict

`requests-7328` is a constrained source/test materialization win with exact
accepted-diff parity and live focused validation under the corrected
checkout-local Requests validation harness. The constrained-source queue can
move to the next uncovered formatter-family row, `click-3434`.
