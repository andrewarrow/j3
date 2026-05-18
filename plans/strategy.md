# j3 Strategy

This is the north star for `j3`. It is not a changelog, daily plan, benchmark
dump, or worker board. Use `plans/active.md`, `plans/backlog.md`, and
`plans/progress.md` for execution. Use focused docs for detailed metrics and
experiment reports.

The purpose of this document is to keep the project aimed at the huge goal:
build a local Python coding agent that can eventually edit, repair, refactor,
and improve real repositories without asking a frontier autoregressive LLM to
write candidate patches.

## The Bet

Current LLM coding agents are powerful, but their core loop is inefficient:

```text
prompt + large repo context -> generate patch tokens -> run tools -> retry
```

That works because frontier LLMs carry enormous priors about language, code,
libraries, and developer intent. It is also wasteful. The agent repeatedly
looks at raw text and samples source tokens when the durable object it needs is
more abstract: the repository state, the goal, the action under consideration,
and the likely consequence of that action.

The JEPA bet is that coding agents should learn compact transition models:

```text
state(repo, request, observations, history) + action(edit)
  -> predicted next state, utility, and remaining uncertainty
```

For video, this is the difference between predicting every pixel in every frame
and understanding that a car is moving across the screen. For code, it is the
difference between reading every token in a repository on every turn and
understanding that a failing assertion points to a boundary condition, a prompt
asks for tests only, or a package layout requires updating `__init__.py`.

If this works, the efficiency difference can be enormous. A local transition
model should not need giant context windows or hosted patch generation for
every edit. It should propose structured actions, predict their consequences,
validate the cheapest plausible path, and learn from the observed outcome.

The hard part is that efficiency does not create competence by itself. LLMs
currently have broad language and code knowledge. `j3` must earn that knowledge
through local data, repo representations, structured actions, docs, tests,
issue/PR transitions, and learned encoders. That bridge is the project.

## Definition Of No-LLM

No-LLM means the production agent does not ask a large autoregressive language
model to author candidate patches or stream source code into the repo.

Allowed:

- local learned encoders for prompts, code, repo state, and observations
- local classifiers, rankers, transition models, retrieval indexes, and planners
- typed code builders and structured source transformations
- local constrained generators if their outputs are validated and represented
  as structured actions
- frontier LLMs during development as scaffolding, review, labeling assistance,
  or teacher signal, when provenance is recorded and eval splits remain clean

Not allowed as the core product path:

- sending repo text to a hosted LLM for patch authoring
- using free-form LLM-generated diffs as the main edit mechanism
- claiming local autonomy when a hidden hosted model is doing the hard edit

The goal is not "never use language models." The goal is to stop depending on a
giant next-token model as the runtime code-writing engine.

## Six-Month Target

The six-month target is not a Codex replacement. It is a credible local Python
repo maintenance agent with a narrow but real wedge:

- add tests to small existing Python libraries without changing production code
- make small library and CLI feature edits following local conventions
- repair common failing-test patterns with structured actions
- update simple package exports, config, and entrypoints
- ask clarification instead of guessing when requirements are under-specified
- run in shadow mode on real repos and explain what it would do
- enter guarded opt-in mode only when held-out real-repo gates pass

By six months, success means a developer can point `j3` at selected small Python
projects and get useful local suggestions or guarded edits for a constrained
task class. Success does not mean broad open-ended software engineering.

## Long-Term Target

The long-term bar remains intentionally high: Codex-level Python repository
editing without frontier LLM patch generation.

That requires all of the following:

- coding-agent English understanding
- repo-state understanding across files, imports, packages, tests, config, docs,
  entrypoints, and conventions
- a broad structured action vocabulary for repair, creation, tests, refactors,
  package metadata, docs, and validation
- code materialization that can turn an intended state change into actual source
  without pasting arbitrary model text
- local knowledge of common Python libraries, tooling, packaging, and idioms
- candidate generation broad enough to contain the right edit
- ranking and transition prediction strong enough to test few candidates
- validation that handles flaky, slow, missing, and partial test suites
- multi-step planning and rollback
- calibrated clarification when the goal is ambiguous
- held-out evidence across repos, domains, prompts, and task families

