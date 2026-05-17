"""Compact AST before/after deltas for candidate metadata."""

from __future__ import annotations

import ast
import re
import warnings
from collections import Counter
from collections.abc import Mapping


MAX_DELTA_FEATURES = 24


def python_ast_delta_metadata(before: str, after: str) -> dict[str, object]:
    """Return compact AST feature deltas between two Python source strings."""

    before_features = _python_ast_features(before)
    after_features = _python_ast_features(after)
    if before_features is None or after_features is None:
        return {
            "ast_parse_ok": False,
            "ast_delta_added_features": {},
            "ast_delta_removed_features": {},
            "ast_delta_added_count": 0,
            "ast_delta_removed_count": 0,
            "ast_delta_net_count": 0,
        }

    added = +(after_features - before_features)
    removed = +(before_features - after_features)
    added_count = sum(added.values())
    removed_count = sum(removed.values())
    return {
        "ast_parse_ok": True,
        "ast_delta_added_features": _top_delta_features(added),
        "ast_delta_removed_features": _top_delta_features(removed),
        "ast_delta_added_count": added_count,
        "ast_delta_removed_count": removed_count,
        "ast_delta_net_count": sum(after_features.values()) - sum(before_features.values()),
    }


def ast_delta_feature_map(metadata: Mapping[str, object]) -> dict[str, float]:
    """Convert serialized AST delta metadata into ranker features."""

    features: dict[str, float] = {}
    parse_ok = metadata.get("ast_parse_ok")
    if parse_ok is True:
        features["ast_parse_ok"] = 1.0
    elif parse_ok is False:
        features["ast_parse_error"] = 1.0

    added_count = _int_value(metadata.get("ast_delta_added_count"), default=0)
    removed_count = _int_value(metadata.get("ast_delta_removed_count"), default=0)
    net_count = _int_value(metadata.get("ast_delta_net_count"), default=0)
    if added_count > 0:
        features[f"ast_delta_added_count:{_count_bucket(added_count)}"] = 1.0
        features["ast_delta_added_count_scaled"] = min(added_count, 20) / 20.0
    if removed_count > 0:
        features[f"ast_delta_removed_count:{_count_bucket(removed_count)}"] = 1.0
        features["ast_delta_removed_count_scaled"] = min(removed_count, 20) / 20.0
    if net_count > 0:
        features["ast_delta_net_count:increase"] = 1.0
    elif net_count < 0:
        features["ast_delta_net_count:decrease"] = 1.0
    elif parse_ok is True:
        features["ast_delta_net_count:same"] = 1.0

    for direction in ("added", "removed"):
        key = f"ast_delta_{direction}_features"
        value = metadata.get(key)
        if not isinstance(value, Mapping):
            continue
        for token, count in sorted(value.items()):
            feature_name = str(token)
            if not feature_name:
                continue
            numeric_count = _int_value(count, default=0)
            if numeric_count <= 0:
                continue
            features[f"ast_delta_{direction}:{feature_name}"] = 1.0
            features[f"ast_delta_{direction}_count:{feature_name}"] = min(numeric_count, 4) / 4.0
    return features


def _python_ast_features(source: str) -> Counter[str] | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError:
        return None

    features = Counter[str]()
    for node in ast.walk(tree):
        node_name = type(node).__name__
        features[f"node:{node_name}"] += 1
        if isinstance(node, ast.Compare):
            for op in node.ops:
                features[f"cmpop:{type(op).__name__}"] += 1
        elif isinstance(node, ast.BoolOp):
            features[f"boolop:{type(node.op).__name__}"] += 1
        elif isinstance(node, ast.BinOp):
            features[f"binop:{type(node.op).__name__}"] += 1
        elif isinstance(node, ast.UnaryOp):
            features[f"unary:{type(node.op).__name__}"] += 1
        elif isinstance(node, ast.Constant):
            features[f"constant_type:{type(node.value).__name__}"] += 1
            literal = _literal_token(node.value)
            if literal is not None:
                features[f"literal:{literal}"] += 1
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if call_name:
                features[f"call:{call_name}"] += 1
        elif isinstance(node, ast.Attribute):
            features[f"attr:{node.attr}"] += 1
        elif isinstance(node, ast.Name):
            features[f"name:{node.id}"] += 1
        elif isinstance(node, ast.Dict):
            _add_dict_features(features, node)
    return features


def _add_dict_features(features: Counter[str], node: ast.Dict) -> None:
    for key_node, value_node in zip(node.keys, node.values, strict=True):
        key = _constant_value(key_node)
        if key is None:
            continue
        key_token = _literal_token(key)
        if key_token is None:
            continue
        features[f"dict_key:{key_token}"] += 1
        value = _constant_value(value_node)
        value_token = _literal_token(value)
        if value_token is not None:
            features[f"dict_value_for_key:{key_token}:{value_token}"] += 1


def _constant_value(node: ast.AST | None) -> object | None:
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _literal_token(value: object) -> str | None:
    if isinstance(value, str):
        normalized = re.sub(r"\s+", "_", value.strip().lower())
        normalized = re.sub(r"[^a-z0-9_./:+-]+", "", normalized)
        if not normalized:
            return "str:<empty>"
        return f"str:{normalized[:80]}"
    if isinstance(value, bool):
        return f"bool:{value}"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"number:{value:.12g}"
    if value is None:
        return "none"
    return None


def _top_delta_features(counter: Counter[str]) -> dict[str, int]:
    return dict(counter.most_common(MAX_DELTA_FEATURES))


def _count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 3:
        return "2_3"
    if value <= 7:
        return "4_7"
    return "8_plus"


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return default
