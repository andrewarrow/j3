# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plans/strategy.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: Prompt+Repo JEPA transition V0
- Completed iterations: 5 for this reset; Prompt-JEPA developer demo reset
  completed 5 iterations; previous Prompt-JEPA index reset completed 8
  iterations
- Passing focused tests: `pytest tests/test_prompt_intents.py -q`;
  `pytest tests/test_cli.py -q`;
  `pytest tests/test_prompt_jepa.py -q`;
  `python -m py_compile j3/prompt_jepa_demo.py j3/features.py j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`;
  `python cli.py demo-prompt-jepa --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl --out /tmp/j3-prompt-jepa-demo --top-k 5`;
  `python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null`;
  `python -m py_compile cli.py $(rg --files -g '*.py')`;
  `pytest -q`;
  `pytest tests/test_repo_state.py -q`;
  `python -m py_compile j3/repo_state.py`;
  `python cli.py --help`;
  `pytest tests/test_prompt_repo_transitions.py -q`;
  `pytest tests/test_cli.py -q`;
  `python -m py_compile j3/prompt_repo_transitions.py`;
  `python -m py_compile j3/prompt_repo_transitions.py cli/handlers.py cli/parser.py cli/__init__.py`;
  `python cli.py eval-prompt-repo-transitions --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl --top-k 3 --json`;
  `git diff --check`
- Latest implementation/demo commit: demo transition artifact wiring pending
- Current blocker: none
- Next task: update developer docs with the state/action/target transition story.

## Active Task Queue

- [x] Add reusable repo-state encoder artifact over Python source files.
- [x] Build `prompt-repo-transition-v1` rows from demo outcomes.
- [x] Add a tiny evaluation-only transition predictor V0.
- [x] Add consequence-prediction metrics and residuals.
- [x] Wire transition rows/model/eval into `demo-prompt-jepa` report artifacts.
- [ ] Update developer docs with the state/action/target transition story.

## Worker Iteration Template

Use this shape for each worker handoff:

```md
### Iteration N: <task>

- Worker:
- Goal:
- Files changed:
- Tests run:
- Result:
- Commit:
- Push:
- Next:
- Blockers:
```

## 2026-05-17

- Reset `plans/today.md` away from unsupported-intent fixture refinement and
  toward a concrete Prompt-JEPA encoder/index slice.
- Stopped the in-flight label-expansion worker before it committed or pushed.
  It reported a clean worktree and no partial changes.
- Previous loop outcomes retained in git history:
  - prompt-intent JSONL loading and profiling
  - token/bigram/char-ngram learned baseline
  - `j3 train-prompt-intents`
  - fixture-backed request-spec blocking for unsupported calculator prompts
  - `j3 change --repo ... --prompt "add exponent support"`
- Active decision:
  - stop expanding local labels as the main work
  - build a persisted JEPA-shaped index with separate context and target
    embeddings
  - keep production routing fixture-backed until retrieval/index metrics exist
- Iteration 1 assigned next step: implement `j3/prompt_jepa.py` or equivalent with:
  - index metadata and row dataclasses
  - deterministic context encoder
  - deterministic target encoder
  - save/load JSON format validation
  - nearest-neighbor query
  - focused tests

### Iteration 1: Prompt-JEPA index module

- Worker: Codex worker iteration 1
- Goal: add the Prompt-JEPA index module with separate context and target
  encoders, JSON save/load validation, nearest-neighbor query, and focused
  tests.
- Files changed: `j3/prompt_jepa.py`, `tests/test_prompt_jepa.py`,
  `pyproject.toml`, `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 6 tests;
  `python -m py_compile j3/prompt_jepa.py` passed; `git diff --check` passed.
- Result: implemented persisted `j3.prompt-jepa-index.v1` artifact support,
  deterministic feature-hashing context and target encoders, fixture index
  building, stable JSON save/load validation, nearest-neighbor query results,
  and structured target encoding for request/change spec records.
- Commit: `a62376d`
- Push: succeeded to `main`
- Next: add CLI build/query commands for persisted Prompt-JEPA indexes.
- Blockers: none.

### Iteration 2: Prompt-JEPA CLI build/query commands

- Worker: Codex worker iteration 2
- Goal: add CLI build/query commands for the persisted Prompt-JEPA index and
  focused CLI tests without changing production request-spec/change-spec
  routing.
- Files changed: `cli/parser.py`, `cli/handlers.py`, `cli/__init__.py`,
  `tests/test_cli.py`, `plans/today.progress.md`
- Tests run: `pytest tests/test_cli.py -q` passed with 29 tests;
  `pytest tests/test_prompt_jepa.py -q` passed with 6 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed; manual smoke build/query with
  `examples/prompt_intents/greenshot_7_intents.jsonl` passed.
- Result: implemented `build-prompt-jepa-index` and
  `query-prompt-jepa-index`, persisted local prompt-intent labels to
  `j3.prompt-jepa-index.v1`, printed stable human-readable build/query
  summaries, and added CLI coverage for both commands.
- Commit: `8fff432`
- Push: succeeded to `main`
- Next: add Prompt-JEPA retrieval evaluation metrics over held-out splits.
- Blockers: none.

### Iteration 3: Prompt-JEPA retrieval eval metrics

- Worker: Codex worker iteration 3
- Goal: add Prompt-JEPA retrieval evaluation metrics over held-out
  validation/test splits using a train-only index, plus focused tests and a CLI
  command.
- Files changed: `j3/prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 7 tests;
  `pytest tests/test_cli.py -q` passed with 31 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed.
