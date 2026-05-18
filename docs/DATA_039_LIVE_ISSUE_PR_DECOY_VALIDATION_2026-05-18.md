# DATA-039 Live Issue/PR Decoy Validation

Task: `DATA-039`

Date: 2026-05-18

## Result

DATA-039 materialized and live-validated four realistic decoys for the
validated `scrapy/scrapy#7293/#7351` issue/PR replay. This resolves the Scrapy
row's label-only decoy blocker from DATA-037/DATA-038:

- `decoys_not_live_validated` is removed for the Scrapy row.
- `decoy_candidate_after_unavailable` is removed for the Scrapy row.
- The ranking harness remains shadow-only.

The useful hard result is negative: the Scrapy row is still not rankable as a
clean accepted-versus-failing-decoys set because two of the four live decoys
pass the focused validation command.

## Live Outcomes

| Decoy | Validation | Touched Files | Meaning |
| --- | --- | --- | --- |
| `scrapy_stale_min_stats_selection` | failed | `tests/test_pqueues.py` | accepted tests catch stale source |
| `scrapy_mutating_peek` | passed | `scrapy/pqueues.py`, `tests/test_pqueues.py` | focused command does not catch peek side effect |
| `scrapy_missing_last_selected_slot` | failed | `scrapy/pqueues.py`, `tests/test_pqueues.py` | accepted tests catch missing rotation state |
| `scrapy_missing_tests` | passed | `scrapy/pqueues.py` | source-only candidate passes focused validation |

This creates a new ranking blocker:

- `decoy_validation_outcomes_include_passing_candidates`

That blocker is intentional. Passing decoys mean the current validation signal
cannot honestly support pass@1/pass@k claims for this row.

## Artifacts

- `/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-bundle.json`
- `/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-candidates.jsonl`
- `/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-report.md`
- `/tmp/j3-data-039-ranking-with-live-decoys/ranking-report.json`
- `/tmp/j3-data-039-ranking-with-live-decoys/ranking-report.md`

## Next Probe

The next useful ranking task is not a scorer tweak. It is another falsification
probe: either live-materialize pytest #14462 decoys, or strengthen validation
for Scrapy enough to turn passing semantic/test decoys into trustworthy
failures without leaking accepted labels.
