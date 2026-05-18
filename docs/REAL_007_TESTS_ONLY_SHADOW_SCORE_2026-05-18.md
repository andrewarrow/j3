# REAL-007 Tests-Only Shadow Score

Date: 2026-05-18

## Result

`REAL-007` reran the tests-only shadow scorer after `GS7-009`, counting both
the calibration `iniconfig-tests-parse-comments` candidate and the first
held-out `h11-tests-bytesify-memoryview` candidate through the real-repo tests
planner surface.

- Live artifacts: `/tmp/j3-real-007-shadow-score`
- Preflight JSONL: `/tmp/j3-real-007-shadow-score/preflight.jsonl`
- Score JSON: `/tmp/j3-real-007-shadow-score/score.json`
- Report: `/tmp/j3-real-007-shadow-score/report.md`
- Zero hosted usage: confirmed

## Live Smoke

Command:

```bash
PATH=/tmp/j3-real-007-shadow-score/.venv/bin:$PATH python -m j3.real_repo_preflight --manifest examples/real_repo_eval_ladder.json --repo iniconfig --repo h11 --work-root /tmp/j3-real-007-shadow-score/repos --outcome /tmp/j3-real-007-shadow-score/preflight.jsonl
```

Result: passed with 4 rows, `blocker_labels = ["none"]`, repositories
`["h11", "iniconfig"]`, runtime 5.120 seconds.

Command:

```bash
PATH=/tmp/j3-real-007-shadow-score/.venv/bin:$PATH python -m j3.real_repo_shadow_score --manifest examples/real_repo_eval_ladder.json --repo-path iniconfig=/tmp/j3-real-007-shadow-score/repos/iniconfig --repo-path h11=/tmp/j3-real-007-shadow-score/repos/h11 --validate-candidates --out /tmp/j3-real-007-shadow-score/score.json --report /tmp/j3-real-007-shadow-score/report.md
```

Result: passed with `pass@1 = 2/4`, `pass@3 = 2/4`,
`candidate_count = 2`, `candidates_tested = 2`, and
`gate_decision = remain_shadow_only`.

## Metrics

- Calibration pass@3: `1/1`
- Held-out pass@3: `1/3`
- Total pass@1: `2/4`
- Total pass@3: `2/4`
- First passing ranks: `[1, 1, null, null]`
- Candidate validation statuses: `passed = 2`, `blocked = 2`
- Production-file modifications: `0`
- Writes outside allowlist: `0`
- Candidate target path violations: `0`
- Hidden-like agreement: `2 agreeing`, `0 disagreeing`, `2 not run`

## Task Rows

| Task | Split | Candidate validation | pass@3 | First passing rank | Mutation scope | Hidden-like |
| --- | --- | --- | --- | --- | --- | --- |
| `iniconfig-tests-parse-comments` | calibration | passed | true | 1 | `testing/test_iniconfig.py`; 0 production changes; 0 outside allowlist | agrees |
| `h11-tests-bytesify-memoryview` | heldout | passed | true | 1 | `h11/tests/test_util.py`; 0 production changes; 0 outside allowlist | agrees |
| `humanize-tests-naturalsize-negative-strings` | heldout | blocked: `test_case_materialization_gap` | false | none | no files changed | not run |
| `boltons-tests-slugify-delimiter` | heldout | blocked: `test_case_materialization_gap` | false | none | no files changed | not run |

## Gate Decision

The tests-only product gate remains `remain_shadow_only`: total `pass@3` is
`2/4`, below the `3/4` threshold. `humanize` and `boltons` remain explicit
materialization blockers, not omitted rows.
