from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.existing_repo_tests import (
    ExistingRepoTestsError,
    apply_existing_repo_tests,
    blocker_from_error,
    existing_repo_tests_attempt_row,
    existing_repo_tests_spec_from_request,
    inspect_slugify_one_file_repo,
    plan_existing_repo_tests,
)
from j3.request_spec import parse_request_to_spec


SLUGIFY_SOURCE_TEXT = (
    '"""Small text slugification helpers for documentation paths."""\n'
    "\n"
    "from __future__ import annotations\n"
    "\n"
    "import re\n"
    "\n"
    "\n"
    "def slugify(text: str) -> str:\n"
    '    """Return a lowercase, hyphen-separated slug for text."""\n'
    "\n"
    r'    parts = re.findall(r"[a-z0-9]+", text.lower())' + "\n"
    '    return "-".join(parts)\n'
)


def _write_slugify_repo(repo: Path) -> None:
    (repo / "slugify.py").write_text(SLUGIFY_SOURCE_TEXT, encoding="utf-8")


def _tests_only_request():
    return parse_request_to_spec(
        "add pytest coverage for an existing slugify.py library without changing implementation",
        task_name="slugify_tests_only_existing",
    )


def test_plan_existing_repo_tests_inspects_one_file_slugify_repo(
    tmp_path: Path,
) -> None:
    _write_slugify_repo(tmp_path)
    request_spec = _tests_only_request()
    tests_spec = existing_repo_tests_spec_from_request(request_spec)

    plan = plan_existing_repo_tests(tests_spec, tmp_path)
    record = plan.to_record()

    assert json.loads(json.dumps(record)) == record
    assert record["schema_version"] == "existing-repo-tests-plan-v1"
    assert record["task_type"] == "add_tests"
    assert record["repo_mode"] == "existing_repo"
    assert record["domain"] == "text_slugify"
    assert record["source_files"] == ["slugify.py"]
    assert record["target_test_files"] == ["tests/test_slugify.py"]
    assert record["production_files"] == ["slugify.py"]
    assert [action["kind"] for action in record["actions"]] == [
        "inspect_repo",
        "inspect_one_file_library",
        "add_existing_repo_tests",
        "validate",
    ]
    assert record["actions"][1]["payload"]["public_callable"] == "slugify"  # type: ignore[index]
    assert record["actions"][2]["target"] == "tests/test_slugify.py"  # type: ignore[index]
    assert record["actions"][2]["payload"]["write_policy"] == (  # type: ignore[index]
        "create_or_refine_test_file_only"
    )
    assert record["validation"] == {
        "commands": ["python -m pytest tests/test_slugify.py -q"],
        "hidden_cases": True,
    }


def test_apply_existing_repo_tests_writes_tests_only_and_records_outcome(
    tmp_path: Path,
) -> None:
    _write_slugify_repo(tmp_path)
    source_before = (tmp_path / "slugify.py").read_bytes()
    request_spec = _tests_only_request()
    tests_spec = existing_repo_tests_spec_from_request(request_spec)
    plan = plan_existing_repo_tests(tests_spec, tmp_path)

    result = apply_existing_repo_tests(plan, tmp_path)

    assert result.status == "validated"
    assert result.files_changed == ["tests/test_slugify.py"]
    assert result.target_test_files == ["tests/test_slugify.py"]
    assert result.production_files == ["slugify.py"]
    assert result.production_files_changed == []
    assert result.validation["status"] == "passed"
    assert result.validation["command"] == "python -m pytest tests/test_slugify.py -q"
    assert (tmp_path / "slugify.py").read_bytes() == source_before
    assert 'from slugify import slugify' in (
        tmp_path / "tests/test_slugify.py"
    ).read_text(encoding="utf-8")

    row = existing_repo_tests_attempt_row(
        raw_prompt=request_spec.prompt,
        request_spec=request_spec,
        spec=tests_spec,
        plan=plan,
        result=result,
        source="test",
    )

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["schema_version"] == "existing-repo-tests-attempt-v1"
    assert row["record_kind"] == "greenshot_7_existing_repo_tests_attempt"
    assert row["normalized_request_spec"]["task_type"] == "add_tests"  # type: ignore[index]
    assert row["existing_repo_tests_spec"]["change_policy"] == {  # type: ignore[index]
        "mode": "tests_only",
        "production_files_must_remain_unchanged": True,
    }
    assert row["changed_files"] == ["tests/test_slugify.py"]
    assert row["target_test_files"] == ["tests/test_slugify.py"]
    assert row["production_files"] == ["slugify.py"]
    assert row["production_files_changed"] == []
    assert row["passed"] is True
    assert row["failure_observation"] is None


def test_inspect_slugify_repo_reports_precise_missing_repo_state(
    tmp_path: Path,
) -> None:
    with pytest.raises(ExistingRepoTestsError) as caught:
        inspect_slugify_one_file_repo(tmp_path)

    blocker = blocker_from_error(caught.value)
    assert blocker == {
        "field": "repo_state",
        "reason": "missing_repo_state",
        "message": "missing one-file slugify library: expected slugify.py",
    }
