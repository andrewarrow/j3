# MAT-020 Requests #7433 Source-Region Candidate

Task: `MAT-020`

Date: 2026-05-19

## Result

MAT-020 materialized the held-out `psf/requests#7433` stream-wrapper
candidate using reusable action records:

- `replace_function_region`
- `insert_pytest_function_after_anchor`

No action kind contains the repo name, issue number, or PR number. The
candidate changed only the accepted source/test paths:

- `src/requests/models.py`
- `tests/test_requests.py`

## Pinned Refs

- Base ref: `0b401c76b6e80a4eecf3c690085b2553f6e261ca`
- PR head ref: `ea1c36c1b1a8364e234b6ad49ea05e3261636f8a`
- Accepted merge commit from manifest: `6404f345e562d962abe6700a1c357ec1e7e18232`

## Parity

The final candidate matched the accepted PR source/test diff after normalizing
Git hunk context labels:

- Full accepted-diff parity: `true`
- Source/test scoped parity: `true`
- Accepted changed files:
  `["src/requests/models.py", "tests/test_requests.py"]`
- Mutation scope: only the two accepted files changed.

Candidate-after metadata records source/test diffs, diff summaries, AST parse
success, source signature preservation, file hashes, and mutation scope in
`candidate.json`.

## Validation

Live materialization was run over a fresh checkout at the pinned base ref:

```bash
PYTHONPATH=/Users/aa/os/j3 python -m j3.heldout_source_region_candidate \
  --candidate requests-7433 \
  --repo-path /tmp/j3-mat-020-requests-7433-live \
  --accepted-diff /tmp/j3-mat-020-requests-7433-final/accepted.diff \
  --out /tmp/j3-mat-020-requests-7433-final/candidate.json \
  --report /tmp/j3-mat-020-requests-7433-final/report.md \
  --diff-out /tmp/j3-mat-020-requests-7433-final/candidate.diff \
  --validate \
  --validation-timeout-seconds 30
```

Validation result: `timeout` after `30.012s` for:

```bash
python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q
```

A diagnostic run with `--setup-show -s` confirmed collection, fixture setup,
and the local `pytest-httpbin` request reaching the redirect endpoint before
timing out:

```text
collected 1 item
tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect
SETUP S httpbin
127.0.0.1 ... "POST /redirect-to?url=/post&status_code=307 HTTP/1.1" 307 0
```

This is recorded as `candidate_validation_timeout`, not hidden as a source
materialization failure.

## Artifacts

- `/tmp/j3-mat-020-requests-7433-final/candidate.json`
- `/tmp/j3-mat-020-requests-7433-final/report.md`
- `/tmp/j3-mat-020-requests-7433-final/candidate.diff`
- `/tmp/j3-mat-020-requests-7433-final/accepted.diff`

## Verdict

`requests-7433` is a constrained source/test materialization win with exact
accepted diff parity and reusable action shapes. The remaining blocker is live
validation timeout in the local Requests `pytest-httpbin` redirect path.
`requests-7328` should stay as the compact alternate for a later constrained
row, not a silent replacement for this result.
