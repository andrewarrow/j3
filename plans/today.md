# Today Plan: Learned Prompt Understanding And Intent Fidelity Slice

This 24-hour plan resets the active GreenShot work from "can generate a simple
calculator repo" to "does not overclaim unsupported intent, and can make a small
structured change in an existing generated calculator repo."

The immediate regression is:

```bash
python cli.py implement \
  --prompt "make me a complex graphic calc app" \
  --out ../sample2
```

This should not silently build a simple argparse calculator. The request asks
for a complex graphical calculator app, while the current implementation only
supports a narrow Python CLI calculator. The correct behavior is to ask a
clarification or return an unsupported-intent response before writing calculator
files.

The second target is the next practical path after generation:

```bash
python cli.py change \
  --repo /Users/aa/os/sample \
  --prompt "add exponent support to calculator.py"
```

The exact command name may change during implementation, but the behavior should
be prompt-driven editing of an existing repo, not test-only repair and not a new
repo build.

## Goal For The Next 24 Hours

Build a more honest GreenShot request pipeline that moves toward learned prompt
understanding instead of accumulating hand-written English rules:

```text
natural-language prompt
  -> labeled prompt record
  -> prompt representation / encoder training target
  -> intent/scope prediction with evidence
  -> clarification when requested interface or scope is unsupported
  -> request-spec-v1 only when the predicted request matches supported capability
  -> existing-repo change spec for narrow calculator edits
  -> structured patch actions
  -> validation
  -> prompt/spec/action/outcome row
```

Success means j3 has a concrete data/evaluation path for English prompt
understanding, can say "I cannot safely do that yet" for unsupported UI or
complexity requests, and can make progress toward one small requested change to
an existing calculator repo through structured code edits.

## Non-Goals For Today

- No full GUI, web, desktop, TUI, or graphical calculator generation.
- No broad existing-repo natural-language editing beyond calculator.py.
- No production-quality prompt encoder today. The target is the first concrete
  learned-understanding slice: labeled rows, representation targets, held-out
  evaluation, and a tiny trainable model only if the data is ready.
- No new dependency unless the standard library is clearly insufficient.
- No general free-form source generation.
- No changes to `plan.md` unless the strategic roadmap truly changes.

## Core Problems To Fix

1. The parser treats any calculator-ish prompt as the simple CLI calculator.
2. Prompt understanding is still mostly deterministic English parsing. That is
   useful as an oracle or fallback, but not the main research direction.
3. Interface and complexity requests are not represented as capability
   constraints that a learned encoder can predict.
4. `request-spec-v1` has no clear field for rejected or unsupported interface
   requests beyond generic clarification.
5. `j3 implement` currently creates new repos only.
6. Existing-repo changes are possible only through failing tests, not direct
   user prompts.
7. The prompt seed corpus in `../prompts` has labels that should drive the
   first learned prompt-understanding evaluation, but it has not been profiled
   or wired into training/eval.

## Expected User-Facing Behavior

Unsupported or underspecified graphical request:

```bash
python cli.py implement \
  --prompt "make me a complex graphic calc app" \
  --out /tmp/j3-graphic-calc
```

Expected:

- exits non-zero
- prints a clear clarification or unsupported-scope message
- does not write `calculator.py`
- records a blocked outcome if `--record` is supplied
- says the supported calculator target today is a Python CLI calculator
- asks whether the user wants a simple CLI calculator or a specific graphical
  app scope/framework

Supported new-repo request remains valid:

```bash
python cli.py implement \
  --prompt "make me a simple cli calc" \
  --out /tmp/j3-cli-calc
```

Expected:

- still builds the CLI calculator
- still validates generated tests
- still writes `request-spec.json`
- still records a passing outcome if requested

Existing-repo small change:

```bash
python cli.py change \
  --repo /tmp/j3-cli-calc \
  --prompt "add exponent support"
```

Expected:

- inspects the existing repo enough to confirm it is the known calculator shape
- parses the prompt as a supported calculator feature addition
- updates `calculator.py`
- updates or adds tests
- validates with `python -m pytest tests/test_calculator_cli.py -q`
- records a prompt/spec/action/outcome row when requested

The first supported existing-repo change should be exponent/power:

- canonical feature: `power`
- aliases: `power`, `pow`, `^`, `**`
- behavior: `python calculator.py 2 ^ 3` prints `8`

