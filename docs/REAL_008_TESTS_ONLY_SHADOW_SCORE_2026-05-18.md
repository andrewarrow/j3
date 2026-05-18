# REAL-008 Tests-Only Shadow Score

Date: 2026-05-18

## Result

`REAL-008` reran the tests-only shadow scorer after `GS7-010`, counting the
materialized `iniconfig`, `h11`, and `humanize` candidates through the
real-repo tests planner surface.

- Live artifacts: `/tmp/j3-real-008-shadow-score-live`
- Preflight JSONL: `/tmp/j3-real-008-shadow-score-live/preflight.jsonl`
- Score JSON: `/tmp/j3-real-008-shadow-score-live/score.json`
- Report: `/tmp/j3-real-008-shadow-score-live/report.md`
- Zero hosted usage: confirmed

## Live Smoke

Command:

```bash
python -m j3.real_repo_preflight --manifest examples/real_repo_eval_ladder.json --repo iniconfig --repo h11 --repo humanize --work-root /tmp/j3-real-008-shadow-score-live/repos --outcome /tmp/j3-real-008-shadow-score-live/preflight.jsonl
```

Result: passed with 6 rows, `blocker_labels = ["none"]`, repositories
`["h11", "humanize", "iniconfig"]`, runtime 7.774 seconds.

Command:

```bash
python -m j3.real_repo_shadow_score --manifest examples/real_repo_eval_ladder.json --repo-path iniconfig=/tmp/j3-real-008-shadow-score-live/repos/iniconfig --repo-path h11=/tmp/j3-real-008-shadow-score-live/repos/h11 --repo-path humanize=/tmp/j3-real-008-shadow-score-live/repos/humanize --validate-candidates --out /tmp/j3-real-008-shadow-score-live/score.json --report /tmp/j3-real-008-shadow-score-live/report.md
```

Result: passed with `pass@1 = 3/4`, `pass@3 = 3/4`,
`candidate_count = 3`, `candidates_tested = 3`, and
`gate_decision = allow_guarded_tests_only_opt_in`.

## Metrics

- Calibration pass@3: `1/1`
- Held-out pass@3: `2/3`
- Total pass@1: `3/4`
- Total pass@3: `3/4`
- First passing ranks: `[1, 1, 1, null]`
- Candidate validation statuses: `passed = 3`, `blocked = 1`
- Production-file modifications: `0`
- Writes outside allowlist: `0`
- Candidate target path violations: `0`
- Hidden-like agreement: `3 agreeing`, `0 disagreeing`, `1 not run`

## Task Rows

| Task | Split | Candidate validation | pass@3 | First passing rank | Mutation scope | Hidden-like |
| --- | --- | --- | --- | --- | --- | --- |
| `iniconfig-tests-parse-comments` | calibration | passed | true | 1 | `testing/test_iniconfig.py`; 0 production changes; 0 outside allowlist | agrees |
| `h11-tests-bytesify-memoryview` | heldout | passed | true | 1 | `h11/tests/test_util.py`; 0 production changes; 0 outside allowlist | agrees |
| `humanize-tests-naturalsize-negative-strings` | heldout | passed | true | 1 | `tests/test_filesize.py`; 0 production changes; 0 outside allowlist | agrees |
| `boltons-tests-slugify-delimiter` | heldout | blocked: `test_case_materialization_gap` | false | none | no files changed | not run |

## Gate Decision

The manifest tests-only gate passes at `pass@3 = 3/4` against the `3/4`
threshold. Guarded tests-only opt-in is allowed only for materialized,
validation-passing tests-only candidates that write task-allowlisted test files,
preserve production files byte-for-byte, have no writes outside allowlists, and
have no hidden-like disagreement. The UI/CLI must show the planned action,
changed paths, validation command, and rollback path before applying.

`boltons-tests-slugify-delimiter` remains blocked on
`test_case_materialization_gap` and is not inside the guarded opt-in scope until
`GS7-011` produces and validates a materializer.
