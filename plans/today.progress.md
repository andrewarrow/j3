# Today Progress

This file is the live progress log for `plans/today.md`. Keep `plan.md` stable.
Keep `plans/today.md` stable for routine progress, but update it narrowly when
new implementation facts change the 24-hour plan itself. Record any
`plans/today.md` change here with the reason.

## Status

- Current phase: unsupported-requirement labels and eval target added locally
- Completed iterations: 7
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
  - `python cli.py train-prompt-intents --labels ../prompts/coding_agent_prompts_seed.jsonl --target expected_action repo_mode requires_clarification primary_artifact --show-residuals --residual-limit 12`
  - `python cli.py train-prompt-intents --labels examples/prompt_intents/greenshot_7_intents.jsonl --target unsupported_requirement --show-residuals --residual-limit 12`
  - `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
- Latest implementation commit: `44283da598c50102c3291fdc18b56ac3720cccff`
- Current blocker: none
- Next task: keep learned production routing blocked; inspect unsupported-
  requirement residuals and add more held-out label coverage or better encoder
  features before any model can replace fixture-backed request-spec or
  change-spec routing

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

### Iteration 5: Prompt-Intent Residual Reporting

- Worker: Codex
- Goal: inspect held-out residuals from the learned prompt-intent baseline and
  decide the next narrow data/target improvement before production routing.
- Files changed:
  - `prompt_intents.py`
  - `cli/handlers.py`
  - `cli/parser.py`
  - `tests/test_prompt_intents.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 7 tests
  - `pytest tests/test_cli.py -q` -> passed, 26 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
    -> passed, 43 tests
  - `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
    -> passed
  - `git diff --check` -> passed
  - `python cli.py train-prompt-intents --labels ../prompts/coding_agent_prompts_seed.jsonl --target expected_action repo_mode --show-residuals`
    -> passed
- Residual findings:
  - `expected_action` validation misses: `seed-0015` greenfield library
    predicted as existing-repo change; `seed-0059` refactor and `seed-0067`
    CI config predicted as new-repo requests; `seed-0074` and `seed-0078`
    vague clarification prompts predicted as concrete existing-repo changes.
  - `expected_action` test misses: `seed-0065` ruff config predicted as a
    new-repo request; `seed-0076` and `seed-0080` vague/implicit-scope
    clarification prompts predicted as concrete existing-repo changes.
  - `repo_mode` misses: `seed-0015` greenfield library predicted as
    existing-repo; `seed-0062` package refactor and `seed-0065` ruff config
    predicted as new-repo.
  - Misses cluster around ambiguous clarification safety and source/config/
    refactor artifact routing, not around the calculator graphical regression.
- Result:
  - Added learned-baseline residual records to split metrics and JSON output.
  - Added `j3 train-prompt-intents --show-residuals` plus
    `--residual-limit` for human inspection of misclassified rows.
  - Extracted existing `expected.artifacts` labels into prompt-intent targets
    and profile counts so future eval can separate source, tests, docs,
    config, package, and CI-oriented requests.
  - Production routing remains fixture-backed and conservative; no learned
    model is wired into request-spec or change-spec behavior.
- Commit: `b369919971d86d77f6d25c0c687ae705ea4dc4ed`
- Push: succeeded to `main`
- Next: add targeted train/validation/test labels or a second-stage target for
  `ask_clarification` vs concrete existing-repo work and for config/refactor/
  package artifact routing. Keep graphical/unsupported-interface labels as a
  separate gap before learned production routing.
- Blockers: none

### Iteration 6: Derived Prompt-Intent Safety Targets

- Worker: Codex
- Goal: add targeted derived train/eval targets for clarification safety and
  artifact routing, using existing seed labels and keeping graphical/
  unsupported-interface labels as a separate gap before learned production
  routing.
- Files changed:
  - `prompt_intents.py`
  - `cli/parser.py`
  - `cli/handlers.py`
  - `tests/test_prompt_intents.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 7 tests
  - `pytest tests/test_cli.py -q` -> passed, 27 tests
  - `pytest tests/test_prompt_intents.py tests/test_cli.py -q` -> passed, 34 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
    -> passed, 44 tests
  - `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
    -> passed
  - `git diff --check` -> passed
  - `python cli.py train-prompt-intents --labels ../prompts/coding_agent_prompts_seed.jsonl --target expected_action repo_mode requires_clarification primary_artifact --show-residuals --residual-limit 12`
    -> passed
- Result:
  - Added derived scalar targets `requires_clarification` and
    `primary_artifact` to normalized prompt-intent records and train/eval CLI
    choices. These are derived from existing `expected.action`/`clarify`,
    `clarification_fields`, and the first `expected.artifacts` label.
  - Added profile counts for the derived targets and missing artifact labels.
    Seed corpus profile: `requires_clarification` no=72/yes=8; primary
    artifact includes module=35, cli=17, pyproject=4, tests=8, package=1,
    ci_config=1, none=8. The `none` rows are the eight clarification rows.
  - Added residual context output so misses show action, repo mode, primary
    artifact, and clarification requirement. This makes expected-action misses
    show safety/config/package context directly, for example `seed-0067`
    as `ci_config`, `seed-0065` as `pyproject`, and `seed-0074`/`seed-0078`
    as `requires_clarification=yes`.
  - Held-out metrics for new targets:
    - `requires_clarification`: validation 13/15 = 0.867 vs majority 13/15 =
      0.867; test 10/12 = 0.833 vs majority 10/12 = 0.833. It isolates the
      vague clarification misses but is not better than majority yet.
    - `primary_artifact`: validation 7/15 = 0.467 vs majority 5/15 = 0.333;
      test 8/12 = 0.667 vs majority 6/12 = 0.500. It improves artifact
      routing eval but still misses package/CI/pyproject and some docs/none
      rows.
  - Inspected requested residual rows:
    - `seed-0015`: greenfield library, primary artifact `module`
    - `seed-0059`: existing-repo refactor, primary artifact `module`
    - `seed-0062`: existing-repo package refactor, primary artifact `package`
    - `seed-0065`: existing-repo ruff config, primary artifact `pyproject`
    - `seed-0067`: existing-repo CI config, primary artifact `ci_config`
    - `seed-0074`, `seed-0076`, `seed-0078`, `seed-0080`: clarification rows,
      primary artifact `none`, `requires_clarification=yes`
  - Production routing remains fixture-backed and conservative; no learned
    model is wired into request-spec or change-spec behavior.
  - Data gap: the external seed corpus still has no explicit unsupported
    graphical/interface requirement labels (`unsupported_requirement_count=0`),
    so graphical unsupported-interface routing remains a separate labeling
    gap before learned production routing.
- Commit: `2e14c9367836d84835243ee6be297da3614262ea`
- Push: succeeded to `main`
- Next: add/source explicit unsupported-interface labels for graphical or other
  unsupported UI requests in the seed corpus before any learned production
  routing decision.
- Blockers: none

### Iteration 7: Unsupported-Requirement Labels And Target

- Worker: Codex
- Goal: add/source explicit unsupported-interface labels for graphical or other
  unsupported UI requests before any learned production routing decision.
- Files changed:
  - `prompt_intents.py`
  - `examples/prompt_intents/greenshot_7_intents.jsonl`
  - `cli/parser.py`
  - `cli/handlers.py`
  - `tests/test_prompt_intents.py`
  - `tests/test_cli.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 8 tests
  - `pytest tests/test_cli.py -q` -> passed, 27 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
    -> passed, 45 tests
  - `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
    -> passed
  - `git diff --check` -> passed
  - `python cli.py train-prompt-intents --labels examples/prompt_intents/greenshot_7_intents.jsonl --target unsupported_requirement --show-residuals --residual-limit 12`
    -> passed
  - `python cli.py train-prompt-intents --labels ../prompts/coding_agent_prompts_seed.jsonl --target expected_action repo_mode requires_clarification primary_artifact --show-residuals --residual-limit 12`
    -> passed
- Result:
  - Did not edit `../prompts/coding_agent_prompts_seed.jsonl` because it is
    outside the current git repo. The external seed corpus still profiles as
    `unsupported_requirement_counts={"none": 80}` and remains unsuitable for
    unsupported-interface training.
  - Added focused local prompt-intent fixture rows for unsupported graphical,
    GUI, desktop, web, UI, and scientific calculator requests. Local fixture
    coverage is now 25 rows with 17 unsupported/clarification rows.
  - Added a scalar `unsupported_requirement` target derived from labeled
    `unsupported_requirements`, while preserving the multi-label list. For
    prompts with both generic complexity and concrete interface labels,
    `unsupported_requirement` prioritizes the concrete label, e.g.
    `make me a complex graphic calc app` -> `graphical_interface`.
  - Local unsupported label counts:
    `graphical_interface=6`, `web_interface=3`,
    `scientific_operations_unspecified=3`, `desktop_interface=2`,
    `ui_interface=1`, `visual_interface_scope=1`,
    `domain_unspecified=1`, `none=8`.
  - Added `unsupported_requirement` to train/eval CLI target choices and
    residual context output. Production routing remains fixture-backed exact
    matching; no learned model was wired into request-spec or change-spec
    behavior.
  - Local `unsupported_requirement` learned-baseline metrics:
    train 11/11 = 1.000 vs majority 4/11 = 0.364; validation 5/6 = 0.833 vs
    majority 2/6 = 0.333; test 3/8 = 0.375 vs majority 2/8 = 0.250.
  - Residual gap: held-out graphical examples remain weak. Misses include
    `make me a complex graphic calc app`, `make a graphical calculator`, and
    `make a graphical desktop calc`, so this target is not ready for learned
    production routing.
- Commit: `44283da598c50102c3291fdc18b56ac3720cccff`
- Push: succeeded to `main`
- Next: add more split-balanced unsupported-interface labels and/or improve
  prompt representation features so graphical/UI unsupported target recall
  improves on held-out rows before production learned routing is reconsidered.
- Blockers: none

### Iteration 8: Split-Balanced Unsupported-Interface Labels

- Worker: Codex
- Goal: add more split-balanced unsupported-interface labels so graphical/UI
  unsupported target recall improves on held-out rows before learned production
  routing is reconsidered.
- Files changed:
  - `examples/prompt_intents/greenshot_7_intents.jsonl`
  - `tests/test_prompt_intents.py`
  - `plans/today.progress.md`
- Tests run:
  - `pytest tests/test_prompt_intents.py -q` -> passed, 8 tests
  - `pytest tests/test_prompt_intents.py tests/test_request_spec.py tests/test_existing_repo_change.py tests/test_cli.py -q`
    -> passed, 45 tests
  - `python -m py_compile prompt_intents.py cli/handlers.py cli/parser.py cli/__init__.py`
    -> passed
  - `git diff --check` -> passed
  - `python cli.py train-prompt-intents --labels examples/prompt_intents/greenshot_7_intents.jsonl --target unsupported_requirement --show-residuals --residual-limit 20`
    -> passed
- Result:
  - Added 10 focused local fixture rows: graphical/gui calculator requests,
    one ambiguous math clarification row, and two supported `none` negatives
    for command-line/new-repo and existing-repo power phrasing.
  - Local fixture coverage is now 35 rows with split counts train=17,
    validation=8, test=10. Unsupported requirement counts are
    `graphical_interface=12`, `none=10`, `web_interface=3`,
    `scientific_operations_unspecified=3`, `desktop_interface=2`,
    `domain_unspecified=2`, `ui_interface=2`, and
    `visual_interface_scope=1`.
  - Local `unsupported_requirement` learned-baseline metrics improved from
    train 1.000, validation 0.833, test 0.375 to train 17/17 = 1.000,
    validation 7/8 = 0.875, and test 9/10 = 0.900. Majority baselines were
    train 6/17 = 0.353, validation 2/8 = 0.250, and test 2/10 = 0.200.
  - The previous held-out graphical misses are no longer residuals:
    `gs7-intent-0004` (`make me a complex graphic calc app`),
    `gs7-intent-0005` (`make a graphical calculator`),
    `gs7-intent-0006` (`make a gui calculator`), and `gs7-intent-0024`
    (`make a graphical desktop calc`) are all correctly labeled.
  - Remaining residuals:
    - validation: `gs7-intent-0033` expected `ui_interface`, predicted
      `graphical_interface` for `create a calculator UI app`
    - test: `gs7-intent-0009` expected `domain_unspecified`, predicted
      `ui_interface` for `make a math thing`
  - Production routing remains fixture-backed and conservative; no learned
    model was wired into request-spec or change-spec behavior.
- Commit: pending at progress-log update time
- Push: pending at progress-log update time
- Next: inspect the remaining UI-vs-graphical and ambiguous-math residuals, or
  improve prompt representation features, before any learned production routing
  decision.
- Blockers: none
