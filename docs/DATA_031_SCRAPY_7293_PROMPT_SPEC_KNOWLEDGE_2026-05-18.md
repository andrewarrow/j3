# DATA-031 Scrapy Prompt/Spec And Local Knowledge

Evidence acquisition only; no candidate source edits were attempted.

## Row

- Replay ID: `scrapy__scrapy-issue-7293-pr-7351`
- Repo: `scrapy/scrapy`
- Split: `validation`
- Repo-before checkout:
  `/tmp/j3-data-030-validation-preflight/repos/scrapy__scrapy-scrapy__scrapy-issue-7293-pr-7351-2b174e348d88`
- DATA-030 baseline: `pytest tests/test_pqueues.py -q` passed with
  `11 passed, 2 skipped, 2 warnings in 0.20s`

## Evidence

- Prompt/spec:
  `/tmp/j3-data-031-scrapy-7293-evidence/spec.jsonl`
- Prompt/spec report:
  `/tmp/j3-data-031-scrapy-7293-evidence/spec.md`
- Local knowledge:
  `/tmp/j3-data-031-scrapy-7293-evidence/knowledge.jsonl`

The prompt/spec record is normalized and covers the
`DownloaderInterface._active_downloads` issue framing, observed versus expected
queue behavior, affected Scrapy APIs/classes, reproduction input shape,
acceptance-test shape, downloader-aware slot tie-breaking, slot active-download
count semantics, and priority queue ordering reproduction.

The local-knowledge JSONL emits six records covering changed-file context for
`scrapy/pqueues.py` and `tests/test_pqueues.py`, the focused DATA-030
validation recipe, downloader-aware priority queue behavior, slot active
download accounting, pqueue test patterns, provenance, validation split labels,
and remaining readiness blockers.

## Remaining Blockers

- Candidate materialization is still deferred.
- Ranking/decoy evidence is still deferred.
- Future candidate scope should stay limited to `scrapy/pqueues.py` and
  `tests/test_pqueues.py` unless a coordinator explicitly broadens the task.
