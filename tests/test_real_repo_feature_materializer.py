from __future__ import annotations

import json
from pathlib import Path

from j3.real_repo_feature_materializer import (
    CANDIDATE_VALIDATION_DEFERRED,
    H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID,
    HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID,
    INICONFIG_SECTION_DEFAULT_TASK_ID,
    materialize_real_repo_feature_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


def _manifest_h11_feature_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(item for item in manifest["repositories"] if item["id"] == "h11")
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID
    )
    return repo, task


def _manifest_iniconfig_feature_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(item for item in manifest["repositories"] if item["id"] == "iniconfig")
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == INICONFIG_SECTION_DEFAULT_TASK_ID
    )
    return repo, task


def _manifest_humanize_feature_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(item for item in manifest["repositories"] if item["id"] == "humanize")
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID
    )
    return repo, task


def _write_synthetic_h11_checkout(repo: Path) -> None:
    (repo / "h11" / "tests").mkdir(parents=True)
    (repo / "h11" / "__init__.py").write_text(
        """from __future__ import annotations

from ._util import bytesify

__all__ = ["bytesify"]
""",
        encoding="utf-8",
    )
    (repo / "h11" / "_util.py").write_text(
        """from typing import Any, Dict, NoReturn, Pattern, Tuple, Type, TypeVar, Union

__all__ = [
    "bytesify",
]


def bytesify(s: Union[bytes, bytearray, memoryview, int, str]) -> bytes:
    # Fast-path:
    if type(s) is bytes:
        return s
    if isinstance(s, str):
        s = s.encode("ascii")
    if isinstance(s, int):
        raise TypeError("expected bytes-like object, not int")
    return bytes(s)
""",
        encoding="utf-8",
    )
    (repo / "h11" / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "h11" / "tests" / "test_util.py").write_text(
        """import pytest

from .._util import bytesify


def test_bytesify() -> None:
    assert bytesify(b"123") == b"123"
    assert bytesify(bytearray(b"123")) == b"123"
    assert bytesify(memoryview(b"123")) == b"123"
    assert bytesify("123") == b"123"

    with pytest.raises(UnicodeEncodeError):
        bytesify("\\u1234")

    with pytest.raises(TypeError, match="int"):
        bytesify(10)
""",
        encoding="utf-8",
    )


