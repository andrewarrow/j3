# MAT-016 Flask #5903 Filesystem-Idiom Candidate

## Scope

- Repo: `pallets/flask`
- Reference PR: `https://github.com/pallets/flask/pull/5903`
- Base ref: `407eb76b27884848383a37c7274654f0271e4bc4`
- Accepted head ref: `3d03098a97ddc6a908aa4a50c2ef7381f8297d0a`
- Candidate id: `mat-016-flask-instance-folder-exist-ok`

## Result

The candidate is covered by a reusable filesystem idiom action, not by
`statement_block_replace`.

- Action kinds: `makedirs_exist_ok_rewrite`, `makedirs_exist_ok_rewrite`
- `statement_block_replace`: not used
- Changed files: `docs/tutorial/factory.rst`,
  `examples/tutorial/flaskr/__init__.py`
- Accepted changed files: `docs/tutorial/factory.rst`,
  `examples/tutorial/flaskr/__init__.py`
- Writes outside allowlist: none
- Accepted diff normalized match: true
- Candidate diff summary: 2 added lines, 8 removed lines
- Python AST parse: true for `examples/tutorial/flaskr/__init__.py`
- Docs AST parse: false for `docs/tutorial/factory.rst`, expected because it is
  RST with an indented Python tutorial example
- Validation: `python -m py_compile examples/tutorial/flaskr/__init__.py`
  passed in `0.021s`

## Materialized Diff

Both accepted edits replace the same swallowed filesystem exception idiom:

```diff
-    try:
-        os.makedirs(app.instance_path)
-    except OSError:
-        pass
+    os.makedirs(app.instance_path, exist_ok=True)
```

The reusable action is parameterized by target file, optional function/class
scope, module name, path expression, and exception type. For Python files it
matches an AST `try` node whose body is a single `os.makedirs` call and whose
single handler is `except OSError: pass`. For the tutorial RST file it matches
the same indented code-example shape exactly once.

## Artifacts

- `/tmp/j3-mat-016-flask-5903-final/candidate.json`
- `/tmp/j3-mat-016-flask-5903-final/report.md`
- `/tmp/j3-mat-016-flask-5903-final/candidate.diff`
- `/tmp/j3-mat-016-flask-5903-final/accepted.diff`
