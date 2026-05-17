# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: reset to Prompt-JEPA encoder and index implementation
- Completed iterations: 4 for this reset
- Passing focused tests: `pytest tests/test_cli.py -q`;
  `pytest tests/test_prompt_jepa.py -q`;
  `python -m py_compile prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`;
  `git diff --check`
- Latest implementation commit: `6c94881`
- Current blocker: none
- Next task: compare context-neighbor and predicted-target residuals, then
  improve target-space domain retrieval without changing production routing.

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
- Iteration 1 assigned next step: implement `prompt_jepa.py` or equivalent with:
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
- Files changed: `prompt_jepa.py`, `tests/test_prompt_jepa.py`,
  `pyproject.toml`, `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 6 tests;
  `python -m py_compile prompt_jepa.py` passed; `git diff --check` passed.
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
  `python -m py_compile prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
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
- Files changed: `prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 7 tests;
  `pytest tests/test_cli.py -q` passed with 31 tests;
  `python -m py_compile prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
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
- Files changed: `prompt_jepa.py`, `cli/parser.py`, `cli/handlers.py`,
  `tests/test_prompt_jepa.py`, `tests/test_cli.py`,
  `plans/today.progress.md`
- Tests run: `pytest tests/test_prompt_jepa.py -q` passed with 9 tests;
  `pytest tests/test_cli.py -q` passed with 32 tests;
  `python -m py_compile prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py`
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
