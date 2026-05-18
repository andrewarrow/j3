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
   or when multiple residuals point to the same missing capability.

The coordinator may pause all workers. A short pause for choosing the right next
task is better than parallel work that does not move the project.

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
or `plans/progress.md`, not a new daily plan.

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
