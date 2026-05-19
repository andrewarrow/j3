# SCALE-001 Local Pretraining Feasibility Inventory

Date: 2026-05-19

## Verdict

`j3` has enough local data and artifact discipline to justify near-term local
encoders, sparse learned rankers, and small shadow-only transition models for
the current Python maintenance wedge. It does not have enough reviewed data,
compute planning, objective clarity, or evaluation coverage to claim frontier
scale language/code pretraining feasibility.

The useful next step is not broad model scale. It is to turn the existing
prompt/spec, repo-state, local-knowledge, action, validation, and issue/PR
artifacts into stable train/eval records with provenance and leakage controls.
Frontier-scale pretraining remains a long-term research requirement, not a
near-term product dependency.

## Feasible Near Term

Near-term local learning should stay bounded to models that improve existing
gates while leaving code materialization to structured actions and validated
builders:

- Prompt/spec classifiers and encoders that predict task type, ambiguity,
  expected action, target artifact, and inferred defaults.
- Code-region and repo-state encoders that improve retrieval over local
  conventions, package layout, tests, imports, and changed symbols.
- Sparse or small neural rankers over candidate/action/outcome records.
- Shadow-only transition models that predict action utility, observation delta,
  blocker labels, and validation likelihood.
- Retrieval models for local knowledge records, validation recipes, accepted
  diffs, failed candidates, and hard negatives.

These are plausible because the repo already has deterministic encoders,
structured action records, validation outcomes, and held-out real-repo gates.
The bar for any learned model is beating feature hashing, rules, and linear
baselines on held-out repos without changing production routing.

## Not Feasible Yet

The repo is not ready for frontier-scale language/code pretraining:

- Data volume is orders of magnitude short. The strategy target notes
  `100,000+` examples for serious local pretraining; the durable reviewed
  task/outcome data is still in the hundreds to low thousands depending on how
  synthetic rows and scratch artifacts are counted.
- The current data is wedge-shaped: pytest authoring, small-library edits,
  structured repair, real-repo ladder tasks, and selected issue/PR replays.
  It does not cover broad Python library competence, algorithm synthesis,
  architectural changes, multi-step planning, or general code generation.
- There is no committed tokenizer, pretraining pipeline, training compute
  budget, checkpoint policy, or model-card/release process for large local
  models.
- License, terms, checksum, split, and redistribution rules are not yet
  consolidated into a data policy. That is the direct follow-on for
  `SCALE-002`.
- Evaluation is strong for guarded wedge gates, but not broad enough to
  measure general language/code pretraining gains.

## Existing Local Data And Evidence

| Source | Current value | Path references | Feasibility use |
| --- | --- | --- | --- |
| Prompt/spec corpus | 320 expanded coding-agent prompt rows are used for prompt-intent and Prompt-JEPA demos. The corpus includes human seed and synthetic template rows, with split and leakage checks. | `docs/PROMPT_JEPA_DEMO.md`, `docs/MODEL_001_PROMPT_INTENT_BASELINE_2026-05-18.md`, `examples/prompt_intents/greenshot_7_intents.jsonl`, external `../prompts/coding_agent_prompts_expanded_v0.jsonl` | Good for schema shakeout and first prompt classifiers; too small and synthetic-heavy for robust pretraining. |
| Deterministic encoders | Feature hashing exists for prompts, source, repo state, and prompt+repo transition records. | `j3/prompt_jepa.py`, `j3/repo_state.py`, `j3/features.py`, `j3/prompt_repo_transitions.py`, `examples/transition_bench/prompt_repo_transitions.jsonl` | Baselines for any learned encoder; learned models must beat these held out. |
| Transition and candidate outcomes | Small structured transition/candidate corpora and shadow matrix artifacts exist. | `examples/transition_bench/candidate_outcomes.jsonl`, `examples/transition_bench/mined_git_transitions.jsonl`, `examples/transition_shadow_matrix.json`, `docs/TRANSITION_MATRIX_RESIDUALS_2026-05-18.md` | Useful for ranking and transition residual learning; not enough for broad world-model training. |
| Real-repo ladder | Pinned tasks and live validation reports exist for tests-only and one-file feature wedges. | `examples/real_repo_eval_ladder.json`, `docs/REAL_REPO_EVAL_LADDER.md`, `docs/REAL_010_TESTS_ONLY_SHADOW_SCORE_2026-05-18.md`, `docs/REAL_012_ONE_FILE_FEATURE_SHADOW_SCORE_2026-05-18.md` | Good held-out gate for small local models; still only four ladder repos and narrow task classes. |
| Issue/PR replay | A mini replay manifest and many focused issue/PR reports now capture prompt text, accepted diffs, validation recipes, decoys, and coverage blockers. | `examples/issue_pr_mini_replay/manifest.json`, `docs/ISSUE_PR_MINI_REPLAY.md`, `docs/DATA_039_LIVE_ISSUE_PR_DECOY_VALIDATION_2026-05-18.md`, `docs/DATA_040_LIVE_PYTEST_DECOY_VALIDATION_2026-05-18.md`, `docs/VAL_002_CROSS_ROW_VALIDATION_STRENGTH_PROBE_2026-05-18.md` | Highest-value path toward trainable real task data; currently too small and not normalized into one durable training table. |
| Materialization coverage | Real PR materialization audits and typed/source-region candidate reports classify expressible action families and gaps. | `docs/MAT_007_REAL_PR_MATERIALIZATION_REFRESH_2026-05-18.md`, `docs/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.md`, `docs/MAT_013_REAL_PR_MATERIALIZATION_COVERAGE_REFRESH_2026-05-18.jsonl`, `docs/MAT_010_CLICK_3422_TYPED_BUILDER_CANDIDATE_2026-05-18.md`, `docs/MAT_014_REQUESTS_7437_TYPED_BUILDER_CANDIDATE_2026-05-19.md` | Good supervision for action-family coverage and materialization-risk prediction; not source-generation pretraining. |
| Local knowledge records | The wedge inventory and extractor code define citeable pytest, packaging, import-style, validation, and library idiom records. | `docs/LOCAL_KNOWLEDGE_INVENTORY.md`, `j3/local_knowledge.py`, `tests/test_local_knowledge.py` | Useful for retrieval and attribution models; needs more records across repos and docs. |
| External Apache Python corpus | A local 31-repo Apache-2.0 corpus is documented outside this repo. | `docs/TRAINING.md`, local `/Users/aa/os/python-apache`, `runs/apache-python-git/examples.jsonl`, `runs/apache-python-git/metrics.json` | Useful raw code/test corpus for local representation learning; not enough by itself because task labels, accepted outcomes, and policy are incomplete. |
| Hard negatives and validation blockers | Decoy validation and policy probes distinguish behavior-observable negatives from coverage gaps and leakage risk. | `docs/HARD_NEGATIVES.md`, `docs/VAL_002_CROSS_ROW_VALIDATION_STRENGTH_PROBE_2026-05-18.md`, `docs/DATA_039_LIVE_ISSUE_PR_DECOY_VALIDATION_2026-05-18.md`, `docs/DATA_040_LIVE_PYTEST_DECOY_VALIDATION_2026-05-18.md` | Critical for ranker training; needs more behavior-observable negatives before production use. |