## Prompt Fixtures To Add

Add or extend fixtures under `examples/greenshot_7/` or a successor directory
with three groups.

Supported new-repo CLI prompts:

- "make me a simple cli calc"
- "make cli app to add two numbers"
- "build a command line calculator for add subtract multiply divide"

Unsupported or clarification prompts:

- "make me a complex graphic calc app"
- "make a graphical calculator"
- "make a gui calculator"
- "make a calculator with a beautiful interface"
- "make a scientific calculator"
- "make a math thing"

Existing-repo change prompts:

- "add exponent support"
- "support power operator"
- "make calculator.py handle 2 ^ 3"
- "add ** as a power alias"
- "change the existing calc to support exponentiation"

Each fixture should carry:

- stable task name
- repo mode: `new_repo`, `existing_repo`, or `unknown`
- expected action: `emit_request_spec`, `ask_clarification`, or
  `emit_existing_repo_change_spec`
- expected domain
- expected interface constraints
- expected features
- expected clarification field and question when blocked

## Spec Shape Updates

Keep `request-spec-v1` backward compatible where possible, but add explicit
structured fields if needed:

```json
{
  "requested_interfaces": [{"kind": "gui", "confidence": 0.89}],
  "supported_interfaces": [{"kind": "cli", "style": "argparse"}],
  "unsupported_requirements": [
    {
      "field": "interfaces",
      "value": "graphic",
      "reason": "graphical_calculator_not_supported"
    }
  ],
  "clarifications_needed": [
    {
      "field": "interfaces",
      "question": "This slice only supports a Python CLI calculator. Do you want a CLI calculator, or should a graphical app scope/framework be specified?"
    }
  ]
}
```

For existing-repo changes, use a focused change spec such as:

```json
{
  "schema_version": "existing-repo-change-spec-v1",
  "task_type": "modify_app",
  "repo_mode": "existing_repo",
  "domain": "calculator",
  "prompt": "add exponent support",
  "target_files": ["calculator.py", "tests/test_calculator_cli.py"],
  "features_to_add": ["power"],
  "operation_aliases": {
    "power": ["power", "pow", "^", "**"]
  },
  "validation": {
    "commands": ["python -m pytest tests/test_calculator_cli.py -q"]
  }
}
```

## Structured Existing-Repo Action Plan

Represent the exponent change as structured actions:

1. `inspect_repo`
   - confirm `calculator.py` exists
   - confirm existing generated calculator structure
2. `parse_existing_calculator`
   - find operation alias table or dispatch branches
3. `add_operator_aliases`
   - feature: `power`
   - aliases: `power`, `pow`, `^`, `**`
4. `add_operator_dispatch`
   - expression: `left ** right`
5. `add_cli_behavior_tests`
   - `2 ^ 3` -> `8`
   - `2 power 3` -> `8`
   - `2 ** 3` -> `8`
6. `run_validation`
   - generated calculator pytest command
7. `record_outcome`
   - prompt/spec/actions/files/validation/pass-fail

Do not hand-write arbitrary patches from a prompt. The edit should be derived
from the structured action record.

## Learned Prompt Understanding Plan

Use `../prompts/coding_agent_prompts_seed.jsonl` as the primary path, not as a
side quest after deterministic parsing.

Step one is data profiling and representation design:

- parse the JSONL
- summarize rows by `repo_mode`, `task_type`, `domain`, split, and tags
- identify rows involving GUI, graphics, unsupported scope, clarification, and
  existing-repo changes
- define the narrow prediction targets needed now, such as `repo_mode`,
  `expected_action`, `domain`, requested interface, unsupported requirement, and
  feature intent
- expose those rows through a dataset loader that a future JEPA-style prompt
  encoder can consume
- add a held-out evaluation harness before improving model behavior

Deterministic rules may remain as a baseline or regression oracle, but they are
not the main deliverable. Do not grow a broad keyword classifier except where a
small fallback is needed to keep user-facing behavior honest.

Training is preferred once the dataset/eval target is concrete. Only train from
`../prompts` if:

- the labels are consistent enough for a narrow classifier
- there is a focused target such as `repo_mode` or `clarification_needed`
- there is a held-out validation split
- the trained artifact beats or complements deterministic rules in a testable
  way

