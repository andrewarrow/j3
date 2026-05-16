# j3 Plan

`j3` is a local-first JEPA coding-agent experiment: treat a Python repository as
a world, structured patches as actions, tests and traces as observations, and a
passing suite as the target state.

The useful prototype loop is now in place:

```text
repo -> transition data -> latent action scorer -> structured candidates
     -> pytest validation -> human-facing patch/fix workflow
```

## Done

- Built the first structured patch action space and deterministic patch
  materializer.
- Added synthetic break/fix transition generation.
- Added `j3 train` with hashed AST embeddings, action-delta prototypes, and
  bounded exemplar deltas.
- Added `j3 mine` for real Python before/after transitions from git history.
- Mined the first local MIT Python corpus:
  - repos mined: 31
  - real Python file transitions: 1,396
- Added `j3 train --transitions ...` so mined `git_transition` examples affect
  ordinary candidate ranking.
- Added GreenShot-2 evaluation over `examples/greenshot_bugs`.
- Added a human-facing `j3 fix` workflow.
- Added structured pytest failure hints:
  - failed node id
  - assertion actual/expected comparisons
  - exception type
  - traceback file/line locations
  - function names from asserts, traceback frames, and pytest explanations
- Threaded failure hints into patch planning so candidates in the failing
  function/file and candidates matching assertion deltas are tested first.
- Added GreenShot-3 with four more task types:
  - swapped call arguments
  - missing import
  - wrong attribute name
  - narrow exception handling
- Added GreenShot-4 as a larger local benchmark:
  - 27 targeted repair tasks
  - multiple examples per supported generated action
  - repeated formula, operator, literal, tail-access, guard, import,
    attribute, call-argument, and exception-handling repairs
- Added candidate generation for:
  - `swap_call_arg`
  - `add_import`
  - `change_attribute`
  - `wrap_try_except`
- Extended failure hints for:
  - `NameError`
  - `ImportError`
  - `ModuleNotFoundError`
  - `AttributeError`
  - `TypeError` argument names
- Added eval diagnostics output:

```bash
j3 eval \
  --tasks examples/greenshot_bugs \
  --checkpoint runs/mit-python-git/model.json \
  --diagnostics runs/mit-python-git/greenshot-diagnostics.json
```

The diagnostics JSON records tested candidates, action kind, symbol, reason,
model score, failure-hint score, and pass/fail status.

## Current Result

Latest GreenShot-2 result with the mined corpus checkpoint:

```text
baseline:     solved=5/5 pass@1=1/5 avg_candidates=21.80
model+hints:  solved=5/5 pass@1=5/5 avg_candidates=1.00
```

Latest GreenShot-3 result with the same checkpoint:

```text
baseline:     solved=4/4 pass@1=1/4 avg_candidates=2.50
model+hints:  solved=4/4 pass@1=4/4 avg_candidates=1.00
```

Latest GreenShot-4 result with the same checkpoint:

```text
baseline:     solved=27/27 pass@1=1/27  avg_candidates=37.93
model+hints:  solved=27/27 pass@1=26/27 avg_candidates=1.04
```

The eval baseline intentionally uses legacy unhinted candidate order. Normal
`patch` and `fix` planning use failure hints by default.

Interpretation:

- `solved=5/5` means both paths eventually found a passing patch for all five
  tasks.
- `pass@1=1/5` means the baseline found the right patch as its first tested
  candidate for only one task.
- `pass@1=5/5` means model+hints found the right patch as the first tested
  candidate for every GreenShot-2 task.
- `avg_candidates=21.80` means the baseline needed about 22 test runs per task
  on average before finding the passing patch.
- `avg_candidates=1.00` means model+hints needed exactly one test run per task
  on average.

This is good news: test-log signal is highly valuable, and the current
candidate ordering can remove a lot of wasted test execution. The caveat is
that GreenShot-4 is still shaped around bugs the current action space already
understands. It is larger than the earlier suites and now exposes at least one
real ranking miss: `meets_minimum_boundary` has two equally hint-relevant
operator candidates, and the checkpoint ranks `<` before the passing `>=`.
These results prove the loop is promising, not that the system is ready for
broad Python repair.

Verification:

```text
pytest: 29 passed
```

## Neural Model Gate

The next neural step should wait until the benchmark is broad enough to expose
repeatable ranking failures.

The reason is practical: before training a neural model, we need to know whether
failures come from ranking, missing actions, weak test-log parsing, or missing
repo context. The diagnostics file gives that visibility by recording every
tested candidate's action, target symbol, reason, model score, hint score, and
pass/fail result.

A neural model becomes the next step when a larger eval shows that good
candidates exist but are ranked poorly. For example:

```text
baseline:     solved=30/50 pass@1=8/50  avg_candidates=45
model+hints:  solved=38/50 pass@1=14/50 avg_candidates=31
```

If diagnostics show many passing candidates sitting behind bad candidates, then
the right next model is a trainable candidate ranker:

```text
failure hints + candidate action + target context + before/after delta
    -> probability candidate will pass
```

That should come before a full neural repo JEPA. A full neural JEPA needs a
larger benchmark and enough positive/negative candidate data to make regressions
visible.

## Next

The evaluation ladder now emits richer diagnostics, the remaining listed
structured actions have first candidate materializers, and common pytest/mypy/
ruff failures are parsed into hints. The current priority is to use those
diagnostics to train a lightweight candidate ranker, not a full neural repo
JEPA.

### Picked Task Queue

Done:

- Added richer diagnostics summaries:
   - per-action pass@1
   - per-action average candidates
   - top failed candidate reasons
   - whether failures are missing-action or bad-ranking failures
- Expanded candidate materialization for:
   - `rename_symbol`
   - richer `modify_condition`
   - signature/call-site propagation
- Improved failure hints for common real failures:
   - KeyError missing keys
   - assertion substring/list/dict diffs
   - mypy output
   - ruff output
- Summarized the GreenShot-4 ranking miss as a bad-ranking failure:
   - `meets_minimum_boundary`
   - wrong first candidate: `>` -> `<`
   - passing second candidate: `>` -> `>=`
   - both had equal failure-hint score, but the checkpoint ranked the wrong
     candidate higher

Next task:

1. Train a lightweight candidate ranker from diagnostics:
   - positive candidate: first tested patch that passes
   - negative candidates: tested patches that fail
   - features: action kind, action params, target symbol, reason, model score,
     failure-hint score, failure mode, and structured failure hints
   - first target: fix GreenShot-4 bad ranking without regressing pass@1
   - keep this separate from the full neural repo JEPA

### Later Tasks

- Add more synthetic-but-realistic repair tasks:
   - attribute rename
   - swapped call arguments
   - missing import
   - wrong default/config value
   - exception handling
   - signature/call-site propagation
   - test updates where appropriate

- Expand the new ranker beyond heuristic/features-only data when diagnostics
  show repeated ranking failures across a broader benchmark.

The neural JEPA version should wait until the benchmark can reveal regressions
that the current prototype scorer and failure-hint heuristics cannot handle.
