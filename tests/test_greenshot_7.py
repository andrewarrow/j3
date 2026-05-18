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
    assert summary["built"] == 10
    assert summary["blocked"] == 5
    assert summary["validation_passed"] == 10
    assert summary["validation_failed"] == 0
    assert summary["records_written"] == 15
    assert summary["failures"] == []
    assert len(summary["output_dirs"]) == 10
    assert len(summary["blocked_output_dirs"]) == 5
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
            "task": "slugify_tests_only_existing",
            "category": "action_coverage",
            "domain": "text_slugify",
            "plan_status": "blocked",
            "validation_status": "not_run",
        },
        {
            "task": "slugify_existing_src_convention",
            "category": "existing_repo_support",
            "domain": "text_slugify",
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
            ]
        )

    for output_dir in summary["blocked_output_dirs"]:
        blocked_repo = Path(str(output_dir))
        assert not (blocked_repo / "calculator.py").exists()
        assert not (blocked_repo / "slugify.py").exists()
        assert not (blocked_repo / "kv_parser.py").exists()
        assert not (blocked_repo / "tests/test_calculator_cli.py").exists()

    rows = _jsonl_rows(records_path)
    assert len(rows) == 15
    assert {row["schema_version"] for row in rows} == {"request-repo-attempt-v1"}
    assert {row["record_kind"] for row in rows} == {
        "greenshot_7_request_to_repo_attempt"
    }
    assert {_nested(row, "metadata")["source"] for row in rows} == {"j3 greenshot-7"}

    built_rows = [
        row
        for row in rows
        if _nested(row, "clarification_decision")["status"] == "not_needed"
    ]
    blocked_rows = [
        row
        for row in rows
        if _nested(row, "clarification_decision")["status"] == "blocked"
    ]
    assert len(built_rows) == 10
    assert len(blocked_rows) == 5
    assert all(_nested(row, "build_result")["status"] == "built" for row in built_rows)
    assert all(_nested(row, "validation")["status"] == "passed" for row in built_rows)
    assert all(row["passed"] is True for row in built_rows)
    assert all(
        _nested(row, "build_result")["status"] == "blocked" for row in blocked_rows
    )
    assert all(
        _nested(row, "validation")["reason"] == "blocked_clarification"
        for row in blocked_rows
    )
    assert all(row["passed"] is False for row in blocked_rows)
    assert {_nested(row, "failure_observation")["kind"] for row in blocked_rows} == {
        "blocking_clarification"
    }

    smoke_repo = out_dir / "calculator_short_calc"
    smoke = _run_calculator(smoke_repo, "8", "/", "2")
    assert smoke.returncode == 0, smoke.stderr
    assert smoke.stdout.strip() == "4"

    assert _run_slugify(out_dir / "slugify_library_basic", "Hello, GS7!") == "hello-gs7"
    parser = _run_kv_parser(out_dir / "key_value_parser_basic")
    assert parser.returncode == 0, parser.stderr
    assert "'host': 'localhost'" in parser.stdout
    assert "'port': '5432'" in parser.stdout
