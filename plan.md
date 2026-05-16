# j3 Recovery Plan

This plan resets the project around the long-term goal:

> Build a no-LLM Python coding agent that learns repo-state consequences of
> structured edits, ranks repair actions from observations, and validates with
> tests.

The current prototype has useful pieces, but it is drifting toward benchmark
heuristics and noisy exhaustive candidate testing. The next work should make
the system produce better learning signal, not just more hand-written fixes.

## Progress Update

Done:

- Synced durable guidance into `AGENTS.md`: learning-signal priority,
  GreenShot-5 as the near-term ladder, task-level eval output by default, and
  candidate-level eval logs behind `--verbose`.
- Completed Immediate Change 1. `j3 eval` now keeps `--quiet`, adds
  `--verbose`, prints task-level progress by default, and suppresses
  candidate-level planning/testing chatter unless verbose mode is enabled.
- Added CLI coverage for default eval output, verbose eval output, and quiet
  eval output.
- Completed Immediate Change 2. `j3 eval` now supports
  `--phase ranked|both|baseline`, defaults to ranked-only CLI evals, and records
  skipped phases explicitly in summaries and diagnostics.
- Added coverage for ranked-only baseline skipping, both-phase summary output,
  and diagnostics for skipped phases.
- Completed Immediate Change 3. Failure hint parsing now treats traceback
  `: in function_name` frame context as a function name, not an exception type,
  and only records exception-looking traceback context as `exception_type`.
- Added coverage for traceback frame context plus later `TypeError` output.
- Completed Immediate Change 4. Candidate rankers now sort primarily by
  `ranker_score`, then `failure_hint_score`, then `model_score`, while
  no-ranker hint prioritization keeps the existing hint-first ordering.
- Added coverage for ranker-over-hint ordering and preserved no-ranker ordering.
- Completed Immediate Change 5. `j3 eval --explore-after-pass N` now tests a
  bounded number of additional candidates after the first pass and diagnostics
  record first-pass index, passing candidates, and before/after-pass counts.
- Added focused eval and diagnostics coverage for post-pass exploration.
- Completed Immediate Change 6. `j3 eval --candidate-outcomes PATH` now writes
  candidate outcome JSONL with one row per tested candidate, including rank
  index, pass labels, first-pass index, and multiple-pass context.
- Added focused evaluation and CLI coverage for candidate outcome export.
- Completed Immediate Change 7. GreenShot-5 now includes
  `order_customer_name_dict_key_helper`, a helper-boundary wrong-dictionary-key
  task that currently exposes a missing action.
- Added focused task-manifest coverage for the new GreenShot-5 task.
- Completed Immediate Change 8. Regenerated GreenShot-5 exploration
  diagnostics, trained a fresh diagnostics ranker, and evaluated it against
  GreenShot-5.
- The refreshed ranker improved GreenShot-5 pass@1 from 1/5 to 2/5 while
  preserving full-budget solved count at 4/5; the remaining unsolved task is
  still diagnosed as a missing action.
- Completed Immediate Change 9. Added `plan.md` as a short pointer to this live
  recovery plan without expanding the README.
- Completed the GreenShot-5 wrong dictionary/subscript key loop. Added a
  `change_subscript_key` structured action, generated replacement keys from repo
  string literals, and used `KeyError`/traceback/assertion hints to prioritize
  subscript-key repairs.
- Updated candidate-ranker training to learn from post-pass exploration
  failures, so pass-at-1 tasks can still contribute positive-vs-failed pairs.
- Regenerated GreenShot-5 exploration diagnostics, candidate outcome JSONL, and
  the diagnostics ranker after adding the subscript-key action.
- GreenShot-5 full-budget ranked eval now solves 5/5; ranker pass@1 improved to
  3/5, with the remaining max-candidate-1 misses classified as ranking
  calibration rather than missing actions.

Verified:

