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
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Sequence


PROMPT_INTENT_SCHEMA_VERSION = "prompt-intent-label-v1"
EVAL_SCHEMA_VERSION = "prompt-intent-eval-v1"
LEARNED_BASELINE_SCHEMA_VERSION = "prompt-intent-token-perceptron-v1"
LEARNED_BASELINE_REPORT_SCHEMA_VERSION = "prompt-intent-learned-baseline-report-v1"
PROMPT_FEATURE_SCHEMA_VERSION = "prompt-token-bigram-char-skipgram-v2"
PROMPT_CORPUS_PROFILE_SCHEMA_VERSION = "prompt-corpus-profile-v1"
PROMPT_CORPUS_VALIDATION_SCHEMA_VERSION = "prompt-corpus-validation-v1"
DEFAULT_PROMPT_INTENTS_PATH = Path("examples/prompt_intents/greenshot_7_intents.jsonl")
PROMPT_CORPUS_REQUIRED_FIELDS = (
    "id",
    "split",
    "source_type",
    "task_type",
    "repo_mode",
    "domain",
    "prompt",
    "expected",
    "tags",
)
PROMPT_CORPUS_REQUIRED_FIELD_TYPES = {
    "id": str,
    "split": str,
    "source_type": str,
    "task_type": str,
    "repo_mode": str,
    "domain": str,
    "prompt": str,
    "expected": dict,
    "tags": list,
}
PROMPT_CORPUS_EXPECTED_FIELD_TYPES = {
    "action": str,
    "features": list,
    "artifacts": list,
    "interfaces": list,
    "requested_interfaces": list,
    "inferred": list,
    "clarify": bool,
    "clarification_fields": list,
    "unsupported_requirements": list,
    "constraints": list,
    "target_files": list,
}
PROMPT_CORPUS_EXPECTED_LIST_FIELDS = {
    field
    for field, expected_type in PROMPT_CORPUS_EXPECTED_FIELD_TYPES.items()
    if expected_type is list
}
PROMPT_CORPUS_SCALAR_LABELS = {
    "split": ("test", "train", "validation"),
    "source_type": (
        "greenshot_7_intent_fixture",
        "human_seed",
        "manual_reviewed_synthetic",
        "synthetic_template_v0",
    ),
    "task_type": (
        "add_feature",
        "add_tests",
        "bugfix",
        "clarify",
        "config_change",
        "create_app",
        "create_library",
        "docs_change",
        "refactor",
    ),
    "repo_mode": ("existing_repo", "new_repo", "unknown"),
    "expected_action": (
        "ask_clarification",
        "emit_existing_repo_change_spec",
        "emit_request_spec",
    ),
    "requires_clarification": ("no", "yes"),
}
PROMPT_CORPUS_NEAR_DUPLICATE_RATIO = 0.88
PROMPT_CORPUS_NEAR_DUPLICATE_TOKEN_OVERLAP = 0.45
PROMPT_CORPUS_NEAR_DUPLICATE_LIMIT = 50
PROMPT_CORPUS_SYNTHETIC_TEMPLATE_VERSIONS = ("prompt-corpus-template-v0",)
PROMPT_CORPUS_SYNTHETIC_REVIEW_STATUSES = (
    "manual_reviewed",
    "unreviewed_synthetic",
)
TARGET_FIELDS = [
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
    "inferred_defaults",
]
SCALAR_TARGET_FIELDS = (
    "repo_mode",
    "task_type",
    "domain",
    "expected_action",
    "requires_clarification",
    "primary_artifact",
    "unsupported_requirement",
    "unsupported_requirement_family",
)
DEFAULT_LEARNED_BASELINE_EPOCHS = 10
UNSUPPORTED_REQUIREMENT_FAMILIES = {
    "complex_scope": "scope",
    "desktop_interface": "interface",
    "domain_unspecified": "domain",
    "graphing_feature_unspecified": "feature_scope",
    "graphical_interface": "interface",
    "scientific_operations_unspecified": "feature_scope",
    "ui_interface": "interface",
    "visual_interface_scope": "interface",
    "web_interface": "interface",
}


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
    unsupported_requirement_family: str = "none"
    requested_interfaces: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    unsupported_requirements: tuple[str, ...] = ()
    clarification_fields: tuple[str, ...] = ()
    inferred_defaults: tuple[str, ...] = ()
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
            "unsupported_requirement_family": self.unsupported_requirement_family,
            "requested_interfaces": list(self.requested_interfaces),
            "features": list(self.features),
            "artifacts": list(self.artifacts),
            "unsupported_requirements": list(self.unsupported_requirements),
            "clarification_fields": list(self.clarification_fields),
            "inferred_defaults": list(self.inferred_defaults),
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
    feature_schema: str = PROMPT_FEATURE_SCHEMA_VERSION

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
        "unsupported_requirement_family_counts": _counter_record(
            record.target.unsupported_requirement_family for record in records
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


def inspect_prompt_corpus(path: Path) -> dict[str, object]:
    """Profile and quality-check raw prompt-intent corpus rows.

    Unlike ``load_prompt_intent_records``, this helper does not assume the corpus
    is already valid. It keeps going after missing fields and unknown labels so
    the CLI can report corpus quality in one stable JSON record.
    """

    return profile_prompt_corpus_rows(
        _load_json_rows(path),
        labels_path=path.expanduser().resolve(),
    )


def validate_prompt_corpus(
    path: Path,
    *,
    fail_on_review: bool = False,
) -> dict[str, object]:
    """Validate raw prompt-intent corpus rows against the DATA-002 policy."""

    return validate_prompt_corpus_rows(
        _load_json_rows(path),
        labels_path=path.expanduser().resolve(),
        fail_on_review=fail_on_review,
    )


def validate_prompt_corpus_rows(
    rows: Sequence[dict[str, object]],
    *,
    labels_path: Path | None = None,
    fail_on_review: bool = False,
) -> dict[str, object]:
    """Return a structured validation report for prompt/spec corpus rows.

    The validator intentionally builds on ``profile_prompt_corpus_rows`` so the
    audit counts and schema gate stay aligned. Fatal errors cover malformed
    rows, unsupported labels, expected-field typing, duplicate ids, and missing
    synthetic provenance. Cross-split near-duplicates are review warnings by
    default because current corpora intentionally keep those examples visible
    until a split cleanup task is assigned.
    """

    profile = profile_prompt_corpus_rows(rows, labels_path=labels_path)
    issues: list[dict[str, object]] = []
    issues.extend(_profile_validation_issues(profile, fail_on_review=fail_on_review))
    issues.extend(_row_validation_issues(rows))

    severity_counts = Counter(str(issue["severity"]) for issue in issues)
    error_count = severity_counts.get("error", 0)
    warning_count = severity_counts.get("warning", 0)
    status = (
        "invalid"
        if error_count
        else "valid_with_warnings"
        if warning_count
        else "valid"
    )
    report: dict[str, object] = {
        "schema_version": PROMPT_CORPUS_VALIDATION_SCHEMA_VERSION,
        "status": status,
        "valid": error_count == 0,
        "total_rows": len(rows),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": sorted(
            issues,
            key=_validation_issue_sort_key,
        ),
        "policy": _prompt_corpus_validation_policy(),
        "profile": profile,
    }
    if labels_path is not None:
        report["labels"] = str(labels_path)
    return report


