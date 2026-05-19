# MAT-021 Requests #7433 Validation Timeout Drilldown

Task: `MAT-021`

Date: 2026-05-19

## Verdict

The `MAT-020` timeout is a local validation setup issue, specifically an
import-path leak to the ambient installed `requests` package. It is not a
candidate regression and not accepted-head behavior.

`MAT-020` can be counted as live-validated by the corrected local-source
diagnostic evidence from this task. The original `MAT-020` artifact still
accurately records that its first validation command timed out, but the row
should not remain classified as `candidate_validation_timeout` for coverage
accounting.

## Setup

Fresh diagnostic checkouts were created under:

```text
/tmp/j3-mat-021-requests-7433-drilldown
```

Checkouts:

- `candidate`: base ref `0b401c76b6e80a4eecf3c690085b2553f6e261ca` plus
  `/tmp/j3-mat-020-requests-7433-final/candidate.diff`.
- `accepted_head`: accepted PR head
  `ea1c36c1b1a8364e234b6ad49ea05e3261636f8a`.
- `base`: unmodified base ref
  `0b401c76b6e80a4eecf3c690085b2553f6e261ca`.
- `base_test_only`: base ref plus only the accepted
  `tests/test_requests.py` hunk.

Full machine-readable command records, including stdout/stderr tails, are in:

```text
/tmp/j3-mat-021-requests-7433-drilldown/diagnostics.json
```

## Key Observation

From the candidate checkout, the original MAT-020 command environment imports
the globally installed package:

```text
2.34.0
/Users/aa/.pyenv/versions/3.11.15/lib/python3.11/site-packages/requests/__init__.py
/Users/aa/.pyenv/versions/3.11.15/bin/python
```

With `PYTHONPATH=src`, the same interpreter imports the checkout source:

```text
2.34.0
/private/tmp/j3-mat-021-requests-7433-drilldown/candidate/src/requests/__init__.py
/Users/aa/.pyenv/versions/3.11.15/bin/python
```

Requests' pytest configuration does not add `src/` to `sys.path`, so running
the focused test with the ambient interpreter can exercise the installed package
instead of the materialized candidate checkout.

## Diagnostic Runs

| Case | Command | Timeout | Runtime | Result | Tail |
| --- | --- | ---: | ---: | --- | --- |
| Candidate, original import path | `python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -vv --setup-show -s` | 12s | 12.010s | timeout | Collected one test, set up `httpbin`, reached `POST /redirect-to?url=/post&status_code=307`, then timed out. |
| Candidate, local source | `PYTHONPATH=src python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q` | 20s | 0.889s | passed | `1 passed in 0.53s` |
| Accepted head, original import path | `python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -vv --setup-show -s` | 12s | 12.011s | timeout | Same redirect endpoint reached before timeout. |
| Accepted head, local source | `PYTHONPATH=src python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q` | 20s | 0.905s | passed | `1 passed in 0.54s` |
| Base, local-source existing selector | `PYTHONPATH=src python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'` | 20s | 0.493s | passed | `5 passed, 333 deselected in 0.12s` |
| Base plus accepted test only, local source | `PYTHONPATH=src python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -vv --setup-show -s` | 12s | 12.013s | timeout | Same redirect endpoint reached before timeout. |
| Candidate, DATA-008 venv recipe setup | `python -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip setuptools wheel && .venv/bin/python -m pip install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme` | 120s | 5.610s | passed | setup completed |
| Candidate, DATA-008 venv recipe validation | `.venv/bin/python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q` | 30s | 1.497s | passed | `1 passed in 0.63s` |
| Accepted head, DATA-008 venv recipe setup | `python -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip setuptools wheel && .venv/bin/python -m pip install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme` | 120s | 5.306s | passed | setup completed |
| Accepted head, DATA-008 venv recipe validation | `.venv/bin/python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q` | 30s | 1.455s | passed | `1 passed in 0.63s` |

## Classification

- Candidate behavior: passes when the candidate checkout source is actually
  imported.
- Accepted-head behavior: passes under the same corrected local-source and venv
  recipes.
- Base behavior: existing focused base tests pass; base plus only the accepted
  test times out, matching the expected pre-fix failure mode.
- Original timeout source: the original MAT-020 command used an ambient Python
  environment that imported site-packages `requests`, not the candidate
  checkout.

The observed timeout should therefore be recorded as `local_setup_issue` /
`validation_import_path_leak`, not as `candidate_validation_timeout`.

## Recommendation

For this Requests row, validation commands should use either the DATA-008
checkout-local venv recipe or an explicit local source import path:

```bash
PYTHONPATH=src python -m pytest \
  tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q
```

The constrained-source queue can move forward with `requests-7433` counted as
materialized and live-validated. The next compact constrained row remains
`requests-7328`; `click-3434` remains the next formatter-family row.
