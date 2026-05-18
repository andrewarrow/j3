from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.existing_repo_conventions import (
    ExistingRepoConventionError,
    apply_existing_repo_convention,
    blocker_from_error,
    existing_repo_convention_attempt_row,
    existing_repo_convention_spec_from_request,
    inspect_slugify_src_convention_repo,
    plan_existing_repo_convention,
)
from j3.request_spec import parse_request_to_spec


SLUGIFY_TEXT = (
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


def _write_src_slugify_repo(repo: Path, *, include_validation: bool = True) -> None:
    (repo / "src/acme_slug").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme-slug"\n'
        'version = "0.1.0"\n'
        "\n"
        "[tool.pytest.ini_options]\n"
        'pythonpath = ["src"]\n',
        encoding="utf-8",
    )
    (repo / "src/acme_slug/__init__.py").write_text(
        '"""Public package exports for acme_slug."""\n',
        encoding="utf-8",
    )
    (repo / "src/acme_slug/text.py").write_text(SLUGIFY_TEXT, encoding="utf-8")
    if include_validation:
        (repo / "tests/test_acme_slug.py").write_text(
            "from __future__ import annotations\n"
            "\n"
            "from acme_slug import slugify\n"
            "\n"
            "\n"
            "def test_package_exports_slugify() -> None:\n"
            '    assert slugify("Hello, Src Layout!") == "hello-src-layout"\n',
            encoding="utf-8",
        )


def _convention_request():
    return parse_request_to_spec(
        "update an existing src/acme_slug/text.py module to expose slugify "
        "in __init__.py following the repo's src layout",
        task_name="slugify_existing_src_convention",
    )


def test_plan_existing_repo_convention_uses_repo_state_coverage(
    tmp_path: Path,
) -> None:
    _write_src_slugify_repo(tmp_path)
    request_spec = _convention_request()
    convention_spec = existing_repo_convention_spec_from_request(request_spec)

    plan = plan_existing_repo_convention(convention_spec, tmp_path)
    record = plan.to_record()

    assert json.loads(json.dumps(record)) == record
    assert record["schema_version"] == "existing-repo-convention-plan-v1"
    assert record["task_type"] == "modify_library"
    assert record["repo_mode"] == "existing_repo"
    assert record["domain"] == "text_slugify"
    assert record["source_edit_files"] == ["src/acme_slug/__init__.py"]
    assert record["protected_source_files"] == ["src/acme_slug/text.py"]
    assert [action["kind"] for action in record["actions"]] == [
        "inspect_repo",
        "inspect_src_package_layout",
        "add_package_export",
        "validate",
    ]

    coverage = record["actions"][0]["payload"]["repo_state_coverage"]  # type: ignore[index]
    coverage_files = {item["path"]: item["roles"] for item in coverage["files"]}  # type: ignore[index]
    assert coverage_files["src/acme_slug/__init__.py"] == ["python"]
    assert coverage_files["src/acme_slug/text.py"] == ["python"]
    assert coverage_files["tests/test_acme_slug.py"] == ["python", "test"]
    assert record["repo_state_evidence"]["package"] == {  # type: ignore[index]
        "name": "src.acme_slug",
        "path": "src/acme_slug",
    }
    assert record["repo_state_evidence"]["public_export_validation_imports"] == [  # type: ignore[index]
        {
            "path": "tests/test_acme_slug.py",
            "module": "acme_slug",
            "imported": "slugify",
            "level": 0,
            "line": 3,
        }
    ]


def test_apply_existing_repo_convention_edits_only_package_export(
    tmp_path: Path,
) -> None:
    _write_src_slugify_repo(tmp_path)
    module_before = (tmp_path / "src/acme_slug/text.py").read_bytes()
    request_spec = _convention_request()
    convention_spec = existing_repo_convention_spec_from_request(request_spec)
    plan = plan_existing_repo_convention(convention_spec, tmp_path)

    result = apply_existing_repo_convention(plan, tmp_path)

    assert result.status == "validated"
    assert result.files_changed == ["src/acme_slug/__init__.py"]
    assert result.source_files_changed == ["src/acme_slug/__init__.py"]
    assert result.protected_source_files_changed == []
    assert result.validation["status"] == "passed"
    assert result.validation["command"] == "python -m pytest tests/test_acme_slug.py -q"
    assert (tmp_path / "src/acme_slug/text.py").read_bytes() == module_before
    init_text = (tmp_path / "src/acme_slug/__init__.py").read_text(encoding="utf-8")
    assert "from .text import slugify" in init_text
    assert '__all__ = ["slugify"]' in init_text

    row = existing_repo_convention_attempt_row(
        raw_prompt=request_spec.prompt,
        request_spec=request_spec,
        spec=convention_spec,
        plan=plan,
        result=result,
        source="test",
    )

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["schema_version"] == "existing-repo-convention-attempt-v1"
    assert row["record_kind"] == "greenshot_7_existing_repo_convention_attempt"
    assert row["changed_files"] == ["src/acme_slug/__init__.py"]
    assert row["source_files_changed"] == ["src/acme_slug/__init__.py"]
    assert row["protected_source_files_changed"] == []
    assert row["validation_commands"] == ["python -m pytest tests/test_acme_slug.py -q"]
    assert row["source_edit_scope"] == {
        "mode": "package_export_only",
        "allowed_source_files": ["src/acme_slug/__init__.py"],
        "protected_source_files": ["src/acme_slug/text.py"],
        "max_source_files_changed": 1,
    }
    assert row["repo_state_evidence_used"]["source_root"] == "src"  # type: ignore[index]
    assert row["passed"] is True
    assert row["failure_observation"] is None


def test_inspect_slugify_src_convention_reports_missing_validation_layer(
    tmp_path: Path,
) -> None:
    _write_src_slugify_repo(tmp_path, include_validation=False)

    with pytest.raises(ExistingRepoConventionError) as caught:
        inspect_slugify_src_convention_repo(tmp_path)

    blocker = blocker_from_error(caught.value)
    assert blocker == {
        "field": "validation",
        "reason": "missing_validation_layer",
        "message": (
            "missing required src-layout convention files: tests/test_acme_slug.py"
        ),
    }
