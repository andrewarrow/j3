# Training Data

This document describes the external Python corpus used for `j3` repair
training and how another developer can reproduce it.

The current corpus lives outside this repository at:

```text
/Users/aa/os/python-apache
```

It contains public GitHub repositories selected as an Apache-2.0-licensed
Python corpus for local `j3` repair training.

## Selection Rules

Selection rules used on May 16, 2026:

- public GitHub repository
- primary language: Python
- GitHub license endpoint reports SPDX `Apache-2.0`
- enough source and/or tests to be useful for repair training
- avoid repos that are mostly lists, course material, payload catalogs, model
  weights, docs, generated examples, or thin release wrappers
- cloned with recent history using `git clone --depth 50 --single-branch`

The corpus is intentionally small enough to run locally:

```text
repos cloned: 31
Python files: 10,208
test files: 2,729
disk use: about 630 MB
```

## How The Repos Were Found

The first pass used GitHub CLI search for popular, public, non-archived Python
repositories with Apache-2.0 license metadata:

```bash
gh search repos \
  --language Python \
  --license apache-2.0 \
  --archived=false \
  --visibility public \
  --stars '>5000' \
  --size '<50000' \
  --sort stars \
  --limit 120 \
  --json fullName,description,license,stargazersCount,language,size,forksCount,pushedAt,url
```

That search output was manually filtered for repositories likely to provide
useful repair-training signal: libraries, frameworks, tools, and applications
with real implementation code and meaningful tests. Repositories with weak
local source/test value were skipped even when popular.

Because GitHub search metadata and repository license metadata can disagree,
the final inclusion check used GitHub's repository license endpoint:

```bash
gh api repos/psf/requests/license --jq '.license.spdx_id'
```

Only repos returning `Apache-2.0` from that endpoint were cloned. Candidates
returning `NOASSERTION`, no license, or any other SPDX value are not part of
this corpus.

## Recreate The Corpus

Create the target directory:

```bash
mkdir -p /Users/aa/os/python-apache
cd /Users/aa/os/python-apache
```

Create `repos-to-clone.txt`:

```text
psf/requests
openai/openai-python
tornadoweb/tornado
google/yapf
aws/chalice
simonw/datasette
simonw/llm
dgtlmoon/changedetection.io
reflex-dev/reflex
Chainlit/chainlit
darrenburns/posting
ranaroussi/yfinance
spotify/luigi
treeverse/dvc
bloomberg/memray
plasma-umass/scalene
microsoft/playwright-python
cleanlab/cleanlab
ludwig-ai/ludwig
huggingface/smolagents
huggingface/peft
huggingface/trl
huggingface/pytorch-image-models
google/langextract
getzep/graphiti
vibrantlabsai/ragas
Lightning-AI/litgpt
Netflix/metaflow
facebookresearch/detectron2
dmlc/dgl
boto/boto3
```

Verify each repo's license before cloning and keep the result:

```bash
printf 'repo\tspdx\n' > license-check.tsv

while read -r repo; do
  [ -n "$repo" ] || continue
  spdx=$(gh api "repos/$repo/license" --jq '.license.spdx_id' 2>/dev/null || echo NO_LICENSE)
  printf '%s\t%s\n' "$repo" "$spdx" >> license-check.tsv
done < repos-to-clone.txt

awk 'NR > 1 && $2 != "Apache-2.0" { bad = 1; print } END { exit bad }' license-check.tsv
```

Clone the repos into stable local directory names:

```bash
while read -r repo; do
  [ -n "$repo" ] || continue
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

Verify the final local shape:

```bash
find /Users/aa/os/python-apache -mindepth 1 -maxdepth 1 -type d -name '*__*' | wc -l
awk 'NR > 1 { count[$2]++ } END { for (spdx in count) print spdx, count[spdx] }' license-check.tsv
awk 'NR > 1 { py += $2; tests += $3 } END { printf "py_files\t%d\ntest_files\t%d\n", py, tests }' corpus-summary.tsv
du -sh /Users/aa/os/python-apache
```

Expected output for the May 16, 2026 corpus:

```text
repos: 31
license: Apache-2.0 31
Python files: 10,208
test files: 2,729
disk use: about 630 MB
```

## Train From This Corpus

From the `j3` repo:

```bash
cd /Users/aa/os/j3
paths=($(find /Users/aa/os/python-apache -maxdepth 1 -type d -name '*__*' | sort))

python3 cli.py train \
  --data $paths \
  --out runs/apache-python-10k \
  --max-examples 10000 \
  --embedding-dim 256
```

Resulting artifacts:

```text
runs/apache-python-10k/model.json
runs/apache-python-10k/metrics.json
runs/apache-python-10k/examples.jsonl
```

## Mine Real Git Transitions

The synthetic corpus is useful, but real repository history is the next better
training signal. `j3 mine` extracts Python file before/after pairs from recent
git commits:

```bash
python3 cli.py mine \
  --repo /Users/aa/os/python-apache/psf__requests \
  --out data/transitions/apache-python/psf__requests.jsonl \
  --max-commits 25 \
  --max-files-per-commit 8
```

To mine the full local corpus:

```bash
mkdir -p data/transitions/apache-python

for repo in /Users/aa/os/python-apache/*__*; do
  [ -d "$repo/.git" ] || continue
  name=${repo##*/}
  python3 cli.py mine \
    --repo "$repo" \
    --out "data/transitions/apache-python/$name.jsonl" \
    --max-commits 25 \
    --max-files-per-commit 8
done
```

Train with both synthetic transitions and mined git transitions:

```bash
paths=($(find /Users/aa/os/python-apache -maxdepth 1 -type d -name '*__*' | sort))

python3 cli.py train \
  --data $paths \
  --transitions data/transitions/apache-python \
  --out runs/apache-python-git \
  --max-examples 10000 \
  --embedding-dim 256
```

Resulting artifacts:

```text
runs/apache-python-git/model.json
runs/apache-python-git/metrics.json
runs/apache-python-git/examples.jsonl
```

## Evaluate The Corpus Model

Run GreenShot-2 against the trained model:

```bash
python3 cli.py eval \
  --tasks examples/greenshot_bugs \
  --checkpoint runs/apache-python-git/model.json \
  --timeout 10
```