- Metrics: local fixture
  `examples/prompt_intents/greenshot_7_intents.jsonl` with top-k 3 and 256
  dimensions used 53 train rows. Validation: expected_action 16/16 top1 and
  top3, repo_mode 16/16 top1 and top3, domain 16/16 top1 and top3,
  unsupported_requirement_family 15/16 top1 and 16/16 top3. Test:
  expected_action 18/18 top1 and top3, repo_mode 18/18 top1 and top3, domain
  18/18 top1 and top3, unsupported_requirement_family 16/18 top1 and 18/18
  top3.
- Metrics: `../prompts/coding_agent_prompts_seed.jsonl` was available and ran
  with top-k 3 and 256 dimensions using 53 train rows. Validation:
  expected_action 8/15 top1 and 12/15 top3, repo_mode 10/15 top1 and 15/15
  top3, domain 0/15 top1 and 1/15 top3,
  unsupported_requirement_family 15/15 top1 and top3. Test: expected_action
  9/12 top1 and 11/12 top3, repo_mode 10/12 top1 and 12/12 top3, domain 0/12
  top1 and 1/12 top3, unsupported_requirement_family 12/12 top1 and top3.
- Result: implemented evaluation-only retrieval metrics with top-1/top-k exact
  matches for scalar target fields, bounded representative misses with query
  ids, expected labels, nearest neighbor ids/scores/targets, and a new
  `eval-prompt-jepa-index` CLI command. Production routing remains unchanged.
- Commit: `8c26fe8`
- Push: succeeded to `main`
- Next: add the first JEPA-style context-to-target embedding predictor, train
  it on train rows, and evaluate target-space retrieval on held-out rows.
- Blockers: none.

### Iteration 4: Prompt-JEPA context-to-target predictor

- Worker: Codex worker iteration 4
- Goal: add the first JEPA-style context-to-target embedding predictor, train
  it on train rows, and evaluate target-space retrieval on held-out rows.
- Files changed: `j3/prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 9 tests;
  `pytest tests/test_cli.py -q` passed with 32 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed.
- Metrics: predicted-target mode on local fixture
  `examples/prompt_intents/greenshot_7_intents.jsonl` with top-k 3 and 256
  dimensions used 53 train rows. Validation: expected_action 16/16 top1 and
  top3, repo_mode 16/16 top1 and top3, domain 16/16 top1 and top3,
  unsupported_requirement_family 16/16 top1 and top3. Test: expected_action
  18/18 top1 and top3, repo_mode 18/18 top1 and top3, domain 18/18 top1 and
  top3, unsupported_requirement_family 17/18 top1 and top3.
- Metrics: predicted-target mode on `../prompts/coding_agent_prompts_seed.jsonl`
  was available and ran with top-k 3 and 256 dimensions using 53 train rows.
  Validation: expected_action 8/15 top1 and 9/15 top3, repo_mode 10/15 top1 and
  11/15 top3, domain 1/15 top1 and 2/15 top3,
  unsupported_requirement_family 15/15 top1 and top3. Test: expected_action
  9/12 top1 and top3, repo_mode 10/12 top1 and top3, domain 0/12 top1 and
  top3, unsupported_requirement_family 12/12 top1 and top3.
- Result: implemented explicit `j3.prompt-jepa-predictor.v0` artifacts using
  nearest-context delta prediction from context embeddings into target
  embeddings, save/load validation, target-space retrieval over train target
  embeddings, predicted-target evaluation metrics, and
  `eval-prompt-jepa-index --mode predicted-target`. Production `implement` and
  `change` behavior remains unchanged.
- Commit: `6c94881`
- Push: succeeded to `main`
- Next: compare context-neighbor and predicted-target residuals, then improve
  domain retrieval in target space without wiring retrieval into production.
- Blockers: none.

### Iteration 5: Prompt-JEPA residual comparison and target-domain retrieval

- Worker: Codex worker iteration 5
- Goal: compare context-neighbor and predicted-target residuals, inspect weak
  seed-domain retrieval, and improve target-space domain retrieval without
  changing production `implement` or `change` routing.
- Files changed: `j3/prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 11 tests;
  `pytest tests/test_cli.py -q` passed with 33 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed.
- Inspection: `../prompts/coding_agent_prompts_seed.jsonl` has sparse exact
  domain coverage in train. Only 3/15 validation rows and 2/12 test rows have
  domains seen in train, so exact domain retrieval has a low ceiling before
  adding more labels. The weak target-space domain misses were mostly action
  or task neighbors dominating sparse domain hints.
