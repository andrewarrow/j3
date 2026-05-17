"""Deterministic request-spec parsing for the GreenShot-7 calculator slice."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from prompt_intents import PromptIntentPrediction, PromptIntentTarget


SCHEMA_VERSION = "request-spec-v1"
CALCULATOR_FEATURES = ["add", "subtract", "multiply", "divide"]
CALCULATOR_ALIASES = {
    "add": ["add", "plus", "+"],
    "subtract": ["subtract", "sub", "minus", "-"],
    "multiply": ["multiply", "mul", "times", "x", "*"],
    "divide": ["divide", "div", "/"],
}
CALCULATOR_ARTIFACTS = ["calculator.py", "tests/test_calculator_cli.py"]
CALCULATOR_INTERFACES = [{"kind": "cli", "style": "argparse"}]
CALCULATOR_VALIDATION = {
    "commands": ["python -m pytest tests/test_calculator_cli.py -q"],
    "hidden_cases": True,
}
BLOCKED_VALIDATION = {"commands": [], "hidden_cases": False}


@dataclass(frozen=True, slots=True)
class RequestSpec:
    """A JSON-compatible user request contract for greenfield work."""

    schema_version: str
    task_name: str
    task_type: str
    language: str
    repo_mode: str
    domain: str
    prompt: str
    artifacts: list[str] = field(default_factory=list)
    interfaces: list[dict[str, str]] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    operation_aliases: dict[str, list[str]] = field(default_factory=dict)
    inferred_defaults: list[dict[str, Any]] = field(default_factory=list)
    requested_interfaces: list[dict[str, object]] = field(default_factory=list)
    supported_interfaces: list[dict[str, str]] = field(default_factory=list)
    unsupported_requirements: list[dict[str, str]] = field(default_factory=list)
    clarifications_needed: list[dict[str, str]] = field(default_factory=list)
    validation: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        """Return a JSON-serializable request-spec record."""

        record = {
            "schema_version": self.schema_version,
            "task_name": self.task_name,
            "task_type": self.task_type,
            "language": self.language,
            "repo_mode": self.repo_mode,
            "domain": self.domain,
            "prompt": self.prompt,
            "artifacts": list(self.artifacts),
            "interfaces": [dict(interface) for interface in self.interfaces],
            "features": list(self.features),
            "operation_aliases": {
                operation: list(aliases)
                for operation, aliases in self.operation_aliases.items()
            },
            "inferred_defaults": [
                {
                    key: list(value) if isinstance(value, list) else value
                    for key, value in inferred.items()
                }
                for inferred in self.inferred_defaults
            ],
            "clarifications_needed": [
                dict(clarification) for clarification in self.clarifications_needed
            ],
            "validation": {
                "commands": list(self.validation.get("commands", [])),
                "hidden_cases": bool(self.validation.get("hidden_cases", False)),
            },
        }
        if self.requested_interfaces:
            record["requested_interfaces"] = [
                dict(interface) for interface in self.requested_interfaces
            ]
        if self.supported_interfaces:
            record["supported_interfaces"] = [
                dict(interface) for interface in self.supported_interfaces
            ]
        if self.unsupported_requirements:
            record["unsupported_requirements"] = [
                dict(requirement) for requirement in self.unsupported_requirements
            ]
        return record


def parse_request_to_spec(
    prompt: str,
    task_name: str | None = None,
    *,
    intent: PromptIntentPrediction | PromptIntentTarget | None = None,
) -> RequestSpec:
    """Parse a narrow coding-agent prompt into a request-spec-v1 record."""

    normalized = _normalize(prompt)
    resolved_task_name = task_name or _slug_task_name(prompt)
    intent_target = _intent_target(intent)

    if _intent_blocks_unsupported_interface(intent_target):
        return _intent_clarification_spec(
            prompt=prompt,
            task_name=resolved_task_name,
            target=intent_target,
            confidence=_intent_confidence(intent),
        )

    if _mentions_scientific_calculator(normalized):
        return _clarification_spec(
            prompt=prompt,
            task_name=resolved_task_name,
            domain="calculator",
            field="features",
            question="Which scientific calculator operations should be supported?",
        )

    explicit_features = _explicit_features(normalized)
    calculator_domain = _has_calculator_domain(normalized, explicit_features)

    if not calculator_domain:
        return _clarification_spec(
            prompt=prompt,
            task_name=resolved_task_name,
            domain="unknown",
            field="domain",
            question=(
                "Should this be a basic CLI calculator, and which operations "
                "should it support?"
            ),
        )

    features = list(explicit_features)
    inferred_defaults: list[dict[str, Any]] = []

    if _has_basic_etc_default(normalized, features):
        features, inferred_defaults = _merge_inferred_features(
            features,
            inferred=CALCULATOR_FEATURES,
            reason="basic_calculator_etc_default_operations",
            confidence=0.86,
        )
    elif _has_operator_parameter_default(normalized):
        features, inferred_defaults = _merge_inferred_features(
            features,
            inferred=CALCULATOR_FEATURES,
            reason="operator_parameter_default_operations",
            confidence=0.82,
        )
    elif _has_simple_calculator_default(normalized, features):
        features, inferred_defaults = _merge_inferred_features(
            features,
            inferred=CALCULATOR_FEATURES,
            reason="simple_calculator_default_operations",
            confidence=0.84,
        )
    elif _has_generic_calculator_default(normalized, features):
        features, inferred_defaults = _merge_inferred_features(
            features,
            inferred=CALCULATOR_FEATURES,
            reason="generic_calculator_default_operations",
            confidence=0.8,
        )

    if not features:
        return _clarification_spec(
            prompt=prompt,
            task_name=resolved_task_name,
            domain="calculator",
            field="features",
            question="Which calculator operations should be supported?",
        )

    return RequestSpec(
        schema_version=SCHEMA_VERSION,
        task_name=resolved_task_name,
        task_type="create_app",
        language="python",
        repo_mode="new_repo",
        domain="calculator",
        prompt=prompt,
        artifacts=list(CALCULATOR_ARTIFACTS),
        interfaces=[dict(interface) for interface in CALCULATOR_INTERFACES],
        features=features,
        operation_aliases=_aliases_for(features),
        inferred_defaults=inferred_defaults,
        clarifications_needed=[],
        validation={
            "commands": list(CALCULATOR_VALIDATION["commands"]),
            "hidden_cases": CALCULATOR_VALIDATION["hidden_cases"],
        },
    )


def _intent_target(
    intent: PromptIntentPrediction | PromptIntentTarget | None,
) -> PromptIntentTarget | None:
    if isinstance(intent, PromptIntentPrediction):
        return intent.target
    if isinstance(intent, PromptIntentTarget):
        return intent
    return None


def _intent_confidence(
    intent: PromptIntentPrediction | PromptIntentTarget | None,
) -> float:
    if isinstance(intent, PromptIntentPrediction):
        return intent.confidence
    return 1.0


def _intent_blocks_unsupported_interface(target: PromptIntentTarget | None) -> bool:
    if target is None:
        return False
    return (
        target.expected_action == "ask_clarification"
        and "interfaces" in target.clarification_fields
        and bool(target.requested_interfaces or target.unsupported_requirements)
    )


def _intent_clarification_spec(
    *,
    prompt: str,
    task_name: str,
    target: PromptIntentTarget,
    confidence: float,
) -> RequestSpec:
    requested_interfaces = [
        {"kind": interface, "confidence": confidence}
        for interface in target.requested_interfaces
    ]
    unsupported_requirements = [
        {
            "field": "interfaces",
            "value": requirement,
            "reason": requirement,
        }
        for requirement in target.unsupported_requirements
    ]
    return _clarification_spec(
        prompt=prompt,
        task_name=task_name,
        domain=target.domain,
        field="interfaces",
        question=(
            "This slice only supports a Python CLI calculator. Do you want a "
            "simple CLI calculator, or should a graphical app scope/framework "
            "be specified?"
        ),
        requested_interfaces=requested_interfaces,
        supported_interfaces=[dict(interface) for interface in CALCULATOR_INTERFACES],
        unsupported_requirements=unsupported_requirements,
    )


def _normalize(prompt: str) -> str:
    return " ".join(prompt.lower().strip().split())


def _slug_task_name(prompt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")
    return slug or "request"


def _mentions_scientific_calculator(normalized: str) -> bool:
    return _has_word(normalized, "scientific") and (
        _has_word(normalized, "calculator") or _has_word(normalized, "calc")
    )


def _has_calculator_domain(normalized: str, explicit_features: list[str]) -> bool:
    if _has_word(normalized, "calculator") or _has_word(normalized, "calc"):
        return True
    if explicit_features and (
        _has_word(normalized, "cli")
        or _has_word(normalized, "app")
        or _has_word(normalized, "script")
        or _has_word(normalized, "two numbers")
        or _has_word(normalized, "number")
    ):
        return True
    return _has_operator_parameter_default(normalized)


def _explicit_features(normalized: str) -> list[str]:
    features: list[str] = []
    for feature in CALCULATOR_FEATURES:
        if _mentions_any_alias(normalized, CALCULATOR_ALIASES[feature]):
            features.append(feature)
    return features


def _mentions_any_alias(normalized: str, aliases: list[str]) -> bool:
    return any(
        _has_symbol(normalized, alias)
        if len(alias) == 1
        else _has_word(normalized, alias)
        for alias in aliases
    )


def _has_basic_etc_default(normalized: str, features: list[str]) -> bool:
    has_etc = _has_word(normalized, "etc")
    has_calculator = _has_word(normalized, "calculator") or _has_word(
        normalized, "calc"
    )
    has_multiple_ops = len(features) >= 2
    asks_basic = _has_word(normalized, "basic") or _has_word(normalized, "simple")
    return has_etc and has_calculator and (has_multiple_ops or asks_basic)


def _has_operator_parameter_default(normalized: str) -> bool:
    return (
        _has_word(normalized, "operator")
        and (_has_word(normalized, "two numbers") or _has_word(normalized, "params"))
    )


def _has_simple_calculator_default(normalized: str, features: list[str]) -> bool:
    if features:
        return False
    has_calculator = _has_word(normalized, "calculator") or _has_word(
        normalized, "calc"
    )
    asks_simple = _has_word(normalized, "simple") or _has_word(normalized, "basic")
    return has_calculator and asks_simple


def _has_generic_calculator_default(normalized: str, features: list[str]) -> bool:
    if features:
        return False
    return _has_word(normalized, "calculator") or _has_word(normalized, "calc")


def _merge_inferred_features(
    explicit_features: list[str],
    *,
    inferred: list[str],
    reason: str,
    confidence: float,
) -> tuple[list[str], list[dict[str, Any]]]:
    features = _ordered_unique([*explicit_features, *inferred])
    inferred_values = [
        feature for feature in inferred if feature not in explicit_features
    ]
    if not inferred_values:
        return features, []
    return features, [
        {
            "field": "features",
            "value": inferred_values,
            "reason": reason,
            "confidence": confidence,
        }
    ]


def _aliases_for(features: list[str]) -> dict[str, list[str]]:
    return {feature: list(CALCULATOR_ALIASES[feature]) for feature in features}


def _ordered_unique(features: list[str]) -> list[str]:
    seen = set(features)
    return [feature for feature in CALCULATOR_FEATURES if feature in seen]


def _clarification_spec(
    *,
    prompt: str,
    task_name: str,
    domain: str,
    field: str,
    question: str,
    requested_interfaces: list[dict[str, object]] | None = None,
    supported_interfaces: list[dict[str, str]] | None = None,
    unsupported_requirements: list[dict[str, str]] | None = None,
) -> RequestSpec:
    return RequestSpec(
        schema_version=SCHEMA_VERSION,
        task_name=task_name,
        task_type="create_app",
        language="python",
        repo_mode="new_repo",
        domain=domain,
        prompt=prompt,
        artifacts=[],
        interfaces=[],
        features=[],
        operation_aliases={},
        inferred_defaults=[],
        requested_interfaces=list(requested_interfaces or []),
        supported_interfaces=list(supported_interfaces or []),
        unsupported_requirements=list(unsupported_requirements or []),
        clarifications_needed=[{"field": field, "question": question}],
        validation=dict(BLOCKED_VALIDATION),
    )


def _has_word(normalized: str, word: str) -> bool:
    return (
        re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", normalized)
        is not None
    )


def _has_symbol(normalized: str, symbol: str) -> bool:
    if symbol == "x":
        return _has_word(normalized, symbol)
    return symbol in normalized
