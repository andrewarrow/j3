"""Prompt-intent dataset and evaluation helpers.

This module is intentionally data-first. It turns labeled prompt rows into
compact targets that a future learned prompt encoder can train on or predict.
It does not try to understand English with hand-written keyword rules.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Sequence


PROMPT_INTENT_SCHEMA_VERSION = "prompt-intent-label-v1"
EVAL_SCHEMA_VERSION = "prompt-intent-eval-v1"
LEARNED_BASELINE_SCHEMA_VERSION = "prompt-intent-token-perceptron-v1"
DEFAULT_PROMPT_INTENTS_PATH = Path("examples/prompt_intents/greenshot_7_intents.jsonl")
TARGET_FIELDS = [
    "repo_mode",
    "task_type",
    "domain",
    "expected_action",
    "requires_clarification",
    "primary_artifact",
    "unsupported_requirement",
    "requested_interfaces",
    "features",
    "artifacts",
    "unsupported_requirements",
    "clarification_fields",
]
SCALAR_TARGET_FIELDS = (
    "repo_mode",
    "task_type",
    "domain",
    "expected_action",
    "requires_clarification",
    "primary_artifact",
    "unsupported_requirement",
)
DEFAULT_LEARNED_BASELINE_EPOCHS = 10


@dataclass(frozen=True, slots=True)
class PromptIntentTarget:
    """The compact supervised target for prompt understanding."""

    repo_mode: str
    task_type: str
    domain: str
    expected_action: str
    requires_clarification: str = "no"
    primary_artifact: str = "none"
    unsupported_requirement: str = "none"
    requested_interfaces: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    unsupported_requirements: tuple[str, ...] = ()
    clarification_fields: tuple[str, ...] = ()
    target_files: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "repo_mode": self.repo_mode,
            "task_type": self.task_type,
            "domain": self.domain,
            "expected_action": self.expected_action,
            "requires_clarification": self.requires_clarification,
            "primary_artifact": self.primary_artifact,
            "unsupported_requirement": self.unsupported_requirement,
            "requested_interfaces": list(self.requested_interfaces),
            "features": list(self.features),
            "artifacts": list(self.artifacts),
            "unsupported_requirements": list(self.unsupported_requirements),
            "clarification_fields": list(self.clarification_fields),
            "target_files": list(self.target_files),
        }


@dataclass(frozen=True, slots=True)
class PromptIntentRecord:
    """One labeled prompt row suitable for prompt encoder training/evaluation."""

    row_id: str
    split: str
    source_type: str
    prompt: str
    target: PromptIntentTarget
    tags: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": PROMPT_INTENT_SCHEMA_VERSION,
            "id": self.row_id,
            "split": self.split,
            "source_type": self.source_type,
            "prompt": self.prompt,
            "target": self.target.to_record(),
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class PromptIntentPrediction:
    """One prompt-intent prediction at the boundary before request-spec building."""

    prompt: str
    target: PromptIntentTarget
    source: str
    confidence: float
    evidence: tuple[str, ...] = ()
    record_id: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "prompt": self.prompt,
            "target": self.target.to_record(),
            "source": self.source,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "record_id": self.record_id,
        }


@dataclass(frozen=True, slots=True)
class PromptIntentEvalResult:
    """Field-level evaluation for prompt-intent predictions."""

    total: int
    exact_matches: int
    field_correct: dict[str, int]
    mismatches: list[dict[str, object]] = field(default_factory=list)

    @property
    def exact_accuracy(self) -> float:
        return self.exact_matches / self.total if self.total else 0.0

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": EVAL_SCHEMA_VERSION,
            "total": self.total,
            "exact_matches": self.exact_matches,
            "exact_accuracy": self.exact_accuracy,
            "field_accuracy": {
                field: {
                    "correct": correct,
                    "total": self.total,
                    "accuracy": correct / self.total if self.total else 0.0,
                }
                for field, correct in self.field_correct.items()
            },
            "mismatches": list(self.mismatches),
        }


@dataclass(frozen=True, slots=True)
class PromptIntentLabelResidual:
    """One held-out scalar label miss from the learned prompt-intent baseline."""

    target_field: str
    row_id: str
    split: str
    source_type: str
    prompt: str
    expected: str
    predicted: str
    baseline_label: str
    baseline_correct: bool
    tags: tuple[str, ...] = ()
    target_context: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        return {
            "target_field": self.target_field,
            "id": self.row_id,
            "split": self.split,
            "source_type": self.source_type,
            "prompt": self.prompt,
            "expected": self.expected,
            "predicted": self.predicted,
            "baseline_label": self.baseline_label,
            "baseline_correct": self.baseline_correct,
            "tags": list(self.tags),
            "target_context": dict(self.target_context),
        }


@dataclass(frozen=True, slots=True)
class PromptIntentLabelMetrics:
    """Held-out scalar-label metrics for a prompt-intent classifier."""

    split: str
    total: int
    correct: int
    baseline_label: str
    baseline_correct: int
    confusion: dict[str, dict[str, int]]
    residuals: tuple[PromptIntentLabelResidual, ...] = ()

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def baseline_accuracy(self) -> float:
        return self.baseline_correct / self.total if self.total else 0.0

    def to_record(self) -> dict[str, object]:
        return {
            "split": self.split,
            "total": self.total,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "baseline": {
                "label": self.baseline_label,
                "correct": self.baseline_correct,
                "accuracy": self.baseline_accuracy,
            },
            "confusion": self.confusion,
            "residuals": [residual.to_record() for residual in self.residuals],
        }


@dataclass(frozen=True, slots=True)
class PromptIntentTokenPerceptronModel:
    """A small learned baseline over prompt tokens.

    This is a deterministic bag-of-token multiclass perceptron. It is useful as
    the first honest learned lower bound for prompt-intent fields, but it is not
    the final JEPA prompt encoder architecture.
    """

    target_field: str
    labels: tuple[str, ...]
    weights: dict[str, dict[str, float]]
    train_split: str
    epochs: int
    feature_schema: str = "prompt-token-unigram-bigram-v1"

    def predict_label(self, prompt: str) -> str:
        """Predict one scalar prompt-intent label from prompt text."""

        if not self.labels:
            raise ValueError("prompt intent model has no labels")
        features = _prompt_token_features(prompt)
        scores = {
            label: _score_label(features, self.weights.get(label, {}))
            for label in self.labels
        }
        return max(self.labels, key=lambda label: (scores[label], label))

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": LEARNED_BASELINE_SCHEMA_VERSION,
            "model_type": "token_perceptron_learned_baseline",
            "target_field": self.target_field,
            "labels": list(self.labels),
            "train_split": self.train_split,
            "epochs": self.epochs,
            "feature_schema": self.feature_schema,
            "weights": {
                label: dict(sorted(weights.items()))
                for label, weights in sorted(self.weights.items())
            },
        }


@dataclass(frozen=True, slots=True)
class PromptIntentTrainingResult:
    """Training/evaluation result for the learned prompt-intent baseline."""

    target_field: str
    train_split: str
    train_rows: int
    model: PromptIntentTokenPerceptronModel
    metrics: dict[str, PromptIntentLabelMetrics]
    majority_label: str
    decision: str

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": "prompt-intent-training-result-v1",
            "target_field": self.target_field,
            "train_split": self.train_split,
            "train_rows": self.train_rows,
            "majority_label": self.majority_label,
            "decision": self.decision,
            "model": self.model.to_record(),
            "metrics": {
                split: metrics.to_record()
                for split, metrics in sorted(self.metrics.items())
            },
        }


PromptIntentPredictor = Callable[[PromptIntentRecord], PromptIntentTarget | dict[str, object]]


def load_prompt_intent_records(path: Path) -> list[PromptIntentRecord]:
    """Load JSONL or JSON-array prompt labels into normalized intent targets."""

    rows = _load_json_rows(path)
    records = [_record_from_row(row, index=index) for index, row in enumerate(rows)]
    if not records:
        raise ValueError(f"no prompt intent rows found in {path}")
    return records


def profile_prompt_intents(records: Sequence[PromptIntentRecord]) -> dict[str, object]:
    """Summarize a prompt-intent dataset without predicting anything."""

    return {
        "schema_version": "prompt-intent-profile-v1",
        "total": len(records),
        "split_counts": _counter_record(record.split for record in records),
        "repo_mode_counts": _counter_record(record.target.repo_mode for record in records),
        "task_type_counts": _counter_record(record.target.task_type for record in records),
        "domain_counts": _counter_record(record.target.domain for record in records),
        "expected_action_counts": _counter_record(
            record.target.expected_action for record in records
        ),
        "requires_clarification_counts": _counter_record(
            record.target.requires_clarification for record in records
        ),
        "primary_artifact_counts": _counter_record(
            record.target.primary_artifact for record in records
        ),
        "unsupported_requirement_counts": _counter_record(
            record.target.unsupported_requirement for record in records
        ),
        "interface_counts": _counter_record(
            interface
            for record in records
            for interface in record.target.requested_interfaces
        ),
        "artifact_counts": _counter_record(
            artifact for record in records for artifact in record.target.artifacts
        ),
        "tag_counts": _counter_record(tag for record in records for tag in record.tags),
        "clarification_count": sum(
            1 for record in records if record.target.expected_action == "ask_clarification"
        ),
        "existing_repo_change_count": sum(
            1
            for record in records
            if record.target.expected_action == "emit_existing_repo_change_spec"
        ),
        "unsupported_requirement_count": sum(
            1 for record in records if record.target.unsupported_requirements
        ),
        "missing_artifact_label_count": sum(
            1 for record in records if record.target.primary_artifact == "none"
        ),
    }


def predict_prompt_intent(
    prompt: str,
    *,
    records: Sequence[PromptIntentRecord] | None = None,
    path: Path = DEFAULT_PROMPT_INTENTS_PATH,
) -> PromptIntentPrediction | None:
    """Return a fixture-backed intent prediction for exact labeled prompts.

    This is a lower-bound prediction boundary, not a broad English parser. It
    only emits targets already present in the prompt-intent fixture/eval data so
    request-spec construction can consume the same shape as a future learned
    predictor.
    """

    candidates = records if records is not None else _default_records(path)
    normalized = _normalize_prompt(prompt)

    for record in candidates:
        if _normalize_prompt(record.prompt) == normalized:
            return PromptIntentPrediction(
                prompt=prompt,
                target=record.target,
                source="prompt_intent_fixture_exact_match",
                confidence=1.0,
                evidence=(record.row_id,),
                record_id=record.row_id,
            )

    return None


def evaluate_prompt_intent_predictions(
    records: Sequence[PromptIntentRecord],
    predictor: PromptIntentPredictor,
) -> PromptIntentEvalResult:
    """Score prompt-intent predictions against labeled targets."""

    field_correct = {field: 0 for field in TARGET_FIELDS}
    exact_matches = 0
    mismatches: list[dict[str, object]] = []

    for record in records:
        expected = record.target
        predicted = _target_from_prediction(predictor(record), expected=expected)
        row_mismatches = []

        for field in TARGET_FIELDS:
            expected_value = getattr(expected, field)
            predicted_value = getattr(predicted, field)
            if expected_value == predicted_value:
                field_correct[field] += 1
            else:
                row_mismatches.append(
                    {
                        "field": field,
                        "expected": _json_value(expected_value),
                        "predicted": _json_value(predicted_value),
                    }
                )

        if row_mismatches:
            mismatches.append(
                {
                    "id": record.row_id,
                    "split": record.split,
                    "prompt": record.prompt,
                    "mismatches": row_mismatches,
                }
            )
        else:
            exact_matches += 1

    return PromptIntentEvalResult(
        total=len(records),
        exact_matches=exact_matches,
        field_correct=field_correct,
        mismatches=mismatches,
    )


def train_prompt_intent_token_baseline(
    records: Sequence[PromptIntentRecord],
    *,
    target_field: str,
    train_split: str = "train",
    eval_splits: Sequence[str] = ("train", "validation", "test"),
    epochs: int = DEFAULT_LEARNED_BASELINE_EPOCHS,
) -> PromptIntentTrainingResult:
    """Train a reproducible token perceptron for one scalar intent field.

    The model trains only on ``train_split`` rows. Validation and test rows are
    used exclusively for metrics. The returned decision is deliberately
    conservative: this helper does not opt the model into production request
    parsing.
    """

    if target_field not in SCALAR_TARGET_FIELDS:
        raise ValueError(
            f"target_field must be one of {', '.join(SCALAR_TARGET_FIELDS)}"
        )
    if epochs < 1:
        raise ValueError("epochs must be at least 1")

    train_records = [record for record in records if record.split == train_split]
    if not train_records:
        raise ValueError(f"no prompt intent rows found for train split {train_split!r}")

    label_counts = Counter(
        _scalar_target_value(record, target_field) for record in train_records
    )
    labels = tuple(sorted(label_counts))
    if len(labels) < 2:
        raise ValueError(f"target_field {target_field!r} needs at least two train labels")

    majority_label = _majority_label(label_counts)
    weights = {label: Counter() for label in labels}

    for _epoch in range(epochs):
        for record in train_records:
            expected = _scalar_target_value(record, target_field)
            features = _prompt_token_features(record.prompt)
            predicted = _predict_from_weights(labels, weights, features)
            if predicted == expected:
                continue
            for feature, value in features.items():
                weights[expected][feature] += value
                weights[predicted][feature] -= value

    model = PromptIntentTokenPerceptronModel(
        target_field=target_field,
        labels=labels,
        weights={
            label: {
                feature: float(weight)
                for feature, weight in sorted(feature_weights.items())
                if weight
            }
            for label, feature_weights in weights.items()
        },
        train_split=train_split,
        epochs=epochs,
    )
    metrics = {
        split: evaluate_prompt_intent_label_model(
            [record for record in records if record.split == split],
            model=model,
            baseline_label=majority_label,
        )
        for split in eval_splits
    }
    return PromptIntentTrainingResult(
        target_field=target_field,
        train_split=train_split,
        train_rows=len(train_records),
        model=model,
        metrics=metrics,
        majority_label=majority_label,
        decision=(
            "evaluation_only_not_wired_to_production"
            if any(split != train_split for split in eval_splits)
            else "training_only_not_wired_to_production"
        ),
    )


def evaluate_prompt_intent_label_model(
    records: Sequence[PromptIntentRecord],
    *,
    model: PromptIntentTokenPerceptronModel,
    baseline_label: str,
) -> PromptIntentLabelMetrics:
    """Evaluate a scalar prompt-intent label model against labeled rows."""

    correct = 0
    baseline_correct = 0
    confusion: dict[str, dict[str, int]] = {}
    residuals: list[PromptIntentLabelResidual] = []

    for record in records:
        expected = _scalar_target_value(record, model.target_field)
        predicted = model.predict_label(record.prompt)
        confusion.setdefault(expected, {})
        confusion[expected][predicted] = confusion[expected].get(predicted, 0) + 1
        if predicted == expected:
            correct += 1
        else:
            residuals.append(
                PromptIntentLabelResidual(
                    target_field=model.target_field,
                    row_id=record.row_id,
                    split=record.split,
                    source_type=record.source_type,
                    prompt=record.prompt,
                    expected=expected,
                    predicted=predicted,
                    baseline_label=baseline_label,
                    baseline_correct=baseline_label == expected,
                    tags=record.tags,
                    target_context=_target_context(record.target),
                )
            )
        if baseline_label == expected:
            baseline_correct += 1

    return PromptIntentLabelMetrics(
        split=records[0].split if records else "empty",
        total=len(records),
        correct=correct,
        baseline_label=baseline_label,
        baseline_correct=baseline_correct,
        confusion={
            expected: dict(sorted(predictions.items()))
            for expected, predictions in sorted(confusion.items())
        },
        residuals=tuple(residuals),
    )


@lru_cache(maxsize=8)
def _default_records(path: Path) -> tuple[PromptIntentRecord, ...]:
    return tuple(load_prompt_intent_records(path))


def _load_json_rows(path: Path) -> list[dict[str, object]]:
    resolved = path.expanduser().resolve()
    text = resolved.read_text(encoding="utf-8")
    if resolved.suffix == ".json":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"{resolved} must contain a JSON array")
        rows = data
    else:
        rows = [
            json.loads(line)
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{resolved} row {index} must be an object")
    return rows


def _record_from_row(row: dict[str, object], *, index: int) -> PromptIntentRecord:
    row_id = _required_str(row, "id", index=index)
    split = _required_str(row, "split", index=index)
    source_type = _required_str(row, "source_type", index=index)
    task_type = _required_str(row, "task_type", index=index)
    repo_mode = _required_str(row, "repo_mode", index=index)
    domain = _required_str(row, "domain", index=index)
    prompt = _required_str(row, "prompt", index=index)
    expected = _optional_dict(row.get("expected"), field="expected", index=index)
    expected_action = _expected_action(row, expected)
    requested_interfaces = _tuple_strs(
        expected.get("requested_interfaces", expected.get("interfaces", [])),
        field="expected.interfaces",
        index=index,
    )
    features = _tuple_strs(
        expected.get("features", []),
        field="expected.features",
        index=index,
    )
    artifacts = _tuple_strs(
        expected.get("artifacts", []),
        field="expected.artifacts",
        index=index,
    )
    unsupported_requirements = _tuple_strs(
        expected.get("unsupported_requirements", []),
        field="expected.unsupported_requirements",
        index=index,
    )
    clarification_fields = _tuple_strs(
        expected.get("clarification_fields", []),
        field="expected.clarification_fields",
        index=index,
    )

    target = PromptIntentTarget(
        repo_mode=repo_mode,
        task_type=task_type,
        domain=domain,
        expected_action=expected_action,
        requires_clarification=_requires_clarification(
            expected=expected,
            expected_action=expected_action,
            clarification_fields=clarification_fields,
        ),
        primary_artifact=_primary_artifact(artifacts),
        unsupported_requirement=_primary_unsupported_requirement(
            unsupported_requirements
        ),
        requested_interfaces=requested_interfaces,
        features=features,
        artifacts=artifacts,
        unsupported_requirements=unsupported_requirements,
        clarification_fields=clarification_fields,
        target_files=_tuple_strs(
            expected.get("target_files", []),
            field="expected.target_files",
            index=index,
        ),
    )
    return PromptIntentRecord(
        row_id=row_id,
        split=split,
        source_type=source_type,
        prompt=prompt,
        target=target,
        tags=_tuple_strs(row.get("tags", []), field="tags", index=index),
    )


def _expected_action(row: dict[str, object], expected: dict[str, object]) -> str:
    explicit = expected.get("action", row.get("expected_action"))
    if isinstance(explicit, str) and explicit:
        return explicit
    if expected.get("clarify") is True or row.get("task_type") == "clarify":
        return "ask_clarification"
    if row.get("repo_mode") == "existing_repo":
        return "emit_existing_repo_change_spec"
    if row.get("repo_mode") == "new_repo":
        return "emit_request_spec"
    return "ask_clarification"


def _requires_clarification(
    *,
    expected: dict[str, object],
    expected_action: str,
    clarification_fields: tuple[str, ...],
) -> str:
    if (
        expected_action == "ask_clarification"
        or expected.get("clarify") is True
        or clarification_fields
    ):
        return "yes"
    return "no"


def _primary_artifact(artifacts: tuple[str, ...]) -> str:
    return artifacts[0] if artifacts else "none"


def _primary_unsupported_requirement(unsupported_requirements: tuple[str, ...]) -> str:
    if not unsupported_requirements:
        return "none"
    for requirement in unsupported_requirements:
        if requirement != "complex_scope":
            return requirement
    return unsupported_requirements[0]


def _target_from_prediction(
    prediction: PromptIntentTarget | dict[str, object],
    *,
    expected: PromptIntentTarget,
) -> PromptIntentTarget:
    if isinstance(prediction, PromptIntentTarget):
        return prediction
    if not isinstance(prediction, dict):
        raise TypeError("prompt intent predictor must return a target or dict")

    return PromptIntentTarget(
        repo_mode=str(prediction.get("repo_mode", expected.repo_mode)),
        task_type=str(prediction.get("task_type", expected.task_type)),
        domain=str(prediction.get("domain", expected.domain)),
        expected_action=str(prediction.get("expected_action", expected.expected_action)),
        requires_clarification=str(
            prediction.get("requires_clarification", expected.requires_clarification)
        ),
        primary_artifact=str(
            prediction.get("primary_artifact", expected.primary_artifact)
        ),
        unsupported_requirement=str(
            prediction.get("unsupported_requirement", expected.unsupported_requirement)
        ),
        requested_interfaces=_tuple_prediction(
            prediction.get("requested_interfaces", expected.requested_interfaces)
        ),
        features=_tuple_prediction(prediction.get("features", expected.features)),
        artifacts=_tuple_prediction(prediction.get("artifacts", expected.artifacts)),
        unsupported_requirements=_tuple_prediction(
            prediction.get("unsupported_requirements", expected.unsupported_requirements)
        ),
        clarification_fields=_tuple_prediction(
            prediction.get("clarification_fields", expected.clarification_fields)
        ),
        target_files=_tuple_prediction(prediction.get("target_files", expected.target_files)),
    )


def _required_str(row: dict[str, object], field: str, *, index: int) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"row {index} field {field!r} must be a non-empty string")
    return value


def _optional_dict(value: object, *, field: str, index: int) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"row {index} field {field!r} must be an object")
    return value


def _tuple_strs(value: object, *, field: str, index: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"row {index} field {field!r} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"row {index} field {field!r} must contain strings")
    return tuple(value)


def _tuple_prediction(value: object) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return ()


def _scalar_target_value(record: PromptIntentRecord, target_field: str) -> str:
    value = getattr(record.target, target_field)
    if not isinstance(value, str):
        raise ValueError(f"target field {target_field!r} is not scalar")
    return value


def _target_context(target: PromptIntentTarget) -> dict[str, object]:
    return {
        "repo_mode": target.repo_mode,
        "task_type": target.task_type,
        "domain": target.domain,
        "expected_action": target.expected_action,
        "requires_clarification": target.requires_clarification,
        "primary_artifact": target.primary_artifact,
        "unsupported_requirement": target.unsupported_requirement,
        "artifacts": list(target.artifacts),
        "unsupported_requirements": list(target.unsupported_requirements),
        "clarification_fields": list(target.clarification_fields),
    }


def _majority_label(label_counts: Counter[str]) -> str:
    if not label_counts:
        raise ValueError("cannot choose majority label from empty counts")
    return sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _prompt_token_features(prompt: str) -> Counter[str]:
    tokens = _prompt_tokens(prompt)
    features: Counter[str] = Counter({"bias": 1})
    features.update(f"tok={token}" for token in tokens)
    features.update(
        f"bigram={tokens[index]} {tokens[index + 1]}"
        for index in range(len(tokens) - 1)
    )
    return features


def _prompt_tokens(prompt: str) -> list[str]:
    return re.findall(r"\*\*|\^|[a-z0-9_]+", prompt.lower())


def _predict_from_weights(
    labels: Sequence[str],
    weights: dict[str, Counter[str]],
    features: Counter[str],
) -> str:
    scores = {
        label: _score_label(features, weights.get(label, {}))
        for label in labels
    }
    return max(labels, key=lambda label: (scores[label], label))


def _score_label(
    features: Counter[str],
    weights: dict[str, float] | Counter[str],
) -> float:
    return sum(
        float(weights.get(feature, 0.0)) * value
        for feature, value in features.items()
    )


def _counter_record(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.lower().strip().split())


def _json_value(value: object) -> object:
    if isinstance(value, tuple):
        return list(value)
    return value
