from __future__ import annotations

import json
from pathlib import Path

from j3.local_knowledge import (
    extract_local_knowledge_records,
    validate_local_knowledge_record,
)
from j3.real_repo_tests_planner import (
    CANDIDATE_VALIDATION_DEFERRED,
    REQUIRED_KNOWLEDGE_PURPOSES,
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


def _manifest_h11_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(item for item in manifest["repositories"] if item["id"] == "h11")
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == "h11-tests-bytesify-memoryview"
    )
    return repo, task


def _manifest_humanize_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(
        item for item in manifest["repositories"] if item["id"] == "humanize"
    )
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == "humanize-tests-naturalsize-negative-strings"
    )
    return repo, task


def _manifest_boltons_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(item for item in manifest["repositories"] if item["id"] == "boltons")
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == "boltons-tests-slugify-delimiter"
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
    def __init__(self, path: str, lineno: int, msg: str) -> None:
        super().__init__(path, lineno, msg)
        self.path = path
        self.lineno = lineno
        self.msg = msg

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno + 1}: {self.msg}"


class IniConfig:
    def __init__(self, source: str, data: str | None = None) -> None:
        self.source = source
        self.sections = _parse_sections(source, data) if data is not None else {}

    def __getitem__(self, name: str) -> str:
        return self.sections[name]


