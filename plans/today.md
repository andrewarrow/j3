# Today Plan: Transition Bench And Action Selection V1

The Prompt+Repo JEPA demo slice is complete. The repo now has:

- a reproducible 320-row prompt corpus
- prompt corpus inspection
- Prompt-JEPA indexing and retrieval evaluation
- a one-command Prompt+Repo JEPA demo
- `repo-state-v1` records
- `prompt-repo-transition-v1` rows
- an evaluation-only `prompt-repo-transition-predictor-v0`
- consequence-prediction metrics and residuals
- developer docs and a focused README pitch

The next slice should make the project more compelling to JEPA developers by
moving from a tiny three-row demo to a measurable action-selection benchmark.

The important question is no longer "can j3 embed prompts?" It is:

```text
given repo_before and several candidate actions,
can j3 predict which candidate future is worth validating first?
```

That is the coding-agent version of a useful JEPA world model.

## Goal For The Next 24 Hours

Build the first transition-benchmark and candidate-action evaluation path:

- inventory the existing local transition assets without checking generated
  data into git
- normalize demo transitions, mined git transitions, and repair candidate
  outcomes into one inspectable benchmark shape
- create candidate-action groups where one or more candidates pass validation
  and the rest are hard negatives
- score/rank candidate futures with local repo-state/action features
- compare against simple baselines
- report metrics that matter for coding agents:
  - pass@1
  - top-k pass rate
  - mean reciprocal rank
  - average candidates validated before first pass
  - local runtime
  - hosted LLM/API tokens: zero
  - hosted repo-context bytes: zero
- write residual examples that show which action choices j3 gets wrong

The outcome should be a small but credible benchmark artifact, not another
prompt list.

## Strategic Decision

Prioritize action selection over more prompt generation.

Why:

- The 320-row prompt corpus is enough for the current narrow prompt slice.
- The Prompt+Repo demo proves the state/action/target artifact shape, but only
  with three transition rows.
- Local ignored assets already exist for scale:
  - `data/transitions/apache-python/*.jsonl` has mined git transition rows in
    this workspace
  - `runs/apache-python-git/model.json` was trained from 10,000 synthetic repair
    examples plus mined git transitions
  - `runs/apache-python-git/*candidate-outcomes.jsonl` records passing and
    failing repair candidates from GreenShot runs
- JEPA developers will look for candidate futures, negatives, ranking margins,
  and residuals.

Do not commit generated JSONL datasets or large run artifacts. Keep `data/` and
`runs/` ignored. Check in only the code, tests, small fixtures, manifests, and
reproduction instructions needed for another developer to rebuild the artifacts
locally or download a packaged release artifact later.

## Existing Baseline

Completed and available in git:

- `tools/prompts/generate_expanded_prompt_corpus.py`
  - generates `../prompts/coding_agent_prompts_expanded_v0.jsonl`
- `inspect-prompt-corpus`
- `demo-prompt-jepa`
  - writes prompt indexes, outcome rows, source embeddings, transition rows,
    transition model, transition eval, and a report
- `eval-prompt-repo-transitions`
  - evaluates `prompt-repo-transition-v1` rows
- `j3/repo_state.py`
  - deterministic `repo-state-v1` records over Python source
- `j3/prompt_repo_transitions.py`
  - transition rows, V0 predictor, eval metrics, residuals
- `j3/mining.py`
  - mines real Python before/after file transitions from git history
- `j3/training.py`
  - trains the older local source-transition prototype from synthetic and mined
    transitions
- candidate-ranking and evaluation infrastructure
  - candidate outcome rows
  - trained ranker support
  - pass@1 / candidate-count diagnostics
- docs:
  - `README.md`
  - `docs/PROMPT_JEPA_DEMO.md`
  - `docs/TRAINING.md`

Observed local ignored assets in this workspace:

- mined Apache Python transition JSONL files under `data/transitions/apache-python`
- an Apache Python run under `runs/apache-python-git`
- GreenShot candidate outcome JSONL files under `runs/apache-python-git`

