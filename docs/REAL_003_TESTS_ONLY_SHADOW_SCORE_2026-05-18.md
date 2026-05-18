# REAL-003 Tests-Only Shadow Score

Date: 2026-05-18

Task: `REAL-003`

Input manifest: `examples/real_repo_eval_ladder.json`

Product gate source: `docs/PRODUCT_WEDGE_DECISION.md`

Generated output:

- `/tmp/j3-real-003-tests-only-shadow-score/score.json`
- `/tmp/j3-real-003-tests-only-shadow-score/report.md`

Command:

```bash
python -m j3.real_repo_shadow_score \
  --manifest examples/real_repo_eval_ladder.json \
  --out /tmp/j3-real-003-tests-only-shadow-score/score.json \
  --report /tmp/j3-real-003-tests-only-shadow-score/report.md
```

## Result

The first shadow score does not reach candidate validation. The current
`GS7-005` tests-only builder is limited to a one-file root `slugify.py` fixture
and `tests/test_slugify.py`. It cannot yet target the real-repo ladder's
`iniconfig`, `h11`, `humanize`, or `boltons` tests-only tasks without adding
repo-state-aware test placement, import selection, and behavior-specific pytest
case authoring.

| Metric | Value |
| --- | --- |
| Tasks scored | 4 tests-only tasks |
| Max candidates | 3 |
| Candidates generated | 0 |
| Candidates tested | 0 |
| pass@1 | 0/4 |
| pass@3 | 0/4 |
| First passing rank | none for every task |
| Correct test location | 0/4 |
| Candidate validation runtime | not run |
| Shadow scorer runtime | about 0.001s |
| Production-file modifications | 0 |
| Writes outside task allowlists | 0 actual writes |
| Hidden-like agreement | not run; no public-validating candidates |
| Hosted patch usage | 0; `zero_hosted_usage_confirmed=true` |

The zero mutation counts are not success evidence. They mean no candidate was
generated or applied. The falsifiable residual is that current tests-only
planning cannot target these real repositories.

## Task Rows

| Task | Split | pass@1 | pass@3 | Runtime / not-run reason | Mutation scope | Hidden-like | Residual labels |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `iniconfig-tests-parse-comments` | calibration | false | false | not run: `unsupported_tests_only_action_slice` | no files changed | not run | `unsupported_tests_only_action_slice`, `prompt_spec_existing_repo_gap`, `tests_only_scope_violation`, `wrong_test_location` |
| `h11-tests-bytesify-memoryview` | heldout | false | false | not run: `unsupported_tests_only_action_slice` | no files changed | not run | `unsupported_tests_only_action_slice`, `prompt_spec_existing_repo_gap`, `tests_only_scope_violation`, `wrong_test_location` |
| `humanize-tests-naturalsize-negative-strings` | heldout | false | false | not run: `unsupported_tests_only_action_slice` | no files changed | not run | `unsupported_tests_only_action_slice`, `prompt_spec_existing_repo_gap`, `tests_only_scope_violation`, `dependency_or_tooling_gap` |
| `boltons-tests-slugify-delimiter` | heldout | false | false | not run: `unsupported_tests_only_action_slice` | no files changed; the fixture target `tests/test_slugify.py` would not match the allowed `tests/test_strutils.py` path | not run | `unsupported_tests_only_action_slice`, `wrong_test_location`, `repo_state_planning_gap`, `tests_only_scope_violation` |

## Gate Decision

Gate 2, Shadow Tests-Only Generalization, fails.

- Required: `pass@3 >= 3/4`.
- Observed: `pass@3 = 0/4`.
- Required: hidden-like checks agree with public validation for passing
  candidates.
- Observed: no public-validating candidates reached hidden-like checks.
- Required: at least `3/4` tasks select the correct local test location and
  import style from repo-state evidence.
- Observed: `0/4`.

Decision: `remain_shadow_only`. Guarded tests-only opt-in is not allowed.

## Next Repair Target

The next useful slice is not more synthetic GreenShot success. It is a generic
real-repo tests-only planner that can read repo-state and local knowledge
records, select the accepted test file, import the public API from the package
layout, and materialize behavior-specific pytest cases while preserving the
production tree byte-for-byte.
