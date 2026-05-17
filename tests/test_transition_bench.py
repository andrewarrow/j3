from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.transition_bench import (
    SOURCE_CANDIDATE_OUTCOME,
    SOURCE_MINED_GIT_TRANSITION,
    SOURCE_PROMPT_REPO_TRANSITION,
    TRANSITION_BENCH_SCHEMA_VERSION,
    load_transition_bench_jsonl,
    normalize_transition_bench_jsonl,
    normalize_transition_bench_jsonl_with_report,
    validate_transition_bench_row,
    write_transition_bench_jsonl,
)


FIXTURES = Path(__file__).parent / "fixtures" / "transition_bench"


def test_normalizes_checked_in_source_fixtures_to_transition_bench_rows() -> None:
    prompt_rows = normalize_transition_bench_jsonl(
        FIXTURES / "prompt_repo_transitions.jsonl",
        source_kind=SOURCE_PROMPT_REPO_TRANSITION,
        embedding_dim=8,
    )
    git_rows = normalize_transition_bench_jsonl(
        FIXTURES / "mined_git_transitions.jsonl",
        source_kind=SOURCE_MINED_GIT_TRANSITION,
        embedding_dim=8,
    )
    candidate_rows = normalize_transition_bench_jsonl(
        FIXTURES / "candidate_outcomes.jsonl",
        source_kind=SOURCE_CANDIDATE_OUTCOME,
        embedding_dim=8,
    )
    rows = (*prompt_rows, *git_rows, *candidate_rows)

    assert [row["schema_version"] for row in rows] == [
        TRANSITION_BENCH_SCHEMA_VERSION,
        TRANSITION_BENCH_SCHEMA_VERSION,
        TRANSITION_BENCH_SCHEMA_VERSION,
        TRANSITION_BENCH_SCHEMA_VERSION,
    ]
    assert [row["source"]["kind"] for row in rows] == [
        SOURCE_PROMPT_REPO_TRANSITION,
        SOURCE_MINED_GIT_TRANSITION,
        SOURCE_CANDIDATE_OUTCOME,
        SOURCE_CANDIDATE_OUTCOME,
    ]

    prompt = prompt_rows[0]
    assert prompt["before"]["kind"] == "repo_state"
    assert prompt["context"]["kind"] == "prompt_context"
    assert prompt["action"]["kind"] == "create_repo"
    assert prompt["target"]["kind"] == "repo_after_embedding"
    assert prompt["target"]["embedding"] == [0.5, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert prompt["validation"]["status"] == "passed"
    assert prompt["cost"]["hosted_llm_api_tokens"] == 0
    assert prompt["cost"]["hosted_repo_context_bytes"] == 0

    git = git_rows[0]
    assert git["identity"]["file_path"] == "calculator.py"
    assert git["before"]["kind"] == "file_source"
    assert git["before"]["source"].endswith("return left - right\n")
    assert len(git["before"]["embedding"]) == 8
    assert git["target"]["kind"] == "file_after_embedding"
    assert len(git["target"]["embedding"]) == 8
    assert git["validation"]["available"] is False
    assert git["cost"]["validation_command_count"] == 0

    failed, passed = candidate_rows
    assert failed["identity"]["task"] == "calculator_add"
    assert failed["before"]["kind"] == "candidate_context"
    assert failed["action"]["kind"] == "change_operator"
    assert failed["target"]["kind"] == "validation_outcome"
    assert failed["validation"]["status"] == "failed"
    assert failed["target"]["passed"] is False
    assert passed["validation"]["status"] == "passed"
    assert passed["target"]["is_first_pass"] is True
    assert passed["cost"]["candidate_rank_index"] == 2


def test_transition_bench_writer_loader_are_deterministic(tmp_path: Path) -> None:
    rows = (
        *normalize_transition_bench_jsonl(
            FIXTURES / "prompt_repo_transitions.jsonl",
            source_kind=SOURCE_PROMPT_REPO_TRANSITION,
            embedding_dim=8,
        ),
        *normalize_transition_bench_jsonl(
            FIXTURES / "mined_git_transitions.jsonl",
            source_kind=SOURCE_MINED_GIT_TRANSITION,
            embedding_dim=8,
        ),
        *normalize_transition_bench_jsonl(
            FIXTURES / "candidate_outcomes.jsonl",
            source_kind=SOURCE_CANDIDATE_OUTCOME,
            embedding_dim=8,
        ),
    )

    first_path = write_transition_bench_jsonl(rows, tmp_path / "bench-a.jsonl")
    second_path = write_transition_bench_jsonl(rows, tmp_path / "bench-b.jsonl")

    assert first_path.read_text(encoding="utf-8") == second_path.read_text(
        encoding="utf-8"
    )
    assert load_transition_bench_jsonl(first_path) == rows
    assert all(line.startswith('{"action"') for line in first_path.read_text(encoding="utf-8").splitlines())


def test_transition_bench_validator_rejects_bad_rows() -> None:
    row = normalize_transition_bench_jsonl(
        FIXTURES / "mined_git_transitions.jsonl",
        source_kind=SOURCE_MINED_GIT_TRANSITION,
        embedding_dim=8,
    )[0]
    broken = json.loads(json.dumps(row))
    broken["before"]["embedding"] = [1.0, 2.0]

    with pytest.raises(ValueError, match="before.embedding length"):
        validate_transition_bench_row(broken)


def test_transition_bench_normalizer_skips_empty_mined_sources(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mined.jsonl"
    rows = [
        {
            "kind": "git_transition",
            "repo": "demo",
            "commit": "2222222222222222222222222222222222222222",
            "parent": "1111111111111111111111111111111111111111",
            "file_path": "calculator.py",
            "before_source": "",
            "after_source": "def add(left, right):\n    return left + right\n",
        },
        {
            "kind": "git_transition",
            "repo": "demo",
            "commit": "3333333333333333333333333333333333333333",
            "parent": "2222222222222222222222222222222222222222",
            "file_path": "calculator.py",
            "before_source": "def add(left, right):\n    return left - right\n",
            "after_source": "",
        },
        {
            "kind": "git_transition",
            "repo": "demo",
            "commit": "4444444444444444444444444444444444444444",
            "parent": "3333333333333333333333333333333333333333",
            "file_path": "calculator.py",
            "before_source": "def add(left, right):\n    return left - right\n",
            "after_source": "def add(left, right):\n    return left + right\n",
        },
    ]
    source.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = normalize_transition_bench_jsonl_with_report(
        source,
        source_kind=SOURCE_MINED_GIT_TRANSITION,
        embedding_dim=8,
    )

    assert len(result.rows) == 1
    assert result.input_row_count == 3
    assert result.source_kind == SOURCE_MINED_GIT_TRANSITION
    assert result.source_path == str(source.resolve())
    assert result.skipped_rows == (
        {
            "source_kind": SOURCE_MINED_GIT_TRANSITION,
            "source_path": str(source.resolve()),
            "row_index": 1,
            "reason": "empty_before_source",
            "repo": "demo",
            "file_path": "calculator.py",
            "commit": "2222222222222222222222222222222222222222",
        },
        {
            "source_kind": SOURCE_MINED_GIT_TRANSITION,
            "source_path": str(source.resolve()),
            "row_index": 2,
            "reason": "empty_after_source",
            "repo": "demo",
            "file_path": "calculator.py",
            "commit": "3333333333333333333333333333333333333333",
        },
    )
    assert normalize_transition_bench_jsonl(
        source,
        source_kind=SOURCE_MINED_GIT_TRANSITION,
        embedding_dim=8,
    ) == result.rows


def test_transition_bench_normalizer_rejects_unknown_source_kind() -> None:
    with pytest.raises(ValueError, match="unsupported transition bench source kind"):
        normalize_transition_bench_jsonl(
            FIXTURES / "mined_git_transitions.jsonl",
            source_kind="unknown",
            embedding_dim=8,
        )
