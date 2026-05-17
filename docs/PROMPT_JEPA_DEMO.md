# Prompt-JEPA Developer Demo

This demo is the fast local story for the current GreenShot-7 slice:

```text
expanded coding-agent prompt corpus
  -> local Prompt-JEPA context/target indexes
real calculator implement/change outcome rows
  -> mixed retrieval evidence
generated calculator repo
  -> validation results
generated Python source
  -> deterministic repo-state and source embedding artifacts
prompt + repo_before + structured action
  -> transition target and evaluation-only consequence prediction
```

It does not call a hosted LLM API, does not send repo text to a hosted model,
and does not switch production routing to retrieval-assisted planning or
transition prediction.

## Generate And Inspect The Corpus

The expanded corpus lives outside this repo by default, under the sibling
`../prompts` workspace. Regenerate it from the checked-in tool:

```bash
python tools/prompts/generate_expanded_prompt_corpus.py
```

Inspect its profile and quality checks:

```bash
python cli.py inspect-prompt-corpus \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --json
```

The current expanded demo corpus has 320 rows: 80 `human_seed` rows and 240
`synthetic_template_v0` rows. The inspector reports split counts, task type,
repo mode, domain, expected action, clarification counts, duplicate normalized
prompts, prompt-family split leakage, missing fields, and unsupported scalar
labels.

## Run The Demo

Use a disposable output directory:

```bash
rm -rf /tmp/j3-prompt-jepa-demo

python cli.py demo-prompt-jepa \
  --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl \
  --out /tmp/j3-prompt-jepa-demo \
  --top-k 5
```

The command writes:

```text
/tmp/j3-prompt-jepa-demo/
+-- index.json
+-- labels-index.json
+-- outcomes.jsonl
+-- report.json
+-- source-embeddings.json
+-- transitions.jsonl
+-- transition-model.json
+-- transition-eval.json
+-- repos/simple-calc/
    +-- calculator.py
    +-- request-spec.json
    +-- tests/test_calculator_cli.py
```

`labels-index.json` contains the prompt-label-only index. `index.json` is the
mixed index built from labels plus real `implement --record` and
`change --record` calculator outcome rows. `outcomes.jsonl` records the
calculator create path, the exponent-support change path, and a blocked
clarification path.

`transitions.jsonl`, `transition-model.json`, and `transition-eval.json` are
the Prompt+Repo JEPA transition artifacts. They turn the same demo outcomes
into an explicit state/action/target prediction problem for local evaluation.

## Validate The Report

Check that the report and source sidecar are valid JSON:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null
python -m json.tool /tmp/j3-prompt-jepa-demo/source-embeddings.json >/dev/null
python -m json.tool /tmp/j3-prompt-jepa-demo/transition-model.json >/dev/null
python -m json.tool /tmp/j3-prompt-jepa-demo/transition-eval.json >/dev/null
```

Inspect the report:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/report.json
```

Important report fields:

- `corpus`: row counts, split counts, source types, task types, and domains.
- `indexes`: `labels_index`, `mixed_index`, and their row counts.
- `held_out_retrieval_eval`: evaluation-only retrieval metrics.
- `generated_calculator_results`: supported and blocked calculator outcomes.
- `representative_queries`: nearest evidence for fixed demo prompts.
- `dry_run_proposals`: `prompt-jepa-planner-proposal-v1` records with
  `applies_changes: false`.
- `source_embeddings`: metadata for the source-embedding sidecar.
- `transitions`: transition row/model/eval artifact paths, metrics, residuals,
  schema versions, and `evaluation_only_not_wired_to_production: true`.
- `hosted_llm_api_tokens`: always `0` in this demo.
- `hosted_repo_context_bytes`: always `0` in this demo.

## Prompt+Repo Transition Story

The transition path is the first demo artifact shaped like a small local world
model:

```text
prompt context
  + repo_before state
  + structured action
  -> predicted repo_after embedding or blocked/clarification target
  -> compare against observed repo_after / blocked target
```

`repo-state-v1` is the deterministic Python repo-state encoding used for
`repo_before` and `repo_after`. It records the schema version, Python source
feature version, embedding dimension, included Python file paths, per-file
SHA-256 hashes and byte counts, aggregate metadata, and a mean aggregate repo
embedding. Empty repos are represented with the same schema and a zero repo
embedding, so create-from-empty and no-change blocked rows are comparable.

`prompt-repo-transition-v1` rows are written to `transitions.jsonl`. Each row
contains:

- prompt context and context-embedding checksum
- Prompt-JEPA target summary and target-embedding checksum
- `repo_before` as a `repo-state-v1` record
- `structured_action` such as calculator repo creation, exponent support, or
  blocked clarification
- observed `outcome`, `validation`, and local cost fields
- `repo_after` as a `repo-state-v1` record for source-changing or no-change
  outcomes, or the no-change state for blocked clarification targets

The demo writes three transition rows today: create the simple calculator repo
from an empty repo state, record the blocked auth clarification without source
changes, and add exponent support to the generated calculator repo.

