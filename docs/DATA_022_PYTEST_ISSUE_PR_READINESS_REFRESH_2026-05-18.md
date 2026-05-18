# DATA-022 Pytest #14442 Readiness Refresh

Readiness scoring only; no candidate source edits were attempted.

## Summary

- Replay: `pytest-dev__pytest-issue-14442-pr-14443`
- JSONL: `/tmp/j3-data-022-readiness-refresh/readiness.jsonl`
- Generated report: `/tmp/j3-data-022-readiness-refresh/report.md`
- Status counts: `{"ready":1}`
- Missing evidence: `{}`
- Evidence counts: `{"prompt_spec":1,"validation":1,"local_knowledge":7}`

The row is `ready_for_candidate_attempt`: DATA-018 proves checkout, setup, and
baseline validation; DATA-021 supplies normalized prompt/spec evidence and all
seven required pytest local-knowledge categories.

## Row

| Replay | Ready | Missing evidence | Validation command | Recommendation |
| --- | --- | --- | --- | --- |
| `pytest-dev__pytest-issue-14442-pr-14443` | `true` | `none` | `pytest testing/test_config.py testing/test_mark.py -q` | `ready_for_candidate_attempt; next_stage_challenge=materialization_gap,ranking_gap` |

## Scope

- Source/test candidate scope:
  `src/_pytest/config/__init__.py`, `testing/test_config.py`,
  `testing/test_mark.py`
- Full accepted-edit scope also includes auxiliary paths:
  `AUTHORS`, `changelog/14442.bugfix.rst`

A future source/test-only candidate may proceed only as an explicit scoped
attempt. Full accepted-edit parity still requires auxiliary materializers or an
explicit decision to exclude the AUTHORS and changelog paths.

## Remaining Next-Stage Challenges

- `materialization_gap`: materialize the accepted source/test edit paths, and
  decide whether to include or explicitly exclude the auxiliary `AUTHORS` and
  `changelog/14442.bugfix.rst` paths.
- `ranking_gap`: rank the candidate action sequence against decoys using
  repo-state, prompt/spec, validation, and local-knowledge evidence before any
  guarded use.

## Evidence

- Prompt/spec:
  `/tmp/j3-data-021-pytest-14442-spec.jsonl`
- Validation:
  `/tmp/j3-data-018-pytest-preflight/outcomes.jsonl`
- Local knowledge:
  `/tmp/j3-data-021-pytest-14442-knowledge.jsonl`
