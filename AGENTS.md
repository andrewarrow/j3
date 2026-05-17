# j3 Agent Handoff

Keep `README.md` small. Put substantial docs in focused markdown files and
reference them.

## Read Order for Fresh Context

1. Read this file.
2. Read `plans/today.md` for the current 24-hour execution scope.
3. Read `plans/today.progress.md` for what has already been done, current
   blockers, and the next concrete step.

Do not reread or edit `plan.md` for ordinary day-to-day work. It is the broad
project strategy and can distract from the active slice. Read `plan.md` only
when the user asks for big-picture direction, the active plan is unclear, or a
decision would change the overall roadmap.

Do not edit `plan.md` or `plans/today.md` unless the user explicitly asks.
Track day-to-day progress only in `plans/today.progress.md`.

## Active Focus

The current active slice is GreenShot-7 request-to-repo work:

- Parse coding-agent English for a narrow calculator CLI domain.
- Convert prompts like "make me a simple cli calc" or "make cli takes as params
  two numbers and operator" into `request-spec-v1`.
- Generate a working Python CLI calculator repo from structured actions.
- Validate with focused tests and hidden-like subprocess checks.
- Record prompt/spec/action/outcome rows that can later train a prompt encoder
  and JEPA transition model.

The first version may use deterministic prompt-to-spec rules. Keep outputs and
records structured so learned models can replace rules later.

## Progress Log Rules

Update `plans/today.progress.md` after meaningful steps:

- files added or changed
- tests run and results
- assumptions confirmed or rejected
- blockers
- next concrete step

Keep progress concise and chronological. Do not duplicate the full plan.

## Project Direction

j3 is a local-first, no-LLM Python coding agent experiment. The long-term goal
is Codex-level repository editing without asking a large autoregressive model to
write candidate patches.

Core loop:

```text
prompt or tool observation
  -> structured goal / observation record
  -> repo-state representation
  -> structured candidate actions
  -> predicted consequence
  -> validation
  -> next action or stop
```

Existing GreenShot-5/6 repair work remains the regression foundation. The new
near-term gap is user intent and greenfield editing, starting with the calculator
CLI request-to-repo path.

Existing `data/` and `runs/` artifacts are useful for Python source transitions,
repair evaluation, and candidate-ranker training. They do not yet train
natural-language prompt understanding.

## Verification Cadence

Default to the smallest focused test that proves the touched behavior.

Useful focused checks:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_patching.py -q
pytest tests/test_failure_hints.py -q
```

For GreenShot-7 work, prefer the focused request-spec, greenfield, and
calculator tests as they are added. Run full `pytest -q` only as an intentional
integration gate after broad shared changes or when the user asks.
