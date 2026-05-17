# Today Plan: Calculator Request-to-Repo Slice

This is a 24-hour execution plan. It intentionally narrows the big `plan.md`
strategy to one practical proof: a user asks for a simple Python CLI calculator
in several natural phrasings, and j3 turns that request into a structured spec,
creates a working repo, validates behavior, and records data that can later feed
real prompt/JEPA training.

## Goal for the Next 24 Hours

Build the first walking version of GreenShot-7:

```text
natural-language prompt
  -> request-spec-v1
  -> structured greenfield plan
  -> generated Python CLI repo
  -> tests / hidden behavior checks pass
  -> prompt/spec/action/outcome record written
```

The initial domain is a basic calculator CLI. It should work for prompt variants
like:

- "make me a simple cli calc"
- "make cli app to add two numbers"
- "make cli takes as params two numbers and operator"
- "make me a simple cli python app that's a basic calculator, it should let the user add two numbers, subtract, etc."
- "build a command line calculator for add subtract multiply divide"
- "create a python script where I can run calc 2 + 3"
- "make a tiny calculator cli with plus minus times and divide"

The first version can use deterministic rules. The output data format must be
designed so those rules can be replaced by a learned prompt encoder later.

## Non-Goals for Today

- No neural prompt encoder yet.
- No JEPA model training yet.
- No broad natural-language coverage beyond calculator-style CLI requests.
- No general free-form source generation.
- No new dependency unless a standard-library approach is impractical.
- No claim of Codex-level behavior.

## Core Assumptions to Test

1. A small deterministic prompt parser can recognize calculator intent across
   common user phrasings.
2. Words like `calc`, `calculator`, `plus`, `minus`, `times`, `operator`, and
   `basic calculator` can map to a structured operation set.
3. `etc.` can be expanded only when paired with a high-confidence domain:
   `basic calculator` -> add, subtract, multiply, divide.
4. If the prompt only says "add two numbers", the minimal feature set can be
   just add unless the phrase also says calculator/basic/etc.
5. A structured greenfield action path can create a repo without asking an LLM
   to write source.
6. The generated code can be boring and constrained as long as it is correct,
   testable, and derived from structured actions.
7. The request/spec/action/outcome records can become future JEPA training rows.

## Expected User-Facing Behavior

For the first calculator CLI, support an argparse-style command:

```bash
python calculator.py 2 + 3
python calculator.py 2 add 3
python calculator.py 5 - 2
python calculator.py 4 multiply 3
python calculator.py 8 / 2
```

Expected output is a single number on stdout.

Baseline operation aliases:

- add: `add`, `plus`, `+`
- subtract: `subtract`, `sub`, `minus`, `-`
- multiply: `multiply`, `mul`, `times`, `x`, `*`
- divide: `divide`, `div`, `/`

Error behavior:

- Unknown operator exits non-zero with a clear message.
- Divide by zero exits non-zero with a clear message.
- Non-numeric input exits non-zero through argparse or validation.

## Prompt Variants for Day-One Coverage

Start with these as concrete request-spec fixtures:

```json
[
  {
    "name": "calculator_basic_etc",
    "prompt": "make me a simple cli python app that's a basic calculator, it should let the user add two numbers, subtract, etc.",
    "expected_features": ["add", "subtract", "multiply", "divide"]
  },
  {
    "name": "calculator_short_calc",
    "prompt": "make me a simple cli calc",
    "expected_features": ["add", "subtract", "multiply", "divide"]
  },
  {
    "name": "calculator_add_only",
    "prompt": "make cli app to add two numbers",
    "expected_features": ["add"]
  },
  {
    "name": "calculator_operator_params",
    "prompt": "make cli takes as params two numbers and operator",
    "expected_features": ["add", "subtract", "multiply", "divide"]
  },
  {
    "name": "calculator_named_ops",
    "prompt": "build a command line calculator for add subtract multiply divide",
    "expected_features": ["add", "subtract", "multiply", "divide"]
  },
  {
    "name": "calculator_symbol_example",
    "prompt": "create a python script where I can run calc 2 + 3",
    "expected_features": ["add"]
  },
  {
    "name": "calculator_aliases",
    "prompt": "make a tiny calculator cli with plus minus times and divide",
    "expected_features": ["add", "subtract", "multiply", "divide"]
  },
  {
    "name": "calculator_ambiguous",
    "prompt": "make a calculator",
    "expected_features": ["add", "subtract", "multiply", "divide"],
    "expected_inferred": true
  }
]
```

Potential negative/clarification fixtures:

```json
[
  {
    "name": "math_tool_unclear",
    "prompt": "make a math thing",
    "expected_action": "ask_clarification"
  },
  {
    "name": "calculator_scientific_unclear",
    "prompt": "make a scientific calculator",
    "expected_action": "ask_clarification"
  }
]
```

The second case is intentionally not day-one behavior unless we explicitly
choose a small scientific subset. It tests that j3 does not over-infer.

