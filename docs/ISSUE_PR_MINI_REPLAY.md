# Issue/PR Mini Replay

`DATA-004` adds a compact mini replay manifest at
`examples/issue_pr_mini_replay/manifest.json`. It normalizes 10 reviewed
GitHub issue/PR examples into prompt text, repo-before refs, accepted PR refs,
validation commands where a focused command can be inferred from changed tests,
license/provenance notes, stable splits, and initial residual labels.

The manifest is intentionally small. It stores titles, links, commit refs,
changed paths, labels, and commands; it does not store issue bodies, PR bodies,
patches, or harvested diffs in git. Larger exports should stay under ignored
`data/` or `/tmp` paths until reviewed.

## Schema

Each record includes:

- `id`: stable `owner__repo-issue-N-pr-M` identifier.
- `prompt_text`: concise issue/PR-derived task text.
- `repo_before_ref`: GitHub repo, branch, and base commit SHA.
- `accepted_change`: merged PR URL, diff URL, merge commit SHA, and changed
  files.
- `validation`: a focused command when changed tests identify one, marked
  `partial` because project setup, dependencies, and full CI are not captured.
- `provenance_license`: repository URL, SPDX license, license URL, and review
  status.
- `stable_split`: deterministic `sha256(id) % 100` split assignment.
- `initial_residual_labels`: first-pass blocker labels from
  `local_knowledge_gap`, `materialization_gap`, `validation_gap`,
  `ranking_gap`, and `prompt_spec_parsing_gap`.

## Curated Examples

| Repo | Issue/PR | Prompt Shape | Focused Validation |
| --- | --- | --- | --- |
| `psf/requests` | #7432 / #7433 | stream detection regression | `pytest tests/test_requests.py -q` |
| `pallets/click` | #2745 / #3364 | `default_map` multi-value behavior | `pytest tests/test_defaults.py -q` |
| `pallets/click` | #3298 / #3299 | non-string default crash | `pytest tests/test_options.py -q` |
| `pytest-dev/pytest` | #14442 / #14443 | strict options in `addopts` | `pytest testing/test_config.py testing/test_mark.py -q` |
| `pytest-dev/pytest` | #14462 / #14466 | timedelta relative tolerance | `pytest testing/python/approx.py -q` |
| `pytest-dev/pytest` | #14381 / #14382 | `-V` version option | `pytest testing/test_helpconfig.py -q` |
| `python-poetry/poetry` | #1328 / #10845 | repository names with periods | config and command tests |
| `pypa/pip` | #12018 / #13886 | URL constraints with extras | `pytest tests/functional/test_install_reqs.py -q` |
| `scrapy/scrapy` | #7293 / #7351 | downloader queue accounting | `pytest tests/test_pqueues.py -q` |
| `python-poetry/poetry` | #6687 / #10785 | PEP 503 upload URL slash | `pytest tests/publishing/test_publisher.py -q` |

## What Breaks First

Local knowledge gaps show up immediately. The rows require domain concepts from
Requests body preparation, Click parameter defaults, pytest configuration,
Poetry repository/auth publishing behavior, pip's resolver, and Scrapy
download queues. A repo-state graph alone will not infer those semantics.

Materialization is also not a small-patch problem. Several accepted changes
touch source, tests, changelog/news files, docs, and fixtures together. The
Poetry period-name example spans 12 files across config, publisher,
authenticator, tests, and fixtures, which is outside current greenfield and
repair builders.

Validation is only partially reproducible from the compact manifest. The
focused commands are inferred from changed test files, but running them against
the exact `repo_before_ref` still requires project-specific setup, Python
version compatibility, optional services, and dependency locks. Pip functional
tests and Poetry publishing tests are likely to expose setup and runtime
constraints before edit quality can be judged.

Ranking remains hard even when the correct edit family exists. Multiple rows
have plausible nearby decoys: pytest config parsing versus mark handling,
Click default conversion versus option formatting, Poetry config-source versus
publisher/auth paths, and pip resolver factory branches. The manifest should be
used to create hard negatives, not only accepted positives.

Prompt/spec parsing is the first textual gate. Titles are compact but omit
repro snippets and environmental details from issue bodies or linked
discussion. Some PR titles reveal the solution and should not be treated as
the only prompt. A replay runner should support prompt variants such as issue
title only, issue title plus body excerpt, and PR title as privileged reference
metadata.

## Next Probe

The next useful step is a replay checker that materializes one repository at
`repo_before_ref`, records whether dependencies and the focused validation
command can run before any edit, and classifies failures as environment,
validation, prompt/spec, ranking, materialization, or local knowledge blockers.
