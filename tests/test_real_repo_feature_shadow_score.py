from __future__ import annotations

import json
from pathlib import Path

from j3 import real_repo_feature_materializer as feature_materializer
from j3.real_repo_feature_shadow_score import (
    format_real_repo_feature_shadow_score,
    run_real_repo_feature_shadow_score,
    write_real_repo_feature_shadow_report,
    write_real_repo_feature_shadow_score,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"
HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID = (
    "humanize-feature-naturalsize-zero-format"
)


def _humanize_feature_materializer_supported() -> bool:
    return hasattr(feature_materializer, "HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID")


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
        """import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
    """Format a number of bytes like a human-readable filesize."""
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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import humanize


def test_naturalsize() -> None:
    assert humanize.naturalsize(0) == "0 Bytes"
    assert humanize.naturalsize(1) == "1 Byte"
    assert humanize.naturalsize(1024, True) == "1.0 KiB"
    assert humanize.naturalsize(1024, False, True) == "1.0K"
""",
        encoding="utf-8",
    )


def test_feature_shadow_score_counts_h11_and_iniconfig_candidates(
    tmp_path: Path,
) -> None:
    h11_path = tmp_path / "h11"
    iniconfig_path = tmp_path / "iniconfig"
    humanize_path = tmp_path / "humanize"
    _write_synthetic_h11_checkout(h11_path)
    _write_synthetic_iniconfig_checkout(iniconfig_path)
    repo_paths = {"h11": h11_path, "iniconfig": iniconfig_path}
    humanize_supported = _humanize_feature_materializer_supported()
    if humanize_supported:
        _write_synthetic_humanize_checkout(humanize_path)
        repo_paths["humanize"] = humanize_path

    score = run_real_repo_feature_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths=repo_paths,
        validate_candidates=True,
    )

    assert json.loads(json.dumps(score, sort_keys=True)) == score
    assert score["schema_version"] == "real-repo-feature-shadow-score-v1"
    assert score["record_kind"] == "real_repo_one_file_feature_shadow_score"
    assert score["zero_hosted_usage_confirmed"] is True

    metrics = score["metrics"]
    assert isinstance(metrics, dict)
    expected_count = 3 if humanize_supported else 2
    expected_pass = "3/4" if humanize_supported else "2/4"
    expected_heldout = "2/3" if humanize_supported else "1/3"
    expected_first_ranks = [1, 1, 1, None] if humanize_supported else [1, 1, None, None]
    expected_repos = (
        ["h11", "humanize", "iniconfig"]
        if humanize_supported
        else ["h11", "iniconfig"]
    )
    assert metrics["tasks_scored"] == 4
    assert metrics["candidate_count"] == expected_count
    assert metrics["candidates_tested"] == expected_count
    assert metrics["calibration"]["pass@3"] == "1/1"
    assert metrics["heldout"]["pass@3"] == expected_heldout
    assert metrics["pass@1"] == expected_pass
    assert metrics["pass@3"] == expected_pass
    assert metrics["first_passing_ranks"] == expected_first_ranks
    assert metrics["distinct_repos_passing"] == expected_repos
    assert metrics["distinct_repos_passing_count"] == expected_count
    assert metrics["production_files_changed"] == expected_count
    assert metrics["production_file_constraint"] == {
        "maximum_production_files_changed": 1,
        "violations": 0,
        "preserved": True,
    }
    assert metrics["writes_outside_allowlist"] == 0
    assert metrics["mutation_scope_violations"] == {
        "production_file_constraint_violations": 0,
        "writes_outside_allowlist": 0,
    }
    assert metrics["candidate_validation_statuses"]["passed"] == expected_count
    assert metrics["candidate_validation_statuses"]["blocked"] == 4 - expected_count
    assert metrics["hidden_like_agreement"]["agreeing"] == expected_count
    assert metrics["hidden_like_agreement"]["not_run"] == 4 - expected_count

    gate = score["gate_decision"]
    assert isinstance(gate, dict)
    assert gate["decision"] == "allow_guarded_one_file_feature_opt_in"
    assert gate["passed"] is True
    assert gate["guarded_opt_in_allowed"] is True
    expected_blocked = ["boltons-feature-slugify-max-length"]
    expected_allowed_tasks = [
        "iniconfig-feature-section-default",
        "h11-feature-bytesify-object-message",
    ]
    if humanize_supported:
        expected_allowed_tasks.append(HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID)
    else:
        expected_blocked.insert(0, HUMANIZE_NATURALSIZE_ZERO_FORMAT_TASK_ID)
    assert gate["blocked_rows"] == expected_blocked
    assert gate["guarded_opt_in_scope"]["allowed_task_ids"] == expected_allowed_tasks
    assert gate["guarded_opt_in_scope"]["path_scope"] == (
        "task allowlisted source and test files only"
    )
    assert "hidden-like checks do not disagree with public validation" in (
        gate["guarded_opt_in_scope"]["requires"]
    )

    rows = score["task_results"]
    assert isinstance(rows, list)
    assert [row["task_id"] for row in rows] == [
        "iniconfig-feature-section-default",
        "h11-feature-bytesify-object-message",
        "humanize-feature-naturalsize-zero-format",
        "boltons-feature-slugify-max-length",
    ]
    assert all(row["zero_hosted_usage_confirmed"] is True for row in rows)

    iniconfig = next(row for row in rows if row["repo_id"] == "iniconfig")
    assert iniconfig["candidate_count"] == 1
    assert iniconfig["candidates_tested"] == 1
    assert iniconfig["pass@1"] is True
    assert iniconfig["pass@3"] is True
    assert iniconfig["first_passing_rank"] == 1
    assert iniconfig["candidate_validation"]["status"] == "passed"
    assert iniconfig["candidate_validation"]["result"]["returncode"] == 0
    assert iniconfig["hidden_like_agreement"] == "agrees"
    assert iniconfig["residual_labels"] == []
    assert iniconfig["blockers"] == []
    assert iniconfig["candidate_record"]["status"] == "materialized"
    assert iniconfig["mutation_scope"]["production_files_changed"] == [
        "src/iniconfig/__init__.py"
    ]

    if humanize_supported:
        humanize = next(row for row in rows if row["repo_id"] == "humanize")
        assert humanize["candidate_count"] == 1
        assert humanize["candidates_tested"] == 1
        assert humanize["pass@1"] is True
        assert humanize["pass@3"] is True
        assert humanize["first_passing_rank"] == 1
        assert humanize["candidate_validation"]["status"] == "passed"
        assert humanize["candidate_validation"]["result"]["returncode"] == 0
        assert humanize["hidden_like_agreement"] == "agrees"
        assert humanize["residual_labels"] == []
        assert humanize["blockers"] == []
        assert humanize["candidate_record"]["status"] == "materialized"
        assert humanize["mutation_scope"]["production_files_changed"] == [
            "src/humanize/filesize.py"
        ]

    h11 = next(row for row in rows if row["repo_id"] == "h11")
    assert h11["candidate_count"] == 1
    assert h11["candidates_tested"] == 1
    assert h11["pass@1"] is True
    assert h11["pass@3"] is True
    assert h11["first_passing_rank"] == 1
    assert h11["candidate_validation"]["status"] == "passed"
    assert h11["candidate_validation"]["result"]["returncode"] == 0
    assert h11["hidden_like_agreement"] == "agrees"
    assert h11["residual_labels"] == []
    assert h11["blockers"] == []
    assert h11["candidate_record"]["status"] == "materialized"

    mutation_scope = h11["mutation_scope"]
    assert mutation_scope["files_changed"] == [
        "h11/_util.py",
        "h11/tests/test_util.py",
    ]
    assert mutation_scope["production_files_changed"] == ["h11/_util.py"]
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["one_production_file_constraint_preserved"] is True

    supported_repos = {"h11", "iniconfig"}
    if humanize_supported:
        supported_repos.add("humanize")
    blocked_rows = [row for row in rows if row["repo_id"] not in supported_repos]
    assert all(row["pass@1"] is False for row in blocked_rows)
    assert all(row["pass@3"] is False for row in blocked_rows)
    assert all(row["first_passing_rank"] is None for row in blocked_rows)
    assert all(row["candidate_validation"]["status"] == "blocked" for row in blocked_rows)
    assert all(
        "one_file_materialization_gap" in row["residual_labels"]
        for row in blocked_rows
    )