def profile_prompt_corpus_rows(
    rows: Sequence[dict[str, object]],
    *,
    labels_path: Path | None = None,
) -> dict[str, object]:
    """Return corpus profile counts plus duplicate/leakage/label checks."""

    split_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    task_type_counts: Counter[str] = Counter()
    repo_mode_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    expected_action_counts: Counter[str] = Counter()
    clarification_counts: Counter[str] = Counter()
    ambiguity_counts: Counter[str] = Counter()
    inferred_default_counts: Counter[str] = Counter()
    inferred_default_presence_counts: Counter[str] = Counter()
    prompt_family_counts: Counter[str] = Counter()
    synthetic_template_family_counts: Counter[str] = Counter()
    template_version_counts: Counter[str] = Counter()
    generation_review_status_counts: Counter[str] = Counter()
    top_level_field_counts: Counter[str] = Counter()
    expected_field_counts: Counter[str] = Counter()
    top_level_schema_variants: Counter[tuple[str, ...]] = Counter()
    expected_schema_variants: Counter[tuple[str, ...]] = Counter()
    prompt_groups: dict[str, list[dict[str, object]]] = {}
    family_groups: dict[str, list[dict[str, object]]] = {}
    prompt_rows: list[dict[str, object]] = []
    missing_required_fields: list[dict[str, object]] = []
    unsupported_scalar_labels: list[dict[str, object]] = []
    expected_field_type_issues: list[dict[str, object]] = []
    synthetic_generation_missing = 0

    for index, row in enumerate(rows):
        row_ref = _row_reference(row, index)
        missing_required_fields.extend(_required_field_issues(row, index=index))

        split = _optional_scalar(row.get("split"))
        source_type = _optional_scalar(row.get("source_type"))
        task_type = _optional_scalar(row.get("task_type"))
        repo_mode = _optional_scalar(row.get("repo_mode"))
        domain = _optional_scalar(row.get("domain"))
        expected = row.get("expected") if isinstance(row.get("expected"), dict) else {}
        assert isinstance(expected, dict)
        expected_action = _expected_action(row, expected)
        requires_clarification = _safe_requires_clarification(
            expected=expected,
            expected_action=expected_action,
        )
        tags = _string_list_value(row.get("tags"))

        split_counts.update([split])
        source_type_counts.update([source_type])
        task_type_counts.update([task_type])
        repo_mode_counts.update([repo_mode])
        domain_counts.update([domain])
        expected_action_counts.update([expected_action])
        clarification_counts.update([requires_clarification])
        ambiguity_counts.update(
            [
                "ambiguous"
                if _row_is_ambiguous(
                    task_type=task_type,
                    tags=tags,
                    expected_action=expected_action,
                    requires_clarification=requires_clarification,
                )
                else "not_ambiguous"
            ]
        )
        top_level_schema_variants.update([tuple(sorted(row))])
        top_level_field_counts.update(str(field) for field in row)
        expected_schema_variants.update([tuple(sorted(expected))])
        expected_field_counts.update(str(field) for field in expected)
        expected_field_type_issues.extend(
            _expected_field_type_issues(row, expected, index=index)
        )

        if "inferred" in expected:
            inferred_default_presence_counts.update(["present"])
            inferred = expected.get("inferred")
            if isinstance(inferred, list):
                inferred_default_counts.update(
                    item for item in inferred if isinstance(item, str) and item
                )
        else:
            inferred_default_presence_counts.update(["missing"])

        template_version = _template_version(row)
        if template_version:
            template_version_counts.update([template_version])
        review_status = _generation_review_status(row)
        if review_status:
            generation_review_status_counts.update([review_status])

        prompt = row.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            normalized_prompt = _normalize_prompt(prompt)
            prompt_groups.setdefault(_normalize_prompt(prompt), []).append(
                {
                    **row_ref,
                    "split": split,
                    "prompt": prompt,
                }
            )
            prompt_rows.append(
                {
                    **row_ref,
                    "split": split,
                    "source_type": source_type,
                    "prompt": prompt,
                    "normalized_prompt": normalized_prompt,
                    "tokens": _prompt_token_set(prompt),
                }
            )

        family = _prompt_family(row)
        if family:
            prompt_family_counts.update([family])
            family_groups.setdefault(family, []).append(
                {
                    **row_ref,
                    "split": split,
                    "prompt": prompt if isinstance(prompt, str) else "",
                }
            )
        else:
            prompt_family_counts.update(["__missing__"])

        if _is_synthetic_template_row(row, source_type=source_type):
            if family:
                synthetic_template_family_counts.update([family])
            else:
                synthetic_template_family_counts.update(["__missing__"])
            if not isinstance(row.get("generation"), dict):
                synthetic_generation_missing += 1

        scalar_values = {
            "split": split,
            "source_type": source_type,
            "task_type": task_type,
            "repo_mode": repo_mode,
            "expected_action": expected_action,
            "requires_clarification": requires_clarification,
        }
        for field, value in scalar_values.items():
            allowed = PROMPT_CORPUS_SCALAR_LABELS[field]
            if value not in allowed:
                unsupported_scalar_labels.append(
                    {
                        **row_ref,
                        "field": field,
                        "value": value,
                        "allowed": list(allowed),
                    }
                )

    duplicate_normalized_prompts = [
        {
            "normalized_prompt": normalized_prompt,
            "count": len(matches),
            "rows": matches,
        }
        for normalized_prompt, matches in sorted(prompt_groups.items())
        if len(matches) > 1
    ]
    duplicate_cross_split_prompts = [
        duplicate
        for duplicate in duplicate_normalized_prompts
        if len({match["split"] for match in duplicate["rows"]}) > 1
    ]
    family_split_leakage = [
        {
            "family": family,
            "splits": sorted({str(match["split"]) for match in matches}),
            "rows": matches,
        }
        for family, matches in sorted(family_groups.items())
        if len({match["split"] for match in matches}) > 1
    ]
    near_duplicate_cross_split_prompts = _near_duplicate_cross_split_prompts(
        prompt_rows
    )
    row_schema_variants = _schema_variant_records(top_level_schema_variants)
    expected_schema_variant_records = _schema_variant_records(expected_schema_variants)
    schema_consistency_issues = _schema_consistency_issues(
        total_rows=len(rows),
        row_schema_variants=row_schema_variants,
        expected_schema_variants=expected_schema_variant_records,
        top_level_field_counts=top_level_field_counts,
        expected_field_counts=expected_field_counts,
        expected_field_type_issues=expected_field_type_issues,
        unsupported_scalar_labels=unsupported_scalar_labels,
        duplicate_cross_split_prompts=duplicate_cross_split_prompts,
        near_duplicate_cross_split_prompts=near_duplicate_cross_split_prompts,
        family_split_leakage=family_split_leakage,
        synthetic_generation_missing=synthetic_generation_missing,
    )

    profile: dict[str, object] = {
        "schema_version": PROMPT_CORPUS_PROFILE_SCHEMA_VERSION,
        "total_rows": len(rows),
        "split_counts": _counter_record(split_counts.elements()),
        "source_type_counts": _counter_record(source_type_counts.elements()),
        "task_type_counts": _counter_record(task_type_counts.elements()),
        "repo_mode_counts": _counter_record(repo_mode_counts.elements()),
        "domain_counts": _counter_record(domain_counts.elements()),
        "expected_action_counts": _counter_record(expected_action_counts.elements()),
        "clarification_counts": _counter_record(clarification_counts.elements()),
        "ambiguity_counts": _counter_record(ambiguity_counts.elements()),
        "inferred_default_counts": _counter_record(inferred_default_counts.elements()),
        "inferred_default_presence_counts": _counter_record(
            inferred_default_presence_counts.elements()
        ),
        "prompt_family_counts": _counter_record(prompt_family_counts.elements()),
        "synthetic_template_family_counts": _counter_record(
            synthetic_template_family_counts.elements()
        ),
        "template_version_counts": _counter_record(template_version_counts.elements()),
        "generation_review_status_counts": _counter_record(
            generation_review_status_counts.elements()
        ),
        "top_level_field_counts": _counter_record(top_level_field_counts.elements()),
        "expected_field_counts": _counter_record(expected_field_counts.elements()),
        "row_schema_variants": row_schema_variants,
        "row_schema_variant_count": len(row_schema_variants),
        "expected_schema_variants": expected_schema_variant_records,
        "expected_schema_variant_count": len(expected_schema_variant_records),
        "duplicate_normalized_prompts": duplicate_normalized_prompts,
        "duplicate_normalized_prompt_count": len(duplicate_normalized_prompts),
        "duplicate_cross_split_prompts": duplicate_cross_split_prompts,
        "duplicate_cross_split_prompt_count": len(duplicate_cross_split_prompts),
        "near_duplicate_cross_split_prompts": near_duplicate_cross_split_prompts,
        "near_duplicate_cross_split_prompt_count": len(
            near_duplicate_cross_split_prompts
        ),
        "near_duplicate_family_leakage": family_split_leakage,
        "near_duplicate_family_leakage_count": len(family_split_leakage),
        "missing_required_fields": missing_required_fields,
        "missing_required_field_count": len(missing_required_fields),
        "unsupported_scalar_labels": unsupported_scalar_labels,
        "unsupported_scalar_label_count": len(unsupported_scalar_labels),
        "expected_field_type_issues": expected_field_type_issues,
        "expected_field_type_issue_count": len(expected_field_type_issues),
        "synthetic_generation_missing_count": synthetic_generation_missing,
        "schema_consistency_issues": schema_consistency_issues,
        "schema_consistency_issue_count": len(schema_consistency_issues),
        "data_002_validate_fields": _data_002_validate_fields(
            schema_consistency_issues
        ),
    }
    if labels_path is not None:
        profile["labels"] = str(labels_path)
    return profile


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


