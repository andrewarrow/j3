from __future__ import annotations

import json
from pathlib import Path

from j3.real_repo_shadow_score import (
    CandidateValidationResult,
    format_real_repo_tests_only_shadow_score,
    run_real_repo_tests_only_shadow_score,
    write_real_repo_tests_only_shadow_report,
    write_real_repo_tests_only_shadow_score,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


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

    def __getitem__(self, name: str) -> dict[str, str]:
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


def test_parse_sections() -> None:
    assert IniConfig("source.ini").source == "source.ini"


def test_duplicate_keys_report_key_name() -> None:
    with pytest.raises(ParseError, match="key"):
        raise ParseError("source.ini", 1, "duplicate name 'key'")
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


def _passing_validation_runner(
    command: str,
    cwd: Path,
    timeout_seconds: int,
) -> CandidateValidationResult:
    if "h11/tests/test_util.py" in command:
        stdout = "11 passed in 0.02s\n"
    elif "tests/test_filesize.py" in command:
        stdout = "79 passed in 0.03s\n"
    elif "tests/test_strutils.py" in command:
        stdout = "20 passed in 0.03s\n"
    else:
        stdout = "54 passed in 0.03s\n"
    return CandidateValidationResult(
        command=command,
        cwd=str(cwd),
        timeout_seconds=timeout_seconds,
        returncode=0,
        stdout=stdout,
        status="passed",
    )


def test_real_repo_tests_only_shadow_score_scores_iniconfig_candidate(
    tmp_path: Path,
) -> None:
    iniconfig_path = tmp_path / "iniconfig"
    h11_path = tmp_path / "h11"
    humanize_path = tmp_path / "humanize"
    boltons_path = tmp_path / "boltons"
    _write_synthetic_iniconfig_checkout(iniconfig_path)
    _write_synthetic_h11_checkout(h11_path)
    _write_synthetic_humanize_checkout(humanize_path)
    _write_synthetic_boltons_checkout(boltons_path)

    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={
            "iniconfig": iniconfig_path,
            "h11": h11_path,
            "humanize": humanize_path,
            "boltons": boltons_path,
        },
        validate_candidates=True,
        validation_runner=_passing_validation_runner,
    )

    assert json.loads(json.dumps(score)) == score
    assert score["schema_version"] == "real-repo-tests-shadow-score-v1"
    assert score["record_kind"] == "real_repo_tests_only_shadow_score"
    assert score["zero_hosted_usage_confirmed"] is True

    metrics = score["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["tasks_scored"] == 4
    assert metrics["candidate_count"] == 4
    assert metrics["candidates_tested"] == 4
    assert metrics["pass@1"] == "4/4"
    assert metrics["pass@3"] == "4/4"
    assert metrics["first_passing_ranks"] == [1, 1, 1, 1]
    assert metrics["calibration"]["pass@3"] == "1/1"
    assert metrics["heldout"]["pass@3"] == "3/3"
    assert metrics["correct_test_location"] == "4/4"
    assert metrics["production_file_modifications"] == 0
    assert metrics["writes_outside_allowlist"] == 0
    assert metrics["mutation_scope_violations"] == {
        "production_file_modifications": 0,
        "writes_outside_allowlist": 0,
        "candidate_target_path_violations": 0,
    }
    assert metrics["candidate_validation_statuses"]["passed"] == 4
    assert metrics["candidate_validation_statuses"]["blocked"] == 0
    assert metrics["hidden_like_agreement"]["agreeing"] == 4
    assert metrics["hidden_like_agreement"]["not_run"] == 0

    gate = score["gate_decision"]
    assert isinstance(gate, dict)
    assert gate["decision"] == "allow_guarded_tests_only_opt_in"
    assert gate["passed"] is True
    assert gate["guarded_opt_in_allowed"] is True
    assert gate["blocked_rows"] == []
    assert gate["failed_checks"] == []
    assert gate["guarded_opt_in_scope"]["allowed_task_ids"] == [
        "iniconfig-tests-parse-comments",
        "h11-tests-bytesify-memoryview",
        "humanize-tests-naturalsize-negative-strings",
        "boltons-tests-slugify-delimiter",
    ]

    rows = score["task_results"]
    assert isinstance(rows, list)
    assert {row["task_id"] for row in rows} == {
        "iniconfig-tests-parse-comments",
        "h11-tests-bytesify-memoryview",
        "humanize-tests-naturalsize-negative-strings",
        "boltons-tests-slugify-delimiter",
    }
    assert all(row["zero_hosted_usage_confirmed"] is True for row in rows)

    iniconfig = next(row for row in rows if row["repo_id"] == "iniconfig")
    assert iniconfig["candidate_count"] == 1
    assert iniconfig["candidates_tested"] == 1
    assert iniconfig["pass@1"] is True
    assert iniconfig["pass@3"] is True
    assert iniconfig["first_passing_rank"] == 1
    assert iniconfig["candidate_validation"]["status"] == "passed"
    assert iniconfig["candidate_validation"]["result"]["stdout"] == (
        "54 passed in 0.03s\n"
    )
    assert iniconfig["hidden_like_agreement"] == "agrees"
    assert iniconfig["residual_labels"] == []
    assert iniconfig["blockers"] == []
    assert iniconfig["candidate_record"]["status"] == "materialized"

    mutation_scope = iniconfig["mutation_scope"]
    assert mutation_scope["files_changed"] == ["testing/test_iniconfig.py"]
    assert mutation_scope["production_files_changed"] == []
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["candidate_target_path_violations"] == []
    assert mutation_scope["candidate_after"]["test_case_ids"] == [
        "iniconfig_comment_only_lines",
        "iniconfig_inline_section_comments",
        "iniconfig_duplicate_key_reports_name",
    ]

    h11 = next(row for row in rows if row["repo_id"] == "h11")
    assert h11["candidate_count"] == 1
    assert h11["candidates_tested"] == 1
    assert h11["pass@1"] is True
    assert h11["pass@3"] is True
    assert h11["first_passing_rank"] == 1
    assert h11["candidate_validation"]["status"] == "passed"
    assert h11["candidate_validation"]["result"]["stdout"] == "11 passed in 0.02s\n"
    assert h11["hidden_like_agreement"] == "agrees"
    assert h11["residual_labels"] == []
    assert h11["blockers"] == []
    assert h11["candidate_record"]["status"] == "materialized"
    assert h11["mutation_scope"]["files_changed"] == ["h11/tests/test_util.py"]
    assert h11["mutation_scope"]["production_files_changed"] == []
    assert h11["mutation_scope"]["writes_outside_allowlist"] == []
    assert h11["mutation_scope"]["candidate_after"]["test_case_ids"] == [
        "h11_bytesify_bytearray",
        "h11_bytesify_memoryview",
        "h11_bytesify_ascii_str",
        "h11_bytesify_non_ascii_str",
        "h11_bytesify_int_type_error",
    ]

    humanize = next(row for row in rows if row["repo_id"] == "humanize")
    assert humanize["candidate_count"] == 1
    assert humanize["candidates_tested"] == 1
    assert humanize["pass@1"] is True
    assert humanize["pass@3"] is True
    assert humanize["first_passing_rank"] == 1
    assert humanize["candidate_validation"]["status"] == "passed"
    assert humanize["candidate_validation"]["result"]["stdout"] == (
        "79 passed in 0.03s\n"
    )
    assert humanize["hidden_like_agreement"] == "agrees"
    assert humanize["residual_labels"] == []
    assert humanize["blockers"] == []
    assert humanize["candidate_record"]["status"] == "materialized"
    assert humanize["mutation_scope"]["files_changed"] == ["tests/test_filesize.py"]
    assert humanize["mutation_scope"]["production_files_changed"] == []
    assert humanize["mutation_scope"]["writes_outside_allowlist"] == []
    assert humanize["mutation_scope"]["candidate_after"]["test_case_ids"] == [
        "humanize_naturalsize_negative_numeric_strings",
        "humanize_naturalsize_negative_gnu_suffixes",
        "humanize_naturalsize_negative_binary_suffixes",
    ]

    boltons = next(row for row in rows if row["repo_id"] == "boltons")
    assert boltons["candidate_count"] == 1
    assert boltons["candidates_tested"] == 1
    assert boltons["pass@1"] is True
    assert boltons["pass@3"] is True
    assert boltons["first_passing_rank"] == 1
    assert boltons["candidate_validation"]["status"] == "passed"
    assert boltons["candidate_validation"]["result"]["stdout"] == (
        "20 passed in 0.03s\n"
    )
    assert boltons["hidden_like_agreement"] == "agrees"
    assert boltons["residual_labels"] == []
    assert boltons["blockers"] == []
    assert boltons["candidate_record"]["status"] == "materialized"
    assert boltons["mutation_scope"]["files_changed"] == ["tests/test_strutils.py"]
    assert boltons["mutation_scope"]["production_files_changed"] == []
    assert boltons["mutation_scope"]["writes_outside_allowlist"] == []
    assert boltons["mutation_scope"]["candidate_after"]["test_case_ids"] == [
        "boltons_slugify_custom_delimiters",
        "boltons_slugify_empty_string",
        "boltons_slugify_ascii_output",
        "boltons_slugify_lower_false",
    ]


def test_shadow_score_blocks_materialized_rows_without_checkout(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "iniconfig"
    _write_synthetic_iniconfig_checkout(repo_path)

    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={"iniconfig": repo_path},
        validate_candidates=True,
        validation_runner=_passing_validation_runner,
    )
    rows = score["task_results"]
    assert isinstance(rows, list)

    humanize = next(item for item in rows if item["repo_id"] == "humanize")
    assert humanize["candidate_count"] == 0
    assert humanize["candidate_validation"]["status"] == "blocked"
    assert humanize["candidate_validation"]["not_run_reason"] == (
        "candidate_checkout_missing"
    )

    boltons = next(item for item in rows if item["repo_id"] == "boltons")
    assert boltons["candidate_count"] == 0
    assert boltons["candidate_validation"]["status"] == "blocked"
    assert boltons["candidate_validation"]["not_run_reason"] == (
        "candidate_checkout_missing"
    )
    assert boltons["blockers"] == [
        {
            "field": "repo_path",
            "reason": "candidate_checkout_missing",
            "message": (
                "boltons-tests-slugify-delimiter candidate scoring requires "
                "a checkout path"
            ),
        }
    ]
    assert "candidate_checkout_missing" in boltons["residual_labels"]


def test_shadow_score_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    iniconfig_path = tmp_path / "iniconfig"
    h11_path = tmp_path / "h11"
    humanize_path = tmp_path / "humanize"
    boltons_path = tmp_path / "boltons"
    _write_synthetic_iniconfig_checkout(iniconfig_path)
    _write_synthetic_h11_checkout(h11_path)
    _write_synthetic_humanize_checkout(humanize_path)
    _write_synthetic_boltons_checkout(boltons_path)
    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={
            "iniconfig": iniconfig_path,
            "h11": h11_path,
            "humanize": humanize_path,
            "boltons": boltons_path,
        },
        validate_candidates=True,
        validation_runner=_passing_validation_runner,
    )

    score_path = write_real_repo_tests_only_shadow_score(
        score,
        tmp_path / "score.json",
    )
    report_path = write_real_repo_tests_only_shadow_report(
        score,
        tmp_path / "report.md",
    )

    assert json.loads(score_path.read_text(encoding="utf-8"))["metrics"]["pass@3"] == "4/4"
    report = report_path.read_text(encoding="utf-8")
    assert "REAL-010 Tests-Only Shadow Score" in report
    assert "Calibration pass@3: `1/1`" in report
    assert "Held-out pass@3: `3/3`" in report
    assert "pass@3: `4/4`" in report
    assert "| `iniconfig-tests-parse-comments` | calibration | passed | True | True | 1 |" in report
    assert "| `h11-tests-bytesify-memoryview` | heldout | passed | True | True | 1 |" in report
    assert "| `humanize-tests-naturalsize-negative-strings` | heldout | passed | True | True | 1 |" in report
    assert "| `boltons-tests-slugify-delimiter` | heldout | passed | True | True | 1 |" in report
    assert "allow_guarded_tests_only_opt_in" in report
    assert "Blocked rows: `none`" in report
    assert format_real_repo_tests_only_shadow_score(score) == report
