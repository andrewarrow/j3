from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from j3 import issue_pr_docs_materializer as materializer
from j3.issue_pr_docs_materializer import (
    CLICK_COMMANDS_DOCS_PATH,
    CLICK_DOCS_CONF_ASSIGNMENT,
    CLICK_DOCS_CONF_PATH,
    CLICK_DEFAULT_MAP_REPLAY_ID,
    build_click_default_map_commands_docs_section,
    insert_click_default_map_commands_docs_section,
    insert_sphinx_conf_scalar_assignment,
    main,
    run_click_commands_docs_materializer,
    validate_click_default_map_commands_docs_section,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"
CLICK_DEFAULT_MAP_SHA = "8a2b48901a08b3d2ec3a9bbd151948a9765368c6"


def test_generated_section_has_data019_contract() -> None:
    section = build_click_default_map_commands_docs_section()

    assert validate_click_default_map_commands_docs_section(section) is None
    assert section.startswith("### Multi-value parameters")
    assert "nargs > 1" in section
    assert "{class}`Tuple`" in section
    assert '"point": "3 4"' in section
    assert "split on whitespace" in section


def test_section_insert_preserves_unrelated_commands_content() -> None:
    before = (
        "# Commands\n"
        "\n"
        "Intro text.\n"
        "\n"
        "## Overriding Defaults\n"
        "\n"
        "Existing default_map docs.\n"
        "\n"
        "## Context Defaults\n"
        "\n"
        "Context defaults stay here.\n"
    )
    section = build_click_default_map_commands_docs_section()

    after = insert_click_default_map_commands_docs_section(before, section)

    assert "Existing default_map docs." in after
    assert "Context defaults stay here." in after
    assert after.replace("\n" + section, "", 1) == before
    assert after.index("### Multi-value parameters") < after.index("## Context Defaults")


def test_sphinx_conf_assignment_insert_compiles_and_blocks_duplicates() -> None:
    before = (
        "extensions = []\n"
        "intersphinx_mapping = {\n"
        '    "python": ("https://docs.python.org/3/", None),\n'
        "}\n"
        "\n"
        "html_theme = 'click'\n"
    )

    after = insert_sphinx_conf_scalar_assignment(before)

    assert after.count(CLICK_DOCS_CONF_ASSIGNMENT) == 1
    assert after.index(CLICK_DOCS_CONF_ASSIGNMENT) > after.index("intersphinx_mapping")
    compile(after, CLICK_DOCS_CONF_PATH, "exec")
    with pytest.raises(materializer.IssuePrDocsMaterializerError) as error:
        insert_sphinx_conf_scalar_assignment(after)
    assert error.value.blocker["reason"] == "duplicate_sphinx_conf_assignment"


def test_materializer_writes_only_docs_paths_and_records_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _click_docs_repo(tmp_path)
    monkeypatch.setattr(
        materializer,
        "_git_stdout",
        lambda repo_path, args: CLICK_DEFAULT_MAP_SHA
        if tuple(args) == ("rev-parse", "HEAD")
        else "",
    )

    result = run_click_commands_docs_materializer(
        repo,
        manifest_path=MANIFEST_PATH,
        candidate_artifact_path=_candidate_artifact(tmp_path),
        auxiliary_gap_audit_path=_auxiliary_gap_audit(tmp_path),
        data019_candidate_artifact_path=_data019_candidate_artifact(tmp_path),
        validate=False,
    )
    record = result.to_record()

    assert record["status"] == "materialized"
    assert record["materialization"]["status"] == "materialized"
    assert record["materialization"]["preserved_unrelated_content"] is True
    assert record["materialization"]["sphinx_conf_assignment_count"] == 1
    assert record["materialization"]["sphinx_conf_compile_check_passed"] is True
    assert record["mutation_scope"]["files_changed"] == [
        CLICK_COMMANDS_DOCS_PATH,
        CLICK_DOCS_CONF_PATH,
    ]
    assert record["mutation_scope"]["writes_outside_target"] == []
    assert record["candidate_diff"]["changed_files"] == [
        CLICK_COMMANDS_DOCS_PATH,
        CLICK_DOCS_CONF_PATH,
    ]
    assert "### Multi-value parameters" in record["candidate_diff"]["diff"]
    assert CLICK_DOCS_CONF_ASSIGNMENT in record["candidate_diff"]["diff"]
    assert "src/click/core.py" not in record["mutation_scope"]["files_changed"]
    assert "tests/test_defaults.py" not in record["mutation_scope"]["files_changed"]
    assert record["evidence"]["data014_candidate"]["status"] == "loaded"
    assert record["evidence"]["data017_auxiliary_gap"]["status"] == "loaded"
    assert record["evidence"]["data019_docs_materializer"]["status"] == "loaded"
    action_kinds = {action["kind"] for action in record["actions"]}
    assert "sphinx_conf_scalar_assignment_insert" in action_kinds


def test_materializer_cli_writes_json_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _click_docs_repo(tmp_path)
    out_path = tmp_path / "candidate.json"
    report_path = tmp_path / "report.md"
    monkeypatch.setattr(
        materializer,
        "_git_stdout",
        lambda repo_path, args: CLICK_DEFAULT_MAP_SHA
        if tuple(args) == ("rev-parse", "HEAD")
        else "",
    )

    exit_code = main(
        [
            "--repo-path",
            str(repo),
            "--manifest",
            str(MANIFEST_PATH),
            "--candidate-artifact",
            str(_candidate_artifact(tmp_path)),
            "--auxiliary-gap-audit",
            str(_auxiliary_gap_audit(tmp_path)),
            "--data019-candidate-artifact",
            str(_data019_candidate_artifact(tmp_path)),
            "--out",
            str(out_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    record = json.loads(out_path.read_text(encoding="utf-8"))
    assert record["target_path"] == f"{CLICK_COMMANDS_DOCS_PATH},{CLICK_DOCS_CONF_PATH}"
    assert record["mutation_scope"]["files_changed"] == [
        CLICK_COMMANDS_DOCS_PATH,
        CLICK_DOCS_CONF_PATH,
    ]
    report = report_path.read_text(encoding="utf-8")
    assert "DATA-020 Click Integrated Docs Materializer" in report
    assert "Multi-value parameters" in report
    assert CLICK_DOCS_CONF_ASSIGNMENT in report


def _click_docs_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "click"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (docs / "commands.md").write_text(
        "# Commands\n"
        "\n"
        "Before defaults.\n"
        "\n"
        "## Overriding Defaults\n"
        "\n"
        "A command can define defaults with `default_map`.\n"
        "\n"
        "## Context Defaults\n"
        "\n"
        "Context default docs.\n",
        encoding="utf-8",
    )
    (docs / "conf.py").write_text(
        "extensions = []\n"
        "intersphinx_mapping = {\n"
        '    "python": ("https://docs.python.org/3/", None),\n'
        "}\n"
        "\n"
        "html_theme = 'click'\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "placeholder.py").write_text("# unchanged\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


def _candidate_artifact(tmp_path: Path) -> Path:
    path = tmp_path / "data014-candidate.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-candidate-attempt-v1",
                "record_kind": "issue_pr_candidate_attempt",
                "candidate_id": (
                    "issue-pr-candidate/"
                    "pallets__click-issue-2745-pr-3364/test-fixture"
                ),
                "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
                "repo": "pallets/click",
                "status": "validated",
                "action_family": "click_default_map_multi_value_candidate",
                "residual_labels": [
                    "candidate_validation_passed",
                    "accepted_auxiliary_paths_not_materialized",
                ],
                "mutation_scope": {
                    "files_changed": [
                        "src/click/core.py",
                        "tests/test_defaults.py",
                    ],
                    "materialization_gap_paths": [
                        "CHANGES.rst",
                        "docs/commands.md",
                        "docs/conf.py",
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _data019_candidate_artifact(tmp_path: Path) -> Path:
    path = tmp_path / "data019-candidate.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-docs-materializer-v1",
                "record_kind": "issue_pr_docs_materializer",
                "candidate_id": (
                    "issue-pr-docs-materializer/"
                    "pallets__click-issue-2745-pr-3364/test-fixture"
                ),
                "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
                "repo": "pallets/click",
                "status": "blocked",
                "action_family": (
                    "click_default_map_docs_section_generator_v1+"
                    "myst_markdown_section_insert_v1"
                ),
                "residual_labels": [
                    "docs_commands_section_materialized",
                    "docs_reference_resolution_failure",
                ],
                "mutation_scope": {"files_changed": [CLICK_COMMANDS_DOCS_PATH]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _auxiliary_gap_audit(tmp_path: Path) -> Path:
    path = tmp_path / "data017-audit.jsonl"
    path.write_text(
        json.dumps(
            {
                "schema_version": "issue-pr-auxiliary-gap-audit-v1",
                "record_kind": "issue_pr_auxiliary_gap_audit",
                "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
                "path": CLICK_COMMANDS_DOCS_PATH,
                "classification": "requiring_constrained_local_generator",
                "proposed_action_family": (
                    "click_default_map_docs_section_generator_v1 + "
                    "myst_markdown_section_insert_v1"
                ),
                "validation_cost": {
                    "tier": "moderate",
                    "commands": [
                        "git diff --check",
                        "python -m sphinx -b html docs /tmp/j3-docs",
                    ],
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "schema_version": "issue-pr-auxiliary-gap-audit-v1",
                "record_kind": "issue_pr_auxiliary_gap_audit",
                "replay_id": CLICK_DEFAULT_MAP_REPLAY_ID,
                "path": CLICK_DOCS_CONF_PATH,
                "classification": "covered_by_small_proposed_deterministic_action",
                "proposed_action_family": "sphinx_conf_scalar_assignment_insert_v1",
                "validation_cost": {
                    "tier": "cheap",
                    "commands": ["python -m py_compile docs/conf.py"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