def _write_synthetic_iniconfig_checkout(repo: Path) -> None:
    (repo / "src" / "iniconfig").mkdir(parents=True)
    (repo / "testing").mkdir()
    (repo / "src" / "iniconfig" / "__init__.py").write_text(
        '''"""brain-dead simple parser for ini-style files."""

import os
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from typing import Final
from typing import TypeVar
from typing import overload

_D = TypeVar("_D")
_T = TypeVar("_T")


class SectionWrapper:
    config: Final["IniConfig"]
    name: Final[str]

    def __init__(self, config: "IniConfig", name: str) -> None:
        self.config = config
        self.name = name

    def __getitem__(self, key: str) -> str:
        return self.config.sections[self.name][key]

    def __iter__(self) -> Iterator[str]:
        section: Mapping[str, str] = self.config.sections.get(self.name, {})

        def lineof(key: str) -> int:
            return self.config.lineof(self.name, key)  # type: ignore[return-value]

        yield from sorted(section, key=lineof)

    def items(self) -> Iterator[tuple[str, str]]:
        for name in self:
            yield name, self[name]


class IniConfig:
    path: Final[str]
    sections: Final[Mapping[str, Mapping[str, str]]]
    _sources: Final[Mapping[tuple[str, str | None], int]]

    def __init__(
        self,
        path: str | os.PathLike[str],
        data: str | None = None,
        encoding: str = "utf-8",
    ) -> None:
        self.path = os.fspath(path)
        section = ""
        sections: dict[str, dict[str, str]] = {}
        sources: dict[tuple[str, str | None], int] = {}
        for lineno, raw_line in enumerate((data or "").splitlines()):
            line = raw_line.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                sections[section] = {}
                sources[section, None] = lineno
            elif "=" in line and section:
                key, value = line.split("=", 1)
                key = key.strip()
                sections[section][key] = value.strip()
                sources[section, key] = lineno
        self._sources = sources
        self.sections = sections

    def lineof(self, section: str, name: str | None = None) -> int | None:
        lineno = self._sources.get((section, name))
        return None if lineno is None else lineno + 1

    @overload
    def get(
        self,
        section: str,
        name: str,
    ) -> str | None: ...

    @overload
    def get(
        self,
        section: str,
        name: str,
        default: _D,
        convert: None = None,
    ) -> str | _D: ...

    def get(  # type: ignore
        self,
        section: str,
        name: str,
        default: _D | None = None,
        convert: Callable[[str], _T] | None = None,
    ) -> _D | _T | str | None:
        try:
            value: str = self.sections[section][name]
        except KeyError:
            return default
        else:
            if convert is not None:
                return convert(value)
            else:
                return value

    def __getitem__(self, name: str) -> SectionWrapper:
        if name not in self.sections:
            raise KeyError(name)
        return SectionWrapper(self, name)

    def __iter__(self) -> Iterator[SectionWrapper]:
        for name in sorted(self.sections, key=self.lineof):  # type: ignore
            yield SectionWrapper(self, name)
''',
        encoding="utf-8",
    )
    (repo / "src" / "iniconfig" / "_parse.py").write_text("", encoding="utf-8")
    (repo / "testing" / "test_iniconfig.py").write_text(
        """import pytest

from iniconfig import IniConfig


def test_missing_section() -> None:
    config = IniConfig("x", data="[section]\\nvalue=1")
    with pytest.raises(KeyError):
        config["other"]


def test_iter_file_order() -> None:
    config = IniConfig(
        "x.ini",
        data="[section]\\nvalue = 1\\nvalue2 = 2\\n",
    )
    assert list(config["section"]) == ["value", "value2"]
""",
        encoding="utf-8",
    )


