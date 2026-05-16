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

Current GreenShot-5 signal:

```text
ranked, no candidate ranker:
  solved=5/5 pass@1=2/5 avg_candidates=1.80

ranked, diagnostics candidate ranker:
  solved=5/5 pass@1=3/5 avg_candidates=1.40
```

Current interpretation:

- The action-generation loop is improving: the latest missing action was found,
  implemented, and verified.
- The ranker is useful but still shallow. It improves pass@1 on GreenShot-5, but
  the remaining max-candidate-1 misses are ranking calibration failures, not
  missing actions.
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
- [ ] Add wrong default/config constant in a separate module.
- [ ] Add nested-module missing import with at least one decoy import.
- [ ] Add exception handling through a wrapper API.
- [ ] Add swapped arguments across modules.
- [ ] Add rename propagated through helper and public API.
- [ ] Add a task with two passing patches where one is semantically preferable.
- [ ] Add a task where the correct edit is in a caller, not the failing frame.
- [ ] Add a task where the correct edit is in a callee, not the public API.
- [ ] Add a task where tests expose an error only after one repair is applied.
- [ ] Grow GreenShot-5 to at least 20 tasks before neural ranker work.
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
- [ ] Add missing dictionary key/default.
- [ ] Change function default parameter value.
- [ ] Change module-level config constant.
- [ ] Add missing keyword argument.
- [ ] Remove wrong keyword argument.
- [ ] Change call target to nearby helper.
- [ ] Replace attribute chain segment.
- [ ] Replace enum/string mode value.
- [ ] Add simple branch case.
- [ ] Add early return for `None`.
- [ ] Add fallback for missing mapping key.
- [ ] Insert narrow exception handler around non-return statements.
- [ ] Propagate rename across multiple files.
- [ ] Update imports after symbol movement.
- [ ] Support multi-edit actions with bounded, typed edit lists.
- [ ] Deduplicate equivalent candidates before test execution.
- [ ] Store action schemas in a machine-readable registry.

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
- [ ] Teach `train-ranker` to consume `--candidate-outcomes PATH` directly.
- [ ] Include before/after AST delta features in outcome rows.
- [ ] Include compact target context in outcome rows.
- [ ] Include failing observation features in outcome rows.
- [ ] Include candidate diff size and edit locality.
- [ ] Include whether candidates are equivalent or overlapping.
- [ ] Include multiple-passing-candidate groups.
- [ ] Mark preferred patch when multiple patches pass.
- [ ] Export datasets with stable split metadata.
- [ ] Add a command to summarize outcome datasets.
- [ ] Add a command to compare ranker behavior across two diagnostics files.

### Ranker Before Neural

- [x] Lightweight diagnostics ranker exists.
- [x] Ranker can override handcrafted hint score.
- [x] GreenShot-5 ranker improves pass@1 from 2/5 to 3/5 on full-budget ranked
  eval.
- [ ] Train ranker from candidate outcome JSONL.
- [ ] Add per-action and per-task-family ranker metrics.
- [ ] Penalize over-memorized reason/action strings when they regress other task
  families.
- [ ] Add feature ablation reporting.
- [ ] Add calibration reporting, not just pairwise accuracy.
- [ ] Add cross-benchmark validation: train on GreenShot-5 subset, test on held
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
  --checkpoint runs/mit-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --quiet
```

Use exploration when collecting ranker data:

```bash
python cli.py eval \
  --tasks examples/greenshot_5 \
  --checkpoint runs/mit-python-git/model.json \
  --timeout 10 \
  --max-candidates 80 \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/mit-python-git/greenshot-5-explore-diagnostics.json \
  --candidate-outcomes runs/mit-python-git/greenshot-5-candidate-outcomes.jsonl \
  --quiet
```

Use GreenShot-4 only as a periodic regression/reporting gate:

```bash
python cli.py eval \
  --tasks examples/greenshot_4 \
  --checkpoint runs/mit-python-git/model.json \
  --timeout 10 \
  --phase both \
  --quiet \
  --diagnostics runs/mit-python-git/greenshot-4-diagnostics.json
```

Run full pytest before broad merges:

```bash
pytest -q
```

## Immediate Next Tasks

1. Add the next GreenShot-5 ladder task: wrong default value or config constant
   in a separate module.
   - Keep it small and diagnostic.
   - The failing test should distinguish action-generation failure from ranking
     failure.
   - The correct edit should not be in the public API wrapper.

2. Close the loop for that task.
   - Generate the right structured candidate.
   - Parse/prioritize the observation.
   - Verify GreenShot-5 solves with full budget.
   - Regenerate diagnostics and candidate outcomes.
   - Record whether the remaining problem is missing action, weak hint, or bad
     ranking.

3. Teach `train-ranker` to consume candidate outcome JSONL directly.
   - Add `--candidate-outcomes PATH`.
   - Keep `--diagnostics` compatibility.
   - Report rows, passing rows, failing rows, tasks, and training pairs.
   - Prefer outcome JSONL for new experiments.

4. Improve ranker calibration.
   - The current diagnostics ranker solves 5/5 full-budget but only 3/5 pass@1.
   - Investigate the two remaining max-candidate-1 misses before adding many
     more tasks.
   - Avoid overfitting to exact action/reason strings when hint and context
     features should generalize.

5. Add a compact diagnostics comparison command.
   - Compare two diagnostics files.
   - Show per-task rank movement, pass@1 changes, bad-ranking changes, and top
     failed candidate reasons.

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
