# DATA-034 Scrapy #7293 Materialization Coverage Audit

Machine-readable audit over the accepted Scrapy #7293/#7351 changed paths. No candidate source edits were attempted.

## Summary

- Rows: `2`
- Classification counts: `{"requiring_constrained_local_generator_or_source_region_action":2}`
- Current structured-action covered paths: `0`
- Accepted paths fully expressible now: `false`

## Path Audit

| Path | Classification | Current action | Proposed action | Validation cost |
| --- | --- | --- | --- | --- |
| `scrapy/pqueues.py` | `requiring_constrained_local_generator_or_source_region_action` | `source_region_replace_v1 exists, but the accepted edit spans state initialization, a new helper method, and two call-site replacements with peek/pop state differences` | `scrapy_downloader_slot_rotation_source_region_v1 + python_method_insert_and_callsite_replace_v1` | `moderate` |
| `tests/test_pqueues.py` | `requiring_constrained_local_generator_or_source_region_action` | `deterministic pytest insertion exists only for prior bounded fixtures and cannot yet synthesize Scrapy request-slot setup inside the existing TestDownloaderAwarePriorityQueue class` | `scrapy_pqueue_pytest_class_method_insert_v1` | `moderate` |

## Findings

### `scrapy/pqueues.py`

- Accepted diff stats: `{"accepted_numstat":{"added":30,"removed":2},"anchors":["DownloaderAwarePriorityQueue.__init__","DownloaderAwarePriorityQueue._next_slot","DownloaderAwarePriorityQueue.pop","DownloaderAwarePriorityQueue.peek"],"change_kind":"python_queue_slot_rotation_state_and_helper_insert","git_diff_stats":{"added":30,"hunk_count":4,"removed":2},"semantic_payload":"track the last selected downloader slot, add a helper that rotates among equal active-download counts without starving later slots, update pop state when selecting, and keep peek non-mutating"}`
- Action recommendation: Use a constrained source-region materializer for DownloaderAwarePriorityQueue that inserts _last_selected_slot, adds _next_slot, and replaces only pop/peek slot selection based on DATA-031 downloader-aware queue facts.
- Likely failure mode: using min(stats) tie-breaking unchanged, mutating rotation state during peek, resetting rotation when a selected slot is deleted, mishandling slot ordering after the last slot, or touching unrelated priority-queue behavior
- Smallest next task: `DATA-034-next-scrapy-slot-rotation-source`
- Probe: py_compile passes, the diff adds _last_selected_slot and _next_slot, pop calls update_state=True, peek calls update_state=False, and no unrelated queue methods change

### `tests/test_pqueues.py`

- Accepted diff stats: `{"accepted_numstat":{"added":49,"removed":0},"anchors":["from scrapy.core.downloader import Downloader","TestDownloaderAwarePriorityQueue.test_tie_breaking_rotates_slots","TestDownloaderAwarePriorityQueue.test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted"],"change_kind":"pytest_downloader_aware_queue_test_insert","git_diff_stats":{"added":49,"hunk_count":2,"removed":0},"semantic_payload":"import Downloader for DOWNLOAD_SLOT metadata and add two focused DownloaderAwarePriorityQueue tests covering equal-active slot rotation and continued rotation after a selected slot is removed"}`
- Action recommendation: Use a constrained pytest class-method inserter that can add the Downloader import, build Request objects with DOWNLOAD_SLOT metadata, and assert the accepted slot sequences under existing pqueue fixtures.
- Likely failure mode: adding generic queue-order tests without Downloader.DOWNLOAD_SLOT metadata, placing methods outside TestDownloaderAwarePriorityQueue, asserting URLs instead of slot rotation, or missing the deleted-slot continuation case
- Smallest next task: `DATA-034-next-scrapy-pqueue-test-inserter`
- Probe: only the Downloader import and two accepted test methods are added, slot sequences match the accepted PR, and pytest tests/test_pqueues.py -q passes with the source edit

## Artifacts

- JSONL: `/private/tmp/j3-data-034-scrapy-materialization-audit/audit.jsonl`