These local assets are useful for development, but the new code must still have
small checked-in fixtures so CI and another developer can run the focused tests
without those private ignored files.

## Non-Goals

- Do not generate another large prompt corpus in this slice.
- Do not commit `data/`, `runs/`, or generated benchmark JSONL files.
- Do not require GitHub, network access, GPU, model downloads, or hosted LLMs.
- Do not switch production `implement`, `change`, `patch`, or `fix` routing to
  the new scorer yet.
- Do not claim benchmark significance from tiny fixtures. Report scale and
  limitations plainly.

## Step-By-Step Work Plan

### Step 1: Add A Transition Asset Inventory

Deliverable:

- add a small inventory path, likely `j3/transition_assets.py`
- summarize available local assets:
  - prompt corpus path and row count if present
  - Prompt+Repo demo artifacts if present
  - mined git transition files and row counts if present
  - candidate outcome files and row counts if present
  - trained prototype model metadata if present
- add a CLI command such as `inspect-transition-assets`
- make missing ignored assets a normal condition, not an error
- include checksums or stable file summaries for reproducibility

Why this matters:

- it tells developers exactly what data-backed evidence exists locally
- it avoids pretending ignored artifacts are part of git
- it creates the manifest foundation for a future GitHub Release zip

Verification:

```bash
pytest tests/test_transition_assets.py -q
pytest tests/test_cli.py -q
python cli.py inspect-transition-assets --json
```

### Step 2: Define A Transition Bench Schema

Deliverable:

- add a schema such as `transition-bench-v1`
- normalize rows from:
  - `prompt-repo-transition-v1` demo rows
  - mined `git_transition` before/after source rows
  - candidate outcome rows from repair evals
- keep source-specific fields explicit:
  - source kind
  - repo/file identity or task identity
  - repo-before or file-before embedding
  - structured action or candidate action
  - repo-after/file-after target embedding when available
  - validation outcome when available
  - cost fields
- add deterministic JSONL writer/loader/validator helpers
- include tiny checked-in fixtures for tests

Why this matters:

- it connects the prompt demo, source-transition training, and repair eval
  infrastructure into one JEPA-shaped benchmark surface
- it lets future learned models target the same artifact instead of one-off
  demo files

Verification:

```bash
pytest tests/test_transition_bench.py -q
python -m py_compile j3/transition_bench.py
```

### Step 3: Build Candidate Action-Choice Groups

Deliverable:

- convert candidate outcome JSONL rows into grouped action-choice records,
  likely `transition-action-choice-v1`
- group by task, phase, and repair plan
- include all validated candidates in rank order:
  - candidate action record
  - candidate target context
  - source/repo-before embedding
  - candidate repo-after or patched-source embedding when available
  - pass/fail validation result
  - candidate rank and first-passing index
- preserve hard negatives: failed candidates that looked plausible enough to
  validate

Why this matters:

- action choice is where a coding-agent world model becomes useful
- negatives make the benchmark more credible than nearest-neighbor retrieval

Verification:

```bash
pytest tests/test_transition_action_choice.py -q
```

### Step 4: Add An Evaluation-Only Future Scorer

Deliverable:

- add a deterministic V1 scorer over candidate action-choice groups
- score each candidate using local features:
  - repo/file-before embedding
  - candidate action kind and parameters
  - predicted after-state delta
  - validation/failure-hint features when present
- compare against baselines:
  - existing rank order
  - random or stable lexical order
  - prompt/source-only nearest neighbor where applicable
  - existing candidate ranker when available
- report:
  - pass@1
  - top-k pass rate
  - MRR
  - average first-passing rank
  - average candidates saved vs baseline
  - residual action-choice examples

Why this matters:

- this is the clearest small proof that j3 can predict useful candidate futures
  before test validation

Verification:

```bash
pytest tests/test_transition_action_choice.py -q
pytest tests/test_candidate_ranking.py -q
```

### Step 5: Add A One-Command Bench Demo

Deliverable:

- add a command such as `demo-transition-bench` or `eval-transition-bench`
- default to tiny checked-in fixtures so it works everywhere
- optionally accept ignored local assets:

