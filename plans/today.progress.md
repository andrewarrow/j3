# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: learned prompt-intent baseline evaluated
- Completed iterations: 4
- Passing focused tests:
  - `pytest tests/test_prompt_intents.py -q`
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py -q`
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_cli.py -q`
  - `pytest tests/test_existing_repo_change.py -q`
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
  - `git diff --check`
  - `python -m py_compile prompt_intents.py request_spec.py cli/handlers.py`
  - `python -m py_compile existing_repo_change.py cli/handlers.py cli/parser.py cli/__init__.py`
- `python cli.py train-prompt-intents --labels ../prompts/coding_agent_prompts_seed.jsonl --target expected_action repo_mode`
- `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
- Latest implementation commit: `fc9dc87a9b734234e9ebdcbd883147f9dea3d7f7`
- Current blocker: none
- Next task: decide the next learned prompt-understanding target after reviewing
  the token-perceptron residuals; do not replace fixture-backed production
  intent prediction yet

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

- Reset `plans/today.md` from the completed GreenShot-7 calculator
  request-to-repo slice to a new intent-fidelity and existing-repo change slice.
- Reset this progress log to start a fresh loop at iteration 0.
- New regression target:
  - `python cli.py implement --prompt "make me a complex graphic calc app" --out ../sample2`
  - Expected future behavior: blocked clarification, no generated simple CLI
    calculator files.
- New existing-repo target:
  - generate a calculator repo
  - run a prompt-driven existing-repo change such as `add exponent support`
  - validate `python calculator.py 2 ^ 3` -> `8`
- Confirmed prompt corpus exists for profiling:
  - `../prompts/README.md`
  - `../prompts/coding_agent_prompts_seed.jsonl`
- Current next step: add unsupported-interface and existing-repo-change fixtures,
  then make the request parser fail the graphical calculator regression in the
  right direction.
- User pushed back on broad hard-coded English rules. Updated `plans/today.md`
  to make learned prompt understanding the active direction: prompt corpus
  profiling, explicit encoder targets, held-out evaluation, and training or a
  documented data blocker. Deterministic rules should remain only as a
  lower-bound baseline or narrow safety fallback.
- Current next step after the pivot: build the prompt corpus loader/profile and
  prompt-intent eval target before expanding parser keyword coverage.

### Iteration 1: Prompt-Intent Dataset And Eval Harness

- Worker: Codex
- Goal: pivot away from broad deterministic unsupported-interface parsing and
  add the smallest learned/JEPA-oriented prompt understanding step.
- Files changed:
  - `prompt_intents.py`
  - `examples/prompt_intents/greenshot_7_intents.jsonl`
  - `tests/test_prompt_intents.py`
  - `pyproject.toml`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 4 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py -q` ->
    passed, 8 tests
  - `git diff --check` -> passed
  - `python -m py_compile prompt_intents.py` -> passed
- Result:
  - Added labeled prompt-intent rows for supported CLI calculator creation,
    unsupported graphical/complex/interface/scientific/math prompts, and
    existing-repo power/exponent change prompts.
  - Added a loader that normalizes JSONL prompt labels into explicit
    `PromptIntentTarget` records: `repo_mode`, `task_type`, `domain`,
    `expected_action`, requested interfaces, features, unsupported
    requirements, clarification fields, and target files.
  - Added a profile helper and field-level evaluation harness that can score a
    future JEPA-style prompt encoder or other learned predictor against labels.
  - Profiled `../prompts/coding_agent_prompts_seed.jsonl`: 80 rows, splits
    train=53/validation=15/test=12, repo modes existing_repo=54/new_repo=25/
    unknown=1, expected actions ask_clarification=8/
    emit_existing_repo_change_spec=50/emit_request_spec=22.
  - Deferred training: the external seed corpus has useful held-out splits and
    clarification/change labels, but no explicit unsupported graphical
    requirement labels yet; this iteration therefore adds dataset/eval plumbing
    and focused GreenShot-7 labels instead of training a misleading model.
- Commit: `e6b62d1162202798a67d62b6dc92e21f259bd9fa`
- Push: succeeded to `main`
- Next: wire an intent prediction object into request-spec construction, then
  make `make me a complex graphic calc app` block through that path while
  preserving simple CLI calculator generation.
- Blockers: none

### Iteration 2: Prompt Intent To Request-Spec Blocking

- Worker: Codex
- Goal: connect prompt-intent prediction objects to request-spec construction
  so unsupported graphical/complex calculator prompts are rejected through the
  new prompt-intent path while preserving supported simple CLI generation.
- Files changed:
  - `prompt_intents.py`
  - `request_spec.py`
  - `cli/handlers.py`
  - `tests/test_prompt_intents.py`
  - `tests/test_request_spec.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_cli.py -q`
    -> passed, 32 tests
  - `python -m py_compile prompt_intents.py request_spec.py cli/handlers.py`
    -> passed
  - `git diff --check` -> passed
  - `python cli.py implement --prompt "make me a complex graphic calc app" --out <tmp>`
    -> exited 1, printed the CLI-only clarification, and did not write
    `calculator.py`
  - `python cli.py implement --prompt "make me a simple cli calc" --out <tmp> --no-validate`
    plus `python <tmp>/calculator.py 2 + 3` -> succeeded and printed `5`