def _parse_sections(path: str, data: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    for lineno, raw_line in enumerate(data.splitlines()):
        line = raw_line.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            section_line = line
            for marker in "#;":
                section_line = section_line.split(marker)[0].rstrip()
            current = section_line[1:-1]
            sections[current] = {}
            continue
        if current is None:
            raise ParseError(path, lineno, "no section header defined")
        name, value = line.split("=", 1)
        key = name.strip()
        if key in sections[current]:
            raise ParseError(path, lineno, f"duplicate name {key!r}")
        sections[current][key] = value.strip()
    return sections
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


def _write_synthetic_h11_checkout(repo: Path) -> None:
    (repo / "h11" / "tests").mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "h11"
version = "0.14.0"
requires-python = ">=3.8"
""",
        encoding="utf-8",
    )
    (repo / "h11" / "__init__.py").write_text(
        """from __future__ import annotations

from ._util import bytesify

__all__ = ["bytesify"]
""",
        encoding="utf-8",
    )
    (repo / "h11" / "_util.py").write_text(
        """from __future__ import annotations


def bytesify(value: bytes | bytearray | memoryview | int | str) -> bytes:
    if type(value) is bytes:
        return value
    if isinstance(value, str):
        value = value.encode("ascii")
    if isinstance(value, int):
        raise TypeError("expected bytes-like object, not int")
    return bytes(value)
""",
        encoding="utf-8",
    )
    (repo / "h11" / "tests" / "test_util.py").write_text(
        """import pytest

from .._util import bytesify


def test_bytesify() -> None:
    assert bytesify(b"123") == b"123"
    assert bytesify(bytearray(b"123")) == b"123"
    assert bytesify("123") == b"123"

    with pytest.raises(UnicodeEncodeError):
        bytesify("\\u1234")

    with pytest.raises(TypeError):
        bytesify(10)
""",
        encoding="utf-8",
    )


def _write_synthetic_humanize_checkout(repo: Path) -> None:
    (repo / "src" / "humanize").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "humanize"
version = "4.9.0"
requires-python = ">=3.8"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "humanize" / "__init__.py").write_text(
        """from __future__ import annotations

from .filesize import naturalsize

__all__ = ["naturalsize"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "humanize" / "filesize.py").write_text(
        """from __future__ import annotations

from math import log

suffixes = {
    "decimal": ("kB", "MB", "GB"),
    "binary": ("KiB", "MiB", "GiB"),
    "gnu": "KMG",
}


def naturalsize(
    value: float | str,
    binary: bool = False,
    gnu: bool = False,
    format: str = "%.1f",
) -> str:
    suffix = (
        suffixes["gnu"]
        if gnu
        else suffixes["binary"]
        if binary
        else suffixes["decimal"]
    )
    base = 1024 if (gnu or binary) else 1000
    bytes_ = float(value)
    abs_bytes = abs(bytes_)
    if abs_bytes == 1 and not gnu:
        return "%d Byte" % int(bytes_)
    if abs_bytes < base:
        return f"{int(bytes_)}B" if gnu else "%d Bytes" % int(bytes_)
    exp = int(min(log(abs_bytes, base), len(suffix)))
    space = "" if gnu else " "
    return format % (bytes_ / (base**exp)) + space + suffix[exp - 1]
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_filesize.py").write_text(
        """from __future__ import annotations

import pytest

import humanize


@pytest.mark.parametrize(
    "test_args, expected",
    [
        ([300], "300 Bytes"),
        (["1000"], "1.0 kB"),
        ([1024, True], "1.0 KiB"),
        ([1024, False, True], "1.0K"),
    ],
)
def test_naturalsize(test_args: list[object], expected: str) -> None:
    assert humanize.naturalsize(*test_args) == expected
""",
        encoding="utf-8",
    )


def _write_synthetic_boltons_checkout(repo: Path) -> None:
    (repo / "boltons").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "boltons"
version = "23.1.0"
requires-python = ">=3.8"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
        encoding="utf-8",
    )
    (repo / "boltons" / "__init__.py").write_text(
        """from __future__ import annotations
""",
        encoding="utf-8",
    )
    (repo / "boltons" / "strutils.py").write_text(
        """from __future__ import annotations

import re
import unicodedata

_punct_re = re.compile(r"[\\W_]+")


def asciify(text: str) -> bytes:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore")


def split_punct_ws(text: str) -> list[str]:
    return [word for word in _punct_re.split(text) if word]


def slugify(
    text: str, delim: str = "_", lower: bool = True, ascii: bool = False
) -> str | bytes:
    ret = delim.join(split_punct_ws(text)) or delim if text else ""
    if ascii:
        ret = asciify(ret)
    if lower:
        ret = ret.lower()
    return ret
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_strutils.py").write_text(
        """from __future__ import annotations

import pytest

from boltons import strutils


@pytest.mark.parametrize(
    ("text", "expected"),
    [("First post! Hi!!!!~1    ", "first_post_hi_1")],
)
def test_slugify_default_delimiter(text: str, expected: str) -> None:
    assert strutils.slugify(text) == expected
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
        repo_id=str(repo["id"]),
        repo_ref=str(repo["checkout_ref"]),
        split=str(repo["split"]),
        repo_url=str(repo["upstream"]),
        license=str(repo["license"]),
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=repo["setup_commands"],
        baseline_validation_commands=repo["baseline_validation_commands"],
        tasks=[task],
    )


def test_real_repo_tests_planner_materializes_iniconfig_test_cases(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_iniconfig_rows()
    _write_synthetic_iniconfig_checkout(tmp_path)
    source_before = (tmp_path / "src" / "iniconfig" / "__init__.py").read_bytes()
    test_before = (tmp_path / "testing" / "test_iniconfig.py").read_text(
        encoding="utf-8"
    )
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
    assert row["status"] == "materialized"
    assert row["target_test_file"] == "testing/test_iniconfig.py"
    assert row["validation_commands"] == [
        "python -m pytest testing/test_iniconfig.py -q"
    ]
    assert row["residual_labels"] == [CANDIDATE_VALIDATION_DEFERRED]
    assert row["blockers"] == []

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
    assert mutation_scope["mode"] == "tests_only"
    assert mutation_scope["planned_write_files"] == ["testing/test_iniconfig.py"]
    assert mutation_scope["files_changed"] == ["testing/test_iniconfig.py"]
    assert mutation_scope["production_files"] == ["src/iniconfig/__init__.py"]
    assert mutation_scope["production_files_changed"] == []
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files_must_remain_unchanged"] is True
    assert mutation_scope["candidate_after"]["target_test_file"] == (
        "testing/test_iniconfig.py"
    )
    assert mutation_scope["candidate_after"]["test_case_ids"] == [
        "iniconfig_comment_only_lines",
        "iniconfig_inline_section_comments",
        "iniconfig_duplicate_key_reports_name",
    ]
    assert row["production_files"] == ["src/iniconfig/__init__.py"]
    assert set(row["production_file_hashes_before"]) == {
        "src/iniconfig/__init__.py"
    }
    assert (tmp_path / "src" / "iniconfig" / "__init__.py").read_bytes() == (
        source_before
    )

    validation = row["validation"]
    assert validation == {
        "status": "not_run",
        "commands": ["python -m pytest testing/test_iniconfig.py -q"],
        "selected_command": "python -m pytest testing/test_iniconfig.py -q",
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
    }

    candidate_after = row["candidate_after"]
    assert candidate_after["available"] is True
    assert candidate_after["wrote_file"] is True
    assert candidate_after["planned_changed_files"] == ["testing/test_iniconfig.py"]
    assert candidate_after["test_functions"] == [
        "test_comment_only_lines_are_ignored_between_entries",
        "test_inline_section_comments_are_stripped",
        "test_duplicate_key_error_reports_offending_key",
    ]
    assert candidate_after["sha256_before"] != candidate_after["sha256_after"]
    assert candidate_after["diff_summary"]["added_line_count"] > 0

    materialize_action = row["actions"][3]
    assert materialize_action["payload"]["status"] == "materialized"
    assert [
        case["id"] for case in materialize_action["payload"]["cases"]
    ] == candidate_after["test_case_ids"]

    test_after = (tmp_path / "testing" / "test_iniconfig.py").read_text(
        encoding="utf-8"
    )
    assert test_after != test_before
    assert "test_comment_only_lines_are_ignored_between_entries" in test_after
    assert "test_inline_section_comments_are_stripped" in test_after
    assert "test_duplicate_key_error_reports_offending_key" in test_after

    rerow = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()
    assert rerow["status"] == "already_applied"
    assert rerow["mutation_scope"]["files_changed"] == []


def test_real_repo_tests_planner_materializes_h11_bytesify_cases(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_rows()
    _write_synthetic_h11_checkout(tmp_path)
    production_before = {
        "h11/__init__.py": (tmp_path / "h11" / "__init__.py").read_bytes(),
        "h11/_util.py": (tmp_path / "h11" / "_util.py").read_bytes(),
    }
    test_before = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )
    records = _knowledge_records(tmp_path, repo, task)

    row = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["repo_id"] == "h11"
    assert row["repo_split"] == "heldout"
    assert row["task_id"] == "h11-tests-bytesify-memoryview"
    assert row["status"] == "materialized"
    assert row["target_test_file"] == "h11/tests/test_util.py"
    assert row["validation_commands"] == [
        "python -m pytest h11/tests/test_util.py -q"
    ]
    assert REQUIRED_KNOWLEDGE_PURPOSES == (
        "test_location",
        "import_style",
        "validation",
    )
    assert row["residual_labels"] == [CANDIDATE_VALIDATION_DEFERRED]
    assert row["blockers"] == []

    select_test_file = row["actions"][1]
    assert select_test_file["target"] == "h11/tests/test_util.py"
    assert select_test_file["payload"]["repo_state_confirmed"] is True
    assert {
        "task.allowed_write_paths",
        "task.public_validation_commands",
        "local_knowledge.validation_recipe_record",
        "local_knowledge.pytest_layout_record",
    } <= set(select_test_file["payload"]["selection_sources"])

    import_evidence = row["import_style_evidence"]
    assert {
        ("pytest", None),
        (".._util", "bytesify"),
    } <= {
        (item["module"], item["imported"])
        for item in import_evidence["repo_state_imports"]
    }
    assert import_evidence["selected_public_imports"] == []
    assert import_evidence["local_knowledge_relative_import_examples"] == [
        {
            "path": "h11/tests/test_util.py",
            "import": ".._util",
            "names": ["bytesify"],
            "kind": "from_import",
            "level": 2,
            "line": 3,
        }
    ]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "tests_only"
    assert mutation_scope["planned_write_files"] == ["h11/tests/test_util.py"]
    assert mutation_scope["files_changed"] == ["h11/tests/test_util.py"]
    assert mutation_scope["production_files"] == ["h11/__init__.py", "h11/_util.py"]
    assert mutation_scope["production_files_changed"] == []
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files_must_remain_unchanged"] is True
    assert row["production_files"] == ["h11/__init__.py", "h11/_util.py"]
    assert set(row["production_file_hashes_before"]) == {
        "h11/__init__.py",
        "h11/_util.py",
    }
    assert {
        path: (tmp_path / path).read_bytes() for path in production_before
    } == production_before

    candidate_after = row["candidate_after"]
    assert candidate_after["available"] is True
    assert candidate_after["wrote_file"] is True
    assert candidate_after["planned_changed_files"] == ["h11/tests/test_util.py"]
    assert candidate_after["test_case_ids"] == [
        "h11_bytesify_bytearray",
        "h11_bytesify_memoryview",
        "h11_bytesify_ascii_str",
        "h11_bytesify_non_ascii_str",
        "h11_bytesify_int_type_error",
    ]
    assert candidate_after["test_functions"] == [
        "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
        "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
        "test_bytesify_accepts_bytes_like_inputs_and_ascii_str",
        "test_bytesify_rejects_non_ascii_str",
        "test_bytesify_rejects_int",
    ]
    assert candidate_after["sha256_before"] != candidate_after["sha256_after"]
    assert candidate_after["diff_summary"]["added_line_count"] > 0

    materialize_action = row["actions"][3]
    assert materialize_action["payload"]["status"] == "materialized"
    assert [
        case["id"] for case in materialize_action["payload"]["cases"]
    ] == candidate_after["test_case_ids"]

    validation = row["validation"]
    assert validation == {
        "status": "not_run",
        "commands": ["python -m pytest h11/tests/test_util.py -q"],
        "selected_command": "python -m pytest h11/tests/test_util.py -q",
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
    }

    citations = row["knowledge_citations"]
    assert {"import_style", "pytest_style", "test_location", "validation"} <= set(
        citations
    )
    assert row["knowledge_attribution"]["missing_purposes"] == []
    assert row["knowledge_attribution"]["residual_labels"] == []
    knowledge_use = row["knowledge_use_record"]
    assert isinstance(knowledge_use, dict)
    validate_local_knowledge_record(knowledge_use)
    assert knowledge_use["record_type"] == "knowledge_use_record"
    assert knowledge_use["split"] == "heldout"
    assert knowledge_use["data"]["missing_purposes"] == []
    assert knowledge_use["data"]["validation_result"] == {
        "status": "materialized",
        "command": "python -m pytest h11/tests/test_util.py -q",
        "reason": CANDIDATE_VALIDATION_DEFERRED,
    }

    test_after = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )
    assert test_after != test_before
    assert "memoryview" in test_after
    assert "test_bytesify_rejects_non_ascii_str" in test_after
    assert "pytest.raises(TypeError, match=\"int\")" in test_after

    rerow = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()
    assert rerow["status"] == "already_applied"
    assert rerow["mutation_scope"]["files_changed"] == []


def test_real_repo_tests_planner_materializes_humanize_naturalsize_cases(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_humanize_rows()
    _write_synthetic_humanize_checkout(tmp_path)
    production_before = {
        "src/humanize/__init__.py": (
            tmp_path / "src" / "humanize" / "__init__.py"
        ).read_bytes(),
        "src/humanize/filesize.py": (
            tmp_path / "src" / "humanize" / "filesize.py"
        ).read_bytes(),
    }
    test_before = (tmp_path / "tests" / "test_filesize.py").read_text(
        encoding="utf-8"
    )
    records = _knowledge_records(tmp_path, repo, task)

    row = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["repo_id"] == "humanize"
    assert row["repo_split"] == "heldout"
    assert row["task_id"] == "humanize-tests-naturalsize-negative-strings"
    assert row["status"] == "materialized"
    assert row["target_test_file"] == "tests/test_filesize.py"
    assert row["validation_commands"] == [
        "python -m pytest tests/test_filesize.py -q --benchmark-disable"
    ]
    assert row["residual_labels"] == [CANDIDATE_VALIDATION_DEFERRED]
    assert row["blockers"] == []

    select_test_file = row["actions"][1]
    assert select_test_file["target"] == "tests/test_filesize.py"
    assert select_test_file["payload"]["repo_state_confirmed"] is True
    assert {
        "task.allowed_write_paths",
        "task.public_validation_commands",
        "local_knowledge.validation_recipe_record",
        "local_knowledge.pytest_layout_record",
    } <= set(select_test_file["payload"]["selection_sources"])

    import_evidence = row["import_style_evidence"]
    assert {
        ("pytest", None),
        ("humanize", None),
    } <= {
        (item["module"], item["imported"])
        for item in import_evidence["repo_state_imports"]
    }
    assert import_evidence["selected_public_imports"] == [
        {
            "path": "tests/test_filesize.py",
            "module": "humanize",
            "imported": None,
            "level": 0,
            "line": 5,
        }
    ]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "tests_only"
    assert mutation_scope["planned_write_files"] == ["tests/test_filesize.py"]
    assert mutation_scope["files_changed"] == ["tests/test_filesize.py"]
    assert mutation_scope["production_files"] == [
        "src/humanize/__init__.py",
        "src/humanize/filesize.py",
    ]
    assert mutation_scope["production_files_changed"] == []
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files_must_remain_unchanged"] is True
    assert row["production_files"] == [
        "src/humanize/__init__.py",
        "src/humanize/filesize.py",
    ]
    assert set(row["production_file_hashes_before"]) == {
        "src/humanize/__init__.py",
        "src/humanize/filesize.py",
    }
    assert {
        path: (tmp_path / path).read_bytes() for path in production_before
    } == production_before

    candidate_after = row["candidate_after"]
    assert candidate_after["available"] is True
    assert candidate_after["wrote_file"] is True
    assert candidate_after["planned_changed_files"] == ["tests/test_filesize.py"]
    assert candidate_after["test_case_ids"] == [
        "humanize_naturalsize_negative_numeric_strings",
        "humanize_naturalsize_negative_gnu_suffixes",
        "humanize_naturalsize_negative_binary_suffixes",
    ]
    assert candidate_after["test_functions"] == [
        "test_naturalsize_accepts_negative_numeric_strings",
        "test_naturalsize_formats_negative_gnu_suffixes",
        "test_naturalsize_formats_negative_binary_suffixes",
    ]
    assert candidate_after["sha256_before"] != candidate_after["sha256_after"]
    assert candidate_after["diff_summary"]["added_line_count"] > 0

    materialize_action = row["actions"][3]
    assert materialize_action["payload"]["status"] == "materialized"
    assert [
        case["id"] for case in materialize_action["payload"]["cases"]
    ] == candidate_after["test_case_ids"]

    validation = row["validation"]
    assert validation == {
        "status": "not_run",
        "commands": [
            "python -m pytest tests/test_filesize.py -q --benchmark-disable"
        ],
        "selected_command": (
            "python -m pytest tests/test_filesize.py -q --benchmark-disable"
        ),
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
    }

    citations = row["knowledge_citations"]
    assert {"import_style", "pytest_style", "test_location", "validation"} <= set(
        citations
    )
    knowledge_use = row["knowledge_use_record"]
    assert isinstance(knowledge_use, dict)
    validate_local_knowledge_record(knowledge_use)
    assert knowledge_use["record_type"] == "knowledge_use_record"
    assert knowledge_use["split"] == "heldout"
    assert knowledge_use["data"]["validation_result"] == {
        "status": "materialized",
        "command": (
            "python -m pytest tests/test_filesize.py -q --benchmark-disable"
        ),
        "reason": CANDIDATE_VALIDATION_DEFERRED,
    }

    test_after = (tmp_path / "tests" / "test_filesize.py").read_text(
        encoding="utf-8"
    )
    assert test_after != test_before
    assert "test_naturalsize_accepts_negative_numeric_strings" in test_after
    assert "test_naturalsize_formats_negative_gnu_suffixes" in test_after
    assert "test_naturalsize_formats_negative_binary_suffixes" in test_after
    assert '("-1024", "-1.0K")' in test_after
    assert '("-1024", "-1.0 KiB")' in test_after

    rerow = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()
    assert rerow["status"] == "already_applied"
    assert rerow["mutation_scope"]["files_changed"] == []


def test_real_repo_tests_planner_materializes_boltons_slugify_cases(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_boltons_rows()
    _write_synthetic_boltons_checkout(tmp_path)
    production_before = {
        "boltons/__init__.py": (tmp_path / "boltons" / "__init__.py").read_bytes(),
        "boltons/strutils.py": (tmp_path / "boltons" / "strutils.py").read_bytes(),
    }
    test_before = (tmp_path / "tests" / "test_strutils.py").read_text(
        encoding="utf-8"
    )
    records = _knowledge_records(tmp_path, repo, task)

    row = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["repo_id"] == "boltons"
    assert row["repo_split"] == "heldout"
    assert row["task_id"] == "boltons-tests-slugify-delimiter"
    assert row["status"] == "materialized"
    assert row["target_test_file"] == "tests/test_strutils.py"
    assert row["validation_commands"] == [
        "python -m pytest tests/test_strutils.py -q"
    ]
    assert row["residual_labels"] == [CANDIDATE_VALIDATION_DEFERRED]
    assert row["blockers"] == []

    select_test_file = row["actions"][1]
    assert select_test_file["target"] == "tests/test_strutils.py"
    assert select_test_file["payload"]["repo_state_confirmed"] is True
    assert {
        "task.allowed_write_paths",
        "task.public_validation_commands",
        "local_knowledge.validation_recipe_record",
        "local_knowledge.pytest_layout_record",
    } <= set(select_test_file["payload"]["selection_sources"])

    import_evidence = row["import_style_evidence"]
    assert ("boltons", "strutils") in {
        (item["module"], item["imported"])
        for item in import_evidence["repo_state_imports"]
    }
    assert import_evidence["selected_public_imports"] == [
        {
            "path": "tests/test_strutils.py",
            "module": "boltons",
            "imported": "strutils",
            "level": 0,
            "line": 5,
        }
    ]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "tests_only"
    assert mutation_scope["planned_write_files"] == ["tests/test_strutils.py"]
    assert mutation_scope["files_changed"] == ["tests/test_strutils.py"]
    assert mutation_scope["production_files"] == [
        "boltons/__init__.py",
        "boltons/strutils.py",
    ]
    assert mutation_scope["production_files_changed"] == []
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files_must_remain_unchanged"] is True
    assert row["production_files"] == [
        "boltons/__init__.py",
        "boltons/strutils.py",
    ]
    assert set(row["production_file_hashes_before"]) == {
        "boltons/__init__.py",
        "boltons/strutils.py",
    }
    assert {
        path: (tmp_path / path).read_bytes() for path in production_before
    } == production_before

    candidate_after = row["candidate_after"]
    assert candidate_after["available"] is True
    assert candidate_after["wrote_file"] is True
    assert candidate_after["planned_changed_files"] == ["tests/test_strutils.py"]
    assert candidate_after["test_case_ids"] == [
        "boltons_slugify_custom_delimiters",
        "boltons_slugify_empty_string",
        "boltons_slugify_ascii_output",
        "boltons_slugify_lower_false",
    ]
    assert candidate_after["test_functions"] == [
        "test_slugify_accepts_custom_delimiters",
        "test_slugify_empty_string_stays_empty",
        "test_slugify_ascii_mode_returns_bytes",
        "test_slugify_preserves_case_when_lower_false",
    ]
    assert candidate_after["sha256_before"] != candidate_after["sha256_after"]
    assert candidate_after["diff_summary"]["added_line_count"] > 0

    materialize_action = row["actions"][3]
    assert materialize_action["payload"]["status"] == "materialized"
    assert [
        case["id"] for case in materialize_action["payload"]["cases"]
    ] == candidate_after["test_case_ids"]

    validation = row["validation"]
    assert validation == {
        "status": "not_run",
        "commands": ["python -m pytest tests/test_strutils.py -q"],
        "selected_command": "python -m pytest tests/test_strutils.py -q",
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
    }

    citations = row["knowledge_citations"]
    assert {"import_style", "pytest_style", "test_location", "validation"} <= set(
        citations
    )
    knowledge_use = row["knowledge_use_record"]
    assert isinstance(knowledge_use, dict)
    validate_local_knowledge_record(knowledge_use)
    assert knowledge_use["record_type"] == "knowledge_use_record"
    assert knowledge_use["split"] == "heldout"
    assert knowledge_use["data"]["validation_result"] == {
        "status": "materialized",
        "command": "python -m pytest tests/test_strutils.py -q",
        "reason": CANDIDATE_VALIDATION_DEFERRED,
    }

    test_after = (tmp_path / "tests" / "test_strutils.py").read_text(
        encoding="utf-8"
    )
    assert test_after != test_before
    assert "test_slugify_accepts_custom_delimiters" in test_after
    assert "test_slugify_empty_string_stays_empty" in test_after
    assert "test_slugify_ascii_mode_returns_bytes" in test_after
    assert "test_slugify_preserves_case_when_lower_false" in test_after
    assert '("-1024", "-1.0K")' not in test_after
    assert 'isinstance(result, bytes)' in test_after

    rerow = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=records,
    ).to_record()
    assert rerow["status"] == "already_applied"
    assert rerow["mutation_scope"]["files_changed"] == []


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
        "status": "materialized",
        "command": "python -m pytest testing/test_iniconfig.py -q",
        "reason": CANDIDATE_VALIDATION_DEFERRED,
    }
    assert knowledge_use["data"]["cited_purposes"] == citations
    assert knowledge_use["data"]["required_purposes"] == [
        "test_location",
        "import_style",
        "validation",
    ]
    assert knowledge_use["data"]["missing_purposes"] == []
    assert row["knowledge_attribution"] == {
        "retrieved_record_ids": knowledge_use["data"]["retrieved_record_ids"],
        "cited_purposes": citations,
        "required_purposes": ["test_location", "import_style", "validation"],
        "missing_purposes": [],
        "residual_labels": [],
    }


def test_real_repo_tests_planner_marks_partial_knowledge_gap(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_iniconfig_rows()
    _write_synthetic_iniconfig_checkout(tmp_path)
    records = _knowledge_records(tmp_path, repo, task)
    public_api_records = tuple(
        record for record in records if record["record_type"] == "public_api_record"
    )

    row = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=public_api_records,
    ).to_record()

    public_api_record_ids = [str(record["id"]) for record in public_api_records]
    assert set(row["knowledge_citations"]) == {"import_style"}
    assert row["knowledge_citations"]["import_style"] == public_api_record_ids
    assert row["knowledge_attribution"] == {
        "retrieved_record_ids": public_api_record_ids,
        "cited_purposes": {"import_style": public_api_record_ids},
        "required_purposes": ["test_location", "import_style", "validation"],
        "missing_purposes": ["test_location", "validation"],
        "residual_labels": ["missing_knowledge"],
    }
    assert row["residual_labels"] == [
        CANDIDATE_VALIDATION_DEFERRED,
        "missing_knowledge",
    ]

    knowledge_use = row["knowledge_use_record"]
    assert isinstance(knowledge_use, dict)
    validate_local_knowledge_record(knowledge_use)
    assert knowledge_use["data"]["retrieved_record_ids"] == public_api_record_ids
    assert knowledge_use["data"]["cited_purposes"] == {
        "import_style": public_api_record_ids
    }
    assert knowledge_use["data"]["missing_purposes"] == [
        "test_location",
        "validation",
    ]
    assert "missing_knowledge" in knowledge_use["links"]["residual_labels"]


def test_real_repo_tests_planner_marks_knowledge_not_used_when_no_records(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_iniconfig_rows()
    _write_synthetic_iniconfig_checkout(tmp_path)

    row = plan_real_repo_tests_only_candidate(
        tmp_path,
        repo=repo,
        task=task,
        local_knowledge_records=(),
    ).to_record()

    assert row["knowledge_citations"] == {}
    assert row["knowledge_attribution"] == {
        "retrieved_record_ids": [],
        "cited_purposes": {},
        "required_purposes": ["test_location", "import_style", "validation"],
        "missing_purposes": ["test_location", "import_style", "validation"],
        "residual_labels": ["knowledge_not_used"],
    }
    assert row["residual_labels"] == [
        CANDIDATE_VALIDATION_DEFERRED,
        "knowledge_not_used",
    ]

    knowledge_use = row["knowledge_use_record"]
    assert isinstance(knowledge_use, dict)
    validate_local_knowledge_record(knowledge_use)
    assert knowledge_use["data"]["retrieved_record_ids"] == []
    assert knowledge_use["data"]["cited_purposes"] == {}
    assert knowledge_use["data"]["missing_purposes"] == [
        "test_location",
        "import_style",
        "validation",
    ]
    assert "knowledge_not_used" in knowledge_use["links"]["residual_labels"]