- Metrics: local fixture
  `examples/prompt_intents/greenshot_7_intents.jsonl` with top-k 3 and 256
  dimensions used 53 train rows. Context-neighbor validation: expected_action
  16/16 top1 and top3, repo_mode 16/16 top1 and top3, domain 16/16 top1 and
  top3, unsupported_requirement_family 16/16 top1 and top3. Context-neighbor
  test: expected_action 18/18 top1 and top3, repo_mode 18/18 top1 and top3,
  domain 18/18 top1 and top3, unsupported_requirement_family 16/18 top1 and
  18/18 top3. Predicted-target validation: all four fields 16/16 top1 and
  top3. Predicted-target test: all four fields 18/18 top1 and top3.
- Metrics: `../prompts/coding_agent_prompts_seed.jsonl` with top-k 3 and 256
  dimensions used 53 train rows. Context-neighbor validation: expected_action
  5/15 top1 and 13/15 top3, repo_mode 7/15 top1 and 14/15 top3, domain 0/15
  top1/top3, unsupported_requirement_family 15/15 top1 and top3.
  Context-neighbor test: expected_action 9/12 top1 and 11/12 top3, repo_mode
  9/12 top1 and 12/12 top3, domain 0/12 top1 and 1/12 top3,
  unsupported_requirement_family 12/12 top1 and top3. Predicted-target
  validation: expected_action 11/15 top1 and 13/15 top3, repo_mode 9/15 top1
  and 11/15 top3, domain 2/15 top1/top3,
  unsupported_requirement_family 15/15 top1 and top3. Predicted-target test:
  expected_action 11/12 top1/top3, repo_mode 9/12 top1 and 10/12 top3, domain
  1/12 top1/top3, unsupported_requirement_family 12/12 top1 and top3.
- Residual comparison: on seed domain top1, predicted-target fixed validation
  `seed-0015` and `seed-0059`, and test `seed-0051`, with no domain
  regressions. Expected-action top1 also improved from context-neighbor to
  predicted-target on seed validation 5/15 to 11/15 and test 9/12 to 11/12.
- Result: added `eval-prompt-jepa-index --mode compare` for residual movement
  reporting, bumped context/target encoder schemas to v2, added canonical
  target summary and shared lexical features, included row tags in target
  embeddings, and added an evaluation-only schema-aware domain hint for
  predicted-target target-space scoring. Production routing remains unchanged.
- Commit: `f11c9d2`
- Push: succeeded to `main`
- Next: add Prompt-JEPA indexing for real prompt/spec/action/outcome rows, not
  just labeled prompt-intent fixtures.
- Blockers: none.

### Iteration 6: Prompt-JEPA outcome row indexing

- Worker: Codex worker iteration 6
- Goal: add Prompt-JEPA indexing for real prompt/spec/action/outcome rows
  produced by `implement --record` and `change --record`, without wiring
  retrieval into production routing.
- Files changed: `j3/prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`, `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 12 tests;
  `pytest tests/test_cli.py -q` passed with 34 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed.
- Result: added normalization for supported real outcome JSONL rows
  (`greenshot_7_request_to_repo_attempt` and
  `greenshot_7_existing_repo_change_attempt`) into JEPA target records that
  preserve request/change specs, structured actions, validation status,
  pass/fail, files written/changed, and nested outcome details. Added
  `build-prompt-jepa-index --records` alongside `--labels`, including mixed
  source support, while leaving `implement` and `change` routing unchanged.
- Commit: `4df56c1`
- Push: succeeded to `main`
- Next: build an outcome index from accumulated real `--record` rows and
  inspect nearest-neighbor quality before considering any retrieval-assisted
  planner proposal path.
- Blockers: none.

### Iteration 7: Real outcome index quality smoke

- Worker: Codex worker iteration 7
- Goal: build an outcome index from accumulated real `--record` rows and
  inspect nearest-neighbor quality before considering any retrieval-assisted
  planner proposal path.
- Files changed: `tests/test_cli.py`, `plans/today.progress.md`
- Tests run: `pytest tests/test_cli.py::test_prompt_jepa_index_command_queries_real_recorded_outcomes -q`
  passed with 1 test; `pytest tests/test_cli.py -q` passed with 35 tests;
  `pytest tests/test_prompt_jepa.py -q` passed with 12 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed.
- Smoke commands: used a temporary `/tmp/j3-outcome-index-smoke.*` workspace,
  appended three real rows with `python cli.py implement --prompt "make me a
  simple cli calc" --out "$tmpdir/calc" --record "$records"` exit 0,
  `python cli.py implement --prompt "make me a complex graphic calc app" --out
  "$tmpdir/blocked-graphic" --record "$records"` expected exit 1, and
  `python cli.py change --repo "$tmpdir/calc" --prompt "add exponent support"
  --record "$records"` exit 0. Built the index with
  `python cli.py build-prompt-jepa-index --records "$records" --out "$index"
  --embedding-dim 128`; `python -m json.tool "$index" >/dev/null` passed.
