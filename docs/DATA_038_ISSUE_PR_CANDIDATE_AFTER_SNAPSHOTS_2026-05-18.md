# DATA-038 Issue/PR Candidate-After Snapshots

Task: `DATA-038`

Date: 2026-05-18

## Result

DATA-038 added sidecar candidate-after snapshots for the validated real
issue/PR candidates from DATA-029 and DATA-035.

The snapshot bundle covers:

- `pytest-dev__pytest-issue-14462-pr-14466`
- `scrapy__scrapy-issue-7293-pr-7351`

It writes full after-file snapshots for all four touched files, with hashes,
diff metadata, AST metadata, validation status, and provenance. No production
ranking gate changed.

## Ranking Impact

Rerunning the DATA-037 ranking harness with the bundle removes
`full_candidate_after_unavailable` for the accepted candidates. The ranking
rows still block because realistic decoys do not have materialized after-file
snapshots or live validation outcomes.

Current remaining ranking blockers:

- `no_guarded_issue_pr_ranker`
- `decoys_not_live_validated`
- `issue_specific_semantics_not_in_current_features`
- `decoy_candidate_after_unavailable`

## Artifacts

- `/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-bundle.json`
- `/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-candidates.jsonl`
- `/tmp/j3-data-038-issue-pr-candidate-after-snapshots/candidate-after-report.md`
- `/tmp/j3-data-038-ranking-with-snapshots/ranking-report.json`
- `/tmp/j3-data-038-ranking-with-snapshots/ranking-report.md`
