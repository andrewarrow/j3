# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: prompt-to-repo CLI wiring complete; ready for GreenShot-7
  runner work or training row recording
- Completed iterations: 6
- Passing focused tests: prompt seed JSONL validation, `test -s REQUEST_SPEC.md`,
  GreenShot-7 fixture JSON validation, `pytest tests/test_request_spec.py -q`,
  `pytest tests/test_greenfield_calculator.py -q`, `pytest tests/test_cli.py -q`,
  direct `python cli.py implement ...` smoke, `git diff --check`
- Latest implementation commit: `8bc36d67953df204a45ece8e590046fec4f4c78d`
  (`Add implement CLI command`)
- Current blocker: none
- Next task: add prompt/spec/action/outcome row recording or the bounded
  GreenShot-7 task runner, without broadening beyond calculator request-to-repo

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
- Commit: `9a9f93b094e9c35b2bbeb6965556681480accc4f` (`Add GreenShot-7 prompt fixtures`)
- Push: succeeded to `origin/main`
- Next: Implement the deterministic prompt-to-`request-spec-v1` baseline parser
  against `examples/greenshot_7/tasks.json`.
- Blockers: none

### Iteration 3: Add request spec parser

- Worker: Codex Worker Iteration 3
- Goal: Implement the deterministic prompt-to-`request-spec-v1` baseline parser
  for the GreenShot-7 calculator fixture manifest.
- Files changed:
  - `request_spec.py`
  - `tests/test_request_spec.py`
  - `pyproject.toml`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_request_spec.py -q`
  - `git diff --check`
- Result: Added `RequestSpec` and `parse_request_to_spec`, covering the eight
  positive calculator prompts and two clarification prompts in
  `examples/greenshot_7/tasks.json`, including operation aliases, inferred
  defaults, blocking clarifications, and validation fields.
- Commit: `60ac8ae4af704fee01e63b9c9066246cd32df89a` (`Add request spec parser`)
- Push: succeeded to `origin/main`
- Next: Build structured greenfield calculator action planning from
  `request-spec-v1`; do not generate repos until that slice is assigned.
- Blockers: none

### Iteration 4: Add greenfield action planning

- Worker: Codex Worker Iteration 4
- Goal: Implement structured GreenShot-7 calculator repo planning from
  `request-spec-v1` without materializing output repos.
- Files changed:
  - `greenfield.py`
  - `tests/test_greenfield_calculator.py`
  - `pyproject.toml`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_greenfield_calculator.py -q`
  - `pytest tests/test_request_spec.py -q`
  - `git diff --check`
- Result: Added `greenfield-plan-v1` records with ordered add-only actions for
  calculator source and test files, operation dispatch derived from spec
  features and aliases, CLI entrypoint planning, behavior test planning, and a
  blocked clarification plan for non-actionable specs.
- Commit: `8b1d6891e7611ff06962f43d1b1016f9d1d6958f` (`Add greenfield action planning`)
- Push: succeeded to `origin/main`
- Next: Materialize generated calculator repos from `greenfield-plan-v1`
  actions and run subprocess smoke checks.
- Blockers: none

### Iteration 5: Build calculator repos from plans

- Worker: Codex Worker Iteration 5
- Goal: Materialize deterministic calculator repos from `greenfield-plan-v1`
  action payloads and validate generated repos with subprocess smoke checks.
- Files changed:
  - `greenfield.py`
  - `tests/test_greenfield_calculator.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_greenfield_calculator.py -q`
  - `pytest tests/test_request_spec.py -q`
  - `git diff --check`
- Result: Added `BuildResult`, `build_calculator_repo`, and
  `materialize_calculator_repo`; generated dependency-free `calculator.py` and
  subprocess pytest coverage from structured action payloads; covered
  four-operation, add-only, hidden-like subprocess, and blocked clarification
  cases.
- Commit: `6e018c8e07e77d338cc521a1d6b6c4db579aaa36`
  (`Build calculator repos from plans`)
- Push: succeeded to `origin/main`
- Next: Add CLI entry point wiring for prompt-to-repo implementation without
  broadening the calculator slice.
- Blockers: none

### Iteration 6: Add implement CLI command

- Worker: Codex Worker Iteration 6
- Goal: Add CLI wiring for prompt-to-repo calculator implementation without
  adding training row recording or a broader GreenShot-7 runner.
- Files changed:
  - `cli/parser.py`
  - `cli/handlers.py`
  - `cli/__init__.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_cli.py -q`
  - `pytest tests/test_greenfield_calculator.py -q`
  - `pytest tests/test_request_spec.py -q`
  - `git diff --check`
  - `python cli.py implement --prompt "make me a simple cli calc" --out /tmp/j3-calc-demo`
  - `python /tmp/j3-calc-demo/calculator.py 2 + 3`
- Result: Added `j3 implement --prompt ... --out ...` for the calculator
  request-to-repo path. The command parses prompts into `request-spec-v1`,
  builds the generated repo, writes `request-spec.json`, runs generated pytest
  validation by default, supports `--no-validate`, and exits non-zero with a
  clarification message for blocked prompts without writing calculator files.
- Commit: `8bc36d67953df204a45ece8e590046fec4f4c78d`
  (`Add implement CLI command`)
- Push: succeeded to `origin/main`
- Next: Add prompt/spec/action/outcome row recording or the bounded GreenShot-7
  task runner.
- Blockers: none
