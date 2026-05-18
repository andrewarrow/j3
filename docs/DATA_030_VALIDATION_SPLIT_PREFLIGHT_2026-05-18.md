# DATA-030 Validation-Split Issue/PR Preflight

Pre-edit replay preflight only. No candidate source edits were attempted.

## Summary

- Rows: `2`
- Status counts: `{"blocked":2}`
- Command classifications: `{"commands_passed":1,"dependency_fixture_setup_failure":1}`
- Evidence acquisition statuses: `{"blocked_on_validation_recipe":1,"ready_for_prompt_spec_and_local_knowledge":1}`
- Next validation-split row ready for evidence acquisition: `scrapy__scrapy-issue-7293-pr-7351`

## Rows

| Replay | Result |
| --- | --- |
| `pypa__pip-issue-12018-pr-13886` | Checkout, setup, and ref verification passed. Baseline validation `pytest tests/functional/test_install_reqs.py -q` failed in pre-edit state with `ModuleNotFoundError: No module named 'installer'` while importing `tests/conftest.py`, so the row is blocked on validation recipe/dependency setup rather than edit quality. Required local knowledge remains `pip_resolvelib_factory_candidate_selection`, `pip_install_functional_test_fixtures`, and `requirement_constraint_extras_semantics`; materialization and ranking are deferred agent-stage residuals. |
| `scrapy__scrapy-issue-7293-pr-7351` | Checkout, setup, and baseline validation passed with `11 passed, 2 skipped, 2 warnings`. The row is ready for prompt/spec and local-knowledge acquisition, with prompt gaps around `DownloaderAwarePriorityQueue` tie-breaking, active-download count semantics, and priority queue ordering reproduction. Required local knowledge is `scrapy_downloader_aware_priority_queue`, `scrapy_slot_active_download_accounting`, and `scrapy_pqueue_test_patterns`; ranking remains deferred. |

## Artifacts

- JSONL: `/tmp/j3-data-030-validation-preflight/outcomes-data-030.jsonl`
- Report: `/tmp/j3-data-030-validation-preflight/report-data-030.md`
- Raw first pip run: `/tmp/j3-data-030-validation-preflight/outcomes-pip.jsonl`
