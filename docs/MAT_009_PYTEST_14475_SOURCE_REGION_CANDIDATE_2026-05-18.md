# MAT-009 Pytest #14475 Source-Region Candidate

Task: `MAT-009`

Date: 2026-05-18

## Result

MAT-009 materialized and live-validated the held-out
`pytest-dev/pytest#14475` mark-expression scanner fix using reusable action
records:

- `replace_function_region`
- `insert_pytest_function_after_anchor`

No action kind contains the repo name, issue number, or PR number. The final
candidate changed only the source/test paths:

- `src/_pytest/mark/expression.py`
- `testing/test_mark_expression.py`

The accepted PR also added `changelog/14474.bugfix.rst`, so full accepted-diff
parity is intentionally false. Source/test scoped accepted-diff parity is true.

## Validation

Focused validation passed on a fresh checkout pinned to
`7df5d80ff3a98714a1d3cdbe82941229e511f4b3`:

```bash
PYTHONPATH=src python -c "from _pytest.mark.expression import Expression; matcher=lambda name, **kwargs: name in {r'\\nfoo\\n', r'test\\case', 'mark'}; assert Expression.compile(r'\\nfoo\\n and mark(x=\"y\")').evaluate(matcher); assert Expression.compile(r'mark(x=\"y\") and \\nfoo\\n').evaluate(matcher); assert Expression.compile(r'test\\case and mark(x=\"y\")').evaluate(matcher)"
```

The run completed in `0.078s`.

## Evidence

Artifacts:

- `/tmp/j3-mat-009-pytest-14475-final/candidate.json`
- `/tmp/j3-mat-009-pytest-14475-final/report.md`
- `/tmp/j3-mat-009-pytest-14475-final/candidate.diff`
- `/tmp/j3-mat-009-pytest-14475-final/accepted.diff`

The first attempted pytest command imported `_pytest` from an older temp
checkout instead of the candidate checkout. The final validation command forces
`PYTHONPATH=src` and exercises the accepted regression directly, making the
check local to the fresh candidate checkout.