If the corpus is not ready for training, record exactly what is missing and
produce the dataset/evaluation code anyway.

## Step-By-Step Work Plan

### Step 1: Profile Prompt Corpus And Labels

Deliverable:

- load `../prompts/coding_agent_prompts_seed.jsonl`
- summarize available labels and splits
- identify supported CLI, unsupported graphical/complex, and existing-repo
  change rows
- record label gaps or inconsistencies that block training

Verification:

- JSONL parser validates all seed rows
- focused test asserts expected minimum coverage for the active GreenShot-7
  intent targets

### Step 2: Define Prompt Encoder Targets And Eval Harness

Deliverable:

- define a compact target schema for prompt understanding:
  `repo_mode`, `expected_action`, `domain`, `requested_interfaces`,
  `unsupported_requirements`, and `features`
- add a dataset/eval module that can score predicted targets against labels
- include a deterministic baseline only as a lower-bound comparator

Verification:

- focused dataset/eval tests pass
- baseline metrics are printed or asserted for the active label subset

### Step 3: Connect Learned/Evaluable Intent To Request Spec

Deliverable:

- request-spec construction consumes an intent prediction object rather than
  scattering English checks through spec helpers
- unsupported graphical/complex calculator requests can be blocked through that
  prediction path
- supported CLI calculator generation still works

Verification:

- `pytest tests/test_request_spec.py -q`
- direct unsupported CLI check exits non-zero and writes no calculator files
- direct supported CLI calculator smoke still passes

### Step 4: Improve Blocked Outcome Recording

Deliverable:

- records distinguish unsupported interface from generic ambiguity
- rows include requested interfaces, unsupported requirements, and
  clarification status

Verification:

- `--record` on graphical prompt writes one blocked JSONL row
- row has `passed: false` and a useful failure observation

### Step 5: Train Or Defer With Evidence

Deliverable:

- train the smallest useful prompt-intent model if the profile supports it, or
  record why training would be misleading today
- if training proceeds, keep the artifact local and evaluate on a held-out split

Verification:

- training decision is recorded in `plans/today.progress.md`
- model metrics or deferral reason are reproducible from a command/test

### Step 6: Define Existing-Repo Change Spec

Deliverable:

- `existing-repo-change-spec-v1` documentation or docstring
- parser for narrow calculator existing-repo change prompts
- fixture coverage for exponent/power support

Verification:

- tests assert repo mode, target files, feature to add, aliases, and validation

### Step 7: Inspect Existing Calculator Repo

Deliverable:

- function that confirms a repo contains the generated calculator shape
- rejects unrelated repos with a clear blocked result

Verification:

- generated sample repo is accepted
- empty/unrelated repo is blocked

### Step 8: Plan Existing-Repo Patch Actions

Deliverable:

- structured action plan for adding `power`
- no file writes yet

Verification:

- tests assert action sequence and payloads

### Step 9: Materialize Existing-Repo Change

Deliverable:

- apply structured `power` action to `calculator.py`
- update generated tests
- do not overwrite unrelated user changes

Verification:

- temp generated repo gets power support
- existing add/subtract/multiply/divide behavior still passes
- `2 ^ 3`, `2 power 3`, and `2 ** 3` pass

### Step 10: Add Existing-Repo CLI Command

Deliverable:

- CLI entry point such as:

```bash
python cli.py change \
  --repo /tmp/j3-cli-calc \
  --prompt "add exponent support"
```

Minimum behavior:

- parse prompt
- inspect repo
- plan structured actions
- apply patch
- run validation unless `--no-validate`
- print concise summary
- write outcome row with `--record`

Verification:

- direct smoke on a generated repo
- blocked smoke on an unrelated repo

### Step 11: Add End-To-End Regression For The Bad Prompt

Deliverable:

- focused test or CLI smoke proving:

```bash
python cli.py implement \
  --prompt "make me a complex graphic calc app" \
  --out /tmp/j3-graphic-calc
```

does not create the simple CLI calculator.

Verification:

- exit code non-zero
- no `calculator.py`
- clear clarification text
- blocked record when `--record` is supplied

### Step 12: Decide Whether To Train

Deliverable:

- short note in progress file based on the `../prompts` profile
- either:
  - defer training with a concrete data/label blocker, or
  - train a narrow classifier with a documented target and validation result

Verification:

