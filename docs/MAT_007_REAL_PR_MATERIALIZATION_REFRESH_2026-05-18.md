# MAT-007 Real PR Materialization Coverage Refresh

Task: `MAT-007`

Date: 2026-05-18

## Question

After the DATA-029 pytest #14462 and DATA-035 Scrapy #7293 source/test
candidate wins, is the materialization surface becoming reusable, or is it
drifting toward one bespoke action family per accepted PR?

Short answer: the wins are real, but the held-out coverage thesis has not
changed enough yet. The two validated candidates prove that constrained
source/test materialization can reproduce difficult accepted diffs, but the
held-out panel still has a large constrained-generator bucket and an equally
large typed-builder bucket. The next proof must show reuse of general action
records such as source-region replacement, method insertion, call-site
replacement, and pytest class insertion without PR-named materializers.

## Artifacts

- JSONL rows:
  `docs/MAT_007_REAL_PR_MATERIALIZATION_REFRESH_2026-05-18.jsonl`
- Copied runtime artifact:
  `/tmp/j3-mat-007-real-pr-materialization-refresh/MAT_007_REAL_PR_MATERIALIZATION_REFRESH_2026-05-18.jsonl`

## Sample

The held-out refresh panel contains 24 real accepted Python PR diffs from the
MAT-001 universe, excluding the DATA-029 validated pytest #14466 row. DATA-035
Scrapy #7351 was not part of MAT-001, so it is recorded separately as a
validated-candidate reference row and not counted in the held-out totals.

All 24 held-out rows and both validated-candidate reference rows use primary
GitHub PR diff URLs. A live URL check on 2026-05-18 returned HTTP 200 for every
recorded `.diff` URL.

Excluded from held-out counts:

- `pytest-dev/pytest#14466`: DATA-029 validated candidate reference.
- `scrapy/scrapy#7351`: DATA-035 validated candidate reference.

## Held-Out Counts

| Weakest sufficient materialization | Count |
| --- | ---: |
| `current_structured_action` | 4 |
| `general_typed_builder` | 7 |
| `repo_convention_builder` | 4 |
| `constrained_local_generator` | 7 |
| `not_currently_expressible` | 2 |

If the two validated candidate reference rows are included for post-win
context, they add two more `constrained_local_generator` examples, both now
validated for their specific replay rows. They are not counted as held-out
generalization evidence.

## Row Summary

