"""Small code-state encoder used by the first local trainer."""

from __future__ import annotations

import ast
import hashlib
import math
import warnings
from collections import Counter


FEATURE_VERSION = "ast-hash-v1"


def embed_python_source(text: str, *, dim: int) -> list[float]:
    """Embed Python source into a deterministic, normalized feature vector."""

    if dim < 8:
        raise ValueError("dim must be >= 8")

    features = Counter[str]()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError:
        features["syntax:error"] += 1
        return _normalize(_hash_features(features, dim))

    for node in ast.walk(tree):
        node_name = type(node).__name__
        features[f"node:{node_name}"] += 1

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            features["def:function"] += 1
            features[f"args:{len(node.args.args)}"] += 1
        elif isinstance(node, ast.ClassDef):
            features["def:class"] += 1
            features[f"bases:{len(node.bases)}"] += 1
        elif isinstance(node, ast.Call):
            features[f"call_args:{len(node.args)}"] += 1
            call_name = _call_name(node.func)
            if call_name:
                features[f"call:{call_name}"] += 1
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                features[f"compare:{type(op).__name__}"] += 1
        elif isinstance(node, ast.BoolOp):
            features[f"boolop:{type(node.op).__name__}"] += 1
        elif isinstance(node, ast.BinOp):
            features[f"binop:{type(node.op).__name__}"] += 1
        elif isinstance(node, ast.UnaryOp):
            features[f"unary:{type(node.op).__name__}"] += 1
        elif isinstance(node, ast.Constant):
            features[f"constant:{type(node.value).__name__}"] += 1

    return _normalize(_hash_features(features, dim))


def vector_delta(after: list[float], before: list[float]) -> list[float]:
    if len(after) != len(before):
        raise ValueError("vectors must have the same dimension")
    return [a - b for a, b in zip(after, before, strict=True)]


def mean_vector(vectors: list[list[float]], *, dim: int) -> list[float]:
    if not vectors:
        return [0.0] * dim

    total = [0.0] * dim
    for vector in vectors:
        if len(vector) != dim:
            raise ValueError("all vectors must match dim")
        for index, value in enumerate(vector):
            total[index] += value
    return [value / len(vectors) for value in total]


def _hash_features(features: Counter[str], dim: int) -> list[float]:
    vector = [0.0] * dim
    for name, count in features.items():
        digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign * math.log1p(count)
    return vector


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return vector
    return [value / magnitude for value in vector]


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
