from __future__ import annotations

import json
from pathlib import Path

from j3.local_knowledge import (
    extract_local_knowledge_records,
    validate_local_knowledge_record,
)
from j3.real_repo_tests_planner import (
    TEST_CASE_MATERIALIZATION_BLOCKER,
    plan_real_repo_tests_only_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


def _manifest_iniconfig_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(
        item for item in manifest["repositories"] if item["id"] == "iniconfig"
    )
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == "iniconfig-tests-parse-comments"
    )
    return repo, task


def _write_synthetic_iniconfig_checkout(repo: Path) -> None:
    (repo / "src" / "iniconfig").mkdir(parents=True)
    (repo / "testing").mkdir()
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "iniconfig"
version = "2.0.0"
requires-python = ">=3.8"

[tool.pytest.ini_options]
testpaths = ["testing"]
pythonpath = ["src"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "iniconfig" / "__init__.py").write_text(
        """from __future__ import annotations


class ParseError(ValueError):
    pass


class IniConfig:
    def __init__(self, source: str) -> None:
        self.source = source

    def __getitem__(self, name: str) -> str:
        raise KeyError(name)
""",
        encoding="utf-8",
    )
    (repo / "testing" / "test_iniconfig.py").write_text(
        """from __future__ import annotations

import pytest

from iniconfig import IniConfig, ParseError


@pytest.mark.parametrize(
    "source",
    [
        "[section]\\nkey=value\\n",
        "[other]\\nname=value\\n",
    ],
)
def test_parse_sections(source: str) -> None:
    assert IniConfig(source).source == source


def test_duplicate_keys_report_key_name() -> None:
    with pytest.raises(ParseError, match="key"):
        raise ParseError("duplicate key")
""",
        encoding="utf-8",
    )


def _knowledge_records(
    repo_path: Path,
    repo: dict[str, object],
    task: dict[str, object],
) -> tuple[dict[str, object], ...]:
    return extract_local_knowledge_records(
        repo_path,
        repo_id="iniconfig",
        repo_ref=str(repo["checkout_ref"]),
        split="calibration",
        repo_url=str(repo["upstream"]),
        license=str(repo["license"]),
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=repo["setup_commands"],
        baseline_validation_commands=repo["baseline_validation_commands"],
        tasks=[task],
    )


def test_real_repo_tests_planner_selects_iniconfig_test_file_and_blocks_cases(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_iniconfig_rows()
    _write_synthetic_iniconfig_checkout(tmp_path)
    records = _knowledge_records(tmp_path, repo, task)

    candidate = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    )
    row = candidate.to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["schema_version"] == "real-repo-tests-candidate-v1"
    assert row["record_kind"] == "real_repo_tests_only_candidate"
    assert row["action_family"] == "tests_only_existing_repo_pytest"
    assert row["repo_id"] == "iniconfig"
    assert row["task_id"] == "iniconfig-tests-parse-comments"
    assert row["status"] == "blocked"
    assert row["target_test_file"] == "testing/test_iniconfig.py"
    assert row["validation_commands"] == [
        "python -m pytest testing/test_iniconfig.py -q"
    ]
    assert row["residual_labels"] == [TEST_CASE_MATERIALIZATION_BLOCKER]
    assert row["blockers"] == [
        {
            "field": "test_case_materialization",
            "reason": TEST_CASE_MATERIALIZATION_BLOCKER,
            "message": (
                "repo-state test placement and import style are selected, but "
                "behavior-specific pytest case materialization is not implemented"
            ),
        }
    ]

    assert [action["kind"] for action in row["actions"]] == [
        "inspect_repo_state",
        "select_test_file",
        "select_import_style",
        "materialize_pytest_cases",
        "validate",
    ]
    select_test_file = row["actions"][1]
    assert select_test_file["target"] == "testing/test_iniconfig.py"
    assert select_test_file["payload"]["repo_state_confirmed"] is True
    assert {
        "task.allowed_write_paths",
        "task.public_validation_commands",
        "local_knowledge.validation_recipe_record",
        "local_knowledge.pytest_layout_record",
    } <= set(select_test_file["payload"]["selection_sources"])

    mutation_scope = row["mutation_scope"]
    assert mutation_scope == {
        "mode": "tests_only",
        "planned_write_files": ["testing/test_iniconfig.py"],
        "files_changed": [],
        "production_files": ["src/iniconfig/__init__.py"],
        "production_files_changed": [],
        "writes_outside_allowlist": [],
        "production_files_must_remain_unchanged": True,
    }
    assert row["production_files"] == ["src/iniconfig/__init__.py"]
    assert set(row["production_file_hashes_before"]) == {
        "src/iniconfig/__init__.py"
    }

    validation = row["validation"]
    assert validation == {
        "status": "not_run",
        "commands": ["python -m pytest testing/test_iniconfig.py -q"],
        "selected_command": "python -m pytest testing/test_iniconfig.py -q",
        "not_run_reason": TEST_CASE_MATERIALIZATION_BLOCKER,
        "candidate_validation_network_allowed": False,
    }


def test_real_repo_tests_planner_cites_import_style_and_knowledge_use(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_iniconfig_rows()
    _write_synthetic_iniconfig_checkout(tmp_path)
    records = _knowledge_records(tmp_path, repo, task)
    record_ids_by_type: dict[str, list[str]] = {}
    for record in records:
        record_ids_by_type.setdefault(str(record["record_type"]), []).append(
            str(record["id"])
        )

    row = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()

    import_evidence = row["import_style_evidence"]
    assert {
        ("__future__", "annotations"),
        ("pytest", None),
        ("iniconfig", "IniConfig"),
        ("iniconfig", "ParseError"),
    } <= {
        (item["module"], item["imported"])
        for item in import_evidence["repo_state_imports"]
    }
    assert import_evidence["selected_public_imports"] == [
        {
            "path": "testing/test_iniconfig.py",
            "module": "iniconfig",
            "imported": "IniConfig",
            "level": 0,
            "line": 5,
        },
        {
            "path": "testing/test_iniconfig.py",
            "module": "iniconfig",
            "imported": "ParseError",
            "level": 0,
            "line": 5,
        },
    ]
    assert import_evidence["local_knowledge_import_examples"] == [
        {
            "path": "testing/test_iniconfig.py",
            "import": "iniconfig",
            "names": ["IniConfig", "ParseError"],
            "kind": "from_import",
        }
    ]

    citations = row["knowledge_citations"]
    assert set(citations) == {
        "import_style",
        "pytest_style",
        "test_location",
        "validation",
    }
    assert set(citations["validation"]) <= set(
        record_ids_by_type["validation_recipe_record"]
    )
    assert set(citations["import_style"]) <= set(
        record_ids_by_type["public_api_record"]
    )

    knowledge_use = row["knowledge_use_record"]
    assert isinstance(knowledge_use, dict)
    validate_local_knowledge_record(knowledge_use)
    assert knowledge_use["record_type"] == "knowledge_use_record"
    assert knowledge_use["data"]["candidate_id"] == row["candidate_id"]
    assert knowledge_use["data"]["action_family"] == (
        "tests_only_existing_repo_pytest"
    )
    assert knowledge_use["data"]["validation_result"] == {
        "status": "blocked",
        "command": "python -m pytest testing/test_iniconfig.py -q",
        "reason": TEST_CASE_MATERIALIZATION_BLOCKER,
    }
    assert knowledge_use["data"]["cited_purposes"] == citations
