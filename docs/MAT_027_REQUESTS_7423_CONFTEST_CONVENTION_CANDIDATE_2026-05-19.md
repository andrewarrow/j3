# MAT-027 Requests #7423 Conftest Convention Candidate

Candidate attempt for `psf/requests#7423`.

## Summary

`MAT-027` materialized the accepted PR diff with a reusable repo-convention
action:

- `insert_pytest_fixture_after_anchor`

No action kind is named for Requests, PR 7423, or this task. The candidate
changes only `tests/conftest.py` and inserts an autouse pytest fixture after
the local `prepare_url` helper, matching the repo-local convention of central
pytest fixtures in `tests/conftest.py`.

## Pinned Refs

- Base ref: `e8d2c015eecda8273612dd4562425e00cd164ba5`
- Accepted head ref: `da905d0eb1de1184d323d39dfc2ce2b423df7bee`
- Reference PR: <https://github.com/psf/requests/pull/7423>
- Accepted changed files: `tests/conftest.py`

## Candidate Metadata

- Candidate status: `validated`
- Mutation scope: `tests/conftest.py`
- Writes outside allowlist: none
- Candidate diff summary: `+9/-0`, one hunk
- Accepted diff normalized match: `true`
- Repo-convention scoped match: `true`
- `tests/conftest.py` SHA-256 before:
  `c31d83bf96fbf585c0d497fbf21a39b2e69411948ddb947e5ad51e5857976c5c`
- `tests/conftest.py` SHA-256 after:
  `6d65ffb582519f80a66c5d1ef571e3c33395a199f9e67fcb500c6ad2d7800e0a`

Convention detection recorded:

- target file is `conftest.py`
- `pytest` import exists
- existing fixtures: `httpbin`, `httpbin_secure`, `nosan_server`
- inserted fixture: `clean_proxy_environ(monkeypatch)`
- inserted fixture decorator: `@pytest.fixture(autouse=True)`

## Validation

Live validation ran from the pinned base checkout after materialization:

```bash
HTTP_PROXY=http://127.0.0.1:1 \
HTTPS_PROXY=http://127.0.0.1:1 \
ALL_PROXY=http://127.0.0.1:1 \
PYTHONPATH=src python -m pytest \
  tests/test_requests.py::TestRequests::test_HTTP_200_OK_GET_ALTERNATIVE -q
```

Result: `1 passed in 0.62s`.

The command explicitly uses checkout-local Requests with `PYTHONPATH=src` to
avoid the MAT-021 ambient site-packages import leak.

## Artifacts

- Candidate JSON:
  `/tmp/j3-mat-027-requests-7423/final/candidate.json`
- Candidate report:
  `/tmp/j3-mat-027-requests-7423/final/report.md`
- Candidate diff:
  `/tmp/j3-mat-027-requests-7423/final/candidate.diff`
- Accepted diff:
  `/tmp/j3-mat-027-requests-7423/accepted.diff`

## Result

`requests-7423` is materialized and live-validated with exact accepted-diff
parity. This closes one `repo_convention_builder` row from the MAT-007 panel.
The remaining repo-convention rows are `click-3405`, `requests-7315`, and
`pytest-14429`.