```bash
python cli.py demo-transition-bench \
  --prompt-demo /tmp/j3-prompt-jepa-demo \
  --mined-transitions data/transitions/apache-python \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench
```

- write:

```text
manifest.json
transition-bench.jsonl
action-choices.jsonl
action-choice-eval.json
report.json
```

- include explicit zero hosted token/context fields

Why this matters:

- a JEPA developer should be able to run one command and see state/action/target
  rows, candidate negatives, metrics, and residuals

Verification:

```bash
python cli.py demo-transition-bench --out /tmp/j3-transition-bench
python -m json.tool /tmp/j3-transition-bench/report.json >/dev/null
python -m json.tool /tmp/j3-transition-bench/action-choice-eval.json >/dev/null
```

### Step 6: Document Reproduction And Packaging

Deliverable:

- update `docs/PROMPT_JEPA_DEMO.md` or add a focused
  `docs/TRANSITION_BENCH.md`
- explain:
  - what is checked in
  - what is generated locally
  - why generated JSONL files stay out of git
  - how to rebuild from ignored local Apache data
  - how a future release zip should be produced and verified
- keep `README.md` small; link to the focused doc

Why this matters:

- another developer needs a credible reproduction path without requiring the
  exact local workspace

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- `plans/today.progress.md` tracks the new reset and task queue
- a transition asset inventory runs with and without ignored local data
- a checked-in fixture can produce `transition-bench-v1` rows
- candidate action-choice groups are represented with passing and failing
  candidates
- an evaluation-only scorer reports pass@1, top-k, MRR, average first-passing
  rank, and residuals
- generated benchmark artifacts remain ignored and reproducible
- docs explain the checked-in vs generated artifact boundary

Strong success:

- the bench can also consume the local Apache mined transitions and GreenShot
  candidate outcomes
- report output shows hundreds or thousands of transition/candidate rows when
  local ignored assets are available
- residuals make failure modes obvious
- metrics compare j3 future scoring against at least one baseline
- the demo highlights zero hosted LLM/API tokens and zero hosted repo-context
  bytes

## Testing Plan

Run focused checks first:

```bash
pytest tests/test_transition_assets.py -q
pytest tests/test_transition_bench.py -q
pytest tests/test_transition_action_choice.py -q
pytest tests/test_cli.py -q
python -m py_compile \
  j3/transition_assets.py \
  j3/transition_bench.py \
  j3/transition_action_choice.py \
  cli/handlers.py cli/parser.py cli/__init__.py
git diff --check
```

Manual smoke:

```bash
python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5

python cli.py inspect-transition-assets --json

python cli.py demo-transition-bench \
  --prompt-demo /tmp/j3-prompt-jepa-demo \
  --mined-transitions data/transitions/apache-python \
  --candidate-outcomes runs/apache-python-git/greenshot-6-candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench

python -m json.tool /tmp/j3-transition-bench/report.json >/dev/null
python -m json.tool /tmp/j3-transition-bench/action-choice-eval.json >/dev/null
```

Run full `pytest -q` only after broad shared changes or before a final
integration gate.

## Open Decisions

1. Command names:
   - Proposed: `inspect-transition-assets` and `demo-transition-bench`.

2. Module names:
   - Proposed: `j3/transition_assets.py`, `j3/transition_bench.py`, and
     `j3/transition_action_choice.py`.

3. Release packaging:
   - Proposed: do not package data yet. First generate `manifest.json` with
     stable checksums. After the artifact shape stabilizes, publish a zip as a
     GitHub Release asset rather than committing JSONL to git.

4. Model boundary:
   - Proposed: keep all scoring evaluation-only until action-choice metrics are
     credible on held-out tasks.

## After This Slice

1. Convert mined git transitions into repo-level before/after records instead
   of file-level only.
2. Add held-out split support by repository and task family.
3. Add hard-negative mining from high-ranked failed candidates.
4. Feed action-choice residuals back into the prompt/repo transition predictor.
5. Only then consider a small learned local encoder to replace deterministic
   feature hashing.