```bash
pytest tests/test_cli.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_failure_hints.py -q
pytest tests/test_patching.py tests/test_candidate_ranking.py -q
python -m py_compile patching.py evaluation.py cli.py tests/test_evaluation.py tests/test_cli.py
python -m py_compile examples/greenshot_5/shop/api.py examples/greenshot_5/shop/orders.py examples/greenshot_5/tests/test_shop.py tests/test_evaluation.py
python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --timeout 10 --max-candidates 80 --phase ranked --explore-after-pass 5 --diagnostics runs/mit-python-git/greenshot-5-explore-diagnostics.json --candidate-outcomes runs/mit-python-git/greenshot-5-candidate-outcomes.jsonl --quiet
python cli.py train-ranker --diagnostics runs/mit-python-git/greenshot-5-explore-diagnostics.json --out runs/mit-python-git --epochs 12 --learning-rate 0.25
python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --ranker runs/mit-python-git/candidate-ranker.json --timeout 10 --max-candidates 1 --phase ranked --diagnostics runs/mit-python-git/greenshot-5-ranker-smoke-diagnostics.json --quiet
python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --ranker runs/mit-python-git/candidate-ranker.json --timeout 10 --max-candidates 80 --phase ranked --diagnostics runs/mit-python-git/greenshot-5-ranker-diagnostics.json --quiet
pytest tests/test_candidate_ranking.py tests/test_patching.py -q
python -m py_compile actions.py patching.py candidate_ranking.py tests/test_patching.py tests/test_candidate_ranking.py
python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --timeout 10 --max-candidates 80 --phase ranked --diagnostics runs/mit-python-git/greenshot-5-subscript-smoke-diagnostics.json --quiet
```

Observed GreenShot-5 ranked smoke with `--max-candidates 1` now reports 5
tasks, solves 3/5 with the refreshed diagnostics ranker, and leaves the two
remaining failures as ranking misses rather than missing actions.

Next:

- Add the next GreenShot-5 ladder task: wrong default value or config constant
  in a separate module.
- Keep the task small enough to diagnose action generation vs. ranking clearly.
- After adding it, close the loop the same way: generate the action, prioritize
  it from structured observations, verify the task, and regenerate diagnostics.

## Current Diagnosis

The good parts:

- Structured candidate generation and deterministic materialization work.
- Pytest validation in temporary repos works.
- Failure hints clearly reduce wasted testing on GreenShot-4.
- Diagnostics now expose candidate order, scores, reasons, and pass/fail labels.
- GreenShot-5 is a better benchmark direction because it starts to require
  multi-file reasoning.
- Eval output and phase selection are now usable for day-to-day work.
- Exploration diagnostics and candidate outcome JSONL now provide the right
  shape of data for ranker training.

The current blockers:

- The refreshed GreenShot-5 ranker solves 5/5 with full budget and improves
  pass@1 to 3/5, but the remaining misses show that exact action/reason
  memorization can still outrank stronger task-specific hints.
- `--candidate-outcomes` exports one row per tested candidate, while
  `train-ranker` still reads diagnostics. The trainer now uses post-pass
  exploration failures from diagnostics, but it does not yet consume the JSONL
  outcome stream directly.
- GreenShot-5 is still too small for neural work. It should keep growing, but
  only after each new missing-action fixture has been closed or clearly
  classified.

## Principle

Do not optimize for "eventually passes after many tests." Optimize for:

1. The correct action is generated.
2. The correct target is represented.
3. The observation is parsed into useful structured evidence.
4. The ranker puts the passing candidate near the top before validation.
5. Diagnostics explain whether failure was missing action, bad ranking, weak
   hints, or insufficient repo context.

That is the path toward a JEPA-style coding agent. Exhaustive pytest search is
only a label generator and safety check.

## Immediate Changes

### 1. Make Eval Output Less Repetitive

Status: done. Implemented in `cli.py` with `--verbose` and summary progress
filtering. Covered by focused CLI tests.

Change `cli.py` and `evaluation.py` so normal eval output is task-level, not
candidate-level.

Implement:

- Keep `--quiet`.
- Add `--verbose` for current per-candidate progress.
- Make default progress print only:
  - eval start
  - task start
  - baseline summary
  - ranked summary
  - final totals
- Keep candidate-level lines available only under `--verbose`.

Suggested implementation:

- In `cli.py`, replace the single `_progress` callback with two callbacks:
  - `_summary_progress(message: str)`
  - `_verbose_progress(message: str)`
