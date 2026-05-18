# DATA-021 Pytest Strict Addopts Evidence

Prompt/spec and local-knowledge evidence only; no candidate source edits were
attempted.

## Summary

- Replay: `pytest-dev__pytest-issue-14442-pr-14443`
- Repo-before ref: `8f81c76744daf72d4f77cfc8423f4bdc60733d78`
- Accepted merge ref: `a481f264d70ac3d053d5f7408f4ac1ec439d0c2f`
- Prompt/spec JSONL: `/tmp/j3-data-021-pytest-14442-spec.jsonl`
- Prompt/spec report: `/tmp/j3-data-021-pytest-14442-spec.md`
- Local-knowledge JSONL: `/tmp/j3-data-021-pytest-14442-knowledge.jsonl`

## Evidence

The prompt/spec row is `normalized` and covers the minimal reproduction,
observed behavior, expected behavior, affected API/surface, input shape, and
acceptance test shape for `--strict-markers` and `--strict-config` supplied via
`addopts`.

The local-knowledge JSONL emits seven records:

- `repo_changed_file_context`
- `focused_validation_recipe`
- `pytest_strict_addopts_behavior`
- `pytest_strict_markers_config_semantics`
- `pytest_repo_test_patterns`
- `pytest_changelog_fragment_convention`
- `pytest_authors_convention`

The changed-file context covers `AUTHORS`, `changelog/14442.bugfix.rst`,
`src/_pytest/config/__init__.py`, `testing/test_config.py`, and
`testing/test_mark.py`.

## Validation Recipe

DATA-018 already proved checkout, setup, and baseline validation for this row:

```bash
python -m pip install -e . pytest
pytest testing/test_config.py testing/test_mark.py -q
```

The baseline result was `353 passed, 2 xfailed in 3.29s`.

## Remaining Blockers

This task intentionally did not attempt candidate edits. The remaining readiness
blockers are candidate-readiness refresh, ranking evidence, and a decision on
whether a future attempt is source/test-only or includes auxiliary
materializers for `AUTHORS` and `changelog/14442.bugfix.rst`.
