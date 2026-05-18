# DATA-040 Live Pytest Issue/PR Decoy Validation

Task: `DATA-040`

Date: 2026-05-18

## Result

DATA-040 materialized and live-validated four realistic decoys for the
validated `pytest-dev/pytest#14462/#14466` issue/PR replay. This resolves the
pytest row's label-only decoy blockers from DATA-037/DATA-038:

- `decoys_not_live_validated` is removed for the pytest row.
- `decoy_candidate_after_unavailable` is removed for the pytest row.
- The ranking harness remains shadow-only.

The hard result is negative in the same way DATA-039 was negative for Scrapy:
the pytest row is still not rankable as a clean accepted-versus-failing-decoys
set because one of the four live decoys passes the focused validation command.

## Live Outcomes

| Decoy | Validation | Touched Files | Meaning |
| --- | --- | --- | --- |
| `pytest_rel_timedelta_object_semantics` | failed | `src/_pytest/python_api.py`, `testing/python/approx.py` | focused tests catch stale timedelta relative-tolerance semantics |
| `pytest_missing_container_dispatch` | failed | `src/_pytest/python_api.py`, `testing/python/approx.py` | focused tests catch missing container dispatch |
| `pytest_missing_invalid_tolerance_tests` | passed | `src/_pytest/python_api.py`, `testing/python/approx.py` | source is accepted but focused command cannot distinguish missing test coverage |
| `pytest_partial_source_test_materialization` | failed | `src/_pytest/python_api.py`, `testing/python/approx.py` | focused tests catch partial source semantics |

Both validated issue/PR rows now have live decoy validation and candidate-after
snapshots for every candidate, but both rows still block on:

- `decoy_validation_outcomes_include_passing_candidates`

That blocker is intentional. Passing decoys mean the current validation signal
cannot honestly support pass@1/pass@k claims for the issue/PR ranking rows.

## Artifacts

- `/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-bundle.json`
- `/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-candidates.jsonl`
- `/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-report.md`
- `/tmp/j3-data-040-ranking-with-live-decoys/ranking-report.json`
- `/tmp/j3-data-040-ranking-with-live-decoys/ranking-report.md`

## Next Probe

The next issue/PR ranking task should strengthen validation for passing decoys
without leaking accepted labels. A ranker change before that would hide the
actual problem: the current validation recipes do not make every hard negative
observable as a failure.