- Query observations: `build a simple command line calculator` returned
  `request-repo-attempt-0001` first with score 0.275073; `add power operator to
  the calculator` returned `existing-repo-change-attempt-0003` first with score
  0.131788; `build a graphical calculator app` returned the blocked graphical
  `request-repo-attempt-0002` first with score 0.264297. The indexed rows
  preserved outcome status and pass/fail tags: built/passed for the simple
  calculator row, blocked/failed for the graphical row, and validated/passed
  for the exponent change row.
- Result: added a focused CLI integration test that creates real
  `implement/change --record` outcome rows in a temp directory, builds a
  Prompt-JEPA outcome index, and asserts nearest-neighbor quality for create,
  change, and blocked graphical prompts. No generated repos, temp paths, or
  index fixtures were committed. Production routing remains unchanged.
- Commit: `f5a8035`
- Push: succeeded to `main`
- Next: design an evaluation-only retrieval-assisted planner proposal dry run
  from real outcome-index neighbors, without changing production `implement` or
  `change` routing.
- Blockers: none.

### Iteration 8: Retrieval-assisted planner proposal dry run

- Worker: Codex worker iteration 8
- Goal: design and implement an evaluation-only retrieval-assisted planner
  proposal dry run from real outcome-index neighbors, without changing
  production `implement` or `change` routing.
- Files changed: `j3/prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 13 tests;
  `pytest tests/test_cli.py -q` passed with 35 tests;
  `python -m py_compile j3/prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `git diff --check` passed.
- Result: added `propose_from_prompt_jepa`, an evaluation-only
  `prompt-jepa-planner-proposal-v1` record with `mode: dry_run`,
  `applies_changes: false`, top-neighbor evidence, suggested outcome
  kind/status, target summary, and confidence fields. Added
  `propose-from-prompt-jepa --index ... --prompt ... --top-k ...` with
  human-readable and JSON output. Focused tests cover create/success,
  existing-repo power change, and blocked graphical evidence from real
  outcome-index neighbors. Production `implement` and `change` routing remains
  unchanged.
- Commit: `d8bfd1b`
- Push: succeeded to `main`
- Next: review proposal dry-run output against additional real outcome rows and
  decide whether a future planner should consume proposals directly or through
  a separate planner-evidence adapter.
- Blockers: none.

### Documentation: README Prompt-JEPA progress

- Goal: update `README.md` to reflect GreenShot-7 Prompt-JEPA progress and the
  actual small-example use of separate prompt context and target embeddings.
- Files changed: `README.md`, `plans/today.progress.md`
- Tests run: `python cli.py build-prompt-jepa-index --labels
  examples/prompt_intents/greenshot_7_intents.jsonl --out
  /tmp/j3-prompt-jepa-index.json` passed; `python cli.py query-prompt-jepa-index
  --index /tmp/j3-prompt-jepa-index.json --prompt "make me a simple cli calc"
  --top-k 5` passed and returned `gs7-intent-0001` first with score `0.928041`;
  `python cli.py query-prompt-jepa-index --index /tmp/j3-prompt-jepa-index.json
  --prompt "make me a complex calc for spaceships" --top-k 5` passed and
  returned `gs7-intent-0004` first with expected action `ask_clarification`;
  `python cli.py eval-prompt-jepa-index --labels
  examples/prompt_intents/greenshot_7_intents.jsonl --mode compare` passed;
  `python cli.py propose-from-prompt-jepa --index
  /tmp/j3-prompt-jepa-index.json --prompt "make me a complex calc for
  spaceships" --top-k 5` passed and emitted a dry-run proposal with
  `gs7-intent-0004` as nearest evidence;
  temp `python cli.py implement --prompt "make me a simple cli calc" --out
  "$tmpdir"` passed with generated repo validation; `git diff --check` passed.
- Result: README now documents the GreenShot-7 prompt-to-repo path, the
  persisted `j3.prompt-jepa-index.v1` artifact, context-vs-target embedding
  separation, calculator index build/query/eval commands, dry-run planner
  proposal behavior, and the current production-routing boundary.
- Next: keep README concise; move deeper Prompt-JEPA metrics or design notes to
  focused docs if they grow beyond the small current-progress summary.
- Blockers: none.

### Reset: Prompt-JEPA developer demo and corpus scale-up

- Goal: reread `plans/strategy.md`, `plans/today.md`, `plans/today.progress.md`,
  `docs/TRAINING.md`, and `../prompts` context, then reset the active 24-hour plan
  to the next work most likely to make the repo compelling to outside
  developers.
- Files changed: `plans/today.md`, `plans/today.progress.md`
- Decision: prioritize a fast local Prompt-JEPA demo and expanded prompt corpus
  before a deeper Apache-source JEPA training run. The source-training path is
  important, but the repo first needs a runnable prompt-to-repo/index/proposal
  demo showing local execution, inspectable structured records, timings,
  validation, and zero hosted LLM token use.
- Current facts: `../prompts/coding_agent_prompts_seed.jsonl` has 80 rows;
  the Prompt-JEPA index/proposal path exists; GreenShot-7 can already produce
  real calculator request/change outcome rows; `j3/features.py` already provides a
  deterministic Python source encoder that can be added as a demo sidecar.
