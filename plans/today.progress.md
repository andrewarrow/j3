# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: pre-implementation setup for GreenShot-7 calculator slice
- Completed iterations: 2
- Passing focused tests: prompt seed JSONL validation, `test -s REQUEST_SPEC.md`,
  GreenShot-7 fixture JSON validation
- Latest commit: `Add GreenShot-7 prompt fixtures`
- Current blocker: none
- Next task: implement deterministic prompt-to-`request-spec-v1` baseline parser

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

- Created the active 24-hour plan in `plans/today.md`.
- Created the prompt seed corpus in `../prompts/`:
  - `README.md`
  - `coding_agent_prompts_seed.jsonl`
- Validated the seed corpus shape:
  - 80 rows
  - train=53, validation=15, test=12
  - 8 clarification rows
- Rewrote `AGENTS.md` so fresh context windows read:
  1. `AGENTS.md`
  2. `plans/today.md`
  3. `plans/today.progress.md`
- Tightened `AGENTS.md` verification guidance for the active GreenShot-7 slice:
  create and run focused tests such as `tests/test_request_spec.py`,
  `tests/test_greenfield_calculator.py`, and `tests/test_greenshot_7.py` as the
  implementation is built.
- Clarified the documentation policy: ordinary progress goes here, while
  `plans/today.md` may be updated narrowly if new discoveries change the actual
  24-hour execution plan.
- Current next step: start Step 1 from `plans/today.md` by adding
  `REQUEST_SPEC.md` for `request-spec-v1`, including calculator `etc.`
  inference and at least one clarification example.

### Iteration 1: Add request spec docs

- Worker: Codex Worker Iteration 1
- Goal: Add `REQUEST_SPEC.md` documenting `request-spec-v1` for the
  GreenShot-7 calculator request-to-repo path.
- Files changed:
  - `REQUEST_SPEC.md`
  - `plans/today.progress.md`
- Tests run:
  - `test -s REQUEST_SPEC.md`
- Result: Added the bounded request spec documentation with purpose, day-one
  schema fields, calculator prompt examples, high-confidence `etc.` inference,
  operation aliases, validation expectations, and clarification examples.
- Commit: `25ac8e153e170c89278f668f1c6c716c36d3d2b1` (`Add request spec docs`)
- Push: succeeded to `origin/main`
- Next: Implement deterministic prompt-to-`request-spec-v1` parsing fixtures.
- Blockers: none

### Iteration 2: Add GreenShot-7 prompt fixtures

- Worker: Codex Worker Iteration 2
- Goal: Add deterministic calculator prompt fixtures for the GreenShot-7
  prompt-to-`request-spec-v1` parser slice without implementing parser code.
- Files changed:
  - `examples/greenshot_7/tasks.json`
  - `plans/today.progress.md`
- Tests run:
  - `python -m json.tool examples/greenshot_7/tasks.json >/dev/null`
  - Inline Python validation for 10 rows, 8 `emit_request_spec` positives, 2
    `ask_clarification` rows, matching task names, prompts, and features.
- Result: Added a single structured manifest with the eight day-one calculator
  prompts and two clarification prompts from `plans/today.md`, including stable
  task names, prompt text, expected actions, expected features, and expected
  `request-spec-v1` fields for later parser tests.
- Commit: `Add GreenShot-7 prompt fixtures`
- Push: succeeded to `origin/main`
- Next: Implement the deterministic prompt-to-`request-spec-v1` baseline parser
  against `examples/greenshot_7/tasks.json`.
- Blockers: none
