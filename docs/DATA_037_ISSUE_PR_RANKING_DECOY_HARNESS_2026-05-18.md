# DATA-037 Issue/PR Ranking Decoy Harness

Task: `DATA-037`

Date: 2026-05-18

## Result

DATA-037 added a shadow-only ranking harness for the validated real issue/PR
candidates from DATA-029 and DATA-035.

The harness builds one accepted validated candidate plus four hard decoys for
each replay row:

- `pytest-dev__pytest-issue-14462-pr-14466`
- `scrapy__scrapy-issue-7293-pr-7351`

It does not change any production ranking gate.

## Metrics

| Metric | Value |
| --- | ---: |
| Rows | 2 |
| Accepted candidates | 2 |
| Decoys | 8 |
| Rankable rows | 0 |
| Blocked rows | 2 |
| pass@1 | blocked |
| pass@k | blocked |

Both rows block with these reasons:

- `no_guarded_issue_pr_ranker`
- `decoys_not_live_validated`
- `full_candidate_after_unavailable`
- `issue_specific_semantics_not_in_current_features`

## Interpretation

This is a useful negative result. j3 now has validated real source/test
candidates, but the current candidate-record feature surface is not enough to
honestly rank those accepted candidates above realistic issue-specific decoys.

The next ranking proof should add complete candidate-after snapshots or
live-validated decoy outcomes before claiming pass@1/pass@k on these rows.

## Artifacts

- `/tmp/j3-data-037-issue-pr-ranking-decoys/ranking-report.json`
- `/tmp/j3-data-037-issue-pr-ranking-decoys/decoy-candidates.jsonl`
- `/tmp/j3-data-037-issue-pr-ranking-decoys/ranking-report.md`
