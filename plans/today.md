# Today Plan: Prompt JEPA Encoder And Index

This 24-hour plan replaces the label-refinement loop with the first concrete
Prompt-JEPA index slice.

The last loop added useful prompt-intent data, train/test splits, residual
reporting, and a small learned classifier. That work is now support material,
not the active focus. Do not spend this slice expanding unsupported-interface
fixtures unless a test needs one small row.

## Goal For The Next 24 Hours

Build the first local JEPA-style prompt encoder and index artifact:

```text
prompt / task context
  -> context encoder vector
structured target record
  -> target encoder vector
context + target
  -> stored index row with neighbors and metadata
new prompt
  -> context vector
  -> nearest indexed prompt/spec/action/outcome rows
  -> candidate target evidence for later planner use
```

This must be an actual persisted index and query path, not another classifier
only. The first version may use deterministic standard-library feature hashing
for the encoder, but the data model must be JEPA-shaped: separate context and
target embeddings, stable vector dimensions, metadata, held-out evaluation, and
a file format that a neural encoder can replace.

## Existing Building Blocks

- `prompt_intents.py` loads prompt-intent JSONL rows, extracts structured
  targets, trains a small token baseline, and reports residuals.
- `examples/prompt_intents/greenshot_7_intents.jsonl` contains local prompt
  labels for GreenShot-7 calculator generation, unsupported prompts, and
  existing-repo power changes.
- `../prompts/coding_agent_prompts_seed.jsonl` contains a broader prompt seed
  corpus with train/validation/test splits.
- `features.py`, `training.py`, and `repair/patching/model.py` already provide
  a code-state embedding and JEPA-shaped transition baseline for Python repair.
- `request_spec.py` and `existing_repo_change.py` can produce structured target
  records for supported calculator paths.

## Definition Of Prompt-JEPA V0

Use a small explicit index schema such as:

```json
{
  "format": "j3.prompt-jepa-index.v1",
  "embedding_dim": 256,
  "context_encoder": {
    "kind": "feature_hashing",
    "schema_version": "prompt-context-v1"
  },
  "target_encoder": {
    "kind": "feature_hashing",
    "schema_version": "prompt-target-v1"
  },
  "rows": [
    {
      "id": "seed-0001",
      "split": "train",
      "source_path": "../prompts/coding_agent_prompts_seed.jsonl",
      "prompt": "make me a simple cli calc",
      "context_embedding": [0.0],
      "target_embedding": [0.0],
      "target": {
        "repo_mode": "new_repo",
        "expected_action": "emit_request_spec",
        "domain": "calculator"
      }
    }
  ]
}
```

The exact field names may change during implementation, but keep these
properties:

- context and target embeddings are separate
- vector dimension is fixed and validated
- rows keep enough metadata to inspect nearest neighbors
- train/validation/test split is preserved
- JSON output is stable and diffable
- query can run without network or model downloads

## Non-Goals For Today

- No production replacement of fixture-backed routing.
- No broad natural-language parser expansion.
- No new dependency unless the standard library is clearly insufficient and
  the watcher approves it.
- No GPU, transformer, or external embedding API.
- No edits to `plan.md`.
- No more large fixture-label expansion unless it directly validates the index.

## Step-By-Step Work Plan

### Step 1: Add Prompt-JEPA Index Module

Deliverable:

- module such as `prompt_jepa.py`
- dataclasses for index metadata, rows, query results, and eval results
- deterministic context encoder for prompt/task context
- deterministic target encoder for structured targets
- cosine similarity or dot-product nearest-neighbor search
- save/load JSON index with format validation

Verification:

- focused unit tests for encode, save/load, and query
- bad format/dimension cases are rejected

### Step 2: Build Index From Prompt JSONL

Deliverable:

- build from `examples/prompt_intents/greenshot_7_intents.jsonl`
- build from `../prompts/coding_agent_prompts_seed.jsonl` when present
- each row stores prompt, split, target metadata, context embedding, and target
  embedding

Verification:

- test index row count equals loaded records
- train/validation/test counts are preserved
- generated index JSON validates with `json.tool`

### Step 3: Add CLI Commands

Deliverable:

```bash
python cli.py build-prompt-jepa-index \
  --labels ../prompts/coding_agent_prompts_seed.jsonl \
  --out /tmp/j3-prompt-jepa-index.json

python cli.py query-prompt-jepa-index \
  --index /tmp/j3-prompt-jepa-index.json \
  --prompt "make me a simple cli calc" \
  --top-k 5
```

Verification:

- CLI tests cover build and query
- query prints nearest row ids, scores, actions, repo modes, and domains

### Step 4: Add Retrieval Evaluation

Deliverable:

- evaluate validation/test prompts against an index built from train rows
- metrics such as top-1/top-3 exact match for `expected_action`, `repo_mode`,
  `domain`, and optionally unsupported-requirement family
- residual output for bad neighbors

Verification:

- focused tests assert metrics shape and at least one meaningful retrieval
  result on local fixtures
- progress records metrics for local fixtures and `../prompts`

### Step 5: Connect To Existing Structured Records

Deliverable:

- target encoder can accept `PromptIntentTarget.to_record()`
- target encoder can also encode `request-spec-v1` and
  `existing-repo-change-spec-v1` records if supplied
- no production routing change yet

Verification:

- tests encode a request spec and an existing-repo change spec into stable
  target vectors

## Acceptance Criteria

Minimum success:

- a Prompt-JEPA index can be built, saved, loaded, and queried
- index rows have separate context and target embeddings
- CLI build/query works on local prompt fixtures
- retrieval eval runs on a train/validation/test split
- no production route is switched to learned retrieval

Strong success:

- build/query/eval works on both local fixtures and `../prompts`
- top-k retrieval returns sensible calculator and existing-repo neighbors
- target encoder supports prompt-intent, request-spec, and existing-repo change
  records
- progress file records metrics and next model/index improvement

## Testing Plan

Run focused checks first:

```bash
pytest tests/test_prompt_jepa.py -q
pytest tests/test_cli.py -q
pytest tests/test_prompt_intents.py -q
git diff --check
python -m py_compile prompt_jepa.py cli/handlers.py cli/parser.py cli/__init__.py
```

Manual smoke:

```bash
python cli.py build-prompt-jepa-index \
  --labels examples/prompt_intents/greenshot_7_intents.jsonl \
  --out /tmp/j3-prompt-jepa-index.json

python -m json.tool /tmp/j3-prompt-jepa-index.json >/dev/null

python cli.py query-prompt-jepa-index \
  --index /tmp/j3-prompt-jepa-index.json \
  --prompt "make me a simple cli calc" \
  --top-k 5
```

Run full `pytest -q` only after broad shared changes or before a final
integration gate.

## Open Decisions

1. Index format name:
   - Proposed: `j3.prompt-jepa-index.v1`.

2. Embedding dimension:
   - Proposed: default `256`, configurable for tests.

3. First retrieval metric:
   - Proposed: top-k match on `expected_action`, `repo_mode`, and `domain`.

4. Production use:
   - Proposed: no production routing until retrieval quality is measured and a
     rollback path exists.

## After This Slice

1. Train a predictor from context embedding to target embedding.
2. Add repo-state context vectors alongside prompt context.
3. Index prompt/spec/action/outcome rows produced by real CLI runs.
4. Use nearest target rows to propose structured candidate actions.
5. Compare retrieval-assisted action selection against the current fixture and
   parser paths.