- Result: `plans/today.md` now targets an expanded 300-350 row prompt corpus,
  prompt corpus quality gate, one-command demo/report, mixed labels+records
  index, thin source-embedding bridge, and developer-facing docs.
- Tests run: `git diff --check` passed.
- Next: implement the first unchecked task: add the reproducible expanded
  prompt corpus under `../prompts` with clear provenance and stable splits.
- Blockers: none.

### Iteration 1: Expanded prompt corpus generation

- Worker: Codex local iteration
- Goal: generate a larger prompt corpus in `../prompts` and keep enough notes
  for another developer to reproduce the artifact.
- Files changed: `tools/prompts/generate_expanded_prompt_corpus.py`,
  `tools/prompts/README.md`,
  `../prompts/coding_agent_prompts_expanded_v0.jsonl`,
  `../prompts/GENERATION.md`, `../prompts/README.md`,
  `plans/today.md`, `plans/today.progress.md`
- Plan update: raised the target corpus size from roughly 250-300 rows to
  roughly 300-350 rows because the deterministic template pass produced 320
  useful rows while still staying small enough for fast local demo use.
- Tests run: `python tools/prompts/generate_expanded_prompt_corpus.py` passed and
  produced 320 rows; `python -m py_compile
  tools/prompts/generate_expanded_prompt_corpus.py` passed; `python cli.py
  train-prompt-intents --labels
  ../prompts/coding_agent_prompts_expanded_v0.jsonl --target expected_action
  repo_mode task_type domain requires_clarification` passed; `python cli.py
  build-prompt-jepa-index --labels
  ../prompts/coding_agent_prompts_expanded_v0.jsonl --out
  /tmp/j3-expanded-prompt-jepa-index.json` passed; `python cli.py
  eval-prompt-jepa-index --labels
  ../prompts/coding_agent_prompts_expanded_v0.jsonl --mode compare` passed;
  representative `query-prompt-jepa-index` and `propose-from-prompt-jepa`
  commands passed; `git diff --check` passed.
- Corpus result: 320 total rows: 80 `human_seed`, 240
  `synthetic_template_v0`; splits are train 206, validation 42, test 72.
  Expected action counts are `emit_existing_repo_change_spec` 164,
  `emit_request_spec` 122, and `ask_clarification` 34.
- Baseline result: token baseline on held-out splits reached validation/test
  `expected_action` 36/42 and 64/72, `repo_mode` 36/42 and 68/72,
  `task_type` 29/42 and 53/72, `domain` 15/42 and 17/72, and
  `requires_clarification` 40/42 and 68/72. Domain remains intentionally hard
  because the expanded corpus has many sparse domains.
- Prompt-JEPA smoke: expanded index built with 320 rows. Querying `make me a
  simple cli calc` returned `synth-0001` first with score `0.849906` and
  `emit_request_spec`; querying `make me a complex calc for spaceships`
  returned `synth-0228` first with score `0.880979` and
  `ask_clarification`; querying `add auth` returned the auth clarification seed
  first.
- Result: `tools/prompts/generate_expanded_prompt_corpus.py` is the checked-in
  source of truth for generating the expanded corpus, and `../prompts` now has
  generation notes plus a 320-row demo corpus with explicit synthetic
  provenance. The generator skips duplicate prompts from the human seed rather
  than weakening duplicate validation.
- Next: add the prompt corpus quality/profile command or equivalent tested
  path.
- Blockers: none.

### Plan adjustment: stop expanding before measurement

- Decision: do not keep adding prompt rows in Step 1 right now. The 320-row
  corpus is enough for the next demo slice; the next leverage point is Step 2,
  a prompt corpus quality/profile gate, followed by the one-command demo report.
- Reason: more synthetic prompts without duplicate checks, family leakage
  checks, and representative demo metrics would make the corpus larger but not
  more convincing to outside developers.
- Files changed: `tools/prompts/generate_expanded_prompt_corpus.py`,
  `tools/prompts/README.md`, `../prompts/GENERATION.md`,
  `../prompts/README.md`, `plans/today.md`, `plans/today.progress.md`
- Tests run: `python tools/prompts/generate_expanded_prompt_corpus.py` passed
  and reproduced the 320-row corpus.
- Next: implement the prompt corpus quality/profile command.
- Blockers: none.

### Iteration 2: Prompt corpus quality/profile command

- Worker: Codex local iteration
- Goal: add a tested `inspect-prompt-corpus` path for the expanded prompt
  corpus.
- Files changed: `j3/prompt_intents.py`, `cli/parser.py`, `cli/handlers.py`,
  `cli/__init__.py`, `tests/test_prompt_intents.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_intents.py -q` passed with 12 tests;
  `pytest tests/test_cli.py -q` passed with 36 tests; `python -m py_compile
  j3/prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py` passed;
  `python cli.py inspect-prompt-corpus --labels
  ../prompts/coding_agent_prompts_expanded_v0.jsonl --json` passed; `git diff
  --check` passed.
- Result: implemented JSON and human-readable corpus profiling for total rows,
  split counts, task type, repo mode, domain, expected action, clarification
  counts, duplicate normalized prompts, prompt-family split leakage, missing
  required fields, and unsupported scalar labels. The expanded 320-row corpus
  currently reports no duplicate normalized prompts, no prompt-family leakage,
  no missing required fields, and no unsupported scalar labels.
