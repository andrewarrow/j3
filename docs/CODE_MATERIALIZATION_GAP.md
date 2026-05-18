# Code Materialization Gap Audit

Task: `MAT-001`

Date: 2026-05-18

## Question

Can the current structured-action thesis scale from predicted repo-after intent
to actual source files?

Short answer: it is not broken, but it is already cracking at the materializer.
The current action set is good for narrow local repair and a few deterministic
greenfield shapes. In 25 merged Python PRs, only 4 primary edits fit current
structured actions directly. Most real accepted changes need either typed
source builders, repo-convention-aware test/config builders, or a constrained
local generator for small source regions.

## Current Materialization Surface

Current source materialization is split across two narrow paths:

- Repair candidates under `repair/patching/generators/` emit one-file
  `CandidatePatch` objects from typed `PatchAction` records such as
  `change_literal`, `change_operator`, `change_subscript_key`,
  `change_dict_key`, `change_dict_value`, `add_dict_key`, `add_keyword_arg`,
  `add_import`, `change_attribute`, `wrap_try_except`, `rename_symbol`,
  `modify_condition`, and `propagate_signature`.
- Greenfield builders in `j3/greenfield.py` render deterministic calculators,
  slugify libraries, and key/value parsers from action lists such as
  `create_file`, `add_function_def`, `add_cli_entrypoint`, and bounded test
  builders.

What is missing is the middle: materializers that can create or edit source
regions that are too structured for free-form patching but too varied for the
current hard-coded builders.

## Classification Rules

I sampled merged PRs from `pallets/click`, `pallets/flask`, `psf/requests`, and
`pytest-dev/pytest`. Each PR has at least one Python source, test, fixture, or
Python-adjacent tooling file. The label is the weakest mechanism that could
produce a reviewable, behaviorally equivalent code-bearing diff. I did not
require exact changelog prose, but I did count tests, fixtures, config, and
lockfile changes when they carried the accepted change.

Labels:

- `current_structured_action`: current repair or greenfield actions can
  express the main source edit if the target is known.
- `general_typed_builder`: needs a reusable AST/config/test builder not
  present today, but no repo-specific convention inference or local synthesis.
- `repo_convention_builder`: needs to inspect local test, fixture, import,
  package, or config conventions before materializing the edit.
- `constrained_local_generator`: needs synthesized source inside a bounded
  existing region, followed by AST parsing, diff limits, validation, and
  rollback.
- `not_currently_expressible`: too broad for the above without multi-step
  planning, migration tooling, or architectural design.

## Counts

| Label | Count |
| --- | ---: |
| `current_structured_action` | 4 |
| `general_typed_builder` | 7 |
| `repo_convention_builder` | 4 |
| `constrained_local_generator` | 8 |
| `not_currently_expressible` | 2 |

## PR Labels

