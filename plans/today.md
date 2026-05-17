# Today Plan: Intent Fidelity And Existing-Repo Change Slice

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

Build a more honest GreenShot request pipeline:

```text
natural-language prompt
  -> intent/scope classification
  -> clarification when requested interface or scope is unsupported
  -> request-spec-v1 only when the request matches supported capability
  -> existing-repo change spec for narrow calculator edits
  -> structured patch actions
  -> validation
  -> prompt/spec/action/outcome row
```

Success means j3 can say "I cannot safely do that yet" for unsupported UI or
complexity requests, and can make at least one small requested change to an
existing calculator repo through structured code edits.

## Non-Goals For Today

- No full GUI, web, desktop, TUI, or graphical calculator generation.
- No broad existing-repo natural-language editing beyond calculator.py.
- No neural prompt encoder unless the data profile shows an extremely small,
  useful classifier can be trained and tested inside the day.
- No new dependency unless the standard library is clearly insufficient.
- No general free-form source generation.
- No changes to `plan.md` unless the strategic roadmap truly changes.

## Core Problems To Fix

1. The parser treats any calculator-ish prompt as the simple CLI calculator.
2. Interface words like `graphic`, `graphical`, `gui`, `desktop`, `web`, and
   `complex` are not represented as capability constraints.
3. `request-spec-v1` has no clear field for rejected or unsupported interface
   requests beyond generic clarification.
4. `j3 implement` currently creates new repos only.
5. Existing-repo changes are possible only through failing tests, not direct
   user prompts.
6. The prompt seed corpus in `../prompts` has labels that may help define a
   better intent classifier, but it has not been evaluated against current
   parser behavior.

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

## Prompt Corpus Plan

Use `../prompts/coding_agent_prompts_seed.jsonl` before training anything.

Step one is profiling and evaluation:

- parse the JSONL
- summarize rows by `repo_mode`, `task_type`, `domain`, split, and tags
- identify rows involving GUI, graphics, unsupported scope, clarification, and
  existing-repo changes
- compare current deterministic parser decisions against the labeled expected
  fields where labels are usable
- write a small report or test fixture from the mismatch cases

Training is optional for this slice. Only train from `../prompts` if:

- the labels are consistent enough for a narrow classifier
- there is a focused target such as `repo_mode` or `clarification_needed`
- there is a held-out validation split
- the trained artifact beats or complements deterministic rules in a testable
  way

The default path is still deterministic rules plus fixtures. The corpus should
drive eval coverage first, not become a premature model.

## Step-By-Step Work Plan

### Step 1: Reset Active Fixtures For Intent Fidelity

Deliverable:

- add unsupported graphical/complex calculator prompts
- add existing-repo calculator change prompts
- keep existing successful CLI calculator prompts

Verification:

- fixture JSON parses
- stable task names
- each row has expected action and repo mode

### Step 2: Add Parser Guard For Unsupported Interfaces

Deliverable:

- parser detects graphical/UI/web/desktop/complex interface words
- parser emits blocked clarification instead of a simple CLI spec
- `make me a complex graphic calc app` is covered by a test

Verification:

- `pytest tests/test_request_spec.py -q`
- direct CLI check exits non-zero and writes no calculator files

### Step 3: Preserve Supported CLI Behavior

Deliverable:

- existing successful CLI prompts still parse and build
- add-only policy still holds
- `j3 implement --prompt "make me a simple cli calc"` still works

Verification:

- existing GreenShot-7 tests remain green
- direct `j3 implement` smoke passes

### Step 4: Improve Blocked Outcome Recording

Deliverable:

- records distinguish unsupported interface from generic ambiguity
- rows include requested interfaces, unsupported requirements, and
  clarification status

Verification:

- `--record` on graphical prompt writes one blocked JSONL row
- row has `passed: false` and a useful failure observation

### Step 5: Profile `../prompts`

Deliverable:

- script or test helper that reads `../prompts/coding_agent_prompts_seed.jsonl`
- summary counts by label
- extracted mismatch/clarification examples that should become fixtures

Verification:

- JSONL parser validates all seed rows
- test asserts expected split counts or minimum coverage

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
  - defer training and add more deterministic fixtures, or
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

- `make me a complex graphic calc app` asks clarification and writes no simple
  CLI calculator.
- Existing simple CLI calculator generation still works.
- Unsupported interface decisions are represented in fixtures and records.
- `../prompts` is profiled and at least one finding is converted into a test or
  fixture.

Strong success:

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

- classify requested interface and unsupported requirements before defaulting to
  a simple CLI calculator.

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
   - Proposed: profile and evaluate now; defer model training unless a narrow
     label target is clearly ready.

## After Today

If this slice works, next tasks should be:

1. Add another existing-repo calculator change such as modulo or unary negate.
2. Add a tests-only prompt for an existing repo.
3. Add a non-calculator clarification task such as "make an app with auth".
4. Add a tiny non-calculator existing-repo feature with local style detection.
5. Use the prompt corpus profile to grow fixtures before training a prompt
   classifier.
