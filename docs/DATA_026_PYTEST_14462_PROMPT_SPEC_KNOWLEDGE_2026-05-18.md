# DATA-026 Pytest #14462 Prompt/Spec And Local Knowledge

Evidence-only acquisition for `pytest-dev__pytest-issue-14462-pr-14466`.
No candidate source edits were attempted.

## Artifacts

- Prompt/spec JSONL:
  `/tmp/j3-data-026-pytest-14462-evidence/spec.jsonl`
- Prompt/spec report:
  `/tmp/j3-data-026-pytest-14462-evidence/spec.md`
- Local-knowledge JSONL:
  `/tmp/j3-data-026-pytest-14462-evidence/knowledge.jsonl`

## Result

- Prompt/spec rows: `1`, status `normalized`.
- Local-knowledge rows: `6`.
- Record type counts:
  `{"library_idiom_record":3,"pytest_pattern_record":1,"repo_changed_file_context_record":1,"validation_recipe_record":1}`.
- Changed-file context covers `src/_pytest/python_api.py` and
  `testing/python/approx.py`.
- Focused validation recipe records DATA-018 setup
  `python -m pip install -e . pytest` and validation
  `pytest testing/python/approx.py -q`, with DATA-018 baseline result
  `102 passed, 18 skipped in 0.15s`.

## Semantics Captured

- `ApproxTimedelta` repo-before behavior rejects `rel=0.01` and treats
  `rel=timedelta(...)` as an absolute tolerance.
- Expected timedelta behavior is numeric relative tolerance:
  `effective_tolerance = max(abs_tolerance, rel * abs(expected))`.
- `datetime` keeps rejecting relative tolerance and requires
  `abs=timedelta(...)`.
- Acceptance test shape lives in `TestApproxDatetime` and covers within/outside
  tolerance, rel type validation, negative/NaN rel, abs+rel interaction,
  expected-value scaling, and sequence/mapping dispatch.

## Remaining Blockers

- `materialization_gap`: future work still needs a bounded source/test
  candidate for `src/_pytest/python_api.py` and `testing/python/approx.py`.
- `ranking_gap`: future work still needs candidate ranking evidence against
  plausible decoys.