def test_feature_shadow_score_does_not_count_unvalidated_materialization(
    tmp_path: Path,
) -> None:
    h11_path = tmp_path / "h11"
    iniconfig_path = tmp_path / "iniconfig"
    humanize_path = tmp_path / "humanize"
    _write_synthetic_h11_checkout(h11_path)
    _write_synthetic_iniconfig_checkout(iniconfig_path)
    repo_paths = {"h11": h11_path, "iniconfig": iniconfig_path}
    humanize_supported = _humanize_feature_materializer_supported()
    if humanize_supported:
        _write_synthetic_humanize_checkout(humanize_path)
        repo_paths["humanize"] = humanize_path

    score = run_real_repo_feature_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths=repo_paths,
        validate_candidates=False,
    )
    rows = score["task_results"]
    h11 = next(row for row in rows if row["repo_id"] == "h11")
    iniconfig = next(row for row in rows if row["repo_id"] == "iniconfig")
    expected_count = 3 if humanize_supported else 2

    assert score["metrics"]["candidate_count"] == expected_count
    assert score["metrics"]["candidates_tested"] == 0
    assert score["metrics"]["pass@1"] == "0/4"
    assert score["metrics"]["pass@3"] == "0/4"
    assert h11["candidate_validation"]["status"] == "deferred"
    assert iniconfig["candidate_validation"]["status"] == "deferred"
    assert h11["pass@1"] is False
    assert h11["pass@3"] is False
    assert iniconfig["pass@1"] is False
    assert iniconfig["pass@3"] is False
    assert h11["first_passing_rank"] is None
    assert iniconfig["first_passing_rank"] is None
    if humanize_supported:
        humanize = next(row for row in rows if row["repo_id"] == "humanize")
        assert humanize["candidate_validation"]["status"] == "deferred"
        assert humanize["pass@1"] is False
        assert humanize["pass@3"] is False
        assert humanize["first_passing_rank"] is None
        assert "deferred" in humanize["residual_labels"]
    assert "candidate_validation_deferred" not in h11["residual_labels"]
    assert "deferred" in h11["residual_labels"]
    assert "deferred" in iniconfig["residual_labels"]
    assert score["gate_decision"]["decision"] == "remain_shadow_only"


