# MAT-033 Flask Autoescape Candidate Evidence

## Target

- Task: `MAT-033`
- Row: `flask-6013`
- Repo: `pallets/flask`
- PR: <https://github.com/pallets/flask/pull/6013>
- PR state: merged on 2026-05-02
- Base branch/ref from PR evidence: `main` at
  `06ea505ce2b2042af26e96d35ebf159af7c0869d`
- Accepted head ref from PR evidence:
  `9368fb3f3c52d74534d14c1bef03c79c103356cd`
- Accepted changed files: `CHANGES.rst`, `src/flask/sansio/app.py`

## Candidate

The candidate uses reusable action records only:

- `replace_function_region`: replaces the single
  `select_jinja_autoescape` suffix-check return expression with
  `filename.lower().endswith(...)`.
- `insert_text_around_anchor`: inserts the accepted changelog entry.
- `insert_text_around_anchor`: inserts the accepted `versionchanged` note in
  the method docstring.

No action kind includes a repo, PR, issue, or MAT task identifier.

## Live Artifact

- Checkout: `/tmp/j3-mat-033-flask-6013-live/repo`
- Accepted diff:
  `/tmp/j3-mat-033-flask-6013-live/accepted.diff`
- Candidate JSON:
  `/tmp/j3-mat-033-flask-6013-live/final/candidate.json`
- Candidate report:
  `/tmp/j3-mat-033-flask-6013-live/final/report.md`
- Candidate diff:
  `/tmp/j3-mat-033-flask-6013-live/final/candidate.diff`

Mutation scope:

- Allowed write paths: `CHANGES.rst`, `src/flask/sansio/app.py`
- Actual changed files: `CHANGES.rst`, `src/flask/sansio/app.py`
- Writes outside allowlist: none

Accepted-diff comparison:

- Full accepted-diff parity: true
- Source-only scoped parity for `src/flask/sansio/app.py`: true
- Source/docs scoped parity for `CHANGES.rst` and
  `src/flask/sansio/app.py`: true

Validation:

```bash
PYTHONPATH=src python -c "from flask import Flask; app = Flask(__name__); assert app.select_jinja_autoescape('INDEX.HTML'); assert app.select_jinja_autoescape('template.SVG'); assert not app.select_jinja_autoescape('readme.TXT')"
```

Result: passed.

## Result

`pallets/flask#6013` materializes and live-validates with exact full
accepted-diff parity. Remaining non-materialized MAT-007 counts are now
`current_structured_action = 2`, `general_typed_builder = 0`,
`repo_convention_builder = 0`, `constrained_local_generator = 0`, and
`not_currently_expressible = 2`.
