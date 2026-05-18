# Prompt Corpus Tools

This directory contains checked-in tools for generating local j3 prompt corpora.
The generated JSONL files are written to the sibling `../prompts` workspace by
default so large or experimental corpora do not enter git history by accident.

## Expanded Demo Corpus

Generate the current expanded demo corpus:

```bash
python tools/prompts/generate_expanded_prompt_corpus.py
```

Default inputs and outputs:

```text
../prompts/coding_agent_prompts_seed.jsonl
../prompts/coding_agent_prompts_expanded_v0.jsonl
```

The generated rows are synthetic template rows. They are marked with:

- `source_type: synthetic_template_v0`
- `tags` containing `synthetic` and `prompt-corpus-template-v0`
- `prompt_family`
- `generation.generated_by: codex`
- `generation.template_version: prompt-corpus-template-v0`
- `generation.review_status: unreviewed_synthetic`

The checked-in generator plus the seed JSONL are the reproducible recipe. A
developer with the same seed file can regenerate byte-stable output. The
runtime j3 demo still uses zero hosted LLM calls; Codex assistance here is
only for bootstrapping the corpus artifact.

## Current Policy

- Stop the current slice at 320 rows.
- Add a corpus quality/profile gate before generating more synthetic rows.
- Keep unreviewed scratch corpora in `../prompts`.
- Later, move a small reviewed demo corpus into `examples/prompt_intents/` if it
  should be part of the public clone-and-test path.
- Publish larger corpora as versioned archives with manifests and checksums.

## Quality Audit

Profile the expanded corpus before using it for prompt/model claims:

```bash
python cli.py inspect-prompt-corpus --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl
python cli.py inspect-prompt-corpus --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl --json
```

The JSON profile includes source/split/task/domain counts, clarification and
ambiguity counts, inferred defaults, synthetic template families, cross-split
duplicate and near-duplicate risks, schema variants, unsupported scalar labels,
and fields the next schema validator should enforce.

## Schema Validation

Validate the current prompt/spec row schema before using a corpus for learned
prompt or transition-model work:

```bash
python cli.py validate-prompt-corpus --labels ../prompts/coding_agent_prompts_seed.jsonl
python cli.py validate-prompt-corpus --labels ../prompts/coding_agent_prompts_expanded_v0.jsonl
python cli.py validate-prompt-corpus --labels examples/prompt_intents/greenshot_7_intents.jsonl
```

The validator fails on missing required fields, unsupported scalar labels,
invalid expected-field types, unsupported expected actions, duplicate ids, exact
cross-split prompt duplicates, and missing synthetic provenance. Cross-split
near-duplicates are reported as review warnings by default; use
`--fail-on-review` when a cleanup gate should treat them as fatal.
