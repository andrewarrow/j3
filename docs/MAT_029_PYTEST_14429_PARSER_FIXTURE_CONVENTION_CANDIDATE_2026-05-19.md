# MAT-029 Pytest #14429 Parser-Fixture Convention Candidate

Task: `MAT-029`

Date: 2026-05-19

## Result

MAT-029 materialized and live-validated `pytest-dev/pytest#14429` with
reusable repo-convention and bounded source/test action records:

- `replace_exact_source_lines_after_anchor`
- `insert_pytest_function_after_anchor`

No action kind contains the repository name, issue number, or PR number.

Pinned refs:

- Base: `8f81c76744daf72d4f77cfc8423f4bdc60733d78`
- Accepted head: `641a97b7695430f9fc4e9113b31d797447dc9654`

The candidate changed only:

- `src/_pytest/config/argparsing.py`
- `testing/test_parseopt.py`

The accepted PR also adds `changelog/13817.bugfix.rst`, so full
accepted-diff parity is intentionally false. Source/test scoped parity and
repo-convention scoped parity are true.

## Validation

Focused validation passed on the pinned candidate checkout:

```bash
trap 'rm -f src/_pytest/_version.py' EXIT; printf '%s\n' 'version = "99.0.0"' 'version_tuple = (99, 0, 0)' > src/_pytest/_version.py; PYTHONPATH=src python -m pytest testing/test_parseopt.py::test_argument_repr_uninitialized testing/test_parseopt.py::test_argument_repr_initialized -q
```

Result: `2 passed in 0.02s`.

The temporary `_pytest._version` file is a validation-harness shim for this
checkout's setuptools-scm generated metadata and is removed by the command's
trap. It is not part of the candidate mutation scope.

## Evidence

Artifacts:

- `/tmp/j3-mat-029-pytest-14429/accepted.diff`
- `/tmp/j3-mat-029-pytest-14429/final/candidate.json`
- `/tmp/j3-mat-029-pytest-14429/final/candidate.diff`
- `/tmp/j3-mat-029-pytest-14429/final/report.md`
- `/tmp/j3-mat-029-pytest-14429/final/candidate.formatted.json`

Candidate metadata records accepted changed files, candidate-after diff/hash
metadata, actual mutation scope, accepted-diff comparison, validation result,
and `zero_hosted_llm_source_judgment = true`.
