do not let the README.md file get too big. When adding more add new markdown files and reference them like TRAINING.md

Project direction:
- j3 is an experiment in a local-first JEPA coding agent: repair Python repos by predicting consequences of structured edits in latent repo space, without asking an LLM to generate patch candidates first.
- Treat the repo as a world: code is state, patches are actions, tests/type checks/stack traces are observations, and a passing suite is the target state.
- The current codebase is the prototype proving that loop: mine/train/rank structured patches, then validate with tests.
- Current milestone is moving from toy synthetic transitions toward real git-history signal and better ranking.
- Optimize for learning signal, not exhaustive pytest search: the correct action should be generated, the correct target represented, observations parsed into structured evidence, the ranker should put passing candidates near the top before validation, and diagnostics should distinguish missing actions from bad ranking or weak hints.
- `j3 mine` writes real Python before/after transitions to `data/transitions/*.jsonl`.
- `j3 train --transitions ...` combines synthetic transitions with mined `git_transition` examples.
- The prototype model is still non-neural: hashed AST embeddings, action-delta prototypes, and bounded exemplar deltas. Mined git exemplars should influence ordinary candidate actions during ranking.
- Keep GreenShot-4 as a periodic regression gate, and use GreenShot-5 as the short-term development ladder for multi-file call chains, decoy candidates, helper-level repairs, signature propagation, and nested imports.
- When reporting benchmark-style evals, include baseline vs model-ranked solved, pass@1, and average candidates. For day-to-day work, prefer the fastest focused eval mode that exercises the changed behavior.
- `j3 eval` defaults to ranked-only, task-level progress. Use `--phase both` for benchmark refreshes, `--verbose` for candidate-level progress, and `--quiet` to suppress progress logging.
- Use `j3 eval --explore-after-pass N --candidate-outcomes PATH` when collecting ranker data. Candidate outcome JSONL should be one row per tested candidate and include rank index, pass label, first-pass index, scores, action, target, params, and multiple-pass context.
- For the current next task and commit sequence, follow `plan.md` instead of duplicating the live queue here.
- Whenever editing `plan.md`, keep it as a clean handoff: remove or move completed/stale next steps, make the immediate next sequence explicit, and avoid leaving old tasks in any "Next tasks" list after they are done.

Verification cadence:
- Default to the smallest focused test that proves the touched behavior. Good examples:
  - `pytest tests/test_candidate_ranking.py -q`
  - `pytest tests/test_evaluation.py -q`
  - `pytest tests/test_patching.py -q`
  - `pytest tests/test_failure_hints.py -q`
- For small follow-up edits, run only the focused test that covers the edit. Do not reflexively run full `pytest`.
- Run full `pytest` as an intentional integration gate: before merging broad behavior changes, after touching multiple shared paths in a way focused tests do not cover, or when the user asks for a full verification pass.
- Run quick eval smoke checks with tight budgets when useful, for example `python3 cli.py eval --tasks examples/greenshot_3 --checkpoint runs/apache-python-git/model.json --timeout 10 --max-candidates 1`.
- Run the full GreenShot-4 checkpoint eval only when intentionally refreshing benchmark numbers, investigating ranking/diagnostics behavior, or when explicitly requested.
- When running GreenShot-4 for the ranking-miss path, use `runs/apache-python-git/model.json` if it exists and report baseline vs model-ranked solved, pass@1, average candidates, plus any bad-ranking/missing-action summary.