- Add a small helper that filters messages. Summary mode should suppress
  messages beginning with:
  - `baseline: running`
  - `baseline: exit`
  - `candidates:`
  - `rank:`
  - `hints:`
  - `test: candidate=`
  - `selected:`
  - `status: no passing candidate`
- `--verbose` should use the current unfiltered callback.

Tests to add:

- A CLI test that runs a tiny eval with default progress and asserts that
  `test: candidate=` is not printed.
- A CLI test that runs the same eval with `--verbose` and asserts that
  `test: candidate=` is printed.
- A CLI test that `--quiet` still suppresses progress lines.

Keep these tests small. Use `examples/greenshot_bug` or `examples/greenshot_3`
with `--max-candidates 1`, not GreenShot-4.

### 2. Add a Ranked-Only Eval Mode

Status: done. Implemented in `cli.py` and `evaluation.py`; skipped phases are
represented as `skipped` in CLI summaries and as `"skipped": true` in
diagnostics. Covered by focused CLI and evaluation tests.

The unhinted baseline is useful, but it should not run every time.

Add an eval phase selector:

```bash
python cli.py eval --tasks examples/greenshot_5 --phase ranked
python cli.py eval --tasks examples/greenshot_5 --phase both
python cli.py eval --tasks examples/greenshot_5 --phase baseline
```

Recommended defaults:

- `--phase both` for benchmark refreshes and diagnostics intended for reporting.
- `--phase ranked` for day-to-day development.

Implementation notes:

- Keep `EvalSummary` able to report both phases.
- If only one phase is run, represent the skipped phase explicitly in the
  summary and diagnostics instead of pretending it failed.
- Diagnostics should include `"skipped": true` for skipped phases.

Tests to add:

- `test_eval_ranked_phase_skips_baseline_candidate_testing`.
- `test_eval_both_phase_preserves_existing_summary_numbers`.
- `test_diagnostics_records_skipped_phase`.

### 3. Fix Failure Hint Exception Parsing

Status: done. Traceback frame context such as `: in function_name` is captured
as a function name, not as `exception_type`. Covered by focused failure-hint
tests.

Fix `failure_hints.py` so traceback frame lines like:

```text
shop/api.py:20: in profile_heading
```

do not set `exception_type` to `in`.

Implementation notes:

- `TRACEBACK_LOCATION_RE` should capture traceback context separately from
  exception names.
- Only set `exception_type` from actual exception names matching
  `EXCEPTION_RE`, for example `TypeError`, `NameError`, `AssertionError`.
- Preserve traceback locations and function-name extraction.

Tests to add:

- A pytest-output fixture with both `: in function_name` frames and a later
  `TypeError`.
- Assert that `hint.exception_type == "TypeError"`.
- Assert that `"in"` is not used as an exception type.
- Assert that the relevant function names and source files are still captured.

Run:

```bash
pytest tests/test_failure_hints.py -q
```

### 4. Let the Ranker Override Bad Hint Ordering

Status: done. With a candidate ranker present, candidate ordering now uses
`ranker_score` before `failure_hint_score`. No-ranker hint-first ordering is
preserved. Covered by focused candidate-ranking tests.

Right now candidate sorting is:

```text
failure_hint_score -> ranker_score -> model_score
```

That means the ranker cannot fix GreenShot-5 cases where the wrong candidate
has a higher handcrafted hint score.

Change ranking policy in `patching.py`:

- Without a ranker, keep the current ordering:
  `failure_hint_score -> model_score`.
- With a ranker, use the ranker as the primary candidate ordering signal after
  candidate features include hints:
  `ranker_score -> failure_hint_score -> model_score`.

This makes the ranker a learned scorer over hint/context features, not just a
tie-breaker.

Tests to add:

- A unit test where candidate A has higher `failure_hint_score`, candidate B has
  higher `ranker_score`, and candidate B must rank first.
- A unit test proving that without a ranker, the old hint-first behavior is
  preserved.

Run:

```bash
pytest tests/test_patching.py tests/test_candidate_ranking.py -q
```

### 5. Add Diagnostic Exploration Mode

Status: done. Implemented for eval through `--explore-after-pass`; normal
`patch` and `fix` still use the default first-pass stopping behavior. Covered
by focused evaluation diagnostics tests.

