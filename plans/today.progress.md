# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` and
`plans/today.md` stable unless the user explicitly asks to change them.

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
- Current next step: start Step 1 from `plans/today.md` by adding
  `REQUEST_SPEC.md` for `request-spec-v1`, including calculator `etc.`
  inference and at least one clarification example.
