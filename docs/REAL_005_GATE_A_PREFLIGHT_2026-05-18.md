# REAL-005 Gate A Live Baseline Preflight

Date: 2026-05-18

## Summary

Live baseline preflight passed for two held-out ladder repositories beyond the
`iniconfig` calibration run from `REAL-004`.

- Repos: `h11`, `humanize`
- Output: `/tmp/j3-real-005-gate-a-preflight/outcomes.jsonl`
- Rows: 4 task rows
- Runtime: 8.047 seconds
- Preflight status: `passed`
- Blocker label: `none`
- Environment blocker label: `none`
- Hosted usage: none

Combined with `REAL-004`, Gate A now has three baseline-passing repositories:
`iniconfig`, `h11`, and `humanize`. That satisfies the Gate A minimum of three
repositories passing baseline validation from clean checkouts. `boltons` was
not needed for this threshold and remains untested by this run.

## Command

The run used an isolated `/tmp` virtualenv so setup dependencies did not change
the shared development environment.

```bash
rm -rf /tmp/j3-real-005-gate-a-preflight
mkdir -p /tmp/j3-real-005-gate-a-preflight
python -m venv /tmp/j3-real-005-gate-a-preflight/.venv
PATH=/tmp/j3-real-005-gate-a-preflight/.venv/bin:$PATH \
  python -m j3.real_repo_preflight \
  --manifest examples/real_repo_eval_ladder.json \
  --repo h11 \
  --repo humanize \
  --work-root /tmp/j3-real-005-gate-a-preflight/repos \
  --outcome /tmp/j3-real-005-gate-a-preflight/outcomes.jsonl
```

CLI summary:

```json
{"blocker_labels": ["none"], "outcome_path": "/private/tmp/j3-real-005-gate-a-preflight/outcomes.jsonl", "preflight_statuses": ["passed"], "repo_ids": ["h11", "humanize"], "row_count": 4, "runtime_seconds": 8.047}
```

## Command Results

Checkout:

| Repo | Command | CWD | Timeout | Return | Status |
| --- | --- | --- | ---: | ---: | --- |
| `h11` | `git clone --no-checkout https://github.com/python-hyper/h11.git /private/tmp/j3-real-005-gate-a-preflight/repos/h11` | `/private/tmp/j3-real-005-gate-a-preflight/repos` | 120 | 0 | `passed` |
| `h11` | `git checkout --detach 62c5068c971579d61fa1b55373390e12f25fd856` | `/private/tmp/j3-real-005-gate-a-preflight/repos/h11` | 120 | 0 | `passed` |
| `humanize` | `git clone --no-checkout https://github.com/python-humanize/humanize.git /private/tmp/j3-real-005-gate-a-preflight/repos/humanize` | `/private/tmp/j3-real-005-gate-a-preflight/repos` | 120 | 0 | `passed` |
| `humanize` | `git checkout --detach bde649fc2927c022dd2a9eedba2a1ed677b97902` | `/private/tmp/j3-real-005-gate-a-preflight/repos/humanize` | 120 | 0 | `passed` |

Setup:

| Repo | Command | CWD | Timeout | Return | Status |
| --- | --- | --- | ---: | ---: | --- |
| `h11` | `python -m pip install -e . -r test-requirements.txt` | `/private/tmp/j3-real-005-gate-a-preflight/repos/h11` | 600 | 0 | `passed` |
| `humanize` | `python -m pip install -e '.[tests]'` | `/private/tmp/j3-real-005-gate-a-preflight/repos/humanize` | 600 | 0 | `passed` |

Baseline validation:

| Repo | Command | CWD | Timeout | Return | Status | Result |
| --- | --- | --- | ---: | ---: | --- | --- |
| `h11` | `python -m pytest h11/tests/test_util.py h11/tests/test_headers.py h11/tests/test_state.py -q` | `/private/tmp/j3-real-005-gate-a-preflight/repos/h11` | 600 | 0 | `passed` | `19 passed in 0.03s` |
| `humanize` | `python -m pytest tests/test_filesize.py tests/test_number.py tests/test_lists.py tests/test_time.py -q --benchmark-disable` | `/private/tmp/j3-real-005-gate-a-preflight/repos/humanize` | 600 | 0 | `passed` | `679 passed in 0.53s` |

## Network Policy

The JSONL rows record the manifest policy:

- Checkout network allowed: `true`
- Setup network allowed: `true`
- Baseline validation network allowed: `false`
- Candidate validation network allowed: `false`
- Description: `network allowed only during clean dependency setup; candidate validation must run offline`

## Task Rows

| Task | Allowed write check | Preflight status | Blocker |
| --- | --- | --- | --- |
| `h11-tests-bytesify-memoryview` | `passed` for `h11/tests/test_util.py` | `passed` | `none` |
| `h11-feature-bytesify-object-message` | `passed` for `h11/_util.py`, `h11/tests/test_util.py` | `passed` | `none` |
| `humanize-tests-naturalsize-negative-strings` | `passed` for `tests/test_filesize.py` | `passed` | `none` |
| `humanize-feature-naturalsize-zero-format` | `passed` for `src/humanize/filesize.py`, `tests/test_filesize.py` | `passed` | `none` |

## Failure Classification

No checkout, setup, baseline validation, or allowed-write preflight failures
occurred. There are no agent-failure labels in this run because no candidate
generation or edit validation was attempted.

## Result

Cheap baseline validation is viable for the first three ladder repositories
tested live. Gate A is satisfied for `iniconfig`, `h11`, and `humanize`; the
next scoring work can rely on those three clean baselines while keeping any
future `boltons` result classified separately if it exposes an environment,
setup, or validation blocker.
