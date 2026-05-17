# request-spec-v1

`request-spec-v1` is the first structured request format for GreenShot-7. It
turns a narrow coding-agent prompt into a small, explicit contract that later
steps can plan from without asking a language model to generate source code.

Day one is intentionally limited to Python CLI calculator requests. The format
must be predictable enough for deterministic rules now and stable enough that a
learned prompt encoder can emit the same records later.

## Purpose

The spec captures:

- what the user asked for
- which app domain was recognized
- which implementation artifacts should exist
- which user-facing interface should be generated
- which calculator operations are required or inferred
- which defaults were inferred and why
- which clarification questions block implementation
- which validations prove the generated repo works

A worker should only move from request parsing to repo creation when
`clarifications_needed` is empty.

## Day-One Schema

The day-one record is JSON-compatible and uses this shape:

```json
{
  "schema_version": "request-spec-v1",
  "task_name": "calculator_basic_etc",
  "task_type": "create_app",
  "language": "python",
  "repo_mode": "new_repo",
  "domain": "calculator",
  "prompt": "make me a simple cli calc",
  "artifacts": ["calculator.py", "tests/test_calculator_cli.py"],
  "interfaces": [
    {
      "kind": "cli",
      "style": "argparse"
    }
  ],
  "features": ["add", "subtract", "multiply", "divide"],
  "operation_aliases": {
    "add": ["add", "plus", "+"],
    "subtract": ["subtract", "sub", "minus", "-"],
    "multiply": ["multiply", "mul", "times", "x", "*"],
    "divide": ["divide", "div", "/"]
  },
  "inferred_defaults": [],
  "clarifications_needed": [],
  "validation": {
    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
    "hidden_cases": true
  }
}
```

Field meanings:

- `schema_version`: literal `request-spec-v1`.
- `task_name`: stable fixture or generated identifier for the request.
- `task_type`: day-one value is `create_app`.
- `language`: day-one value is `python`.
- `repo_mode`: day-one value is `new_repo`.
- `domain`: day-one recognized domain. The supported value is `calculator`.
- `prompt`: original user prompt, preserved for training records.
- `artifacts`: files the greenfield action path is expected to create.
- `interfaces`: user-facing entry points. Day one supports an argparse CLI.
- `features`: normalized calculator operations to implement.
- `operation_aliases`: accepted spellings or symbols for each operation.
- `inferred_defaults`: defaults added by parser rules with reason and
  confidence.
- `clarifications_needed`: blocking questions when intent is too broad or
  ambiguous.
- `validation`: commands and hidden-like behavior checks expected after
  generation.

## Calculator Prompt Examples

These prompts should produce non-blocking calculator specs:

```json
[
  {
    "prompt": "make me a simple cli calc",
    "features": ["add", "subtract", "multiply", "divide"],
    "inference": "basic calculator defaults"
  },
  {
    "prompt": "make cli app to add two numbers",
    "features": ["add"],
    "inference": "explicit add-only request"
  },
  {
    "prompt": "make cli takes as params two numbers and operator",
    "features": ["add", "subtract", "multiply", "divide"],
    "inference": "operator implies basic calculator operation set"
  },
  {
    "prompt": "make me a simple cli python app that's a basic calculator, it should let the user add two numbers, subtract, etc.",
    "features": ["add", "subtract", "multiply", "divide"],
    "inference": "etc. expanded inside high-confidence basic calculator context"
  },
  {
    "prompt": "create a python script where I can run calc 2 + 3",
    "features": ["add"],
    "inference": "symbol example requires addition"
  }
]
```

## `etc.` Inference

`etc.` is only expandable when the surrounding prompt already establishes a
high-confidence basic calculator domain. The parser may infer the four standard
operations when the prompt contains strong calculator terms such as
`calculator`, `calc`, or `basic calculator`, and at least one of these is true:

- the prompt names multiple calculator operations and then says `etc.`
- the prompt asks for a basic/simple calculator
- the prompt asks for two numbers plus an operator

For this slice, the inferred operation set is:

```json
["add", "subtract", "multiply", "divide"]
```

Every inferred operation must be recorded in `inferred_defaults`. Example:

```json
{
  "field": "features",
  "value": ["multiply", "divide"],
  "reason": "basic_calculator_etc_default_operations",
  "confidence": 0.86
}
```

Prompts that only say `etc.` without a clear calculator domain should not be
expanded. They should produce a clarification instead.

## Operation Aliases

Generated CLIs should accept these operation aliases:

```json
{
  "add": ["add", "plus", "+"],
  "subtract": ["subtract", "sub", "minus", "-"],
  "multiply": ["multiply", "mul", "times", "x", "*"],
  "divide": ["divide", "div", "/"]
}
```

The canonical operation names in `features` are the object keys above. Aliases
are interface behavior, not extra features.

## Validation Expectations

A generated calculator repo should include focused pytest coverage and be
usable through a subprocess-style CLI. For a full four-operation calculator,
validation should cover:

- `python calculator.py 2 + 3` prints `5`
- `python calculator.py 2 add 3` prints `5`
- `python calculator.py 5 - 2` prints `3`
- `python calculator.py 4 multiply 3` prints `12`
- `python calculator.py 8 / 2` prints `4`
- unknown operators exit non-zero with a clear message
- divide by zero exits non-zero with a clear message when divide is enabled
- non-numeric input exits non-zero through argparse or validation

Specs should set `validation.hidden_cases` to `true` when the generated repo is
expected to pass additional equivalent alias and error checks.

## Clarification And Ambiguity

When the parser cannot safely map the prompt to the day-one calculator domain or
operation set, it should emit a blocking clarification instead of guessing.

Example:

```json
{
  "schema_version": "request-spec-v1",
  "task_name": "math_tool_unclear",
  "task_type": "create_app",
  "language": "python",
  "repo_mode": "new_repo",
  "domain": "unknown",
  "prompt": "make a math thing",
  "artifacts": [],
  "interfaces": [],
  "features": [],
  "operation_aliases": {},
  "inferred_defaults": [],
  "clarifications_needed": [
    {
      "field": "domain",
      "question": "Should this be a basic CLI calculator, and which operations should it support?"
    }
  ],
  "validation": {
    "commands": [],
    "hidden_cases": false
  }
}
```

`make a scientific calculator` is also ambiguous for day one. It names a
calculator, but it implies functions beyond add, subtract, multiply, and divide.
Until a scientific subset is explicitly defined, the parser should ask which
operations are required.