The ranker cannot learn from only the failed candidates before the first passing
candidate. Add an eval-only exploration mode that keeps testing a bounded number
of candidates after the first pass.

Add:

```bash
python cli.py eval \
  --tasks examples/greenshot_5 \
  --checkpoint runs/mit-python-git/model.json \
  --phase ranked \
  --explore-after-pass 5 \
  --diagnostics runs/mit-python-git/greenshot-5-explore-diagnostics.json
```

Behavior:

- Normal `patch` and `fix` should still stop at the first passing candidate.
- `eval --explore-after-pass N` should continue testing up to `N` additional
  candidates after the first passing candidate.
- Diagnostics should record:
  - first passing candidate index
  - all passing candidates found
  - candidates tested before pass
  - candidates tested after pass

Why this matters:

- It creates positive and negative labels for ranking.
- It reveals multiple valid repairs.
- It makes overfitting to first-pass ordering visible.

Tests to add:

- A focused eval test with a small artificial task where one candidate passes
  early and exploration records more tested candidates.
- A diagnostics test that verifies `first_passing_index` and `passing_candidates`
  are written.

## Benchmark Direction

GreenShot-4 should become a periodic regression gate, not the main development
target. It mostly proves that hints can find known single-file actions.

GreenShot-5 should become the short-term ladder because it introduces:

- multi-file call chains
- decoy candidates
- helper-level repairs
- signature propagation
- imports outside the public API surface

Current GreenShot-5 blocker:

- `order_customer_name_dict_key_helper` fails because the action space cannot
  yet repair `order["name"]` to `order["customer_name"]`.
- Do not add another GreenShot-5 fixture until this missing-action task is
  either solved or explicitly documented as out of scope.

Then add more GreenShot-5 tasks in this order:

1. Wrong default value or config constant in a separate module.
2. Missing import in a nested module, with a decoy import elsewhere.
3. Exception handling through a wrapper API.
4. Swapped arguments across modules.
5. Rename propagated through helper and public API.
6. A task that has two plausible passing patches, where one is smaller or more
   semantically correct.

Every new benchmark task should answer one question:

- Is the action missing?
- Is the target missing?
- Are hints weak?
- Is ranking weak?
- Is repo context weak?

Avoid adding many tasks that only repeat the same action with different names.

## Training Data Direction

Do not start a full neural JEPA yet. First, create the right supervised signal.

Near-term data format should include:

- repo snapshot features
- failing test output
- structured failure hints
- candidate action kind
- candidate target
- before/after candidate delta
- validation result
- whether the candidate was first pass
- whether other candidates also passed

Status: candidate outcome export exists. Each row is one candidate, not one
task. The next training-data task is to make `train-ranker` consume this JSONL
format so post-pass exploration data is actually used.

Current candidate outcome fields:

```json
{
  "task": "profile_signature_propagation",
  "phase": "ranked",
  "file_path": "shop/profiles.py",
  "action": "propagate_signature",
  "params": {"from": "name", "to": "username"},
  "reason": "propagate signature name name to username",
  "model_score": 0.0,
  "failure_hint_score": 80.0,
  "ranker_score": null,
  "passed": true,
  "rank_index": 2,
  "first_passing_index": 2
}
```

This is the dataset a real ranker can learn from.

Next ranker-data changes:

- Add `python cli.py train-ranker --candidate-outcomes PATH`.
- Train from all candidate outcome rows, not only failed candidates before first
  pass.
- Build pairwise examples from every passing candidate against nearby failing
  candidates from the same task.
- Keep diagnostics training as a compatibility path, but prefer JSONL outcomes
  for new experiments.
- Report how many tasks, candidate rows, passing rows, failing rows, and pairs
  were used.

## Modeling Direction

The long-term JEPA path should be staged:

### Stage A: Better Linear Ranker

Use diagnostics-derived candidate outcome rows.

Features:

- action kind
- action params
- target node type
- target symbol
- file match
- function match
- traceback distance
- assertion deltas
- exception type
- model score
- AST delta embedding
- call graph distance from failing frame

Goal:

- Improve pass@1 on GreenShot-5 without adding benchmark-specific rules.

### Stage B: Trainable Candidate Ranker

Replace the tiny perceptron with a small trainable model.

Input:

