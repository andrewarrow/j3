# MAT-028 Requests #7315 Adapter Convention Candidate

Candidate attempt for `psf/requests#7315`.

## Summary

`MAT-028` materialized the accepted PR diff with reusable bounded
repo-convention actions:

- `delete_exact_source_lines_after_anchor`
- `rename_pytest_function`
- `replace_pytest_assertion_expected_literal`

No action kind is named for Requests, PR 7315, or this task. The candidate
deletes the local `HTTPAdapter.request_url` leading-slash normalization guard,
renames the existing adapter test, and updates that test's expected path value.

## Pinned Refs

- Base ref: `e8d2c015eecda8273612dd4562425e00cd164ba5`
- Accepted head ref: `fd628095d7b9ddbf3e987d8a4bf0e6062768916f`
- Reference PR: <https://github.com/psf/requests/pull/7315>
- Accepted changed files: `src/requests/adapters.py`, `tests/test_adapters.py`

The PR branch head was `cead573dedd928161ca7c402ddacbd8c8e05faee`, but the
accepted mainline commit is the squash merge commit above.

## Candidate Metadata

- Candidate status: `validated`
- Mutation scope: `src/requests/adapters.py`, `tests/test_adapters.py`
- Writes outside allowlist: none
- Candidate diff summary: `+2/-4`, two hunks
- Accepted diff normalized match: `true`
- Repo-convention scoped match: `true`
- `src/requests/adapters.py` SHA-256 before:
  `2d225e496546bea5bd1864f769af3774a0cdcd43d876eddf5516678925cb4135`
- `src/requests/adapters.py` SHA-256 after:
  `647eabd4453de232aa40b55ff033d6f19778910b7e7069c51fdf63076fc77493`
- `tests/test_adapters.py` SHA-256 before:
  `28f88de1601bcde6a9f178b98452d6b90c55f5d1a6c9a2c15622cd760fbd4c91`
- `tests/test_adapters.py` SHA-256 after:
  `102494aa704f8505fb22fa476452f6aa3aae756da82fe2d5b2a2a3f366b38bf4`

Convention detection recorded:

- source anchor function: `request_url`
- exact deleted line count: 2
- adapter test import: `requests.adapters`
- renamed test:
  `test_request_url_trims_leading_path_separators` ->
  `test_request_url_handles_leading_path_separators`
- assertion expected literal: `/v:h` -> `//v:h`

## Validation

Live validation ran from the pinned base checkout after materialization:

```bash
PYTHONPATH=src python -m pytest \
  tests/test_adapters.py::test_request_url_handles_leading_path_separators -q
```

Result: `1 passed in 0.01s`.

The command explicitly uses checkout-local Requests with `PYTHONPATH=src` to
avoid the MAT-021 ambient site-packages import leak.

## Artifacts

- Candidate JSON:
  `/tmp/j3-mat-028-requests-7315/final/candidate.json`
- Candidate report:
  `/tmp/j3-mat-028-requests-7315/final/report.md`
- Candidate diff:
  `/tmp/j3-mat-028-requests-7315/final/candidate.diff`
- Accepted diff:
  `/tmp/j3-mat-028-requests-7315/accepted.diff`

## Result

`requests-7315` is materialized and live-validated with exact accepted-diff
parity. This closes one more `repo_convention_builder` row from the MAT-007
panel. The remaining repo-convention rows are `click-3405` and `pytest-14429`.
