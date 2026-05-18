# Product Wedge Decision

Task: `WEDGE-001`

Date: 2026-05-18

## Decision

Choose exactly one first product path:

```text
guarded local tests-only maintenance for small existing Python libraries
```

This is narrower than "tests plus conservative source edits" as an initial
user promise. The new evidence says tests-only maintenance is the first usable
wedge because it forces real repo inspection, local pytest and packaging
knowledge, cheap validation, action coverage, and held-out ranking without
requiring the project to solve the whole code materialization gap first.

Conservative one-file small-library source maintenance remains the adjacent
shadow path. It should be implemented and evaluated because the six-month
target needs it, but it is not part of the first guarded product promise until
the source materialization gates below pass.

## User Promise

For selected small Python libraries, j3 will run locally, inspect the repository,
plan a tests-only edit, show the intended file changes, add or refine pytest
coverage without changing production code, run the configured validation, and
leave an auditable transition record with residual labels when it cannot proceed.

j3 will not silently send repository code to a hosted model. It will ask for
clarification when the task is underspecified. It will report partial confidence
when validation is incomplete, slow, flaky, or unavailable.

## Non-Goals

- No Codex replacement claim.
- No broad feature implementation as the first product promise.
- No default production-source edits before the source gates pass.
- No multi-file migrations, architecture changes, dependency upgrades, lockfile
  rewrites, or broad refactors.
- No repo-specific action rules keyed to held-out repository names, paths, or
  exact prompt strings.
- No production routing from learned or heuristic rankers unless held-out gates
  beat deterministic baselines without regressions.

## Why This Wedge

The user preference was tests-only edits plus conservative small-library
maintenance. The evidence supports that direction, but with a stricter product
boundary.

- [REAL-001](REAL_REPO_EVAL_LADDER.md) makes real-repo generalization falsifiable
  with four pinned small Python repos, tests-only tasks, one-file feature tasks,
  repo-level split rules, hidden-like checks, and runtime caps.
- [MAT-001](CODE_MATERIALIZATION_GAP.md) shows current structured actions cover
  only 4 of 25 sampled real accepted PRs directly. Eight need constrained local
  source generation, which is too risky for the first guarded promise.
- [DATA-004](ISSUE_PR_MINI_REPLAY.md) shows real issue/PR rows immediately hit
  local knowledge, validation, ranking, materialization, and prompt/spec gaps.
- [KNOW-001](LOCAL_KNOWLEDGE_INVENTORY.md) defines the pytest, packaging, and
  small-library convention records that must become local data, not hardcoded
  intuition.
- `MAT-002` is still needed, but as a shadow proof for source edits rather than
  a reason to overpromise the first product.

Tests-only maintenance is still a hard wedge. Passing it requires repo-state
planning, local knowledge, structured action coverage, cheap validation, and
held-out ranking evidence. It also gives users a useful artifact with lower
blast radius than production source edits.

## Hard Question Mapping

| Hard question | Wedge answer | Required proof |
| --- | --- | --- |
| Real-repo generalization | Score only on pinned or newly held-out repos, split by repository. | `REAL-002` preflight plus `REAL-001` tests-only gate: `pass@3 >= 3/4`, no source changes, hidden-like checks agree. |
| Structured action coverage | Use generic existing-repo pytest builders and repo-convention builders, not repo-name rules. | Passing tasks use predeclared action families; zero held-out passes depend on repository-name or prompt-string special cases. |
| Repo-state planning | Select the correct test location, import path, package layout, and allowed write path from repo state. | At least `3/4` tests-only tasks write to the accepted test location, and every passing task stays inside allowlisted paths. |
| Local knowledge | Encode pytest, packaging, import, fixture, parametrization, and CLI/library conventions as data. | `KNOW-001` defines provenance and split rules; `KNOW-002` emits records that product runs cite or mark as missing. |
| Cheap validation | Prefer targeted pytest and import checks with timeouts over full CI. | Baseline passes on at least `3/4` real repos, median scored task runtime is `<= 180s`, every scored task is `< 600s`, and no network is used during candidate validation. |
| Held-out ranking | Ranking can assist only after it wins outside fixtures. | Candidate ranking improves first-passing rank or `pass@1` over deterministic ordering on held-out real-repo tasks with zero `pass@3` regression. |

## Guarded Rollout Gates

### Gate 0: Evidence Hygiene

Before any product claim:

- `docs/PRODUCT_WEDGE_DECISION.md` exists and names this single wedge.
- Every run records prompt, repo ref, request spec, candidate actions,
  validation, residual label, split, provenance, and zero hosted patch usage.
- `plans/active.md`, `plans/backlog.md`, and `plans/progress.md` agree on the
  active wedge tasks.

### Gate 1: Harness And Validation Preflight

Linked follow-ups: `REAL-002` and `DATA-005`.

Pass condition:

- At least `3/4` `REAL-001` repositories pass baseline setup and targeted
  validation from clean checkouts.
- At least one `DATA-004` issue/PR row can be checked out, setup-checked, and
  classified before edits.
- Failures are labeled as environment, validation, prompt/spec, ranking,
  materialization, or local knowledge blockers.
- Median baseline validation for scored real-repo tasks is `<= 180s`; no
  baseline validation exceeds `600s`.

