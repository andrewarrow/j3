# MAT-034 Pytest #14472 Array-Interface Candidate

## PR Evidence

- Repository: `pytest-dev/pytest`
- PR: `https://github.com/pytest-dev/pytest/pull/14472`
- GitHub PR API base ref: `7df5d80ff3a98714a1d3cdbe82941229e511f4b3`
- GitHub PR API head ref: `8bae589cfba6aa7f17e621e5d89b05004303b0b8`
- `git ls-remote` PR head: `8bae589cfba6aa7f17e621e5d89b05004303b0b8`
- Accepted changed files:
  - `AUTHORS`
  - `changelog/14456.bugfix.rst`
  - `src/_pytest/python_api.py`

## Candidate

- Candidate id: `mat-034-pytest-array-interface-receiver`
- Mutation scope: `AUTHORS`, `changelog/14456.bugfix.rst`,
  `src/_pytest/python_api.py`
- Reusable action kinds:
  - `replace_function_region`
  - `insert_text_around_anchor`
  - `create_text_file`
- Source edit: replace
  `hasattr("obj", "__array_interface__")` with
  `hasattr(obj, "__array_interface__")` in `_as_numpy_array`.
- Full accepted-diff parity: true.
- Source-only scoped parity: true.
- Source/docs scoped parity: true.

## Validation

- Command:
  `PYTHONPATH=src python -c "import numpy as np; from _pytest.python_api import _as_numpy_array; base = np.array([1.0, 2.0]); obj = type('ArrayInterfaceOnly', (), {'__array_interface__': base.__array_interface__})(); arr = _as_numpy_array(obj); assert arr is not None; assert arr.tolist() == [1.0, 2.0]"`
- Result: passed.
- Candidate status: `validated`.

## Artifacts

- Candidate JSON:
  `/tmp/j3-mat-034-pytest-14472-live/final/candidate.json`
- Candidate report:
  `/tmp/j3-mat-034-pytest-14472-live/final/report.md`
- Candidate diff:
  `/tmp/j3-mat-034-pytest-14472-live/final/candidate.diff`
- Accepted diff:
  `/tmp/j3-mat-034-pytest-14472-live/accepted.diff`