def _write_synthetic_humanize_checkout(repo: Path) -> None:
    (repo / "src" / "humanize").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "humanize" / "__init__.py").write_text(
        """from __future__ import annotations

from .filesize import naturalsize

__all__ = ["naturalsize"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "humanize" / "filesize.py").write_text(
        '''"""Bits and bytes related humanization."""

from __future__ import annotations

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
    """Format a number of bytes like a human-readable filesize.

    Args:
        value (int, float, str): Integer to convert.
        binary (bool): If `True`, uses binary suffixes.
        gnu (bool): If `True`, uses GNU-style suffixes.
        format (str): Custom formatter.

    Returns:
        str: Human readable representation of a filesize.
    """
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
''',
        encoding="utf-8",
    )
    (repo / "src" / "humanize" / "number.py").write_text("", encoding="utf-8")
    (repo / "tests" / "test_filesize.py").write_text(
        """from __future__ import annotations

import humanize


def test_naturalsize() -> None:
    assert humanize.naturalsize(0) == "0 Bytes"
    assert humanize.naturalsize(1) == "1 Byte"
    assert humanize.naturalsize(1024, True) == "1.0 KiB"
    assert humanize.naturalsize(1024, False, True) == "1.0K"
""",
        encoding="utf-8",
    )


def test_materializes_h11_bytesify_object_message_feature(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_feature_rows()
    _write_synthetic_h11_checkout(tmp_path)
    production_before = {
        "h11/__init__.py": (tmp_path / "h11" / "__init__.py").read_bytes(),
        "h11/_util.py": (tmp_path / "h11" / "_util.py").read_bytes(),
    }
    test_before = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )

    candidate = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
        validate=True,
    )
    row = candidate.to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["schema_version"] == "real-repo-feature-candidate-v1"
    assert row["record_kind"] == "real_repo_one_file_feature_candidate"
    assert row["action_family"] == "one_file_source_feature_region"
    assert row["repo_id"] == "h11"
    assert row["repo_split"] == "heldout"
    assert row["task_id"] == "h11-feature-bytesify-object-message"
    assert row["status"] == "materialized"
    assert row["target_source_file"] == "h11/_util.py"
    assert row["target_test_file"] == "h11/tests/test_util.py"
    assert row["validation"]["status"] == "passed"
    assert row["validation"]["selected_command"] == (
        "python -m pytest h11/tests/test_util.py -q"
    )
    assert row["validation"]["candidate_validation_network_allowed"] is False
    assert row["zero_hosted_usage_confirmed"] is True
    assert row["blockers"] == []
    assert row["residual_labels"] == ["candidate_validation_passed"]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "one_file_feature"
    assert mutation_scope["planned_write_files"] == [
        "h11/_util.py",
        "h11/tests/test_util.py",
    ]
    assert mutation_scope["files_changed"] == [
        "h11/_util.py",
        "h11/tests/test_util.py",
    ]
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files"] == ["h11/__init__.py", "h11/_util.py"]
    assert mutation_scope["production_files_changed"] == ["h11/_util.py"]
    assert mutation_scope["maximum_production_files_changed"] == 1
    assert mutation_scope["allowed_production_file"] == "h11/_util.py"
    assert mutation_scope["one_production_file_constraint_preserved"] is True

    assert row["production_file_hashes_before"]["h11/__init__.py"] == (
        row["production_file_hashes_after"]["h11/__init__.py"]
    )
    assert row["production_file_hashes_before"]["h11/_util.py"] != (
        row["production_file_hashes_after"]["h11/_util.py"]
    )
    assert (tmp_path / "h11" / "__init__.py").read_bytes() == (
        production_before["h11/__init__.py"]
    )
    assert (tmp_path / "h11" / "_util.py").read_bytes() != (
        production_before["h11/_util.py"]
    )

    source_after = row["candidate_after"]["source_file"]
    assert source_after["status"] == "materialized"
    assert source_after["target_function"] == "bytesify"
    assert source_after["touched_region"]["region_name"] == (
        "unsupported_object_type_error_message"
    )
    assert source_after["candidate_after"]["ast_parse_ok"] is True
    assert source_after["candidate_after"]["signature_preserved"] is True
    assert source_after["candidate_after"]["import_changes"] == {
        "added": [],
        "removed": [],
    }
    assert "except TypeError" in source_after["candidate_after"]["diff"]
    assert "type(s).__name__" in source_after["candidate_after"]["diff"]

    test_after = row["candidate_after"]["test_file"]
    assert test_after["planned_changed_files"] == ["h11/tests/test_util.py"]
    assert test_after["wrote_file"] is True
    assert test_after["test_case_ids"] == [
        "h11_bytesify_unsupported_object_type_name"
    ]
    assert test_after["ast_delta"]["ast_parse_ok"] is True
    assert test_after["sha256_before"] != test_after["sha256_after"]
    assert "UnsupportedThing" in test_after["diff"]

    namespace: dict[str, object] = {}
    exec((tmp_path / "h11" / "_util.py").read_text(encoding="utf-8"), namespace)
    bytesify = namespace["bytesify"]

    class UnsupportedThing:
        pass

    assert bytesify(b"abc") == b"abc"
    assert bytesify(bytearray(b"abc")) == b"abc"
    assert bytesify(memoryview(b"abc")) == b"abc"
    assert bytesify("abc") == b"abc"
    try:
        bytesify(UnsupportedThing())
    except TypeError as error:
        message = str(error)
    else:
        raise AssertionError("bytesify should reject UnsupportedThing")
    assert "UnsupportedThing" in message
    assert "bytes-like object" in message

    test_after_text = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )
    assert test_after_text != test_before
    assert "test_bytesify_rejects_unsupported_object_with_type_name" in test_after_text


def test_materializer_can_plan_without_writing(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_feature_rows()
    _write_synthetic_h11_checkout(tmp_path)
    source_before = (tmp_path / "h11" / "_util.py").read_text(encoding="utf-8")
    test_before = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )

    row = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
        write=False,
    ).to_record()

    assert row["status"] == "planned"
    assert row["validation"] == {
        "status": "not_run",
        "commands": ["python -m pytest h11/tests/test_util.py -q"],
        "selected_command": "python -m pytest h11/tests/test_util.py -q",
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
        "runtime_seconds": 0.0,
    }
    assert row["mutation_scope"]["files_changed"] == []
    assert row["mutation_scope"]["production_files_changed"] == []
    assert (tmp_path / "h11" / "_util.py").read_text(encoding="utf-8") == source_before
    assert (
        tmp_path / "h11" / "tests" / "test_util.py"
    ).read_text(encoding="utf-8") == test_before


def test_materializes_iniconfig_section_default_feature(tmp_path: Path) -> None:
    repo, task = _manifest_iniconfig_feature_rows()
    _write_synthetic_iniconfig_checkout(tmp_path)
    production_before = {
        "src/iniconfig/__init__.py": (
            tmp_path / "src" / "iniconfig" / "__init__.py"
        ).read_bytes(),
        "src/iniconfig/_parse.py": (
            tmp_path / "src" / "iniconfig" / "_parse.py"
        ).read_bytes(),
    }
    test_before = (tmp_path / "testing" / "test_iniconfig.py").read_text(
        encoding="utf-8"
    )

    candidate = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
        validate=False,
    )
    row = candidate.to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["repo_id"] == "iniconfig"
    assert row["repo_split"] == "calibration"
    assert row["task_id"] == "iniconfig-feature-section-default"
    assert row["status"] == "materialized"
    assert row["target_source_file"] == "src/iniconfig/__init__.py"
    assert row["target_test_file"] == "testing/test_iniconfig.py"
    assert row["validation"] == {
        "status": "not_run",
        "commands": ["python -m pytest testing/test_iniconfig.py -q"],
        "selected_command": "python -m pytest testing/test_iniconfig.py -q",
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
        "runtime_seconds": 0.0,
    }
    assert row["zero_hosted_usage_confirmed"] is True
    assert row["blockers"] == []
    assert row["residual_labels"] == [CANDIDATE_VALIDATION_DEFERRED]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "one_file_feature"
    assert mutation_scope["planned_write_files"] == [
        "src/iniconfig/__init__.py",
        "testing/test_iniconfig.py",
    ]
    assert mutation_scope["files_changed"] == [
        "src/iniconfig/__init__.py",
        "testing/test_iniconfig.py",
    ]
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files"] == [
        "src/iniconfig/__init__.py",
        "src/iniconfig/_parse.py",
    ]
    assert mutation_scope["production_files_changed"] == ["src/iniconfig/__init__.py"]
    assert mutation_scope["maximum_production_files_changed"] == 1
    assert mutation_scope["allowed_production_file"] == "src/iniconfig/__init__.py"
    assert mutation_scope["one_production_file_constraint_preserved"] is True

    assert row["production_file_hashes_before"]["src/iniconfig/_parse.py"] == (
        row["production_file_hashes_after"]["src/iniconfig/_parse.py"]
    )
    assert row["production_file_hashes_before"]["src/iniconfig/__init__.py"] != (
        row["production_file_hashes_after"]["src/iniconfig/__init__.py"]
    )
    assert (tmp_path / "src" / "iniconfig" / "_parse.py").read_bytes() == (
        production_before["src/iniconfig/_parse.py"]
    )
    assert (tmp_path / "src" / "iniconfig" / "__init__.py").read_bytes() != (
        production_before["src/iniconfig/__init__.py"]
    )

    source_after = row["candidate_after"]["source_file"]
    assert source_after["status"] == "materialized"
    assert source_after["target_function"] is None
    assert source_after["touched_region"]["region_name"] == (
        "optional_section_default_method"
    )
    assert source_after["candidate_after"]["ast_parse_ok"] is True
    assert source_after["candidate_after"]["signature_preserved"] is None
    assert source_after["candidate_after"]["import_changes"] == {
        "added": [],
        "removed": [],
    }
    assert "def get_section" in source_after["candidate_after"]["diff"]
    assert "return SectionWrapper(self, name)" in source_after["candidate_after"]["diff"]

    test_after = row["candidate_after"]["test_file"]
    assert test_after["planned_changed_files"] == ["testing/test_iniconfig.py"]
    assert test_after["wrote_file"] is True
    assert test_after["test_case_ids"] == [
        "iniconfig_get_section_missing_default",
        "iniconfig_get_section_existing_order",
    ]
    assert test_after["ast_delta"]["ast_parse_ok"] is True
    assert test_after["sha256_before"] != test_after["sha256_after"]
    assert "test_get_section_returns_default_for_missing_section" in test_after["diff"]

    namespace: dict[str, object] = {}
    exec(
        (tmp_path / "src" / "iniconfig" / "__init__.py").read_text(encoding="utf-8"),
        namespace,
    )
    ini_config = namespace["IniConfig"]
    config = ini_config("x", data="[section]\nsecond=2\nfirst=1\nthird=3")
    default = {"fallback": "value"}

    assert config.get_section("missing", default) is default
    assert config.get_section("missing") is None
    try:
        config["missing"]
    except KeyError as error:
        assert error.args == ("missing",)
    else:
        raise AssertionError("missing __getitem__ should still raise KeyError")
    section = config.get_section("section", default)
    assert section is not default
    assert list(section) == ["second", "first", "third"]
    assert list(section.items()) == [
        ("second", "2"),
        ("first", "1"),
        ("third", "3"),
    ]

    test_after_text = (tmp_path / "testing" / "test_iniconfig.py").read_text(
        encoding="utf-8"
    )
    assert test_after_text != test_before
    assert "test_get_section_existing_section_preserves_order" in test_after_text


def test_materializes_humanize_naturalsize_zero_format_feature(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_humanize_feature_rows()
    _write_synthetic_humanize_checkout(tmp_path)
    production_before = {
        "src/humanize/__init__.py": (
            tmp_path / "src" / "humanize" / "__init__.py"
        ).read_bytes(),
        "src/humanize/filesize.py": (
            tmp_path / "src" / "humanize" / "filesize.py"
        ).read_bytes(),
        "src/humanize/number.py": (
            tmp_path / "src" / "humanize" / "number.py"
        ).read_bytes(),
    }
    test_before = (tmp_path / "tests" / "test_filesize.py").read_text(
        encoding="utf-8"
    )

    candidate = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
        validate=False,
    )
    row = candidate.to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["repo_id"] == "humanize"
    assert row["repo_split"] == "heldout"
    assert row["task_id"] == "humanize-feature-naturalsize-zero-format"
    assert row["status"] == "materialized"
    assert row["target_source_file"] == "src/humanize/filesize.py"
    assert row["target_test_file"] == "tests/test_filesize.py"
    assert row["validation"] == {
        "status": "not_run",
        "commands": [
            "python -m pytest tests/test_filesize.py -q --benchmark-disable"
        ],
        "selected_command": (
            "python -m pytest tests/test_filesize.py -q --benchmark-disable"
        ),
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
        "runtime_seconds": 0.0,
    }
    assert row["zero_hosted_usage_confirmed"] is True
    assert row["blockers"] == []
    assert row["residual_labels"] == [CANDIDATE_VALIDATION_DEFERRED]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "one_file_feature"
    assert mutation_scope["planned_write_files"] == [
        "src/humanize/filesize.py",
        "tests/test_filesize.py",
    ]
    assert mutation_scope["files_changed"] == [
        "src/humanize/filesize.py",
        "tests/test_filesize.py",
    ]
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files"] == [
        "src/humanize/__init__.py",
        "src/humanize/filesize.py",
        "src/humanize/number.py",
    ]
    assert mutation_scope["production_files_changed"] == [
        "src/humanize/filesize.py"
    ]
    assert mutation_scope["maximum_production_files_changed"] == 1
    assert mutation_scope["allowed_production_file"] == "src/humanize/filesize.py"
    assert mutation_scope["one_production_file_constraint_preserved"] is True

    assert row["production_file_hashes_before"]["src/humanize/__init__.py"] == (
        row["production_file_hashes_after"]["src/humanize/__init__.py"]
    )
    assert row["production_file_hashes_before"]["src/humanize/number.py"] == (
        row["production_file_hashes_after"]["src/humanize/number.py"]
    )
    assert row["production_file_hashes_before"]["src/humanize/filesize.py"] != (
        row["production_file_hashes_after"]["src/humanize/filesize.py"]
    )
    assert (tmp_path / "src" / "humanize" / "__init__.py").read_bytes() == (
        production_before["src/humanize/__init__.py"]
    )
    assert (tmp_path / "src" / "humanize" / "number.py").read_bytes() == (
        production_before["src/humanize/number.py"]
    )
    assert (tmp_path / "src" / "humanize" / "filesize.py").read_bytes() != (
        production_before["src/humanize/filesize.py"]
    )

    source_after = row["candidate_after"]["source_file"]
    assert source_after["status"] == "materialized"
    assert source_after["target_function"] == "naturalsize"
    assert source_after["touched_region"]["region_name"] == (
        "zero_format_signature_and_zero_guard"
    )
    assert source_after["candidate_after"]["ast_parse_ok"] is True
    assert source_after["candidate_after"]["signature_preserved"] is False
    assert source_after["candidate_after"]["import_changes"] == {
        "added": [],
        "removed": [],
    }
    assert "zero_format: str | None = None" in source_after["candidate_after"]["diff"]
    assert "return zero_format" in source_after["candidate_after"]["diff"]

    test_after = row["candidate_after"]["test_file"]
    assert test_after["planned_changed_files"] == ["tests/test_filesize.py"]
    assert test_after["wrote_file"] is True
    assert test_after["test_case_ids"] == [
        "humanize_naturalsize_zero_format_zero_values",
        "humanize_naturalsize_zero_format_default_unchanged",
        "humanize_naturalsize_zero_format_nonzero_ignored",
    ]
    assert test_after["ast_delta"]["ast_parse_ok"] is True
    assert test_after["sha256_before"] != test_after["sha256_after"]
    assert "test_naturalsize_zero_format_handles_zero_values" in test_after["diff"]

    namespace: dict[str, object] = {}
    exec(
        (tmp_path / "src" / "humanize" / "filesize.py").read_text(encoding="utf-8"),
        namespace,
    )
    naturalsize = namespace["naturalsize"]

    assert naturalsize(0, zero_format="empty") == "empty"
    assert naturalsize(-0.0, zero_format="empty") == "empty"
    assert naturalsize(0) == "0 Bytes"
    assert naturalsize(-0.0) == "0 Bytes"
    assert naturalsize(1, zero_format="empty") == "1 Byte"
    assert naturalsize(1024, True, zero_format="empty") == "1.0 KiB"
    assert naturalsize(1024, False, True, zero_format="empty") == "1.0K"

    test_after_text = (tmp_path / "tests" / "test_filesize.py").read_text(
        encoding="utf-8"
    )
    assert test_after_text != test_before
    assert "test_naturalsize_zero_format_default_behavior_is_unchanged" in (
        test_after_text
    )


def test_materializer_blocks_when_source_region_is_not_expressible(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_feature_rows()
    _write_synthetic_h11_checkout(tmp_path)
    (tmp_path / "h11" / "_util.py").write_text(
        """from typing import Union


def bytesify(s: Union[bytes, bytearray, memoryview, int, str]) -> bytes:
    if isinstance(s, str):
        s = s.encode("ascii")
    return bytes(s).strip()
""",
        encoding="utf-8",
    )

    row = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
    ).to_record()

    assert row["status"] == "blocked"
    assert row["blockers"] == [
        {
            "field": "source_region",
            "reason": "target_selection",
            "message": "target source line not found:     return bytes(s)",
        }
    ]
    assert row["residual_labels"] == ["target_selection"]
    assert row["candidate_after"]["source_file"] == {
        "available": False,
        "target_source_file": "h11/_util.py",
        "not_available_reason": "target_selection",
    }
    assert row["mutation_scope"]["files_changed"] == []