## What Could Kill The Project

These are the blockers to watch. If they are not solved, commit velocity will
not matter.

### Fixture Overfitting

Synthetic GreenShot tasks and known residuals can make the system look better
than it is. The project must move quickly toward held-out real repositories,
issue/PR replay, and user-like prompts. A new fixture is useful only when it
creates reusable signal: a new action, observation, ranking feature, validation
gate, or real generalization test.

### Action Vocabulary Explosion

Structured actions are efficient because they constrain search. They become a
trap if every new task requires a bespoke action. Add actions from residual
evidence, not imagination. When many tasks need new action kinds, step back and
design a more general builder, transformation family, or representation.

### Code Materialization Gap

Predicting a repo-after embedding is not enough. The agent must materialize the
change into files. This is the biggest technical bridge from JEPA theory to a
working coding agent.

The materialization stack should develop in this order:

1. AST and config transformations for existing code.
2. Typed builders for common files: modules, tests, CLIs, packages, configs.
3. Repo-convention-aware builders that inspect surrounding code.
4. Constrained local generators for small source regions, wrapped as structured
   actions with validation and rollback.
5. Learned proposal models only after non-neural builders and rankers expose
   clear residuals.

### Missing Local Knowledge

Frontier LLMs know pytest, packaging, FastAPI, argparse, pandas, typing,
tracebacks, docs, and idioms because they were pretrained on huge corpora. `j3`
must acquire useful subsets of that knowledge locally:

- mine issue/PR transitions with provenance and stable splits
- index package docs and README examples
- learn repo conventions from the current project
- store outcomes from every candidate it tries
- encode library-specific concepts as data, not one-off rules

### Weak Validation

Tests are the truth source, but real tests are slow, incomplete, flaky, and
sometimes absent. `j3` needs validation as a first-class system:

- test discovery and selection
- subprocess, import, lint, type, and smoke checks
- timeout and flaky-test handling
- generated hidden-like checks for small tasks
- confidence reporting when validation is partial
- rollback after failed edits

### Human Bottleneck

An agent loop can produce many commits. One human still has to enforce honest
evals, prevent overfitting, choose product wedges, review risky architecture,
and decide when a result is not meaningful. The operating model should multiply
execution while keeping strategic choices explicit.

## Architecture

`j3` should stay decomposed. Each layer has a measurable contract.

### Prompt And Intent

Input:

- user request
- optional repo context
- optional tool failure or issue text
- optional docs, examples, README, or existing tests

Output:

- structured request spec
- task type, domain, artifacts, interfaces, constraints, and features
- explicit vs inferred requirements
- confidence and ambiguity fields
- clarification action when needed

This layer handles coding-agent English, not all natural language.

### Repo And Observation State

The repo state must be compact, inspectable, and stable:

- files, packages, imports, modules, functions, classes, methods
- calls, symbols, exports, config, entrypoints, tests, fixtures, docs
- source hashes and embeddings
- tool observations: pytest, traceback, mypy, ruff, stdout, stderr, warnings
- request-derived target observations

The repo representation is the substrate for planning and transition
prediction. If it cannot see the relevant convention, the planner will guess.

### Goal Specification

The request spec is the contract between language and editing. It describes the
desired repo state without containing raw implementation text.

Examples:

- create a small Python CLI
- add tests for an existing function
- add one feature following local conventions
- repair a failing behavior
- update package exports or metadata
- refactor without behavior change
- ask a clarification

### Structured Actions

Actions are typed and auditable:

- repair AST/config/text transformations
- greenfield builders for modules, tests, CLIs, packages, configs, and docs
- existing-repo builders for tests-only edits and convention-following edits
- refactor actions with behavior-preservation checks
- validation, clarification, rollback, and stop actions

Actions should remain machine-readable so ranking, transition prediction,
validation, explanation, and training can all consume the same records.

