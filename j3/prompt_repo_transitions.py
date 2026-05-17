"""Prompt-to-repo transition rows for Prompt+Repo JEPA experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from j3.prompt_jepa import (
    EXISTING_REPO_CHANGE_ATTEMPT_KIND,
    REQUEST_REPO_ATTEMPT_KIND,
    default_prompt_jepa_metadata,
    encode_prompt_context,
    encode_prompt_target,
)


PROMPT_REPO_TRANSITION_SCHEMA_VERSION = "prompt-repo-transition-v1"
PROMPT_REPO_TRANSITION_TARGET_SCHEMA_VERSION = "prompt-repo-transition-target-v1"
PROMPT_REPO_TRANSITION_PREDICTOR_SCHEMA_VERSION = "prompt-repo-transition-predictor-v0"
PROMPT_REPO_TRANSITION_FEATURE_SCHEMA_VERSION = "prompt-repo-transition-feature-v1"
PROMPT_REPO_TRANSITION_PREDICTION_SCHEMA_VERSION = (
    "prompt-repo-transition-prediction-v0"
)
NEAREST_ACTION_DELTA_PREDICTOR_KIND = "nearest_context_action_delta"
EVALUATION_ONLY_DECISION = "evaluation-only"
TRANSITION_ARTIFACT = "transitions.jsonl"
HOSTED_LLM_API_TOKENS = 0
HOSTED_REPO_CONTEXT_BYTES = 0
ACTION_FEATURE_WEIGHT = 0.12
PROMPT_CONTEXT_FEATURE_WEIGHT = 0.44
REPO_BEFORE_FEATURE_WEIGHT = 0.44


@dataclass(frozen=True, slots=True)
class PromptRepoOutcomeState:
    """Repo states observed before and, when source changed, after an outcome."""

    repo_before: Mapping[str, object]
    repo_after: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PromptRepoTransitionPredictorV0:
    """Evaluation-only V0 predictor over prompt-repo transition rows."""

    schema_version: str
    predictor_kind: str
    decision: str
    embedding_dim: int
    train_row_ids: tuple[str, ...]
    global_source_delta: tuple[float, ...]
    action_source_deltas: Mapping[str, tuple[float, ...]]
    train_examples: tuple[dict[str, object], ...]

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "predictor_kind": self.predictor_kind,
            "decision": self.decision,
            "feature_schema_version": PROMPT_REPO_TRANSITION_FEATURE_SCHEMA_VERSION,
            "prediction_schema_version": PROMPT_REPO_TRANSITION_PREDICTION_SCHEMA_VERSION,
            "embedding_dim": self.embedding_dim,
            "train_rows": len(self.train_row_ids),
            "train_row_ids": list(self.train_row_ids),
            "global_source_delta": list(self.global_source_delta),
            "action_source_deltas": {
                key: list(self.action_source_deltas[key])
                for key in sorted(self.action_source_deltas)
            },
            "train_examples": [_json_copy(example) for example in self.train_examples],
        }

    def predict(self, row: Mapping[str, object]) -> dict[str, object]:
        """Predict the transition target for one row without applying changes."""

        validate_prompt_repo_transition_predictor(self)
        _validate_transition_row(row)
        row_dim = _transition_embedding_dim(row)
        if row_dim != self.embedding_dim:
            raise ValueError(
                "transition row embedding dimension does not match predictor "
                f"dimension {self.embedding_dim}"
            )

        query_vector = _transition_input_vector(row, dim=self.embedding_dim)
        nearest = max(
            self.train_examples,
            key=lambda example: (
                _dot(query_vector, _float_tuple(example["input_vector"])),
                str(example["row_id"]),
            ),
        )
        action_kind = _transition_action_kind(row)
        target_kind = str(nearest["target_kind"])

        if target_kind == "repo_after_embedding":
            delta = self.action_source_deltas.get(action_kind, self.global_source_delta)
            if not delta:
                delta = _float_tuple(nearest.get("source_delta", []))
            repo_before = _repo_embedding_from_transition(row, field="repo_before")
            predicted_embedding = _vector_add(repo_before, delta)
            return {
                "schema_version": PROMPT_REPO_TRANSITION_PREDICTION_SCHEMA_VERSION,
                "decision": EVALUATION_ONLY_DECISION,
                "predictor_kind": self.predictor_kind,
                "nearest_train_row_id": str(nearest["row_id"]),
                "input_features": _input_feature_summary(row),
                "target": {
                    "kind": "repo_after_embedding",
                    "outcome_kind": str(nearest["outcome_kind"]),
                    "outcome_status": nearest.get("outcome_status"),
                    "validation_status": nearest.get("validation_status"),
                    "embedding_dim": self.embedding_dim,
                    "repo_after_embedding": list(predicted_embedding),
                    "source_delta_kind": (
                        "action_conditioned_average"
                        if action_kind in self.action_source_deltas
                        else "global_average"
                    ),
                },
            }

        return {
            "schema_version": PROMPT_REPO_TRANSITION_PREDICTION_SCHEMA_VERSION,
            "decision": EVALUATION_ONLY_DECISION,
            "predictor_kind": self.predictor_kind,
            "nearest_train_row_id": str(nearest["row_id"]),
            "input_features": _input_feature_summary(row),
            "target": {
                "kind": "blocked_or_clarification",
                "outcome_kind": str(nearest["outcome_kind"]),
                "outcome_status": nearest.get("outcome_status"),
                "validation_status": nearest.get("validation_status"),
                "failure_kind": nearest.get("failure_kind"),
                "clarification_fields": list(
                    _string_list(nearest.get("clarification_fields", []))
                ),
                "repo_after_embedding": None,
            },
        }


def build_prompt_repo_transition_rows(
    outcome_rows: Sequence[Mapping[str, object]],
    outcome_states: Sequence[PromptRepoOutcomeState],
    *,
    embedding_dim: int = 256,
) -> tuple[dict[str, object], ...]:
    """Build stable transition rows from demo prompt/spec/action/outcome rows."""

    if len(outcome_rows) != len(outcome_states):
        raise ValueError("outcome_rows and outcome_states must have the same length")

    return tuple(
        build_prompt_repo_transition_row(
            row,
            outcome_states[index - 1],
            index=index,
            embedding_dim=embedding_dim,
        )
        for index, row in enumerate(outcome_rows, start=1)
    )


def build_prompt_repo_transition_row(
    outcome_row: Mapping[str, object],
    state: PromptRepoOutcomeState,
    *,
    index: int,
    embedding_dim: int = 256,
) -> dict[str, object]:
    """Build one JSON-serializable Prompt+Repo JEPA transition row."""

    metadata = default_prompt_jepa_metadata(embedding_dim=embedding_dim)
    record_kind = _required_str(outcome_row, "record_kind", index=index)
    prompt = _outcome_prompt(outcome_row, index=index)
    task_type = _task_type(outcome_row, record_kind=record_kind, index=index)
    action = _structured_action(outcome_row, record_kind=record_kind, index=index)
    validation = _validation(outcome_row, index=index)
    outcome = _outcome_summary(
        outcome_row,
        record_kind=record_kind,
        action_kind=str(action["kind"]),
        validation=validation,
        index=index,
    )
    target_summary = _target_summary(
        outcome_row,
        record_kind=record_kind,
        action=action,
        outcome=outcome,
        validation=validation,
        index=index,
    )
    tags = _transition_tags(target_summary)
    context_embedding = encode_prompt_context(
        prompt,
        dim=embedding_dim,
        source_type=record_kind,
        task_type=task_type,
        tags=tags,
    )
    target_embedding = encode_prompt_target(
        target_summary,
        dim=embedding_dim,
        tags=tags,
    )
    repo_before = _repo_state_record(state.repo_before, field="repo_before")
    after_kind = str(outcome["kind"])
    if after_kind in {"source_changed", "source_unchanged"}:
        if state.repo_after is None:
            raise ValueError(
                f"transition {index} requires repo_after for outcome kind {after_kind}"
            )
        repo_after_state = _repo_state_record(state.repo_after, field="repo_after")
    else:
        repo_after_state = repo_before

    return {
        "schema_version": PROMPT_REPO_TRANSITION_SCHEMA_VERSION,
        "id": f"prompt-repo-transition-{index:04d}",
        "source_outcome": {
            "record_kind": record_kind,
            "outcome_row_index": index,
            "outcome_row_id": _optional_str(outcome_row.get("id"))
            or _optional_str(outcome_row.get("row_id")),
        },
        "prompt_context": {
            "prompt": prompt,
            "context_encoder": metadata.context_encoder.to_record(),
            "embedding_dim": embedding_dim,
            "embedding_checksum": _checksum_json(context_embedding),
            "embedding": list(context_embedding),
        },
        "prompt_jepa_target": {
            "target_encoder": metadata.target_encoder.to_record(),
            "embedding_dim": embedding_dim,
            "embedding_checksum": _checksum_json(target_embedding),
            "summary": target_summary,
        },
        "repo_before": {
            "state_checksum": _checksum_json(repo_before),
            "state": repo_before,
        },
        "structured_action": action,
        "outcome": outcome,
        "repo_after": {
            "kind": after_kind,
            "state_checksum": _checksum_json(repo_after_state),
            "state": repo_after_state,
        },
        "validation": validation,
        "cost": _cost_record(
            repo_before=repo_before,
            repo_after=repo_after_state,
            validation=validation,
        ),
    }


def write_prompt_repo_transitions_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write transition rows as deterministic JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def load_prompt_repo_transition_rows(path: Path) -> tuple[dict[str, object], ...]:
    """Load transition JSONL rows."""

    rows: list[dict[str, object]] = []
    with path.expanduser().resolve().open(encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"transition row {line_index} must be an object")
            rows.append(row)
    return tuple(rows)


def fit_prompt_repo_transition_predictor_v0(
    rows: Sequence[Mapping[str, object]],
) -> PromptRepoTransitionPredictorV0:
    """Fit a tiny deterministic evaluation-only transition predictor."""

    if not rows:
        raise ValueError("at least one transition row is required")

    validated_rows = tuple(rows)
    for row in validated_rows:
        _validate_transition_row(row)

    embedding_dim = _transition_embedding_dim(validated_rows[0])
    for row in validated_rows:
        row_dim = _transition_embedding_dim(row)
        if row_dim != embedding_dim:
            raise ValueError(
                "all transition rows must share embedding dimension "
                f"{embedding_dim}; found {row_dim}"
            )

    train_examples: list[dict[str, object]] = []
    source_deltas_by_action: dict[str, list[tuple[float, ...]]] = {}
    all_source_deltas: list[tuple[float, ...]] = []

    for row in validated_rows:
        target = _transition_training_target(row, dim=embedding_dim)
        action_kind = _transition_action_kind(row)
        source_delta = target.get("source_delta")
        if isinstance(source_delta, tuple):
            source_deltas_by_action.setdefault(action_kind, []).append(source_delta)
            all_source_deltas.append(source_delta)
        train_examples.append(
            {
                "row_id": _transition_row_id(row),
                "input_vector": list(_transition_input_vector(row, dim=embedding_dim)),
                "action_kind": action_kind,
                "outcome_kind": _transition_outcome_kind(row),
                "outcome_status": _optional_str(
                    _mapping_field(row, "outcome", index=0).get("status")
                ),
                "validation_status": _optional_str(
                    _mapping_field(row, "validation", index=0).get("status")
                ),
                "target_kind": target["kind"],
                "failure_kind": target.get("failure_kind"),
                "clarification_fields": list(
                    _string_list(target.get("clarification_fields", []))
                ),
                "repo_after_embedding": list(
                    _float_tuple(target.get("repo_after_embedding", []))
                )
                if target.get("kind") == "repo_after_embedding"
                else None,
                "source_delta": list(source_delta)
                if isinstance(source_delta, tuple)
                else [],
            }
        )

    zero_delta = tuple(0.0 for _ in range(embedding_dim))
    predictor = PromptRepoTransitionPredictorV0(
        schema_version=PROMPT_REPO_TRANSITION_PREDICTOR_SCHEMA_VERSION,
        predictor_kind=NEAREST_ACTION_DELTA_PREDICTOR_KIND,
        decision=EVALUATION_ONLY_DECISION,
        embedding_dim=embedding_dim,
        train_row_ids=tuple(str(example["row_id"]) for example in train_examples),
        global_source_delta=(
            _mean_vectors(all_source_deltas, dim=embedding_dim)
            if all_source_deltas
            else zero_delta
        ),
        action_source_deltas={
            action_kind: _mean_vectors(action_deltas, dim=embedding_dim)
            for action_kind, action_deltas in sorted(source_deltas_by_action.items())
        },
        train_examples=tuple(train_examples),
    )
    validate_prompt_repo_transition_predictor(predictor)
    return predictor


def predict_prompt_repo_transition_target_v0(
    predictor: PromptRepoTransitionPredictorV0,
    row: Mapping[str, object],
) -> dict[str, object]:
    """Predict one transition target with a fitted V0 predictor."""

    return predictor.predict(row)


def write_prompt_repo_transition_predictor_json(
    predictor: PromptRepoTransitionPredictorV0,
    path: Path,
) -> Path:
    """Persist a transition predictor artifact as deterministic JSON."""

    validate_prompt_repo_transition_predictor(predictor)
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(predictor.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved


def load_prompt_repo_transition_predictor_json(
    path: Path,
) -> PromptRepoTransitionPredictorV0:
    """Load a persisted transition predictor artifact."""

    data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("transition predictor artifact must be a JSON object")
    predictor = _predictor_from_record(data)
    validate_prompt_repo_transition_predictor(predictor)
    return predictor


def validate_prompt_repo_transition_predictor(
    predictor: PromptRepoTransitionPredictorV0,
) -> None:
    """Validate a transition predictor artifact and vector dimensions."""

    if predictor.schema_version != PROMPT_REPO_TRANSITION_PREDICTOR_SCHEMA_VERSION:
        raise ValueError(
            "unsupported prompt-repo transition predictor schema "
            f"{predictor.schema_version!r}"
        )
    if predictor.predictor_kind != NEAREST_ACTION_DELTA_PREDICTOR_KIND:
        raise ValueError(
            f"unsupported prompt-repo transition predictor kind {predictor.predictor_kind!r}"
        )
    if predictor.decision != EVALUATION_ONLY_DECISION:
        raise ValueError("prompt-repo transition predictor must be evaluation-only")
    if predictor.embedding_dim < 1:
        raise ValueError("predictor embedding_dim must be positive")
    if not predictor.train_row_ids:
        raise ValueError("predictor must include train row ids")
    if len(set(predictor.train_row_ids)) != len(predictor.train_row_ids):
        raise ValueError("predictor train row ids must be unique")
    if len(predictor.global_source_delta) != predictor.embedding_dim:
        raise ValueError("global source delta dimension mismatch")
    for action_kind, delta in predictor.action_source_deltas.items():
        if not action_kind:
            raise ValueError("action source delta key must be non-empty")
        if len(delta) != predictor.embedding_dim:
            raise ValueError(f"source delta dimension mismatch for {action_kind!r}")
    if len(predictor.train_examples) != len(predictor.train_row_ids):
        raise ValueError("predictor train examples must match train row ids")
    for index, example in enumerate(predictor.train_examples, start=1):
        row_id = example.get("row_id")
        if not isinstance(row_id, str) or not row_id:
            raise ValueError(f"predictor train example {index} row_id must be a string")
        vector = _float_tuple(example.get("input_vector", []))
        if len(vector) != predictor.embedding_dim:
            raise ValueError(
                f"predictor train example {row_id!r} input dimension mismatch"
            )
        target_kind = example.get("target_kind")
        if target_kind not in {"repo_after_embedding", "blocked_or_clarification"}:
            raise ValueError(
                f"predictor train example {row_id!r} has invalid target kind"
            )
        if target_kind == "repo_after_embedding":
            target_embedding = _float_tuple(example.get("repo_after_embedding", []))
            if len(target_embedding) != predictor.embedding_dim:
                raise ValueError(
                    f"predictor train example {row_id!r} target dimension mismatch"
                )


def _predictor_from_record(record: Mapping[str, object]) -> PromptRepoTransitionPredictorV0:
    embedding_dim = record.get("embedding_dim")
    if not isinstance(embedding_dim, int) or isinstance(embedding_dim, bool):
        raise ValueError("transition predictor embedding_dim must be an integer")
    action_source_deltas_raw = record.get("action_source_deltas", {})
    if not isinstance(action_source_deltas_raw, Mapping):
        raise ValueError("transition predictor action_source_deltas must be an object")
    train_examples_raw = record.get("train_examples", [])
    if not isinstance(train_examples_raw, list):
        raise ValueError("transition predictor train_examples must be a list")
    train_examples: list[dict[str, object]] = []
    for index, example in enumerate(train_examples_raw, start=1):
        if not isinstance(example, Mapping):
            raise ValueError(
                f"transition predictor train example {index} must be an object"
            )
        copied = _json_copy(example)
        if not isinstance(copied, dict):
            raise ValueError(
                f"transition predictor train example {index} must be an object"
            )
        train_examples.append(copied)
    return PromptRepoTransitionPredictorV0(
        schema_version=_required_str(record, "schema_version", index=0),
        predictor_kind=_required_str(record, "predictor_kind", index=0),
        decision=_required_str(record, "decision", index=0),
        embedding_dim=embedding_dim,
        train_row_ids=tuple(_string_list(record.get("train_row_ids", []))),
        global_source_delta=_float_tuple(record.get("global_source_delta", [])),
        action_source_deltas={
            str(action_kind): _float_tuple(delta)
            for action_kind, delta in action_source_deltas_raw.items()
        },
        train_examples=tuple(train_examples),
    )


def _validate_transition_row(row: Mapping[str, object]) -> None:
    if row.get("schema_version") != PROMPT_REPO_TRANSITION_SCHEMA_VERSION:
        raise ValueError("transition row must use prompt-repo-transition-v1")
    _transition_row_id(row)
    dim = _transition_embedding_dim(row)
    prompt_context = _mapping_field(row, "prompt_context", index=0)
    if len(_float_tuple(prompt_context.get("embedding", []))) != dim:
        raise ValueError("prompt context embedding dimension mismatch")
    _repo_embedding_from_transition(row, field="repo_before")
    outcome_kind = _transition_outcome_kind(row)
    repo_after = _mapping_field(row, "repo_after", index=0)
    if outcome_kind in {"source_changed", "source_unchanged"}:
        _repo_embedding_from_transition(row, field="repo_after")
    elif outcome_kind != "blocked_no_change":
        raise ValueError(f"unsupported transition outcome kind {outcome_kind!r}")
    if repo_after.get("kind") != outcome_kind:
        raise ValueError("repo_after kind must match outcome kind")


def _transition_embedding_dim(row: Mapping[str, object]) -> int:
    prompt_context = _mapping_field(row, "prompt_context", index=0)
    dim = prompt_context.get("embedding_dim")
    if not isinstance(dim, int) or isinstance(dim, bool) or dim < 1:
        raise ValueError("transition prompt_context.embedding_dim must be positive")
    return dim


def _transition_row_id(row: Mapping[str, object]) -> str:
    row_id = row.get("id")
    if not isinstance(row_id, str) or not row_id:
        raise ValueError("transition row id must be a non-empty string")
    return row_id


def _transition_action_kind(row: Mapping[str, object]) -> str:
    action = _mapping_field(row, "structured_action", index=0)
    kind = action.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError("transition structured_action.kind must be a string")
    return kind


def _transition_outcome_kind(row: Mapping[str, object]) -> str:
    outcome = _mapping_field(row, "outcome", index=0)
    kind = outcome.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError("transition outcome.kind must be a string")
    return kind


def _transition_input_vector(
    row: Mapping[str, object],
    *,
    dim: int,
) -> tuple[float, ...]:
    prompt_context = _mapping_field(row, "prompt_context", index=0)
    prompt_embedding = _float_tuple(prompt_context.get("embedding", []))
    repo_before_embedding = _repo_embedding_from_transition(row, field="repo_before")
    categorical_embedding = _hash_feature_vector(
        _transition_categorical_features(row),
        dim=dim,
    )
    if len(prompt_embedding) != dim:
        raise ValueError("prompt context embedding dimension mismatch")
    if len(repo_before_embedding) != dim:
        raise ValueError("repo-before embedding dimension mismatch")
    return _normalize(
        tuple(
            (PROMPT_CONTEXT_FEATURE_WEIGHT * prompt_embedding[index])
            + (REPO_BEFORE_FEATURE_WEIGHT * repo_before_embedding[index])
            + (ACTION_FEATURE_WEIGHT * categorical_embedding[index])
            for index in range(dim)
        )
    )


def _transition_categorical_features(row: Mapping[str, object]) -> tuple[str, ...]:
    action = _mapping_field(row, "structured_action", index=0)
    outcome = _mapping_field(row, "outcome", index=0)
    validation = _mapping_field(row, "validation", index=0)
    source = _mapping_field(row, "source_outcome", index=0)
    features: list[str] = []
    for prefix, mapping, fields in (
        ("source", source, ("record_kind",)),
        ("action", action, ("kind", "repo_mode", "task_type", "domain")),
        ("outcome", outcome, ("kind", "status", "failure_kind")),
        ("validation", validation, ("status",)),
    ):
        for field in fields:
            value = mapping.get(field)
            if isinstance(value, str) and value:
                features.append(f"{prefix}:{field}:{value}")
    for field in ("features", "target_files", "action_kinds"):
        for value in _string_list(action.get(field, [])):
            features.append(f"action:{field}:{value}")
    return tuple(features)


def _transition_training_target(
    row: Mapping[str, object],
    *,
    dim: int,
) -> dict[str, object]:
    outcome_kind = _transition_outcome_kind(row)
    if outcome_kind in {"source_changed", "source_unchanged"}:
        before = _repo_embedding_from_transition(row, field="repo_before")
        after = _repo_embedding_from_transition(row, field="repo_after")
        if len(before) != dim or len(after) != dim:
            raise ValueError("repo target embedding dimension mismatch")
        return {
            "kind": "repo_after_embedding",
            "repo_after_embedding": after,
            "source_delta": tuple(
                after_value - before_value
                for before_value, after_value in zip(before, after, strict=True)
            ),
        }

    target_summary = _mapping_field(
        _mapping_field(row, "prompt_jepa_target", index=0),
        "summary",
        index=0,
    )
    outcome = _mapping_field(row, "outcome", index=0)
    return {
        "kind": "blocked_or_clarification",
        "failure_kind": outcome.get("failure_kind"),
        "clarification_fields": _string_list(
            target_summary.get("clarification_fields", [])
        ),
    }


def _repo_embedding_from_transition(
    row: Mapping[str, object],
    *,
    field: str,
) -> tuple[float, ...]:
    wrapper = _mapping_field(row, field, index=0)
    state = _repo_state_record(_mapping_field(wrapper, "state", index=0), field=field)
    dim = _transition_embedding_dim(row)
    embedding = _float_tuple(state.get("repo_embedding", []))
    if len(embedding) != dim:
        raise ValueError(f"{field} repo_embedding dimension mismatch")
    return embedding


def _input_feature_summary(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "feature_schema_version": PROMPT_REPO_TRANSITION_FEATURE_SCHEMA_VERSION,
        "prompt_context_embedding": True,
        "repo_before_embedding": True,
        "categorical_features": list(_transition_categorical_features(row)),
    }


def _hash_feature_vector(features: Sequence[str], *, dim: int) -> tuple[float, ...]:
    vector = [0.0 for _ in range(dim)]
    for feature in features:
        digest = sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dim
        sign = 1.0 if digest[8] % 2 == 0 else -1.0
        vector[index] += sign
    return _normalize(tuple(vector))


def _mean_vectors(vectors: Sequence[Sequence[float]], *, dim: int) -> tuple[float, ...]:
    if not vectors:
        return tuple(0.0 for _ in range(dim))
    return tuple(
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(dim)
    )


def _vector_add(
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[float, ...]:
    if len(left) != len(right):
        raise ValueError("cannot add vectors with different dimensions")
    return tuple(
        left_value + right_value
        for left_value, right_value in zip(left, right, strict=True)
    )


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("cannot compare vectors with different dimensions")
    return sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )


def _normalize(vector: Sequence[float]) -> tuple[float, ...]:
    magnitude = sum(value * value for value in vector) ** 0.5
    if magnitude == 0.0:
        return tuple(float(value) for value in vector)
    return tuple(float(value) / magnitude for value in vector)


def _float_tuple(value: object) -> tuple[float, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError("expected a numeric vector")
    floats: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise ValueError("expected a numeric vector")
        floats.append(float(item))
    return tuple(floats)


def _structured_action(
    row: Mapping[str, object],
    *,
    record_kind: str,
    index: int,
) -> dict[str, object]:
    if record_kind == REQUEST_REPO_ATTEMPT_KIND:
        spec = _mapping_field(row, "normalized_request_spec", index=index)
        actions = _list_field(row, "greenfield_actions", index=index)
        action_kinds = _action_kinds(actions)
        kind = "ask_clarification" if "ask_clarification" in action_kinds else "create_repo"
        return {
            "kind": kind,
            "record_kind": record_kind,
            "repo_mode": _optional_str(spec.get("repo_mode")),
            "task_type": _optional_str(spec.get("task_type")),
            "domain": _optional_str(spec.get("domain")),
            "features": _string_list(spec.get("features", [])),
            "target_files": _string_list(spec.get("artifacts", [])),
            "action_kinds": action_kinds,
            "action_count": len(action_kinds),
        }
    if record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        spec = _mapping_field(row, "existing_repo_change_spec", index=index)
        actions = _list_field(row, "existing_repo_actions", index=index)
        action_kinds = _action_kinds(actions)
        return {
            "kind": "modify_repo",
            "record_kind": record_kind,
            "repo_mode": _optional_str(spec.get("repo_mode")),
            "task_type": _optional_str(spec.get("task_type")),
            "domain": _optional_str(spec.get("domain")),
            "features": _string_list(spec.get("features_to_add", [])),
            "target_files": _string_list(spec.get("target_files", [])),
            "action_kinds": action_kinds,
            "action_count": len(action_kinds),
        }
    raise ValueError(f"transition row {index} has unsupported record_kind {record_kind!r}")


def _outcome_summary(
    row: Mapping[str, object],
    *,
    record_kind: str,
    action_kind: str,
    validation: Mapping[str, object],
    index: int,
) -> dict[str, object]:
    passed = bool(row.get("passed", False))
    failure = row.get("failure_observation")
    failure_kind = _failure_kind(failure)
    if failure_kind == "blocking_clarification" or action_kind == "ask_clarification":
        kind = "blocked_no_change"
    elif record_kind == REQUEST_REPO_ATTEMPT_KIND:
        build_result = _mapping_field(row, "build_result", index=index)
        kind = "source_changed" if build_result.get("status") == "built" else "source_unchanged"
    elif record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        change_result = _mapping_field(row, "change_result", index=index)
        changed = bool(_string_list(change_result.get("files_changed", [])))
        kind = "source_changed" if changed else "source_unchanged"
    else:
        raise ValueError(f"transition row {index} has unsupported record_kind {record_kind!r}")
    return {
        "kind": kind,
        "status": _outcome_status(row, record_kind=record_kind, index=index),
        "passed": passed,
        "failure_kind": failure_kind,
    }


def _target_summary(
    row: Mapping[str, object],
    *,
    record_kind: str,
    action: Mapping[str, object],
    outcome: Mapping[str, object],
    validation: Mapping[str, object],
    index: int,
) -> dict[str, object]:
    return _drop_none_values(
        {
            "schema_version": PROMPT_REPO_TRANSITION_TARGET_SCHEMA_VERSION,
            "record_kind": record_kind,
            "action_kind": action.get("kind"),
            "outcome_kind": outcome.get("kind"),
            "outcome_status": outcome.get("status"),
            "validation_status": validation.get("status"),
            "passed": outcome.get("passed"),
            "repo_mode": action.get("repo_mode"),
            "task_type": action.get("task_type"),
            "domain": action.get("domain"),
            "features": list(action.get("features", []))
            if isinstance(action.get("features"), list)
            else [],
            "target_files": list(action.get("target_files", []))
            if isinstance(action.get("target_files"), list)
            else [],
            "action_kinds": list(action.get("action_kinds", []))
            if isinstance(action.get("action_kinds"), list)
            else [],
            "failure_kind": outcome.get("failure_kind"),
            "clarification_fields": _clarification_fields(row, record_kind, index=index),
        }
    )


def _validation(row: Mapping[str, object], *, index: int) -> dict[str, object]:
    validation = _mapping_field(row, "validation", index=index)
    return {
        "status": _optional_str(validation.get("status")),
        "command": _optional_str(validation.get("command")),
        "exit_code": validation.get("exit_code"),
    }


def _cost_record(
    *,
    repo_before: Mapping[str, object],
    repo_after: Mapping[str, object],
    validation: Mapping[str, object],
) -> dict[str, object]:
    before_aggregate = _mapping_field(repo_before, "aggregate", index=0)
    after_aggregate = _mapping_field(repo_after, "aggregate", index=0)
    command = validation.get("command")
    return {
        "hosted_llm_api_tokens": HOSTED_LLM_API_TOKENS,
        "hosted_repo_context_bytes": HOSTED_REPO_CONTEXT_BYTES,
        "validation_command_count": 1 if isinstance(command, str) and command else 0,
        "repo_before_python_file_count": int(
            before_aggregate.get("python_file_count", 0)
        ),
        "repo_after_python_file_count": int(after_aggregate.get("python_file_count", 0)),
        "repo_before_python_byte_count": int(
            before_aggregate.get("total_python_byte_count", 0)
        ),
        "repo_after_python_byte_count": int(
            after_aggregate.get("total_python_byte_count", 0)
        ),
    }


def _repo_state_record(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    record = _json_copy(value)
    if not isinstance(record, dict):
        raise ValueError(f"{field} must be an object")
    if record.get("schema_version") != "repo-state-v1":
        raise ValueError(f"{field} must use repo-state-v1")
    return record


def _outcome_status(
    row: Mapping[str, object],
    *,
    record_kind: str,
    index: int,
) -> str | None:
    if record_kind == REQUEST_REPO_ATTEMPT_KIND:
        return _optional_str(_mapping_field(row, "build_result", index=index).get("status"))
    if record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        return _optional_str(_mapping_field(row, "change_result", index=index).get("status"))
    return None


def _task_type(
    row: Mapping[str, object],
    *,
    record_kind: str,
    index: int,
) -> str | None:
    if record_kind == REQUEST_REPO_ATTEMPT_KIND:
        return _optional_str(
            _mapping_field(row, "normalized_request_spec", index=index).get("task_type")
        )
    if record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        return _optional_str(
            _mapping_field(row, "existing_repo_change_spec", index=index).get("task_type")
        )
    return None


def _clarification_fields(
    row: Mapping[str, object],
    record_kind: str,
    *,
    index: int,
) -> list[str]:
    if record_kind != REQUEST_REPO_ATTEMPT_KIND:
        return []
    spec = _mapping_field(row, "normalized_request_spec", index=index)
    clarifications = spec.get("clarifications_needed", [])
    fields: list[str] = []
    if not isinstance(clarifications, list | tuple):
        return fields
    for item in clarifications:
        if not isinstance(item, Mapping):
            continue
        field = item.get("field")
        if isinstance(field, str) and field:
            fields.append(field)
    return fields


def _transition_tags(target_summary: Mapping[str, object]) -> tuple[str, ...]:
    tags: list[str] = ["transition"]
    for field in (
        "record_kind",
        "action_kind",
        "outcome_kind",
        "validation_status",
        "repo_mode",
        "task_type",
        "domain",
        "failure_kind",
    ):
        value = target_summary.get(field)
        if isinstance(value, str) and value:
            tags.append(value)
    tags.extend(_string_list(target_summary.get("features", [])))
    return tuple(dict.fromkeys(tags))


def _action_kinds(actions: Sequence[object]) -> list[str]:
    kinds: list[str] = []
    for action in actions:
        if not isinstance(action, Mapping):
            continue
        kind = action.get("kind")
        if isinstance(kind, str) and kind:
            kinds.append(kind)
    return kinds


def _failure_kind(value: object) -> str:
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if isinstance(kind, str) and kind:
            return kind
    return "none"


def _outcome_prompt(row: Mapping[str, object], *, index: int) -> str:
    prompt = row.get("raw_prompt", row.get("prompt"))
    if not isinstance(prompt, str) or not prompt:
        raise ValueError(f"transition row {index} has no prompt")
    return prompt


def _required_str(row: Mapping[str, object], field: str, *, index: int) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"transition row {index} field {field!r} must be a string")
    return value


def _mapping_field(
    row: Mapping[str, object],
    field: str,
    *,
    index: int,
) -> Mapping[str, object]:
    value = row.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"transition row {index} field {field!r} must be an object")
    return value


def _list_field(
    row: Mapping[str, object],
    field: str,
    *,
    index: int,
) -> list[object]:
    value = row.get(field)
    if not isinstance(value, list):
        raise ValueError(f"transition row {index} field {field!r} must be a list")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, str)]


def _drop_none_values(record: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if value is not None}


def _checksum_json(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value, sort_keys=True))
