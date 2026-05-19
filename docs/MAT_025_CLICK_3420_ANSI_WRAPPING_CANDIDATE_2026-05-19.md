# MAT-025 Click #3420 ANSI Wrapping Candidate

## Summary

- Candidate: `mat-025-click-ansi-wrapping`
- Reference PR: `https://github.com/pallets/click/pull/3420`
- Repo: `pallets/click`
- Split: held out
- Base ref: `d959898db264aaf07e70ad4eafa254286f9a5185`
- Accepted head ref: `587e3cc7f4804a4fa62f3dab8839a6e1f8954d7c`
- Accepted changed files:
  - `CHANGES.rst`
  - `src/click/_textwrap.py`
  - `src/click/formatting.py`
  - `tests/test_formatting.py`
- Candidate changed files: same as accepted.

## Action Records

The row uses reusable action kinds only:

- `replace_delimited_region` for the bounded `_textwrap.py` behavior region.
- `replace_function_region` for the bounded `wrap_text` docstring region.
- `insert_pytest_function_after_anchor` for formatter regression tests.
- `insert_text_around_anchor` for the test import and changelog entry.

No action kind is named for Click #3420 or this PR. The larger `_textwrap.py`
replacement is still bounded by explicit local markers and an import allowlist
for `from ._compat import _ansi_re` and `from ._compat import term_len`.

## Parity

- Full accepted-diff parity: `true`
- Source/test scoped parity: `true`
  - scope: `src/click/_textwrap.py`, `src/click/formatting.py`,
    `tests/test_formatting.py`
- Source/docs/test scoped parity: `true`
  - scope: all accepted files, including `CHANGES.rst`
- Candidate diff summary: 6 hunks, 214 added lines, 2 removed lines.
- Source AST metadata:
  - `src/click/_textwrap.py`: parse ok, 2 hunks, 139 added, 2 removed.
  - `src/click/formatting.py`: parse ok, signature preserved, 1 hunk,
    6 added.
- Candidate-after hashes:
  - `CHANGES.rst`:
    `d65dde5a82424bf51a993c99974c46b617ab8250b59a1e75cd730fb072724346`
  - `src/click/_textwrap.py`:
    `ed9d0ded59a7fbae933524d4c29e8e5c96dc5174666044fd87d736b9c0fca104`
  - `src/click/formatting.py`:
    `03582ed53e4aceb9e78332eaf112060ba9c305e55cc6074eb71bdce4fd499cfb`
  - `tests/test_formatting.py`:
    `b87b861620305260bb58c6f12bf06b9446ffdebe985c8295129a9049d414ba70`

## Validation

Live focused validation passed in a fresh pinned checkout with checkout-local
source:

```bash
PYTHONPATH=src python -m pytest tests/test_formatting.py::test_wrap_text_visible_width tests/test_formatting.py::test_write_usage_styled_prefix_keeps_options_on_one_line -q
```

Result: `4 passed in 0.01s`.

## Artifacts

- `/tmp/j3-mat-025-click-3420/final/candidate.json`
- `/tmp/j3-mat-025-click-3420/final/report.md`
- `/tmp/j3-mat-025-click-3420/final/candidate.diff`
- `/tmp/j3-mat-025-click-3420/final/accepted.diff`
- `/tmp/j3-mat-025-click-3420/final/accepted-files.txt`

## Blockers

None. Target selection, source-region materialization, pytest insertion/import
refinement, accepted-diff parity, and live validation all succeeded.
