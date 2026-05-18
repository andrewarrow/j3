# j3 Active Board

This is the live coordinator board. Keep it current and compact.

## Coordination State

- Coordinator mode: persistent multi-week execution.
- Parallel worker default: 2.
- Parallel worker maximum: 3, only with disjoint write scopes.
- Current review state: continuous loop mode. The active set may be empty only
  while the coordinator is recording the next assignments; ready work should be
  dispatched rather than leaving the board idle.
- Current product gate stance: transition ranking remains shadow-only; the
  2026-05-18 `TRANS-001` full matrix and `TRANS-004` targeted subset decisions
  were `remain_shadow_only`.

## Active Tasks

### `MAT-002`: Constrained source-region materialization probe

- Status: active
- Owner: worker Sartre (`019e3b50-c9b1-7cc0-9e2e-9230f72ae46e`)
- Started: 2026-05-18
- Goal: turn the largest `MAT-001` bucket into an executable probe by adding a
  bounded source-region materializer contract and focused tests.
- Write scope: `j3/source_region_materializer.py`,
  `tests/test_source_region_materializer.py`, optional docs under `docs/`, and
  plan updates.
- Acceptance: materialize a small replacement inside one named function or
  explicitly delimited region with AST parsing, signature preservation, changed
  line budget, forbidden import changes by default, and candidate-after diff
  metadata. Include a fixture shaped like the `psf/requests#7427`
  `should_bypass_proxies` domain-boundary edit so failure or success maps back
  to the audit.
- Tests: focused source-region tests, `pytest tests/test_plan_consistency.py -q`,
  and `git diff --check`.

### `WEDGE-001`: Product wedge decision

- Status: active
- Owner: worker Boyle (`019e3b51-328a-7c62-adc9-ba8cbf1055ba`)
- Started: 2026-05-18
- Goal: choose the first usable product path and make its gates/failure
  criteria concrete enough to stop vague Codex-replacement drift.
- Write scope: a focused product decision doc under `docs/` and plan updates.
- Acceptance: choose the wedge, define the user promise, non-goals, guarded
  rollout gates, evaluation links to `REAL-001`, `MAT-001`, `DATA-004`, and
  `KNOW-001`, and concrete pivot/failure criteria.
- Tests: `pytest tests/test_plan_consistency.py -q` and `git diff --check`.

## Ready Queue

These are good next assignments for the next loop:

1. `REAL-002`: add a preflight runner for the real-repo eval ladder.
2. `DATA-005`: add a replay preflight runner for one issue/PR row.
3. `GS7-005`: add tests-only existing-repo support for one-file libraries.
4. `GS7-006`: add repo-state-aware library convention edits.

Run at most two tasks in parallel unless write scopes are plainly disjoint.

## Paused Or Blocked

- `TRANS-003`: blocked until the `TRANS-002` generation and ranking residuals
  have focused fixes or regression evidence; do not expand the full matrix
  until targeted `TRANS-004` evidence is recorded.
- `MODEL-002`: superseded by bounded scorer subtasks in the backlog, beginning
  with `MODEL-003` through `MODEL-006`.

## Coordinator Review Triggers

Review before assigning more work if:

- `TRANS-001` reports a gate worse than expected
- `GS7-001` reveals missing actions rather than simple ranking failures
- `DATA-001` shows prompt split leakage or weak schema consistency
- two workers need the same files
- the next useful task is unclear

## Recently Completed

- `KNOW-001`: added `docs/LOCAL_KNOWLEDGE_INVENTORY.md`, choosing the first
  local-knowledge wedge as pytest authoring and validation, Python packaging
  and import layout, and small-library maintenance conventions. The inventory
  maps required concepts to local sources, JSONL record families, provenance
  and split rules, extraction rules, evaluation hooks, and the first three
  acquisition commands for real-repo preflight records, pytest pattern
  extraction, and issue/PR replay knowledge residual rows.
- `DATA-004`: added `docs/ISSUE_PR_MINI_REPLAY.md`,
  `examples/issue_pr_mini_replay/manifest.json`, and a schema test for 10
  curated issue/PR replay rows from Requests, Click, pytest, Poetry, pip, and
  Scrapy. The manifest records prompt text, repo-before refs, accepted PR refs,
  focused validation commands where inferable, provenance/license notes,
  stable splits, and residual labels for local knowledge, materialization,
  validation, ranking, and prompt/spec parsing blockers.
- `MAT-001`: added `docs/CODE_MATERIALIZATION_GAP.md`, classifying 25 merged
  Python PR diffs by the weakest materialization layer needed. Result: 4 fit
  current structured actions, 7 need general typed builders, 4 need
  repo-convention builders, 8 need constrained local generation, and 2 are
  out of current scope. The audit concludes the structured-action thesis is
  useful for tiny local repairs but cracking at source materialization unless
  typed builders and bounded local generators are added.
- `REAL-001`: added `docs/REAL_REPO_EVAL_LADDER.md`,
  `examples/real_repo_eval_ladder.json`, and a manifest schema test. The ladder
  pins four permissively licensed Python repos, defines tests-only and one-file
  feature tasks, records validation commands, split/leakage rules, runtime
  limits, pass/fail gates, and explicit falsifiers for real-repo
  generalization.