## Request Spec Shape

Use `request-spec-v1` records. Day-one fields:

```json
{
  "schema_version": "request-spec-v1",
  "task_name": "calculator_basic_etc",
  "task_type": "create_app",
  "language": "python",
  "repo_mode": "new_repo",
  "domain": "calculator",
  "prompt": "...",
  "artifacts": ["calculator.py", "tests/test_calculator_cli.py"],
  "interfaces": [{"kind": "cli", "style": "argparse"}],
  "features": ["add", "subtract", "multiply", "divide"],
  "operation_aliases": {
    "add": ["add", "plus", "+"],
    "subtract": ["subtract", "sub", "minus", "-"],
    "multiply": ["multiply", "mul", "times", "x", "*"],
    "divide": ["divide", "div", "/"]
  },
  "inferred_defaults": [
    {
      "field": "features",
      "value": ["multiply", "divide"],
      "reason": "basic_calculator_default_operations",
      "confidence": 0.86
    }
  ],
  "clarifications_needed": [],
  "validation": {
    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
    "hidden_cases": true
  }
}
```

## Greenfield Action Plan

Represent implementation as structured actions:

1. `create_file`
   - target: `calculator.py`
2. `add_import`
   - module: `argparse`
3. `add_function_def`
   - name: `calculate`
   - params: `left: float`, `operator: str`, `right: float`
4. `add_operator_dispatch`
   - operation set from request spec
   - aliases from request spec
5. `add_cli_entrypoint`
   - parse `left`, `operator`, `right`
   - print result
6. `create_test_file`
   - target: `tests/test_calculator_cli.py`
7. `add_cli_behavior_tests`
   - one passing case per inferred operation
   - unknown operator
   - divide by zero when divide is enabled

The first implementation may materialize these actions through templates, but
the action record should stay structured.

## Files to Add or Change

Likely files:

- `REQUEST_SPEC.md`
- `request_spec.py` or `repair/request_spec.py`
- `greenfield.py` or `repair/greenfield.py`
- `examples/greenshot_7/tasks.json`
- `examples/greenshot_7/calculator_prompts/*.json`
- `tests/test_request_spec.py`
- `tests/test_greenfield_calculator.py`
- `tests/test_greenshot_7.py`

CLI path options:

- Add `j3 implement --request PATH --out PATH`.
- Or add a lower-level command first: `j3 request-spec --prompt "..."`
- Or keep the first slice as library functions plus tests before adding CLI.

Preferred path for today:

1. Library functions first.
2. Then CLI command.
3. Then GreenShot-7 task runner.

## Step-by-Step Work Plan

### Step 1: Add Request Spec Documentation

Deliverable:

- `REQUEST_SPEC.md`

Contents:

- Purpose of `request-spec-v1`.
- Calculator examples.
- Ambiguity examples.
- Field definitions.
- Provenance and split fields.
- How records become future model training data.

Verification:

- Markdown exists and is linked from `plan.md` or `plans/today.md`.

### Step 2: Add Prompt Fixture Data

Deliverable:

- Calculator prompt fixture JSON or JSONL under `examples/greenshot_7/`.

Minimum rows:

- 8 positive calculator prompts.
- 2 clarification/negative prompts.

Verification:

- JSON parses.
- Stable task names.
- Expected feature sets match the table above.

### Step 3: Implement Deterministic Prompt-to-Spec Baseline

Deliverable:

- A small parser function like:

```python
parse_request_to_spec(prompt: str) -> RequestSpec
```

Rules:

- Detect Python CLI creation intent.
- Detect calculator domain from `calc`, `calculator`, arithmetic symbols, or
  operation words.
- Map explicit operation words and symbols to features.
- Expand `basic calculator`, `simple calc`, or generic `calculator` to the four
  basic operations.
- Expand `etc.` only when domain confidence is high.
- Ask clarification for vague math prompts without calculator or operations.

Verification:

- Unit tests for every prompt variant.
- Tests assert inferred defaults and clarification fields, not only features.

### Step 4: Implement Structured Calculator Repo Builder

Deliverable:

- Function like:

```python
build_calculator_repo(spec: RequestSpec, out_dir: Path) -> BuildResult
```

Behavior:

- Creates `calculator.py`.
- Creates `tests/test_calculator_cli.py`.
- Does not add dependencies.
- Writes deterministic, formatted Python.

Verification:

- Generated repo imports.
- Generated tests pass.
- File list is exactly expected unless explicitly configured.

### Step 5: Add Hidden Behavior Checks

Deliverable:

- Tests that run the generated CLI with subprocess.

Cases:

- `2 + 3` -> `5`
- `2 add 3` -> `5`
- `5 - 2` -> `3`
- `4 multiply 3` -> `12`
- `8 / 2` -> `4`
- divide by zero fails
- unknown operator fails

For add-only prompts:

