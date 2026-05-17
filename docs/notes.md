# j3 Notes

Durable reminders from the external repo review and goal discussion. This file
is for project memory, not the live task queue; `plans/strategy.md` remains the source of
truth for current implementation steps.

## Positioning

Do not claim that nobody is doing JEPA for code. That is too broad. SWE-JEPA,
code-jepa-mvp, UEWM, LLM-JEPA, and CWM/WorldRepair make the broader space
non-empty.

The sharper claim is:

> `j3` is trying to turn JEPA-style latent prediction into an actual local,
> structured-action automated program repair loop.

Good short positioning:

> world-model program repair for Python repos.

## Reference Links

Core project:

- j3: https://github.com/andrewarrow/j3

JEPA/code and world-model neighbors:

- SWE-JEPA: https://github.com/arcyleung/SWE-JEPA
- code-jepa-mvp: https://github.com/vvbae/code-jepa-mvp
- UEWM: https://github.com/LT-860514/uewm
- LLM-JEPA: https://github.com/rbalestr-lab/llm-jepa
- CWM: https://github.com/facebookresearch/cwm
- WorldRepair: no separate GitHub repo verified in this review; paper:
  https://openreview.net/forum?id=xG3Chtifiz

Local/search-based and APR references:

- Darjeeling: https://github.com/squaresLab/Darjeeling
- DL4PatchCorrectness: https://github.com/TruX-DTF/DL4PatchCorrectness
- PyGGI: https://github.com/coinse/pyggi
- Recoder: https://github.com/pkuzqh/Recoder
- T5APR: https://github.com/h4iku/T5APR
- MultiMend: https://github.com/h4iku/MultiMend
- CoditT5: https://github.com/EngineeringSoftware/CoditT5
- BugsInPy: https://github.com/soarsmu/BugsInPy

LLM coding-agent references:

- SWE-agent: https://github.com/SWE-agent/SWE-agent
- OpenHands: https://github.com/OpenHands/OpenHands
- AutoCodeRover: https://github.com/AutoCodeRoverSG/auto-code-rover
- Agentless: https://github.com/OpenAutoCoder/Agentless

## North Star vs Milestones

Codex-level Python editing quality is the long-term bar, not the next milestone.
The near-term proof should be much narrower:

- generate a passing structured candidate for constrained failing pytest tasks
- rank passing candidates before decoys
- beat random/heuristic structured candidate order
- reduce test executions before first green
- generalize to held-out task families and then small real repos
- eventually solve mined git-history or BugsInPy-style bugs without
  LLM-generated patches

Codex/GPT can help build the infrastructure quickly, but the thesis should be
judged by evals and learning signal, not by how much code an LLM can write for
the repo.

## Current Strategic Decision

Keep building the pre-neural structured repair loop. Do not pause for broad
integration of outside projects and do not start the main neural JEPA track
until the benchmark, candidate outcome data, and ranker diagnostics are broad
enough to expose regressions.

The next valuable work is still:

- richer candidate outcome rows
- candidate deduplication and outcome caching
- target context and call/traceback distance features
- held-out task-family validation
- a simple local/random/search baseline
- hard-negative mining from high-ranked failed candidates

## Useful External Lessons

Darjeeling is the best engineering reference for local repair infrastructure:
borrow candidate outcome caching, equivalent-patch detection, selected/remainder
test phases, test ordering, and clean separation between patch generation and
evaluation.

DL4PatchCorrectness is useful for ranker discipline: borrow before/after
diff/AST delta features, hard negatives, correctness metrics, and calibration
thinking.

PyGGI is useful as a baseline, not architecture. Compare `j3` against random or
local search over the same structured candidate space on pass@1, solved count,
candidate count, and time-to-first-green.

Recoder is useful conceptually: keep actions syntax-aware, typed, and capable of
copying or filling project-specific identifiers. Its edit-decoder ideas are more
useful than its old implementation stack.

SWE-JEPA is the closest conceptual JEPA/code project, but it is representation
and steering work rather than local structured repair. Save its lessons for the
future neural track: full-context latent targets, contrastive/retrieval metrics,
static probes, and caution around representation collapse.

## Risks To Keep Visible

Synthetic bugs may not transfer to real repo repair. Mutation tasks are useful
for tight iteration, but real bugs involve missing concepts, API misuse,
multi-file behavior, unclear intent, and architectural context.

Action-space coverage can become the bottleneck. Structured edits keep search
sane, but they also cap what `j3` can fix. When candidates are missing, add the
smallest typed action that covers the failure family.

Ranking can overfit tiny ladders. In-sample GreenShot pass@1 gains are useful
signals for iteration, not evidence of broad Python editing competence.

Representation quality alone will not solve repair. SWE-JEPA-style latent
features need to plug into a strong action, observation, ranking, and validation
loop.

Do not compare primarily against SWE-agent/OpenHands yet. The first credible
comparison is against local search and heuristic structured ordering, because
that tests `j3`'s core thesis directly.

## Eval Framing

The most important claim to prove before neural work:

> A learned or feature-based structured-action ranker beats random or heuristic
> local search on pass@1, candidate count, and time-to-first-green.

Useful metrics to keep reporting:

- solved / total
- pass@1
- average and median candidates tested
- time-to-first-green
- missing-action count
- bad-ranking count
- weak-hint count
- multiple-passing-candidate count
- per-action and per-task-family pass@1
- calibration for "worth testing" scores
