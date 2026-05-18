# MAT-003 h11 Feature Materialization Probe

## Result

`MAT-003` materialized the pinned
`h11-feature-bytesify-object-message` one-file feature candidate.

- Candidate id: `feature-feb53105560c596a`
- Live checkout: `/tmp/j3-mat-003-live/h11`
- Candidate record: `/tmp/j3-mat-003-live/candidate.json`
- Production file changed: `h11/_util.py`
- Test file changed: `h11/tests/test_util.py`
- Writes outside allowlist: none
- Zero hosted usage: confirmed

## Source Edit

The candidate uses one bounded `replace_function_region` action in
`bytesify`, replacing the final `return bytes(s)` with a `try`/`except
TypeError` block. Unsupported objects now raise:

```text
expected bytes-like object, not <ConcreteTypeName>
```

Existing behavior for `bytes`, `bytearray`, `memoryview`, ASCII `str`,
non-ASCII `str`, and `int` is preserved by the focused validation.

## Metadata

- Source diff summary: 1 hunk, 6 added lines, 1 removed line, 7 changed lines.
- Source AST parse: passed.
- Function signature preservation: passed.
- Import changes: none.
- Test diff summary: 1 hunk, 10 added lines, 0 removed lines.
- Test AST parse: passed.
- One-production-file constraint: preserved.

## Validation

Setup succeeded with:

```bash
python -m pip install -e /tmp/j3-mat-003-live/h11 -r /tmp/j3-mat-003-live/h11/test-requirements.txt
```

Candidate materialization and validation:

```bash
python -m j3.real_repo_feature_materializer --repo-path /tmp/j3-mat-003-live/h11 --validate --out /tmp/j3-mat-003-live/candidate.json
python -m pytest h11/tests/test_util.py -q
```

Result: `7 passed in 0.01s`; materializer-recorded validation runtime was
`0.14` seconds.

## Blockers

None for this probe. The current source-region materializer can express this
h11 edit because the change is a single bounded region inside one function.
