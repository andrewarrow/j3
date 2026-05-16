# j3 Current Plan

This file is the live handoff for the next context window. Keep it compact.
Move long design notes into focused markdown files if they grow.

## Long-Term Goal

Build a local-first, no-LLM Python coding agent that can repair and improve
repositories by choosing structured edits, predicting their consequences,
validating with tools, and iterating toward passing tests.

The intended path is:

1. Reliable structured patch generation.
2. Strong candidate-outcome data from real repair attempts.
3. A trainable candidate ranker that beats handcrafted hint ordering on held-out
   tasks.
4. A repo-state and transition model that predicts which structured edit should
   move the repo toward a better observed state.
5. A bounded planning policy that can make multi-step repairs without free-form
   patch generation.

Do not start the main neural/JEPA track until the benchmark and outcome data can
separate missing actions, weak observations, bad ranking, and weak planning.

## Strategic Correction

GreenShot-5 was useful for tightening the repair loop. It is now too easy to
make progress look better by adding one handcrafted task and one handcrafted
action at a time.

The next phase should shift from toy ladder growth to held-out real-repo signal.
GreenShot-6 exists, but it is only a scaffold so far. The first GreenShot-6 task
is package-shaped, not proof that the system handles real packages.

Default next move:

- Prefer mutation-generated and git-history-derived tasks from real repos.
- Prefer dataset and validation tooling over broad action expansion.
- Add a new action only when a held-out task proves the candidate is missing.
- Improve hints/ranking when the right candidate exists but is late.

## Current State

Implemented repair loop capabilities:

- `j3 eval` supports ranked, baseline, and both phases.
- Eval output is task-level by default; candidate logs are behind `--verbose`.
- Eval diagnostics record tested candidates, passing candidates, first passing
  index, skipped phases, failure hints, target context, and exploration rows.
- `j3 eval --candidate-outcomes PATH` writes one row per tested candidate.
- `train-ranker` consumes diagnostics and candidate-outcome JSONL directly.
- `train-ranker` supports held-out task names and task families from the same
  input sources.
- Candidate outcome rows carry compact failure hints, target context, preferred
  patch labels, task families, scores, and pass labels.
- The patching code is split under `repair/patching/`; root `patching.py` is a
  compatibility shim.
- The planner supports bounded multi-step repair when a candidate changes the
  observed failure and exposes the next repair.

Implemented action families:

- `replace_expr`
- `insert_guard`
- `change_literal`
- `change_operator`
- `change_subscript_key`
- `change_dict_key`
- `change_dict_value`
- `add_dict_key`
- `swap_call_arg`
- `add_keyword_arg`
- `add_import`
- `add_import_fallback`
- `change_attribute`
- `change_module_constant`
- `wrap_try_except`
- `add_fallback_warning`
- `change_return_value`
- `rename_symbol`
- `modify_condition`
- `propagate_signature`

Implemented observation/hint parsing:

- Pytest failed node ids.
- Assertion comparisons and numeric deltas.
- Pytest `AssertionError: assert ... == ...` comparison lines.
- Traceback files, lines, and function frame context.
- `NameError`, `ImportError`, `ModuleNotFoundError`, `AttributeError`,
  `KeyError`, and TypeError argument names.
- Mypy and ruff diagnostics.
- Pytest warning `match=...` strings.

Recent work:

- GreenShot-5 reached 20 tasks.
- GreenShot-6 scaffold was added with a package-style metadata task.
- `change_dict_value` now covers dictionary literal value repairs.
- String assertion comparisons rank the preferred dictionary-value edit at rank
  1.
- Planner failure signatures now normalize parsed list/dict assertion values
  before using them for loop detection.

Last focused verification:

```bash
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_failure_hints.py tests/test_actions.py -q
pytest tests/test_candidate_ranking.py -q
python cli.py eval --tasks examples/greenshot_6 --timeout 10 --max-candidates 80 --phase ranked --quiet
git diff --check
```

GreenShot-6 scaffold result:

```text
ranked, no candidate ranker:
  solved=1/1 pass@1=1/1 avg_candidates=1.00
```

Treat this as a smoke check, not a benchmark claim.

## Next Right Things

### 1. Make GreenShot-6 Real

Goal: GreenShot-6 should use small real packages or real-package-derived
fixtures, not invented toy modules.

