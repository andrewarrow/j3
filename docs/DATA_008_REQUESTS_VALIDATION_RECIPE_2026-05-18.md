# DATA-008 Requests Validation Recipe Isolation

Candidate-free validation recipe work for
`psf__requests-issue-7432-pr-7433`; no candidate source edits were attempted.

## Result

The Requests row does not need to remain blocked on the recursive `httpbin`
fixture failure. The blocker was the DATA-006 setup command, which installed
`pytest` but not Requests' `pytest-httpbin`/`httpbin` test fixtures.

Use this hermetic pre-edit recipe before candidate generation:

```bash
python -m venv .venv &&
.venv/bin/python -m pip install -q --upgrade pip setuptools wheel &&
.venv/bin/python -m pip install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme
.venv/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'
```

The focused selector passes on the repo-before checkout with `5 passed, 333
deselected`; on the accepted PR merge it selects the added issue-specific test
and passes with `6 passed, 333 deselected`.

## Attempts

| Attempt | Setup command | Validation command | Runtime | First failed stage | Evidence | Recommendation |
| --- | --- | --- | ---: | --- | --- | --- |
| Original DATA-006 setup | `python -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip setuptools wheel && .venv/bin/python -m pip install -e requests pytest` | `.venv/bin/python -m pytest tests/test_requests.py -q` | setup `1.76s`; validation `8.75s` | validation | `recursive dependency involving fixture 'httpbin' detected`; `142 passed, 1 skipped, 1 xfailed, 194 errors` | Do not use; fixture dependency missing. |
| Repository test deps | `.venv/bin/python -m pip install -r requirements-dev.txt` | `.venv/bin/python -m pytest tests/test_requests.py -q` | setup `4.50s`; validation `38.72s` | none | `336 passed, 1 skipped, 1 xfailed` | Valid but too broad for focused replay. |
| Exact future test node | existing `.venv` after repository test deps | `.venv/bin/python -m pytest tests/test_requests.py::TestRequests::test_getattr_proxy_stream_follows_redirect -q` | validation `0.69s` | validation | pytest exit `4`, node not found on repo-before checkout | Not usable as a pre-edit baseline command. |
| Existing prepare/rewind nodes | existing `.venv` after repository test deps | `.venv/bin/python -m pytest tests/test_requests.py::TestRequests::test_prepare_body_position_non_stream tests/test_requests.py::TestRequests::test_rewind_body tests/test_requests.py::TestRequests::test_rewind_partially_read_body tests/test_requests.py::TestRequests::test_rewind_body_no_seek tests/test_requests.py::TestRequests::test_rewind_body_failed_seek tests/test_requests.py::TestRequests::test_rewind_body_failed_tell -q` | validation `0.23s` | none | `6 passed` | Valid baseline smoke, but it will not automatically include a newly added issue-specific test. |
| Focused `-k` with minimal fixture deps | `python -m venv .venv-min && .venv-min/bin/python -m pip install -q --upgrade pip setuptools wheel && .venv-min/bin/python -m pip install -e requests pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme` | `.venv-min/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'` | setup `2.79s`; validation `0.93s` | none | `5 passed, 333 deselected` | Valid shape; final recipe should use an in-checkout venv. |
| Discarded accepted-merge diagnostic | reused `.venv-min` installed editable from the repo-before checkout | `.venv-min/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'` from an accepted-merge clone | killed after about `60s` | validation | invalid diagnostic because the editable install still pointed at repo-before source | Do not count. Rerun with an accepted-checkout-local venv. |
| Final DATA-008 recipe smoke | `python -m venv .venv && .venv/bin/python -m pip install -q --upgrade pip setuptools wheel && .venv/bin/python -m pip install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme` | `.venv/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'` | setup `5.695s`; validation `1.157s`; total `8.194s` | none | `5 passed, 333 deselected` | Use this as the Requests pre-edit validation recipe. |
| Accepted PR recipe check | same venv-local setup on merge commit `6404f345e562d962abe6700a1c357ec1e7e18232` | `.venv/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'` | setup `2.75s`; validation `1.66s` | none | `6 passed, 333 deselected` | Confirms the selector catches the accepted issue-specific test once present. |

## Artifacts

- Recipe attempt JSONL: `/tmp/j3-data-008-live/attempts.jsonl`
- Recipe attempt report: `/tmp/j3-data-008-live/report.md`
- Repo-before checkout: `/tmp/j3-data-008-live/repos/psf__requests-psf__requests-issue-7432-pr-7433-0b401c76b6e8`
- Accepted-merge diagnostic checkout: `/tmp/j3-data-008-accepted/requests`

## Recommendation

Mark the DATA-007 Requests validation blocker as resolved by recipe isolation.
Candidate generation may proceed for this row only after separate prompt/spec
and local-knowledge blockers are addressed; the manifest still records
`prompt_spec_parsing_gap`, `local_knowledge_gap`, and `ranking_gap` as
non-validation residuals.
