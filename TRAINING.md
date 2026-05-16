# Training Data

This document describes the first external Python corpus used for `j3` training
and how another developer can reproduce it.

The current corpus lives outside this repository at:

```text
/Users/aa/os/python
```

It contains public GitHub repositories selected as an MIT-licensed Python corpus
for local `j3` repair training.

## Selection Rules

Selection rules used on May 16, 2026:

- public GitHub repository
- primary language: Python
- GitHub license endpoint reports SPDX `MIT`
- enough source and/or tests to be useful for repair training
- cloned with recent history using `git clone --depth 50 --single-branch`

The corpus is intentionally small enough to run locally:

```text
repos cloned: 31
Python files: 8,261
test files: 3,475
disk use: about 394 MB
```

## How The Repos Were Found

The first pass used GitHub CLI search for popular, public, non-archived Python
repositories with MIT license metadata:

```bash
gh search repos \
  --language Python \
  --license mit \
  --archived=false \
  --visibility public \
  --stars '>1000' \
  --size '<50000' \
  --sort stars \
  --limit 80 \
  --json fullName,description,license,stargazersCount,language,size,forksCount,pushedAt,url
```

That search output was manually filtered to avoid repos that are mostly lists,
payload catalogs, model weights, docs, or examples without useful tests.

Because GitHub search metadata and repository license metadata can disagree, the
final inclusion check used GitHub's repository license endpoint:

```bash
gh api repos/psf/black/license --jq '.license.spdx_id'
```

Only repos returning `MIT` from that endpoint were cloned. Candidates returning
`NOASSERTION` were skipped for this first corpus.

## Recreate The Corpus

Create the target directory:

```bash
mkdir -p /Users/aa/os/python
cd /Users/aa/os/python
```

Create `repos-to-clone.txt`:

```text
psf/black
python-poetry/poetry
Delgan/loguru
modelcontextprotocol/python-sdk
openai/openai-agents-python
magic-wormhole/magic-wormhole
chriskiehl/Gooey
Textualize/rich
fastapi/fastapi
fastapi/typer
PyCQA/isort
pytest-dev/pytest
tox-dev/tox
python-attrs/attrs
pypa/pip
sqlalchemy/sqlalchemy
sqlalchemy/alembic
locustio/locust
ArchiveBox/ArchiveBox
9001/copyparty
nvbn/thefuck
openai/whisper
karpathy/nanoGPT
karpathy/minGPT
eriklindernoren/ML-From-Scratch
lucidrains/vit-pytorch
openai/swarm
microsoft/markitdown
github/spec-kit
browser-use/browser-use
agronholm/apscheduler
```

Verify each repo's license before cloning:

```bash
while read -r repo; do
  spdx=$(gh api "repos/$repo/license" --jq '.license.spdx_id' 2>/dev/null || echo NO_LICENSE)
  printf '%s\t%s\n' "$repo" "$spdx"
done < repos-to-clone.txt
```

Clone the repos into stable local directory names:

```bash
while read -r repo; do
  dir=${repo//\//__}
  git clone --depth 50 --single-branch "https://github.com/$repo.git" "$dir"
done < repos-to-clone.txt
```

Generate a local corpus summary:

```bash
printf 'repo_dir\tpy_files\ttest_files\tcommits_depth\tdisk\n' > corpus-summary.tsv

for dir in */.git; do
  repo_dir=${dir%/.git}
  py_files=$(find "$repo_dir" -path '*/.git' -prune -o -type f -name '*.py' -print | wc -l | tr -d ' ')
  test_files=$(find "$repo_dir" -path '*/.git' -prune -o -type f \( -name 'test_*.py' -o -name '*_test.py' -o -path '*/tests/*.py' \) -print | wc -l | tr -d ' ')
  commits=$(git -C "$repo_dir" rev-list --count HEAD 2>/dev/null || echo 0)
  disk=$(du -sh "$repo_dir" | awk '{print $1}')
  printf '%s\t%s\t%s\t%s\t%s\n' "$repo_dir" "$py_files" "$test_files" "$commits" "$disk" >> corpus-summary.tsv
done
```

## Train From This Corpus

From the `j3` repo:

```bash
cd /Users/aa/os/j3
paths=($(find /Users/aa/os/python -maxdepth 1 -type d -name '*__*' | sort))
python3 cli.py train \
  --data $paths \
  --out runs/mit-python-10k \
  --max-examples 10000 \
  --embedding-dim 256
```

