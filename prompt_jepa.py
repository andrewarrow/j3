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
from typing import Any, Mapping, Sequence

from prompt_intents import (
    PromptIntentRecord,
    load_prompt_intent_records,
)


PROMPT_JEPA_INDEX_FORMAT = "j3.prompt-jepa-index.v1"
PROMPT_CONTEXT_ENCODER_SCHEMA_VERSION = "prompt-context-v1"
PROMPT_TARGET_ENCODER_SCHEMA_VERSION = "prompt-target-v1"
FEATURE_HASHING_KIND = "feature_hashing"
DEFAULT_EMBEDDING_DIM = 256
MIN_EMBEDDING_DIM = 8


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
