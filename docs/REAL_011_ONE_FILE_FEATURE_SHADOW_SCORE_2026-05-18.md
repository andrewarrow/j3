# REAL-011 One-File Feature Shadow Score

REAL-011 reran the one-file feature gate after `MAT-004` added the
`iniconfig-feature-section-default` materializer. At integration time,
`MAT-005` had also added `humanize-feature-naturalsize-zero-format`, so this
score counts iniconfig, h11, and humanize through
`j3.real_repo_feature_materializer`.

## Live Run

```bash
python -m j3.real_repo_preflight --manifest examples/real_repo_eval_ladder.json --repo iniconfig --repo h11 --repo humanize --work-root /tmp/j3-real-011-feature-shadow-score-live-v2/repos --outcome /tmp/j3-real-011-feature-shadow-score-live-v2/preflight.jsonl

python -m j3.real_repo_feature_shadow_score --manifest examples/real_repo_eval_ladder.json --repo-path iniconfig=/tmp/j3-real-011-feature-shadow-score-live-v2/repos/iniconfig --repo-path h11=/tmp/j3-real-011-feature-shadow-score-live-v2/repos/h11 --repo-path humanize=/tmp/j3-real-011-feature-shadow-score-live-v2/repos/humanize --validate-candidates --out /tmp/j3-real-011-feature-shadow-score-live-v2/score.json --report /tmp/j3-real-011-feature-shadow-score-live-v2/report.md
```

Artifacts:

- `/tmp/j3-real-011-feature-shadow-score-live-v2/preflight.jsonl`
- `/tmp/j3-real-011-feature-shadow-score-live-v2/score.json`
- `/tmp/j3-real-011-feature-shadow-score-live-v2/report.md`

## Result

- `pass@1`: `3/4`
- `pass@3`: `3/4`
- Calibration pass@3: `1/1`
- Held-out pass@3: `2/3`
- Distinct repos passing: `3` (`iniconfig`, `h11`, `humanize`)
- Candidate validation statuses: `passed = 3`, `blocked = 1`
- First passing ranks: `[1, 1, 1, null]`
- Production-file constraint violations: `0`
- Writes outside allowlist: `0`
- Hidden-like agreement: `3` agreeing, `0` disagreeing, `1` not run
- Hosted usage: `0`

`boltons-feature-slugify-max-length` remains an explicit
`one_file_materialization_gap` blocker.

## Gate Decision

The manifest one-file feature gate passes:
`allow_guarded_one_file_feature_opt_in`.

Guarded opt-in is limited to:

- `iniconfig-feature-section-default`
- `h11-feature-bytesify-object-message`
- `humanize-feature-naturalsize-zero-format`

Requirements:

- candidate validation passes before applying
- writes stay inside the task allowlist
- only the task's single allowlisted production file changes
- hidden-like checks do not disagree with public validation
- planned action, changed paths, validation command, and rollback path are
  shown before applying