The first training run produced:

```text
source files: 8254
synthetic transitions: 10000
actions:
  change_literal: 6128
  change_operator: 772
  change_return_value: 49
  modify_condition: 2217
  replace_expr: 834
```

Resulting artifacts:

```text
runs/mit-python-10k/model.json
runs/mit-python-10k/metrics.json
runs/mit-python-10k/examples.jsonl
```

## Mine Real Git Transitions

The synthetic corpus is useful, but real repository history is the next better
training signal. `j3 mine` extracts Python file before/after pairs from recent
git commits:

```bash
python3 cli.py mine \
  --repo /Users/aa/os/python/psf__black \
  --out data/transitions/psf__black.jsonl \
  --max-commits 25 \
  --max-files-per-commit 8
```

To mine the full local corpus:

```bash
mkdir -p data/transitions

for repo in /Users/aa/os/python/*__*; do
  [ -d "$repo/.git" ] || continue
  name=${repo##*/}
  python3 cli.py mine \
    --repo "$repo" \
    --out "data/transitions/$name.jsonl" \
    --max-commits 25 \
    --max-files-per-commit 8
done
```

The first bounded mining run produced:

```text
repos mined: 31
real Python file transitions: 1,396
```

Train with both synthetic transitions and mined git transitions:

```bash
paths=($(find /Users/aa/os/python -maxdepth 1 -type d -name '*__*' | sort))

python3 cli.py train \
  --data $paths \
  --transitions data/transitions \
  --out runs/mit-python-git \
  --max-examples 10000 \
  --embedding-dim 256
```

The combined run produced:

```text
source files: 8254
examples: 11396
mined transitions: 1396
actions:
  change_literal: 6128
  change_operator: 772
  change_return_value: 49
  git_transition: 1396
  modify_condition: 2217
  replace_expr: 834
```

Resulting artifacts:

```text
runs/mit-python-git/model.json
runs/mit-python-git/metrics.json
runs/mit-python-git/examples.jsonl
```

## Evaluate The Corpus Model

Run GreenShot-2 against the trained model:

```bash
python3 cli.py eval \
  --tasks examples/greenshot_bugs \
  --checkpoint runs/mit-python-10k/model.json \
  --timeout 10
```

Observed result:

```text
baseline: solved=5/5 pass@1=1/5 avg_candidates=21.80
model-ranked: solved=5/5 pass@1=0/5 avg_candidates=16.80
```

The current prototype model reduces average search but does not improve pass@1
yet. That is expected: the current trainer uses synthetic transitions and a
prototype latent action-delta scorer, not a neural JEPA model.

The combined synthetic plus git-transition model currently produces the same
GreenShot-2 metrics. That means the data path works, but the prototype scorer is
too shallow to benefit from real commit history yet. The next modeling step is a
trainable encoder/ranker that can learn from the `git_transition` examples
instead of only averaging action deltas.

## Full Repository URLs

- https://github.com/psf/black
- https://github.com/python-poetry/poetry
- https://github.com/Delgan/loguru
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/openai/openai-agents-python
- https://github.com/magic-wormhole/magic-wormhole
- https://github.com/chriskiehl/Gooey
- https://github.com/Textualize/rich
- https://github.com/fastapi/fastapi
- https://github.com/fastapi/typer
- https://github.com/PyCQA/isort
- https://github.com/pytest-dev/pytest
- https://github.com/tox-dev/tox
- https://github.com/python-attrs/attrs
- https://github.com/pypa/pip
- https://github.com/sqlalchemy/sqlalchemy
- https://github.com/sqlalchemy/alembic
- https://github.com/locustio/locust
- https://github.com/ArchiveBox/ArchiveBox
- https://github.com/9001/copyparty
- https://github.com/nvbn/thefuck
- https://github.com/openai/whisper
- https://github.com/karpathy/nanoGPT
- https://github.com/karpathy/minGPT
- https://github.com/eriklindernoren/ML-From-Scratch
- https://github.com/lucidrains/vit-pytorch
- https://github.com/openai/swarm
- https://github.com/microsoft/markitdown
- https://github.com/github/spec-kit
- https://github.com/browser-use/browser-use
- https://github.com/agronholm/apscheduler
