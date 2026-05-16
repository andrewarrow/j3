do not let the README.md file get too big. When adding more add new markdown files and reference them like TRAINING.md

Project direction:
- j3 is an experiment in a local-first JEPA coding agent: repair Python repos by predicting consequences of structured edits in latent repo space, without asking an LLM to generate patch candidates first.
- Treat the repo as a world: code is state, patches are actions, tests/type checks/stack traces are observations, and a passing suite is the target state.
- The current codebase is the prototype proving that loop: mine/train/rank structured patches, then validate with tests.
- Current milestone is moving from toy synthetic transitions toward real git-history signal and better ranking.
- `j3 mine` writes real Python before/after transitions to `data/transitions/*.jsonl`.
- `j3 train --transitions ...` combines synthetic transitions with mined `git_transition` examples.
- The prototype model is still non-neural: hashed AST embeddings, action-delta prototypes, and bounded exemplar deltas. Mined git exemplars should influence ordinary candidate actions during ranking.
- Keep evaluating against `examples/greenshot_bugs` and report baseline vs model-ranked solved, pass@1, and avg candidates.
- Next priority after mining/scorer plumbing: build a stronger eval ladder, parse pytest/error logs into structured hints, expand the structured action space, then add a trainable encoder/ranker.

Verification cadence:
- Run focused tests for the modules touched by the change first.
- Run full `pytest` once before final when the change affects behavior, ranking, diagnostics, candidate generation, parsing, CLI flows, or shared code.
- Do not repeatedly rerun full `pytest` after tiny follow-up edits when a focused test covers the edit.
- Run the GreenShot-4 checkpoint eval only when diagnostics/ranking behavior changed or when benchmark numbers are explicitly requested.
- When running GreenShot-4 for the ranking-miss path, use `runs/mit-python-git/model.json` if it exists and report baseline vs model-ranked solved, pass@1, average candidates, plus any bad-ranking/missing-action summary.
