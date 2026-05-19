# MAT-035 Flask #5898 Redirect Default Candidate

## Scope

- Task: `MAT-035`
- PR: `pallets/flask#5898`
- PR API: `https://api.github.com/repos/pallets/flask/pulls/5898`
- Diff URL: `https://github.com/pallets/flask/pull/5898.diff`
- Base ref: `eb58d862cc4a8f31a369b6e9ad1724e9e642f13f`
- Accepted head ref: `eca5fd1dfdc614c2df876cc32018a7d71f84ea82`
- `git ls-remote` PR head: `eca5fd1dfdc614c2df876cc32018a7d71f84ea82`
- Accepted changed files: `CHANGES.rst`, `docs/api.rst`,
  `src/flask/helpers.py`, `src/flask/sansio/app.py`

## Reusable Actions

- `replace_function_region`: update the `flask.redirect` default status-code
  literal from `302` to `303`.
- `replace_function_region`: update the `Flask.redirect` default status-code
  literal from `302` to `303`.
- `insert_text_around_anchor`: insert the accepted changelog entry.
- `insert_text_around_anchor`: insert the accepted `flask.redirect`
  `versionchanged` note.
- `insert_text_around_anchor`: insert the accepted `Flask.redirect`
  `versionchanged` note.
- `replace_text_span`: update the existing API docs route-default redirect
  status text from `301` to `308`.

The action names are generic and contain no repo, issue, PR, or task-specific
identifier.

## Candidate Result

- Artifact directory: `/tmp/j3-mat-035-flask-5898-live/final`
- Candidate JSON:
  `/tmp/j3-mat-035-flask-5898-live/final/candidate.json`
- Candidate report:
  `/tmp/j3-mat-035-flask-5898-live/final/report.md`
- Candidate diff:
  `/tmp/j3-mat-035-flask-5898-live/final/candidate.diff`
- Status: `validated`
- Residual labels: `candidate_validation_passed`
- Mutation scope: `CHANGES.rst`, `docs/api.rst`, `src/flask/helpers.py`,
  `src/flask/sansio/app.py`
- Writes outside allowlist: none
- Candidate diff summary: `+14/-3`, 6 hunks, 4 files

## Accepted-Diff Comparison

- Full accepted-diff parity: `true`
- Source-only scoped parity: `true`
- Source/docs scoped parity: `true`
- Changed-file parity: `true`

The normalized accepted diff and normalized candidate diff are identical.

## Live Validation

Command:

```bash
PYTHONPATH=src python -c "from flask import Flask, redirect; app = Flask(__name__); ctx = app.app_context(); ctx.push(); assert redirect('/target').status_code == 303; assert app.redirect('/target').status_code == 303; assert redirect('/target', 302).status_code == 302; ctx.pop()"
```

Result: passed, return code `0`, runtime `0.091` seconds.