- Commit: `0c5c51f`
- Push: succeeded to `main`
- Next: add a one-command Prompt-JEPA demo/report path with timings, artifact
  sizes, representative queries, dry-run proposals, and hosted API tokens `0`.
- Blockers: none.

### Iteration 3: Prompt-JEPA one-command demo/report

- Worker: Codex local iteration
- Goal: add a one-command `demo-prompt-jepa` path with timings, artifact sizes,
  representative queries, dry-run proposals, generated calculator validation,
  blocked evidence, and hosted API tokens/context bytes `0`.
- Files changed: `j3/prompt_jepa_demo.py`, `cli/parser.py`, `cli/handlers.py`,
  `cli/__init__.py`, `tests/test_cli.py`, `plans/today.progress.md`
- Tests run: `pytest tests/test_cli.py::test_demo_prompt_jepa_command_writes_local_report -q`
  passed; `pytest tests/test_prompt_jepa.py -q` passed with 13 tests;
  `pytest tests/test_cli.py -q` passed with 37 tests; `python -m py_compile
  j3/prompt_jepa_demo.py j3/prompt_jepa.py cli/handlers.py cli/parser.py
  cli/__init__.py` passed; `python cli.py demo-prompt-jepa --labels
  ../prompts/coding_agent_prompts_expanded_v0.jsonl --out
  /tmp/j3-prompt-jepa-demo --top-k 5` passed; `python -m json.tool
  /tmp/j3-prompt-jepa-demo/report.json >/dev/null` passed; `git diff --check`
  passed.
- Demo result: the expanded 320-row corpus produced a 320-row labels index and
  a 323-row mixed labels+records index. The demo generated and validated a
  simple calculator repo, applied and validated exponent support, recorded a
  blocked `add auth` outcome, wrote `labels-index.json`, `index.json`,
  `outcomes.jsonl`, and `report.json`, and printed
  `hosted_llm_api_tokens: 0` plus `hosted_repo_context_bytes: 0`.
- Representative behavior: `make me a simple cli calc` and
  `add exponent support` are supported/validated calculator paths;
  `make me a complex calc for spaceships` and the todo CLI prompt are reported
  as retrieval-only; `add auth` is reported as blocked. Dry-run proposals remain
  `applies_changes: false` and production routing is unchanged.
- Commit: `74aa004`
- Push: succeeded to `main`
- Next: add a thin Python source-embedding sidecar for generated demo repos
  using `features.embed_python_source`.
- Blockers: none.

### Iteration 4: Prompt-JEPA demo source-embedding sidecar

- Worker: Codex local iteration
- Goal: add a thin Python source-embedding sidecar for generated demo repos
  using `features.embed_python_source`, without changing production routing.
- Files changed: `j3/prompt_jepa_demo.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_cli.py::test_demo_prompt_jepa_command_writes_local_report -q`
  passed; `pytest tests/test_cli.py -q` passed with 37 tests;
  `python -m py_compile j3/prompt_jepa_demo.py j3/features.py cli/handlers.py
  cli/parser.py cli/__init__.py` passed; `python cli.py demo-prompt-jepa
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl --out
  /tmp/j3-prompt-jepa-demo --top-k 5` passed; `python -m json.tool
  /tmp/j3-prompt-jepa-demo/report.json >/dev/null` passed; `git diff --check`
  passed.
- Result: the demo now scans the supported generated calculator repo for Python
  files after exponent support is applied, embeds each file with the existing
  deterministic AST hash source encoder, writes `source-embeddings.json`, and
  adds concise source-embedding metadata to `report.json`. The sidecar records
  `calculator.py` and `tests/test_calculator_cli.py` with source byte counts,
  SHA-256 hashes, embedding lengths, and vectors. Production `implement`,
  `change`, and Prompt-JEPA routing remain unchanged.
- Commit: `1347a11`
- Push: succeeded to `main`
- Next: document the demo in README or a focused demo doc with exact commands
  and honest supported/retrieval-only boundaries.
- Blockers: none.

### Iteration 5: Prompt-JEPA developer demo docs

- Worker: Codex worker iteration 5
- Goal: document the Prompt-JEPA developer demo with exact commands and honest
  supported/retrieval-only boundaries.
- Files changed: `docs/PROMPT_JEPA_DEMO.md`, `README.md`,
  `plans/today.progress.md`
- Tests/checks run: `python cli.py demo-prompt-jepa --labels
  ../prompts/coding_agent_prompts_expanded_v0.jsonl --out
  /tmp/j3-prompt-jepa-demo --top-k 5` passed; `python -m json.tool
  /tmp/j3-prompt-jepa-demo/report.json >/dev/null` passed;
  `python -m json.tool /tmp/j3-prompt-jepa-demo/source-embeddings.json
  >/dev/null` passed; `python /tmp/j3-prompt-jepa-demo/repos/simple-calc/calculator.py
  2 + 3` returned `5`; `python /tmp/j3-prompt-jepa-demo/repos/simple-calc/calculator.py
  2 '**' 3` returned `8`; `python -m pytest
  /tmp/j3-prompt-jepa-demo/repos/simple-calc/tests -q` passed with 2 tests;
  `git diff --check` passed.
