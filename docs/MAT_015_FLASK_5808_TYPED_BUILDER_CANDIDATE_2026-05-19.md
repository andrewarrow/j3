# MAT-015 Flask #5808 Typed-Builder Candidate

## Scope

- Repo: `pallets/flask`
- Reference PR: `https://github.com/pallets/flask/pull/5808`
- Base ref: `85793d6c223dd845e8f218403a5ced83041d37e1`
- Accepted head ref: `dbd4c2882593f6118103120aa96fa9acdf7deedb`
- Candidate id: `mat-015-flask-jinja-autoescape-filename-typing`

## Result

The candidate stays in the pure typed-builder layer.

- Action kinds: `function_signature_update`
- `statement_block_replace`: not used
- Changed files: `src/flask/sansio/app.py`
- Accepted changed files: `src/flask/sansio/app.py`
- Writes outside allowlist: none
- Accepted diff normalized match: true
- Candidate AST parse: true
- Candidate diff summary: 1 added line, 1 removed line
- Validation: `python -m py_compile src/flask/sansio/app.py` passed in `0.022s`

## Materialized Diff

The candidate changes `App.select_jinja_autoescape` so the `filename`
parameter annotation accepts `None`:

```diff
-    def select_jinja_autoescape(self, filename: str) -> bool:
+    def select_jinja_autoescape(self, filename: str | None) -> bool:
```

This is represented by reusable `function_signature_update` parameters:
target file, class name, function name, and parameter annotation. No PR-named
action kind or source-block replacement was needed.

## Artifacts

- `/tmp/j3-mat-015-flask-5808-final/candidate.json`
- `/tmp/j3-mat-015-flask-5808-final/report.md`
- `/tmp/j3-mat-015-flask-5808-final/candidate.diff`
- `/tmp/j3-mat-015-flask-5808-final/accepted.diff`
