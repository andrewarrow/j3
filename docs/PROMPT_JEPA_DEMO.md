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
  -> deterministic source embedding sidecar
```

It does not call a hosted LLM API, does not send repo text to a hosted model,
and does not switch production routing to retrieval-assisted planning.

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

## Validate The Report

Check that the report and source sidecar are valid JSON:

```bash
python -m json.tool /tmp/j3-prompt-jepa-demo/report.json >/dev/null
python -m json.tool /tmp/j3-prompt-jepa-demo/source-embeddings.json >/dev/null
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
- `hosted_llm_api_tokens`: always `0` in this demo.
- `hosted_repo_context_bytes`: always `0` in this demo.

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

## Supported Boundaries

Supported and validated by this demo:

- Create a simple calculator CLI repo from `make me a simple cli calc`.
- Change that generated calculator repo with `add exponent support`.
- Validate the generated calculator repo with its pytest suite.
- Build and query local Prompt-JEPA indexes.
- Produce dry-run planner proposals for inspection.
- Write deterministic source embeddings for generated Python files.

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
- No model download, GPU requirement, or neural training run.
- No production routing switch. `implement` and `change` still use their
  deterministic request/change parsers and builders.
- No claim that synthetic prompt rows prove broad generalization.
