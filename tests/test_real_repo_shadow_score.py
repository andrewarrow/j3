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


def _passing_validation_runner(
    command: str,
    cwd: Path,
    timeout_seconds: int,
) -> CandidateValidationResult:
    return CandidateValidationResult(
        command=command,
        cwd=str(cwd),
        timeout_seconds=timeout_seconds,
        returncode=0,
        stdout="54 passed in 0.03s\n",
        status="passed",
    )


def test_real_repo_tests_only_shadow_score_scores_iniconfig_candidate(
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

    assert json.loads(json.dumps(score)) == score
    assert score["schema_version"] == "real-repo-tests-shadow-score-v1"
    assert score["record_kind"] == "real_repo_tests_only_shadow_score"
    assert score["zero_hosted_usage_confirmed"] is True

    metrics = score["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["tasks_scored"] == 4
    assert metrics["candidate_count"] == 1
    assert metrics["candidates_tested"] == 1
    assert metrics["pass@1"] == "1/4"
    assert metrics["pass@3"] == "1/4"
    assert metrics["first_passing_ranks"] == [1, None, None, None]
    assert metrics["correct_test_location"] == "1/4"
    assert metrics["production_file_modifications"] == 0
    assert metrics["writes_outside_allowlist"] == 0
    assert metrics["hidden_like_agreement"]["agreeing"] == 1
    assert metrics["hidden_like_agreement"]["not_run"] == 3

    gate = score["gate_decision"]
    assert isinstance(gate, dict)
    assert gate["decision"] == "remain_shadow_only"
    assert gate["passed"] is False
    assert gate["guarded_opt_in_allowed"] is False

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

    heldout_rows = [row for row in rows if row["repo_split"] == "heldout"]
    assert all(row["pass@1"] is False for row in heldout_rows)
    assert all(row["pass@3"] is False for row in heldout_rows)
    assert all(row["first_passing_rank"] is None for row in heldout_rows)
    assert all(row["hidden_like_agreement"] == "not_run" for row in heldout_rows)
    assert all(row["candidate_validation"]["status"] == "blocked" for row in heldout_rows)
    assert all(
        "test_case_materialization_gap" in row["residual_labels"]
        for row in heldout_rows
    )


def test_shadow_score_keeps_heldout_materializer_blockers(
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

    for repo_id in ("h11", "humanize", "boltons"):
        row = next(item for item in rows if item["repo_id"] == repo_id)
        assert row["candidate_count"] == 0
        assert row["candidates_tested"] == 0
        assert row["candidate_validation"]["status"] == "blocked"
        assert row["candidate_validation"]["not_run_reason"] == (
            "test_case_materialization_gap"
        )
        assert row["blockers"] == [
            {
                "field": "test_case_materialization",
                "reason": "test_case_materialization_gap",
                "message": (
                    "held-out tests-only candidate materialization is not "
                    f"implemented for {row['task_id']}"
                ),
            }
        ]
        assert "heldout_materializer_missing" in row["residual_labels"]
        assert "test_case_materialization_gap" in row["residual_labels"]


def test_shadow_score_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    repo_path = tmp_path / "iniconfig"
    _write_synthetic_iniconfig_checkout(repo_path)
    score = run_real_repo_tests_only_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={"iniconfig": repo_path},
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

    assert json.loads(score_path.read_text(encoding="utf-8"))["metrics"]["pass@3"] == "1/4"
    report = report_path.read_text(encoding="utf-8")
    assert "REAL-006 Tests-Only Shadow Score" in report
    assert "pass@3: `1/4`" in report
    assert "| `iniconfig-tests-parse-comments` | calibration | passed | True | True | 1 |" in report
    assert "remain_shadow_only" in report
    assert format_real_repo_tests_only_shadow_score(score) == report
