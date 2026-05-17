"""Prompt-JEPA index with deterministic local encoders.

This module is intentionally retrieval-only. It builds a persisted prompt index
with separate context and target embeddings so later learned encoders can
replace the feature-hashing encoders without changing the artifact shape.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from prompt_intents import (
    PromptIntentRecord,
    load_prompt_intent_records,
)


PROMPT_JEPA_INDEX_FORMAT = "j3.prompt-jepa-index.v1"
PROMPT_JEPA_PREDICTOR_FORMAT = "j3.prompt-jepa-predictor.v0"
PROMPT_CONTEXT_ENCODER_SCHEMA_VERSION = "prompt-context-v1"
PROMPT_TARGET_ENCODER_SCHEMA_VERSION = "prompt-target-v1"
FEATURE_HASHING_KIND = "feature_hashing"
NEAREST_CONTEXT_DELTA_PREDICTOR_KIND = "nearest_context_delta"
DEFAULT_EMBEDDING_DIM = 256
MIN_EMBEDDING_DIM = 8
DEFAULT_RETRIEVAL_EVAL_FIELDS = (
    "expected_action",
    "repo_mode",
    "domain",
    "unsupported_requirement_family",
)


@dataclass(frozen=True, slots=True)
class PromptJepaEncoderMetadata:
    """Metadata for one deterministic feature-hashing encoder."""

    kind: str
    schema_version: str

    def to_record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class PromptJepaIndexMetadata:
    """Top-level Prompt-JEPA index metadata."""

    format: str
    embedding_dim: int
    context_encoder: PromptJepaEncoderMetadata
    target_encoder: PromptJepaEncoderMetadata
    sources: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "format": self.format,
            "embedding_dim": self.embedding_dim,
            "context_encoder": self.context_encoder.to_record(),
            "target_encoder": self.target_encoder.to_record(),
            "sources": list(self.sources),
        }


@dataclass(frozen=True, slots=True)
class PromptJepaIndexRow:
    """One indexed prompt/target pair with separate JEPA-shaped embeddings."""

    row_id: str
    split: str
    source_type: str
    prompt: str
    context_embedding: tuple[float, ...]
    target_embedding: tuple[float, ...]
    target: dict[str, object]
    source_path: str | None = None
    tags: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "id": self.row_id,
            "split": self.split,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "prompt": self.prompt,
            "context_embedding": list(self.context_embedding),
            "target_embedding": list(self.target_embedding),
            "target": _json_copy(self.target),
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class PromptJepaQueryResult:
    """Nearest-neighbor result for a prompt context query."""

    row_id: str
    score: float
    prompt: str
    split: str
    source_type: str
    target_metadata: dict[str, object]
    source_path: str | None = None
    tags: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "id": self.row_id,
            "score": self.score,
            "prompt": self.prompt,
            "split": self.split,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "target_metadata": _json_copy(self.target_metadata),
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class PromptJepaEvalResult:
    """Small retrieval metric container for later held-out evaluation wiring."""

    split: str
    total: int
    top_k: int
    field_matches: dict[str, int] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "prompt-jepa-retrieval-eval-v1",
            "split": self.split,
            "total": self.total,
            "top_k": self.top_k,
            "field_matches": dict(sorted(self.field_matches.items())),
        }


@dataclass(frozen=True, slots=True)
class PromptJepaPredictor:
    """Prompt-JEPA predictor v0 from context embedding into target space."""

    format: str
    kind: str
    embedding_dim: int
    train_split: str
    train_row_ids: tuple[str, ...]
    mean_delta: tuple[float, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "format": self.format,
            "kind": self.kind,
            "embedding_dim": self.embedding_dim,
            "train_split": self.train_split,
            "train_rows": len(self.train_row_ids),
            "train_row_ids": list(self.train_row_ids),
            "mean_delta": list(self.mean_delta),
            "decision": "predictor_v0_not_wired_to_production",
        }

    def predict_target_embedding(
        self,
        context_embedding: Sequence[float],
        *,
        index: "PromptJepaIndex",
    ) -> tuple[float, ...]:
        """Project one context embedding into target embedding space."""

        validate_prompt_jepa_predictor(self)
        validate_prompt_jepa_index(index)
        if len(context_embedding) != self.embedding_dim:
            raise ValueError(
                "context embedding dimension does not match predictor "
                f"dimension {self.embedding_dim}"
            )
        if index.metadata.embedding_dim != self.embedding_dim:
            raise ValueError(
                "index embedding dimension does not match predictor "
                f"dimension {self.embedding_dim}"
            )

        train_rows = _predictor_train_rows(index=index, predictor=self)
        nearest = max(
            train_rows,
            key=lambda row: (_dot(context_embedding, row.context_embedding), row.row_id),
        )
        delta = tuple(
            target_value - context_value
            for context_value, target_value in zip(
                nearest.context_embedding,
                nearest.target_embedding,
                strict=True,
            )
        )
        return _normalize(
            tuple(
                context_value + delta_value
                for context_value, delta_value in zip(
                    context_embedding,
                    delta,
                    strict=True,
                )
            )
        )


@dataclass(frozen=True, slots=True)
class PromptJepaFieldRetrievalMetrics:
    """Top-1 and top-k retrieval metrics for one scalar target field."""

    field: str
    total: int
    top_1_correct: int
    top_k_correct: int

    @property
    def top_1_accuracy(self) -> float:
        return self.top_1_correct / self.total if self.total else 0.0

    @property
    def top_k_accuracy(self) -> float:
        return self.top_k_correct / self.total if self.total else 0.0

    def to_record(self) -> dict[str, object]:
        return {
            "field": self.field,
            "total": self.total,
            "top_1_correct": self.top_1_correct,
            "top_1_accuracy": self.top_1_accuracy,
            "top_k_correct": self.top_k_correct,
            "top_k_accuracy": self.top_k_accuracy,
        }


@dataclass(frozen=True, slots=True)
class PromptJepaRetrievalMiss:
    """Representative held-out query whose nearest neighbors missed labels."""

    query_id: str
    split: str
    prompt: str
    missed_fields_top_1: tuple[str, ...]
    missed_fields_top_k: tuple[str, ...]
    expected: dict[str, str]
    nearest_neighbor_id: str | None
    nearest_neighbor_score: float | None
    nearest_neighbor_target: dict[str, str]
    top_k_neighbor_ids: tuple[str, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "query_id": self.query_id,
            "split": self.split,
            "prompt": self.prompt,
            "missed_fields_top_1": list(self.missed_fields_top_1),
            "missed_fields_top_k": list(self.missed_fields_top_k),
            "expected": dict(self.expected),
            "nearest_neighbor_id": self.nearest_neighbor_id,
            "nearest_neighbor_score": self.nearest_neighbor_score,
            "nearest_neighbor_target": dict(self.nearest_neighbor_target),
            "top_k_neighbor_ids": list(self.top_k_neighbor_ids),
        }


@dataclass(frozen=True, slots=True)
class PromptJepaRetrievalSplitResult:
    """Retrieval evaluation for one held-out split."""

    split: str
    total: int
    top_k: int
    field_metrics: dict[str, PromptJepaFieldRetrievalMetrics]
    misses: tuple[PromptJepaRetrievalMiss, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "split": self.split,
            "total": self.total,
            "top_k": self.top_k,
            "field_metrics": {
                field: self.field_metrics[field].to_record()
                for field in sorted(self.field_metrics)
            },
            "misses": [miss.to_record() for miss in self.misses],
        }


@dataclass(frozen=True, slots=True)
class PromptJepaRetrievalEvalResult:
    """Held-out retrieval evaluation over a train-only Prompt-JEPA index."""

    train_split: str
    train_rows: int
    embedding_dim: int
    top_k: int
    fields: tuple[str, ...]
    split_results: dict[str, PromptJepaRetrievalSplitResult]

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "prompt-jepa-retrieval-eval-v1",
            "decision": "evaluation_only_not_wired_to_production",
            "train_split": self.train_split,
            "train_rows": self.train_rows,
            "embedding_dim": self.embedding_dim,
            "top_k": self.top_k,
            "fields": list(self.fields),
            "splits": {
                split: self.split_results[split].to_record()
                for split in sorted(self.split_results)
            },
        }


@dataclass(frozen=True, slots=True)
class PromptJepaPredictedTargetEvalResult:
    """Held-out retrieval after context-to-target prediction."""

    train_split: str
    train_rows: int
    embedding_dim: int
    top_k: int
    fields: tuple[str, ...]
    predictor: PromptJepaPredictor
    split_results: dict[str, PromptJepaRetrievalSplitResult]

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "prompt-jepa-predicted-target-eval-v1",
            "decision": "evaluation_only_not_wired_to_production",
            "mode": "predicted-target",
            "train_split": self.train_split,
            "train_rows": self.train_rows,
            "embedding_dim": self.embedding_dim,
            "top_k": self.top_k,
            "fields": list(self.fields),
            "predictor": self.predictor.to_record(),
            "splits": {
                split: self.split_results[split].to_record()
                for split in sorted(self.split_results)
            },
        }


@dataclass(frozen=True, slots=True)
class PromptJepaIndex:
    """In-memory Prompt-JEPA index artifact."""

    metadata: PromptJepaIndexMetadata
    rows: tuple[PromptJepaIndexRow, ...]

    def to_record(self) -> dict[str, object]:
        record = self.metadata.to_record()
        record["rows"] = [row.to_record() for row in self.rows]
        return record

    def query(self, prompt: str, *, top_k: int = 5) -> tuple[PromptJepaQueryResult, ...]:
        """Return nearest rows by prompt context cosine similarity."""

        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        query_embedding = encode_prompt_context(
            prompt,
            dim=self.metadata.embedding_dim,
        )
        scored = [
            (
                _dot(query_embedding, row.context_embedding),
                row,
            )
            for row in self.rows
        ]
        scored.sort(key=lambda item: (-item[0], item[1].row_id))

        return tuple(
            PromptJepaQueryResult(
                row_id=row.row_id,
                score=score,
                prompt=row.prompt,
                split=row.split,
                source_type=row.source_type,
                source_path=row.source_path,
                target_metadata=_target_metadata(row.target),
                tags=row.tags,
            )
            for score, row in scored[:top_k]
        )


def default_prompt_jepa_metadata(
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    sources: Sequence[str] = (),
) -> PromptJepaIndexMetadata:
    """Create default metadata for the deterministic Prompt-JEPA V0 index."""

    _validate_embedding_dim(embedding_dim)
    return PromptJepaIndexMetadata(
        format=PROMPT_JEPA_INDEX_FORMAT,
        embedding_dim=embedding_dim,
        context_encoder=PromptJepaEncoderMetadata(
            kind=FEATURE_HASHING_KIND,
            schema_version=PROMPT_CONTEXT_ENCODER_SCHEMA_VERSION,
        ),
        target_encoder=PromptJepaEncoderMetadata(
            kind=FEATURE_HASHING_KIND,
            schema_version=PROMPT_TARGET_ENCODER_SCHEMA_VERSION,
        ),
        sources=tuple(sources),
    )


def encode_prompt_context(
    prompt: str,
    *,
    dim: int = DEFAULT_EMBEDDING_DIM,
    source_type: str | None = None,
    task_type: str | None = None,
    tags: Sequence[str] = (),
) -> tuple[float, ...]:
    """Encode prompt/task context into a fixed-size normalized vector."""

    _validate_embedding_dim(dim)
    features = _prompt_context_features(
        prompt,
        source_type=source_type,
        task_type=task_type,
        tags=tags,
    )
    return _normalize(_hash_features(features, dim=dim))


def encode_prompt_target(
    target: object,
    *,
    dim: int = DEFAULT_EMBEDDING_DIM,
) -> tuple[float, ...]:
    """Encode a structured target record into a fixed-size normalized vector."""

    _validate_embedding_dim(dim)
    target_record = target.to_record() if hasattr(target, "to_record") else target
    if not isinstance(target_record, Mapping):
        raise TypeError("target must be a mapping or expose to_record()")
    features = _target_features(target_record)
    return _normalize(_hash_features(features, dim=dim))


def build_prompt_jepa_index(
    records: Sequence[PromptIntentRecord],
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    source_path: Path | str | None = None,
) -> PromptJepaIndex:
    """Build a Prompt-JEPA index from loaded prompt-intent records."""

    _validate_embedding_dim(embedding_dim)
    if not records:
        raise ValueError("at least one prompt intent record is required")

    source = str(source_path) if source_path is not None else None
    metadata = default_prompt_jepa_metadata(
        embedding_dim=embedding_dim,
        sources=(source,) if source else (),
    )
    rows = tuple(
        PromptJepaIndexRow(
            row_id=record.row_id,
            split=record.split,
            source_type=record.source_type,
            source_path=source,
            prompt=record.prompt,
            context_embedding=encode_prompt_context(
                record.prompt,
                dim=embedding_dim,
                source_type=record.source_type,
                task_type=record.target.task_type,
                tags=record.tags,
            ),
            target_embedding=encode_prompt_target(record.target, dim=embedding_dim),
            target=record.target.to_record(),
            tags=record.tags,
        )
        for record in records
    )
    return PromptJepaIndex(metadata=metadata, rows=rows)


def build_prompt_jepa_index_from_path(
    path: Path,
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> PromptJepaIndex:
    """Load prompt-intent labels from JSON/JSONL and build an index."""

    return build_prompt_jepa_index(
        load_prompt_intent_records(path),
        embedding_dim=embedding_dim,
        source_path=path,
    )


def train_prompt_jepa_predictor(
    index: PromptJepaIndex,
    *,
    train_split: str = "train",
) -> PromptJepaPredictor:
    """Train the explicit Prompt-JEPA predictor v0 from indexed train rows."""

    validate_prompt_jepa_index(index)
    train_rows = [row for row in index.rows if row.split == train_split]
    if not train_rows:
        raise ValueError(f"no Prompt-JEPA rows found for train split {train_split!r}")

    dim = index.metadata.embedding_dim
    mean_delta = tuple(
        sum(row.target_embedding[i] - row.context_embedding[i] for row in train_rows)
        / len(train_rows)
        for i in range(dim)
    )
    predictor = PromptJepaPredictor(
        format=PROMPT_JEPA_PREDICTOR_FORMAT,
        kind=NEAREST_CONTEXT_DELTA_PREDICTOR_KIND,
        embedding_dim=dim,
        train_split=train_split,
        train_row_ids=tuple(row.row_id for row in train_rows),
        mean_delta=mean_delta,
    )
    validate_prompt_jepa_predictor(predictor)
    return predictor


def query_prompt_jepa_predicted_target(
    index: PromptJepaIndex,
    predictor: PromptJepaPredictor,
    prompt: str,
    *,
    top_k: int = 5,
    source_type: str | None = None,
    task_type: str | None = None,
    tags: Sequence[str] = (),
) -> tuple[PromptJepaQueryResult, ...]:
    """Predict a target embedding and retrieve nearest train target rows."""

    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    context_embedding = encode_prompt_context(
        prompt,
        dim=index.metadata.embedding_dim,
        source_type=source_type,
        task_type=task_type,
        tags=tags,
    )
    predicted_target = predictor.predict_target_embedding(
        context_embedding,
        index=index,
    )
    return _query_target_embeddings(
        index=index,
        predictor=predictor,
        target_embedding=predicted_target,
        top_k=top_k,
    )


def evaluate_prompt_jepa_retrieval(
    records: Sequence[PromptIntentRecord],
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    train_split: str = "train",
    eval_splits: Sequence[str] = ("validation", "test"),
    top_k: int = 3,
    fields: Sequence[str] = DEFAULT_RETRIEVAL_EVAL_FIELDS,
    miss_limit: int = 20,
    source_path: Path | str | None = None,
) -> PromptJepaRetrievalEvalResult:
    """Evaluate held-out prompts against nearest train-split rows.

    This builds a train-only retrieval index, queries each requested held-out
    split, and reports exact scalar-field matches for the nearest row and for
    any of the top-k rows. It is intentionally evaluation-only.
    """

    _validate_embedding_dim(embedding_dim)
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if miss_limit < 0:
        raise ValueError("miss_limit must be >= 0")
    if not fields:
        raise ValueError("at least one evaluation field is required")

    eval_fields = tuple(dict.fromkeys(fields))
    train_records = [record for record in records if record.split == train_split]
    if not train_records:
        raise ValueError(f"no prompt intent rows found for train split {train_split!r}")

    index = build_prompt_jepa_index(
        train_records,
        embedding_dim=embedding_dim,
        source_path=source_path,
    )
    split_results = {
        split: _evaluate_prompt_jepa_retrieval_split(
            [record for record in records if record.split == split],
            index=index,
            split=split,
            top_k=top_k,
            fields=eval_fields,
            miss_limit=miss_limit,
        )
        for split in eval_splits
    }
    return PromptJepaRetrievalEvalResult(
        train_split=train_split,
        train_rows=len(train_records),
        embedding_dim=embedding_dim,
        top_k=top_k,
        fields=eval_fields,
        split_results=split_results,
    )


def evaluate_prompt_jepa_predicted_target_retrieval(
    records: Sequence[PromptIntentRecord],
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    train_split: str = "train",
    eval_splits: Sequence[str] = ("validation", "test"),
    top_k: int = 3,
    fields: Sequence[str] = DEFAULT_RETRIEVAL_EVAL_FIELDS,
    miss_limit: int = 20,
    source_path: Path | str | None = None,
) -> PromptJepaPredictedTargetEvalResult:
    """Evaluate context-to-target predictions with train target retrieval."""

    _validate_embedding_dim(embedding_dim)
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if miss_limit < 0:
        raise ValueError("miss_limit must be >= 0")
    if not fields:
        raise ValueError("at least one evaluation field is required")

    eval_fields = tuple(dict.fromkeys(fields))
    train_records = [record for record in records if record.split == train_split]
    if not train_records:
        raise ValueError(f"no prompt intent rows found for train split {train_split!r}")

    index = build_prompt_jepa_index(
        train_records,
        embedding_dim=embedding_dim,
        source_path=source_path,
    )
    predictor = train_prompt_jepa_predictor(index, train_split=train_split)
    split_results = {
        split: _evaluate_prompt_jepa_predicted_target_split(
            [record for record in records if record.split == split],
            index=index,
            predictor=predictor,
            split=split,
            top_k=top_k,
            fields=eval_fields,
            miss_limit=miss_limit,
        )
        for split in eval_splits
    }
    return PromptJepaPredictedTargetEvalResult(
        train_split=train_split,
        train_rows=len(train_records),
        embedding_dim=embedding_dim,
        top_k=top_k,
        fields=eval_fields,
        predictor=predictor,
        split_results=split_results,
    )


def evaluate_prompt_jepa_predicted_target_retrieval_from_path(
    path: Path,
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    train_split: str = "train",
    eval_splits: Sequence[str] = ("validation", "test"),
    top_k: int = 3,
    fields: Sequence[str] = DEFAULT_RETRIEVAL_EVAL_FIELDS,
    miss_limit: int = 20,
) -> PromptJepaPredictedTargetEvalResult:
    """Load prompt-intent labels and evaluate predicted-target retrieval."""

    return evaluate_prompt_jepa_predicted_target_retrieval(
        load_prompt_intent_records(path),
        embedding_dim=embedding_dim,
        train_split=train_split,
        eval_splits=eval_splits,
        top_k=top_k,
        fields=fields,
        miss_limit=miss_limit,
        source_path=path,
    )


def evaluate_prompt_jepa_retrieval_from_path(
    path: Path,
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    train_split: str = "train",
    eval_splits: Sequence[str] = ("validation", "test"),
    top_k: int = 3,
    fields: Sequence[str] = DEFAULT_RETRIEVAL_EVAL_FIELDS,
    miss_limit: int = 20,
) -> PromptJepaRetrievalEvalResult:
    """Load prompt-intent labels and run held-out retrieval evaluation."""

    return evaluate_prompt_jepa_retrieval(
        load_prompt_intent_records(path),
        embedding_dim=embedding_dim,
        train_split=train_split,
        eval_splits=eval_splits,
        top_k=top_k,
        fields=fields,
        miss_limit=miss_limit,
        source_path=path,
    )


def save_prompt_jepa_predictor(predictor: PromptJepaPredictor, path: Path) -> None:
    """Persist a Prompt-JEPA predictor artifact as stable JSON."""

    validate_prompt_jepa_predictor(predictor)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(predictor.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_prompt_jepa_predictor(path: Path) -> PromptJepaPredictor:
    """Load and validate a persisted Prompt-JEPA predictor artifact."""

    data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Prompt-JEPA predictor must be a JSON object")
    predictor = _predictor_from_record(data)
    validate_prompt_jepa_predictor(predictor)
    return predictor


def save_prompt_jepa_index(index: PromptJepaIndex, path: Path) -> None:
    """Persist a Prompt-JEPA index as stable, validated JSON."""

    validate_prompt_jepa_index(index)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(index.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_prompt_jepa_index(path: Path) -> PromptJepaIndex:
    """Load and validate a persisted Prompt-JEPA index JSON artifact."""

    data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Prompt-JEPA index must be a JSON object")

    metadata = _metadata_from_record(data)
    rows_value = data.get("rows")
    if not isinstance(rows_value, list):
        raise ValueError("Prompt-JEPA index field 'rows' must be a list")

    rows = tuple(
        _row_from_record(row, index=index, dim=metadata.embedding_dim)
        for index, row in enumerate(rows_value)
    )
    loaded = PromptJepaIndex(metadata=metadata, rows=rows)
    validate_prompt_jepa_index(loaded)
    return loaded


def validate_prompt_jepa_index(index: PromptJepaIndex) -> None:
    """Validate index format, encoder schemas, and row vector dimensions."""

    if index.metadata.format != PROMPT_JEPA_INDEX_FORMAT:
        raise ValueError(
            f"unsupported Prompt-JEPA index format {index.metadata.format!r}"
        )
    _validate_embedding_dim(index.metadata.embedding_dim)
    _validate_encoder_metadata(
        index.metadata.context_encoder,
        expected_schema=PROMPT_CONTEXT_ENCODER_SCHEMA_VERSION,
        label="context_encoder",
    )
    _validate_encoder_metadata(
        index.metadata.target_encoder,
        expected_schema=PROMPT_TARGET_ENCODER_SCHEMA_VERSION,
        label="target_encoder",
    )
    if not index.rows:
        raise ValueError("Prompt-JEPA index must contain at least one row")

    seen_ids: set[str] = set()
    for row in index.rows:
        if not row.row_id:
            raise ValueError("Prompt-JEPA index rows must have non-empty ids")
        if row.row_id in seen_ids:
            raise ValueError(f"duplicate Prompt-JEPA row id {row.row_id!r}")
        seen_ids.add(row.row_id)
        if len(row.context_embedding) != index.metadata.embedding_dim:
            raise ValueError(
                f"row {row.row_id!r} context embedding dimension does not match "
                f"{index.metadata.embedding_dim}"
            )
        if len(row.target_embedding) != index.metadata.embedding_dim:
            raise ValueError(
                f"row {row.row_id!r} target embedding dimension does not match "
                f"{index.metadata.embedding_dim}"
            )
        if not isinstance(row.target, dict):
            raise ValueError(f"row {row.row_id!r} target must be an object")


def validate_prompt_jepa_predictor(predictor: PromptJepaPredictor) -> None:
    """Validate predictor format and vector dimensions."""

    if predictor.format != PROMPT_JEPA_PREDICTOR_FORMAT:
        raise ValueError(
            f"unsupported Prompt-JEPA predictor format {predictor.format!r}"
        )
    if predictor.kind != NEAREST_CONTEXT_DELTA_PREDICTOR_KIND:
        raise ValueError(f"unsupported Prompt-JEPA predictor kind {predictor.kind!r}")
    _validate_embedding_dim(predictor.embedding_dim)
    if not predictor.train_split:
        raise ValueError("Prompt-JEPA predictor train_split must be non-empty")
    if not predictor.train_row_ids:
        raise ValueError("Prompt-JEPA predictor must contain train row ids")
    if len(set(predictor.train_row_ids)) != len(predictor.train_row_ids):
        raise ValueError("Prompt-JEPA predictor train row ids must be unique")
    if len(predictor.mean_delta) != predictor.embedding_dim:
        raise ValueError(
            "Prompt-JEPA predictor mean_delta dimension does not match "
            f"{predictor.embedding_dim}"
        )


def _metadata_from_record(record: dict[str, object]) -> PromptJepaIndexMetadata:
    index_format = _required_str(record, "format", label="index")
    embedding_dim = record.get("embedding_dim")
    if not isinstance(embedding_dim, int) or isinstance(embedding_dim, bool):
        raise ValueError("Prompt-JEPA index field 'embedding_dim' must be an integer")
    _validate_embedding_dim(embedding_dim)

    context_encoder = _encoder_from_record(
        record.get("context_encoder"),
        field="context_encoder",
    )
    target_encoder = _encoder_from_record(
        record.get("target_encoder"),
        field="target_encoder",
    )
    sources = _optional_str_tuple(record.get("sources", []), field="sources")
    metadata = PromptJepaIndexMetadata(
        format=index_format,
        embedding_dim=embedding_dim,
        context_encoder=context_encoder,
        target_encoder=target_encoder,
        sources=sources,
    )
    if metadata.format != PROMPT_JEPA_INDEX_FORMAT:
        raise ValueError(f"unsupported Prompt-JEPA index format {metadata.format!r}")
    return metadata


def _predictor_from_record(record: dict[str, object]) -> PromptJepaPredictor:
    embedding_dim = record.get("embedding_dim")
    if not isinstance(embedding_dim, int) or isinstance(embedding_dim, bool):
        raise ValueError(
            "Prompt-JEPA predictor field 'embedding_dim' must be an integer"
        )
    _validate_embedding_dim(embedding_dim)
    return PromptJepaPredictor(
        format=_required_str(record, "format", label="predictor"),
        kind=_required_str(record, "kind", label="predictor"),
        embedding_dim=embedding_dim,
        train_split=_required_str(record, "train_split", label="predictor"),
        train_row_ids=_optional_str_tuple(
            record.get("train_row_ids", []),
            field="train_row_ids",
        ),
        mean_delta=_vector_from_record(
            record.get("mean_delta"),
            dim=embedding_dim,
            field="predictor mean_delta",
        ),
    )


def _encoder_from_record(value: object, *, field: str) -> PromptJepaEncoderMetadata:
    if not isinstance(value, dict):
        raise ValueError(f"Prompt-JEPA index field {field!r} must be an object")
    return PromptJepaEncoderMetadata(
        kind=_required_str(value, "kind", label=field),
        schema_version=_required_str(value, "schema_version", label=field),
    )


def _row_from_record(
    value: object,
    *,
    index: int,
    dim: int,
) -> PromptJepaIndexRow:
    if not isinstance(value, dict):
        raise ValueError(f"Prompt-JEPA row {index} must be an object")

    row_id = _required_str(value, "id", label=f"row {index}")
    target = value.get("target")
    if not isinstance(target, dict):
        raise ValueError(f"Prompt-JEPA row {row_id!r} field 'target' must be an object")
    source_path = value.get("source_path")
    if source_path is not None and not isinstance(source_path, str):
        raise ValueError(
            f"Prompt-JEPA row {row_id!r} field 'source_path' must be a string or null"
        )

    return PromptJepaIndexRow(
        row_id=row_id,
        split=_required_str(value, "split", label=f"row {row_id}"),
        source_type=_required_str(value, "source_type", label=f"row {row_id}"),
        source_path=source_path,
        prompt=_required_str(value, "prompt", label=f"row {row_id}"),
        context_embedding=_vector_from_record(
            value.get("context_embedding"),
            dim=dim,
            field=f"row {row_id} context_embedding",
        ),
        target_embedding=_vector_from_record(
            value.get("target_embedding"),
            dim=dim,
            field=f"row {row_id} target_embedding",
        ),
        target=_json_copy(target),
        tags=_optional_str_tuple(value.get("tags", []), field=f"row {row_id} tags"),
    )


def _prompt_context_features(
    prompt: str,
    *,
    source_type: str | None,
    task_type: str | None,
    tags: Sequence[str],
) -> Counter[str]:
    tokens = _prompt_tokens(prompt)
    normalized = " ".join(tokens)
    features: Counter[str] = Counter({"ctx:bias": 1})
    if normalized:
        features[f"ctx:prompt={normalized}"] += 1
        features[f"ctx:token_count_bucket={min(len(tokens), 12)}"] += 1
    if source_type:
        features[f"ctx:source_type={source_type}"] += 1
    if task_type:
        features[f"ctx:task_type={task_type}"] += 1
    for tag in tags:
        features[f"ctx:tag={tag}"] += 1

    features.update(f"ctx:tok={token}" for token in tokens)
    features.update(
        f"ctx:bigram={tokens[index]} {tokens[index + 1]}"
        for index in range(len(tokens) - 1)
    )
    features.update(
        f"ctx:trigram={tokens[index]} {tokens[index + 1]} {tokens[index + 2]}"
        for index in range(len(tokens) - 2)
    )
    padded = f" {normalized} "
    for width in range(3, 6):
        features.update(
            f"ctx:char{width}={padded[index:index + width]}"
            for index in range(len(padded) - width + 1)
        )
    return features


def _target_features(target: Mapping[str, object]) -> Counter[str]:
    features: Counter[str] = Counter({"tgt:bias": 1})
    _flatten_target_features(features, prefix="tgt", value=target)
    return features


def _flatten_target_features(
    features: Counter[str],
    *,
    prefix: str,
    value: object,
) -> None:
    if isinstance(value, Mapping):
        for key in sorted(value):
            item = value[key]
            key_prefix = f"{prefix}.{key}"
            features[f"{key_prefix}:present"] += 1
            _flatten_target_features(features, prefix=key_prefix, value=item)
    elif isinstance(value, list | tuple):
        features[f"{prefix}:len={len(value)}"] += 1
        for item in value:
            if isinstance(item, str | int | float | bool) or item is None:
                features[f"{prefix}:item={_feature_scalar(item)}"] += 1
            else:
                _flatten_target_features(features, prefix=f"{prefix}[]", value=item)
    else:
        features[f"{prefix}={_feature_scalar(value)}"] += 1


def _hash_features(features: Counter[str], *, dim: int) -> tuple[float, ...]:
    vector = [0.0] * dim
    for name, count in features.items():
        digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign * math.log1p(count)
    return tuple(vector)


def _normalize(vector: tuple[float, ...]) -> tuple[float, ...]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return vector
    return tuple(value / magnitude for value in vector)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    return sum(a * b for a, b in zip(left, right, strict=True))


def _target_metadata(target: Mapping[str, object]) -> dict[str, object]:
    metadata_fields = (
        "schema_version",
        "repo_mode",
        "task_type",
        "domain",
        "expected_action",
        "requires_clarification",
        "primary_artifact",
        "unsupported_requirement",
        "unsupported_requirement_family",
        "requested_interfaces",
        "features",
        "artifacts",
        "unsupported_requirements",
        "clarification_fields",
        "target_files",
        "features_to_add",
    )
    return {
        field_name: _json_copy(target[field_name])
        for field_name in metadata_fields
        if field_name in target
    }


def _predictor_train_rows(
    *,
    index: PromptJepaIndex,
    predictor: PromptJepaPredictor,
) -> tuple[PromptJepaIndexRow, ...]:
    train_row_ids = set(predictor.train_row_ids)
    rows = tuple(row for row in index.rows if row.row_id in train_row_ids)
    if len(rows) != len(train_row_ids):
        missing = sorted(train_row_ids.difference(row.row_id for row in rows))
        raise ValueError(
            "Prompt-JEPA predictor references rows missing from index: "
            + ", ".join(missing[:5])
        )
    return rows


def _query_target_embeddings(
    *,
    index: PromptJepaIndex,
    predictor: PromptJepaPredictor,
    target_embedding: Sequence[float],
    top_k: int,
) -> tuple[PromptJepaQueryResult, ...]:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if len(target_embedding) != index.metadata.embedding_dim:
        raise ValueError(
            "target embedding dimension does not match index "
            f"dimension {index.metadata.embedding_dim}"
        )

    scored = [
        (_dot(target_embedding, row.target_embedding), row)
        for row in _predictor_train_rows(index=index, predictor=predictor)
    ]
    scored.sort(key=lambda item: (-item[0], item[1].row_id))
    return tuple(
        PromptJepaQueryResult(
            row_id=row.row_id,
            score=score,
            prompt=row.prompt,
            split=row.split,
            source_type=row.source_type,
            source_path=row.source_path,
            target_metadata=_target_metadata(row.target),
            tags=row.tags,
        )
        for score, row in scored[:top_k]
    )


def _evaluate_prompt_jepa_retrieval_split(
    records: Sequence[PromptIntentRecord],
    *,
    index: PromptJepaIndex,
    split: str,
    top_k: int,
    fields: Sequence[str],
    miss_limit: int,
) -> PromptJepaRetrievalSplitResult:
    return _score_prompt_jepa_eval_records(
        records,
        split=split,
        top_k=top_k,
        fields=fields,
        miss_limit=miss_limit,
        get_results=lambda record: index.query(record.prompt, top_k=top_k),
    )


def _evaluate_prompt_jepa_predicted_target_split(
    records: Sequence[PromptIntentRecord],
    *,
    index: PromptJepaIndex,
    predictor: PromptJepaPredictor,
    split: str,
    top_k: int,
    fields: Sequence[str],
    miss_limit: int,
) -> PromptJepaRetrievalSplitResult:
    return _score_prompt_jepa_eval_records(
        records,
        split=split,
        top_k=top_k,
        fields=fields,
        miss_limit=miss_limit,
        get_results=lambda record: query_prompt_jepa_predicted_target(
            index,
            predictor,
            record.prompt,
            top_k=top_k,
            source_type=record.source_type,
            task_type=record.target.task_type,
            tags=record.tags,
        ),
    )


def _score_prompt_jepa_eval_records(
    records: Sequence[PromptIntentRecord],
    *,
    split: str,
    top_k: int,
    fields: Sequence[str],
    miss_limit: int,
    get_results: Callable[[PromptIntentRecord], tuple[PromptJepaQueryResult, ...]],
) -> PromptJepaRetrievalSplitResult:
    counters = {
        field: {"total": 0, "top_1_correct": 0, "top_k_correct": 0}
        for field in fields
    }
    misses: list[PromptJepaRetrievalMiss] = []

    for record in records:
        expected = _scalar_field_values(record.target.to_record(), fields=fields)
        if not expected:
            continue

        results = get_results(record)
        nearest = results[0] if results else None
        missed_top_1: list[str] = []
        missed_top_k: list[str] = []

        for field, expected_value in expected.items():
            counters[field]["total"] += 1
            top_1_value = (
                _scalar_eval_value(nearest.target_metadata.get(field))
                if nearest is not None
                else None
            )
            top_k_values = [
                value
                for result in results
                if (value := _scalar_eval_value(result.target_metadata.get(field)))
                is not None
            ]

            if top_1_value == expected_value:
                counters[field]["top_1_correct"] += 1
            else:
                missed_top_1.append(field)

            if expected_value in top_k_values:
                counters[field]["top_k_correct"] += 1
            else:
                missed_top_k.append(field)

        if missed_top_1 and len(misses) < miss_limit:
            misses.append(
                PromptJepaRetrievalMiss(
                    query_id=record.row_id,
                    split=record.split,
                    prompt=record.prompt,
                    missed_fields_top_1=tuple(missed_top_1),
                    missed_fields_top_k=tuple(missed_top_k),
                    expected=expected,
                    nearest_neighbor_id=nearest.row_id if nearest else None,
                    nearest_neighbor_score=nearest.score if nearest else None,
                    nearest_neighbor_target=(
                        _scalar_field_values(nearest.target_metadata, fields=fields)
                        if nearest is not None
                        else {}
                    ),
                    top_k_neighbor_ids=tuple(result.row_id for result in results),
                )
            )

    field_metrics = {
        field: PromptJepaFieldRetrievalMetrics(
            field=field,
            total=counter["total"],
            top_1_correct=counter["top_1_correct"],
            top_k_correct=counter["top_k_correct"],
        )
        for field, counter in counters.items()
    }
    return PromptJepaRetrievalSplitResult(
        split=split,
        total=len(records),
        top_k=top_k,
        field_metrics=field_metrics,
        misses=tuple(misses),
    )


def _scalar_field_values(
    target: Mapping[str, object],
    *,
    fields: Sequence[str],
) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in fields:
        if field not in target:
            continue
        value = _scalar_eval_value(target[field])
        if value is not None:
            values[field] = value
    return values


def _scalar_eval_value(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, bool | int | float):
        return _feature_scalar(value)
    return None


def _vector_from_record(value: object, *, dim: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Prompt-JEPA index field {field!r} must be a list")
    if len(value) != dim:
        raise ValueError(
            f"Prompt-JEPA index field {field!r} must have dimension {dim}"
        )
    vector: list[float] = []
    for index, item in enumerate(value):
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise ValueError(
                f"Prompt-JEPA index field {field!r} item {index} must be numeric"
            )
        vector.append(float(item))
    return tuple(vector)


def _validate_encoder_metadata(
    metadata: PromptJepaEncoderMetadata,
    *,
    expected_schema: str,
    label: str,
) -> None:
    if metadata.kind != FEATURE_HASHING_KIND:
        raise ValueError(f"{label} kind must be {FEATURE_HASHING_KIND!r}")
    if metadata.schema_version != expected_schema:
        raise ValueError(f"{label} schema_version must be {expected_schema!r}")


def _validate_embedding_dim(dim: int) -> None:
    if not isinstance(dim, int) or isinstance(dim, bool):
        raise ValueError("embedding_dim must be an integer")
    if dim < MIN_EMBEDDING_DIM:
        raise ValueError(f"embedding_dim must be >= {MIN_EMBEDDING_DIM}")


def _prompt_tokens(prompt: str) -> list[str]:
    return re.findall(r"\*\*|\^|[a-z0-9_]+", prompt.lower())


def _feature_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _required_str(record: Mapping[str, object], field: str, *, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} field {field!r} must be a non-empty string")
    return value


def _optional_str_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Prompt-JEPA index field {field!r} must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"Prompt-JEPA index field {field!r} must contain strings")
    return tuple(value)


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))