### Candidate Ranking

Candidate ranking predicts which action should be tried first:

- Does the action match the prompt/spec?
- Does it address the failing observation?
- Is the target local to the relevant repo graph?
- Does the candidate preserve conventions?
- Is it small enough and semantically plausible?
- Is it validated or likely to validate cheaply?
- Is it preferred when multiple candidates pass?

Ranking should beat simple baselines before it influences production routing.

### JEPA Transition Model

The transition layer predicts consequences in latent state:

```text
s(repo_before, request_spec, observations, history) + a(action)
  -> repo_after_target, observation_delta, utility, uncertainty
```

The first useful version does not need to generate code. It needs to:

- distinguish source-changing, tests-only, clarification, and no-op outcomes
- predict whether an action family is aligned with the goal
- rank candidate futures before expensive validation
- expose residuals that say what representation or data is missing

### Planner And Policy

The planner chooses bounded next actions:

- inspect repo
- ask clarification
- propose candidates
- apply one structured edit
- run selected validation
- rollback
- continue
- stop with evidence

Every planner decision should leave an outcome row suitable for training.

## Hard Falsifiable Questions

The next tasks should prove or disprove these before expanding demos:

1. Can `j3` generalize outside its own fixtures?
2. Can structured actions cover enough real Python edits?
3. Can repo-state expose conventions well enough to plan?
4. Can local knowledge records replace frontier-LLM runtime intuition for the
   selected Python wedge?
5. Can validation stay cheap and trustworthy?
6. Can ranking and transition gains survive held-out real repositories?

Every GreenShot, model, data, or documentation task should attach to at least
one of these questions. If it cannot, it belongs below the hard-proof queue.

## Real-Repo Eval Ladder

Do not claim broad progress from local fixtures alone. Move through these gates.

### Gate 0: Fixture Reliability

Use GreenShot and unit tests to keep regressions visible.

Required signal:

- deterministic focused tests
- candidate outcome rows
- residual classification
- no hidden hosted usage

### Gate 1: Held-Out Small Repos

Create or collect small real Python repos with clean licenses and stable tests.

Task classes:

- tests-only edits
- one-file library changes
- simple CLIs
- package export updates
- config and entrypoint changes

Required signal:

- repo-level split, not prompt paraphrase split
- hidden-like checks
- no train/test leakage by task family
- pass@1, pass@k, candidates tested, runtime, and residual groups

### Gate 2: Issue/PR Replay

Use reviewed issue/PR records:

- issue or PR text as prompt
- repo-before checkout
- accepted diff as reference
- validation commands when available
- license and terms recorded

The goal is not exact diff match. The goal is behaviorally valid local edits
that solve the same request.

### Gate 3: Shadow On Real Projects

Run on real repos without changing production routing:

- generate advice rows
- compare against existing deterministic ranking
- record what would have been edited
- run validation where safe
- keep transition ranking shadow-only until gates pass

### Gate 4: Guarded Opt-In

Allow edits only for task classes that pass held-out gates:

- narrow task type
- bounded write scope
- clean validation
- rollback available
- confidence reported
- user-visible diff and rationale

### Gate 5: Broader Agent

Only after repeated real-repo success:

- multi-step plans
- cross-file feature work
- repo-specific conventions
- refactors
- docs and tests together
- broader package ecosystem support

## Data Strategy

Data is the product moat if this approach works.

Collect every example as a transition record:

```text
prompt / issue / observation
repo_before
request_spec
action candidates
chosen action
validation result
repo_after or blocked target
residual label
provenance
split
```

Prioritize:

- real issue/PR pairs with reviewed provenance
- candidate outcomes from actual repair attempts
- prompt/spec rows written in coding-agent English
- docs and README examples linked to behavior
- hard negatives where tempting edits are wrong
- clarification examples, not only success cases

Quality rules:

- stable splits by repo, domain, task family, and prompt family
- no training on paraphrases of held-out tasks
- synthetic data marked as synthetic
- source licenses and terms recorded
- generated artifacts kept out of git unless small and intentional
- exact command lines recorded for reproducibility

