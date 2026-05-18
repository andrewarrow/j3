# VAL-002 Cross-Row Validation Strength Probe

Task: `VAL-002`

Date: 2026-05-18

## Result

VAL-002 ran stronger label-safe behavior probes against every passing decoy
from the DATA-039 Scrapy row and DATA-040 pytest row. This remains a
shadow-only validation adequacy probe; no production ranking gate changed.

- Passing decoys found: `3`
- Live behavior probe runs: `6`
- Converted passing decoys to failures: `1`
- Coverage-gap blockers: `2`
- Accepted candidate failures: `0`
- Runtime: `1.048s`

## Live Outcomes

| Replay | Passing Decoy | Accepted | Decoy | Meaning |
| --- | --- | --- | --- | --- |
| `scrapy__scrapy-issue-7293-pr-7351` | `scrapy_mutating_peek` | passed | failed | issue-derived peek behavior converts a semantic passing decoy into a failure |
| `scrapy__scrapy-issue-7293-pr-7351` | `scrapy_missing_tests` | passed | passed | source behavior matches accepted; failing this would require accepted-test or accepted-diff leakage |
| `pytest-dev__pytest-issue-14462-pr-14466` | `pytest_missing_invalid_tolerance_tests` | passed | passed | source behavior matches accepted; failing this would require accepted-test or accepted-diff leakage |

The useful result is mixed. Label-safe behavior validation can recover at least
one missed semantic decoy without breaking the accepted candidate. It cannot
turn source-equivalent, coverage-gap decoys into failures without leaking the
accepted tests or accepted diff as the label.

## Product-Gate Blocker

The issue/PR ranking gate remains blocked on:

- `coverage_gap_decoy_indistinguishable_without_accepted_label_leakage`

That blocker should not be papered over by scorer tuning. A rankable
accepted-versus-decoy set needs either behavior-observable negative candidates
or a separate policy that treats coverage-gap decoys as non-ranking product
risks rather than ordinary hard negatives.

## Artifacts

- `/tmp/j3-val-002-validation-strength-probe/validation-strength-report.json`
- `/tmp/j3-val-002-validation-strength-probe/validation-strength-report.md`
- `/tmp/j3-val-002-accepted-checkouts/scrapy`
- `/tmp/j3-val-002-accepted-checkouts/pytest`

## Next Probe

The next validation task should define how coverage-gap decoys affect issue/PR
ranking readiness without using accepted-label leakage. The key question is
whether they belong in the ranker denominator, a product safety gate, or a
separate coverage-generation objective.
