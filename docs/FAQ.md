# FAQ

## Will j3 eventually have a Codex-like terminal UI?

That is a good target, but `j3` should not pretend to be a chat model. The
terminal UI should make the code-world planner easy to use:

```text
j3> fix failing tests
j3 found 3 failing tests.

Candidate patch:
  action: replace_expr
  file: pricing.py
  tests: pass

Apply? [y/n/show diff]
```

The useful product is a local coding engine that can inspect a repo, plan
structured edits, test those edits in temporary copies, and ask the human before
changing files.

## If there is no LLM, how can a human say "change this program to do x"?

In no-LLM mode, `j3` needs an executable or structured target. Examples:

```bash
j3 patch --repo . --test "python -m pytest tests/test_pricing.py"
j3 fix --repo . --failing-tests
j3 patch --repo . --goal discount_final_price --test "python -m pytest tests/test_pricing.py"
```

The key point is that the test, type error, lint error, benchmark failure, or
named structured goal tells `j3` what "better" means. The model can then search
for edits that move the repo toward that target state.

## How would no-LLM mode parse "make discounts return final price"?

It would not understand that sentence the way a language model does. A no-LLM
parser would be deliberately limited and transparent. It could use:

- keyword matching: `discount`, `final price`, `return`
- repo symbols: functions like `apply_discount`, files like `pricing.py`
- test names: `test_discount_returns_remaining_price`
- error output: assertion values such as `50.0 == 150`
- a small goal registry: `discount_final_price -> prefer final-price formulas`

For example, the phrase:

```text
make discounts return final price
```

could be converted into a structured hint:

```json
{
  "goal": "discount_final_price",
  "symbols": ["discount", "price"],
  "preferred_actions": ["replace_expr"],
  "requires_test": true
}
```

That hint can help rank candidates, but it is not enough by itself. In no-LLM
mode, `j3` should still require a test or another executable signal before it
applies a patch. Otherwise it is guessing from English, which is exactly the
behavior this project is trying to avoid.

## Should j3 use an LLM at all?

For open-ended human requests, yes, optionally. The clean architecture is:

```text
human request
  -> intent adapter
  -> j3 planner
  -> structured patch candidates
  -> tests/typechecks/runtime validation
  -> patch or human review
```

The intent adapter can be an LLM, a rule-based parser, or a future local
language model. Its job is to translate messy human language into structured
objectives, test ideas, file hints, and constraints.

`j3` remains the patch planner and verifier. The LLM does not need to generate
the final patch.

## What does the LLM-assisted version look like?

A human might type:

```text
add CSV export to reports and reject empty filenames
```

An intent adapter could turn that into:

```json
{
  "files_hint": ["reports.py", "export.py"],
  "tests_to_add": [
    "CSV export writes a header row",
    "empty filename raises ValueError"
  ],
  "constraints": [
    "preserve existing JSON export",
    "do not change the public API unless required"
  ]
}
```

Then `j3` can work against those executable targets. The important distinction
is that the LLM handles language and task decomposition; `j3` handles repo-state
prediction, structured edit ranking, and validation.

## What is the honest long-term claim?

`j3` should be able to repair code against executable signals without any LLM.
For natural human language, an LLM is useful as an optional intent adapter.

The project claim should stay precise:

> LLMs are optional for language. They are not the patch engine.
