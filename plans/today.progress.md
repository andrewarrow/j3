# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: reset complete; ready to implement intent-fidelity fixtures
- Completed iterations: 0
- Passing focused tests: none yet for this reset slice
- Latest implementation commit: none yet in this reset slice
- Current blocker: none
- Next task: add fixtures and tests proving `make me a complex graphic calc app`
  asks clarification instead of generating the simple CLI calculator

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