def test_feature_shadow_score_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    h11_path = tmp_path / "h11"
    iniconfig_path = tmp_path / "iniconfig"
    humanize_path = tmp_path / "humanize"
    _write_synthetic_h11_checkout(h11_path)
    _write_synthetic_iniconfig_checkout(iniconfig_path)
    repo_paths = {"h11": h11_path, "iniconfig": iniconfig_path}
    humanize_supported = _humanize_feature_materializer_supported()
    if humanize_supported:
        _write_synthetic_humanize_checkout(humanize_path)
        repo_paths["humanize"] = humanize_path
    score = run_real_repo_feature_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths=repo_paths,
        validate_candidates=True,
    )

    score_path = write_real_repo_feature_shadow_score(
        score,
        tmp_path / "score.json",
    )
    report_path = write_real_repo_feature_shadow_report(
        score,
        tmp_path / "report.md",
    )

    expected_pass = "3/4" if humanize_supported else "2/4"
    expected_heldout = "2/3" if humanize_supported else "1/3"
    expected_repos = "3" if humanize_supported else "2"
    assert json.loads(score_path.read_text(encoding="utf-8"))["metrics"]["pass@3"] == expected_pass
    report = report_path.read_text(encoding="utf-8")
    assert "REAL-011 One-File Feature Shadow Score" in report
    assert "Calibration pass@3: `1/1`" in report
    assert f"Held-out pass@3: `{expected_heldout}`" in report
    assert f"pass@1: `{expected_pass}`" in report
    assert f"pass@3: `{expected_pass}`" in report
    assert f"Distinct repos passing: `{expected_repos}`" in report
    assert "Production-file constraint preserved: `true`" in report
    assert "| `iniconfig-feature-section-default` | calibration | passed | True | True | 1 |" in report
    assert "| `h11-feature-bytesify-object-message` | heldout | passed | True | True | 1 |" in report
    if humanize_supported:
        assert "| `humanize-feature-naturalsize-zero-format` | heldout | passed | True | True | 1 |" in report
    assert "allow_guarded_one_file_feature_opt_in" in report
    assert format_real_repo_feature_shadow_score(score) == report
