# REAL-006 Tests-Only Shadow Score

Date: 2026-05-18

## Command

```bash
python -m venv /tmp/j3-real-006-shadow-score/.venv
PATH=/tmp/j3-real-006-shadow-score/.venv/bin:$PATH \
  python -m j3.real_repo_preflight \
  --manifest examples/real_repo_eval_ladder.json \
  --repo iniconfig \
  --work-root /tmp/j3-real-006-shadow-score/repos \
  --outcome /tmp/j3-real-006-shadow-score/preflight.jsonl
PATH=/tmp/j3-real-006-shadow-score/.venv/bin:$PATH \
  python -m j3.real_repo_shadow_score \
  --manifest examples/real_repo_eval_ladder.json \
  --repo-path iniconfig=/tmp/j3-real-006-shadow-score/repos/iniconfig \
  --validate-candidates \
  --out /tmp/j3-real-006-shadow-score/score.json \
  --report /tmp/j3-real-006-shadow-score/report.md
```

## Result

- Output JSON: `/tmp/j3-real-006-shadow-score/score.json`
- Output report: `/tmp/j3-real-006-shadow-score/report.md`
- Preflight JSONL: `/tmp/j3-real-006-shadow-score/preflight.jsonl`
- Zero hosted usage: true
- pass@1: `1/4`
- pass@3: `1/4`
- First passing ranks: `[1, null, null, null]`
- Candidate count: `1`
- Candidates tested: `1`
- Scorer runtime: `0.134487s`
- Production file modifications: `0`
- Writes outside allowlist: `0`
- Hidden-like agreement: `1 agreeing`, `0 disagreeing`, `3 not_run`
- Gate decision: `remain_shadow_only`

The `iniconfig-tests-parse-comments` calibration task was materialized through
the GS7-008 planner surface into `testing/test_iniconfig.py` and validated with
`python -m pytest testing/test_iniconfig.py -q`, which passed with `54 passed in
0.03s`. The mutation scope changed only the allowed test file and left
`src/iniconfig` production files unchanged.

Held-out tests-only rows for `h11`, `humanize`, and `boltons` remain explicit
machine-readable blockers with `test_case_materialization_gap` and
`heldout_materializer_missing` residual labels. They are not counted as omitted
or unmeasured successes.

The gate remains shadow-only because the tests-only threshold is at least three
passing tasks out of four, and this run has one passing calibration task out of
four.
