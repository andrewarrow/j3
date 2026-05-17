# j3 Agent Handoff

Keep `README.md` small. Put substantial docs in focused markdown files and
reference them.

## Read Order for Fresh Context

1. Read this file.
2. Read `plans/today.md` for the current 24-hour execution scope.
3. Read `plans/today.progress.md` for what has already been done, current
   blockers, and the next concrete step.

Do not reread or edit `plans/strategy.md` for ordinary day-to-day work. It is the broad
project strategy and can distract from the active slice. Read `plans/strategy.md` only
when the user asks for big-picture direction, the active plan is unclear, or a
decision would change the overall roadmap.

Do not edit `plans/strategy.md` during ordinary day-to-day work unless the user explicitly
asks or the strategic roadmap has truly changed.

Keep `plans/today.md` stable for routine progress. It may be updated when new
facts change the 24-hour execution plan itself: a tested assumption is wrong, a
scope decision changes, a better next-step breakdown is discovered, or a new
blocker requires replanning. When updating `plans/today.md`, keep edits narrow
and also record the reason in `plans/today.progress.md`.

Track ordinary day-to-day progress only in `plans/today.progress.md`.

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

## Agent Loop Protocol

When running repeated worker-agent iterations, keep this parent context as the
watcher and assign exactly one bounded task to each worker.

Watcher flow:

1. Read `plans/today.progress.md`.
2. Pick the next unchecked task from the progress file.
3. If no task is listed there, pick the next step from `plans/today.md` and add
   it to the progress file before starting a worker.
4. Spawn one worker for that task.
5. Review the worker result, commit status, pushed commit, and tests.
6. Update or confirm `plans/today.progress.md`.
7. Start the next worker only after the previous worker is closed.

Worker flow:

1. Read `AGENTS.md`, `plans/today.md`, and `plans/today.progress.md`.
2. Do exactly the assigned slice.
3. Prefer implementation plus focused tests over more planning.
4. Run the focused tests relevant to the slice.
5. Update `plans/today.progress.md` with files changed, tests, result, commit,
   push, blockers, and next task.
6. Stage only relevant files.
7. Commit with a concise task-specific message.
8. Push.
9. Report commit hash, tests run, push result, and any blocker.

Do not edit `plans/strategy.md` during worker iterations unless the watcher explicitly
assigns that strategic documentation change. Edit `plans/today.md` only if the
assigned work discovers information that changes the 24-hour plan; record that
plan update in `plans/today.progress.md`.

## Worker Definition of Done

A worker iteration is done only when:

- one bounded slice is complete
- focused tests for that slice pass, or a blocker is recorded
- generated files are intentional
- `plans/today.progress.md` is updated
- relevant files are staged and committed
- push succeeds
- `git status --short` is clean except for explicitly deferred work

If tests fail and the fix is obvious, fix it in the same iteration. If the fix
requires broad scope expansion, stop, record the blocker, and report back.

## Commit Rules

- Use one task per commit.
- Use concise commit messages such as `Add request spec docs`.
- Do not include unrelated dirty files.
- Do not add dependencies without watcher approval.
- Do not use destructive git commands.
- Do not rewrite or clean up unrelated history.

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

For the active GreenShot-7 calculator work, create focused tests as the feature
is built. The expected near-term test files are:

- `tests/test_request_spec.py`
- `tests/test_greenfield_calculator.py`
- `tests/test_greenshot_7.py`

Run the relevant new test first, for example:

```bash
pytest tests/test_request_spec.py -q
pytest tests/test_greenfield_calculator.py -q
pytest tests/test_greenshot_7.py -q
```

If an implementation CLI is added, also smoke it directly:

```bash
python cli.py implement --prompt "make me a simple cli calc" --out /tmp/j3-calc-demo
python /tmp/j3-calc-demo/calculator.py 2 + 3
python -m pytest /tmp/j3-calc-demo/tests -q
```

Existing repair-focused checks remain useful when touching repair, evaluation,
or ranking code:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_patching.py -q
pytest tests/test_failure_hints.py -q
```

Run full `pytest -q` only as an intentional integration gate after broad shared
changes or when the user asks.
