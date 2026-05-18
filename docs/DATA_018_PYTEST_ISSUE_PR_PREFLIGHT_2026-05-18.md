# DATA-018 Pytest Issue/PR Replay Preflight

Pre-edit replay preflight only; no candidate source edits were attempted.

## Summary

- Manifest: `examples/issue_pr_mini_replay/manifest.json`
- Batch:
  `pytest-dev__pytest-issue-14442-pr-14443`,
  `pytest-dev__pytest-issue-14462-pr-14466`,
  `pytest-dev__pytest-issue-14381-pr-14382`
- JSONL: `/tmp/j3-data-018-pytest-preflight/outcomes.jsonl`
- Generated report: `/tmp/j3-data-018-pytest-preflight/report.md`
- Runtime: `24.382` seconds
- Status counts: `{"blocked":3}`
- First failed stages: `{"none":3}`
- Command output classification: checkout, setup, and baseline validation all
  passed; remaining blockers are pre-edit prompt/spec and local-knowledge gaps,
  not edit quality.

## Command

```bash
rm -rf /tmp/j3-data-018-pytest-preflight
mkdir -p /tmp/j3-data-018-pytest-preflight
python -m venv /tmp/j3-data-018-pytest-preflight/.venv
PATH=/tmp/j3-data-018-pytest-preflight/.venv/bin:$PATH \
PYTHONPATH=/Users/aa/os/j3 \
  python -m j3.issue_pr_preflight \
  --manifest examples/issue_pr_mini_replay/manifest.json \
  --workspace /tmp/j3-data-018-pytest-preflight/repos \
  --outcome /tmp/j3-data-018-pytest-preflight/outcomes.jsonl \
  --report /tmp/j3-data-018-pytest-preflight/report.md \
  --replay-id pytest-dev__pytest-issue-14442-pr-14443 \
  --replay-id pytest-dev__pytest-issue-14462-pr-14466 \
  --replay-id pytest-dev__pytest-issue-14381-pr-14382 \
  --setup-command "python -m pip install -e . pytest" \
  --timeout-seconds 600
```

## Rows

| Replay | Checkout | Setup | Baseline validation | Runtime | First failed stage | Blocking class |
| --- | --- | --- | --- | ---: | --- | --- |
| `pytest-dev__pytest-issue-14442-pr-14443` | passed | passed | `353 passed, 2 xfailed in 3.29s` | `12.979` | `none` | `local_knowledge_missing` |
| `pytest-dev__pytest-issue-14462-pr-14466` | passed | passed | `102 passed, 18 skipped in 0.15s` | `5.473` | `none` | `local_knowledge_missing` |
| `pytest-dev__pytest-issue-14381-pr-14382` | passed | passed | `12 passed in 0.31s` | `5.928` | `none` | `prompt_spec_incomplete` |

## Residuals

### `pytest-dev__pytest-issue-14442-pr-14443`

- Prompt/spec gaps: manifest labels `prompt_spec_parsing_gap`; normalize the
  strict `addopts` reproduction, observed silent strict-option failure,
  expected strict marker/config behavior, affected config option parsing
  surface, input shape, and focused acceptance tests in `testing/test_config.py`
  / `testing/test_mark.py`.
- Required local knowledge: pytest changed-file context, test patterns,
  focused validation recipe, addopts option parsing order, strict marker and
  strict config semantics, changelog fragment convention, and AUTHORS update
  convention.
- Materialization/ranking residuals: ranking gap remains. The accepted edit also
  includes `AUTHORS` and `changelog/14442.bugfix.rst`, so a full accepted-edit
  attempt would need auxiliary-path materialization or an explicit focused
  source/test-only scope.

### `pytest-dev__pytest-issue-14462-pr-14466`

- Prompt/spec gaps: no manifest `prompt_spec_parsing_gap`, but candidate work
  still needs a normalized spec for timedelta `approx`, observed `rel` treated
  as absolute tolerance, expected relative tolerance from the expected value,
  affected `src/_pytest/python_api.py` surface, and acceptance coverage in
  `testing/python/approx.py`.
- Required local knowledge: pytest changed-file context, test patterns,
  focused validation recipe, `ApproxTimedelta` tolerance semantics, float
  relative tolerance handling, datetime/timedelta comparison behavior, and
  skip patterns in `testing/python/approx.py`.
- Materialization/ranking residuals: manifest labels `materialization_gap` and
  `ranking_gap`; source/test paths are only
  `src/_pytest/python_api.py` and `testing/python/approx.py`.

### `pytest-dev__pytest-issue-14381-pr-14382`

- Prompt/spec gaps: manifest labels `prompt_spec_parsing_gap`; normalize the
  short `-V` CLI reproduction, observed missing version output, expected
  version display behavior, affected `src/_pytest/config/__init__.py` option
  registration/handling surface, input shape, and acceptance coverage in
  `testing/test_helpconfig.py`.
- Required local knowledge: pytest changed-file context, test patterns,
  focused validation recipe, help/version option handling, CLI invocation tests
  in `testing/test_helpconfig.py`, and changelog fragment convention.
- Materialization/ranking residuals: manifest labels `materialization_gap` and
  `validation_gap`. Baseline validation passed in this preflight, so the
  validation gap is now a recipe/provenance normalization concern rather than a
  setup or baseline blocker.

## Recommendation

No pytest row is ready for a candidate attempt yet because none has normalized
prompt/spec plus local-knowledge evidence. The first row ready for the next
normalization step is `pytest-dev__pytest-issue-14442-pr-14443`: checkout,
setup, and baseline validation passed, and it is first in the batch order.
Normalize its strict `addopts` prompt/spec and acquire pytest local-knowledge
records before any candidate generation.