## Missing Before Serious Local Pretraining

Data gaps:

- A single versioned training manifest that joins prompts, repo-before refs,
  action records, candidate-after snapshots, validation outcomes, residuals,
  hard negatives, split labels, checksums, and provenance.
- More real issue/PR examples with accepted diffs, behavior-observable decoys,
  validation recipes, and candidate-after snapshots.
- More local knowledge records extracted from docs, README examples, tests,
  configs, and accepted diffs.
- Stable split rules by repository, task family, prompt family, synthetic
  template family, and source license.
- Clear handling for scratch `/tmp` artifacts versus checked-in durable
  examples.

Objective gaps:

- Explicit contrastive or supervised objectives for prompt/spec, code-region,
  repo-state, local-knowledge retrieval, action ranking, and transition
  prediction.
- Negative sampling rules that avoid label leakage from accepted diffs or
  decoy names.
- Calibration targets for uncertainty, blocker prediction, clarification, and
  validation cost.
- A policy for whether any local generator objective is allowed, and how its
  outputs become structured actions instead of free-form patch text.

Compute and tooling gaps:

- Hardware inventory, expected training times, storage budget, checkpoint
  cadence, and reproducibility commands.
- Tokenization or AST/bytecode representation decisions for larger code
  models.
- Dataset build commands that can regenerate every row from source refs and
  checksums.
- Model registry, evaluation harness, and rollback policy for local checkpoints.

Evaluation gaps:

- Held-out issue/PR replay suites large enough to compare feature hashing,
  linear baselines, and small neural encoders.
- Regression gates that separate calibration repos from held-out repos.
- Metrics for retrieval usefulness, action-family selection, validation-cost
  prediction, hard-negative ranking, and blocker calibration.
- Red-team leakage checks for synthetic prompt families, accepted test
  structure, decoy labels, and repo overlap.

## Concrete Data-Policy Questions For SCALE-002

- Which local artifacts are allowed in durable training manifests: checked-in
  examples, generated `/tmp` reports, external repo snapshots, docs snapshots,
  or all of them with different retention rules?
- What license and terms fields are mandatory for raw code, docs, issues, PRs,
  generated candidates, and synthetic prompts?
- How should checksums be computed for source files, normalized diffs,
  validation logs, and extracted snippets?
- What is the stable split policy when the same repo appears in prompt rows,
  issue/PR replay, local knowledge, and real-repo ladder tasks?
- Can frontier-LLM-assisted labels be used for training, or only for
  development review, and how must teacher provenance be recorded?
- Which data may be redistributed, which may remain local-only, and which must
  be excluded from model release artifacts?

## Recommended Next Use

Use this inventory as the link target for future `SCALE-*` tasks. The next
practical sequence is:

1. Finish `SCALE-002` data provenance and release policy.
2. Build a small durable training manifest from existing prompt/spec,
   transition, real-repo, materialization, validation, and hard-negative rows.
3. Train or evaluate only small shadow models that target one current gate.
4. Treat broader local pretraining as blocked until data policy, scale,
   objectives, compute, and held-out evaluation are explicit.