Failing this gate blocks product work. The next task is harness repair or repo
replacement, not more action growth.

### Gate 2: Shadow Tests-Only Generalization

Linked follow-ups: `GS7-005`, `KNOW-002`, and `REAL-001`.

Pass condition:

- `pass@3 >= 3/4` on `REAL-001` tests-only tasks.
- `0` production-file modifications.
- `0` writes outside task allowlists.
- Hidden-like checks agree with public validation for every passing candidate.
- Every passing candidate uses a generic tests-only or repo-convention action
  family; no repo-specific branch is allowed.
- At least `3/4` tasks select the correct local test location and import style
  from repo-state evidence.

Passing this gate allows continued shadow runs and user-visible dry-run advice.
It does not yet allow automatic edits.

### Gate 3: Guarded Tests-Only Opt-In

Pass condition:

- Gate 2 passes twice: once on the initial ladder and once after either a new
  held-out small repo is added or one calibration repo is removed from scoring.
- The CLI presents the planned action, changed paths, validation commands,
  residual labels, and rollback path before applying changes.
- The run writes a transition record that can be replayed or audited.
- `git diff --check` and the task validation commands pass after applying the
  tests-only candidate.

Only after this gate should the product allow guarded local tests-only edits.

### Gate 4: Conservative Source Maintenance Remains Shadow-Only

Linked follow-ups: `MAT-002`, `GS7-006`, and `REAL-001` one-file feature tasks.

Pass condition before source edits can move beyond shadow:

- `MAT-002` can replace a bounded region inside one named function while
  preserving AST parseability, the function signature, import constraints,
  changed-line budget, and candidate-after diff metadata.
- `REAL-001` one-file feature gate passes: `pass@3 >= 2/4`, at least two
  repositories pass, no candidate edits more than one production file, and
  hidden-like checks agree with public validation.
- Source candidates remain bounded by allowlisted files and rollback is tested.

Until this gate passes, j3 may explain source maintenance candidates in shadow
mode, but it must not promise guarded production-source edits.

### Gate 5: Held-Out Ranking Before Routing

Linked follow-ups: `MODEL-003` through `MODEL-006`.

Pass condition:

- Ranker or scorer changes improve first-passing rank or `pass@1` on held-out
  real-repo tasks compared with deterministic ordering.
- There is zero `pass@3` regression on the same held-out set.
- The improvement is not limited to GreenShot or transition fixtures.
- The evidence uses repo-level splits and excludes hidden checks from training
  or prompt/action tuning.

Until this gate passes, transition ranking remains shadow-only.

## Failure And Pivot Criteria

Pivot away from this wedge or narrow it further if any of these happen after the
named proof tasks have completed:

- Action coverage explosion: more than `30%` of held-out failures require new
  bespoke action kinds, or a passing held-out task depends on a repo-name,
  path-name, or exact-prompt special case.
- Weak held-out generalization: after `GS7-005`, `REAL-002`, and one
  residual-driven repair cycle, tests-only `pass@3 < 3/4` while at least three
  baseline repos validate.
- Validation too slow or untrustworthy: fewer than three real repos have passing
  baselines, median scored runtime is `> 180s`, any successful task exceeds
  `600s`, or more than one hidden-like check disagrees with public validation.
- Ranker gains disappear outside fixtures: scorer work improves GreenShot or
  transition fixtures but does not improve first-passing rank or `pass@1` on
  held-out real-repo tasks, or it regresses `pass@3`.
- Knowledge acquisition is not usable data: `KNOW-002` cannot emit provenance,
  split, extraction, and evaluation records for pytest/package conventions, or
  product runs keep emitting unstructured local-knowledge explanations rather
  than machine-readable records.
- Source materialization stays unsafe: `MAT-002` cannot enforce AST parsing,
  signature preservation, line-budget limits, import constraints, and rollback
  for a bounded function-region edit.

If the tests-only path passes but source maintenance fails, keep the product as
tests-only and continue source work in shadow. If tests-only fails while
validation and local knowledge are solid, pivot to an even narrower product:
repo-local test placement and validation advice without editing files.

## Next Task Queue

Hardest proof tasks first:

1. `REAL-002`: build the real-repo eval ladder preflight runner. Proves pinned
   checkout, baseline setup, allowed write paths, timeouts, and JSONL outcomes.
2. `DATA-005`: build the issue/PR replay preflight runner for one `DATA-004`
   row. Separates environment and validation blockers from agent failures.
3. `GS7-005`: add tests-only existing-repo support for one-file libraries.
   First implementation slice for the selected product wedge.
4. `KNOW-002`: extract first wedge knowledge records from the completed
   `KNOW-001` inventory so tests-only planning can cite pytest layout, package
   layout, public imports, validation recipes, and pytest patterns.
5. `GS7-006`: add repo-state-aware library convention edits, limited to path,
   import, export, and local test-convention planning.
6. `MAT-002`: finish the constrained source-region materialization probe and
   keep it shadow-only until Gate 4 passes.
7. `REAL-003`: run the first tests-only wedge shadow score after `REAL-002`
   and `GS7-005` clear their blockers.
8. `MODEL-006`: add candidate-after or AST-delta observation for ranking
   evidence without changing production routing.