def evaluate_prompt_intent_learned_baseline(
    records: Sequence[PromptIntentRecord],
    *,
    target_fields: Sequence[str] = SCALAR_TARGET_FIELDS,
    train_split: str = "train",
    eval_splits: Sequence[str] = ("validation", "test"),
    epochs: int = DEFAULT_LEARNED_BASELINE_EPOCHS,
    residual_limit: int = 25,
) -> dict[str, object]:
    """Return a compact learned-baseline report for the current prompt corpus."""

    if not records:
        raise ValueError("at least one prompt intent record is required")
    if epochs < 1:
        raise ValueError("epochs must be at least 1")

    fields = _baseline_report_fields(target_fields)
    field_models = {
        field: _field_baseline_for_report(
            records,
            target_field=field,
            train_split=train_split,
            eval_splits=eval_splits,
            epochs=epochs,
        )
        for field in fields
    }
    inferred_model = _train_inferred_default_baseline(
        records,
        train_split=train_split,
        epochs=epochs,
    )

    split_reports: dict[str, dict[str, object]] = {}
    residual_groups: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for split in eval_splits:
        split_records = [record for record in records if record.split == split]
        split_reports[split] = _evaluate_baseline_report_split(
            split_records,
            split=split,
            fields=fields,
            field_models=field_models,
            inferred_model=inferred_model,
            residual_groups=residual_groups,
            residual_limit=residual_limit,
        )

    return {
        "schema_version": LEARNED_BASELINE_REPORT_SCHEMA_VERSION,
        "total_rows": len(records),
        "train_split": train_split,
        "train_rows": sum(1 for record in records if record.split == train_split),
        "eval_splits": list(eval_splits),
        "target_fields": list(fields),
        "field_models": {
            field: _field_model_report(field_models[field])
            for field in fields
        },
        "inferred_default_model": {
            "status": inferred_model["status"],
            "labels": list(inferred_model["labels"]),
        },
        "splits": split_reports,
        "grouped_residuals": sorted(
            residual_groups.values(),
            key=lambda group: (
                str(group["split"]),
                str(group["target_field"]),
                -int(group["count"]),
                str(group["expected"]),
                str(group["predicted"]),
            ),
        ),
        "decision": "evaluation_only_not_wired_to_production",
    }


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
    inferred_defaults = _tuple_strs(
        expected.get("inferred", []),
        field="expected.inferred",
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
        unsupported_requirement_family=_unsupported_requirement_family(
            unsupported_requirements
        ),
        requested_interfaces=requested_interfaces,
        features=features,
        artifacts=artifacts,
        unsupported_requirements=unsupported_requirements,
        clarification_fields=clarification_fields,
        inferred_defaults=inferred_defaults,
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


def _unsupported_requirement_family(unsupported_requirements: tuple[str, ...]) -> str:
    requirement = _primary_unsupported_requirement(unsupported_requirements)
    return UNSUPPORTED_REQUIREMENT_FAMILIES.get(requirement, requirement)


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
        unsupported_requirement_family=str(
            prediction.get(
                "unsupported_requirement_family",
                expected.unsupported_requirement_family,
            )
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
        inferred_defaults=_tuple_prediction(
            prediction.get("inferred_defaults", expected.inferred_defaults)
        ),
        target_files=_tuple_prediction(prediction.get("target_files", expected.target_files)),
    )


def _profile_validation_issues(
    profile: dict[str, object],
    *,
    fail_on_review: bool,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for item in _dict_list(profile.get("missing_required_fields")):
        issues.append(
            _validation_issue(
                "error",
                "missing_required_field"
                if item.get("issue") == "missing"
                else "invalid_required_field",
                field=str(item.get("field", "__row__")),
                message=(
                    f"row is missing required field {item.get('field')!r}"
                    if item.get("issue") == "missing"
                    else f"required field {item.get('field')!r} has invalid value"
                ),
                item=item,
            )
        )
    for item in _dict_list(profile.get("unsupported_scalar_labels")):
        issues.append(
            _validation_issue(
                "error",
                "unsupported_scalar_label",
                field=str(item.get("field", "__row__")),
                message=(
                    f"unsupported {item.get('field')} label {item.get('value')!r}; "
                    f"allowed={item.get('allowed')}"
                ),
                item=item,
                value=item.get("value"),
                allowed=item.get("allowed"),
            )
        )
    for item in _dict_list(profile.get("expected_field_type_issues")):
        issue_name = str(item.get("issue", "expected_field_type_issue"))
        issues.append(
            _validation_issue(
                "error",
                issue_name,
                field=str(item.get("field", "expected")),
                message=_expected_field_type_message(item),
                item=item,
            )
        )
    for item in _dict_list(profile.get("duplicate_cross_split_prompts")):
        issues.append(
            _validation_issue(
                "error",
                "duplicate_prompt_cross_split_leakage",
                field="prompt",
                message="normalized prompt appears in more than one split",
                item=item,
            )
        )
    for item in _dict_list(profile.get("near_duplicate_cross_split_prompts")):
        severity = "error" if fail_on_review else "warning"
        issues.append(
            _validation_issue(
                severity,
                "near_duplicate_prompt_cross_split_review",
                field="prompt",
                message="near-duplicate prompt pair crosses splits and needs review",
                item=item,
            )
        )
    for item in _dict_list(profile.get("near_duplicate_family_leakage")):
        severity = "error" if fail_on_review else "warning"
        issues.append(
            _validation_issue(
                severity,
                "prompt_family_cross_split_review",
                field="prompt_family",
                message="prompt family spans multiple splits and needs review",
                item=item,
            )
        )
    return issues


def _row_validation_issues(
    rows: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    seen_ids: dict[str, dict[str, object]] = {}
    for index, row in enumerate(rows):
        row_ref = _row_reference(row, index)
        row_id = row.get("id")
        if isinstance(row_id, str) and row_id:
            previous = seen_ids.get(row_id)
            if previous is not None:
                issues.append(
                    _validation_issue(
                        "error",
                        "duplicate_id",
                        field="id",
                        message=f"row id {row_id!r} appears more than once",
                        item=row_ref,
                        first_line=previous["line"],
                    )
                )
            else:
                seen_ids[row_id] = row_ref

        tags = row.get("tags")
        if isinstance(tags, list) and not all(
            isinstance(tag, str) and tag for tag in tags
        ):
            issues.append(
                _validation_issue(
                    "error",
                    "invalid_list_items",
                    field="tags",
                    message="tags must contain non-empty strings",
                    item=row_ref,
                )
            )

        expected = row.get("expected")
        if not isinstance(expected, dict):
            continue
        source_type = _optional_scalar(row.get("source_type"))
        expected_action = _expected_action(row, expected)
        issues.extend(
            _expected_schema_policy_issues(
                row=row,
                expected=expected,
                index=index,
                source_type=source_type,
                expected_action=expected_action,
            )
        )
        issues.extend(
            _synthetic_provenance_issues(
                row,
                index=index,
                source_type=source_type,
            )
        )
    return issues


def _expected_schema_policy_issues(
    *,
    row: dict[str, object],
    expected: dict[str, object],
    index: int,
    source_type: str,
    expected_action: str,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    row_ref = _row_reference(row, index)
    explicit_action = expected.get("action", row.get("expected_action"))
    if not isinstance(explicit_action, str) or not explicit_action:
        if source_type == "human_seed":
            issues.append(
                _validation_issue(
                    "warning",
                    "legacy_expected_action_missing",
                    field="expected.action",
                    message=(
                        "human_seed row omits expected.action; validator is "
                        f"using derived action {expected_action!r}"
                    ),
                    item=row_ref,
                    derived_action=expected_action,
                )
            )
        else:
            issues.append(
                _validation_issue(
                    "error",
                    "expected_action_missing",
                    field="expected.action",
                    message="expected.action is required for non-legacy rows",
                    item=row_ref,
                )
            )

    for field_name in _required_expected_fields(
        source_type=source_type,
        expected_action=expected_action,
    ):
        if field_name not in expected:
            issues.append(
                _validation_issue(
                    "error",
                    "expected_required_field_missing",
                    field=f"expected.{field_name}",
                    message=f"expected.{field_name} is required by source policy",
                    item=row_ref,
                    source_type=source_type,
                )
            )
    return issues


def _required_expected_fields(
    *,
    source_type: str,
    expected_action: str,
) -> tuple[str, ...]:
    if source_type.startswith("synthetic_template"):
        return (
            "action",
            "artifacts",
            "clarification_fields",
            "clarify",
            "features",
            "inferred",
            "interfaces",
            "unsupported_requirements",
        )
    if source_type == "greenshot_7_intent_fixture":
        return (
            "action",
            "clarification_fields",
            "features",
            "unsupported_requirements",
        )
    required = ["artifacts", "clarify", "features", "interfaces"]
    if expected_action == "ask_clarification":
        required.append("clarification_fields")
    return tuple(required)


def _synthetic_provenance_issues(
    row: dict[str, object],
    *,
    index: int,
    source_type: str,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if not _is_synthetic_template_row(row, source_type=source_type):
        generation = row.get("generation")
        if generation is not None and not isinstance(generation, dict):
            issues.append(
                _validation_issue(
                    "error",
                    "generation_invalid_type",
                    field="generation",
                    message="generation must be an object when present",
                    item=_row_reference(row, index),
                )
            )
        return issues

    row_ref = _row_reference(row, index)
    family = _prompt_family(row)
    if not family:
        issues.append(
            _validation_issue(
                "error",
                "prompt_family_missing",
                field="prompt_family",
                message="synthetic template row must include prompt_family",
                item=row_ref,
            )
        )

    generation = row.get("generation")
    if not isinstance(generation, dict):
        issues.append(
            _validation_issue(
                "error",
                "synthetic_generation_metadata_missing",
                field="generation",
                message="synthetic template row must include generation metadata",
                item=row_ref,
            )
        )
        return issues

    template_version = generation.get("template_version")
    if not isinstance(template_version, str) or not template_version:
        issues.append(
            _validation_issue(
                "error",
                "synthetic_template_version_missing",
                field="generation.template_version",
                message="synthetic template row must include generation.template_version",
                item=row_ref,
            )
        )
    elif template_version not in PROMPT_CORPUS_SYNTHETIC_TEMPLATE_VERSIONS:
        issues.append(
            _validation_issue(
                "error",
                "unsupported_synthetic_template_version",
                field="generation.template_version",
                message=(
                    f"unsupported synthetic template version {template_version!r}; "
                    f"allowed={list(PROMPT_CORPUS_SYNTHETIC_TEMPLATE_VERSIONS)}"
                ),
                item=row_ref,
                value=template_version,
                allowed=list(PROMPT_CORPUS_SYNTHETIC_TEMPLATE_VERSIONS),
            )
        )

    review_status = generation.get("review_status")
    if not isinstance(review_status, str) or not review_status:
        issues.append(
            _validation_issue(
                "error",
                "synthetic_review_status_missing",
                field="generation.review_status",
                message="synthetic template row must include generation.review_status",
                item=row_ref,
            )
        )
    elif review_status not in PROMPT_CORPUS_SYNTHETIC_REVIEW_STATUSES:
        issues.append(
            _validation_issue(
                "error",
                "unsupported_synthetic_review_status",
                field="generation.review_status",
                message=(
                    f"unsupported synthetic review status {review_status!r}; "
                    f"allowed={list(PROMPT_CORPUS_SYNTHETIC_REVIEW_STATUSES)}"
                ),
                item=row_ref,
                value=review_status,
                allowed=list(PROMPT_CORPUS_SYNTHETIC_REVIEW_STATUSES),
            )
        )
    return issues


def _validation_issue(
    severity: str,
    issue: str,
    *,
    field: str,
    message: str,
    item: dict[str, object],
    **extra: object,
) -> dict[str, object]:
    row_ref = {
        key: item[key]
        for key in ("row_index", "line", "id")
        if key in item
    }
    return {
        **row_ref,
        "severity": severity,
        "issue": issue,
        "field": field,
        "message": message,
        **extra,
    }


def _validation_issue_sort_key(issue: dict[str, object]) -> tuple[object, ...]:
    line = issue.get("line")
    return (
        0 if issue["severity"] == "error" else 1,
        line if isinstance(line, int) else 10**9,
        str(issue.get("issue", "")),
        str(issue.get("field", "")),
    )


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _expected_field_type_message(item: dict[str, object]) -> str:
    issue = item.get("issue")
    field = item.get("field")
    if issue == "invalid_type":
        return (
            f"{field} must be {item.get('expected_type')}; "
            f"got {item.get('actual_type')}"
        )
    if issue == "invalid_list_items":
        return f"{field} must contain non-empty strings"
    if issue == "unknown_expected_field":
        return f"{field} is not a supported expected field"
    return f"{field} has invalid expected-field schema"


def _prompt_corpus_validation_policy() -> dict[str, object]:
    return {
        "fatal": [
            "missing or invalid required top-level fields",
            "duplicate row ids",
            "unsupported split/source_type/task_type/repo_mode labels",
            "unsupported expected.action labels",
            "invalid expected-field types or list items",
            "missing synthetic prompt_family or generation metadata",
            "exact normalized prompt duplicates across splits",
        ],
        "review": [
            "near-duplicate prompts across splits",
            "prompt families that span multiple splits",
            "legacy human_seed rows that omit explicit expected.action",
        ],
        "source_policies": {
            "human_seed": (
                "legacy seed rows may omit expected.action and "
                "expected.unsupported_requirements when the action is derivable"
            ),
            "synthetic_template_v0": (
                "requires expected.action, stable expected list fields, "
                "prompt_family, generation.template_version, and "
                "generation.review_status"
            ),
            "greenshot_7_intent_fixture": (
                "request-spec fixture rows require explicit expected.action, "
                "features, unsupported_requirements, and clarification_fields; "
                "prompt_family/generation are not required"
            ),
        },
    }


def _row_reference(row: dict[str, object], index: int) -> dict[str, object]:
    row_id = row.get("id")
    return {
        "row_index": index,
        "line": index + 1,
        "id": row_id if isinstance(row_id, str) and row_id else None,
    }


def _required_field_issues(
    row: dict[str, object],
    *,
    index: int,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    row_ref = _row_reference(row, index)
    for field in PROMPT_CORPUS_REQUIRED_FIELDS:
        if field not in row:
            issues.append({**row_ref, "field": field, "issue": "missing"})
            continue
        value = row[field]
        expected_type = PROMPT_CORPUS_REQUIRED_FIELD_TYPES[field]
        if not isinstance(value, expected_type):
            issues.append({**row_ref, "field": field, "issue": "invalid_type"})
            continue
        if isinstance(value, str) and not value.strip():
            issues.append({**row_ref, "field": field, "issue": "empty"})
    return issues


def _safe_requires_clarification(
    *,
    expected: dict[str, object],
    expected_action: str,
) -> str:
    clarification_fields = expected.get("clarification_fields", [])
    if not isinstance(clarification_fields, list):
        clarification_fields = []
    if (
        expected_action == "ask_clarification"
        or expected.get("clarify") is True
        or clarification_fields
    ):
        return "yes"
    return "no"


def _row_is_ambiguous(
    *,
    task_type: str,
    tags: Sequence[str],
    expected_action: str,
    requires_clarification: str,
) -> bool:
    return (
        task_type == "clarify"
        or expected_action == "ask_clarification"
        or requires_clarification == "yes"
        or "ambiguous" in tags
        or "clarification" in tags
    )


def _expected_field_type_issues(
    row: dict[str, object],
    expected: dict[str, object],
    *,
    index: int,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    row_ref = _row_reference(row, index)
    for field, value in expected.items():
        expected_type = PROMPT_CORPUS_EXPECTED_FIELD_TYPES.get(field)
        if expected_type is None:
            issues.append(
                {
                    **row_ref,
                    "field": f"expected.{field}",
                    "issue": "unknown_expected_field",
                }
            )
            continue
        if not isinstance(value, expected_type):
            issues.append(
                {
                    **row_ref,
                    "field": f"expected.{field}",
                    "issue": "invalid_type",
                    "expected_type": expected_type.__name__,
                    "actual_type": type(value).__name__,
                }
            )
            continue
        if field in PROMPT_CORPUS_EXPECTED_LIST_FIELDS:
            invalid_items = [
                item for item in value if not isinstance(item, str) or not item
            ]
            if invalid_items:
                issues.append(
                    {
                        **row_ref,
                        "field": f"expected.{field}",
                        "issue": "invalid_list_items",
                    }
                )
    return issues


def _prompt_family(row: dict[str, object]) -> str | None:
    family = row.get("prompt_family")
    if isinstance(family, str) and family:
        return family
    tags = row.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, str):
                continue
            for prefix in ("prompt_family:", "family:"):
                if tag.startswith(prefix) and len(tag) > len(prefix):
                    return tag[len(prefix):]
    return None


def _template_version(row: dict[str, object]) -> str | None:
    generation = row.get("generation")
    if isinstance(generation, dict):
        template_version = generation.get("template_version")
        if isinstance(template_version, str) and template_version:
            return template_version

    tags = row.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("prompt-corpus-template-"):
                return tag
    return None


def _generation_review_status(row: dict[str, object]) -> str | None:
    generation = row.get("generation")
    if not isinstance(generation, dict):
        return None
    review_status = generation.get("review_status")
    if isinstance(review_status, str) and review_status:
        return review_status
    return None


def _is_synthetic_template_row(
    row: dict[str, object],
    *,
    source_type: str,
) -> bool:
    if source_type.startswith("synthetic_template"):
        return True
    tags = row.get("tags")
    if isinstance(tags, list):
        return any(
            isinstance(tag, str) and tag.startswith("prompt-corpus-template-")
            for tag in tags
        )
    return False


def _near_duplicate_cross_split_prompts(
    prompt_rows: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    pairs: list[dict[str, object]] = []
    for left_index, left in enumerate(prompt_rows):
        for right in prompt_rows[left_index + 1:]:
            if left["split"] == right["split"]:
                continue
            left_prompt = str(left["normalized_prompt"])
            right_prompt = str(right["normalized_prompt"])
            ratio = SequenceMatcher(None, left_prompt, right_prompt).ratio()
            left_tokens = left["tokens"]
            right_tokens = right["tokens"]
            if not isinstance(left_tokens, set) or not isinstance(right_tokens, set):
                continue
            token_overlap = _token_overlap(left_tokens, right_tokens)
            if (
                ratio < PROMPT_CORPUS_NEAR_DUPLICATE_RATIO
                or token_overlap < PROMPT_CORPUS_NEAR_DUPLICATE_TOKEN_OVERLAP
            ):
                continue
            pairs.append(
                {
                    "similarity": round(ratio, 4),
                    "token_overlap": round(token_overlap, 4),
                    "left": _near_duplicate_row_record(left),
                    "right": _near_duplicate_row_record(right),
                }
            )

    return sorted(
        pairs,
        key=lambda pair: (
            -float(pair["similarity"]),
            -float(pair["token_overlap"]),
            str(pair["left"]["id"]),
            str(pair["right"]["id"]),
        ),
    )[:PROMPT_CORPUS_NEAR_DUPLICATE_LIMIT]


def _near_duplicate_row_record(row: dict[str, object]) -> dict[str, object]:
    return {
        "row_index": row["row_index"],
        "line": row["line"],
        "id": row["id"],
        "split": row["split"],
        "source_type": row["source_type"],
        "prompt": row["prompt"],
    }


def _token_overlap(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right)


def _schema_variant_records(
    variants: Counter[tuple[str, ...]],
) -> list[dict[str, object]]:
    return [
        {"count": count, "fields": list(fields)}
        for fields, count in sorted(
            variants.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _schema_consistency_issues(
    *,
    total_rows: int,
    row_schema_variants: Sequence[dict[str, object]],
    expected_schema_variants: Sequence[dict[str, object]],
    top_level_field_counts: Counter[str],
    expected_field_counts: Counter[str],
    expected_field_type_issues: Sequence[dict[str, object]],
    unsupported_scalar_labels: Sequence[dict[str, object]],
    duplicate_cross_split_prompts: Sequence[dict[str, object]],
    near_duplicate_cross_split_prompts: Sequence[dict[str, object]],
    family_split_leakage: Sequence[dict[str, object]],
    synthetic_generation_missing: int,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if len(row_schema_variants) > 1:
        issues.append(
            {
                "issue": "top_level_schema_variants",
                "count": len(row_schema_variants),
                "field": "__row__",
            }
        )
    if len(expected_schema_variants) > 1:
        issues.append(
            {
                "issue": "expected_schema_variants",
                "count": len(expected_schema_variants),
                "field": "expected",
            }
        )
    for field in ("prompt_family", "generation"):
        missing = total_rows - top_level_field_counts.get(field, 0)
        if missing:
            issues.append(
                {
                    "issue": "optional_top_level_field_missing",
                    "field": field,
                    "missing_count": missing,
                }
            )
    for field in ("action", "inferred", "clarification_fields", "unsupported_requirements"):
        missing = total_rows - expected_field_counts.get(field, 0)
        if missing:
            issues.append(
                {
                    "issue": "expected_field_missing",
                    "field": f"expected.{field}",
                    "missing_count": missing,
                }
            )
    if expected_field_type_issues:
        issues.append(
            {
                "issue": "expected_field_type_issues",
                "count": len(expected_field_type_issues),
                "field": "expected",
            }
        )
    if unsupported_scalar_labels:
        issues.append(
            {
                "issue": "unsupported_scalar_labels",
                "count": len(unsupported_scalar_labels),
                "field": "scalar_labels",
            }
        )
    if duplicate_cross_split_prompts:
        issues.append(
            {
                "issue": "duplicate_prompt_cross_split_leakage",
                "count": len(duplicate_cross_split_prompts),
                "field": "prompt",
            }
        )
    if near_duplicate_cross_split_prompts:
        issues.append(
            {
                "issue": "near_duplicate_prompt_cross_split_risk",
                "count": len(near_duplicate_cross_split_prompts),
                "field": "prompt",
            }
        )
    if family_split_leakage:
        issues.append(
            {
                "issue": "prompt_family_cross_split_leakage",
                "count": len(family_split_leakage),
                "field": "prompt_family",
            }
        )
    if synthetic_generation_missing:
        issues.append(
            {
                "issue": "synthetic_generation_metadata_missing",
                "count": synthetic_generation_missing,
                "field": "generation",
            }
        )
    return issues


def _data_002_validate_fields(
    schema_consistency_issues: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    fields = {
        "id": "non-empty unique row identifier",
        "split": "supported stable split label",
        "source_type": "supported provenance label",
        "task_type": "supported task label",
        "repo_mode": "supported repository mode",
        "domain": "non-empty domain label",
        "prompt": "non-empty prompt string and normalized duplicate key",
        "tags": "list of non-empty strings",
        "prompt_family": "template family or intentional missing marker",
        "generation.template_version": "required for synthetic template rows",
        "generation.review_status": "required for synthetic template rows",
        "expected.action": "explicit supported action label",
        "expected.features": "list of non-empty strings",
        "expected.artifacts": "list of non-empty strings",
        "expected.interfaces": "list of non-empty strings",
        "expected.inferred": "list of non-empty inferred default labels",
        "expected.clarify": "boolean clarification marker",
        "expected.clarification_fields": "list of non-empty strings",
        "expected.unsupported_requirements": "list of non-empty strings",
    }
    issue_fields = {
        str(issue.get("field"))
        for issue in schema_consistency_issues
        if issue.get("field")
    }
    return [
        {
            "field": field,
            "reason": reason,
            "flagged_by_current_profile": field in issue_fields,
        }
        for field, reason in sorted(fields.items())
    ]


def _optional_scalar(value: object) -> str:
    if isinstance(value, str) and value:
        return value
    return "__missing__"


def _string_list_value(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


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
        "unsupported_requirement_family": target.unsupported_requirement_family,
        "artifacts": list(target.artifacts),
        "unsupported_requirements": list(target.unsupported_requirements),
        "clarification_fields": list(target.clarification_fields),
        "inferred_defaults": list(target.inferred_defaults),
    }


def _baseline_report_fields(target_fields: Sequence[str]) -> tuple[str, ...]:
    fields = list(target_fields)
    for required in ("expected_action", "requires_clarification"):
        if required not in fields:
            fields.append(required)
    invalid = [field for field in fields if field not in SCALAR_TARGET_FIELDS]
    if invalid:
        raise ValueError(
            "target_fields must be scalar prompt-intent fields; "
            f"invalid={', '.join(invalid)}"
        )
    return tuple(dict.fromkeys(fields))


def _field_baseline_for_report(
    records: Sequence[PromptIntentRecord],
    *,
    target_field: str,
    train_split: str,
    eval_splits: Sequence[str],
    epochs: int,
) -> dict[str, object]:
    train_records = [record for record in records if record.split == train_split]
    label_counts = Counter(
        _scalar_target_value(record, target_field) for record in train_records
    )
    majority_label = _majority_label(label_counts)
    if len(label_counts) < 2:
        return {
            "status": "constant_single_train_label",
            "target_field": target_field,
            "train_rows": len(train_records),
            "majority_label": majority_label,
            "labels": tuple(sorted(label_counts)),
            "model": None,
            "metrics": {
                split: _evaluate_constant_label_baseline(
                    [record for record in records if record.split == split],
                    target_field=target_field,
                    baseline_label=majority_label,
                )
                for split in eval_splits
            },
        }

    result = train_prompt_intent_token_baseline(
        records,
        target_field=target_field,
        train_split=train_split,
        eval_splits=eval_splits,
        epochs=epochs,
    )
    return {
        "status": "trained",
        "target_field": target_field,
        "train_rows": result.train_rows,
        "majority_label": result.majority_label,
        "labels": result.model.labels,
        "model": result.model,
        "metrics": result.metrics,
    }


def _evaluate_constant_label_baseline(
    records: Sequence[PromptIntentRecord],
    *,
    target_field: str,
    baseline_label: str,
) -> PromptIntentLabelMetrics:
    residuals: list[PromptIntentLabelResidual] = []
    confusion: dict[str, dict[str, int]] = {}
    correct = 0
    for record in records:
        expected = _scalar_target_value(record, target_field)
        confusion.setdefault(expected, {})
        confusion[expected][baseline_label] = (
            confusion[expected].get(baseline_label, 0) + 1
        )
        if expected == baseline_label:
            correct += 1
        else:
            residuals.append(
                PromptIntentLabelResidual(
                    target_field=target_field,
                    row_id=record.row_id,
                    split=record.split,
                    source_type=record.source_type,
                    prompt=record.prompt,
                    expected=expected,
                    predicted=baseline_label,
                    baseline_label=baseline_label,
                    baseline_correct=baseline_label == expected,
                    tags=record.tags,
                    target_context=_target_context(record.target),
                )
            )
    return PromptIntentLabelMetrics(
        split=records[0].split if records else "empty",
        total=len(records),
        correct=correct,
        baseline_label=baseline_label,
        baseline_correct=correct,
        confusion={
            expected: dict(sorted(predictions.items()))
            for expected, predictions in sorted(confusion.items())
        },
        residuals=tuple(residuals),
    )


def _field_model_report(field_model: dict[str, object]) -> dict[str, object]:
    metrics = field_model["metrics"]
    assert isinstance(metrics, dict)
    return {
        "status": field_model["status"],
        "train_rows": field_model["train_rows"],
        "majority_label": field_model["majority_label"],
        "labels": list(field_model["labels"]),  # type: ignore[arg-type]
        "metrics": {
            split: _compact_label_metrics(metric)
            for split, metric in sorted(metrics.items())
            if isinstance(metric, PromptIntentLabelMetrics)
        },
    }


def _compact_label_metrics(metrics: PromptIntentLabelMetrics) -> dict[str, object]:
    return {
        "total": metrics.total,
        "correct": metrics.correct,
        "accuracy": metrics.accuracy,
        "baseline": {
            "label": metrics.baseline_label,
            "correct": metrics.baseline_correct,
            "accuracy": metrics.baseline_accuracy,
        },
        "residual_count": len(metrics.residuals),
        "confusion": metrics.confusion,
    }


def _predict_field_for_report(
    field_model: dict[str, object],
    prompt: str,
) -> str:
    model = field_model.get("model")
    if isinstance(model, PromptIntentTokenPerceptronModel):
        return model.predict_label(prompt)
    return str(field_model["majority_label"])


def _evaluate_baseline_report_split(
    records: Sequence[PromptIntentRecord],
    *,
    split: str,
    fields: Sequence[str],
    field_models: dict[str, dict[str, object]],
    inferred_model: dict[str, object],
    residual_groups: dict[tuple[str, str, str, str], dict[str, object]],
    residual_limit: int,
) -> dict[str, object]:
    field_correct = {field: 0 for field in fields}
    exact_field_matches = 0
    ambiguity_correct = 0
    clarification_correct = 0
    inferred_true_positive = 0
    inferred_false_positive = 0
    inferred_false_negative = 0
    inferred_exact_matches = 0

    for record in records:
        predictions = {
            field: _predict_field_for_report(field_models[field], record.prompt)
            for field in fields
        }
        row_exact = True
        for field in fields:
            expected = _scalar_target_value(record, field)
            predicted = predictions[field]
            if predicted == expected:
                field_correct[field] += 1
            else:
                row_exact = False
                _add_baseline_residual_group(
                    residual_groups,
                    split=split,
                    target_field=field,
                    expected=expected,
                    predicted=predicted,
                    record=record,
                    residual_limit=residual_limit,
                )
        if row_exact:
            exact_field_matches += 1

        if predictions["requires_clarification"] == record.target.requires_clarification:
            clarification_correct += 1
        if _predicted_ambiguity(predictions) == _expected_ambiguity(record):
            ambiguity_correct += 1

        predicted_inferred = set(
            _predict_inferred_defaults(inferred_model, record.prompt)
        )
        expected_inferred = set(record.target.inferred_defaults)
        if predicted_inferred == expected_inferred:
            inferred_exact_matches += 1
        for label in sorted(expected_inferred & predicted_inferred):
            inferred_true_positive += 1
        for label in sorted(predicted_inferred - expected_inferred):
            inferred_false_positive += 1
            _add_baseline_residual_group(
                residual_groups,
                split=split,
                target_field="inferred_defaults",
                expected="<absent>",
                predicted=label,
                record=record,
                residual_limit=residual_limit,
            )
        for label in sorted(expected_inferred - predicted_inferred):
            inferred_false_negative += 1
            _add_baseline_residual_group(
                residual_groups,
                split=split,
                target_field="inferred_defaults",
                expected=label,
                predicted="<missing>",
                record=record,
                residual_limit=residual_limit,
            )

    total = len(records)
    return {
        "total": total,
        "exact_field_accuracy": {
            "correct": exact_field_matches,
            "total": total,
            "accuracy": exact_field_matches / total if total else 0.0,
        },
        "field_accuracy": {
            field: {
                "correct": correct,
                "total": total,
                "accuracy": correct / total if total else 0.0,
            }
            for field, correct in field_correct.items()
        },
        "clarification_accuracy": {
            "correct": clarification_correct,
            "total": total,
            "accuracy": clarification_correct / total if total else 0.0,
        },
        "ambiguity_accuracy": {
            "correct": ambiguity_correct,
            "total": total,
            "accuracy": ambiguity_correct / total if total else 0.0,
        },
        "inferred_default_metrics": {
            "true_positive": inferred_true_positive,
            "false_positive": inferred_false_positive,
            "false_negative": inferred_false_negative,
            "precision": (
                inferred_true_positive
                / (inferred_true_positive + inferred_false_positive)
                if inferred_true_positive + inferred_false_positive
                else 0.0
            ),
            "recall": (
                inferred_true_positive
                / (inferred_true_positive + inferred_false_negative)
                if inferred_true_positive + inferred_false_negative
                else 0.0
            ),
            "exact_match_accuracy": {
                "correct": inferred_exact_matches,
                "total": total,
                "accuracy": inferred_exact_matches / total if total else 0.0,
            },
        },
    }


def _expected_ambiguity(record: PromptIntentRecord) -> bool:
    return (
        record.target.requires_clarification == "yes"
        or record.target.expected_action == "ask_clarification"
        or record.target.task_type == "clarify"
        or "ambiguous" in record.tags
    )


def _predicted_ambiguity(predictions: dict[str, str]) -> bool:
    return (
        predictions.get("requires_clarification") == "yes"
        or predictions.get("expected_action") == "ask_clarification"
    )


def _add_baseline_residual_group(
    groups: dict[tuple[str, str, str, str], dict[str, object]],
    *,
    split: str,
    target_field: str,
    expected: str,
    predicted: str,
    record: PromptIntentRecord,
    residual_limit: int,
) -> None:
    key = (split, target_field, expected, predicted)
    group = groups.setdefault(
        key,
        {
            "split": split,
            "target_field": target_field,
            "expected": expected,
            "predicted": predicted,
            "count": 0,
            "examples": [],
        },
    )
    group["count"] = int(group["count"]) + 1
    examples = group["examples"]
    assert isinstance(examples, list)
    if len(examples) < residual_limit:
        examples.append(
            {
                "id": record.row_id,
                "source_type": record.source_type,
                "task_type": record.target.task_type,
                "repo_mode": record.target.repo_mode,
                "prompt": record.prompt,
            }
        )


def _train_inferred_default_baseline(
    records: Sequence[PromptIntentRecord],
    *,
    train_split: str,
    epochs: int,
) -> dict[str, object]:
    train_records = [record for record in records if record.split == train_split]
    labels = tuple(
        sorted(
            {
                label
                for record in train_records
                for label in record.target.inferred_defaults
            }
        )
    )
    weights = {label: Counter() for label in labels}
    if not labels:
        return {"status": "constant_empty", "labels": labels, "weights": weights}

    for _epoch in range(epochs):
        for record in train_records:
            features = _prompt_token_features(record.prompt)
            expected_labels = set(record.target.inferred_defaults)
            for label in labels:
                expected = 1 if label in expected_labels else -1
                predicted = 1 if _score_label(features, weights[label]) > 0 else -1
                if predicted == expected:
                    continue
                for feature, value in features.items():
                    weights[label][feature] += expected * value

    return {"status": "trained_one_vs_rest", "labels": labels, "weights": weights}


def _predict_inferred_defaults(
    model: dict[str, object],
    prompt: str,
) -> tuple[str, ...]:
    labels = model["labels"]
    weights = model["weights"]
    if not isinstance(labels, tuple) or not isinstance(weights, dict):
        return ()
    features = _prompt_token_features(prompt)
    return tuple(
        label
        for label in labels
        if isinstance(label, str)
        and _score_label(features, weights.get(label, {})) > 0
    )


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
    features.update(_prompt_character_ngram_features(tokens))
    features.update(_prompt_skip_bigram_features(tokens))
    return features


def _prompt_tokens(prompt: str) -> list[str]:
    return re.findall(r"\*\*|\^|[a-z0-9_]+", prompt.lower())


def _prompt_token_set(prompt: str) -> set[str]:
    return set(_prompt_tokens(prompt))


def _prompt_character_ngram_features(tokens: Sequence[str]) -> Counter[str]:
    normalized = f" {' '.join(tokens)} "
    features: Counter[str] = Counter()
    for width in range(3, 6):
        features.update(
            f"char{width}={normalized[index:index + width]}"
            for index in range(len(normalized) - width + 1)
        )
    return features


def _prompt_skip_bigram_features(tokens: Sequence[str]) -> Counter[str]:
    features: Counter[str] = Counter()
    for left_index, left in enumerate(tokens):
        max_right_index = min(len(tokens), left_index + 4)
        for right_index in range(left_index + 2, max_right_index):
            distance = right_index - left_index
            features[f"skip{distance}={left} {tokens[right_index]}"] += 1
    return features


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
