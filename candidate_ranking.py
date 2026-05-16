"""Lightweight candidate ranker trained from eval diagnostics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol

from actions import PatchAction


RANKER_FORMAT = "j3.candidate-ranker.v1"
RANKER_FEATURE_VERSION = "candidate-diagnostics-v3"
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")

_SYMBOLIC_PARAM_VALUES = {
    "!=",
    "%",
    "*",
    "+",
    "-",
    "/",
    "//",
    "<",
    "<=",
    "==",
    ">",
    ">=",
    "and",
    "in",
    "is",
    "is not",
    "not in",
    "or",
}


class CandidateLike(Protocol):
    file_path: str
    action: PatchAction
    reason: str
    model_score: float | None
    failure_hint_score: float


@dataclass(frozen=True, slots=True)
class CandidateRankerTrainingResult:
    out_dir: Path
    ranker_path: Path
    metrics_path: Path
    diagnostics_paths: list[Path]
    candidate_outcome_paths: list[Path]
    rows: int
    passing_rows: int
    failing_rows: int
    tasks: int
    plans: int
    training_pairs: int
    features: int
    mistakes: int
    training_accuracy: float
    margin_violations: int


@dataclass(frozen=True, slots=True)
class CandidateRankerModel:
    """Small linear ranker over candidate diagnostics features."""

    path: Path
    weights: dict[str, float]
    bias: float = 0.0

    @classmethod
    def load(cls, path: Path) -> "CandidateRankerModel":
        resolved = path.expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if payload.get("format") != RANKER_FORMAT:
            raise ValueError(f"unsupported candidate ranker format in {resolved}")
        return cls(
            path=resolved,
            weights={str(name): float(value) for name, value in payload.get("weights", {}).items()},
            bias=float(payload.get("bias", 0.0)),
        )

    def score(self, candidate: CandidateLike, hints: list[object] | tuple[object, ...] = ()) -> float:
        return score_features(candidate_features(candidate, hints=hints), self.weights, self.bias)


def train_candidate_ranker(
    *,
    diagnostics_paths: list[Path] | None = None,
    candidate_outcome_paths: list[Path] | None = None,
    out_dir: Path,
    epochs: int = 8,
    learning_rate: float = 0.25,
    margin: float = 1.0,
    plan_name: str = "ranked",
) -> CandidateRankerTrainingResult:
    """Train a pairwise linear ranker from eval diagnostics or outcome rows."""

    diagnostics_paths = diagnostics_paths or []
    candidate_outcome_paths = candidate_outcome_paths or []
    if not diagnostics_paths:
        if not candidate_outcome_paths:
            raise ValueError("at least one diagnostics or candidate outcome path is required")
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be positive")
    if margin <= 0:
        raise ValueError("margin must be positive")

    resolved_paths = [path.expanduser().resolve() for path in diagnostics_paths]
    resolved_outcome_paths = [path.expanduser().resolve() for path in candidate_outcome_paths]
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    plans = 0
    task_names: set[str] = set()
    rows = 0
    passing_rows = 0
    failing_rows = 0
    for path in resolved_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task in payload.get("tasks", []):
            if not isinstance(task, dict):
                continue
            if task.get("name"):
                task_names.add(str(task["name"]))
            plan = task.get(plan_name)
            if not isinstance(plan, dict):
                continue
            plan_pairs = _training_pairs_from_plan(plan)
            if plan_pairs:
                plans += 1
                pairs.extend(plan_pairs)
            tested = plan.get("tested_candidates")
            if isinstance(tested, list):
                rows += len(tested)
                passing_rows += sum(
                    1 for candidate in tested if isinstance(candidate, dict) and candidate.get("passed") is True
                )

    for path in resolved_outcome_paths:
        grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            rows += 1
            task = str(row.get("task", ""))
            phase = str(row.get("phase", plan_name))
            if task:
                task_names.add(task)
            if row.get("passed") is True:
                passing_rows += 1
            grouped_rows.setdefault((task, phase), []).append(row)

        for (_task, phase), task_rows in grouped_rows.items():
            if phase != plan_name:
                continue
            plan_pairs = _training_pairs_from_outcome_rows(task_rows)
            if plan_pairs:
                plans += 1
                pairs.extend(plan_pairs)

    failing_rows = rows - passing_rows

    if not pairs:
        raise ValueError("training sources did not contain solved plans with failed candidates")

    weights: dict[str, float] = {}
    mistakes = 0
    for _ in range(epochs):
        for positive, negative in pairs:
            pos_score = score_features(positive, weights)
            neg_score = score_features(negative, weights)
            if pos_score <= neg_score + margin:
                _update_weights(weights, positive, learning_rate)
                _update_weights(weights, negative, -learning_rate)
                mistakes += 1

    correct_pairs, margin_violations = _score_training_pairs(pairs, weights, margin=margin)
    training_accuracy = correct_pairs / len(pairs)

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    ranker_path = output / "candidate-ranker.json"
    metrics_path = output / "candidate-ranker-metrics.json"
    model = {
        "format": RANKER_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": RANKER_FEATURE_VERSION,
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "candidate_outcome_sources": [str(path) for path in resolved_outcome_paths],
        "plan": plan_name,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "margin": margin,
        "bias": 0.0,
        "weights": dict(sorted(weights.items())),
    }
    metrics = {
        "diagnostics_sources": [str(path) for path in resolved_paths],
        "candidate_outcome_sources": [str(path) for path in resolved_outcome_paths],
        "plan": plan_name,
        "rows": rows,
        "passing_rows": passing_rows,
        "failing_rows": failing_rows,
        "tasks": len(task_names),
        "plans": plans,
        "training_pairs": len(pairs),
        "features": len(weights),
        "mistakes": mistakes,
        "training_accuracy": training_accuracy,
        "margin_violations": margin_violations,
        "artifacts": {
            "ranker": ranker_path.name,
            "metrics": metrics_path.name,
        },
    }
    ranker_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return CandidateRankerTrainingResult(
        out_dir=output,
        ranker_path=ranker_path,
        metrics_path=metrics_path,
        diagnostics_paths=resolved_paths,
        candidate_outcome_paths=resolved_outcome_paths,
        rows=rows,
        passing_rows=passing_rows,
        failing_rows=failing_rows,
        tasks=len(task_names),
        plans=plans,
        training_pairs=len(pairs),
        features=len(weights),
        mistakes=mistakes,
        training_accuracy=training_accuracy,
        margin_violations=margin_violations,
    )


def score_features(features: Mapping[str, float], weights: Mapping[str, float], bias: float = 0.0) -> float:
    return bias + sum(weights.get(name, 0.0) * value for name, value in features.items())


def candidate_features(
    candidate: CandidateLike,
    hints: list[object] | tuple[object, ...] = (),
) -> dict[str, float]:
    action = candidate.action.kind.value
    params = dict(candidate.action.params)
    features: dict[str, float] = {
        "bias": 1.0,
        f"action:{action}": 1.0,
        "failure_hint_score": candidate.failure_hint_score / 100.0,
    }
    if candidate.failure_hint_score > 0:
        features["has_failure_hint_score"] = 1.0
        features[f"action_has_failure_hint_score:{action}"] = 1.0
    if candidate.model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = candidate.model_score
    if candidate.action.target.symbol:
        features["has_target_symbol"] = 1.0
    if candidate.action.target.node_kind:
        features[f"node_kind:{candidate.action.target.node_kind}"] = 1.0

    _add_param_features(features, action, params)
    _add_import_locality_features(features, action, candidate.file_path, params)

    for hint in hints:
        _merge_hint_features(features, candidate, action, hint)
    if hints:
        _add_hint_token_overlap_features(
            features,
            action=action,
            candidate_tokens=_candidate_tokens(
                candidate.file_path,
                candidate.action.target.symbol,
                params,
            ),
            params=params,
            hint_tokens=_hint_tokens(hints),
        )

    return features


def _training_pairs_from_plan(plan: dict[str, object]) -> list[tuple[dict[str, float], dict[str, float]]]:
    tested = plan.get("tested_candidates")
    selected = plan.get("selected")
    if not isinstance(tested, list) or not isinstance(selected, dict):
        return []

    hints = plan.get("failure_hints", [])
    positive_index = _first_passing_index(tested)
    if positive_index is None:
        return []
    positive = tested[positive_index]
    if not isinstance(positive, dict):
        return []

    positive_features = _candidate_record_features(positive, hints)
    pairs: list[tuple[dict[str, float], dict[str, float]]] = []
    for index, candidate in enumerate(tested):
        if index == positive_index:
            continue
        if isinstance(candidate, dict) and candidate.get("passed") is not True:
            pairs.append((positive_features, _candidate_record_features(candidate, hints)))
    return pairs


def _training_pairs_from_outcome_rows(
    rows: list[dict[str, object]],
) -> list[tuple[dict[str, float], dict[str, float]]]:
    ordered_rows = sorted(rows, key=lambda row: _int_value(row.get("rank_index"), default=0))
    positive = _first_passing_outcome_row(ordered_rows)
    if positive is None:
        return []

    hints = _outcome_row_hints(ordered_rows)
    positive_features = _candidate_record_features(positive, hints)
    return [
        (positive_features, _candidate_record_features(candidate, hints))
        for candidate in ordered_rows
        if candidate is not positive and candidate.get("passed") is not True
    ]


def _first_passing_outcome_row(rows: list[dict[str, object]]) -> dict[str, object] | None:
    for candidate in rows:
        if candidate.get("is_first_pass") is True:
            return candidate
    for candidate in rows:
        if candidate.get("passed") is True:
            return candidate
    return None


def _first_passing_index(candidates: list[object]) -> int | None:
    for index, candidate in enumerate(candidates):
        if isinstance(candidate, dict) and candidate.get("passed") is True:
            return index
    return None


def _candidate_record_features(candidate: dict[str, object], hints: object) -> dict[str, float]:
    action = str(candidate.get("action", ""))
    params = candidate.get("params", {})
    features: dict[str, float] = {
        "bias": 1.0,
        f"action:{action}": 1.0,
        "failure_hint_score": _float_value(candidate.get("failure_hint_score")) / 100.0,
    }
    if _float_value(candidate.get("failure_hint_score")) > 0:
        features["has_failure_hint_score"] = 1.0
        features[f"action_has_failure_hint_score:{action}"] = 1.0
    model_score = candidate.get("model_score")
    if model_score is not None:
        features["has_model_score"] = 1.0
        features["model_score"] = _float_value(model_score)
    symbol = candidate.get("symbol")
    if symbol:
        features["has_target_symbol"] = 1.0
    node_kind = candidate.get("node_kind")
    if node_kind:
        features[f"node_kind:{node_kind}"] = 1.0
    if isinstance(params, dict):
        _add_param_features(features, action, params)
        _add_import_locality_features(
            features,
            action,
            str(candidate.get("file_path", "")),
            params,
        )

    if isinstance(hints, list):
        for hint in hints:
            if isinstance(hint, dict):
                _merge_hint_record_features(features, candidate, action, hint)
        if hints and isinstance(params, dict):
            _add_hint_token_overlap_features(
                features,
                action=action,
                candidate_tokens=_candidate_tokens(
                    str(candidate.get("file_path", "")),
                    candidate.get("symbol"),
                    params,
                ),
                params=params,
                hint_tokens=_hint_record_tokens(hints),
            )
    return features


def _add_param_features(features: dict[str, float], action: str, params: Mapping[str, object]) -> None:
    for key, value in sorted(params.items()):
        normalized = _normalize_value(value)
        features[f"param:{key}"] = 1.0
        features[f"action_param:{action}:{key}"] = 1.0
        features[f"param_type:{key}:{type(value).__name__}"] = 1.0
        if normalized in _SYMBOLIC_PARAM_VALUES:
            features[f"param_symbol:{key}={normalized}"] = 1.0
            features[f"action_param_symbol:{action}:{key}={normalized}"] = 1.0

    original = params.get("from")
    replacement = params.get("to")
    if _is_plain_number(original) and _is_plain_number(replacement):
        delta = float(replacement) - float(original)
        if delta > 0:
            features["numeric_param_delta:increase"] = 1.0
        elif delta < 0:
            features["numeric_param_delta:decrease"] = 1.0
        else:
            features["numeric_param_delta:same"] = 1.0
        features[f"action_numeric_param_delta:{action}"] = 1.0


def _add_import_locality_features(
    features: dict[str, float],
    action: str,
    file_path: str,
    params: Mapping[str, object],
) -> None:
    if action != "add_import":
        return
    module = params.get("module")
    if not isinstance(module, str) or not module:
        return

    file_module_parts = _module_parts_from_file_path(file_path)
    import_parts = tuple(part for part in module.split(".") if part)
    if not file_module_parts or not import_parts:
        return

    target_package = file_module_parts[:-1]
    import_package = import_parts[:-1]
    if not target_package:
        return

    prefix = _common_prefix_len(target_package, import_package)
    if prefix:
        features["import_module_target_package_overlap"] = prefix / len(target_package)
        features["action_import_module_target_package_overlap:add_import"] = features[
            "import_module_target_package_overlap"
        ]
    if target_package == import_package:
        features["import_module_same_target_package"] = 1.0
        features["action_import_module_same_target_package:add_import"] = 1.0
    elif prefix:
        features["import_module_shares_target_package_prefix"] = 1.0
        features["action_import_module_shares_target_package_prefix:add_import"] = 1.0


def _module_parts_from_file_path(file_path: str) -> tuple[str, ...]:
    path = Path(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return tuple(parts)


def _common_prefix_len(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    count = 0
    for left_part, right_part in zip(left, right, strict=False):
        if left_part != right_part:
            break
        count += 1
    return count


def _is_plain_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _merge_hint_features(
    features: dict[str, float],
    candidate: CandidateLike,
    action: str,
    hint: object,
) -> None:
    exception_type = getattr(hint, "exception_type", None)
    if exception_type:
        features[f"hint_exception:{exception_type}"] = 1.0
        features[f"action_hint_exception:{action}:{exception_type}"] = 1.0
    assertions = getattr(hint, "assertions", [])
    if assertions:
        features["hint_has_assertion"] = 1.0
        for assertion in assertions:
            operator = getattr(assertion, "operator", None)
            if operator:
                features[f"hint_assert_operator:{operator}"] = 1.0
    if candidate.action.target.symbol and candidate.action.target.symbol in getattr(hint, "function_names", set()):
        features["hint_symbol_match"] = 1.0
        features[f"action_hint_symbol_match:{action}"] = 1.0
    if candidate.file_path in getattr(hint, "source_files", set()):
        features["hint_file_match"] = 1.0
        features[f"action_hint_file_match:{action}"] = 1.0
    _merge_name_set_features(
        features,
        action,
        dict(candidate.action.params),
        name_set=getattr(hint, "missing_names", set()),
        prefix="missing_name",
    )
    _merge_name_set_features(
        features,
        action,
        dict(candidate.action.params),
        name_set=getattr(hint, "missing_attributes", set()),
        prefix="missing_attribute",
    )
    _merge_name_set_features(
        features,
        action,
        dict(candidate.action.params),
        name_set=getattr(hint, "type_error_names", set()),
        prefix="type_error_name",
    )
    missing_keys = getattr(hint, "missing_keys", set())
    if missing_keys:
        features["hint_has_missing_key"] = 1.0
        for key in missing_keys:
            features[f"hint_missing_key:{key}"] = 1.0
            features[f"action_hint_missing_key:{action}:{key}"] = 1.0
        params = dict(candidate.action.params)
        original = params.get("from")
        replacement = params.get("to")
        if isinstance(original, str) and original in missing_keys:
            features["hint_missing_key_matches_from"] = 1.0
            features[f"action_hint_missing_key_matches_from:{action}"] = 1.0
        if isinstance(replacement, str) and any(key in replacement for key in missing_keys):
            features["hint_missing_key_in_to"] = 1.0
            features[f"action_hint_missing_key_in_to:{action}"] = 1.0


def _merge_hint_record_features(
    features: dict[str, float],
    candidate: dict[str, object],
    action: str,
    hint: dict[str, object],
) -> None:
    exception_type = hint.get("exception_type")
    if exception_type:
        features[f"hint_exception:{exception_type}"] = 1.0
        features[f"action_hint_exception:{action}:{exception_type}"] = 1.0
    assertions = hint.get("assertions", [])
    if assertions:
        features["hint_has_assertion"] = 1.0
        for assertion in assertions:
            if isinstance(assertion, dict) and assertion.get("operator"):
                features[f"hint_assert_operator:{assertion['operator']}"] = 1.0
    symbol = candidate.get("symbol")
    if symbol and symbol in set(hint.get("function_names", [])):
        features["hint_symbol_match"] = 1.0
        features[f"action_hint_symbol_match:{action}"] = 1.0
    if candidate.get("file_path") in set(hint.get("source_files", [])):
        features["hint_file_match"] = 1.0
        features[f"action_hint_file_match:{action}"] = 1.0
    params = candidate.get("params", {})
    if isinstance(params, dict):
        _merge_name_set_features(
            features,
            action,
            params,
            name_set=set(hint.get("missing_names", [])),
            prefix="missing_name",
        )
        _merge_name_set_features(
            features,
            action,
            params,
            name_set=set(hint.get("missing_attributes", [])),
            prefix="missing_attribute",
        )
        _merge_name_set_features(
            features,
            action,
            params,
            name_set=set(hint.get("type_error_names", [])),
            prefix="type_error_name",
        )
    missing_keys = set(hint.get("missing_keys", []))
    if missing_keys:
        features["hint_has_missing_key"] = 1.0
        for key in missing_keys:
            features[f"hint_missing_key:{key}"] = 1.0
            features[f"action_hint_missing_key:{action}:{key}"] = 1.0
        params = candidate.get("params", {})
        if isinstance(params, dict):
            original = params.get("from")
            replacement = params.get("to")
            if isinstance(original, str) and original in missing_keys:
                features["hint_missing_key_matches_from"] = 1.0
                features[f"action_hint_missing_key_matches_from:{action}"] = 1.0
            if isinstance(replacement, str) and any(key in replacement for key in missing_keys):
                features["hint_missing_key_in_to"] = 1.0
                features[f"action_hint_missing_key_in_to:{action}"] = 1.0


def _merge_name_set_features(
    features: dict[str, float],
    action: str,
    params: Mapping[str, object],
    *,
    name_set: set[str],
    prefix: str,
) -> None:
    if not name_set:
        return
    features[f"hint_has_{prefix}"] = 1.0
    original = params.get("from")
    replacement = params.get("to")
    name = params.get("name")
    module = params.get("module")
    if isinstance(original, str) and original in name_set:
        features[f"hint_{prefix}_matches_from"] = 1.0
        features[f"action_hint_{prefix}_matches_from:{action}"] = 1.0
    if isinstance(replacement, str) and replacement in name_set:
        features[f"hint_{prefix}_matches_to"] = 1.0
        features[f"action_hint_{prefix}_matches_to:{action}"] = 1.0
    if isinstance(name, str) and name in name_set:
        features[f"hint_{prefix}_matches_import_name"] = 1.0
        features[f"action_hint_{prefix}_matches_import_name:{action}"] = 1.0
    if isinstance(module, str) and any(module == item or module.endswith(f".{item}") for item in name_set):
        features[f"hint_{prefix}_matches_module"] = 1.0
        features[f"action_hint_{prefix}_matches_module:{action}"] = 1.0


def _add_hint_token_overlap_features(
    features: dict[str, float],
    *,
    action: str,
    candidate_tokens: set[str],
    params: Mapping[str, object],
    hint_tokens: set[str],
) -> None:
    if not candidate_tokens or not hint_tokens:
        return
    overlap = candidate_tokens & hint_tokens
    if overlap:
        value = min(len(overlap), 8) / 8.0
        features["hint_candidate_token_overlap"] = value
        features[f"action_hint_candidate_token_overlap:{action}"] = value

    for key in ("from", "to", "name", "module"):
        value = params.get(key)
        if not isinstance(value, str):
            continue
        param_tokens = _tokens(value)
        param_overlap = param_tokens & hint_tokens
        if param_overlap:
            feature_value = min(len(param_overlap), 6) / 6.0
            features[f"hint_param_{key}_token_overlap"] = feature_value
            features[f"action_hint_param_{key}_token_overlap:{action}"] = feature_value


def _candidate_tokens(
    file_path: str,
    symbol: object,
    params: Mapping[str, object],
) -> set[str]:
    tokens = _tokens(file_path)
    if isinstance(symbol, str):
        tokens |= _tokens(symbol)
    for key in ("from", "to", "name", "module", "import", "replacement"):
        value = params.get(key)
        if isinstance(value, str):
            tokens |= _tokens(value)
    return tokens


def _hint_tokens(hints: list[object] | tuple[object, ...]) -> set[str]:
    tokens: set[str] = set()
    for hint in hints:
        for attr in (
            "nodeid",
            "summary",
            "exception_type",
            "function_names",
            "missing_names",
            "missing_attributes",
            "missing_modules",
            "missing_keys",
            "type_error_names",
            "assertion_diff_lines",
            "source_files",
        ):
            tokens |= _tokens_from_hint_value(getattr(hint, attr, None))
        for location in getattr(hint, "traceback_locations", []):
            tokens |= _tokens(getattr(location, "file_path", ""))
        for diagnostic in getattr(hint, "tool_diagnostics", []):
            tokens |= _tokens(getattr(diagnostic, "file_path", ""))
            tokens |= _tokens(getattr(diagnostic, "message", ""))
    return tokens


def _hint_record_tokens(hints: list[dict[str, object]]) -> set[str]:
    tokens: set[str] = set()
    for hint in hints:
        for key in (
            "nodeid",
            "summary",
            "exception_type",
            "function_names",
            "missing_names",
            "missing_attributes",
            "missing_modules",
            "missing_keys",
            "type_error_names",
            "assertion_diff_lines",
            "source_files",
        ):
            tokens |= _tokens_from_hint_value(hint.get(key))
        for location in hint.get("traceback_locations", []):
            if isinstance(location, dict):
                tokens |= _tokens(location.get("file_path"))
        for diagnostic in hint.get("tool_diagnostics", []):
            if isinstance(diagnostic, dict):
                tokens |= _tokens(diagnostic.get("file_path"))
                tokens |= _tokens(diagnostic.get("message"))
    return tokens


def _tokens_from_hint_value(value: object) -> set[str]:
    if isinstance(value, str):
        return _tokens(value)
    if isinstance(value, (set, list, tuple)):
        tokens: set[str] = set()
        for item in value:
            tokens |= _tokens_from_hint_value(item)
        return tokens
    return set()


def _tokens(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    tokens: set[str] = set()
    for match in TOKEN_RE.finditer(value):
        token = match.group(0)
        for part in re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", token).replace("_", " ").split():
            normalized = part.lower()
            if len(normalized) >= 3:
                tokens.add(normalized)
    return tokens


def _outcome_row_hints(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        hints = row.get("failure_hints")
        if isinstance(hints, list):
            return [hint for hint in hints if isinstance(hint, dict)]
    return []


def _update_weights(weights: dict[str, float], features: Mapping[str, float], scale: float) -> None:
    for name, value in features.items():
        weights[name] = weights.get(name, 0.0) + scale * value
        if abs(weights[name]) < 1e-12:
            del weights[name]


def _score_training_pairs(
    pairs: list[tuple[dict[str, float], dict[str, float]]],
    weights: Mapping[str, float],
    *,
    margin: float,
) -> tuple[int, int]:
    correct = 0
    margin_violations = 0
    for positive, negative in pairs:
        pos_score = score_features(positive, weights)
        neg_score = score_features(negative, weights)
        if pos_score > neg_score:
            correct += 1
        if pos_score <= neg_score + margin:
            margin_violations += 1
    return correct, margin_violations


def _normalize_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return default
