# MAT-008 Requests #7427 Source-Region Candidate

Task: `MAT-008`

Date: 2026-05-18

## Result

MAT-008 materialized and live-validated the held-out `psf/requests#7427`
domain-boundary fix using reusable action records:

- `replace_function_region`
- `insert_pytest_function_after_anchor`

No action kind contains the repo name, issue number, or PR number. The
candidate changed only the accepted source/test paths:

- `src/requests/utils.py`
- `tests/test_utils.py`

## Validation

Focused validation passed:

```bash
python -m pytest tests/test_utils.py::test_should_bypass_proxies_no_proxy_domain_boundary -q
```

The run completed in `0.383s` on the final fresh checkout.

## Evidence

The final candidate matched the accepted PR diff after normalizing Git hunk
context labels, changed exactly the two accepted files, and recorded
candidate-after diff/AST metadata plus mutation scope.

Artifacts:

- `/tmp/j3-mat-008-requests-7427-final/candidate.json`
- `/tmp/j3-mat-008-requests-7427-final/report.md`
- `/tmp/j3-mat-008-requests-7427-final/candidate.diff`
- `/tmp/j3-mat-008-requests-7427-final/accepted.diff`
