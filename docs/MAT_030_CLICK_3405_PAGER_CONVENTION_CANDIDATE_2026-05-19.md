# MAT-030 Click #3405 Pager Convention Candidate

Task: `MAT-030`

Reference PR: https://github.com/pallets/click/pull/3405

## Result

`pallets/click#3405` materializes with reusable repo-convention action
records. The accepted PR is test-only:

- Base ref: `98302ac4f49e443a48abd3fbb95c86202b89547d`
- Accepted head ref: `b761eda3bad977ec2f485451d85fd8ec365f0bf4`
- Accepted changed files: `tests/test_termui.py`
- Candidate changed files: `tests/test_termui.py`
- Validation command: `PYTHONPATH=src python -m pytest tests/test_termui.py::test_get_pager_file_with_real_pager_binary_stream tests/test_termui.py::test_echo_via_pager_real_pager_handles_ansi -q`
- Live validation: `passed`

The candidate has exact full accepted-diff parity. Source/test scoped parity is
also true; there are no changelog or docs files in this accepted diff.

## Reusable Actions

- `replace_exact_source_lines_after_anchor`: updates the local real-pager helper
  to use `cat` and document the Unix pipe-pager scope.
- `replace_exact_source_lines_after_anchor`: updates the stream test docstring
  after the Windows path is skipped.
- `insert_pytest_mark_decorator_before_function`: inserts a generic
  `pytest.mark.skipif` marker before the existing parametrize decorator for the
  real pager stream test.
- `insert_pytest_mark_decorator_before_function`: inserts the same generic
  marker for the `echo_via_pager` pager test.

The mark-decorator action checks the local Click test conventions that make the
edit bounded: `pytest` import, imported `WIN` platform sentinel, existing
`pytest.mark.parametrize` decorator, `monkeypatch` and `capfd` fixture
arguments, and pager stream source fragments.

## Candidate Metadata

- Candidate JSON: `/tmp/j3-mat-030-click-3405-live/final/candidate.json`
- Candidate report: `/tmp/j3-mat-030-click-3405-live/final/report.md`
- Candidate diff: `/tmp/j3-mat-030-click-3405-live/final/candidate.diff`
- Accepted diff: `/tmp/j3-mat-030-click-3405-live/accepted.diff`
- Candidate diff SHA-256:
  `1425c39d73113e77923c99167751f9bde4655e7726a01900b6962733b7284e02`
- Candidate diff summary: `+17/-5`, 4 hunks, 22 changed lines.
- `tests/test_termui.py` before SHA-256:
  `fe81a4b955c797d20c7292191cf0feb18d742e734d1079591999fe38b8bcfcda`
- `tests/test_termui.py` after SHA-256:
  `54abc2e7e3c409688cfd601ddb1bf8592854c81cbc54d7d3223b5fdd0a2612d7`

## Scope

Mutation scope is one allowlisted test file. No source, docs, changelog,
validation-policy, ranking, transition, local-knowledge, or matrix files are
part of this materialization.

This closes the final remaining `repo_convention_builder` row from the
MAT-007 panel. The remaining non-materialized MAT-007 counts are now:
`current_structured_action = 4`, `general_typed_builder = 0`,
`repo_convention_builder = 0`, `constrained_local_generator = 0`, and
`not_currently_expressible = 2`.
