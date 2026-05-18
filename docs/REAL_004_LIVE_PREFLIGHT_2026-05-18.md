# REAL-004 Live Real-Repo Baseline Preflight

Date: 2026-05-18

## Summary

The `REAL-002` preflight runner passed a live checkout/setup/baseline run for
the `iniconfig` calibration repository from `examples/real_repo_eval_ladder.json`.
This validates the harness path for one pinned real checkout before depending on
real-repo scoring claims.

- Repo: `iniconfig`
- Split: `calibration`
- Ref: `77db208ab4ae0cd2061d909fe222a1db72867850`
- Output: `/tmp/j3-real-004-live-preflight/outcomes.jsonl`
- Rows: 2 task rows
- Runtime: 3.119 seconds
- Preflight status: `passed`
- Blocker label: `none`
- Environment blocker label: `none`
- Hosted usage: none

## Command

The run used an isolated `/tmp` virtualenv so the manifest setup command could
install dependencies without changing the shared environment.

```bash
rm -rf /tmp/j3-real-004-live-preflight
mkdir -p /tmp/j3-real-004-live-preflight
python -m venv /tmp/j3-real-004-live-preflight/.venv
PATH=/tmp/j3-real-004-live-preflight/.venv/bin:$PATH \
  python -m j3.real_repo_preflight \
  --manifest examples/real_repo_eval_ladder.json \
  --repo iniconfig \
  --work-root /tmp/j3-real-004-live-preflight/repos \
  --outcome /tmp/j3-real-004-live-preflight/outcomes.jsonl
```

CLI summary:

```json
{"blocker_labels": ["none"], "outcome_path": "/private/tmp/j3-real-004-live-preflight/outcomes.jsonl", "preflight_statuses": ["passed"], "repo_ids": ["iniconfig"], "row_count": 2, "runtime_seconds": 3.119}
```

Environment note: an initial harness-prep attempt with `python3 -m venv` failed
before the runner started because local `python3` resolved to Python 3.14.4 and
`ensurepip` exited nonzero. The recorded live run used `python` 3.11.15 and
completed successfully, so this is not a repo preflight blocker.

## Command Results

Checkout:

| Command | CWD | Timeout | Return | Status |
| --- | --- | ---: | ---: | --- |
| `git clone --no-checkout https://github.com/pytest-dev/iniconfig.git /private/tmp/j3-real-004-live-preflight/repos/iniconfig` | `/private/tmp/j3-real-004-live-preflight/repos` | 120 | 0 | `passed` |
| `git checkout --detach 77db208ab4ae0cd2061d909fe222a1db72867850` | `/private/tmp/j3-real-004-live-preflight/repos/iniconfig` | 120 | 0 | `passed` |

Setup:

| Command | CWD | Timeout | Return | Status |
| --- | --- | ---: | ---: | --- |
| `python -m pip install -e . pytest` | `/private/tmp/j3-real-004-live-preflight/repos/iniconfig` | 600 | 0 | `passed` |

Baseline validation:

| Command | CWD | Timeout | Return | Status | Result |
| --- | --- | ---: | ---: | --- | --- |
| `python -m pytest testing -q` | `/private/tmp/j3-real-004-live-preflight/repos/iniconfig` | 600 | 0 | `passed` | `49 passed in 0.03s` |

The checkout was verified at:

```text
77db208ab4ae0cd2061d909fe222a1db72867850
```

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
| `iniconfig-tests-parse-comments` | `passed` for `testing/test_iniconfig.py` | `passed` | `none` |
| `iniconfig-feature-section-default` | `passed` for `src/iniconfig/__init__.py`, `testing/test_iniconfig.py` | `passed` | `none` |

## Result

The runner survived a real pinned checkout, dependency setup, and baseline
validation for the calibration repository. This proves the live path for one
repo but does not satisfy Gate A by itself; the ladder still needs at least
three repositories passing baseline validation before broad scoring claims are
trustworthy.
