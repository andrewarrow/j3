# j3 Operating Model

This file defines the persistent coordinator/worker loop. It replaces the old
24-hour `today.md` plan cycle.

## File Roles

- `plans/active.md`: live coordinator board. Shows active workers, ready queue,
  paused work, limits, and current review state.
- `plans/backlog.md`: durable multi-week backlog grouped by workstream.
- `plans/progress.md`: chronological execution log. Append concise entries after
  meaningful work.
- `plans/strategy.md`: long-term direction and strategic constraints.
- `plans/today.md` and `plans/today.progress.md`: legacy redirects only.

## Coordinator Loop

The coordinator is responsible for direction, not just dispatch.

Recommended model level: `xhigh`. The coordinator is the agent in charge and
must spend its reasoning budget on task selection, worker scoping, integration
review, strategic drift detection, and deciding when to pause.

### Continuous Loop Contract

The coordinator/worker process is a loop. Once the user starts the agent loop,
the coordinator should continue cycling through assignment, worker execution,
review, integration, and the next assignment. A review checkpoint is not a
stopping condition. An empty active board is only a transient state while the
coordinator is choosing and recording the next assignments.

After every completed worker batch, the coordinator must either:

- dispatch the next bounded ready task or tasks, or
- record the explicit blocker that prevents dispatch.

Do not end a loop turn solely because the previous batch completed, because a
review was performed, or because the next tasks require choosing. Stop only when
the user explicitly asks to pause/stop, no ready tasks remain, useful work is
blocked, or continuing would require an unsafe or unavailable decision.

1. Re-read `plans/active.md`, `plans/backlog.md`, and the latest
   `plans/progress.md` entries.
2. Choose one to three bounded tasks whose results would materially advance the
   product direction.
3. Prefer tasks that create reusable data, evaluation, validation, or action
   coverage over tasks that only improve a demo.
4. Assign work only after recording it in `plans/active.md`.
5. Give every worker one task ID, one clear goal, an explicit write scope, and
   focused verification commands.
6. Do local integration or review work while workers run. Do not duplicate a
   worker's write scope.
7. When a worker finishes, inspect the diff, tests, commit, push result, and
   plan updates before starting more work in that area.
8. Update `plans/active.md` and `plans/progress.md`.
9. Reassess after three to five completed worker tasks, after any gate failure,
   or when multiple residuals point to the same missing capability, then assign
   the next ready task unless a concrete blocker prevents it.

The coordinator may briefly let the active set drain while reviewing results,
but should not leave it drained when ready work exists. A short checkpoint for
choosing the right next task is better than parallel work that does not move the
project, but the checkpoint should normally end with new assignments.

## Model Selection

Use this policy when the runtime supports model-level selection:

- Coordinator: `xhigh`.
- Default worker: `high`.
- Mechanical worker: `medium`.
- Architecture/research worker: `xhigh`.

Use `high` for most bounded worker slices: implementation, focused tests,
evidence runs, small docs updates, and command/report plumbing.

Use `medium` only for low-risk mechanical tasks with clear patterns, such as
recording command output, formatting docs, or adding straightforward fixtures.

Use `xhigh` for workers only when the task itself demands deeper reasoning:
planner/model interface changes, structured action family design, residual
clusters spanning subsystems, training-objective decisions, or data strategy
with long-term consequences.

Do not compensate for vague assignments by raising the worker model level. Split
the task until a `high` worker can usually execute it cleanly.

## Parallelism Policy

Default parallelism is two workers. The coordinator may use three only when
tasks are independent, valuable, and have disjoint write scopes.

Good parallel tasks:

- one worker adds a GreenShot-7 fixture while another audits prompt corpus
  labels
- one worker runs/records transition matrix evidence while another implements a
  small request-spec validator
- one worker writes docs for a completed workflow while another fixes focused
  tests in an unrelated module

Bad parallel tasks:

- two workers editing the same planner, parser, or test file
- broad refactors without a concrete acceptance test
- workers adding new actions without residual evidence that the action is needed
- dataset expansion that is not tied to provenance, splits, and evaluation

## Task Size

A good worker task should fit this shape:

```md
### TASK-ID: Short Title

- Goal:
- Why now:
- Write scope:
- Do not touch:
- Acceptance:
- Tests:
- Progress update required:
```

If a task cannot be described this way, it is too vague for a worker. Split it
or keep it with the coordinator.

## Review Cadence

Do a coordinator review when any of these happen:

- three to five worker iterations complete
- a product gate blocks guarded use
- a residual report shows a repeated failure family
- the active queue drifts away from `plans/backlog.md`
- workers are mostly producing docs or fixtures without new validation signal
- a task starts requiring broad architecture changes

Review output should be a small edit to `plans/active.md`, `plans/backlog.md`,
or `plans/progress.md`, not a new daily plan. After the review, continue the
loop by dispatching the next ready task or recording the blocker that prevents
dispatch.

## Capability Direction

Use the realistic target as the stepping stone:

- reliable request-to-repo tasks for narrow Python apps and libraries
- strong prompt/spec/action/outcome records
- typed action builders instead of free-form patch generation
- retrieval and rankers over structured records
- hidden-like tests and subprocess checks
- transition shadow matrices and residual reports
- conservative gates before product use

Keep the frontier target visible:

- broad Python and library competence
- algorithm synthesis
- long-horizon planning
- flexible source generation when structured actions are insufficient
- local language/code pretraining or strong local encoders
- validation-first product behavior

Do not pretend the realistic target proves the frontier target. Use it to create
the data and system discipline needed to climb.

## Falsifiable Task Selection

Do not replace fixture comfort with a giant vague mandate. The coordinator
should prefer tasks that answer a hard yes/no question quickly:

- Can `j3` generalize outside its own fixtures?
- Can structured actions cover enough real Python edits?
- Can repo-state expose conventions well enough to plan?
- Can local knowledge records replace frontier-LLM runtime intuition for the
  chosen wedge?
- Can validation stay cheap and trustworthy on real checkouts?
- Can ranking or transition gains survive held-out real repositories?

A worker task is high leverage when it can prove one of those questions, fail
one of those questions with a precise residual, or reduce the blocker that
prevents the next proof. GreenShot progress is useful only when it is attached
to that kind of falsifiable question.

## Rabbit-Hole Controls

- If a task fails twice for the same reason, record the residual and escalate to
  coordinator review.
- Do not add dependencies without a clear capability reason.
- Do not add more synthetic data without an evaluation it will improve.
- Do not grow GreenShot tasks with more near-duplicate literals when the real
  gap is prompt understanding, action coverage, or ranking evidence.
- Do not make guarded ranking default while matrix gates say shadow-only.
- Do not rewrite planning docs to create the feeling of progress.

## Progress Entries

Append entries to `plans/progress.md` in this shape:

```md
### YYYY-MM-DD - TASK-ID - Short title

- Owner:
- Files changed:
- Tests:
- Result:
- Commit:
- Push:
- Next:
- Blockers:
```

Use `Commit: none` for coordinator-only uncommitted planning work.
