# Local Knowledge Inventory

Task: `KNOW-001`

Date: 2026-05-18

## Decision

The first local-knowledge wedge is:

```text
pytest authoring and validation
  + Python packaging and import layout
  + small-library maintenance conventions
```

This is narrower than general Python coding and broader than the current
GreenShot fixtures. It directly supports the next useful product surface:
tests-only existing-repo edits, conservative one-file small-library changes,
and constrained source-region materialization with local validation.

The knowledge must become local data, not hand-written rules hidden in builder
code. A builder may use an extracted convention record, a retrieved pytest
pattern, or a validated packaging layout. It should not know by construction
that "pytest projects use `tests/`", that "`src/` packages need editable
installs", or that `monkeypatch.setenv` belongs in `conftest.py`.

## Wedge Scope

In scope:

- Pytest test discovery, file layout, function and class naming, markers,
  parametrization, fixtures, `conftest.py`, `monkeypatch`, `tmp_path`,
  `capsys`, warning and exception assertions, and targeted invocation.
- Packaging and import setup for small Python libraries: flat packages,
  `src/` layout, namespace package signals, `pyproject.toml`, `setup.cfg`,
  `setup.py`, package exports, public modules, editable installs, console
  scripts, and package-local test invocation.
- Small-library idioms that appear in the current wedge: pure functions,
  parser helpers, validation helpers, public API re-exports, simple CLI
  entrypoints, config readers, environment-sensitive behavior, text/path
  handling, and compatibility guards.
- Local convention detection: where tests live, how tests import the package,
  how fixtures are named, how parametrized cases are formatted, what validation
  command is cheap enough, and which paths may be edited for a task.
- Outcome data: validation results, residual labels, accepted diffs, rejected
  candidates, and hidden-like check failures linked back to the knowledge
  records used by the candidate.

Out of scope for this first wedge:

- Broad framework internals such as Flask app/request context semantics,
  Poetry publishing/auth internals, pip resolver behavior, and Scrapy queue
  accounting except when they appear as held-out issue/PR replay residuals.
- Large migrations, lockfile rewrites, multi-module architecture changes, and
  CI provider knowledge.
- Runtime use of a frontier LLM to infer test, packaging, or library
  conventions on demand.

## Required Concepts

