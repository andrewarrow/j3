from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from j3.greenshot_7 import run_greenshot_7_tasks


TASKS_PATH = Path("examples/greenshot_7/tasks.json")


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _run_calculator(repo: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "calculator.py"), *argv],
        text=True,
        capture_output=True,
        check=False,
    )


def _run_slugify(repo: Path, text: str) -> str:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from slugify import slugify; import sys; print(slugify(sys.argv[1]))",
            text,
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _run_kv_parser(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from kv_parser import parse_key_value_lines; "
                "print(parse_key_value_lines('host=localhost\\n# skip\\nport=5432'))"
            ),
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def _nested(row: dict[str, object], key: str) -> dict[str, object]:
    value = row[key]
    assert isinstance(value, dict)
    return value


def test_run_greenshot_7_tasks_builds_validates_and_records(tmp_path: Path) -> None:
    out_dir = tmp_path / "gs7"
    records_path = tmp_path / "records.jsonl"

    summary = run_greenshot_7_tasks(TASKS_PATH, out_dir, records_path)

    assert summary["total"] == 15
    assert summary["built"] == 12
    assert summary["existing_repo_tests_built"] == 1
    assert summary["existing_repo_conventions_built"] == 1
    assert summary["blocked"] == 3
    assert summary["validation_passed"] == 12
    assert summary["validation_failed"] == 0
    assert summary["records_written"] == 15
    assert summary["failures"] == []
    assert len(summary["output_dirs"]) == 12
    assert len(summary["blocked_output_dirs"]) == 3
    assert summary["classified_failures"] == [
        {
            "task": "math_tool_unclear",
            "category": "expected_clarification",
            "domain": "unknown",
            "plan_status": "blocked",
            "validation_status": "not_run",
        },
        {
            "task": "calculator_scientific_unclear",
            "category": "expected_clarification",
            "domain": "calculator",
            "plan_status": "blocked",
            "validation_status": "not_run",
        },
        {
            "task": "file_converter_unclear",
            "category": "expected_clarification",
            "domain": "unknown",
            "plan_status": "blocked",
            "validation_status": "not_run",
        },
    ]

    for output_dir in summary["output_dirs"]:
        repo = Path(str(output_dir))
        assert any(
            [
                (repo / "calculator.py").exists(),
                (repo / "slugify.py").exists(),
                (repo / "kv_parser.py").exists(),
                (repo / "src/acme_slug/text.py").exists(),
            ]
        )

    for output_dir in summary["blocked_output_dirs"]:
        blocked_repo = Path(str(output_dir))
        assert not (blocked_repo / "calculator.py").exists()
        assert not (blocked_repo / "slugify.py").exists()
        assert not (blocked_repo / "kv_parser.py").exists()
        assert not (blocked_repo / "src/acme_slug/text.py").exists()
        assert not (blocked_repo / "tests/test_calculator_cli.py").exists()

    tasks = {str(task["name"]): task for task in json.loads(TASKS_PATH.read_text())}
    fixture = tasks["slugify_tests_only_existing"]["existing_repo_fixture"]
    fixture_files = fixture["files"]  # type: ignore[index]
    fixture_source = fixture_files[0]["content"]  # type: ignore[index]
    existing_slugify_repo = out_dir / "slugify_tests_only_existing"
    assert (existing_slugify_repo / "slugify.py").read_text(encoding="utf-8") == (
        fixture_source
    )
    assert (existing_slugify_repo / "tests/test_slugify.py").exists()
    convention_repo = out_dir / "slugify_existing_src_convention"
    assert (convention_repo / "src/acme_slug/text.py").exists()
    init_text = (convention_repo / "src/acme_slug/__init__.py").read_text(
        encoding="utf-8"
    )
    assert "from .text import slugify" in init_text
    assert '__all__ = ["slugify"]' in init_text

    rows = _jsonl_rows(records_path)
    assert len(rows) == 15
    assert {row["record_kind"] for row in rows} == {
        "greenshot_7_existing_repo_convention_attempt",
        "greenshot_7_existing_repo_tests_attempt",
        "greenshot_7_request_to_repo_attempt",
    }
    assert {_nested(row, "metadata")["source"] for row in rows} == {"j3 greenshot-7"}

    request_rows = [
        row
        for row in rows
        if row["record_kind"] == "greenshot_7_request_to_repo_attempt"
    ]
    tests_only_rows = [
        row
        for row in rows
        if row["record_kind"] == "greenshot_7_existing_repo_tests_attempt"
    ]
    convention_rows = [
        row
        for row in rows
        if row["record_kind"] == "greenshot_7_existing_repo_convention_attempt"
    ]
    assert len(request_rows) == 13
    assert len(tests_only_rows) == 1
    assert len(convention_rows) == 1

    built_rows = [
        row
        for row in request_rows
        if _nested(row, "clarification_decision")["status"] == "not_needed"
    ]
    blocked_rows = [
        row
        for row in request_rows
        if _nested(row, "clarification_decision")["status"] == "blocked"
    ]
    assert len(built_rows) == 10
    assert len(blocked_rows) == 3
    assert all(_nested(row, "build_result")["status"] == "built" for row in built_rows)
    assert all(_nested(row, "validation")["status"] == "passed" for row in built_rows)
    assert all(row["passed"] is True for row in built_rows)
    assert all(
        _nested(row, "build_result")["status"] == "blocked" for row in blocked_rows
    )
    assert all(
        _nested(row, "clarification_response")["status"] == "needs_clarification"
        for row in blocked_rows
    )
    assert all(
        _nested(row, "clarification_response")["questions"]
        == _nested(row, "build_result")["clarification_response"]["questions"]
        for row in blocked_rows
    )
    assert all(
        _nested(row, "validation")["reason"] == "blocked_clarification"
        for row in blocked_rows
    )
    assert all(row["passed"] is False for row in blocked_rows)
    assert {_nested(row, "failure_observation")["kind"] for row in blocked_rows} == {
        "blocking_clarification"
    }
    assert all(
        _nested(row, "failure_observation")["clarification_response"]
        == _nested(row, "clarification_response")
        for row in blocked_rows
    )

    tests_row = tests_only_rows[0]
    assert tests_row["schema_version"] == "existing-repo-tests-attempt-v1"
    assert tests_row["passed"] is True
    assert tests_row["failure_observation"] is None
    request_spec = _nested(tests_row, "normalized_request_spec")
    assert request_spec["task_type"] == "add_tests"
    assert request_spec["repo_mode"] == "existing_repo"
    tests_spec = _nested(tests_row, "existing_repo_tests_spec")
    assert tests_spec["target_test_files"] == ["tests/test_slugify.py"]
    assert tests_spec["production_files"] == ["slugify.py"]
    assert tests_spec["change_policy"] == {
        "mode": "tests_only",
        "production_files_must_remain_unchanged": True,
    }
    assert [action["kind"] for action in tests_row["existing_repo_actions"]] == [
        "inspect_repo",
        "inspect_one_file_library",
        "add_existing_repo_tests",
        "validate",
    ]
    tests_result = _nested(tests_row, "tests_result")
    assert tests_result["status"] == "validated"
    assert tests_result["files_changed"] == ["tests/test_slugify.py"]
    assert tests_result["target_test_files"] == ["tests/test_slugify.py"]
    assert tests_result["production_files"] == ["slugify.py"]
    assert tests_result["production_files_changed"] == []
    assert tests_row["changed_files"] == ["tests/test_slugify.py"]
    assert tests_row["production_files_changed"] == []
    assert _nested(tests_row, "validation")["status"] == "passed"

    convention_row = convention_rows[0]
    assert convention_row["schema_version"] == "existing-repo-convention-attempt-v1"
    assert convention_row["passed"] is True
    assert convention_row["failure_observation"] is None
    convention_spec = _nested(convention_row, "existing_repo_convention_spec")
    assert convention_spec["source_edit_files"] == ["src/acme_slug/__init__.py"]
    assert convention_spec["protected_source_files"] == ["src/acme_slug/text.py"]
    assert [action["kind"] for action in convention_row["existing_repo_actions"]] == [
        "inspect_repo",
        "inspect_src_package_layout",
        "add_package_export",
        "validate",
    ]
    convention_result = _nested(convention_row, "convention_result")
    assert convention_result["status"] == "validated"
    assert convention_result["files_changed"] == ["src/acme_slug/__init__.py"]
    assert convention_result["source_files_changed"] == ["src/acme_slug/__init__.py"]
    assert convention_result["protected_source_files_changed"] == []
    assert convention_row["changed_files"] == ["src/acme_slug/__init__.py"]
    assert convention_row["validation_commands"] == [
        "python -m pytest tests/test_acme_slug.py -q"
    ]
    assert _nested(convention_row, "repo_state_evidence_used")["source_root"] == "src"
    assert _nested(convention_row, "source_edit_scope") == {
        "mode": "package_export_only",
        "allowed_source_files": ["src/acme_slug/__init__.py"],
        "protected_source_files": ["src/acme_slug/text.py"],
        "max_source_files_changed": 1,
    }
    assert _nested(convention_row, "validation")["status"] == "passed"

    smoke_repo = out_dir / "calculator_short_calc"
    smoke = _run_calculator(smoke_repo, "8", "/", "2")
    assert smoke.returncode == 0, smoke.stderr
    assert smoke.stdout.strip() == "4"

    assert _run_slugify(out_dir / "slugify_library_basic", "Hello, GS7!") == "hello-gs7"
    parser = _run_kv_parser(out_dir / "key_value_parser_basic")
    assert parser.returncode == 0, parser.stderr
    assert "'host': 'localhost'" in parser.stdout
    assert "'port': '5432'" in parser.stdout