- Result:
  - Added a fixture-backed `PromptIntentPrediction` boundary in
    `prompt_intents.py` that exact-matches labeled prompt-intent rows without
    adding broad English keyword rules.
  - Let `parse_request_to_spec(..., intent=...)` consume that prediction and
    emit an interface clarification for unsupported graphical/complex
    calculator intents, including requested/supported interface and unsupported
    requirement fields in the request-spec record only when present.
  - Wired `j3 implement` through `predict_prompt_intent`, so the graphical
    calculator regression blocks before calculator files are written while the
    existing simple CLI calculator path still builds.
- Commit: `7f7b73d44b49d5c2fee9c09987572544b2324d1e`
- Push: succeeded to `main`
- Next: implement the existing-repo calculator change spec/command path for
  exponent/power support.
- Blockers: none

### Iteration 3: Existing-Repo Calculator Power Change

- Worker: Codex
- Goal: add the existing-repo calculator change spec/command path for
  exponent/power support.
- Files changed:
  - `existing_repo_change.py`
  - `cli/handlers.py`
  - `cli/parser.py`
  - `cli/__init__.py`
  - `pyproject.toml`
  - `tests/test_existing_repo_change.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_existing_repo_change.py -q` -> passed, 5 tests
  - `pytest tests/test_cli.py -q` -> passed, 24 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
    -> passed, 39 tests
  - `python -m py_compile existing_repo_change.py cli/handlers.py cli/parser.py cli/__init__.py`
    -> passed
  - `git diff --check` -> passed
  - Temp repo smoke:
    - `python cli.py implement --prompt "make me a simple cli calc" --out <tmp>/repo`
      -> passed and validated generated tests
    - `python cli.py change --repo <tmp>/repo --prompt "add exponent support"`
      -> passed and validated generated tests
    - `python <tmp>/repo/calculator.py 2 ^ 3` -> printed `8`
    - `python <tmp>/repo/calculator.py 2 power 3` -> printed `8`
    - argument-vector smoke for `["2", "**", "3"]` -> printed `8`
    - `python <tmp>/repo/calculator.py 2 '**' 3` -> printed `8`
    - `python -m pytest tests/test_calculator_cli.py -q` in the changed repo
      -> passed, 2 tests
- Result:
  - Added `existing-repo-change-spec-v1`, structured action plan, result, and
    JSONL attempt rows for the narrow calculator power feature.
  - Added `j3 change --repo <repo> --prompt "add exponent support"` and
    `--no-validate`/`--record` support.
  - The command consumes prompt-intent predictions for labeled existing-repo
    calculator power prompts, rejects unsupported prompts, and rejects repos
    that do not match the generated calculator shape.
  - The change updates `calculator.py` with `power`, `pow`, `^`, and `**`
    aliases plus `left ** right` dispatch, updates generated tests for all
    three required CLI examples, and moves the unknown-operator case away from
    `power`.
- Commit: `c4a71c8ef1ee326a26f45ebbecbfa3836c3519d5`
- Push: succeeded to `main`
- Next: train or evaluate the first narrow learned prompt-intent predictor for
  a concrete target such as `repo_mode` or `expected_action`, compare it against
  the deterministic lower-bound baseline, and record whether it is ready to
  replace any fixture-backed prediction path.
- Blockers: none

### Iteration 4: Learned Prompt-Intent Baseline

- Worker: Codex
- Goal: train/evaluate the first narrow learned prompt-intent predictor from the
  available labels with held-out metrics, without production wiring unless
  justified.
- Files changed:
  - `prompt_intents.py`
  - `cli/handlers.py`
  - `cli/parser.py`
  - `cli/__init__.py`
  - `tests/test_prompt_intents.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 7 tests
  - `pytest tests/test_cli.py -q` -> passed, 25 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
    -> passed, 42 tests
  - `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
    -> passed
  - `git diff --check` -> passed
  - `python cli.py train-prompt-intents --labels ../prompts/coding_agent_prompts_seed.jsonl --target expected_action repo_mode`
    -> passed
  - Seed-corpus train-exact-prompt fixture coverage check -> validation 0/15,
    test 0/12
- Result:
  - Added a deterministic standard-library token-perceptron learned baseline
    for scalar prompt-intent fields. It trains only on the train split and
    reports train/validation/test metrics against a train-majority baseline.
  - Added `j3 train-prompt-intents` as an evaluation/reporting command. It does
    not change production `j3 implement` or `j3 change` behavior.
  - Seed-corpus held-out metrics:
    - `expected_action`: validation learned 10/15 = 0.667 vs majority 9/15 =
      0.600; test learned 9/12 = 0.750 vs majority 8/12 = 0.667.
    - `repo_mode`: validation learned 13/15 = 0.867 vs majority 11/15 = 0.733;
      test learned 11/12 = 0.917 vs majority 10/12 = 0.833.
  - Compared with the current fixture-style exact-prompt lower bound on the
    seed corpus using train-only prompts: it has no validation/test prompt
    coverage, so majority-label is the useful numeric baseline for held-out
    scoring.
  - Production wiring decision: do not replace fixture-backed request-spec or
    change-spec prediction yet. The model beats the majority baseline on both
    held-out targets, but `expected_action` still has weak validation accuracy
    and the seed corpus has no explicit unsupported graphical requirement
    labels.
- Commit: `fc9dc87a9b734234e9ebdcbd883147f9dea3d7f7`
- Push: succeeded to `main`
- Next: inspect held-out residuals and add stronger labeled prompt-intent rows
  or feature targets before considering learned production routing.
- Blockers: none
