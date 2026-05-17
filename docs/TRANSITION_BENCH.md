# Transition Bench And Action Selection V1

This document covers the reproducible Transition Bench demo, the boundary
between checked-in fixtures and ignored local data, the checked-in artifact
schemas, the current product modes, and the expected shape of a future release
package.

The benchmark and scorer artifacts are local-only. They do not call hosted LLM
APIs and do not send repository text to hosted models. Production defaults
remain conservative: `implement`, `change`, `patch`, and `fix` keep their
deterministic routing. Only `patch` and `eval` currently expose explicit
transition-scorer shadow advice or guarded ranking flags.

## Product Modes

Transition scoring currently has four product modes. The modes are deliberately
separate so benchmark evidence can improve without silently changing repair
behavior.

### Demo Mode

Demo mode is the default `demo-transition-bench` path over the tiny checked-in
fixtures:

```bash
python cli.py demo-transition-bench \
  --embedding-dim 8 \
  --top-k 1 \
  --out /tmp/j3-transition-bench-report.json
```

It proves that a clean checkout can normalize transition rows, build repair
action-choice groups, score candidates, emit product-readiness gates, and report
zero hosted usage. It is intentionally small; it is not evidence that a scorer
should affect real repair routing.

### Benchmark Mode

Benchmark mode runs the same report over explicit local artifacts, usually with
`--no-fixtures`, local `runs/**/candidate-outcomes.jsonl`, and optionally mined
`data/transitions/**/*.jsonl`:

```bash
python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-candidates-report.json
```

The report includes skipped-row accounting, normalized row counts, action-choice
metrics, V1 and V2 scorer metrics, baselines, calibration metadata, held-out V2
validation metrics, and `product_readiness`. Mined git rows with empty
`before_source` or `after_source` are skipped with structured records instead
of crashing the report. Each skipped row records the source file, row index,
reason, source kind, repo, file path, and commit when available.

`product_readiness` compares the scorer against `existing-rank-order` on solved
action-choice groups. It reports pass@1 delta, top-k delta, MRR delta, average
candidates validated before first pass, residual counts, and one gate result:

- `not_ready_underperforms_existing_rank_order`
- `ready_for_shadow_mode`
- `ready_for_guarded_opt_in`

The V2 scorer is calibrated from local candidate outcomes with deterministic
local features and a held-out split. It is still evidence, not a production
default. A full-bench improvement is not enough; guarded routing requires a
passing product gate, including held-out validation when that report is present.

### Shadow Mode

Shadow mode scores the real repair candidate set that `patch` or `eval` already
generated, but it does not reorder candidates and does not change the selected
patch. Use it to collect advice rows during normal planning:

```bash
python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-shadow \
  --transition-advice-out /tmp/j3-transition-advice.jsonl
```

The same flags are available through `eval` for evaluation runs. The advice
JSONL records the repo-state summary, candidate count, existing selected
candidate, scorer top candidate, agreement with existing rank order, validation
comparison when known, and zero hosted usage fields. Shadow mode is the right
place to inspect regressions because production routing remains unchanged.

### Guarded Opt-In Mode

Guarded mode is explicit and non-default. It is enabled with
`--transition-scorer-rank`, and it requires either a scorer report whose
`product_readiness` objects all allow `ready_for_guarded_opt_in`, or the
intentional experimental escape hatch `--allow-experimental-ranking`:

```bash
python cli.py patch \
  --repo examples/greenshot_bug \
  --test tests/test_calculator.py \
  --transition-scorer-rank \
  --transition-scorer-report /tmp/j3-transition-bench-candidates-report.json
```

If the report contains a failed gate such as
`not_ready_underperforms_existing_rank_order`, planning is refused before
candidate generation. When ranking is allowed, the CLI prints the gate, report
path, and mode so the run is visibly opt-in. The default `patch` and `fix`
paths still do not use transition-scorer ranking.

### Why Defaults Stay Conservative

The current product boundary is intentional. The checked-in fixture demo can
pass because it is tiny. Local candidate benches can show different behavior
from fixture results, and held-out validation can still underperform the
existing rank order. A coding agent should not replace a deterministic repair
heuristic with a scorer until the scorer is robust on messy local artifacts,
beats the existing baseline on honest held-out evidence, and leaves a clear
audit trail. Until then, benchmark, shadow, and guarded modes provide evidence
without changing default production behavior.

## What Is Checked In

The tiny fixture demo lives under:

```text
examples/transition_bench/
+-- prompt_repo_transitions.jsonl
+-- mined_git_transitions.jsonl
+-- candidate_outcomes.jsonl
```

Those files are intentionally small. They let another developer run the demo,
exercise the schemas, and verify the local action-scoring report in a clean
checkout without private local data, network access, GPUs, model downloads, or
hosted APIs.

The fixture demo currently normalizes four `transition-bench-v1` rows:

