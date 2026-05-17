# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` and
`plans/today.md` stable unless the user explicitly asks to change them.

## Status

- Current phase: pre-implementation setup for GreenShot-7 calculator slice
- Completed iterations: 0
- Passing focused tests: prompt seed JSONL validation only
- Latest commit: none yet in this loop
- Current blocker: none
- Next task: add `REQUEST_SPEC.md` for `request-spec-v1`

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
- Current next step: start Step 1 from `plans/today.md` by adding
  `REQUEST_SPEC.md` for `request-spec-v1`, including calculator `etc.`
  inference and at least one clarification example.