| PR | Role | Label | Note |
| --- | --- | --- | --- |
| [click#3434](https://github.com/pallets/click/pull/3434) | held-out | `constrained_local_generator` | Usage-line branch plus output tests. |
| [click#3430](https://github.com/pallets/click/pull/3430) | held-out | `general_typed_builder` | Helper extraction and call replacement. |
| [click#3423](https://github.com/pallets/click/pull/3423) | held-out | `current_structured_action` | Targeted expression replacement. |
| [click#3422](https://github.com/pallets/click/pull/3422) | held-out | `general_typed_builder` | Annotation movement and return annotations. |
| [click#3420](https://github.com/pallets/click/pull/3420) | held-out | `constrained_local_generator` | ANSI-aware wrapping logic. |
| [click#3405](https://github.com/pallets/click/pull/3405) | held-out | `repo_convention_builder` | Pager tests with local fixtures and monkeypatching. |
| [click#3396](https://github.com/pallets/click/pull/3396) | held-out | `general_typed_builder` | Sentinel aliases and parser annotations. |
| [click#3364](https://github.com/pallets/click/pull/3364) | held-out | `constrained_local_generator` | Default-map splitting behavior. |
| [flask#6013](https://github.com/pallets/flask/pull/6013) | held-out | `current_structured_action` | Lowercase expression wrapper. |
| [flask#5903](https://github.com/pallets/flask/pull/5903) | held-out | `general_typed_builder` | Filesystem idiom rewrite. |
| [flask#5898](https://github.com/pallets/flask/pull/5898) | held-out | `current_structured_action` | Redirect default constants. |
| [flask#5812](https://github.com/pallets/flask/pull/5812) | held-out | `not_currently_expressible` | Broad context architecture merge. |
| [flask#5808](https://github.com/pallets/flask/pull/5808) | held-out | `general_typed_builder` | Method annotation update. |
| [flask#5727](https://github.com/pallets/flask/pull/5727) | held-out | `not_currently_expressible` | Tooling and lockfile migration. |
| [requests#7441](https://github.com/psf/requests/pull/7441) | held-out | `general_typed_builder` | Type imports and annotations. |
| [requests#7437](https://github.com/psf/requests/pull/7437) | held-out | `general_typed_builder` | Assignment annotation and type-ignore. |
| [requests#7433](https://github.com/psf/requests/pull/7433) | held-out | `constrained_local_generator` | Stream-wrapper predicate and tests. |
| [requests#7427](https://github.com/psf/requests/pull/7427) | held-out | `constrained_local_generator` | Domain-boundary proxy matching. |
| [requests#7423](https://github.com/psf/requests/pull/7423) | held-out | `repo_convention_builder` | Autouse fixture in local conftest style. |
| [requests#7328](https://github.com/psf/requests/pull/7328) | held-out | `constrained_local_generator` | Redirect history mutation ordering. |
| [requests#7315](https://github.com/psf/requests/pull/7315) | held-out | `repo_convention_builder` | Adapter expectation update. |
| [pytest#14475](https://github.com/pytest-dev/pytest/pull/14475) | held-out | `constrained_local_generator` | Scanner source and regression test pair. |
| [pytest#14472](https://github.com/pytest-dev/pytest/pull/14472) | held-out | `current_structured_action` | Literal receiver to variable receiver. |
| [pytest#14429](https://github.com/pytest-dev/pytest/pull/14429) | held-out | `repo_convention_builder` | Defensive repr guard plus parser-fixture tests. |

Validated candidate reference rows:

| PR | Task | Label | Post-win interpretation |
| --- | --- | --- | --- |
| [pytest#14466](https://github.com/pytest-dev/pytest/pull/14466) | DATA-029 | `constrained_local_generator` | Exact accepted source/test diff now materializes and validates, but the implemented action labels are still pytest-approx specific. |
| [scrapy#7351](https://github.com/scrapy/scrapy/pull/7351) | DATA-035 | `constrained_local_generator` | Exact accepted source/test diff now materializes and validates, but the implemented action labels are still Scrapy slot-rotation specific. |

## What DATA-029 And DATA-035 Changed

DATA-029 and DATA-035 moved two difficult accepted source/test PRs from
"requires constrained local generation" to "can be reproduced by a bounded
validated materializer for that row." That is meaningful because both diffs
required coordinated production and pytest edits, candidate-after diff records,
focused validation, and accepted-diff parity.

They do not yet collapse the held-out constrained bucket. The reusable part is
the mechanism shape:

- bounded source-region replacement
- Python method or helper insertion
- call-site replacement inside a protected mutation scope
- pytest class-method refinement or insertion
- focused validation and accepted-diff parity checks

The risky part is the naming and targeting. The recorded candidate actions are
still domain-specific, such as pytest approx timedelta handling and Scrapy
downloader slot rotation. If the next accepted PR needs another named
`repo_issue_behavior_v1` action instead of parameterizing the mechanism shape,
the project is in action-vocabulary explosion territory.

## Representative Held-Out Examples

`requests#7427` remains the cleanest constrained-source probe. It is small,
public, and bounded to one function plus tests, but the materializer must
synthesize the domain-boundary predicate rather than only replace a literal.
This should reuse MAT-002-style source-region constraints, not a
`requests_7427` special case.

`pytest#14475` is the closest pytest-family reuse test after DATA-029. It needs
a scanner source update plus regression test placement. A passing candidate
would be stronger evidence if it reused generic region replacement and pytest
test insertion instead of adding a scanner-specific materializer.

`click#3430`, `click#3422`, `requests#7441`, and `requests#7437` show that
typed builders are now as important as constrained generation in the held-out
panel. More source-region wins alone will not cover annotation, import, helper
extraction, and signature families.

`requests#7423` and `pytest#14429` show why repo-convention builders remain a
separate layer. The production edit can be tiny, but the accepted proof depends
on local fixture, import, parser, monkeypatch, or test-class conventions.

## Failure Criteria

Treat the materialization surface as failing by vocabulary explosion if any of
these happen:

- More than half of new materializer action kinds added for accepted PR replay
  contain repo names, issue numbers, PR numbers, or behavior-specific nouns
  that cannot apply outside the original row.
- The next 10 held-out constrained-source attempts require more than 10 new
  action kinds total, rather than reusing a small set of parameterized
  source-region, method-insert, call-site, and pytest-insertion actions.
- DATA-029/DATA-035-derived mechanisms cannot cover at least 3 of the next 10
  held-out constrained-source rows without candidate-specific source-builder
  code.
- The held-out constrained bucket stays above 25% after 10 validated
  source-region attempts, excluding rows explicitly labeled
  `not_currently_expressible`.
- General typed-builder rows continue to be deferred while constrained
  source-region rows get bespoke actions; that would leave 7/24 held-out rows
  uncovered by the middle layer MAT-001 said was needed.

Treat held-out generalization as weak if:

- pass@1 on materialized held-out source/test candidates remains below 3/10
  after focused validation recipes are available;
- accepted-diff parity is achieved only on calibration or previously audited
  rows, not on newly sampled held-out PRs;
- materializers pass focused tests but touch files outside the replay allowlist
  or require hidden production gate exceptions;
- the artifact cannot explain which reusable action family produced each hunk.

## Verdict

The structured-action thesis is still viable, but MAT-007 does not justify a
broader product gate. DATA-029 and DATA-035 prove the constrained-source/test
path can work when the target row is deeply understood. The held-out refresh
still says the next durable investment is a small reusable middle layer:
general typed builders, repo-convention pytest builders, and parameterized
source-region actions with validation and rollback.

The next useful task is not another PR-specific materializer. It is a
held-out constrained-source attempt, preferably `requests#7427` or
`pytest#14475`, with a hard rule that the action record must be reusable across
at least one other row in this MAT-007 panel.