Scale targets:

- 100 to 300 curated prompt/spec rows for schema shakeout
- 1,000 to 3,000 rows for first local prompt classifiers
- 10,000 to 50,000 prompt/spec/repo examples for credible generalization
- 100,000+ examples for serious local pretraining

## Model Strategy

Keep simple baselines alive. A learned model matters only when it beats them on
held-out evidence.

### Representation Learning Roadmap

`j3` should not blur deterministic indexing, lightweight learned ranking, and
neural JEPA training. They are different stages with different evidence bars.

Stage 0 is the current scaffolding: structured records plus deterministic
feature hashing. Source, prompt, repo, and transition records are converted into
fixed-size local vectors by hand-designed features and stable hashing. This is
fast, reproducible, inspectable, and useful for retrieval, smoke ranking,
residual reports, and artifact schemas. It is not a claim of deep semantic
understanding.

Stage 1 is sparse or linear learning over structured features. Candidate
rankers and scorer baselines can learn weights from outcome rows while staying
cheap and explainable. This stage should continue until it stops improving
held-out gates.

Stage 2 is small local neural encoders for prompts, code regions, repo state,
and tool observations. These models should learn embeddings from curated
prompt/spec rows, docs/examples, issue/PR transitions, candidate outcomes, and
hard negatives. Their first job is to beat feature-hashing retrieval and linear
rankers on held-out repos, not to generate source.

Stage 3 is the real JEPA transition model:

```text
repo_before + request_spec + observations + action
  -> predicted repo_after / observation_delta / utility / uncertainty
```

This model should be trained from validated transitions, failed candidates, and
blocked clarification outcomes. It should predict consequences and rank futures
before validation, while leaving materialization to structured actions and
bounded generators.

Stage 4 is broader local pretraining over code, docs, tests, issues, PRs, and
candidate outcomes. This is the stage that can start replacing some of the
world knowledge frontier LLMs currently provide. It requires much larger data,
strong provenance rules, stable splits, and enough compute planning to avoid
confusing a local experiment with frontier-scale training.

Entry rules:

- Do not train neural encoders until the record schemas and splits are stable.
- Do not claim neural gains unless they beat deterministic feature-hashing and
  linear baselines on held-out repos and issue/PR replay rows.
- Keep learned model outputs in shadow mode until product gates pass.
- Require every learned decision to leave inspectable evidence: nearest
  examples, action records, feature attribution, or residual labels.
- Prefer smaller local models that improve a bounded gate over larger models
  with vague aggregate metrics.

### Baselines

- rule-based prompt/spec parser for narrow domains
- deterministic builders and repair generators
- sparse or linear rankers over structured features
- retrieval over prior prompts, specs, actions, and outcomes

### Prompt Encoder

Predict structured fields:

- task type
- repo mode
- artifacts
- domain
- interfaces
- features
- constraints
- inferred defaults
- ambiguity and clarification fields

The output is a spec, not source code.

### Repo Encoder

Encode the repo graph and tool observations:

- file/module/package graph
- symbols and references
- tests and fixtures
- config and entrypoints
- docs and examples
- failures and assertions

### Candidate Ranker

Rank actions using:

- action kind and params
- prompt/spec fields
- repo graph locality
- observation alignment
- AST/config/source deltas
- validation history
- preferred-positive labels
- hard negative features

### Transition Model

Predict latent outcomes:

- source-changing vs no-change vs clarification
- expected validation status
- repo-after embedding target
- observation delta
- utility and uncertainty
- residual reason when wrong

### Planning Policy

Learn when to inspect, edit, validate, clarify, rollback, or stop. Start with
deterministic policy. Move to learned policy only after enough outcome rows
exist to evaluate it honestly.

## Action Strategy

Do not grow actions as a wish list. Grow them from residuals.

Add a new action when:

- the correct edit cannot be expressed by existing actions
- the need appears in held-out or real-repo evidence
- validation can prove the action worked
- the action generalizes beyond one handcrafted fixture