Next tasks:

- Add mutation-generated held-out tasks from real repos.
- Add git-history-derived held-out repair tasks.
- Mark every task with a task family and source type:
  - `handcrafted`
  - `mutation`
  - `git_history`
- Keep GreenShot-5 as the toy/helper regression ladder.
- Use GreenShot-6 for held-out package-style signal.

Good first implementation:

- Pick one small Python package already available locally or from mined
  transition data.
- Create 3 to 5 mutation-generated tasks that reuse existing action families.
- Do not add a new action unless a generated task exposes a true missing action.
- Report solved, pass@1, average candidates, and failure category.

### 2. Improve Outcome Dataset Quality

Goal: make candidate outcome rows useful for learning, validation, and later
transition modeling.

Next tasks:

- Add stable split metadata to outcome rows or a sidecar split file.
- Add `language` to candidate outcome rows.
- Add candidate diff size and edit locality features.
- Add before/after AST delta features.
- Record whether candidates are equivalent or overlapping.
- Add a command to summarize outcome datasets.

The dataset summary should report at least:

- rows
- tasks
- task families
- source types
- actions
- passing rows
- preferred-positive rows
- average candidates per task
- pass@1 by family and source type

### 3. Collect Hard Negatives

Goal: train on candidates the current system actually finds tempting.

Next tasks:

- Run GreenShot-5 and GreenShot-6 with `--explore-after-pass`.
- Save diagnostics and candidate outcomes.
- Summarize high-scoring failed candidates.
- Use those rows for ranker training and validation.
- Prefer held-out family/source-type validation over in-sample pass@1.

Use a command like:

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

Add a similar run for GreenShot-6 once it has real held-out tasks.

### 4. Strengthen Observations Before Model Complexity

Goal: ranker and future JEPA inputs should use normalized observations, not raw
test output text.

Next tasks:

- Parse pytest diff hunks into structured value differences.
- Extract expected/actual string fragments from substring failures.
- Extract mapping key/value expectations from assertion diffs.
- Compute traceback distance from each candidate target.
- Compute call graph distance from failing frame to candidate target.
- Record whether a candidate target is in test, public API, helper, model code,
  or config code.
- Add confidence/source fields to hints.
- Add tests for ambiguous or conflicting hints.

### 5. Only Then Expand Actions

Known missing or incomplete action families:

- Remove wrong keyword argument.
- Change call target to nearby helper.
- Replace attribute chain segment.
- Add simple branch case.
- Add early return for `None`.
- Add fallback for missing mapping key.
- Insert narrow exception handler around non-return statements.
- Propagate rename across multiple files.
- Update imports after symbol movement.
- Support bounded multi-edit actions.
- Deduplicate equivalent candidates before test execution.
- Store action schemas in a machine-readable registry.

Do not work this list top-down. Let held-out tasks choose the next action.

## Evaluation Rules

For benchmark-style reports, include:

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
- source-type pass@1
- average test runtime

For focused implementation checks, prefer the smallest relevant test:

```bash
pytest tests/test_failure_hints.py -q
pytest tests/test_candidate_ranking.py -q
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py -q
```

Run full `pytest -q` only as an intentional integration gate after broad shared
behavior changes or before merging.

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

## Stop Conditions

Pause action expansion when:

- pass@1 is not improving despite passing candidates existing.
- new tasks repeat existing action families without new signal.
- candidate generation grows faster than ranking quality.
- the next action is motivated only by a handcrafted fixture.

Pause ranker work when:

- diagnostics mostly show missing actions.
- hints are obviously wrong.
- outcome data has too few independent tasks.
- improvements come only from memorizing exact task or reason strings.

Start neural/JEPA work only when:

- GreenShot-5/6 include at least 50 diverse tasks.
- GreenShot-6 includes real-package-derived held-out tasks.
- Candidate outcomes include hundreds or thousands of labeled rows.
- Stable split metadata exists.
- Held-out task families and source types exist.
- A non-neural ranker has clearly plateaued.
- Failures are categorized well enough to diagnose neural regressions.

## Handoff Recommendation

The next context window should not add another handcrafted GreenShot task first.
It should make GreenShot-6 real by adding mutation-generated or git-history-
derived held-out tasks, then collect candidate outcomes with exploration and
summarize the dataset.
