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
