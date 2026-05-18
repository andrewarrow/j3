# Issue/PR Transition Manifest Prototype

`DATA-003` adds a small, review-first manifest shape for linking issue and pull
request text to accepted repository changes. It is deliberately a manifest, not
a large generated corpus: real harvested outputs should stay under ignored
`data/` or `/tmp` paths until reviewed.

## Prototype Command

The prototype consumes an exported JSON file with `repository`, `issues`, and
`pull_requests` fields. It does not require live GitHub/API access.

```bash
python cli.py mine-issue-pr-manifest \
  --source tests/fixtures/mining/apache_airflow_issue_pr_fixture.json \
  --out /tmp/j3-apache-airflow-issue-pr-manifest.json
```

The checked-in fixture uses one Apache corpus repository, `apache/airflow`, and
emits one candidate record from a merged PR linked to an issue. Unmerged PRs and
PRs without known linked issues are skipped.

## Manifest Shape

Top-level manifest fields:

- `schema_version`: `issue-pr-transition-manifest-v0`
- `source`: export path, source checksum, source kind, retrieved timestamp, and
  `live_api_access_required: false`
- `repository`: provider, owner/name, URL, default branch, and license metadata
- `license_and_terms`: repository SPDX/license URL plus hosting terms notes
- `records`: candidate issue/PR transition records
- `totals`: issues seen, PRs seen, candidate records emitted
- `notes`: review and generated-data cautions

Each candidate record contains:

- `id`: stable `owner__repo-issue-N-pr-M` identifier
- `split` and `stable_split`: deterministic SHA-256 bucket split
- `prompt_source`: issue title/body plus PR title/body
- `issue` and `pull_request`: source numbers, URLs, state, merge metadata, and
  changed-file hints
- `repo_before_ref`: PR base commit SHA/ref
- `repo_after_ref`: merge commit SHA/ref
- `links`: repository, issue, PR, diff, patch, and compare URLs where available
- `provenance`: source kind/path/checksum, retrieval time, review status, and
  manual review requirement
- `license_and_terms`: copied per record for downstream filtering

## Review Status

Records are emitted as `unreviewed_candidate`. Before normalizing them into
prompt/repo transition training rows, a reviewer still needs to verify:

- the issue really describes the user intent rather than incidental discussion
- the merged PR is the accepted implementation for that intent
- `repo_before_ref` and `repo_after_ref` are fetchable and reproduce the diff
- repository license metadata is correct
- hosting-site terms allow the intended storage and use of issue/PR text
- generated manifests with substantial text are kept out of git
