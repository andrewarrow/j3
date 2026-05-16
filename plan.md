# j3 Current Plan

## Table of Contents

- [Goal](#goal)
- [Current Status](#current-status)
- [Near-Term Rule](#near-term-rule)
- [Pre-Neural Work](#pre-neural-work)
  - [Benchmark Ladder](#benchmark-ladder)
  - [Structured Action Space](#structured-action-space)
  - [Observations and Hints](#observations-and-hints)
  - [Candidate Outcome Data](#candidate-outcome-data)
  - [Ranker Before Neural](#ranker-before-neural)
  - [Architecture and Tooling](#architecture-and-tooling)
  - [Language Strategy](#language-strategy)
- [Neural Model Track](#neural-model-track)
  - [Trainable Candidate Ranker](#trainable-candidate-ranker)
  - [Repo-State Encoder](#repo-state-encoder)
  - [JEPA Transition Model](#jepa-transition-model)
  - [Planning Policy](#planning-policy)
- [Evaluation Standards](#evaluation-standards)
- [Immediate Next Tasks](#immediate-next-tasks)
- [Stop Conditions](#stop-conditions)

## Goal

Build a local, no-LLM Python coding agent that can eventually edit, repair,
refactor, and improve Python repositories at Codex-level quality. The target is
not autocomplete and not a patch-template toy. The target is an agent that can
read a repo, understand failing observations, choose structured edits, predict
their consequences, validate with tools, and iterate toward correct code without
asking a large language model to write candidate patches.

The long-term bar is intentionally high: become as good at Python code editing as
Codex running a frontier GPT-5.5-style model with high reasoning effort. The
path there is staged: first build reliable structured repair, then strong
candidate-ranking data, then trainable models, then a JEPA-style repo-transition
planner.

## Current Status

Recent completed work:

- [x] `j3 eval` defaults to ranked-only, task-level output.
- [x] Candidate-level eval logs are behind `--verbose`; `--quiet` is preserved.
- [x] Eval phases support `ranked`, `baseline`, and `both`.
- [x] Diagnostics record skipped phases, first passing index, passing candidates,
  and post-pass exploration counts.
- [x] `j3 eval --candidate-outcomes PATH` writes one JSONL row per tested
  candidate.
- [x] Failure hints no longer treat traceback `: in function_name` context as an
  exception type.
- [x] Candidate rankers can override hint ordering.
- [x] GreenShot-5 includes a helper-boundary wrong dictionary key task.
- [x] The wrong dictionary/subscript key loop is closed with
  `change_subscript_key`.
- [x] Candidate-ranker training now learns from failed candidates after the first
  pass in exploration diagnostics.
- [x] The patching implementation was split from one large `patching.py` file
  into focused modules under `repair/patching/`; root `patching.py` remains a
  compatibility shim.
- [x] GreenShot-5 includes a helper-module wrong default value task.
- [x] `train-ranker` can consume candidate outcome JSONL directly.
- [x] GreenShot-5 includes a nested-module missing import task with a decoy
  local import.
- [x] GreenShot-5 includes exception handling through a wrapper API.
- [x] GreenShot-5 includes swapped arguments across modules.
- [x] GreenShot-5 includes rename propagated through a helper and public API.
- [x] GreenShot-5 includes a multi-pass boundary task where the preferred edit
  is in a helper rather than a narrow public API default.
- [x] GreenShot-5 includes a caller-side string/mode literal repair where the
  traceback runs through a helper.
- [x] Candidate outcome rows carry compact target context and preferred-patch
  labels for tasks that define them.
- [x] GreenShot-5 task manifests carry task-family labels, and diagnostics,
  candidate outcome rows, and ranker metrics report per-task-family signal.
- [x] `train-ranker` can score held-out diagnostics/outcome files after training
  and reports validation pass@1, preferred-positive rank, calibration, and
  per-family slices.
- [x] GreenShot-5 includes a bounded multi-step task where the first repair
  changes the observed failure and exposes the second repair.
- [x] GreenShot-5 includes an Apache-mined serialized payload task where the
  repair adds a missing dictionary output key.
- [x] The missing dictionary output-key loop is covered with `add_dict_key`.
- [x] GreenShot-5 includes an Apache-mined timeout propagation task where the
  repair adds a missing keyword argument through a helper call.
- [x] GreenShot-5 includes an Apache-mined required-setting fallback task where
  the repair replaces a hard `ValueError` with a default plus warning.
- [x] The fallback-plus-warning loop is covered with `add_fallback_warning`, and
  pytest warning `match=...` text is parsed into compact expected-string hints.

Current GreenShot-5 signal:

```text
ranked, no candidate ranker after adding the caller-side string/mode literal task:
  solved=12/12 pass@1=8/12 avg_candidates=1.58

ranked, no candidate ranker after adding the multi-step revealed-failure task:
  solved=13/13 pass@1=8/13 avg_candidates=1.62

ranked, legacy diagnostics candidate ranker:
  solved=9/9 pass@1=5/9 avg_candidates=1.56

ranked, stale outcome-trained candidate ranker artifact:
  solved=9/9 pass@1=5/9 avg_candidates=1.44

ranked, fresh outcome-trained candidate ranker with v3 hint context/locality features:
  solved=9/9 pass@1=8/9 avg_candidates=1.11

ranked, 10-task v4 target-context ranker evaluated after adding the held-out
express-shipping task:
  solved=11/11 pass@1=10/11 avg_candidates=1.09

ranked, fresh 11-task preferred-aware v4 outcome ranker:
  solved=11/11 pass@1=11/11 avg_candidates=1.00

ranked, Apache checkpoint after adding the missing serialized payload key task:
  solved=14/14 pass@1=9/14 avg_candidates=1.64

ranked, Apache checkpoint after adding the timeout keyword passthrough task:
  solved=15/15 pass@1=10/15 avg_candidates=1.67

ranked, Apache checkpoint after adding the fallback-plus-warning task:
  solved=16/16 pass@1=11/16 avg_candidates=1.62

ranked, Apache checkpoint after adding the duplicate-side-effect state-flag
guard task:
  solved=17/17 pass@1=12/17 avg_candidates=1.29
```

Current interpretation:

- The action-generation loop is improving: the latest wrapper-exception ladder
  task was added, the right candidate was generated, and full-budget eval solves
  it at rank 1.
- The repair loop now supports task-level bounded multi-step planning. The first
  GreenShot-5 multi-step task is solved by applying a missing import, reparsing
  the new failure, then changing the caller-side mode literal.
- The serialized payload missing-key task is action-covered by `add_dict_key`;
  KeyError hints rank the preferred helper serializer edit at rank 1.
- The timeout keyword passthrough task is action-covered by `add_keyword_arg`;
  helper-call signature context ranks the public API passthrough edit at rank 1.
- The required-setting fallback task is action-covered by
  `add_fallback_warning`; warning `match=...` text distinguishes the preferred
  default value from decoy fallback candidates and ranks it at rank 1.
- The duplicate-side-effect state-flag task is action-covered by a generalized
  `insert_guard` candidate that recognizes module-level list side effects and
  related `False` state flags; call-graph hint scoring ranks the helper guard at
  rank 1 from the public wrapper assertion.
- The swapped-arguments-across-modules task is action-covered by
  `swap_call_arg`; hint-only ranking solves it at rank 1. A ranker trained from
  old pre-hint outcome rows buries it, which confirms that current outcome data
  needs serialized hint context.
- The public-API signature propagation task is action-covered by
  `propagate_signature`; imported helper keyword context lets the generator
  propose the helper parameter rename, and hint-only ranking solves it at rank 1.
- The wrong-default task is solved by an existing `change_literal` candidate on
  the helper-module default parameter, so it is ranking/hint signal rather than
  a missing action.
- The nested import task generates both the correct local import and a decoy
  local import. Full-budget eval solves it, but the correct candidate is second,
  so this is locality/ranking signal rather than a missing action.
- Candidate-ranker v2 features remove exact reason strings, exact target
  symbols, and arbitrary exact param values from the learned feature set. This
  fixes the prior `quote_total_helper_discount` ranker miss without adding a
  task-specific rule.
- Candidate-ranker v3 outcome rows carry compact failure hints, and the ranker
  has generalized hint-context/locality features for candidate token overlap,
  TypeError name direction, import package locality, and whether a candidate has
  any structured hint support. Fresh 9-task outcome data gets to 8/9 pass@1
  in-sample.
- Candidate-ranker v4 adds compact target context and generic call-graph
  distance features. A 10-task v4 ranker moves the new held-out express-shipping
  task's preferred helper edit ahead of public API default edits, but still ranks
  one wrong helper operator before the preferred `>=` edit.
- Preferred-patch metadata is now available in task manifests and outcome rows,
  and outcome-ranker training uses a marked preferred passing patch as the
  positive example when one exists.
- The outcome-trained ranker signal is still tiny and partly in-sample. Treat it
  as a sign that current misses are ranking/context failures, not evidence of
  broad Python-editing competence.
- The benchmark is still tiny. It is good for tight iteration, not evidence of
  broad Python-editing competence.

## Near-Term Rule

Every new benchmark task must create a clear learning opportunity.

- If no candidate exists, add the smallest structured action that covers it.
- If a candidate exists but is late, improve ranking data/features.
- If hints are wrong, fix observation parsing before adding model complexity.
- If multiple patches pass, record that explicitly and decide which is better.
- Do not add repeated examples that only inflate solved counts.

## Pre-Neural Work

This is the current phase. Do not start the main neural model until this section
has enough coverage and data to make neural regressions visible.

### Benchmark Ladder

- [x] GreenShot-2/3/4 cover single-file structured repairs.
- [x] GreenShot-5 starts multi-file helper/API repair.
- [x] GreenShot-5 includes helper-boundary dictionary key repair.
- [x] Add wrong default/config constant in a separate module.
- [x] Add nested-module missing import with at least one decoy import.
- [x] Add exception handling through a wrapper API.
- [x] Add swapped arguments across modules.
- [x] Add rename propagated through helper and public API.
- [x] Add a task with two passing patches where one is semantically preferable.
- [x] Add a task where the correct edit is in a caller, not the failing frame.
- [x] Add a task where the correct edit is in a callee, not the public API.
- [x] Add a task where tests expose an error only after one repair is applied.
- [x] Add Apache-mined GreenShot-5 task: missing dictionary/output key in a
  serialized payload.
- [ ] Grow GreenShot-5 to at least 20 tasks before neural ranker work.
- [x] Add Apache-mined GreenShot-5 task: missing keyword argument propagated
  through a call chain.
- [x] Add Apache-mined GreenShot-5 task: hard failure replaced by a
  default/fallback plus warning.
- [x] Add Apache-mined GreenShot-5 task: guard that prevents duplicate side
  effects with a state flag.
- [ ] Add Apache-mined GreenShot-5 task: import compatibility fallback from a
  new package path to an old package path.
- [ ] Add Apache-mined GreenShot-5 task: module-level config constant repair.
- [ ] Create GreenShot-6 for small real packages, not only toy fixtures.
- [ ] Add mutation-generated held-out tasks from real repos.
- [ ] Add git-history-derived held-out repair tasks.
- [ ] Track benchmark task families so train/test leakage is visible.

### Structured Action Space

- [x] `replace_expr`
- [x] `insert_guard`
- [x] `change_literal`
- [x] `change_operator`
- [x] `change_subscript_key`
- [x] `swap_call_arg`
- [x] `add_import`
- [x] `change_attribute`
- [x] `wrap_try_except`
- [x] `rename_symbol`
- [x] `modify_condition`
- [x] `propagate_signature`
- [ ] Change dictionary literal key.
- [ ] Change dictionary literal value.
- [x] Add missing dictionary key/default.
- [x] Change function default parameter value.
- [ ] Change module-level config constant.
- [x] Add missing keyword argument.
- [ ] Remove wrong keyword argument.
- [ ] Change call target to nearby helper.
- [ ] Replace attribute chain segment.
- [x] Replace enum/string mode value.
- [ ] Add simple branch case.
- [ ] Add early return for `None`.
- [ ] Add fallback for missing mapping key.
- [x] Add fallback plus warning for a missing optional setting.
- [ ] Insert narrow exception handler around non-return statements.
- [ ] Propagate rename across multiple files.
- [ ] Update imports after symbol movement.
- [ ] Support multi-edit actions with bounded, typed edit lists.
- [ ] Deduplicate equivalent candidates before test execution.
- [ ] Store action schemas in a machine-readable registry.

Apache-mined action examples to prioritize:

- `data/transitions/apache-python/Chainlit__chainlit.jsonl`: widget output adds a
  missing `"disabled"` key; step serialization moves an optional `icon` into
  metadata.
- `data/transitions/apache-python/Lightning-AI__litgpt.jsonl`: JSON data setup
  replaces a required setting error with a fallback default and warning; server
  code propagates a new timeout keyword.
- `data/transitions/apache-python/Chainlit__chainlit.jsonl`: socket startup adds
  an idempotence guard around chat-start hooks; cache setup adds import-path
  compatibility fallback.

### Observations and Hints

- [x] Parse pytest failed node ids.
- [x] Parse assertion comparisons and numeric deltas.
- [x] Parse traceback source files and lines.
- [x] Parse `NameError`, `ImportError`, `ModuleNotFoundError`, `AttributeError`,
  `KeyError`, and TypeError argument names.
- [x] Parse mypy and ruff diagnostics.
- [x] Keep traceback frame context separate from exception type.
- [ ] Parse pytest diff hunks into structured value differences.
- [ ] Extract expected/actual string fragments from substring failures.
- [ ] Extract mapping key/value expectations from assertion diffs.
- [ ] Compute traceback distance from each candidate target.
- [ ] Compute call graph distance from failing frame to candidate target.
- [ ] Record whether candidate target is in test, public API, helper, or model
  code.
- [ ] Parse stdout/stderr clues without relying on raw text embeddings.
- [ ] Preserve tool outputs in compact normalized records.
- [ ] Add confidence/source fields to each hint.
- [ ] Add tests for ambiguous or conflicting hints.

### Candidate Outcome Data

- [x] Eval diagnostics record tested candidates, pass labels, scores, hints, and
  first passing index.
- [x] Exploration mode tests bounded candidates after first pass.
- [x] Candidate outcome JSONL writes one row per tested candidate.
- [x] Diagnostics ranker can learn from post-pass failed candidates.
- [x] Teach `train-ranker` to consume `--candidate-outcomes PATH` directly.
- [ ] Include before/after AST delta features in outcome rows.
- [x] Include compact target context in outcome rows.
- [x] Include failing observation features in outcome rows.
- [ ] Include candidate diff size and edit locality.
- [ ] Include whether candidates are equivalent or overlapping.
- [x] Include multiple-passing-candidate groups.
- [x] Mark preferred patch when multiple patches pass.
- [ ] Export datasets with stable split metadata.
- [ ] Add a command to summarize outcome datasets.
- [ ] Add a command to compare ranker behavior across two diagnostics files.

### Ranker Before Neural

- [x] Lightweight diagnostics ranker exists.
- [x] Ranker can override handcrafted hint score.
- [x] GreenShot-5 ranker improves pass@1 from 3/7 to 5/7 on full-budget ranked
  eval when trained from in-sample candidate outcomes.
- [x] Train ranker from candidate outcome JSONL.
- [x] Add per-action and per-task-family ranker metrics.
- [x] Add calibration reporting, not just pairwise accuracy.
- [ ] Penalize over-memorized reason/action strings when they regress other task
  families.
- [ ] Add feature ablation reporting.
- [x] Add cross-benchmark validation: train on GreenShot-5 subset, test on held
  out tasks.
- [ ] Add a baseline ranker that uses only hints and model scores.
- [ ] Add a learned ranker that uses AST delta/context features.
- [ ] Add hard-negative mining from high-scoring failed candidates.
- [ ] Add candidate deduplication before ranking.

### Architecture and Tooling

- [x] Split patching code into `repair/patching/{types,model,generation,ranking,planner,ast_utils}.py`.
- [x] Keep root `patching.py` compatibility exports.
- [ ] Move candidate-ranker code into `repair/ranking/` or similar cohesive
  package.
- [ ] Move evaluation diagnostics/outcome schema into a dedicated module.
- [ ] Add schema versioning for diagnostics and outcome JSONL.
- [ ] Add typed records for hints and candidate outcomes.
- [ ] Add a small command for inspecting one task's top candidates.
- [ ] Add a command to replay one candidate outcome row.
- [ ] Add regression tests for public imports after module splits.
- [ ] Keep README small; put detailed design in focused markdown files.

### Language Strategy

Python-first is intentional. The project should prove the full repair loop in
one language before expanding to JavaScript, Go, or others. That does not paint
the project into a Python-only corner as long as the model-facing records stay
language-neutral and Python-specific code remains in adapters.

Keep portable:

- [ ] Candidate outcome rows should include `language`.
- [ ] Core records should use portable fields: `file_path`, `span`,
  `node_kind`, `symbol`, `action`, `params`, `observation`, `passed`.
- [ ] Action concepts should stay language-neutral where possible:
  change literal, change call argument, add import, rename symbol, change field
  or key, modify condition.
- [ ] Evaluation should stay command/tool based. Pytest is the Python adapter,
  not the core abstraction.
- [ ] The future JEPA layer should consume normalized repo/action/observation
  records, not raw Python AST objects.

Keep language-specific:

- [ ] Python AST parsing and patch materialization.
- [ ] Pytest failure parsing.
- [ ] Python import/name/attribute semantics.
- [ ] Python benchmark fixtures.

Eventually reshape modules toward:

```text
repair/
  core/
    actions
    candidates
    outcomes
    diagnostics
    ranking
    planning
  languages/
    python/
      parser
      generator
      test_hints_pytest
    javascript/
      parser
      generator
      test_hints_jest
    go/
      parser
      generator
      test_hints_go_test
```

Do not do this extraction too early. First make the Python loop strong enough
that the core abstractions are earned by real use, not guessed upfront.

## Neural Model Track

Start this only after GreenShot-5/6 and candidate-outcome data are broad enough
to distinguish missing actions, weak observations, and bad ranking.

### Trainable Candidate Ranker

- [ ] Define tensorized candidate-outcome dataset.
- [ ] Encode structured action kind, params, target node, and target context.
- [ ] Encode parsed observations, not raw pytest text.
- [ ] Encode AST before/after deltas.
- [ ] Train a small local model to score candidate pass probability.
- [ ] Compare against handcrafted and linear rankers.
- [ ] Track pass@1, avg candidates, and calibration.
- [ ] Validate on held-out task families.
- [ ] Export a stable local model artifact.

### Repo-State Encoder

- [ ] Define repo graph: files, imports, functions, classes, calls, tests.
- [ ] Build compact AST/token embeddings for Python files.
- [ ] Cache repo-state embeddings locally.
- [ ] Incrementally update embeddings after structured edits.
- [ ] Encode failing observations against repo graph nodes.
- [ ] Represent candidate target context without full-source prompting.
- [ ] Add nearest-neighbor search over prior transition examples.

### JEPA Transition Model

- [ ] Define latent state `s(repo, observation)`.
- [ ] Define structured action embedding `a(edit, target, params)`.
- [ ] Train prediction of next latent state or repaired-state delta.
- [ ] Train with synthetic transitions, mined git transitions, and validated
  candidate outcomes.
- [ ] Add negative examples from failed candidates.
- [ ] Predict which observation should improve after an edit.
- [ ] Compare predicted utility against actual pytest validation.
- [ ] Use transition predictions to rank candidates before running tests.

### Planning Policy

- [ ] Move from one-shot repair to multi-step planning.
- [ ] After a candidate changes the failure, reparse observations and continue.
- [ ] Stop on passing tests, repeated failures, or low confidence.
- [ ] Track action history to avoid loops.
- [ ] Prefer smaller semantically local edits when confidence is similar.
- [ ] Support test selection and rerun planning.
- [ ] Generate explanations from structured evidence, not language-model prose.
- [ ] Add a human review mode for multi-edit plans.

## Evaluation Standards

Report these for benchmark refreshes:

- solved / total
- pass@1
- average candidates tested
- median candidates tested
- missing-action count
- bad-ranking count
- weak-hint count
- multiple-passing-candidate count
- per-action pass@1
- per-task-family pass@1
- average test runtime

Use focused checks while editing:

```bash
pytest tests/test_failure_hints.py -q
pytest tests/test_candidate_ranking.py -q
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py -q
```

Use GreenShot-5 for active ranking/action work:

```bash
python cli.py eval \
  --tasks examples/greenshot_5 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --quiet
```

Use exploration when collecting ranker data:

```bash
python cli.py eval \
  --tasks examples/greenshot_5 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/apache-python-git/greenshot-5-explore-diagnostics.json \
  --candidate-outcomes runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl \
  --quiet
```

Use GreenShot-4 only as a periodic regression/reporting gate:

```bash
python cli.py eval \
  --tasks examples/greenshot_4 \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10 \
  --phase both \
  --quiet \
  --diagnostics runs/apache-python-git/greenshot-4-diagnostics.json
```

Run full pytest before broad merges:

```bash
pytest -q
```

## Immediate Next Tasks

1. [x] Add a compact diagnostics comparison command.
   - Compare two diagnostics files.
   - Show per-task rank movement, pass@1 changes, bad-ranking changes, and top
     failed candidate reasons.

2. [x] Add the next GreenShot-5 ladder task.
   - Nested-module missing import with a decoy import is done.
   - Exception handling through a wrapper API is done.
   - Swapped arguments across modules is done.
   - Rename propagated through helper and public API is done.

3. Validate ranker calibration beyond in-sample GreenShot-5.
   - The legacy diagnostics ranker solves 9/9 full-budget and 5/9 pass@1.
   - The stale outcome-ranker artifact solves 9/9 full-budget and 5/9 pass@1.
   - A fresh v3 outcome ranker trained from 9-task exploration rows solves 9/9
     full-budget and 8/9 pass@1 in-sample.
   - A v3 ranker trained from old pre-hint outcome rows solves 9/9 full-budget
     but only 6/9 pass@1 and ranks the new swapped-argument task 16th.
   - Target-context/call-graph features now distinguish helper edits that are
     downstream of hinted public API functions from direct public API edits.
   - A v4 ranker trained before the express-shipping task was added solves the
     expanded 11-task set at 10/11 pass@1; the held-out express task is solved
     at rank 2 by the preferred helper operator edit.
   - Fresh preferred-aware 11-task outcome data solves 11/11 at pass@1
     in-sample.
   - GreenShot-5 now records explicit task families so held-out calibration can
     be sliced by family instead of relying on task names alone.
   - Next ranker work should focus on held-out calibration and operator/value
     preference, because the remaining held-out miss is a wrong helper operator
     ranked just ahead of the preferred `>=` edit.

## Stop Conditions

Pause action-space expansion when:

- pass@1 is not improving despite passing candidates existing.
- new tasks repeat existing action families without adding new signal.
- candidate generation explodes faster than ranking quality improves.

Pause ranker work when:

- diagnostics mostly show missing actions.
- hints are obviously wrong.
- outcome data has too few independent tasks.
- improvements come only from memorizing exact task-specific reason strings.

Start neural work only when:

- GreenShot-5/6 include at least 50 diverse tasks.
- candidate outcomes include hundreds or thousands of labeled rows.
- held-out task families exist.
- a non-neural ranker has clearly plateaued.
- failures are categorized well enough to diagnose neural regressions.
