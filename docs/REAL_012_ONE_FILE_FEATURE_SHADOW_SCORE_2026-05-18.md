# REAL-012 One-File Feature Shadow Score

REAL-012 reran the full one-file feature gate after `MAT-006` added
`boltons-feature-slugify-max-length`. This score counts all four ladder
candidates through `j3.real_repo_feature_materializer`.

## Live Run

```bash
python -m j3.real_repo_preflight --manifest examples/real_repo_eval_ladder.json --repo iniconfig --repo h11 --repo humanize --repo boltons --work-root /tmp/j3-real-012-feature-shadow-score-live/repos --outcome /tmp/j3-real-012-feature-shadow-score-live/preflight.jsonl

python -m j3.real_repo_feature_shadow_score --manifest examples/real_repo_eval_ladder.json --repo-path iniconfig=/tmp/j3-real-012-feature-shadow-score-live/repos/iniconfig --repo-path h11=/tmp/j3-real-012-feature-shadow-score-live/repos/h11 --repo-path humanize=/tmp/j3-real-012-feature-shadow-score-live/repos/humanize --repo-path boltons=/tmp/j3-real-012-feature-shadow-score-live/repos/boltons --validate-candidates --out /tmp/j3-real-012-feature-shadow-score-live/score.json --report /tmp/j3-real-012-feature-shadow-score-live/report.md
```

Artifacts:

- `/tmp/j3-real-012-feature-shadow-score-live/preflight.jsonl`
- `/tmp/j3-real-012-feature-shadow-score-live/score.json`
- `/tmp/j3-real-012-feature-shadow-score-live/report.md`

## Result

- `pass@1`: `4/4`
- `pass@3`: `4/4`
- Calibration pass@3: `1/1`
- Held-out pass@3: `3/3`
- Distinct repos passing: `4` (`boltons`, `h11`, `humanize`, `iniconfig`)
- Candidate validation statuses: `passed = 4`, `blocked = 0`, `failed = 0`
- First passing ranks: `[1, 1, 1, 1]`
- Production-file constraint violations: `0`
- Writes outside allowlist: `0`
- Mutation-scope violations: `0`
- Hidden-like agreement: `4` agreeing, `0` disagreeing, `0` not run
- Hosted usage: `0`
- Blocked rows: none

## Gate Decision

The manifest one-file feature gate passes:
`allow_guarded_one_file_feature_opt_in`.

Guarded opt-in is limited to:

- `iniconfig-feature-section-default`
- `h11-feature-bytesify-object-message`
- `humanize-feature-naturalsize-zero-format`
- `boltons-feature-slugify-max-length`

Requirements:

- candidate validation passes before applying
- writes stay inside the task allowlist
- only the task's single allowlisted production file changes
- hidden-like checks do not disagree with public validation
- planned action, changed paths, validation command, and rollback path are
  shown before applying
