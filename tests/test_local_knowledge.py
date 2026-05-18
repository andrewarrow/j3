from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.local_knowledge import (
    build_knowledge_use_record,
    extract_local_knowledge_records,
    validate_local_knowledge_record,
    write_local_knowledge_jsonl,
)


def _write_calibration_repo(repo: Path) -> None:
    (repo / "src" / "mini_lib").mkdir(parents=True)
    (repo / "testing").mkdir()
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "mini-lib"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
tests = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["testing"]
pythonpath = ["src"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "mini_lib" / "__init__.py").write_text(
        """from __future__ import annotations

from .slug import slugify

__all__ = ["slugify"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "mini_lib" / "slug.py").write_text(
        """from __future__ import annotations


def slugify(text: str) -> str:
    return "-".join(text.lower().split())
""",
        encoding="utf-8",
    )
    (repo / "testing" / "test_slug.py").write_text(
        """from __future__ import annotations

import pytest

from mini_lib import slugify


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello World", "hello-world"),
        ("Already slugged", "already-slugged"),
    ],
)
def test_slugify_cases(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_rejects_none() -> None:
    with pytest.raises(AttributeError):
        slugify(None)  # type: ignore[arg-type]
""",
        encoding="utf-8",
    )


def _tasks() -> list[dict[str, object]]:
    return [
        {
            "id": "mini-lib-tests-slugify",
            "task_type": "tests_only",
            "allowed_write_paths": ["testing/test_slug.py"],
            "public_validation_commands": [
                "python -m pytest testing/test_slug.py -q"
            ],
            "expected_failure_modes": ["wrong_test_location"],
        }
    ]


def test_extract_local_knowledge_records_emit_wedge_record_families(
    tmp_path: Path,
) -> None:
    _write_calibration_repo(tmp_path)

    records = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        repo_url="https://example.invalid/mini-lib",
        license="MIT",
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=["python -m pip install -e '.[tests]'"],
        baseline_validation_commands=["python -m pytest testing -q"],
        tasks=_tasks(),
        outcome_ids_by_task={
            "mini-lib-tests-slugify": ["real_repo_preflight/mini-lib-tests-slugify"]
        },
    )

    for record in records:
        validate_local_knowledge_record(record)
        assert json.loads(json.dumps(record, sort_keys=True)) == record
        assert record["split"] == "calibration"
        assert record["extracted_by"] == "local_knowledge/v1"
        assert len(record["provenance_hash"]) == 64

    by_type: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_type.setdefault(str(record["record_type"]), []).append(record)

    assert {
        "packaging_layout_record",
        "pytest_layout_record",
        "public_api_record",
        "validation_recipe_record",
        "pytest_pattern_record",
    } <= set(by_type)

    packaging = by_type["packaging_layout_record"][0]["data"]
    assert isinstance(packaging, dict)
    assert packaging["layout_kind"] == "src"
    assert packaging["source_roots"] == ["src"]
    assert packaging["package_roots"] == [
        {"package": "mini_lib", "path": "src/mini_lib", "source_root": "src"}
    ]
    assert packaging["build_backend"] == "setuptools.build_meta"

    pytest_layout = by_type["pytest_layout_record"][0]["data"]
    assert isinstance(pytest_layout, dict)
    assert pytest_layout["test_roots"] == ["testing"]
    assert pytest_layout["naming_patterns"] == {
        "files": ["test_*.py", "*_test.py"],
        "functions": ["test_*"],
        "classes": ["Test*"],
    }

    public_api = by_type["public_api_record"][0]["data"]
    assert isinstance(public_api, dict)
    assert public_api["module"] == "mini_lib"
    assert public_api["exported_names"] == ["slugify"]
    assert public_api["explicit_all"] == ["slugify"]
    assert public_api["test_import_examples"] == [
        {
            "path": "testing/test_slug.py",
            "import": "mini_lib",
            "names": ["slugify"],
            "kind": "from_import",
        }
    ]

    validation = by_type["validation_recipe_record"][0]
    assert validation["links"] == {
        "task_ids": ["mini-lib-tests-slugify"],
        "outcome_ids": ["real_repo_preflight/mini-lib-tests-slugify"],
        "residual_labels": ["wrong_test_location"],
    }
    validation_data = validation["data"]
    assert isinstance(validation_data, dict)
    assert validation_data["focused_commands"] == [
        "python -m pytest testing/test_slug.py -q"
    ]
    assert validation_data["allowed_write_paths"] == ["testing/test_slug.py"]

    pattern_data = [record["data"] for record in by_type["pytest_pattern_record"]]
    assert any(
        isinstance(data, dict)
        and data["pattern_kind"] == "parametrize"
        and data["decorator_shape"]["parametrize"]["arg_names"] == [  # type: ignore[index]
            "text",
            "expected",
        ]
        and data["decorator_shape"]["parametrize"]["case_count"] == 2  # type: ignore[index]
        for data in pattern_data
    )


def test_local_knowledge_jsonl_and_use_record_are_stable(tmp_path: Path) -> None:
    _write_calibration_repo(tmp_path)

    first = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        tasks=_tasks(),
    )
    second = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        tasks=_tasks(),
    )
    assert [record["id"] for record in first] == [record["id"] for record in second]

    record_ids_by_type = {record["record_type"]: record["id"] for record in first}
    use_record = build_knowledge_use_record(
        candidate_id="candidate-tests-only-001",
        task_id="mini-lib-tests-slugify",
        retrieved_record_ids=[
            str(record_ids_by_type["pytest_layout_record"]),
            str(record_ids_by_type["packaging_layout_record"]),
            str(record_ids_by_type["public_api_record"]),
            str(record_ids_by_type["validation_recipe_record"]),
        ],
        cited_purposes={
            "test_location": [str(record_ids_by_type["pytest_layout_record"])],
            "import_style": [str(record_ids_by_type["public_api_record"])],
            "validation": [str(record_ids_by_type["validation_recipe_record"])],
        },
        action_family="tests_only_existing_repo_pytest",
        validation_result={
            "status": "passed",
            "command": "python -m pytest testing/test_slug.py -q",
        },
        outcome_id="greenshot_7_existing_repo_tests_attempt/demo",
    )
    validate_local_knowledge_record(use_record)

    output = write_local_knowledge_jsonl([*first, use_record], tmp_path / "records.jsonl")
    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == len(first) + 1
    assert rows[-1]["record_type"] == "knowledge_use_record"
    assert rows[-1]["data"]["action_family"] == "tests_only_existing_repo_pytest"
    assert rows[-1]["links"]["task_ids"] == ["mini-lib-tests-slugify"]


def test_local_knowledge_validation_rejects_raw_source_blobs(
    tmp_path: Path,
) -> None:
    _write_calibration_repo(tmp_path)
    record = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        tasks=_tasks(),
    )[0]
    broken = dict(record)
    broken["data"] = {"raw_source": "def leaked() -> None: pass"}

    with pytest.raises(ValueError, match="raw source blobs"):
        validate_local_knowledge_record(broken)
