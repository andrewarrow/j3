# DATA-006 Issue/PR Mini Replay Preflight

Pre-edit replay preflight only; no candidate code edits were attempted.

## Summary

- Manifest: `examples/issue_pr_mini_replay/manifest.json`
- Batch: first 3 replay rows
- JSONL: `/tmp/j3-data-006-live-preflight/outcomes.jsonl`
- Runtime: 16.060 seconds
- Status counts: `{"blocked":3}`
- Blocker labels: `{"local_knowledge_required":1,"prompt_spec_ambiguous_or_incomplete":1,"validation_baseline_failed":1}`
- Residual categories: `{"local_knowledge":1,"prompt_spec":1,"validation":1}`
- Command stages reached: `{"baseline_validation":3,"checkout_clone":3,"checkout_ref":3,"checkout_verify":3,"setup":3}`
- First failed stages: `{"baseline_validation":1,"none":2}`
- Deferred agent residual labels: `{"materialization_gap":1,"ranking_gap":3}`

## Command

```bash
/tmp/j3-data-006-live-preflight/.venv/bin/python -m j3.issue_pr_preflight \
  --manifest examples/issue_pr_mini_replay/manifest.json \
  --workspace /tmp/j3-data-006-live-preflight/repos \
  --outcome /tmp/j3-data-006-live-preflight/outcomes.jsonl \
  --report /tmp/j3-data-006-live-preflight/report.md \
  --limit 3 \
  --setup-command "python -m pip install -e . pytest" \
  --timeout-seconds 240
```

## Rows

| Replay | Repo | Status | Blockers | Residual | First failed stage | Runtime |
| --- | --- | --- | --- | --- | --- | ---: |
| `psf__requests-issue-7432-pr-7433` | `psf/requests` | `blocked` | `validation_baseline_failed` | `validation` | `baseline_validation` | `11.291` |
| `pallets__click-issue-2745-pr-3364` | `pallets/click` | `blocked` | `prompt_spec_ambiguous_or_incomplete` | `prompt_spec` | `none` | `2.318` |
| `pallets__click-issue-3298-pr-3299` | `pallets/click` | `blocked` | `local_knowledge_required` | `local_knowledge` | `none` | `2.426` |

The Requests row checked out and installed, but focused baseline validation
failed before any edit attempt. The first repeated error was a recursive
`httpbin` fixture dependency in `tests/conftest.py`, so this batch treats the
row as a validation/setup recipe blocker rather than candidate quality signal.

Both Click rows checked out, installed, and passed the focused validation
commands. They remain blocked before edit attempts by the manifest's pre-edit
residual labels: prompt/spec ambiguity for the `default_map` multi-value row,
and local knowledge requirements for the non-string default crash row.