- Addition passes.
- Non-requested operations should either be absent or excluded by spec, depending
  on the chosen policy. Decide this explicitly before coding.

Preferred policy:

- If prompt says only "add two numbers", generate only add.
- If prompt says calculator/calc/basic/etc/operator, generate four operations.

### Step 6: Add CLI Entry Point

Deliverable:

- `j3 implement --prompt "..." --out /tmp/some-repo`

Minimum behavior:

- Parses prompt.
- Writes request spec artifact into output repo, for traceability.
- Builds calculator repo.
- Runs validation unless `--no-validate`.
- Prints concise summary:
  - task type
  - inferred features
  - files written
  - validation result

Fallback if CLI wiring takes too long:

- Keep library-level function and tests finished today.
- Add CLI command tomorrow.

### Step 7: Record Training Rows

Deliverable:

- JSONL row per prompt attempt, probably under `runs/request-to-repo/`.

Fields:

- raw prompt
- normalized spec
- inferred defaults
- clarification decision
- action sequence
- files written
- validation command
- pass/fail
- failure observation if any
- repo output path or hash

Why this matters:

- This is the bridge to real JEPA. The future model needs prompt/spec/repo/action
  transition records, not just source diffs.

### Step 8: Add GreenShot-7 Smoke Task

Deliverable:

- `examples/greenshot_7/` with calculator task manifest.

Minimum task:

- `calculator_basic_etc`

Good if time:

- Add all 8 positive calculator prompts.
- Add 1 clarification task.

Verification:

- Focused test loads GreenShot-7 tasks.
- Focused test runs generated repo validation.

## Testing Plan

Run in this order:

```bash
python -m json.tool examples/greenshot_7/tasks.json >/dev/null
pytest tests/test_request_spec.py -q
pytest tests/test_greenfield_calculator.py -q
pytest tests/test_greenshot_7.py -q
git diff --check
```

If CLI command is added:

```bash
python cli.py implement \
  --prompt "make me a simple cli calc" \
  --out /tmp/j3-calc-demo

python /tmp/j3-calc-demo/calculator.py 2 + 3
python -m pytest /tmp/j3-calc-demo/tests -q
```

Do not run full `pytest` unless shared code changes make focused coverage
insufficient.

## Acceptance Criteria for Today

Minimum success:

- A prompt parser maps at least 6 calculator prompt variants to correct
  request specs.
- At least one generated calculator repo passes its tests.
- Prompt/spec/action/outcome rows are written or the schema for them is tested.
- Ambiguous prompt handling is represented in tests, even if not wired to a user
  CLI yet.

Strong success:

- `j3 implement --prompt ... --out ...` works.
- 8 positive calculator prompt variants generate working repos.
- 2 negative prompts return clarification specs.
- Generated tests include hidden-like subprocess behavior checks.
- Output records are ready to become prompt-to-repo training data.

## Risks and Checks

Risk: The deterministic parser becomes a bag of brittle rules.

Check:

- Keep rules small and emit structured evidence.
- Store all prompt/spec pairs so a learned encoder can replace the rules.

Risk: Greenfield builder turns into free-form source generation.

Check:

- Keep generated files derived from structured actions and stable templates.
- Record action sequence before materialization.

Risk: Calculator is too easy and misleading.

Check:

- Treat it as plumbing proof only.
- Follow immediately with tests-only, existing-repo feature, and clarification
  GreenShot-7 tasks.

Risk: `etc.` expansion overreaches.

Check:

- Expand only with high-confidence domains.
- Add negative examples where vague prompts ask clarification.

Risk: Data records are unusable for JEPA later.

Check:

- Record prompt, spec, repo-before, actions, repo-after/files, validation, and
  pass/fail now.

## Open Decisions

1. Should add-only prompts generate only add, or the full calculator?
   - Proposed: only add unless `calculator`, `calc`, `basic`, `etc.`, or
     `operator` implies a broader calculator.

2. Should the first CLI be argparse positional args or interactive prompt?
   - Proposed: argparse positional args because it is easier to validate and
     still matches "takes as params two numbers and operator".

3. Should generated repo include `pyproject.toml`?
   - Proposed: no for first slice. Keep files minimal.

4. Should prompt data live in `../prompts` or `data/prompts`?
   - Proposed: keep raw seed corpus in `../prompts`; copy stable normalized
     request-spec fixtures into `examples/greenshot_7/`.

5. Should the first builder use templates?
   - Proposed: yes, but templates must be parameterized by structured actions
     and produce recorded action rows.

## After Today

If calculator works, next GreenShot-7 tasks should be:

1. Tests-only request for an existing calculator module.
2. Existing tiny CLI repo: add `--verbose` following local style.
3. Existing library repo: add quoted values to a parser.
4. Clarification task: "make an app with auth".
5. Refactor task: split one script into a package without behavior changes.

The goal is to prove the same pipeline works beyond calculator while still
keeping each step small enough to diagnose.
