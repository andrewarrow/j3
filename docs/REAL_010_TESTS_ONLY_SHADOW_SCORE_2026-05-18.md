# REAL-010 Tests-Only Shadow Score

`REAL-010` reran the tests-only shadow scorer after `GS7-011`, counting all
four materialized tests-only ladder rows through the real-repo tests planner and
live candidate validation path.

## Artifacts

- `/tmp/j3-real-010-shadow-score-live/preflight.jsonl`
- `/tmp/j3-real-010-shadow-score-live/score.json`
- `/tmp/j3-real-010-shadow-score-live/report.md`

## Commands

```bash
python -m j3.real_repo_preflight --manifest examples/real_repo_eval_ladder.json --repo iniconfig --repo h11 --repo humanize --repo boltons --work-root /tmp/j3-real-010-shadow-score-live/repos --outcome /tmp/j3-real-010-shadow-score-live/preflight.jsonl
python -m j3.real_repo_shadow_score --manifest examples/real_repo_eval_ladder.json --repo-path iniconfig=/tmp/j3-real-010-shadow-score-live/repos/iniconfig --repo-path h11=/tmp/j3-real-010-shadow-score-live/repos/h11 --repo-path humanize=/tmp/j3-real-010-shadow-score-live/repos/humanize --repo-path boltons=/tmp/j3-real-010-shadow-score-live/repos/boltons --validate-candidates --out /tmp/j3-real-010-shadow-score-live/score.json --report /tmp/j3-real-010-shadow-score-live/report.md
```

## Result

| Metric | Value |
| --- | --- |
| Tasks scored | `4` |
| Candidate count | `4` |
| Candidates tested | `4` |
| Calibration pass@3 | `1/1` |
| Held-out pass@3 | `3/3` |
| pass@1 | `4/4` |
| pass@3 | `4/4` |
| First passing ranks | `[1, 1, 1, 1]` |
| Candidate validation statuses | `passed = 4`, all other statuses `0` |
| Production-file modifications | `0` |
| Writes outside allowlist | `0` |
| Candidate target path violations | `0` |
| Hidden-like agreement | `agreeing = 4`, `disagreeing = 0`, `not_run = 0` |
| Zero hosted usage | `true` |

Guarded tests-only opt-in remains allowed. The exact allowed task ids are:

- `iniconfig-tests-parse-comments`
- `h11-tests-bytesify-memoryview`
- `humanize-tests-naturalsize-negative-strings`
- `boltons-tests-slugify-delimiter`
