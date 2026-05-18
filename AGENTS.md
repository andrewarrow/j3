# j3 Agent Handoff

Keep `README.md` small. Put substantial docs in focused markdown files and
reference them.

## Read Order for Fresh Context

1. Read this file.
2. Read `plans/active.md` for the current coordinator board.
3. Read `plans/backlog.md` for the persistent multi-week task queue.
4. Read the latest entries in `plans/progress.md` for completed work, blockers,
   and active assumptions.
5. Read `plans/operating-model.md` before coordinating worker agents or changing
   the planning system.

`plans/strategy.md` is the long-term project strategy. Read it when the active
board is unclear, when making big-picture direction decisions, or when a user
asks for strategic review. Do not edit it during ordinary implementation unless
the strategic roadmap has truly changed.

`plans/today.md` and `plans/today.progress.md` are legacy snapshots from the old
24-hour loop. Do not use them as the source of truth for new work.

## Planning System

The project no longer uses throwaway 24-hour plan files. Use these persistent
files instead:

- `plans/operating-model.md`: how the coordinator and workers run.
- `plans/active.md`: the live board of tasks currently assigned, queued, paused,
  or recently completed.
- `plans/backlog.md`: multi-week workstreams and task IDs.
- `plans/progress.md`: concise chronological execution log.
- `plans/strategy.md`: durable long-term direction.

Update `plans/active.md` when task state changes. Update `plans/progress.md`
after meaningful work: files changed, tests run, assumptions confirmed or
rejected, blockers found, commits pushed, and next concrete task.

Do not rewrite planning files just to create a fresh daily narrative. Keep them
stable and append or narrowly edit the parts that changed.

## Coordinator Role

The parent agent is the coordinator. It owns direction, task selection, review,
and integration.

Recommended model level: run the coordinator at `xhigh`. The coordinator makes
the higher-order decisions: direction, task selection, worker scope, integration
review, parallelism, and when to pause. That reasoning budget is worth spending
there.

Coordinator flow:

1. Read `plans/active.md`, `plans/backlog.md`, and recent `plans/progress.md`.
2. Pick the next highest-leverage bounded tasks from the backlog.
3. Keep the active set small: normally one or two workers; at most three when
   tasks are independent and have disjoint write scopes.
4. Record the assignment in `plans/active.md` before starting a worker.
5. Give each worker exactly one bounded task with clear ownership, acceptance
   criteria, expected tests, and files or modules it may edit.
6. Continue useful local work while workers run, without duplicating their
   write scope.
7. Review every worker result for tests, commit status, pushed commit, generated
   files, and plan updates.
8. Update `plans/active.md` and `plans/progress.md`.
9. After several completed iterations, or after any surprising failure, pause
   worker dispatch long enough to reassess the next few tasks.

Parallelism is allowed, but only when it helps. Do not keep workers busy with
low-value work. It is better to pause briefly and choose the right next task
than to create parallel churn.

When selecting worker model level, use the smallest level that fits the task:

- `high`: default for bounded implementation, tests, evidence runs, and focused
  docs.
- `medium`: mechanical tasks such as formatting docs, recording command output,
  or adding straightforward fixtures with clear patterns.
- `xhigh`: hard architecture or research tasks, such as designing a structured
  action family, diagnosing residual clusters across subsystems, changing
  planner/model interfaces, or making training/data strategy decisions.

Do not use stronger workers as a substitute for clear task boundaries. A
well-scoped `high` worker is preferable to an underspecified `xhigh` worker.

Normal setup:

```text
Coordinator: xhigh
Workers: high
Mechanical workers: medium
Hard architecture/research worker: xhigh
```

If the runtime does not expose model-level selection, keep the same logic as a
task-complexity guide.

## Worker Role

Workers do exactly the assigned slice.

Worker flow:

1. Read `AGENTS.md`, `plans/operating-model.md`, `plans/active.md`,
   `plans/backlog.md`, and recent `plans/progress.md`.
2. Confirm the assigned task ID, write scope, acceptance criteria, and tests.
3. Prefer implementation plus focused tests over more planning.
4. Do not edit `plans/strategy.md` unless explicitly assigned.
5. Do not edit unrelated files or revert changes made by others.
6. Run the focused tests relevant to the slice.
7. Update `plans/progress.md` and `plans/active.md` with result, tests, commit,
   push, blockers, and recommended next task.
8. Stage only relevant files.
9. Commit with a concise task-specific message.
10. Push.
11. Report commit hash, tests run, push result, changed files, and blockers.

If tests fail and the fix is local and obvious, fix it in the same iteration. If
the fix requires broad scope expansion, stop, record the blocker, and report it.

## Definition of Done

A worker iteration is done only when:

- one bounded slice is complete
- focused tests for that slice pass, or a blocker is recorded
- generated files are intentional
- `plans/active.md` and `plans/progress.md` are updated
- relevant files are staged and committed
- push succeeds
- `git status --short` is clean except for explicitly deferred work

Coordinator-only documentation or planning changes do not require a worker, but
they still need focused verification such as `git diff --check`.

## Commit Rules

- Use one task per commit.
- Use concise commit messages such as `Add request spec docs`.
- Do not include unrelated dirty files.
- Do not add dependencies without coordinator approval.
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

The realistic stepping stone is a serious narrow Python authoring tool:
request-to-repo tasks, small libraries and CLIs, repo-local feature additions,
tests, configs, typed actions, retrieval, validation, residual reports, and
conservative product gates.

The long-term target remains general GPT-5.5 xhigh-level Python coding. That
will require far more than more fixtures: large language/code pretraining,
broad library and world knowledge, algorithm synthesis, flexible source
generation, long-horizon planning, and strong validation. j3's plausible
advantage is a structured stack: tight action spaces, retrieval, explicit repo
state, outcome data, residual-driven training, and gates that prevent premature
production use.

## Current Technical Priorities

Keep the work pointed at durable capability:

- GreenShot-7 request-to-repo growth with hidden-like tests.
- Prompt/spec/action/outcome records suitable for learned prompt and transition
  models.
- Repair/ranking regression gates from GreenShot-5/6.
- Transition shadow matrix evidence before guarded production ranking.
- Data quality over raw dataset size.
- Issue/PR and prompt/repo transition mining with provenance and stable splits.
- Structured greenfield actions before broad free-form generation.

## Verification Cadence

Default to the smallest focused test that proves the touched behavior.

For request-to-repo work:

```bash
pytest tests/test_request_spec.py -q
pytest tests/test_greenfield_calculator.py -q
pytest tests/test_greenshot_7.py -q
```

For implementation CLI smoke checks:

```bash
python cli.py implement --prompt "make me a simple cli calc" --out /tmp/j3-calc-demo
python /tmp/j3-calc-demo/calculator.py 2 + 3
python -m pytest /tmp/j3-calc-demo/tests -q
```

For repair, evaluation, or ranking changes:

```bash
pytest tests/test_candidate_ranking.py -q
pytest tests/test_evaluation.py -q
pytest tests/test_patching.py -q
pytest tests/test_failure_hints.py -q
```

For transition evidence changes:

```bash
pytest tests/test_transition_shadow_matrix.py -q
pytest tests/test_transition_residuals.py -q
pytest tests/test_transition_evidence_bundle.py -q
pytest tests/test_transition_guarded_trial.py -q
```

Run full `pytest -q` only as an intentional integration gate after broad shared
changes or when the user asks.
