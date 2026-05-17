# Today Plan: Prompt+Repo JEPA Transition V0

The Prompt-JEPA developer demo slice is complete: the repo now has a
reproducible 320-row prompt corpus, a corpus inspector, a one-command local
demo report, mixed prompt/outcome indexing, source-embedding sidecars, focused
docs, and a cleaned root layout.

The next slice should make the project more interesting to JEPA developers by
moving from retrieval evidence to transition prediction:

```text
prompt + repo_before + structured action
  -> predicted repo_after / validation utility
  -> compare candidate next states
  -> choose apply / clarify / stop
```

Do not grow the prompt corpus again yet. The current corpus is enough for this
slice. More synthetic rows will not make the project more credible until j3 can
show a stronger world-model-shaped transition loop.

## Goal For The Next 24 Hours

Build the first explicit Prompt+Repo JEPA transition artifact and evaluation
loop:

- encode repo state deterministically from Python source files
- turn prompt/spec/action/outcome rows into transition rows with:
  - prompt context
  - repo-before embedding
  - structured action / outcome kind
  - repo-after embedding or blocked clarification target
  - validation status and cost fields
- persist the transition dataset as stable JSONL
- train or fit a small local V0 predictor over transition rows
- evaluate whether prompt+repo+action predicts/ranks the right next state
  better than prompt-only retrieval
- add the transition metrics to the demo report and docs

The outcome should look like a tiny local world-model experiment, not just an
index search.

## Strategic Decision

Prioritize Prompt+Repo JEPA transition modeling over more prompt generation.

Why:

- JEPA developers will look for state, action, prediction, and target spaces.
- The current demo already proves local indexing, no hosted tokens, and
  inspectable rows.
- The current source sidecar only records source embeddings; it does not yet
  make source state part of the predictive problem.
- The impressive next claim is: j3 can represent a repo state, an intended
  action, and a target state in a way that can be scored locally before
  validation.

This remains a V0 deterministic/standard-library slice. No neural training,
GPU, hosted embeddings, or production routing switch.

## Existing Baseline

Completed and available:

- `tools/prompts/generate_expanded_prompt_corpus.py`
  - generates `../prompts/coding_agent_prompts_expanded_v0.jsonl`
  - 320 rows: 80 `human_seed`, 240 `synthetic_template_v0`
- `inspect-prompt-corpus`
  - reports corpus shape and quality checks
- `demo-prompt-jepa`
  - builds label-only and mixed Prompt-JEPA indexes
  - writes `report.json`, `outcomes.jsonl`, `index.json`,
    `labels-index.json`, and `source-embeddings.json`
  - records `hosted_llm_api_tokens: 0`
  - records `hosted_repo_context_bytes: 0`
- `j3/features.py`
  - deterministic AST hash vectors for Python source
- `j3/prompt_jepa.py`
  - prompt context/target embeddings, predictor V0, retrieval eval, proposals
- `j3/prompt_jepa_demo.py`
  - one-command demo orchestration
- `docs/PROMPT_JEPA_DEMO.md`
  - developer-facing demo walkthrough

## Non-Goals

- No more synthetic prompt rows in this slice.
- No production routing switch from deterministic `implement` / `change`.
- No hosted LLM/API/embedding calls.
- No GPU, transformer, or model download.
- No broad Apache corpus retraining yet.
- No claim that deterministic V0 embeddings are the final JEPA model.
- No hiding failures: report residuals and weak cases explicitly.

## Step-By-Step Work Plan

### Step 1: Add A Repo-State Encoder Artifact

Deliverable:

- add a small module such as `j3/repo_state.py`
- encode a repository directory into a stable record:
  - schema version
  - feature version
  - embedding dimension
  - included Python file paths
  - file SHA-256 hashes and byte counts
  - aggregate repo embedding
  - empty-repo embedding support
- use `features.embed_python_source` for per-file embeddings
- aggregate deterministically, for example mean vector plus counts
- keep vectors JSON-serializable and validate dimensions

Why this matters:

- it turns the current source sidecar into a reusable repo-state representation
- it creates a concrete `s(repo)` space for JEPA transition work

Verification:

```bash
pytest tests/test_repo_state.py -q
python -m py_compile j3/repo_state.py
```

### Step 2: Build Prompt+Repo Transition Rows

Deliverable:

- add a transition schema such as `prompt-repo-transition-v1`
- build transitions from demo outcomes:
  - create calculator repo:
    - before state: empty repo
    - action: create calculator app
    - after state: generated repo source embedding
    - validation: passed
  - add exponent support:
    - before state: calculator before change
    - action: add exponent support
    - after state: changed repo source embedding
    - validation: passed
  - blocked auth:
    - before state: empty or target repo state as applicable
    - action: ask clarification / blocked
    - after state: no source change
    - validation: not run / blocked
- persist transition JSONL in the demo output, for example:

```text
/tmp/j3-prompt-jepa-demo/transitions.jsonl
```

- include prompt context embedding and Prompt-JEPA target embedding references
  or checksums so the transition rows bridge prompt space and repo-state space

Verification:

```bash
python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null
python - <<'PY'
import json
from pathlib import Path
rows = [json.loads(line) for line in Path('/tmp/j3-prompt-jepa-demo/transitions.jsonl').read_text().splitlines()]
assert rows
print(len(rows), rows[0]['schema_version'])
PY
```

