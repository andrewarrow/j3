from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from j3.features import FEATURE_VERSION, embed_python_source
from j3.repo_state import (
    REPO_STATE_AGGREGATE_KIND,
    REPO_STATE_SCHEMA_VERSION,
    encode_repo_state,
    encode_repo_state_record,
)


def test_encode_repo_state_records_stable_python_file_metadata(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "z.py").write_text("VALUE = 2\n", encoding="utf-8")
    (package / "a.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("not Python\n", encoding="utf-8")

    state = encode_repo_state(tmp_path, embedding_dim=32)
    record = state.to_record()

    assert json.loads(json.dumps(record, sort_keys=True)) == record
    assert record["schema_version"] == REPO_STATE_SCHEMA_VERSION
    assert record["feature_version"] == FEATURE_VERSION
    assert record["embedding_dim"] == 32
    assert record["included_python_file_paths"] == ["pkg/a.py", "z.py"]
    assert record["aggregate"] == {
        "kind": REPO_STATE_AGGREGATE_KIND,
        "python_file_count": 2,
        "total_python_byte_count": len(
            b"def add(left, right):\n    return left + right\n"
        )
        + len(b"VALUE = 2\n"),
    }
    assert record["files"] == [
        {
            "path": "pkg/a.py",
            "sha256": hashlib.sha256(
                b"def add(left, right):\n    return left + right\n"
            ).hexdigest(),
            "byte_count": len(b"def add(left, right):\n    return left + right\n"),
        },
        {
            "path": "z.py",
            "sha256": hashlib.sha256(b"VALUE = 2\n").hexdigest(),
            "byte_count": len(b"VALUE = 2\n"),
        },
    ]
    assert len(record["repo_embedding"]) == 32


def test_encode_repo_state_aggregates_python_embeddings_by_mean(
    tmp_path: Path,
) -> None:
    first = "def add(left, right):\n    return left + right\n"
    second = "def subtract(left, right):\n    return left - right\n"
    (tmp_path / "b.py").write_text(second, encoding="utf-8")
    (tmp_path / "a.py").write_text(first, encoding="utf-8")

    record = encode_repo_state_record(tmp_path, embedding_dim=16)

    first_embedding = embed_python_source(first, dim=16)
    second_embedding = embed_python_source(second, dim=16)
    expected = [
        (left + right) / 2
        for left, right in zip(first_embedding, second_embedding, strict=True)
    ]
    assert record["included_python_file_paths"] == ["a.py", "b.py"]
    assert record["repo_embedding"] == expected


def test_encode_empty_repo_state_uses_zero_embedding(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("empty of Python files\n", encoding="utf-8")

    record = encode_repo_state_record(tmp_path, embedding_dim=24)

    assert record["included_python_file_paths"] == []
    assert record["files"] == []
    assert record["aggregate"] == {
        "kind": REPO_STATE_AGGREGATE_KIND,
        "python_file_count": 0,
        "total_python_byte_count": 0,
    }
    assert record["repo_embedding"] == [0.0] * 24


def test_encode_repo_state_uses_repo_source_exclusions(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('included')\n", encoding="utf-8")
    excluded = tmp_path / ".venv" / "lib"
    excluded.mkdir(parents=True)
    (excluded / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "cached.py").write_text("print('ignored')\n", encoding="utf-8")

    record = encode_repo_state_record(tmp_path, embedding_dim=16)

    assert record["included_python_file_paths"] == ["app.py"]
    assert [file["path"] for file in record["files"]] == ["app.py"]  # type: ignore[index]


def test_encode_repo_state_validates_embedding_dimension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="embedding_dim must be >= 8"):
        encode_repo_state(tmp_path, embedding_dim=7)


def test_encode_repo_state_rejects_missing_repo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="repo does not exist"):
        encode_repo_state(tmp_path / "missing", embedding_dim=16)
