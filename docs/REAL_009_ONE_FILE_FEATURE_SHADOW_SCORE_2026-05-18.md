# REAL-009 One-File Feature Shadow Score

REAL-009 scores the MAT-003 h11 source-feature candidate against the full
one-file feature ladder. The scorer does not count a standalone materializer
pass as product gate evidence; the task passes only when the materialized
candidate also passes its public validation command.

## Result

- Score artifact: `/tmp/j3-real-009-feature-shadow-score-live/score.json`
- Report artifact: `/tmp/j3-real-009-feature-shadow-score-live/report.md`
- Tasks scored: `4`
- Candidate count: `1`
- Candidates tested: `1`
- pass@1: `1/4`
- pass@3: `1/4`
- First passing ranks: `[null, 1, null, null]`
- Distinct repos passing: `1` (`h11`)
- Production-file constraint: preserved
- Production files changed by passing candidate: `1` (`h11/_util.py`)
- Mutation-scope violations: `0`
- Writes outside allowlist: `0`
- Candidate validation: `7 passed in 0.02s`
- Zero hosted usage: confirmed
- Gate decision: `remain_shadow_only`

## Task Rows

| Task | Status | pass@3 | Blocker |
| --- | --- | --- | --- |
| `iniconfig-feature-section-default` | blocked | false | `one_file_materialization_gap` |
| `h11-feature-bytesify-object-message` | passed | true | none |
| `humanize-feature-naturalsize-zero-format` | blocked | false | `one_file_materialization_gap` |
| `boltons-feature-slugify-max-length` | blocked | false | `one_file_materialization_gap` |

## Gate Decision

The one-file feature gate requires at least `2/4` passing tasks across at least
two distinct repositories. Current evidence is `1/4` across one repository, so
one-file feature use remains shadow-only.
