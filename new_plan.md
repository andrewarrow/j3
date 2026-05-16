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

Verified:

```bash
pytest tests/test_cli.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_failure_hints.py -q
pytest tests/test_patching.py tests/test_candidate_ranking.py -q
python -m py_compile patching.py evaluation.py cli.py tests/test_evaluation.py
```

Next:

- Start Immediate Change 6: export candidate outcome rows.

## Current Diagnosis

The good parts:

- Structured candidate generation and deterministic materialization work.
- Pytest validation in temporary repos works.
- Failure hints clearly reduce wasted testing on GreenShot-4.
- Diagnostics now expose candidate order, scores, reasons, and pass/fail labels.
- GreenShot-5 is a better benchmark direction because it starts to require
  multi-file reasoning.

The problems:

- The `eval` baseline intentionally disables failure hints, so it tests many
  irrelevant candidates. This is useful as a control, but it makes normal eval
  output look worse than the actual ranked path.
- Candidate logging is too verbose by default. Per-candidate logs should be a
  verbose/debug mode, not the normal output.
- The optional candidate ranker is currently only a tie-breaker after
  `failure_hint_score`. It cannot fix cases where a wrong candidate has a higher
  hint score than the passing candidate.
- The ranker training data is too small. GreenShot-4 currently provides only one
  useful training pair for the ranker, which is not a meaningful learning set.
- Failure hint parsing is leaking traceback frame text such as `in` into
  `exception_type`, which pollutes ranking features.
- The benchmark is still mostly constructed around actions the system already
  knows how to generate. It needs more missing-action and cross-file tasks.

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

Add more GreenShot-5 tasks in this order:

1. Wrong dictionary key across a helper boundary.
2. Wrong default value or config constant in a separate module.
3. Missing import in a nested module, with a decoy import elsewhere.
4. Exception handling through a wrapper API.
5. Swapped arguments across modules.
6. Rename propagated through helper and public API.
7. A task that has two plausible passing patches, where one is smaller or more
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

Add a `candidate_outcomes.jsonl` export from diagnostics. Each row should be one
candidate, not one task.

Suggested fields:

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

1. Fix noisy eval output and add `--verbose`.
2. Add `--phase ranked|baseline|both`.
3. Fix traceback `exception_type` parsing.
4. Change ranker ordering so ranker can override hints.
5. Add eval exploration after first pass.
6. Export candidate outcome rows.
7. Add the next GreenShot-5 missing-action task.
8. Train and evaluate a new ranker from GreenShot-5 exploration diagnostics.
9. Update `plan.md` with a short pointer to this file, but do not expand the
   README.

The project is back on track when GreenShot-5 pass@1 improves because the model
learned from candidate outcomes, not because another benchmark-specific
heuristic was added.