`prompt-repo-transition-predictor-v0` is a tiny deterministic,
evaluation-only predictor. It uses prompt context, repo-before, structured
action, outcome, and validation/status features to predict either a
repo-after embedding target or a blocked/clarification target.

`prompt-repo-transition-eval-v1` is also evaluation-only. It runs
leave-one-out consequence prediction, compares the V0 predictor with a
prompt-only nearest-neighbor baseline, and reports:

- top-1/top-k outcome-kind matches
- top-1/top-k validation-status matches
- source-changing/no-change versus blocked/clarification split counts
- repo-after embedding distance statistics for source-state targets
- residual examples with prompt, action, expected target, predicted target,
  prompt-only neighbor, and distance fields

These artifacts are not wired into `implement`, `change`, or planner routing.
They exist so developers can inspect the state/action/target spaces before any
production planner consumes transition predictions.

## Inspect Artifacts

Query the label-only index:

```bash
python cli.py query-prompt-jepa-index \
  --index /tmp/j3-prompt-jepa-demo/labels-index.json \
  --prompt "make me a simple cli calc" \
  --top-k 5
```

Query the mixed labels-plus-outcomes index:

```bash
python cli.py query-prompt-jepa-index \
  --index /tmp/j3-prompt-jepa-demo/index.json \
  --prompt "add exponent support" \
  --top-k 5
```

Generate an evaluation-only planner proposal from the mixed index:

```bash
python cli.py propose-from-prompt-jepa \
  --index /tmp/j3-prompt-jepa-demo/index.json \
  --prompt "add auth" \
  --top-k 5 \
  --json
```

Inspect the real outcome rows:

```bash
sed -n '1,3p' /tmp/j3-prompt-jepa-demo/outcomes.jsonl
```

Inspect and smoke the generated calculator repo:

```bash
find /tmp/j3-prompt-jepa-demo/repos/simple-calc -maxdepth 3 -type f | sort

python /tmp/j3-prompt-jepa-demo/repos/simple-calc/calculator.py 2 + 3
python /tmp/j3-prompt-jepa-demo/repos/simple-calc/calculator.py 2 '**' 3
python -m pytest /tmp/j3-prompt-jepa-demo/repos/simple-calc/tests -q
```

Inspect the deterministic source embeddings:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/source-embeddings.json
```

`source-embeddings.json` is a sidecar for generated Python files. It records
file paths, byte counts, SHA-256 hashes, embedding lengths, and vectors for
`repos/simple-calc/calculator.py` and
`repos/simple-calc/tests/test_calculator_cli.py`.

The sidecar uses `features.embed_python_source` with feature version
`ast-hash-v1`. These are deterministic AST hash vectors, not neural training
outputs.

Inspect the Prompt+Repo transition rows:

```bash
python - <<'PY'
import json
from pathlib import Path

rows = [
    json.loads(line)
    for line in Path("/tmp/j3-prompt-jepa-demo/transitions.jsonl").read_text().splitlines()
]
print(len(rows), rows[0]["schema_version"])
for row in rows:
    print(row["id"], row["structured_action"]["kind"], row["outcome"]["kind"])
PY
```

Evaluate the transition rows directly:

```bash
python cli.py eval-prompt-repo-transitions \
  --transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl \
  --top-k 3 \
  --json
```

Inspect the persisted transition artifacts:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/transition-model.json
python -m json.tool /tmp/j3-prompt-jepa-demo/transition-eval.json
```

## Supported Boundaries

Supported and validated by this demo:

- Create a simple calculator CLI repo from `make me a simple cli calc`.
- Change that generated calculator repo with `add exponent support`.
- Validate the generated calculator repo with its pytest suite.
- Build and query local Prompt-JEPA indexes.
- Produce dry-run planner proposals for inspection.
- Write deterministic source embeddings for generated Python files.
- Encode generated Python repos as deterministic `repo-state-v1` records.
- Write `prompt-repo-transition-v1` rows for create, change, and blocked
  calculator-demo outcomes.
- Fit and evaluate `prompt-repo-transition-predictor-v0` locally as an
  evaluation-only artifact.

Retrieval/proposal-only in this demo:

- Non-calculator prompts such as
  `build a small todo cli where I can add tasks and mark them done`.
- Any prompt whose nearest evidence is useful for inspection but has no
  structured builder wired into the demo.

Blocked or clarification examples:

- `add auth` is recorded as blocked with a clarification request rather than
  forced into the calculator builder.
- Prompts with nearest `ask_clarification` evidence are evidence only unless a
  supported deterministic production path also validates them.

Current non-goals and constraints:

- No hosted LLM/API calls.
- No repo text sent to a hosted model.
- Hosted LLM/API tokens remain `0`.
- Hosted repo-context bytes remain `0`.
- No model download, GPU requirement, or neural training run.
- No production routing switch. `implement` and `change` still use their
  deterministic request/change parsers and builders.
- No transition predictor routing switch. `prompt-repo-transition-predictor-v0`
  and `prompt-repo-transition-eval-v1` are for inspection and evaluation only.
- No claim that synthetic prompt rows prove broad generalization.