- one `prompt_repo_transition` row
- one `mined_git_transition` row
- two `candidate_outcome` rows

The two candidate outcomes form one `transition-action-choice-v1` group with
one passing candidate and one hard negative.

## What Is Ignored

These paths are intentionally ignored by git:

```text
data/
runs/
```

They may contain useful local development evidence, but they are not repository
source:

- mined git transition JSONL datasets such as
  `data/transitions/apache-python/*.jsonl`
- generated training examples such as `runs/*/examples.jsonl`
- generated candidate outcome files such as
  `runs/*/*candidate-outcomes.jsonl`
- trained local prototype models and metrics under `runs/`
- large report directories and generated demo artifacts

Do not commit generated JSONL datasets or large run artifacts. Check in code,
tests, fixtures, manifests, and reproduction instructions instead.

Missing `data/` and `runs/` is normal in a clean checkout. The inventory command
reports missing ignored assets as an ordinary condition, not an error.

## Reproduce The Checked-In Fixture Demo

From the repository root:

```bash
python cli.py inspect-transition-assets --json

python cli.py demo-transition-bench \
  --embedding-dim 8 \
  --top-k 1 \
  --out /tmp/j3-transition-bench-report.json

python -m json.tool /tmp/j3-transition-bench-report.json >/dev/null
```

The first command emits a `transition-asset-inventory-v1` manifest for the
current checkout and any local ignored assets that happen to exist.

The second command uses the checked-in fixtures by default, writes a
`transition-bench-demo-report-v1` JSON report, and prints the same core metrics
in human-readable form:

- transition bench row count
- action-choice group count
- candidate count
- pass@1
- top-k pass rate
- mean reciprocal rank
- average candidates validated before first pass
- local runtime
- hosted LLM/API usage fields, all zero
- hosted repo-context bytes, zero

To write the inventory manifest as a file:

```bash
python cli.py inspect-transition-assets \
  --out /tmp/j3-transition-assets.json \
  --json

python -m json.tool /tmp/j3-transition-assets.json >/dev/null
```

## Optional Local-Data Demo

If this workspace has mined transitions and GreenShot candidate outcomes under
ignored `data/` and `runs/`, run the same demo with those files included:

```bash
python cli.py demo-transition-bench \
  --embedding-dim 256 \
  --top-k 3 \
  --mined-transitions data/transitions/apache-python/*.jsonl \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-report.json

python -m json.tool /tmp/j3-transition-bench-local-report.json >/dev/null
```

If you already produced Prompt+Repo transition rows with
`demo-prompt-jepa`, include them too:

```bash
python cli.py demo-transition-bench \
  --embedding-dim 256 \
  --top-k 3 \
  --prompt-repo-transitions /tmp/j3-prompt-jepa-demo/transitions.jsonl \
  --mined-transitions data/transitions/apache-python/*.jsonl \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-report.json
```

Use `--no-fixtures` when you want a report over only explicit local files:

```bash
python cli.py demo-transition-bench \
  --no-fixtures \
  --embedding-dim 256 \
  --top-k 3 \
  --candidate-outcomes runs/apache-python-git/*candidate-outcomes.jsonl \
  --out /tmp/j3-transition-bench-local-only-report.json
```

These commands still use local deterministic code only. They do not require
hosted LLM/API usage.

## Schema Summary

All artifacts are plain JSON or JSONL.

### `transition-asset-inventory-v1`

Produced by `inspect-transition-assets`.

Useful fields:

- `repo_root`: inspected repository root.
- `prompt_corpus`: prompt corpus path, presence, size, row count, and SHA-256.
- `prompt_repo_demo_artifacts`: discovered Prompt+Repo demo directories and
  artifacts such as `report.json`, `transitions.jsonl`,
  `transition-model.json`, and `transition-eval.json`.
- `mined_git_transitions`: JSONL files under `data/transitions/**`, with row
  counts and SHA-256 checksums.
- `candidate_outcomes`: `*candidate-outcomes.jsonl` files under `runs/**`, with
  row counts and SHA-256 checksums.
- `prototype_models`: local `runs/**/model.json` files and readable metadata.
- `totals`: row and file totals for quick comparison.
- `notes`: reminders that missing ignored assets are normal and generated data
  should stay out of git.

### `transition-bench-v1`

Produced internally by `demo-transition-bench` from three source shapes:

- `prompt-repo-transition-v1` demo rows
- mined git transition rows with `kind: "git_transition"`
- repair candidate outcome rows

Common surface:

- `id`: stable normalized row id.
- `source`: source kind, row index, source path, source row id, and source
  schema when available.
- `identity`: source-specific repo, task, file, commit, or outcome identity.
- `before`: repo-state or file-source context plus local embedding fields.
- `context`: prompt, git diff, or candidate diagnostic context.
- `action`: structured action or candidate action record.
- `target`: after-state, after-source, validation target, or unavailable
  target marker depending on source kind.