| Concept | What j3 must know locally | Candidate sources | Structured data target |
| --- | --- | --- | --- |
| Test discovery and layout | Pytest finds `test_*.py` and `*_test.py`, test functions/classes by naming, and project-level config can override defaults. Existing repos may use `tests/`, package-local tests, or `testing/`. | Pytest docs snapshot, repo test trees, `pyproject.toml` or `pytest.ini`, real-repo ladder rows, issue/PR changed paths. | `pytest_layout_record` with discovered roots, naming patterns, config files, import mode hints, and examples. |
| Targeted invocation | Cheap commands should run the smallest useful test file, node id, or hidden-like check after baseline viability passes. | Validation commands from `examples/real_repo_eval_ladder.json`, issue/PR mini replay rows, upstream README/dev docs, observed subprocess outcomes. | `validation_recipe_record` with setup commands, baseline commands, focused commands, timeout, network policy, and failure class. |
| Fixtures and `conftest.py` | Fixture scope, autouse behavior, local fixture naming, fixture dependency order, and when a shared fixture belongs in `conftest.py` instead of a test file. | Pytest docs snapshot, existing repo `conftest.py` files, accepted PRs such as Requests proxy cleanup, validation outcomes. | `pytest_fixture_pattern_record` with fixture signature, scope/autouse, target path, imports, used tests, and provenance. |
| Monkeypatch and environment tests | Use `monkeypatch.setenv`, `delenv`, `setattr`, `setitem`, and context cleanup rather than manual global mutation. | Pytest monkeypatch docs, repo tests using monkeypatch, Requests and Click accepted diffs, failed candidate residuals. | `pytest_tool_pattern_record` with tool kind, setup line examples as AST shapes, cleanup guarantee, and matching task labels. |
| Parametrization and marks | Parametrize cases when local style does; preserve mark ordering, ids, skip/xfail conventions, and long-case formatting. | Pytest docs, existing tests, accepted test diffs from Click/pytest/Requests, hidden-like check failures. | `pytest_case_style_record` with decorator shape, argument names, case count, ids style, mark usage, and neighboring examples. |
| Exception, warning, and output assertions | Use `pytest.raises`, `pytest.warns`, `recwarn`, `capsys`, and snapshot-like assertions in the style already present. | Pytest docs, repo test corpus, GreenShot and real-repo tasks, accepted diffs. | `pytest_assertion_pattern_record` linked to observed import names, assertion helper functions, and expected failure messages. |
| Package layouts | Distinguish flat packages, `src/` layout, namespace packages, single modules, package data, and test import strategy. | `pyproject.toml`, `setup.cfg`, `setup.py`, README install docs, repo tree encoder, real-repo ladder repos. | `packaging_layout_record` with package roots, importable modules, build backend, editable install command, and public API roots. |
| Imports and exports | Public symbols may be exported through `__init__.py`, `__all__`, entrypoints, or documented import paths; tests should import like the repo does. | Source tree, docs examples, tests, accepted diffs, import errors from validation. | `public_api_record` with module path, exported names, re-export chain, test import examples, and confidence. |
| Project configuration | Pytest options, testpaths, markers, addopts, build backend, optional dependencies, and Python version constraints affect validation. | `pyproject.toml`, `pytest.ini`, `tox.ini`, `noxfile.py`, `setup.cfg`, lock/config files, failed setup logs. | `project_config_record` with normalized config fields, raw file checksums, parser warnings, and unsupported keys. |
| CLI entrypoints and script invocation | Console scripts, `python -m package`, module main guards, and command test helpers must be detected before adding tests or demos. | `pyproject.toml` scripts, setup entry points, README usage, tests invoking CLIs, GreenShot CLI fixtures. | `cli_surface_record` with entrypoint kind, command form, argument examples, and validation command references. |
| Small-library idioms | Pure helpers, parsers, normalization functions, defensive validation, boundary checks, text/path handling, and environment-sensitive utilities need reusable examples. | GreenShot 6/7 examples, real-repo ladder tasks, accepted PR regions, repo README examples, validation residuals. | `library_idiom_record` with problem label, input/output examples, target symbol kind, neighboring tests, and accepted action family. |
| Local convention matching | The same task should materialize differently in pytest, Requests, h11, humanize, or boltons based on local style. | Repo-state coverage records, adjacent source and test files, accepted diffs, hidden-like checks. | `repo_convention_record` with per-repo style facts, retrieved examples, split, and freshness timestamp. |

## Source Inventory

Use these source classes in priority order for the wedge.

1. Local repository evidence

   - `examples/greenshot_6/` and `examples/greenshot_7/` provide controlled
     small-library tasks, tests, and known residuals.
   - Real-repo ladder checkouts provide held-out packaging and pytest layout
     evidence for `iniconfig`, `h11`, `humanize`, and `boltons`.
   - Issue/PR mini replay rows provide real task text, accepted PR refs,
     focused validation commands, residual labels, and changed paths.

2. Project files from checked-out repositories

   - `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`, `noxfile.py`,
     `pytest.ini`, `conftest.py`, README/development docs, source modules, and
     tests.
   - These are the highest-value convention sources because they describe the
     exact repo under edit.

3. Accepted diffs and validation outcomes

   - Accepted PR diffs provide positive examples for where tests are added,
     what imports are used, and which source regions change.
   - Failed candidates and validation logs provide hard negatives and residual
     labels: wrong test location, import setup failure, missing fixture,
     materialization gap, ranking gap, and local knowledge gap.

4. Official documentation snapshots

   - Pytest docs for discovery, fixtures, monkeypatch, parametrization, marks,
     `raises`, `warns`, and invocation.
   - Python packaging documentation for `pyproject.toml`, build backends,
     editable installs, console scripts, and package discovery.
   - These snapshots should seed concept definitions and extraction tests; they
     should not override repo-local evidence when a repository differs.

