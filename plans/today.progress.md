# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: prompt-intent dataset/eval baseline added; ready for learned
  model or request-spec integration slice
- Completed iterations: 1
- Passing focused tests:
  - `pytest tests/test_prompt_intents.py -q`
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py -q`
  - `git diff --check`
  - `python -m py_compile prompt_intents.py`
- Latest implementation commit: `e6b62d1162202798a67d62b6dc92e21f259bd9fa`
- Current blocker: none
- Next task: connect prompt-intent prediction objects to request-spec blocking
  so unsupported graphical calculator prompts can be rejected without expanding
  broad parser keyword rules

## Worker Iteration Template

Use this shape for each worker handoff:

```md
### Iteration N: <task>

- Worker:
- Goal:
- Files changed:
- Tests run:
- Result:
- Commit:
- Push:
- Next:
- Blockers:
```

## 2026-05-17

- Reset `plans/today.md` from the completed GreenShot-7 calculator
  request-to-repo slice to a new intent-fidelity and existing-repo change slice.
- Reset this progress log to start a fresh loop at iteration 0.
- New regression target:
  - `python cli.py implement --prompt "make me a complex graphic calc app" --out ../sample2`
  - Expected future behavior: blocked clarification, no generated simple CLI
    calculator files.
- New existing-repo target:
  - generate a calculator repo
  - run a prompt-driven existing-repo change such as `add exponent support`
  - validate `python calculator.py 2 ^ 3` -> `8`
- Confirmed prompt corpus exists for profiling:
  - `../prompts/README.md`
  - `../prompts/coding_agent_prompts_seed.jsonl`
- Current next step: add unsupported-interface and existing-repo-change fixtures,
  then make the request parser fail the graphical calculator regression in the
  right direction.
- User pushed back on broad hard-coded English rules. Updated `plans/today.md`
  to make learned prompt understanding the active direction: prompt corpus
  profiling, explicit encoder targets, held-out evaluation, and training or a
  documented data blocker. Deterministic rules should remain only as a
  lower-bound baseline or narrow safety fallback.
- Current next step after the pivot: build the prompt corpus loader/profile and
  prompt-intent eval target before expanding parser keyword coverage.

### Iteration 1: Prompt-Intent Dataset And Eval Harness

- Worker: Codex
- Goal: pivot away from broad deterministic unsupported-interface parsing and
  add the smallest learned/JEPA-oriented prompt understanding step.
- Files changed:
  - `prompt_intents.py`
  - `examples/prompt_intents/greenshot_7_intents.jsonl`
  - `tests/test_prompt_intents.py`
  - `pyproject.toml`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 4 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py -q` ->
    passed, 8 tests
  - `git diff --check` -> passed
  - `python -m py_compile prompt_intents.py` -> passed
- Result:
  - Added labeled prompt-intent rows for supported CLI calculator creation,
    unsupported graphical/complex/interface/scientific/math prompts, and
    existing-repo power/exponent change prompts.
  - Added a loader that normalizes JSONL prompt labels into explicit
    `PromptIntentTarget` records: `repo_mode`, `task_type`, `domain`,
    `expected_action`, requested interfaces, features, unsupported
    requirements, clarification fields, and target files.
  - Added a profile helper and field-level evaluation harness that can score a
    future JEPA-style prompt encoder or other learned predictor against labels.
  - Profiled `../prompts/coding_agent_prompts_seed.jsonl`: 80 rows, splits
    train=53/validation=15/test=12, repo modes existing_repo=54/new_repo=25/
    unknown=1, expected actions ask_clarification=8/
    emit_existing_repo_change_spec=50/emit_request_spec=22.
  - Deferred training: the external seed corpus has useful held-out splits and
    clarification/change labels, but no explicit unsupported graphical
    requirement labels yet; this iteration therefore adds dataset/eval plumbing
    and focused GreenShot-7 labels instead of training a misleading model.
- Commit: `e6b62d1162202798a67d62b6dc92e21f259bd9fa`
- Push: succeeded to `main`
- Next: wire an intent prediction object into request-spec construction, then
  make `make me a complex graphic calc app` block through that path while
  preserving simple CLI calculator generation.
- Blockers: none
