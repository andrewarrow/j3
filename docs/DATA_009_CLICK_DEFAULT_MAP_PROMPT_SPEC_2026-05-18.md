# DATA-009 Click Default Map Prompt Spec

Prompt/spec normalization only; no candidate source edits were attempted.

## Summary

- Replay row: `pallets__click-issue-2745-pr-3364`
- Output: `/private/tmp/j3-data-009-click-default-map-spec.jsonl`
- Status: `normalized`
- Missing prompt fields: `{}`
- Source text blockers: `{}`

## Structured Fields

- Minimal reproduction: Click command with an eager `--settings` callback that
  mutates `ctx.default_map` before dependent options consume defaults.
- Observed behavior: Click 8.0.0 and later reject the string default for
  `--general-foo` / `--foo` with `Value must be an iterable`.
- Expected behavior: string values from `default_map` are split for multi-value
  parameters using environment-variable splitting semantics.
- Affected API: `click.Context.default_map` via
  `click.core.Option.consume_value`.
- Input shape: string `default_map` values for `nargs > 1` and tuple-typed
  options, with structured tuple/list controls.
- Acceptance test shape: `tests/test_defaults.py::test_default_map_nargs`.
- Mutation timing: during the eager `--settings` callback before later option
  default resolution.
- Multi-value shape: `nargs=2` and explicit tuple type cases.
- String splitting: `ParamType.split_envvar_value`, defaulting to whitespace,
  matching `value_from_envvar` behavior.

## Provenance

- Issue: `https://github.com/pallets/click/issues/2745`
- PR: `https://github.com/pallets/click/pull/3364`
- Diff: `https://github.com/pallets/click/pull/3364.diff`
- Manifest: `examples/issue_pr_mini_replay/manifest.json`