- Result: added a focused demo doc with commands for corpus generation,
  corpus inspection, `demo-prompt-jepa`, report validation, index/proposal
  inspection, outcome-row inspection, generated calculator repo smoke checks,
  and `source-embeddings.json` inspection. README now points to the focused
  doc. The doc states supported calculator create/change paths,
  retrieval/proposal-only non-calculator behavior, blocked clarification
  examples, zero hosted LLM/API and hosted repo-context usage, no production
  routing switch, and deterministic `features.embed_python_source` sidecar
  boundaries.
- Commit: current documentation commit; final hash reported by worker.
- Push: pending until commit is created.
- Next: active queue complete; watcher should choose the next plan slice or
  close this demo/documentation pass.
- Blockers: none.

### Root layout cleanup: move implementation and long-form docs

- Worker: Codex local cleanup
- Goal: reduce root clutter while keeping `cli.py`, `README.md`, and
  `AGENTS.md` discoverable at the repository root.
- Files changed: moved root implementation modules into `j3/`; moved long-form
  markdown docs into `docs/`; moved broad strategy to `plans/strategy.md`;
  updated imports, packaging metadata, README layout, agent handoff references,
  plan/doc references, and tests.
- Tests/checks run: `python -m py_compile cli.py $(rg --files -g '*.py')`
  passed; `pytest -q` passed with 243 tests; `python cli.py --help` passed;
  `git diff --check` passed.
- Result: root `.py`/`.md` files are now limited to `cli.py`, `README.md`, and
  `AGENTS.md`; generated root `__pycache__` artifacts were removed after
  checks.
- Commit: pending.
- Push: pending.
- Next: commit this layout cleanup if requested.
- Blockers: none.

### Reset: Prompt+Repo JEPA transition V0

- Goal: review the completed Prompt-JEPA demo work and reset `plans/today.md`
  to the next slice that will make the repo more compelling to JEPA developers.
- Files changed: `plans/today.md`, `plans/today.progress.md`
- Decision: stop expanding prompts for now. The 320-row corpus, inspector,
  demo report, mixed outcome index, and source-embedding sidecar are enough
  evidence for the local/no-token story. The next higher-value work is an
  explicit transition artifact:
  `prompt + repo_before + structured_action -> predicted repo_after /
  validation utility`.
- Current facts: `demo-prompt-jepa` already writes a local report, real
  calculator outcome rows, mixed indexes, and source embeddings. It does not
  yet produce transition rows, train/evaluate a transition predictor, or compare
  prompt-only retrieval against prompt+repo+action consequence prediction.
- Result: `plans/today.md` now targets a Prompt+Repo JEPA Transition V0 slice:
  reusable repo-state encoder, `prompt-repo-transition-v1` JSONL rows, tiny
  evaluation-only transition predictor, consequence-prediction metrics,
  demo-report integration, and docs.
- Tests run: `git diff --check` passed.
- Next: implement Step 1, the reusable repo-state encoder artifact.
- Blockers: none.

### Iteration 1: Repo-state encoder artifact

- Worker: Codex worker iteration 1
- Goal: add a reusable repo-state encoder artifact over Python source files.
- Files changed: `j3/repo_state.py`, `tests/test_repo_state.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_repo_state.py -q` passed with 6 tests;
  `python -m py_compile j3/repo_state.py` passed; `git diff --check` passed.
- Result: implemented `repo-state-v1` records with deterministic relative
  Python file paths, per-file SHA-256 hashes and byte counts, source feature
  version metadata, embedding dimension metadata, mean aggregate repo
  embeddings, count/byte aggregate metadata, empty-repo zero embeddings, and
  JSON-serializable output helpers.
- Commit: repo-state encoder worker commit; final hash reported by worker.
- Push: succeeded to `main`.
- Next: build `prompt-repo-transition-v1` rows from demo outcomes.
- Blockers: none.

### Iteration 2: Prompt-repo transition rows

- Worker: Codex worker iteration 2
- Goal: build `prompt-repo-transition-v1` rows from demo outcomes.
- Files changed: `j3/prompt_repo_transitions.py`, `j3/prompt_jepa_demo.py`,
  `tests/test_prompt_repo_transitions.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_repo_transitions.py -q` passed with 4
  tests; `pytest tests/test_cli.py::test_demo_prompt_jepa_command_writes_local_report -q`
  passed; `pytest tests/test_cli.py -q` passed with 37 tests;
  `python -m py_compile j3/prompt_repo_transitions.py j3/prompt_jepa_demo.py
  cli/handlers.py cli/parser.py cli/__init__.py` passed; `python cli.py
  demo-prompt-jepa --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl
  --out /tmp/j3-prompt-jepa-demo --top-k 5` passed; `python -m json.tool
  /tmp/j3-prompt-jepa-demo/report.json >/dev/null` passed; transition JSONL
  assertion passed with 3 rows and `prompt-repo-transition-v1`; `git diff
  --check` passed.