- `validation`: availability, status, pass/fail, and source details.
- `cost`: local bytes and validation counts plus zero hosted usage fields.

### `transition-action-choice-v1`

Built from validated repair candidate outcome rows.

Useful fields:

- `source`: source JSONL path, row indices, and row count.
- `grouping`: task, phase, task family, split, language, and repair-plan
  identity.
- `candidate_count` and `validated_candidate_count`.
- `first_passing_index`: rank of the first passing candidate, or `null`.
- `passing_candidate_ranks`: all passing candidate ranks.
- `hard_negative_candidate_ranks`: failed validated candidates that were still
  plausible enough to validate.
- `candidates`: ranked candidate action records with source context, target
  context, candidate-after evidence when available, and validation details.

The grouping code uses an explicit repair-plan id when present. Existing
candidate outcome rows may lack that id, so the fallback identity is derived
from stable task/phase/source fields and the source path.

### `transition-action-scoring-eval-v1`

Produced by the evaluation-only scorer.

Useful fields:

- `scorer.name`: default scorer, currently
  `transition-action-future-scorer-v1`.
- `scorer.feature_version`: default local feature version.
- `top_k`, `group_count`, `solved_group_count`, and `candidate_count`.
- `metrics`: scorer metrics plus baselines:
  `existing-rank-order`, `stable-lexical-order`, and
  `deterministic-random-order`. When V2 calibration is available, metrics also
  include `transition-action-future-scorer-v2`.
- `calibration`: V2 calibration metadata, including split shape, training
  parameters, training group/pair counts, model weights, validation metrics,
  and validation `product_readiness`.
- `residual_examples`: solved groups where the scorer did not put a passing
  candidate first.
- `runtime`: local runtime and zero hosted token/context fields.

Metrics include pass@1, top-k pass rate, mean reciprocal rank, average first
passing rank, average candidates validated before/to first pass, and average
candidates saved versus existing rank order.

The V2 scorer is evaluation-only. It fits pairwise weights from local candidate
outcome groups and supports held-out validation splits by `task_family` or
`source_file`.

### `transition-bench-demo-report-v1`

Produced by `demo-transition-bench`.

Useful fields:

- `decision`: currently `evaluation_only_not_wired_to_production`.
- `uses_checked_in_fixtures`: whether the tiny fixture sources were included.
- `parameters`: `top_k`, `embedding_dim`, and `residual_limit`.
- `asset_inventory`: compact inventory totals for context.
- `sources`: exact source files and row counts included in the report.
- `transition_bench`: input, normalized, and skipped row counts by source kind,
  plus structured `skipped_rows` and per-input normalization records.
- `action_choices`: group, candidate, and solved group counts.
- `action_scoring`: nested `transition-action-scoring-eval-v1` report.
- `product_readiness`: top-level product gate comparing the default scorer to
  `existing-rank-order` on solved action-choice groups.
- `runtime`: local runtime and zero hosted token/context fields.

The report `decision` remains evaluation-only even when the same scorer is used
elsewhere in shadow or guarded opt-in mode. Routing changes are controlled by
the `patch` and `eval` CLI flags, not by generating this report.

## Future Release Packaging

A future release should keep generated data out of git while still giving
developers enough information to rebuild or verify the artifacts.

Expected release contents:

- `manifest.json`: release-level name, version, git commit, created time,
  schema versions, command lines, and environment notes.
- `checksums.sha256`: SHA-256 checksums for every packaged artifact.
- `transition-assets.json`: `transition-asset-inventory-v1` manifest produced
  by `inspect-transition-assets`.
- `transition-bench-report.json`: `transition-bench-demo-report-v1` produced by
  `demo-transition-bench`.
- optional artifact zip containing generated benchmark JSONL/report files from
  ignored `data/` and `runs/` sources.
- a short `REPRODUCE.md` with the exact commands used to rebuild the report
  from either checked-in fixtures or local/public corpus inputs.

The release package may include generated artifacts, but the git repository
should continue to include only source, tests, tiny fixtures, manifests, and
docs. Another developer should be able to verify a release without hosted
LLM/API usage by:

```bash
shasum -a 256 -c checksums.sha256
python -m json.tool transition-assets.json >/dev/null
python -m json.tool transition-bench-report.json >/dev/null
python cli.py inspect-transition-assets --json
python cli.py demo-transition-bench \
  --embedding-dim 8 \
  --top-k 1 \
  --out /tmp/j3-transition-bench-report.json
```

For a local/public rebuild with larger ignored assets, the release notes should
name the exact source corpus, mining commands, candidate-outcome generation
commands, and `demo-transition-bench` inputs. The invariant is that rebuild and
verification remain local and deterministic from already available files.