5. README and development docs

   - READMEs, contributing docs, and test instructions are useful for setup and
     validation but often stale. Treat them as lower-confidence sources until a
     subprocess run confirms them.

## Structured Data Records

The first implementation should create small JSONL records rather than a large
knowledge graph. Records should be append-only and reconstructable from source
snapshots.

Common fields for every record:

```json
{
  "id": "stable sha256-derived id",
  "record_type": "pytest_layout_record",
  "source": {
    "kind": "repo_file|official_doc|accepted_diff|validation_outcome",
    "repo": "owner/name",
    "ref": "commit or docs snapshot id",
    "path": "relative/path.py",
    "url": "optional canonical URL",
    "license": "SPDX or docs terms note",
    "retrieved_at": "ISO-8601 timestamp"
  },
  "split": "calibration|train|validation|test|heldout",
  "provenance_hash": "sha256 of raw source or normalized excerpt",
  "extracted_by": "extractor name and version",
  "confidence": "observed|inferred|validated",
  "links": {
    "task_ids": ["REAL-001/iniconfig-tests-only"],
    "outcome_ids": ["optional validation outcome id"],
    "residual_labels": ["optional residual labels"]
  }
}
```

Initial record families:

- `pytest_layout_record`: test roots, naming patterns, config overrides,
  package import mode, adjacent examples.
- `pytest_pattern_record`: fixtures, monkeypatch, parametrization, marks,
  exception/warning/output assertions, helper imports, and AST shape.
- `packaging_layout_record`: source roots, package roots, build backend,
  editable install command, Python constraints, optional test extras.
- `public_api_record`: importable modules, exported names, re-export paths,
  documented examples, and tests proving the import style.
- `validation_recipe_record`: setup commands, baseline validation, focused
  command, hidden-like command, timeouts, network policy, and observed result.
- `library_idiom_record`: small-library behavior pattern, input/output
  examples, symbol kind, likely action family, and accepted/rejected examples.
- `knowledge_use_record`: candidate id, retrieved knowledge record ids, action
  family chosen, validation result, and residual if it failed.

`knowledge_use_record` is what prevents the inventory from becoming static
documentation. Every j3 candidate for this wedge should be able to say which
local records it used. Evaluation can then ask whether failures came from
missing knowledge, bad retrieval, bad materialization, or bad validation.

## Extraction Rules

Repository extraction should be deterministic:

```text
checkout pinned ref
  -> read config files and repo tree
  -> parse Python files with ast
  -> parse TOML/INI/setup metadata with structured parsers where available
  -> discover pytest patterns from tests and conftest.py
  -> run setup and baseline validation only in a preflight runner
  -> emit JSONL records with checksums and split labels
```

Do not extract by brittle prose matching when structured data exists. Use
`ast` for Python, TOML parsing for `pyproject.toml`, config parsers for INI
files, and subprocess outcome rows for validation facts.

Official docs extraction should be snapshot-based:

- Store the docs version, URL, retrieval date, license or terms note, and
  normalized section id.
- Extract compact concept rows such as `pytest_fixture_scope`,
  `pytest_monkeypatch_setenv`, or `packaging_console_scripts`.
- Keep examples short and provenance-linked. Do not paste full documentation
  pages into checked-in data.

Accepted-diff extraction should be scoped:

- Record changed paths, changed symbol names, test file additions, fixture
  additions, validation command, accepted action family, and residual labels.
- Store raw diffs in ignored local data or an external artifact until the
  provenance and release policy is settled.
- Checked-in manifests may reference URLs, commit SHAs, checksums, and compact
  derived labels.

## Split And Leakage Rules

- Split by repository first. Do not train on `h11`, `humanize`, or `boltons`
  convention records if they are scored held-out repositories in the real-repo
  ladder.
- Calibration repositories may feed extractor development, but their prompts
  and hidden-like checks must not be copied into GreenShot fixtures.
- A source snapshot and all derived records from that snapshot share the same
  split. Do not put README/config/test records from the same commit in
  different splits.
- Official docs concept records may be shared across splits, but doc examples
  must not be used as hidden-like eval checks.
