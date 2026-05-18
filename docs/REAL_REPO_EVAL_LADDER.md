# Real Repo Eval Ladder

`REAL-001` creates the first falsifiable held-out ladder for j3 outside
project-owned fixtures. It is intentionally small: four permissively licensed
Python repositories, two task classes per repository, pinned checkout refs, cheap
validation commands, and explicit failure gates.

The companion manifest is
`examples/real_repo_eval_ladder.json`. It is a harness contract, not an
implementation runner.

## Questions This Answers

Can j3 generalize outside its own fixtures?

- Yes, for this ladder only, if it can solve held-out tests-only and one-file
  feature tasks across multiple real repositories without repo-specific action
  special cases, hosted patch generation, or training on paraphrases of these
  prompts.
- No, for this ladder, if success remains limited to j3 GreenShot fixtures or
  one hand-tuned calibration repository.

Can validation stay cheap and trustworthy?

- Cheap: every task has targeted pytest commands, a per-candidate timeout, and a
  per-task wall-clock cap. The first gate does not run full upstream CI.
- Trustworthy: each run starts from a pinned clean checkout, requires the
  relevant baseline tests to pass before j3 edits, records exact commands, and
  adds hidden-like checks that are not used for prompt/spec or action tuning.

What result falsifies the approach for this ladder?

- Strong falsifier: after generic existing-repo tests-only support and one-file
  feature materialization exist, j3 gets `pass@3 == 0/4` on one-file feature
  tasks or `< 2/4` on tests-only tasks while baseline validation passes on at
  least three repositories.
- Practical falsifier: j3 can pass only by adding repo-specific actions keyed to
  these repositories, by using hosted patch generation, or by relying on prompts
  or hidden checks leaked into training.
- Validation falsifier: more than one repository cannot maintain a passing
  baseline under the pinned setup commands within the runtime cap.

## Repositories

The initial ladder uses these refs, checked on 2026-05-18:

| Repo | License | Ref | Why included |
| --- | --- | --- | --- |
| `pytest-dev/iniconfig` | MIT | `77db208ab4ae0cd2061d909fe222a1db72867850` | tiny `src/` package, parser behavior, pytest suite |
| `python-hyper/h11` | MIT | `62c5068c971579d61fa1b55373390e12f25fd856` | protocol library, package-local tests, stricter invariants |
| `python-humanize/humanize` | MIT | `bde649fc2927c022dd2a9eedba2a1ed677b97902` | small multi-module utility library with typed public APIs |
| `mahmoud/boltons` | BSD-3-Clause | `207651ee6055aabd0d9cdeac2e00140cdc208d44` | larger utility library with older conventions and many modules |

`iniconfig` is the calibration repository for harness shakeout. The scored
held-out set is `h11`, `humanize`, and `boltons`. After the harness itself is
stable, coordinator review may promote all four into held-out scoring only if no
j3 code or prompt tuning used their task text.

## Task Classes

Each repository has two task records in the manifest.

- `tests_only`: add or refine tests for existing behavior. Production files must
  remain unchanged.
- `one_file_feature`: implement one narrowly described behavior in exactly one
  production file, with tests allowed in the existing test location.

The tasks are deliberately boring. They target whether j3 can inspect a real
package, choose the right file, materialize small code or tests, and validate the
result without overfitting to j3-owned fixtures.

## Validation Policy

Every run records:

- repo id and checkout ref
- task id, task type, prompt, and allowed write paths
- baseline validation result before edits
- candidate count, `pass@1`, `pass@3`, first passing candidate rank, and runtime
- public validation commands and hidden-like check result
- residual label for every failure
- zero hosted usage confirmation

Default limits:

- `max_candidates`: 3
- `per_candidate_timeout_seconds`: 120
- `per_task_timeout_seconds`: 600
- `network`: allowed only during clean dependency setup, not during candidate
  validation
- `mutation scope`: no file outside the task's allowed write paths

Validation is considered cheap enough for this spike if the median task runtime
is at or below 180 seconds and no single successful task exceeds 600 seconds.

## Split And Leakage Rules

- Split by repository, not by prompt paraphrase.
- Do not train on source diffs, issue text, prompts, hidden checks, or generated
  variants from scored repositories.
- Do not add these task prompts to GreenShot fixtures.
- Do not add action rules keyed to repo names, paths, or exact prompt strings.
- Hidden-like checks are eval-only. They can be inspected by the coordinator
  after a run, but not used to tune prompt parsing, action generation, or
  ranking.
- If `DATA-004` or later issue/PR replay includes the same repository, that row
  must be assigned to the same split or excluded from this ladder.

## Gates

### Gate A: Baseline Viability

Before running j3, at least three repositories must pass their listed baseline
validation commands from clean checkouts. If not, fix the harness or replace the
repo; do not score j3 against broken upstream setup.

### Gate B: Tests-Only Generalization

Pass condition:

- `pass@3 >= 3/4` on tests-only tasks
- zero production-file modifications
- no hidden-like failures among passing public validations

Failing this gate means current request-to-repo progress has not generalized to
real existing-repo test authoring.

### Gate C: One-File Feature Generalization

Pass condition:

- `pass@3 >= 2/4` on one-file feature tasks
- at least two different repositories pass
- no candidate edits more than one production file
- hidden-like checks agree with public validation on passing candidates

Failing this gate points at the code materialization gap, repo-state selection,
or prompt/spec understanding rather than another synthetic fixture gap.

### Gate D: Trustworthy Cheap Validation

Pass condition:

- median runtime at or below 180 seconds
- all scored tasks under 600 seconds
- no network during candidate validation
- residuals distinguish validation infrastructure failures from agent failures

## First Expected Failure Modes

Expected early residuals:

- `tests_only_scope_violation`: j3 edits source while asked to add tests only.
- `wrong_test_location`: tests are added outside the repo's discovered test
  layout.
- `repo_import_setup_failure`: candidate tests fail because package setup,
  editable install, or import paths are mishandled.
- `one_file_materialization_gap`: the desired behavior is understood but cannot
  be expressed by current structured builders.
- `wrong_symbol_or_module`: j3 picks a plausible utility file but not the one
  the public API uses.
- `validation_selection_gap`: public targeted tests pass but hidden-like checks
  expose an untested behavior.
- `dependency_or_tooling_gap`: upstream test tooling is too new, too slow, or
  unavailable in a clean local environment.

These residuals are the output of the spike. The goal is not to hide them with
repo-specific patches.

## Next Harness Step

The next bounded task should add a runner that can:

1. Clone each repo to `/tmp`.
2. Check out the pinned ref.
3. Run setup and baseline validation.
4. Apply one j3 candidate under an allowlist of writable paths.
5. Run public and hidden-like validations with timeouts.
6. Emit one JSONL outcome row per candidate.

Until that runner exists, the manifest and this document are the source of truth
for `REAL-001`.