- Result: added deterministic transition rows with prompt context embeddings,
  Prompt-JEPA target summaries/checksums, repo-before and repo-after
  `repo-state-v1` records, blocked no-change state handling, validation
  summaries, and zero hosted token/context cost fields. `demo-prompt-jepa` now
  writes `/tmp/j3-prompt-jepa-demo/transitions.jsonl` for its create,
  blocked-clarification, and exponent-change outcomes.
- Commit: `8a5b58e`
- Push: succeeded to `main`.
- Next: add a tiny evaluation-only transition predictor V0.
- Blockers: none.

### Iteration 3: Transition predictor V0

- Worker: Codex Worker Iteration 3
- Goal: add a tiny deterministic evaluation-only predictor over
  `prompt-repo-transition-v1` rows.
- Files changed: `j3/prompt_repo_transitions.py`,
  `tests/test_prompt_repo_transitions.py`, `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_repo_transitions.py -q` passed with 7
  tests; `python -m py_compile j3/prompt_repo_transitions.py` passed;
  `git diff --check` passed.
- Result: implemented `prompt-repo-transition-predictor-v0` with prompt
  context, repo-before, structured action, outcome, and validation/status
  features; source/no-change repo-after embedding targets; blocked
  clarification targets; deterministic nearest-context/action-delta
  predictions; JSON-serializable model metadata; and predictor JSON
  save/load helpers. The predictor is explicitly evaluation-only and not wired
  into production routing.
- Commit: `ca3065d`
- Push: succeeded to `main`.
- Next: add consequence-prediction metrics and residuals.
- Blockers: none.

### Iteration 4: Consequence-prediction metrics and residuals

- Worker: Codex worker iteration 4 for the Prompt+Repo transition V0 reset
- Goal: add inspectable consequence-prediction metrics and residual examples
  for `prompt-repo-transition-v1` rows and the V0 transition predictor.
- Files changed: `j3/prompt_repo_transitions.py`, `cli/parser.py`,
  `cli/handlers.py`, `tests/test_prompt_repo_transitions.py`,
  `tests/test_cli.py`, `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_repo_transitions.py -q` passed with 8
  tests; `pytest tests/test_cli.py -q` passed with 39 tests;
  `python -m py_compile j3/prompt_repo_transitions.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `python cli.py demo-prompt-jepa --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl --out /tmp/j3-prompt-jepa-demo --top-k 5`
  passed; `python cli.py eval-prompt-repo-transitions --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl --top-k 3 --json`
  passed; `git diff --check` passed.
- Result: added leave-one-out transition evaluation with top-1/top-k outcome
  kind and validation-status metrics, repo-after embedding distance metrics for
  source-changing/no-change rows, source-change vs blocked split counts,
  prompt-only nearest-neighbor baseline metrics, and bounded residual examples
  containing prompt, action, expected, predicted, prompt-only, and distance
  fields. Added the evaluation-only `eval-prompt-repo-transitions` CLI command.
- Commit: `5f9fcb9`
- Push: succeeded to `main`.
- Next: wire transition rows/model/eval into `demo-prompt-jepa` report
  artifacts.
- Blockers: none.

### Iteration 5: Demo transition artifact wiring

- Worker: Codex worker iteration 5 for the Prompt+Repo transition V0 reset
- Goal: wire transition rows/model/eval into `demo-prompt-jepa` report
  artifacts while keeping production routing and hosted usage unchanged.
- Files changed: `j3/prompt_jepa_demo.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_cli.py::test_demo_prompt_jepa_command_writes_local_report -q`
  passed; `pytest tests/test_cli.py -q` passed with 39 tests;
  `python -m py_compile j3/prompt_jepa_demo.py j3/prompt_repo_transitions.py cli/handlers.py cli/parser.py cli/__init__.py`
  passed; `python cli.py demo-prompt-jepa --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl --out /tmp/j3-prompt-jepa-demo --top-k 5`
  passed; `python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null`
  passed; `python -m json.tool /tmp/j3-prompt-jepa-demo/transition-model.json >/dev/null`
  passed; `python -m json.tool /tmp/j3-prompt-jepa-demo/transition-eval.json >/dev/null`
  passed; transition JSONL assertion passed with 3 rows and
  `prompt-repo-transition-v1`; `python cli.py eval-prompt-repo-transitions --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl --top-k 3 --json`
  passed with JSON validation; `git diff --check` passed.
- Result: `demo-prompt-jepa` now fits the evaluation-only V0 transition
  predictor over its demo transition rows, writes `transition-model.json`,
  evaluates consequence prediction into `transition-eval.json`, and adds
  transition artifact paths, predictor metadata, source-state feature version,
  concise V0/prompt-only metrics, residual examples, and
  `evaluation_only_not_wired_to_production: true` to `report.json`. Hosted
  LLM token and hosted repo-context usage remain zero.
- Commit: pending until commit is created; final hash reported by worker.
- Push: pending until commit is created.
- Next: update developer docs with the state/action/target transition story.
- Blockers: none.