- Issue/PR replay rows from a repository already in a held-out ladder must
  either inherit that repository split or be excluded from scoring.
- Candidate outcomes must record whether a knowledge record was available at
  candidate time. Post-failure records are allowed only for later training or
  residual analysis, not for rescoring the same run.

## Evaluation Hooks

Knowledge is useful only if it changes measurable behavior. The first hooks:

- Existing-repo tests-only gate: did j3 add tests in the discovered local test
  root, avoid production edits, import the package correctly, and pass public
  plus hidden-like checks?
- Packaging preflight gate: did setup and baseline validation succeed from a
  clean pinned checkout without manual path hacks?
- Retrieval attribution gate: did each candidate cite local records for test
  layout, import style, and validation recipe? If not, label the run as
  `knowledge_not_used` even if it passes.
- Residual separation gate: failures must distinguish `missing_knowledge`,
  `bad_knowledge_retrieval`, `bad_materialization`, `validation_setup_failure`,
  `ranking_gap`, and `prompt_spec_gap`.
- Held-out discipline gate: no scored run may use records derived from the same
  held-out repo split except records extracted from the repo-under-edit during
  its allowed preflight.

## First Acquisition Work

### 1. Real-Repo Pytest/Packaging Preflight Records

Build a runner for one calibration repository, then expand to the ladder:

```bash
python cli.py real-repo-preflight \
  --manifest examples/real_repo_eval_ladder.json \
  --repo iniconfig \
  --out /tmp/j3-real-repo-preflight.jsonl
```

Success criteria:

- Emits `packaging_layout_record`, `pytest_layout_record`, and
  `validation_recipe_record` for the pinned repo.
- Baseline validation passes from a clean checkout.
- The output records exact setup commands, focused commands, runtime, repo ref,
  checksums, and split.

Failure criteria:

- Setup requires undocumented manual intervention.
- Test import behavior is guessed instead of observed.
- A baseline failure is reported as an agent failure rather than a validation
  or environment blocker.

### 2. Pytest Pattern Extractor From Local Test Trees

Build a deterministic extractor over existing tests:

```bash
python cli.py extract-pytest-patterns \
  --repo /tmp/j3-real-repos/iniconfig \
  --out /tmp/j3-pytest-patterns.jsonl
```

Success criteria:

- Finds fixtures, `conftest.py`, parametrization, marks, monkeypatch use, and
  assertion helpers when present.
- Emits AST-backed records with source path, line span, neighboring imports,
  and split.
- Re-running the extractor on the same checkout produces identical records.

Failure criteria:

- The extractor depends on exact repository names.
- Records contain raw large source blobs instead of compact AST shapes and
  checksums.
- Pattern labels cannot be linked to candidate outcomes.

### 3. Issue/PR Replay Knowledge Residual Rows

Extend the mini replay preflight before edit attempts:

```bash
python cli.py issue-pr-preflight \
  --manifest examples/issue_pr_mini_replay/manifest.json \
  --id psf__requests-issue-7432-pr-7433 \
  --out /tmp/j3-issue-pr-preflight.jsonl
```

Success criteria:

- Checks out `repo_before_ref`, records setup and baseline validation result,
  and emits a local-knowledge residual when pytest/package conventions are not
  extractable.
- Links the issue/PR row, accepted changed paths, validation command, extracted
  records, and residual labels.
- Produces hard negatives for wrong test location, wrong import style, and
  missing fixture/convention knowledge.

Failure criteria:

- The row cannot distinguish dependency/setup failure from j3 edit failure.
- It stores full issue bodies or raw diffs in git without a release policy.
- It treats the accepted PR title or changed paths as prompt-visible training
  data for held-out scoring.

## Implementation Notes

- Start with JSONL in ignored scratch paths and compact checked-in manifests
  only after the schema is stable.
- Prefer source-local records over official docs when they conflict. Official
  docs explain available mechanisms; repo evidence decides the convention.
- Keep the first wedge boring. Passing tests-only tasks by using extracted
  layout/import/fixture records is stronger evidence than adding more
  hard-coded GreenShot builders.
