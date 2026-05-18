# DATA-032 Pip Validation Recipe Isolation

Pre-edit validation evidence only; no candidate source edits were attempted.

## Result

- Replay: `pypa__pip-issue-12018-pr-13886`
- Repo-before ref: `8df7b668b3766e1d4a71246509d64aeec47a805b`
- Setup adjustment tested: `python -m pip install -e . installer`
- Dependency added: `installer`
- Validation command: `pytest tests/functional/test_install_reqs.py -q`
- Runtime: `5.141` seconds
- Status: `blocked`
- First failed stage: `validation`
- Command classification: `dependency_fixture_setup_failure`
- Evidence acquisition status: `blocked_on_validation_recipe`

Installing `installer` addresses the DATA-030 blocker, but the same bounded
validation command still fails while importing `tests/conftest.py`. The first
new missing dependency is `scripttest`, imported through `tests/lib/__init__.py`.

## Command Sequence

1. `git clone https://github.com/pypa/pip.git /tmp/j3-data-032-pip-validation-recipe/repos/pypa__pip-pypa__pip-issue-12018-pr-13886-8df7b668b376`
2. `git checkout 8df7b668b3766e1d4a71246509d64aeec47a805b`
3. `git rev-parse HEAD`
4. `python -m pip install -e . installer`
5. `pytest tests/functional/test_install_reqs.py -q`

Validation failed with:

```text
E   ModuleNotFoundError: No module named 'scripttest'
```

## Classification

This is still a validation recipe/dependency blocker, not candidate edit
quality. The row is not ready for prompt/spec or local-knowledge acquisition
until the pip functional-test fixture dependencies are made hermetic with a
bounded setup recipe, or the validation command is replaced with an equivalent
focused subset that does not fail during fixture import.

## Artifacts

- JSONL: `/tmp/j3-data-032-pip-validation-recipe/attempts-data-032.jsonl`
- Report: `/tmp/j3-data-032-pip-validation-recipe/report-data-032.md`
