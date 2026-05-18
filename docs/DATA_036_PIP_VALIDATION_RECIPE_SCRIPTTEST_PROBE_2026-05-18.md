# DATA-036 Pip Validation Recipe Scripttest Probe

Pre-edit validation evidence only; no candidate source edits were attempted.

## Result

- Replay: `pypa__pip-issue-12018-pr-13886`
- Repo-before ref: `8df7b668b3766e1d4a71246509d64aeec47a805b`
- Setup adjustment tested: `python -m pip install -e . installer scripttest`
- Dependencies added: `installer`, `scripttest`
- Validation command: `pytest tests/functional/test_install_reqs.py -q`
- Runtime: `4.758` seconds for the row; `4.812` seconds batch runtime
- Status: `blocked`
- First failed stage: `validation`
- Command classification: `dependency_fixture_setup_failure`
- Evidence acquisition status: `blocked_on_validation_recipe`

Adding `scripttest` removes the DATA-032 missing import blocker. The same
bounded validation command now fails while pytest processes pip's configured
socket options from `pyproject.toml`:

```text
pytest: error: unrecognized arguments: --disable-socket --allow-unix-socket --allow-hosts=localhost
```

The next explicit fixture/tooling dependency is `pytest-socket`. This task stops
there rather than chasing another dependency in the chain.

## Command Sequence

1. `git clone https://github.com/pypa/pip.git /tmp/j3-data-036-pip-validation-scripttest/pypa__pip-pypa__pip-issue-12018-pr-13886-8df7b668b376`
2. `git checkout 8df7b668b3766e1d4a71246509d64aeec47a805b`
3. `git rev-parse HEAD`
4. `python -m pip install -e . installer scripttest`
5. `pytest tests/functional/test_install_reqs.py -q`

## Classification

The row advances past `scripttest` but is still a validation recipe/dependency
blocker, not candidate edit quality. It is not ready for prompt/spec or
local-knowledge acquisition until a bounded pip functional-test setup recipe
also accounts for the socket pytest plugin, or the validation command is
replaced with an equivalent focused subset that does not require the plugin.

## Artifacts

- JSONL: `/tmp/j3-data-036-pip-validation-scripttest/attempts-data-036.jsonl`
- Report: `/tmp/j3-data-036-pip-validation-scripttest/report-data-036.md`