- structured candidate features
- compact AST/context embeddings
- failure hint features
- test-output embeddings from parsed structure, not raw natural language

Output:

- probability candidate passes
- optional calibrated confidence

Goal:

- Generalize across task families, not memorize action parameter strings.

### Stage C: JEPA-Style Repo Transition Model

Train a model to predict latent repaired-state consequences.

Input:

- current repo latent state
- observation latent state
- structured action
- target context

Prediction:

- latent delta toward passing state
- expected observation change
- candidate utility

Goal:

- Rank actions by predicted consequence before validation.

### Stage D: Planner

Move beyond one-shot patches.

Capabilities:

- apply one candidate
- observe new failure
- update repo state
- plan next action
- stop when tests pass or uncertainty is too high

This is where the project starts looking like a no-LLM coding agent rather than
a single-patch repair tool.

## Evaluation Metrics

Report these for every benchmark refresh:

- solved / total
- pass@1
- average candidates tested
- median candidates tested
- candidate generation recall
- missing-action count
- bad-ranking count
- weak-hint count
- multiple-passing-candidate count
- average test runtime

Do not report only solved count. A system that solves by testing 80 candidates
is not learning the intended behavior.

## Verification Cadence

Use focused checks while editing:

```bash
pytest tests/test_failure_hints.py -q
pytest tests/test_candidate_ranking.py -q
pytest tests/test_patching.py -q
pytest tests/test_evaluation.py -q
```

Use GreenShot-5 smoke for active ranking work:

```bash
python cli.py eval \
  --tasks examples/greenshot_5 \
  --checkpoint runs/mit-python-git/model.json \
  --timeout 10 \
  --max-candidates 3 \
  --phase ranked \
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

## Stop Conditions

Pause action-space expansion when:

- pass@1 is not improving despite passing candidates existing.
- diagnostics show repeated bad ranking.
- new tasks only repeat old patterns.

Pause ranker work when:

- diagnostics mostly show missing actions.
- hints are obviously wrong.
- the dataset has too few independent training pairs.

Start neural work only when:

- GreenShot-5 or later has at least 50 diverse tasks.
- diagnostics contain hundreds or thousands of candidate outcome rows.
- failure categories are separable.
- a simple ranker has plateaued for reasons visible in diagnostics.

## Next Commit Sequence

1. Add a structured dictionary/subscript-key repair action.
   - Candidate action name: `change_subscript_key` or `change_dict_key`.
   - Target: `ast.Subscript` with a string literal key.
   - Example repair: `order["name"]` -> `order["customer_name"]`.
   - Use nearby string evidence from failing tests, `KeyError`, assertion diffs,
     and dictionary literals where available.
   - Focused checks:
     `pytest tests/test_patching.py tests/test_failure_hints.py -q`.

2. Prove the current GreenShot-5 missing-action task is solved.
   - Run:
     `python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --timeout 10 --max-candidates 80 --phase ranked --quiet`
   - Expected direction: `order_customer_name_dict_key_helper` should no longer
     be `missing_action`.
   - If pass@1 is poor but the task solves, classify the remaining issue as
     ranking, not action generation.

3. Regenerate GreenShot-5 exploration data.
   - Run ranked eval with `--explore-after-pass 5`, diagnostics, and
     `--candidate-outcomes`.
   - Record solved, pass@1, average candidates, missing-action count, and
     bad-ranking count in this file.

4. Teach `train-ranker` to consume candidate outcome JSONL.
   - Add `--candidate-outcomes PATH`.
   - Use all passing/failing candidate rows from each task.
   - Keep the existing diagnostics input path for compatibility.
   - Focused checks:
     `pytest tests/test_candidate_ranking.py tests/test_cli.py -q`.

5. Train and evaluate a new ranker from candidate outcomes.
   - The ranker should improve pass@1 without pushing known import/attribute
     repairs far down the list.
   - If pass@1 improves but average candidates gets worse, inspect per-action
     ranking before adding more benchmark tasks.

6. Add the next GreenShot-5 ladder task only after the dict-key task is closed:
   wrong default value or config constant in a separate module.

The project is on track when each new fixture either creates a clear missing
action that gets added, or creates ranking data that the ranker can learn from.
Avoid adding another benchmark case while the current one is still an
unaddressed missing action.
