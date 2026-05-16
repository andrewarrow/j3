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
model score, failure-hint score, optional candidate-ranker score, structured
failure hints, and pass/fail status.
- Added `j3 train-ranker` for a lightweight pairwise candidate ranker trained
  from diagnostics.
- Added default stdout progress logging for `j3 eval` so long benchmark runs
  show task, phase, candidate, and elapsed-time information as they execute.

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

Verification baseline:

```text
pytest: 36 passed
```

Everyday verification should stay focused. Use the smallest test that covers
the touched behavior, for example:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_patching.py -q
python3 cli.py eval --tasks examples/greenshot_3 --checkpoint runs/mit-python-git/model.json --timeout 10 --max-candidates 1
```

Run full `pytest` and the full GreenShot-4 checkpoint eval as periodic gates or
before merging broader behavior changes, not after every small edit.

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

## Active Direction

Do not start the full neural JEPA yet. The active work is to make the
evaluation ladder expose repeatable failures, then use diagnostics to decide
whether the next fix is ranking, hint parsing, action generation, or repo
context.

GreenShot-5 is now the main short-term benchmark because it is multi-file and
already exposes ranking misses that GreenShot-4 did not.

## Recent Work

- Added richer diagnostics summaries:
  - per-action pass@1 and average candidates
  - top failed candidate reasons
  - missing-action vs bad-ranking failure modes
  - ranker paths, ranker-score presence, and selected ranker score
- Added first materializers for:
  - `rename_symbol`
  - richer `modify_condition`
  - signature/call-site propagation
- Improved failure hints for:
  - KeyError missing keys
  - assertion substring/list/dict diffs
  - mypy output
  - ruff output
- Added `j3 train-ranker` and trained the first lightweight ranker on refreshed
  GreenShot-4 diagnostics:
  - plans: 1
  - training pairs: 1
  - training accuracy: 1.000
  - margin violations: 0
  - artifacts:
    - `runs/mit-python-git/candidate-ranker.json`
    - `runs/mit-python-git/candidate-ranker-metrics.json`
- Added CLI and diagnostics regression coverage for the ranker path.
- Added GreenShot-5 as a multi-file package benchmark fixture:
  - helper repair through a public API call chain
  - module-local missing import
  - attribute rename with nearby decoy fields
  - signature propagation with a plausible call-site-only wrong fix

GreenShot-5 smoke with the mined corpus checkpoint:

```text
baseline:     solved=1/4 pass@1=0/4 avg_candidates=2.75
model+hints:  solved=4/4 pass@1=1/4 avg_candidates=1.75
```

GreenShot-5 with the GreenShot-4-trained candidate ranker was unchanged from
model+hints. That means the current ranker learned the GreenShot-4 boundary tie
but does not generalize to the new GreenShot-5 misses.

Current GreenShot-5 bad-ranking cases:

- `quote_total_helper_discount`
  - wrong first candidate: `swap_call_arg`
  - passing second candidate: `replace_expr`
- `visible_balance_attribute_decoys`
  - wrong first candidate: `change_attribute` to `available_cents`
  - passing second candidate: `change_attribute` to `balance_cents`
- `profile_signature_propagation`
  - wrong first candidate: call-site-only `rename_symbol`
  - passing second candidate: `propagate_signature`

## Immediate Queue

1. Train a GreenShot-5-specific candidate ranker and compare it against the
   current GreenShot-5 smoke.
   - Command:
     `python cli.py train-ranker --diagnostics runs/mit-python-git/greenshot-5-smoke-diagnostics.json --out runs/greenshot-5-ranker`
   - Then run:
     `python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --ranker runs/greenshot-5-ranker/candidate-ranker.json --timeout 10 --max-candidates 3 --quiet`
   - Record whether pass@1 improves beyond `1/4`.

2. Add a compact regression test that guards the GreenShot-5 fixture shape.
   - Verify manifest count, task names, and that the first task still fails
     before repair.
   - Focused check: `pytest tests/test_evaluation.py -q`.

3. Add one GreenShot-5 missing-action task for a wrong dictionary key or
   default-value repair.
   - The test should fail in a way the current action space cannot fix.
   - Focused check: run the new pytest node directly.

4. Inspect the new missing-action diagnostics.
   - If hints are weak, improve failure hint parsing first.
   - If hints are good but no candidate exists, add the smallest structured
     action/materializer that covers the case.
   - Focused checks:
     - `pytest tests/test_failure_hints.py -q` for hint parser changes
     - `pytest tests/test_patching.py -q` for candidate generation changes

5. Re-run the tight GreenShot-5 eval and update this plan with baseline vs
   model+hints numbers.
   - Command:
     `python cli.py eval --tasks examples/greenshot_5 --checkpoint runs/mit-python-git/model.json --timeout 10 --max-candidates 3 --diagnostics runs/mit-python-git/greenshot-5-smoke-diagnostics.json --quiet`

## Later

- Expand GreenShot-5 with more multi-file tasks:
  - swapped call arguments across modules
  - missing import across modules
  - wrong default/config value
  - exception handling through wrapper APIs
  - signature/call-site propagation across modules
- Broaden the ranker only after diagnostics contain more than a few independent
  bad-ranking examples.
- Start neural model work only after a larger benchmark can distinguish
  ranking failures from missing actions and weak hints.
