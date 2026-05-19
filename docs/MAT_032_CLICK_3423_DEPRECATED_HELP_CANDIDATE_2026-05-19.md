# MAT-032 Click #3423 Deprecated Help Candidate

## Scope

- Repo/PR: `pallets/click#3423`
- Candidate: `mat-032-click-deprecated-help-separator`
- Base ref: `fc6c7c47edd6110b6bd5a1a5297b2035214b0cd1`
- Accepted head ref: `61acdcc4ce718f1f6e49e79625c0a6b088bc8189`
- Merge evidence: GitHub PR API reports one commit, one changed file, merged on
  2026-05-15 with merge commit `0039359443e73ab1034c63a1f6d58aba22c0ebc8`.
- Accepted changed files: `src/click/core.py`

## Action

The candidate uses the reusable `replace_delimited_region` source-region action.
No PR-named action kind was added. The bounded target is the deprecated option
help expression in `src/click/core.py`; the replacement rewrites:

```python
help = help + deprecated_message if help is not None else deprecated_message
```

to the accepted formatted expression that inserts a separator before the
deprecated message.

## Artifact

- Directory: `/tmp/j3-mat-032-click-3423-live`
- Candidate JSON: `/tmp/j3-mat-032-click-3423-live/final/candidate.json`
- Report: `/tmp/j3-mat-032-click-3423-live/final/report.md`
- Candidate diff: `/tmp/j3-mat-032-click-3423-live/final/candidate.diff`
- Accepted diff: `/tmp/j3-mat-032-click-3423-live/accepted.diff`

Candidate metadata:

- Status: `validated`
- Mutation scope mode: `heldout_source_region_source_only`
- Planned write files: `src/click/core.py`
- Actual changed files: `src/click/core.py`
- Writes outside allowlist: none
- Source hash before: `01a262bf7e49ed987d9b9e20ac163185562e2e3537aefe5ef126689965bf89d1`
- Source hash after: `61b929bb8c69449bc831bcf5bc23496f79b6efdcc95eef5569754906972254a9`
- Candidate diff line count: 17
- Accepted diff line count: 17
- Accepted diff normalized parity: `true`
- Accepted source-only scoped parity: `true`

## Validation

Command:

```bash
PYTHONPATH=src python -c "import click; from click.testing import CliRunner; cmd = click.Command('cli', params=[click.Option(['--old'], help='Old option', deprecated=True)]); result = CliRunner().invoke(cmd, ['--help']); assert result.exit_code == 0, result.output; assert 'Old option (DEPRECATED)' in result.output, result.output; assert 'Old option(DEPRECATED)' not in result.output, result.output"
```

Result: passed with return code 0 in 0.052 seconds.

Residual labels: `candidate_validation_passed`.
