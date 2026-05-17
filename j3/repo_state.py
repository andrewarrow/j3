"""Deterministic repository state encoder for Python source files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from j3.features import FEATURE_VERSION as PYTHON_SOURCE_FEATURE_VERSION
from j3.features import embed_python_source, mean_vector
from j3.repo import iter_python_sources


REPO_STATE_SCHEMA_VERSION = "repo-state-v1"
REPO_STATE_AGGREGATE_KIND = "mean-python-source-embeddings-v1"
DEFAULT_REPO_STATE_EMBEDDING_DIM = 256
MIN_REPO_STATE_EMBEDDING_DIM = 8


@dataclass(frozen=True, slots=True)
class RepoStateFile:
    """Metadata for one Python file included in a repo-state record."""

    path: str
    sha256: str
    byte_count: int

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True, slots=True)
class RepoState:
    """Stable JSON-serializable representation of a Python repository state."""

    schema_version: str
    feature_version: str
    embedding_dim: int
    included_python_file_paths: tuple[str, ...]
    files: tuple[RepoStateFile, ...]
    repo_embedding: tuple[float, ...]
    aggregate_kind: str = REPO_STATE_AGGREGATE_KIND

    @property
    def python_file_count(self) -> int:
        return len(self.files)

    @property
    def total_python_byte_count(self) -> int:
        return sum(file.byte_count for file in self.files)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "feature_version": self.feature_version,
            "embedding_dim": self.embedding_dim,
            "included_python_file_paths": list(self.included_python_file_paths),
            "files": [file.to_record() for file in self.files],
            "aggregate": {
                "kind": self.aggregate_kind,
                "python_file_count": self.python_file_count,
                "total_python_byte_count": self.total_python_byte_count,
            },
            "repo_embedding": list(self.repo_embedding),
        }


def encode_repo_state(
    repo_root: Path,
    *,
    embedding_dim: int = DEFAULT_REPO_STATE_EMBEDDING_DIM,
) -> RepoState:
    """Encode Python files under ``repo_root`` into a deterministic repo state."""

    if embedding_dim < MIN_REPO_STATE_EMBEDDING_DIM:
        raise ValueError(
            f"embedding_dim must be >= {MIN_REPO_STATE_EMBEDDING_DIM}"
        )

    sources = iter_python_sources(repo_root)
    file_records: list[RepoStateFile] = []
    file_embeddings: list[list[float]] = []

    for source in sources:
        raw_bytes = source.path.read_bytes()
        embedding = embed_python_source(source.text, dim=embedding_dim)
        _validate_embedding_dimension(
            embedding,
            dim=embedding_dim,
            context=f"embedding for {source.relative_path}",
        )
        file_records.append(
            RepoStateFile(
                path=source.relative_path,
                sha256=hashlib.sha256(raw_bytes).hexdigest(),
                byte_count=len(raw_bytes),
            )
        )
        file_embeddings.append(embedding)

    repo_embedding = mean_vector(file_embeddings, dim=embedding_dim)
    _validate_embedding_dimension(
        repo_embedding,
        dim=embedding_dim,
        context="repo embedding",
    )

    return RepoState(
        schema_version=REPO_STATE_SCHEMA_VERSION,
        feature_version=PYTHON_SOURCE_FEATURE_VERSION,
        embedding_dim=embedding_dim,
        included_python_file_paths=tuple(file.path for file in file_records),
        files=tuple(file_records),
        repo_embedding=tuple(repo_embedding),
    )


def encode_repo_state_record(
    repo_root: Path,
    *,
    embedding_dim: int = DEFAULT_REPO_STATE_EMBEDDING_DIM,
) -> dict[str, object]:
    """Return a JSON-serializable repo-state record."""

    return encode_repo_state(repo_root, embedding_dim=embedding_dim).to_record()


def _validate_embedding_dimension(
    embedding: list[float],
    *,
    dim: int,
    context: str,
) -> None:
    if len(embedding) != dim:
        raise ValueError(f"{context} must have dimension {dim}")