### Step 3: Add A Tiny Transition Predictor V0

Deliverable:

- add a deterministic V0 predictor over transition rows
- input:
  - prompt context embedding
  - repo-before embedding
  - structured action kind / outcome kind features
- target:
  - repo-after embedding for source-changing outcomes
  - blocked/clarification target for non-source outcomes
- baseline can be simple and honest:
  - nearest transition by prompt+repo+action context
  - action-conditioned average delta
  - or a small feature-hash vector over context/action plus repo-before delta
- persist model metadata:
  - schema version
  - embedding dim
  - train row ids
  - predictor kind
  - decision: evaluation-only

Verification:

```bash
pytest tests/test_prompt_repo_transitions.py -q
python -m py_compile j3/prompt_repo_transitions.py
```

### Step 4: Evaluate Consequence Prediction

Deliverable:

- add metrics that JEPA developers can inspect:
  - top-1/top-k correct next outcome kind
  - top-1/top-k validation status
  - nearest predicted repo-after state
  - source-changing vs blocked/clarification split
  - residual examples with prompt, action, expected, predicted, and distance
- compare against prompt-only retrieval where possible
- keep the dataset tiny and honest; the point is shape and instrumentation,
  not benchmark claims

Verification:

```bash
python cli.py eval-prompt-repo-transitions \
  --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl \
  --top-k 3 \
  --json
pytest tests/test_cli.py -q
```

If the command name changes during implementation, update this plan and record
why in `plans/today.progress.md`.

### Step 5: Wire Transition Metrics Into The Demo Report

Deliverable:

- `demo-prompt-jepa` should also write:

```text
/tmp/j3-prompt-jepa-demo/transitions.jsonl
/tmp/j3-prompt-jepa-demo/transition-model.json
/tmp/j3-prompt-jepa-demo/transition-eval.json
```

- `report.json` should include concise transition sections:
  - transition row counts
  - predictor kind
  - evaluation metrics
  - representative residuals
  - source-state feature version
  - explicit `evaluation_only_not_wired_to_production`

Verification:

```bash
python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
python -m json.tool /tmp/j3-prompt-jepa-demo/transition-eval.json >/dev/null
python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null
```

### Step 6: Update Developer-Facing Docs

Deliverable:

- update `docs/PROMPT_JEPA_DEMO.md`
- explain the new transition story:

```text
prompt observation + repo_before state + action
  -> predicted repo_after state / utility
```

- show exact commands to inspect:
  - transition rows
  - repo-state records
  - transition predictor metadata
  - evaluation metrics and residuals
- clearly state what is V0/deterministic and what remains future neural JEPA
  work

Verification:

```bash
git diff --check
```

## Acceptance Criteria

Minimum success:

- reusable repo-state encoder exists and is tested
- demo writes Prompt+Repo transition JSONL rows
- transition rows include prompt, repo-before, action, repo-after or blocked
  target, and validation/cost fields
- a V0 transition predictor/eval path runs locally
- demo report includes transition metrics
- docs explain the transition artifact clearly
- production routing remains unchanged

Strong success:

- transition eval compares prompt-only retrieval vs prompt+repo+action context
- report includes residuals that make failure modes visible
- source-changing and blocked/clarification outcomes are represented
- the demo can be run from scratch in under a minute
- the story is compelling to JEPA developers because it has explicit state,
  action, target, prediction, and evaluation artifacts

## Testing Plan

Run focused checks first:

```bash
pytest tests/test_repo_state.py -q
pytest tests/test_prompt_repo_transitions.py -q
pytest tests/test_prompt_jepa.py -q
pytest tests/test_cli.py -q
python -m py_compile \
  j3/repo_state.py \
  j3/prompt_repo_transitions.py \
  j3/prompt_jepa_demo.py \
  cli/handlers.py cli/parser.py cli/__init__.py
git diff --check
```

Manual smoke:

```bash
python tools/prompts/generate_expanded_prompt_corpus.py

python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5

python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null
python -m json.tool /tmp/j3-prompt-jepa-demo/transitions.jsonl >/dev/null || true
```

For JSONL, use a line-by-line validation helper rather than `json.tool` if the
transition file remains newline-delimited JSON.

Run full `pytest -q` only after broad shared changes or before a final
integration gate.

## Open Decisions

1. Module name:
   - Proposed: `j3/prompt_repo_transitions.py`.

2. CLI command name:
   - Proposed: `eval-prompt-repo-transitions`.

3. Transition predictor V0:
   - Proposed: nearest-neighbor plus action-conditioned repo-state delta.

4. Blocked outcomes:
   - Proposed: represent blocked/clarification targets as non-source outcomes
     with unchanged or empty repo-after state plus explicit `outcome_kind`.

5. Dataset size:
   - Proposed: use current demo outcomes first, then add more structured
     calculator outcome rows only if needed to make the eval meaningful. Do not
     expand generic prompt labels in this slice.

## After This Slice

1. Add a second non-calculator greenfield builder, likely one-file library
   generation, so transition eval covers more than calculator source states.
2. Connect mined source transitions from `docs/TRAINING.md` to the same
   transition schema.
3. Add negative candidate actions and evaluate whether the transition model
   rejects them before validation.
4. Replace deterministic V0 predictors with a small learned local encoder only
   after the transition artifacts and metrics are stable.