- `MODEL-001`: added a compact learned prompt-intent baseline report helper and
  recorded the 2026-05-18 current-corpus metrics in
  `docs/MODEL_001_PROMPT_INTENT_BASELINE_2026-05-18.md`. Current expanded
  corpus evaluation: validation exact-field 10/42 and test exact-field 9/72;
  clarification accuracy remains high at 40/42 validation and 68/72 test;
  inferred-default precision/recall is 0.000 on held-out splits because the
  positive labels are sparse and include a test-only unseen default.
- `GS7-004`: added a first-class `clarification-response-v1` outcome for
  ambiguous request-to-repo prompts. Blocked GreenShot plans, build results,
  JSONL attempt rows, and public `implement` output now carry structured
  questions while continuing to write no generated repo files.
- `REPO-001`: added an inspectable repo-state coverage section alongside the
  deterministic embedding record. Fixture coverage now reports all discovered
  files with roles, Python packages, imports, top-level functions and classes,
  pytest files, config files, likely entrypoints, docs, and parse errors while
  keeping the existing embedding metadata and aggregate fields stable.
- `ACT-001`: added `docs/ACTION_COVERAGE_MAP.md`, separating current
  transition residuals and GreenShot-7 classified gaps into supported repair
  actions, new request-to-repo action needs, ranking/scorer gaps, and
  prompt/spec or existing-repo support gaps. The map recommends tests-only
  existing-repo support and repo-state-aware library convention slices as new
  action work, while keeping transition repair residuals focused on scorer and
  observation improvements.
- `GS7-002`: added five non-calculator request-to-repo fixtures. The small
  slugify library and key/value parser now build and validate through bounded
  greenfield builders; tests-only and existing-repo convention requests are
  classified as `action_coverage` and `existing_repo_support`; the converter
  prompt is classified as `expected_clarification`.
- `DATA-003`: added a deterministic issue/PR transition manifest prototype
  backed by a small `apache/airflow` fixture. The manifest records issue/PR
  text provenance, links, before/after commit refs, stable split buckets, and
  license/terms notes without committing large harvested artifacts.
- `OPS-002`: added a lightweight plan consistency parser and focused pytest
  check for `plans/active.md` and `plans/backlog.md`. The check catches
  malformed task headings, invalid status values, active tasks missing from
  backlog, and active/backlog status drift.
- `TRANS-004`: reran targeted `greenshot_6_subset` transition matrix evidence
  after the `ACT-002` subscript-key fix. The
  `http_no_store_directive_subscript_key` production and shadow candidates now
  solve within the matrix cap at rank 1 via `change_subscript_key`, eliminating
  the candidate-generation gap. Targeted subset totals: 12 tasks, 12 ranked
  solved, 4 matrix residuals, 8 residual-report failures, all
  `scorer_ranking_gap`; targeted guarded decision remains
  `remain_shadow_only`.
- `DATA-002`: added repeatable prompt/spec corpus schema validation on top of
  the `inspect-prompt-corpus` profile path. The validator accepts the seed,
  expanded, and GreenShot-7 intent corpora with zero errors while reporting
  legacy seed expected-action gaps and cross-split near-duplicates as review
  warnings.
- `ACT-002`: fixed the subscript-key candidate cap gap for
  `greenshot_6_subset/http_no_store_directive_subscript_key`. The passing
  `change_subscript_key` candidate from `"no-store"` to `"no_store"` now ranks
  first and validates under `--max-candidates 8`; focused candidate ranking and
  patching tests passed.
- `DATA-001`: expanded `inspect-prompt-corpus` into a repeatable prompt corpus
  quality audit. Current 320-row corpus has no exact normalized duplicates,
  no unsupported scalar labels, and no family split leakage, but it has 2
  cross-split near-duplicate prompt pairs and schema consistency gaps that
  `DATA-002` should validate.
- `TRANS-002`: diagnosed the 2026-05-18 transition matrix residuals. Result:
  14 residual-report failures split into 1 candidate-generation gap
  (`change_subscript_key` for `http_no_store_directive_subscript_key`) and 13
  scorer-ranking gaps concentrated in add-keyword decoys, mapping key/value
  target confusion, boundary/literal ranking, and identifier/signature decoys.
  Diagnosis recorded in `docs/TRANSITION_MATRIX_RESIDUALS_2026-05-18.md`.
- `TRANS-001`: ran the full transition shadow matrix on 2026-05-18. Gate
  result: `remain_shadow_only`; guarded opt-in trial eligibility `false`.
  Matrix totals: 5 suites, 56 tasks, 55 ranked solved, 7 matrix residuals,
  14 residual report failures, zero hosted usage. Evidence under
  `/tmp/j3-trans-001-shadow-matrix` and `/tmp/j3-trans-001-matrix-evidence`.
- `GS7-001`: refreshed the current GreenShot-7 baseline. Result: 10 fixture
  tasks, 8 built and validation-passed, 2 intentionally blocked for
  clarification, no prompt-spec failures, missing-action failures, ranking
  failures, or generated pytest failures observed. Verification: focused
  GreenShot-7 tests plus direct `implement` CLI smoke passed.
- `OPS-001`: migrated from the daily `today*` loop to persistent coordination
  files. Verification: `git diff --check` passed.
- Previous daily loop completed transition shadow suite, residual reports,
  matrix runner, matrix evidence bundle, guarded-trial decision, and matrix docs.
  Those results remain useful, but new work should be tracked here and in
  `plans/progress.md`.
