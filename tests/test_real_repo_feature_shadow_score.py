from __future__ import annotations

import json
from pathlib import Path

from j3.real_repo_feature_shadow_score import (
    format_real_repo_feature_shadow_score,
    run_real_repo_feature_shadow_score,
    write_real_repo_feature_shadow_report,
    write_real_repo_feature_shadow_score,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


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


def test_feature_shadow_score_counts_h11_candidate_and_blocks_unsupported_tasks(
    tmp_path: Path,
) -> None:
    h11_path = tmp_path / "h11"
    _write_synthetic_h11_checkout(h11_path)

    score = run_real_repo_feature_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={"h11": h11_path},
        validate_candidates=True,
    )

    assert json.loads(json.dumps(score, sort_keys=True)) == score
    assert score["schema_version"] == "real-repo-feature-shadow-score-v1"
    assert score["record_kind"] == "real_repo_one_file_feature_shadow_score"
    assert score["zero_hosted_usage_confirmed"] is True

    metrics = score["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["tasks_scored"] == 4
    assert metrics["candidate_count"] == 1
    assert metrics["candidates_tested"] == 1
    assert metrics["pass@1"] == "1/4"
    assert metrics["pass@3"] == "1/4"
    assert metrics["first_passing_ranks"] == [None, 1, None, None]
    assert metrics["distinct_repos_passing"] == ["h11"]
    assert metrics["distinct_repos_passing_count"] == 1
    assert metrics["production_files_changed"] == 1
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
    assert metrics["candidate_validation_statuses"]["passed"] == 1
    assert metrics["candidate_validation_statuses"]["blocked"] == 3
    assert metrics["hidden_like_agreement"]["agreeing"] == 1
    assert metrics["hidden_like_agreement"]["not_run"] == 3

    gate = score["gate_decision"]
    assert isinstance(gate, dict)
    assert gate["decision"] == "remain_shadow_only"
    assert gate["passed"] is False
    assert gate["guarded_opt_in_allowed"] is False

    rows = score["task_results"]
    assert isinstance(rows, list)
    assert [row["task_id"] for row in rows] == [
        "iniconfig-feature-section-default",
        "h11-feature-bytesify-object-message",
        "humanize-feature-naturalsize-zero-format",
        "boltons-feature-slugify-max-length",
    ]
    assert all(row["zero_hosted_usage_confirmed"] is True for row in rows)

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

    blocked_rows = [row for row in rows if row["repo_id"] != "h11"]
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
    _write_synthetic_h11_checkout(h11_path)

    score = run_real_repo_feature_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={"h11": h11_path},
        validate_candidates=False,
    )
    rows = score["task_results"]
    h11 = next(row for row in rows if row["repo_id"] == "h11")

    assert score["metrics"]["candidate_count"] == 1
    assert score["metrics"]["candidates_tested"] == 0
    assert score["metrics"]["pass@1"] == "0/4"
    assert score["metrics"]["pass@3"] == "0/4"
    assert h11["candidate_validation"]["status"] == "deferred"
    assert h11["pass@1"] is False
    assert h11["pass@3"] is False
    assert h11["first_passing_rank"] is None
    assert "candidate_validation_deferred" not in h11["residual_labels"]
    assert "deferred" in h11["residual_labels"]
    assert score["gate_decision"]["decision"] == "remain_shadow_only"


def test_feature_shadow_score_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    h11_path = tmp_path / "h11"
    _write_synthetic_h11_checkout(h11_path)
    score = run_real_repo_feature_shadow_score(
        MANIFEST_PATH,
        created_at="2026-05-18T00:00:00+00:00",
        repo_paths={"h11": h11_path},
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

    assert json.loads(score_path.read_text(encoding="utf-8"))["metrics"]["pass@3"] == "1/4"
    report = report_path.read_text(encoding="utf-8")
    assert "REAL-009 One-File Feature Shadow Score" in report
    assert "pass@1: `1/4`" in report
    assert "pass@3: `1/4`" in report
    assert "Distinct repos passing: `1`" in report
    assert "Production-file constraint preserved: `true`" in report
    assert "| `h11-feature-bytesify-object-message` | heldout | passed | True | True | 1 |" in report
    assert "remain_shadow_only" in report
    assert format_real_repo_feature_shadow_score(score) == report