- if training is deferred, reason is recorded
- if training runs, artifact path and held-out metrics are recorded

## Testing Plan

Run focused checks first:

```bash
python -m json.tool examples/greenshot_7/tasks.json >/dev/null
pytest tests/test_request_spec.py -q
pytest tests/test_greenfield_calculator.py -q
pytest tests/test_cli.py -q
pytest tests/test_greenshot_7.py -q
git diff --check
```

New tests expected during this slice:

```bash
pytest tests/test_prompt_corpus.py -q
pytest tests/test_prompt_intent_eval.py -q
pytest tests/test_existing_repo_change.py -q
```

Manual smoke for the unsupported prompt:

```bash
tmp=$(mktemp -d /tmp/j3-graphic-XXXXXX)
python cli.py implement \
  --prompt "make me a complex graphic calc app" \
  --out "$tmp"
test ! -e "$tmp/calculator.py"
```

Manual smoke for existing-repo change:

```bash
python cli.py implement \
  --prompt "make me a simple cli calc" \
  --out /tmp/j3-change-demo

python cli.py change \
  --repo /tmp/j3-change-demo \
  --prompt "add exponent support"

python /tmp/j3-change-demo/calculator.py 2 ^ 3
python -m pytest /tmp/j3-change-demo/tests -q
```

Run full `pytest -q` only after broad shared changes or before a final
integration gate.

## Acceptance Criteria For Today

Minimum success:

- `../prompts` is profiled into a reproducible prompt-intent dataset summary.
- A prompt-intent evaluation harness exists with explicit targets and a
  deterministic lower-bound baseline.
- The plan records whether a tiny learned model can be trained now, with
  evidence.
- `make me a complex graphic calc app` asks clarification and writes no simple
  CLI calculator.
- Existing simple CLI calculator generation still works.
- Unsupported interface decisions are represented in fixtures and records.

Strong success:

- A first tiny learned prompt-intent model is trained and evaluated on a
  held-out split, even if it covers only one narrow target.
- `j3 change --repo ... --prompt "add exponent support"` works on a generated
  calculator repo.
- The exponent change is planned as structured actions and then materialized.
- Generated and modified calculator tests pass.
- Existing-repo change attempts write prompt/spec/action/outcome JSONL rows.
- The plan has a clear evidence-based decision on whether training from
  `../prompts` is useful now or premature.

## Risks And Checks

Risk: j3 keeps over-infering from a domain word like `calculator`.

Check:

- predict requested interface and unsupported requirements before defaulting to
  a simple CLI calculator, and score that prediction against labeled rows.

Risk: the project spends another iteration proving obvious keyword matching.

Check:

- keep deterministic parsing as a lower-bound comparator only; prioritize
  dataset, encoder target, training decision, and held-out evaluation.

Risk: clarification becomes a generic escape hatch.

Check:

- clarification rows must name the unsupported field and give a concrete next
  choice.

Risk: existing-repo changes become free-form patching.

Check:

- support only the generated calculator shape and only the `power` feature
  until structured action tests pass.

Risk: training from `../prompts` wastes time or produces weak behavior.

Check:

- profile and evaluate first; train only a narrow classifier if labels and
  validation split justify it.

Risk: existing repo contains user edits.

Check:

- inspect current file content, avoid destructive rewrites, and patch only the
  known calculator dispatch/test regions.

## Open Decisions

1. CLI name for existing-repo prompt changes:
   - Proposed: `j3 change --repo PATH --prompt "..."`.

2. Unsupported graphical requests:
   - Proposed: block with clarification rather than generating a CLI fallback.

3. Existing-repo first feature:
   - Proposed: `power`/exponent support because it is small, testable, and
     naturally extends calculator dispatch.

4. Training from `../prompts`:
   - Proposed: profile and evaluate now; train the smallest useful narrow model
     if labels and a held-out split are ready, otherwise record the blocker.

## After Today

If this slice works, next tasks should be:

1. Add another existing-repo calculator change such as modulo or unary negate.
2. Add a tests-only prompt for an existing repo.
3. Add a non-calculator clarification task such as "make an app with auth".
4. Add a tiny non-calculator existing-repo feature with local style detection.
5. Replace the deterministic lower-bound baseline with the learned
   prompt-intent model for the narrow targets where held-out metrics justify it.