Do not add a new action when:

- the correct candidate already exists and ranking is the problem
- the fixture was invented only to justify the action
- the change is better handled by a more general builder
- validation cannot distinguish success from a plausible no-op

Near-term action priorities:

- existing-repo tests-only edits
- repo-state-aware package convention edits
- small library and CLI builders
- clarification as a first-class public outcome
- candidate-after or AST-delta observation for ranking

## Product Wedge

The first usable product should be narrow and trustworthy:

```text
local Python repo maintenance for small projects
```

Start with:

- tests-only edits for one-file and small-package libraries
- conservative repair suggestions for failing pytest tasks
- small feature additions following obvious local conventions
- package export and config updates
- CLI/library scaffolds with tests

User promise:

- runs locally
- shows planned action before risky edits
- validates or reports partial confidence
- never silently sends repo code to a hosted model
- asks clarification instead of guessing high-risk requirements
- leaves an auditable transition record

## Six-Month Readiness Criteria

By the six-month mark, `j3` should be judged against these criteria:

- At least one real-repo task class passes held-out Gate 2 evidence.
- Shadow mode produces useful advice on unfamiliar small Python repos.
- Guarded opt-in is enabled only for task classes with passing gates.
- Prompt/spec parsing handles common coding-agent English in the chosen wedge.
- Repo-state coverage includes packages, imports, functions, classes, tests,
  configs, entrypoints, docs, and parse errors.
- The system has a tests-only existing-repo path and at least one
  convention-following existing-repo edit path.
- Transition ranking remains shadow-only unless it beats existing rank order on
  held-out suites.
- Every product claim cites reproducible commands and residual reports.

If those are met, the project is a serious local coding-agent research product.
If they are not met, do not claim readiness.

## Operating Principles

- Optimize for honest evidence over demo breadth.
- Prefer reusable action surfaces over one-off fixtures.
- Prefer real held-out repos over more synthetic variants.
- Keep production routing conservative until gates pass.
- Treat clarification as success when requirements are genuinely ambiguous.
- Record residuals precisely: missing action, bad ranking, weak observation,
  weak prompt/spec, validation gap, materialization gap, or data leakage.
- Do not add dependencies without a capability reason.
- Do not rewrite planning docs to manufacture progress.
- Every worker batch should leave the system easier to evaluate.

## Stop And Pivot Conditions

Pause fixture growth when:

- new tasks are mostly more literal or typo variants
- metrics improve only on generated or near-duplicate tasks
- residuals keep pointing to ranking, validation, or prompt gaps instead

Pause action expansion when:

- the existing action set can express the correct edit
- candidate counts grow faster than validation and deduplication
- the action does not have a clear real-repo path

Pause model work when:

- baselines are not strong enough to beat
- data splits are weak or leaky
- residuals cannot explain failures
- the model improves aggregate metrics while hurting product gates

Pivot the product wedge when:

- the chosen wedge cannot produce real-repo wins after repeated residual-driven
  iterations
- validation is too weak to prove success
- users do not trust or want the suggested edits

## Immediate Strategic Queue

Execution details belong in `plans/backlog.md`, but the next strategic slices
should stay aligned with this queue:

1. Rerun tests-only real-repo shadow scoring with actual candidate
   materialization, separating calibration from held-out results.
2. Attempt the first held-out tests-only materializer and record whether the
   failure is repo-state planning, local knowledge, materialization, or
   validation.
3. Start a real one-file feature materialization probe for the largest
   `MAT-001` gap.
4. Convert issue/PR mini replay rows into executable preflight and replay
   attempts with residual labels.
5. Grow local knowledge records only where planners cite them or scoring shows
   missing knowledge residuals.
6. Keep transition ranking and learned models shadow-only until gains survive
   held-out real-repo gates.
7. Reassess the product wedge after each real-repo gate failure instead of
   adding more synthetic fixture variants.

The project should always be able to answer: what real task class became more
reliable, what evidence proves it, and what blocker is next?
