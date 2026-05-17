# j3 Current Plan

This file is the live handoff for the project. Keep it current and remove stale
status. Move long experiments, raw metrics, and hard-negative notes into focused
markdown files instead of letting this plan become a changelog.

## Table of Contents

- [Goal](#goal)
- [Definition of No-LLM](#definition-of-no-llm)
- [Core Thesis](#core-thesis)
- [What Must Exist for Codex-Level Editing](#what-must-exist-for-codex-level-editing)
- [Current Reality](#current-reality)
  - [Existing Data and Runs](#existing-data-and-runs)
- [Strategic Correction](#strategic-correction)
- [System Architecture](#system-architecture)
  - [1. Prompt and Intent Layer](#1-prompt-and-intent-layer)
  - [2. Goal Specification Layer](#2-goal-specification-layer)
  - [3. Repo and Observation Layer](#3-repo-and-observation-layer)
  - [4. Structured Action Layer](#4-structured-action-layer)
  - [5. Candidate Ranking Layer](#5-candidate-ranking-layer)
  - [6. JEPA Transition Layer](#6-jepa-transition-layer)
  - [7. Planning and Validation Layer](#7-planning-and-validation-layer)
- [Prompt Understanding Track](#prompt-understanding-track)
  - [Coding-Agent English](#coding-agent-english)
  - [Implicit Requirement Expansion](#implicit-requirement-expansion)
  - [Clarification Policy](#clarification-policy)
  - [Prompt-to-Spec Schema](#prompt-to-spec-schema)
  - [Prompt Data We Need](#prompt-data-we-need)
  - [Prompt Corpus Scale](#prompt-corpus-scale)
  - [Prompt Data Sources](#prompt-data-sources)
  - [Prompt Data Quality Rules](#prompt-data-quality-rules)
- [Repair and Ranking Track](#repair-and-ranking-track)
  - [Current Repair Capabilities](#current-repair-capabilities)
  - [Current GreenShot Signal](#current-greenshot-signal)
  - [Repair Data We Need](#repair-data-we-need)
- [Greenfield Editing Track](#greenfield-editing-track)
  - [Why This Exists](#why-this-exists)
  - [Greenfield Actions](#greenfield-actions)
  - [GreenShot-7 Request-to-Repo Ladder](#greenshot-7-request-to-repo-ladder)
- [Model Tracks](#model-tracks)
  - [Non-Neural Baselines](#non-neural-baselines)
  - [Trainable Prompt Encoder](#trainable-prompt-encoder)
  - [Trainable Candidate Ranker](#trainable-candidate-ranker)
  - [Repo-State Encoder](#repo-state-encoder)
  - [JEPA Repo-Transition Model](#jepa-repo-transition-model)
  - [Planning Policy](#planning-policy)
- [Evaluation Standards](#evaluation-standards)
  - [Repair Evaluation](#repair-evaluation)
  - [Prompt Understanding Evaluation](#prompt-understanding-evaluation)
  - [Greenfield Evaluation](#greenfield-evaluation)
  - [Benchmark Reporting](#benchmark-reporting)
- [Immediate Next Step](#immediate-next-step)
- [Next Queue](#next-queue)
- [Stop Conditions](#stop-conditions)

## Goal

Build a local, no-LLM Python coding agent that can eventually edit, repair,
refactor, and improve Python repositories at Codex-level quality. The target is
not autocomplete and not a patch-template toy. The target is an agent that can
read a repo, understand a user request or failing observation, choose structured
edits, predict their consequences, validate with tools, and iterate toward
correct code without asking a large language model to write candidate patches.

The long-term bar is intentionally high: become as good at Python code editing
as Codex running a frontier GPT-5.5-style model with high reasoning effort. The
path is staged:

1. Reliable structured repair.
2. Strong candidate-outcome data from real repair attempts.
3. User-prompt understanding for the subset of English used to ask coding agents
   for changes or new code.
4. Greenfield structured editing for new files, tests, and project scaffolds.
5. Trainable ranking and repo-state models.
6. A JEPA-style repo-transition planner that predicts which structured edit
   moves the repo toward the requested target state.

## Definition of No-LLM

No-LLM does not mean no learned language encoder. It means:

- Do not ask a large autoregressive language model to write candidate patches.
- Do not depend on free-form source generation as the core editing mechanism.
- Do use local structured models that encode prompts, repo state, observations,
  actions, and outcomes.
- Do let models rank, predict, classify, retrieve, and plan over structured
  records.

The desired system can read natural-language coding requests, but it should turn
them into structured goal specs and structured actions rather than sampling raw
source code.

## Core Thesis

LLM coding agents are powerful because they combine language understanding,
repo reading, patch generation, and tool feedback. j3 should split those skills
into explicit local components:

```text
user prompt or tool observation
  -> normalized goal / observation record
  -> repo-state representation
  -> structured candidate actions
  -> predicted consequence
  -> validation
  -> next action or stop
```

The JEPA claim is not proven by repairing small literals. It is only credible if
j3 learns to represent desired repo transitions and choose actions that move the
repo toward them, including when the desired state starts as user intent rather
than a failing pytest assertion.

## What Must Exist for Codex-Level Editing

j3 eventually needs all of these capabilities:

- Prompt understanding for coding-agent English.
- Repo understanding across files, imports, functions, classes, tests, config,
  package metadata, and docs.
- Structured actions for repair, refactor, creation, deletion, and test edits.
- Candidate generation that is broad enough to contain the right edit.
- Ranking that puts correct and preferred candidates early.
- Validation with tests, type checks, lint, import checks, and hidden behavior
  checks when available.
- Multi-step planning when one edit exposes the next needed edit.
- Ambiguity handling: infer common defaults when confidence is high, ask a
  clarification when confidence is low.
- Data splits that prove generalization across repos, task families, and prompt
  phrasings.

## Current Reality

The current codebase is strongest as a structured Python repair prototype.

Known useful pieces:

- `j3 eval` can run ranked repair attempts and write candidate outcome JSONL.
- Diagnostics record tested candidates, first passing index, passing candidates,
  failure hints, target context, and preferred patch labels.
- `train-ranker` can train from candidate outcome rows and validate held-out
  tasks or families.
- GreenShot-5 reached a 20-task ladder around multi-file repair, helper/API
  boundaries, imports, warnings, config constants, dictionary keys, signature
  propagation, and bounded multi-step repair.
- GreenShot-6 currently has 69 tasks in the worktree:
  - 48 `git_history`
  - 21 `mutation`
  - 50 `train`, 5 `test`, and 14 tasks with legacy deterministic split
    assignment.
- GreenShot-6 is useful real-package-derived signal, but it is skewed toward
  small existing-file repairs:
  - 39 `change_literal`
  - 14 `change_dict_value`
  - 6 `change_operator`
  - 3 `add_keyword_arg`
  - 2 `swap_call_arg`
  - 1 each for `change_dict_key`, `change_subscript_key`,
    `change_module_constant`, `modify_condition`, and `rename_symbol`.

This is necessary foundation work. It is not enough for the full goal.

### Existing Data and Runs

The project already has local training artifacts, but they are not prompt
understanding data.

Current data:

- `data/transitions/apache-python/*.jsonl` contains mined Python before/after
  file transitions from the Apache-licensed local corpus described in
  `docs/TRAINING.md`.
- `runs/apache-python-git/model.json` is the current prototype repair-ranking
  checkpoint trained from synthetic source transitions plus mined git
  transitions.
- `runs/apache-python-git/examples.jsonl` is the generated transition training
  example dump for that checkpoint.
- `runs/apache-python-git/greenshot-5-candidate-outcomes.jsonl` and
  `runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl` are candidate
  outcome datasets from actual repair attempts.
- `runs/apache-python-git/ranker-*` contains trained candidate-ranker artifacts
  and metrics from those outcome rows.

How these are used today:

- `j3 train --data ... --transitions data/transitions/apache-python` consumes
  Python source and mined git transitions to produce a prototype model under
  `runs/`.
- `j3 eval --checkpoint runs/apache-python-git/model.json ...` uses that model
  to score/rank repair candidates.
- `j3 train-ranker --candidate-outcomes runs/...jsonl` consumes candidate
  outcome rows to train the separate candidate ranker.

What is missing:

- No current `data/` or `runs/` artifact trains prompt-to-spec understanding.
- No current artifact learns from natural-language coding-agent prompts.
- No current training path maps prompt text to new files, hidden behavior
  tests, or greenfield repo outcomes.

So the source/transition/ranker data is real and useful, but it is not enough
for user intent. Prompt data is a new first-class dataset, not a replacement for
the existing repair data.

## Strategic Correction

The project is on track for a repair engine, but not yet on track for a
Codex-level coding agent. The missing first-class track is user intent.

Example:

```text
make me a simple cli python app that's a basic calculator, it should let the
user add two numbers, subtract, etc.
```

The string `etc.` cannot be solved from Python AST repair data alone. A coding
agent must infer that a "basic calculator" commonly includes add, subtract,
multiply, and divide. That inference is prompt understanding plus product/task
prior. It should become a structured prediction:

```json
{
  "task_type": "new_python_cli_app",
  "domain": "calculator",
  "features": ["add", "subtract", "multiply", "divide"],
  "interface": "interactive_cli",
  "arity": 2
}
```

Then structured editing can take over.

Near-term correction:

- Stop treating GreenShot-6 growth alone as evidence of long-term progress.
- Keep GreenShot-6 as the repair/ranking regression gate.
- Start GreenShot-7 as request-to-repo work.
- Add prompt/spec data and greenfield actions before adding many more typo-like
  `change_literal` tasks.

## System Architecture

### 1. Prompt and Intent Layer

Input:

- User request.
- Optional repo context.
- Optional tool failure.
- Optional existing tests, README, issues, or examples.

Output:

- Structured task spec.
- Confidence scores.
- Ambiguity fields.
- Optional clarification action.

### 2. Goal Specification Layer

The task spec is the contract between natural language and code editing. It
should describe what must exist after editing without containing raw source.

Examples:

- Create a Python CLI app.
- Add a feature to an existing module.
- Fix a failing behavior.
- Refactor without behavior change.
- Add tests for an existing function.
- Update package metadata.

### 3. Repo and Observation Layer

Normalize repo state and observations:

- Files, packages, imports, symbols, functions, classes, calls.
- Tests, entrypoints, configs, docs, examples.
- Pytest, mypy, ruff, traceback, stdout/stderr, and assertion hints.
- Prompt-derived desired behavior.

User prompts are observations too. A request like "basic calculator" is a
target-state observation, not a test failure.

### 4. Structured Action Layer

Actions must be typed and inspectable:

- Existing repair actions mutate AST or structured text.
- Greenfield actions create files, functions, tests, CLI entrypoints, config,
  package metadata, and docs.
- Refactor actions preserve behavior while changing names, modules, or APIs.

Actions should remain machine-readable so ranking, JEPA prediction, validation,
and explanation can all consume them.

### 5. Candidate Ranking Layer

Rank candidates by predicted utility:

- Does the action match the prompt/spec?
- Does it address the failing observation?
- Is the target local to the relevant repo graph?
- Does the action produce a preferred patch when multiple patches pass?
- Is the action small enough and semantically plausible?

### 6. JEPA Transition Layer

The JEPA state should include repo, request/spec, observations, and action
history:

```text
s(repo, request_spec, observations, history) + a(edit) -> predicted next state
```

The model should predict whether an action moves the repo toward the requested
target state before running expensive validation.

### 7. Planning and Validation Layer

The planner should:

- Propose bounded candidate actions.
- Use ranker and JEPA predictions to choose candidates.
- Apply one or more structured edits.
- Run selected validation.
- Reparse observations.
- Continue, ask a clarification, or stop.

## Prompt Understanding Track

### Coding-Agent English

j3 does not need all of English. It needs the subset people use when asking a
coding agent for code changes.

This subset includes:

- Creation verbs: make, create, build, scaffold, add, implement.
- Repair verbs: fix, debug, make pass, handle, support.
- Refactor verbs: rename, split, extract, clean up, move, simplify.
- Test verbs: add tests, cover, assert, reproduce.
- Artifact nouns: CLI, API, script, package, module, class, function, test,
  config, README, pyproject, endpoint.
- Behavior nouns: calculator, parser, cache, validator, serializer, logger.
- Constraints: simple, basic, local-only, no dependencies, type hints, async,
  backwards compatible.
- Implied scope words: etc., basic, usual, standard, CRUD, REST, auth, config.
- Acceptance phrases: should let the user, when I run, returns, prints, raises.

### Implicit Requirement Expansion

Some words imply conventional defaults. j3 should learn these as structured
priors, not hard-code every phrase forever.

Examples:

- "basic calculator" usually implies add, subtract, multiply, divide.
- "simple CLI app" usually implies an executable entrypoint, argument parsing or
  an interactive loop, help text, and stdout behavior.
- "CRUD API" usually implies create, read, update, delete operations.
- "add auth" is ambiguous and should often ask a clarification unless repo
  conventions strongly imply the method.
- "etc." should expand only when the domain has a high-confidence canonical set.

The model output should include confidence and source of inference:

```json
{
  "inferred": [
    {
      "field": "features",
      "value": ["multiply", "divide"],
      "reason": "basic_calculator_default_operations",
      "confidence": 0.86
    }
  ]
}
```

### Clarification Policy

When confidence is high, infer and proceed. When confidence is low, ask a short
clarifying question instead of fabricating requirements.

Examples:

- Proceed: "basic calculator" -> add/subtract/multiply/divide.
- Ask: "add auth" in an empty repo -> password, OAuth, token, or session?
- Ask: "make it better" -> no concrete target.
- Proceed with local convention: "add another endpoint like the existing one"
  when route patterns and tests make the target clear.

Clarification is a structured action:

```json
{"action": "ask_clarification", "field": "auth_method", "options": [...]}
```

### Prompt-to-Spec Schema

Create a versioned request spec schema. Initial fields:

- `schema_version`
- `request_text`
- `task_type`
- `language`
- `repo_mode`: `new_repo`, `existing_repo`, `unknown`
- `domain`
- `artifacts`
- `features`
- `interfaces`
- `constraints`
- `acceptance_tests`
- `hidden_eval_expectations`
- `clarifications_needed`
- `inferred_defaults`
- `confidence`
- `source_type`
- `split`

Calculator example:

```json
{
  "schema_version": "request-spec-v1",
  "task_type": "create_app",
  "language": "python",
  "repo_mode": "new_repo",
  "domain": "calculator",
  "artifacts": ["calculator.py", "tests/test_calculator.py"],
  "features": ["add", "subtract", "multiply", "divide"],
  "interfaces": [{"kind": "cli", "style": "interactive_or_argparse"}],
  "constraints": ["simple", "two_number_operations"],
  "acceptance_tests": [
    {"operation": "add", "inputs": [2, 3], "expected": 5},
    {"operation": "subtract", "inputs": [5, 2], "expected": 3},
    {"operation": "multiply", "inputs": [4, 3], "expected": 12},
    {"operation": "divide", "inputs": [8, 2], "expected": 4}
  ],
  "inferred_defaults": [
    {"field": "features", "value": ["multiply", "divide"], "confidence": 0.86}
  ],
  "clarifications_needed": []
}
```

### Prompt Data We Need

Training should cover prompt-to-spec, spec-to-plan, and plan-to-repo outcomes:

- Prompt -> structured task spec.
- Prompt + repo summary -> structured task spec.
- Prompt + repo_before -> action sequence.
- Prompt + repo_before -> repo_after latent target.
- Prompt + spec -> hidden behavioral tests.
- Prompt pairs with similar wording but different desired behavior.
- Ambiguous prompts labeled with the clarification that should be asked.

This is not general natural-language training. It is coding-agent request
language aligned to repo changes.

### Prompt Corpus Scale

We are not ready to train a serious prompt encoder yet. We are ready to define
the schema, collect seed data, build deterministic baselines, and make small
GreenShot-7 request-to-repo tasks.

Scale targets:

- 100 to 300 hand-authored prompt/spec rows:
  - Purpose: schema shakeout, rule baselines, prompt phenomena inventory.
  - Good enough to test `etc.`, ambiguity, task type labels, and request-spec
    validation.
  - Not enough for credible generalization claims.
- 1,000 to 3,000 curated rows:
  - Purpose: train a small prompt classifier/spec parser for common coding
    requests.
  - Should cover creation, feature addition, bug fix, refactor, tests, config,
    docs, and clarification.
- 10,000 to 50,000 prompt/spec/repo examples:
  - Purpose: robust held-out prompt understanding across repos and domains.
  - Should include mined issue/PR pairs, normalized commit/PR descriptions,
    human-authored prompts, and synthetic data marked by provenance.
- 100,000+ examples:
  - Purpose: serious local prompt encoder pretraining.
  - Needed if the model must handle many domains, paraphrases, repo styles, and
    implicit requirement patterns without brittle rules.

The immediate corpus lives outside the repo at `../prompts`:

- `../prompts/README.md`
- `../prompts/coding_agent_prompts_seed.jsonl`

That seed file is intentionally small and human-authored. It should be treated
as bootstrapping data for schema and evaluation, not model-scale training data.

### Prompt Data Sources

Use multiple sources and tag every record with provenance.

1. Hand-authored seed tasks.
   - Write small, precise prompts for CLI apps, library functions, config
     changes, tests, docs, refactors, and bug fixes.
   - Include vague variants with `etc.`, `simple`, `basic`, and missing details.

2. Public issue/PR pairs.
   - Link issue text or PR description to repo-before and accepted diff.
   - Extract structured labels: task type, files touched, action kinds, tests.
   - Use only data whose license and terms permit local training.

3. Commit messages plus diffs.
   - Useful when issue text is absent.
   - Lower quality for prompt understanding, but useful for transition modeling.

4. README and docs examples.
   - Examples imply expected behavior.
   - Useful for "make a CLI like this" and API usage tasks.

5. Coding benchmark prompts.
   - Use for prompt-to-behavior and hidden-test evaluation.
   - Prefer repo-edit benchmarks over single-function-only tasks.

6. Synthetic prompt/spec pairs from deterministic templates.
   - Good for bootstrapping schema coverage.
   - Must be marked synthetic and held out separately from real user-like text.

7. Local human-authored prompts.
   - Build a small curated set of prompts people would actually type into a
     coding agent.
   - Include shorthand, typos, ambiguity, and domain assumptions.

### Prompt Data Quality Rules

- Store raw prompt, normalized spec, repo-before hash, repo-after hash, and
  validation command.
- Keep stable splits by repo, domain, and prompt family.
- Do not train and test on paraphrases of the same exact task.
- Track whether defaults were explicit, inferred, or ambiguous.
- Include negative examples where a tempting inference is wrong.
- Include clarification examples, not only successful direct edits.
- Do not use exact prompt strings as ranker features for held-out claims.
- Keep licensing and source provenance in the dataset.

## Repair and Ranking Track

### Current Repair Capabilities

Implemented action families include:

- `replace_expr`
- `insert_guard`
- `change_literal`
- `change_operator`
- `change_subscript_key`
- `change_dict_key`
- `change_dict_value`
- `add_dict_key`
- `swap_call_arg`
- `add_keyword_arg`
- `add_import`
- `add_import_fallback`
- `change_attribute`
- `change_module_constant`
- `wrap_try_except`
- `add_fallback_warning`
- `change_return_value`
- `rename_symbol`
- `modify_condition`
- `propagate_signature`

Observation parsing includes pytest failed nodes, assertion comparisons, numeric
deltas, traceback frames, import/name/attribute/key/type errors, mypy, ruff, and
selected pytest warning strings.

### Current GreenShot Signal

Treat current GreenShot numbers as repair-loop smoke checks, not benchmark proof
of broad coding competence.

Current worktree:

```text
GreenShot-6 tasks: 69
source_type: git_history=48, mutation=21
split: train=50, test=5, legacy deterministic=14
dominant action: change_literal=39
```

Latest known standard refresh before the newest task solved all 68 tasks with
`pass@1=51/68`, average candidates `7.59`, and a clean GreenShot-6 `split:test`
held-out ranker validation. After adding the current task, refresh outcomes
before claiming new metrics.

### Repair Data We Need

- More real git-history repairs that are not only typo/message literals.
- More held-out tasks where the correct candidate exists but ranking is hard.
- More tasks where missing actions are exposed by real data, not invented lists.
- More candidate outcomes with stable splits, source type, task family, action
  kind, pass label, preferred-positive label, AST delta, locality, and relation
  metadata.
- More multi-step repairs where the first edit changes the observed failure.

## Greenfield Editing Track

### Why This Exists

Repair benchmarks start from failing code. Codex-level work often starts from a
request and an empty or partial repo. j3 needs greenfield editing to handle:

- "make me a simple CLI app"
- "add a small FastAPI endpoint"
- "create tests for this parser"
- "add pyproject metadata"
- "split this script into a package"

### Greenfield Actions

Add actions only as benchmarks demand them:

- `create_file`
- `create_package`
- `create_test_file`
- `add_function_def`
- `add_class_def`
- `add_argparse_cli`
- `add_interactive_cli_loop`
- `add_pyproject_script`
- `add_import_for_created_symbol`
- `add_readme_usage`
- `add_hidden_behavior_test`
- `wire_entrypoint_to_function`

These should build AST and config structures through typed builders where
possible, not paste free-form source blobs.

### GreenShot-7 Request-to-Repo Ladder

GreenShot-7 should be the first prompt-to-repo benchmark.

Initial ladder:

1. Empty repo -> basic calculator CLI.
   - Prompt includes `etc.`.
   - Expected inference: add, subtract, multiply, divide.
   - Hidden tests check CLI behavior.

2. Empty repo -> one-file library function plus tests.
   - Prompt describes behavior in English.
   - Hidden tests check edge cases not stated verbatim.

3. Existing tiny repo -> add one feature following local conventions.
   - Prompt references "like the existing command".
   - Tests check convention following.

4. Existing repo -> add test coverage only.
   - Prompt asks for tests, not behavior changes.
   - Validation checks no production change unless needed.

5. Ambiguous prompt -> ask clarification.
   - Prompt lacks a necessary choice.
   - Correct action is `ask_clarification`, not editing.

## Model Tracks

### Non-Neural Baselines

Before neural claims, keep simple baselines:

- Rule-based prompt-to-spec for a few domains.
- Handwritten action generation.
- Linear or sparse ranker over structured features.
- Retrieval over prior specs and action outcomes.

These baselines make it clear what the neural track actually improves.

### Trainable Prompt Encoder

Train a local model to encode coding-agent English into structured spec fields:

- Task type.
- Artifact type.
- Domain.
- Feature set.
- Constraints.
- Interface.
- Explicit vs inferred requirements.
- Ambiguity and clarification fields.

The prompt encoder should predict structured labels, not source code.

### Trainable Candidate Ranker

Continue ranking structured edit candidates using:

- Action kind and params.
- Target node and repo context.
- Parsed observations.
- Prompt/spec fields.
- AST and config deltas.
- Candidate pass/fail outcomes.
- Preferred-positive labels when multiple patches pass.

### Repo-State Encoder

Build a compact repo graph:

- Files, modules, imports.
- Functions, classes, methods.
- Calls and symbol references.
- Tests and fixtures.
- Config and entrypoints.
- Docs and examples.

The encoder should support both repair and greenfield planning.

### JEPA Repo-Transition Model

Train from:

- Synthetic structured transitions.
- Mined git-history transitions.
- Candidate outcome rows.
- Prompt/spec/repo-before/repo-after triples.
- Failed candidate negatives.

Prediction target:

```text
s(repo_before, request_spec, observations) + a
  -> predicted latent repo_after / observation_delta / utility
```

### Planning Policy

The planner should choose between:

- Apply a repair candidate.
- Create or modify files for a request spec.
- Run a validation command.
- Ask a clarification.
- Stop and report success/failure.

It should be bounded, observable, and trained from action outcomes.

## Evaluation Standards

### Repair Evaluation

Report:

- solved / total
- pass@1
- average and median candidates tested
- missing-action count
- bad-ranking count
- weak-hint count
- multiple-passing-candidate count
- per-action pass@1
- per-task-family pass@1
- source-type pass@1
- average test runtime

### Prompt Understanding Evaluation

Report:

- prompt-to-spec exact field accuracy
- semantic feature accuracy
- inferred-default precision and recall
- ambiguity detection precision and recall
- clarification accuracy
- robustness to paraphrase
- generalization to held-out domains and repos

### Greenfield Evaluation

Report:

- hidden-test pass rate
- repo builds/imports
- generated entrypoint works
- requested files exist
- no unnecessary files
- no dependency additions unless requested
- prompt requirements satisfied
- inferred requirements satisfied when confidence was high
- clarification chosen when confidence was low

### Benchmark Reporting

Keep GreenShot-4 as a periodic regression gate.
Keep GreenShot-5/6 as repair and ranking gates.
Create GreenShot-7 for prompt-to-repo.

For day-to-day work, use the smallest focused test that proves the touched
behavior. Run full `pytest -q` only as an intentional integration gate.

## Immediate Next Step

Do this next, before adding more GreenShot-6 literal/typo tasks:

1. Finish the current GreenShot-6 bookkeeping.
   - Run the focused loader and patching tests for the current 69-task state.
   - Refresh GreenShot-6 outcomes with `--explore-after-pass 5`.
   - Rerun the GreenShot-6 `split:test` held-out ranker validation.
   - Update this plan only with fresh metrics that were actually run.

2. Normalize the new prompt seed corpus.
   - Validate `../prompts/coding_agent_prompts_seed.jsonl`.
   - Add a small prompt-corpus summary/check command or test.
   - Decide whether prompt data should stay outside the repo, be referenced from
     `docs/TRAINING.md`, or be copied into `data/prompts/` once the schema is stable.

3. Add `docs/REQUEST_SPEC.md`.
   - Define `request-spec-v1`.
   - Include the calculator prompt with `etc.` expanded to multiply/divide as a
     high-confidence inferred default.
   - Include at least one ambiguous prompt where the correct action is
     clarification.

4. Start GreenShot-7 with the calculator CLI request-to-repo task.
   - Empty repo input.
   - Prompt: "make me a simple cli python app that's a basic calculator, it
     should let the user add two numbers, subtract, etc."
   - Expected spec: add, subtract, multiply, divide.
   - Hidden tests validate behavior.
   - The first implementation may use deterministic prompt-to-spec rules, but
     the data record must be suitable for later training.

## Next Queue

After the immediate step:

- Implement a request-spec loader and validator.
- Add `j3 implement` or equivalent command path for request-to-repo tasks.
- Add the first greenfield actions: `create_file`, `add_function_def`,
  `create_test_file`, and `add_argparse_cli` or `add_interactive_cli_loop`.
- Add five GreenShot-7 seed tasks across creation, feature addition, tests-only,
  convention following, and clarification.
- Create a prompt/spec JSONL dataset format with provenance and stable splits.
- Mine a small issue/PR sample and manually normalize it into request specs.
- Keep GreenShot-6 as the repair regression gate while GreenShot-7 grows.

## Stop Conditions

Pause GreenShot-6 task growth when:

- New tasks are mostly more typo-like `change_literal` examples.
- The held-out ranker is already clean and no new hard negative appears.
- Dataset size increases without new action, ranking, observation, or prompt
  signal.

Pause action expansion when:

- The right candidate already exists and ranking is the actual problem.
- Candidate generation grows faster than validation and deduplication.
- The action is motivated only by a handcrafted fixture.

Pause prompt inference when:

- The system guesses low-confidence requirements instead of asking.
- Prompt/spec data is mostly synthetic templates.
- Evaluation uses exact prompt strings instead of held-out paraphrases,
  domains, and repos.

Start serious JEPA model work only when:

- Repair candidate outcomes have stable, diverse splits.
- Prompt-to-spec records exist for real coding-agent requests.
- GreenShot-7 has request-to-repo tasks with hidden behavioral tests.
- The non-neural baselines are strong enough to be worth beating.
- Failures are categorized well enough to diagnose model regressions.