| # | PR | Merged | Diff size | Label | Why |
| ---: | --- | --- | --- | --- | --- |
| 1 | [pallets/click#3434](https://github.com/pallets/click/pull/3434) | 2026-05-16 | +128/-0, 3 files | `constrained_local_generator` | Adds an early branch in `HelpFormatter.write_usage` plus a parameterized regression suite. The source region is small, but the right code depends on usage-line semantics and rendered output expectations. |
| 2 | [pallets/click#3430](https://github.com/pallets/click/pull/3430) | 2026-05-16 | +30/-32, 2 files | `general_typed_builder` | Extracts helper functions for deprecated labels and rewrites duplicate call sites. This is a reusable helper-extraction/call-replacement transform, not covered by current actions. |
| 3 | [pallets/click#3423](https://github.com/pallets/click/pull/3423) | 2026-05-15 | +5/-1, 1 file | `current_structured_action` | Replaces one option-help expression to insert a separator. A targeted `replace_expr`-style action can express the source edit. |
| 4 | [pallets/click#3422](https://github.com/pallets/click/pull/3422) | 2026-05-16 | +15/-5, 1 file | `general_typed_builder` | Moves instance attribute annotations to class scope and adds `__init__` return annotations. This needs typed annotation builders. |
| 5 | [pallets/click#3420](https://github.com/pallets/click/pull/3420) | 2026-05-16 | +214/-2, 4 files | `constrained_local_generator` | Makes text wrapping ANSI-aware with new helper behavior and broad formatter tests. Existing actions cannot synthesize the new text-measurement logic. |
| 6 | [pallets/click#3405](https://github.com/pallets/click/pull/3405) | 2026-05-16 | +253/-13, 3 files | `repo_convention_builder` | Adds pager tests using local monkeypatch, skip, fixture, and stream conventions, plus a small capability helper. The dominant gap is convention-aware test materialization. |
| 7 | [pallets/click#3396](https://github.com/pallets/click/pull/3396) | 2026-05-04 | +17/-16, 3 files | `general_typed_builder` | Refines sentinel type aliases and parser annotations across files. This is a typed-signature and annotation update family. |
| 8 | [pallets/click#3364](https://github.com/pallets/click/pull/3364) | 2026-04-29 | +75/-0, 5 files | `constrained_local_generator` | Adds default-map string splitting behavior with docs and tests. The source edit is small, but choosing the exact branch and conversion call requires local semantic synthesis. |
| 9 | [pallets/flask#6013](https://github.com/pallets/flask/pull/6013) | 2026-05-02 | +6/-1, 2 files | `current_structured_action` | Wraps the filename expression with a lowercase normalization before suffix matching. A targeted expression replacement can express it. |
| 10 | [pallets/flask#5903](https://github.com/pallets/flask/pull/5903) | 2026-01-28 | +2/-8, 2 files | `general_typed_builder` | Replaces a try/except/pass idiom with `os.makedirs(..., exist_ok=True)` in tutorial code and docs. A generic idiom-rewrite builder would cover it. |
| 11 | [pallets/flask#5898](https://github.com/pallets/flask/pull/5898) | 2026-01-25 | +14/-3, 4 files | `current_structured_action` | Changes redirect default constants from 302 to 303 in two function signatures. Current literal-change actions cover the source edit. |
| 12 | [pallets/flask#5812](https://github.com/pallets/flask/pull/5812) | 2025-09-19 | +779/-1007, 36 files | `not_currently_expressible` | Merges app and request context behavior across core modules, docs, and tests. This is architectural multi-step planning, not materialization of one bounded state change. |
| 13 | [pallets/flask#5808](https://github.com/pallets/flask/pull/5808) | 2026-01-25 | +1/-1, 1 file | `general_typed_builder` | Changes a method annotation from `str` to `str | None`. This belongs to typed annotation editing rather than current literal repair. |
| 14 | [pallets/flask#5727](https://github.com/pallets/flask/pull/5727) | 2025-05-12 | +1876/-534, 24 files | `not_currently_expressible` | Migrates project tooling to `uv`, rewrites requirements, CI, config, and a lockfile. This needs a migration workflow and external tool knowledge. |
| 15 | [psf/requests#7441](https://github.com/psf/requests/pull/7441) | 2026-05-14 | +2/-3, 2 files | `general_typed_builder` | Changes request header types from `MutableMapping` to `Mapping` and removes an import. This is a typed import/annotation builder case. |
| 16 | [psf/requests#7437](https://github.com/psf/requests/pull/7437) | 2026-05-13 | +2/-2, 1 file | `general_typed_builder` | Narrows `Response.reason` typing while preserving runtime initialization with a type-ignore. This needs a type-aware assignment annotation builder. |
| 17 | [psf/requests#7433](https://github.com/psf/requests/pull/7433) | 2026-05-12 | +18/-3, 2 files | `constrained_local_generator` | Adds stream-wrapper detection using `hasattr(data, "__iter__")` and a redirect regression test. Existing actions do not synthesize that local data-flow predicate. |
| 18 | [psf/requests#7427](https://github.com/psf/requests/pull/7427) | 2026-05-11 | +27/-2, 2 files | `constrained_local_generator` | Ports a proxy domain-boundary fix with host normalization and extra branch checks. This is a bounded algorithmic rewrite inside one function. |
| 19 | [psf/requests#7423](https://github.com/psf/requests/pull/7423) | 2026-05-11 | +9/-0, 1 file | `repo_convention_builder` | Adds an autouse pytest fixture to clear proxy environment variables. The materializer must know local `conftest.py`, monkeypatch, and fixture conventions. |
| 20 | [psf/requests#7328](https://github.com/psf/requests/pull/7328) | 2026-04-05 | +9/-2, 2 files | `constrained_local_generator` | Reorders redirect history mutation to avoid self-reference and adds behavior tests. The edit depends on understanding list aliasing and request history semantics. |
| 21 | [psf/requests#7315](https://github.com/psf/requests/pull/7315) | 2026-05-10 | +2/-4, 2 files | `repo_convention_builder` | Removes a path-normalization guard and updates the adapter test expectation. The source deletion is generic, but the accepted proof is a local test-convention edit. |
| 22 | [pytest-dev/pytest#14475](https://github.com/pytest-dev/pytest/pull/14475) | 2026-05-13 | +17/-2, 3 files | `constrained_local_generator` | Fixes a scanner by searching within the current string token and adjusting the reported column. Existing single-expression edits are not enough to choose this coherent paired change and regression test. |
| 23 | [pytest-dev/pytest#14472](https://github.com/pytest-dev/pytest/pull/14472) | 2026-05-14 | +3/-1, 3 files | `current_structured_action` | Replaces a mistaken string-literal receiver with the `obj` variable. This is a direct expression replacement. |
| 24 | [pytest-dev/pytest#14466](https://github.com/pytest-dev/pytest/pull/14466) | 2026-05-12 | +126/-17, 2 files | `constrained_local_generator` | Extends timedelta approximation with relative tolerance validation, computed tolerances, and sequence/mapping tests. This is bounded but genuinely generative source-region work. |
| 25 | [pytest-dev/pytest#14429](https://github.com/pytest-dev/pytest/pull/14429) | 2026-05-07 | +27/-1, 3 files | `repo_convention_builder` | Adds a defensive `__repr__` guard and tests using pytest's parser fixtures. The source guard is simple; the accepted diff needs local test construction. |

## Representative Gaps

### Current Structured Actions Work For Tiny Local Fixes

`click#3423`, `flask#6013`, `flask#5898`, and `pytest#14472` are the sweet
spot. They change a literal, expression receiver, or simple default. If a
ranker selects the right target, the existing patch-action thesis can
materialize these edits.

This is real signal, but it is narrow. These PRs are closer to repair tasks
than to request-to-repo coding.

### Typed Builders Are A Missing General Layer

Seven PRs are not algorithmic, but also not current actions. Examples:

- `click#3422` moves attribute annotations from assignments to class scope.
- `requests#7441` changes imports and type aliases consistently.
- `flask#5903` rewrites a common try/except/pass filesystem idiom.

These do not need free-form generation. They need reusable builders over typed
AST and config operations: add or move annotations, update imports, rewrite a
recognized idiom, extract a helper, remove a guarded block, or update a
signature family.

### Repo-Conventions Matter Immediately

Four PRs need local convention awareness even when the source edit is small.
`requests#7423` is the cleanest example: the whole accepted change is an
autouse pytest fixture in `tests/conftest.py`. A model that predicts
"clear proxy environment variables before tests" still needs a materializer
that can inspect local fixture style, import policy, naming, and monkeypatch
usage.

This directly supports the near-term wedge: tests-only existing-repo support is
not optional. It is a required materialization layer.

### The Largest Gap Is Bounded Local Source Generation

Eight PRs need a constrained generator for a small existing source region:

- `requests#7427`: domain-boundary proxy matching inside one function.
- `pytest#14466`: relative tolerance semantics for timedeltas.
- `click#3434`: usage-line rendering branch plus regression tests.
- `requests#7328`: redirect history mutation order.

These are not giant architectural changes. They are exactly the kind of
everyday maintenance edits a local agent must eventually handle. The current
structured action set cannot cover them without either exploding into bespoke
actions or adding a constrained local generator.

### Some Accepted PRs Are Out Of Scope For Now

`flask#5812` and `flask#5727` should remain outside the six-month wedge.
They require multi-step architectural or tooling migration plans, broad test
selection, docs updates, lockfile/tool knowledge, and review judgment. Treating
these as near-term failures would create pressure to add unsafe free-form
patching.

## Failure Categories

1. Single-edit transaction limit: current repair candidates materialize one
   patch, but real PRs often need coherent source plus tests, or two related
   source edits.
2. No existing-repo test builder: many accepted diffs add pytest cases,
   fixtures, monkeypatches, parametrization, skip markers, or local helpers.
3. No typed annotation/config codemods: type-only and tooling edits are common
   and should be builder territory, not free-form generation.
4. No source-region synthesis: bounded algorithmic changes inside one function
   are the largest bucket.
5. No multi-step migration planner: broad architecture and tooling migrations
   need to stay out of guarded product scope until the lower layers work.

## Smallest Executable Probe

The highest-leverage next probe is a constrained local generator for one
function body plus a repo-convention test builder. Use `psf/requests#7427`
because it is small, local, public, and validates with focused tests.

Probe shape:

```text
repo: psf/requests
base: b684dcb9bbf3aa557d1238e72062c4a29737dd1c
reference PR: https://github.com/psf/requests/pull/7427
target file: src/requests/utils.py
target function: should_bypass_proxies
required behavior: no_proxy entries must respect domain boundaries and exact
  host:port matches
validation: python -m pytest tests/test_utils.py::test_should_bypass_proxies_no_proxy_domain_boundary -q
```

Materialization contract:

1. Inspect the target function and existing `tests/test_utils.py` style.
2. Produce a structured action record like:

   ```json
   {
     "kind": "replace_function_region",
     "target": {
       "file_path": "src/requests/utils.py",
       "symbol": "should_bypass_proxies",
       "region": "no_proxy_host_matching_loop"
     },
     "constraints": {
       "max_changed_source_lines": 12,
       "must_parse_ast": true,
       "must_preserve_signature": true,
       "allowed_import_changes": []
     }
   }
   ```

3. Materialize only that bounded region, not the whole file.
4. Add one pytest parameterization matching local style.
5. Run the focused test and record the candidate-after AST delta.

Passing this probe would prove progress on the largest observed bucket because
it is neither a one-line repair nor a full free-form patch. Failing it cleanly
would still be useful if the residual says whether the missing part was target
selection, source-region synthesis, test construction, or validation.

## Thesis Verdict

The structured-action thesis is scaling for tiny local repairs and narrow
greenfield scaffolds. It is cracking for normal accepted PRs because
"structured action" currently means either a very specific repair transform or
a hard-coded repo builder.

The right response is not to abandon structure. The right response is to add
two middle layers before any broad learned generator:

1. General typed builders for annotations, imports, signatures, helper
   extraction, block deletion, config, and simple pytest tests.
2. Constrained local generators for bounded source regions, wrapped in typed
   action records with AST parsing, diff budgets, validation, rollback, and
   candidate-after observations.

If those layers are not added, the project will overfit GreenShot and repair
fixtures while being unable to materialize the repo-after states that real PRs
actually contain.
