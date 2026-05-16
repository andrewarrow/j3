"""Prototype local training for j3."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from features import FEATURE_VERSION, embed_python_source, mean_vector, vector_delta
from repo import iter_python_sources
from synth import SyntheticTransition, generate_transitions


MODEL_FORMAT = "j3.prototype-jepa.v1"


@dataclass(frozen=True, slots=True)
class TrainingResult:
    out_dir: Path
    model_path: Path
    metrics_path: Path
    examples_path: Path
    source_files: int
    parsed_examples: int
    action_counts: dict[str, int]


def train_from_path(
    *,
    data_path: Path,
    out_dir: Path,
    embedding_dim: int = 256,
    max_examples: int = 500,
) -> TrainingResult:
    """Train the first prototype model from a Python repo path."""

    if embedding_dim < 8:
        raise ValueError("embedding_dim must be >= 8")
    if max_examples < 1:
        raise ValueError("max_examples must be >= 1")

    repo_root = data_path.expanduser().resolve()
    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    sources = iter_python_sources(repo_root)
    transitions: list[SyntheticTransition] = []
    for source in sources:
        remaining = max_examples - len(transitions)
        if remaining <= 0:
            break
        transitions.extend(
            generate_transitions(
                file_path=source.relative_path,
                source=source.text,
                max_examples=min(remaining, 20),
            )
        )

    if not transitions:
        raise ValueError(f"no synthetic Python repair transitions found in {repo_root}")

    deltas_by_action: dict[str, list[list[float]]] = defaultdict(list)
    before_vectors: list[list[float]] = []
    after_vectors: list[list[float]] = []
    action_counts: Counter[str] = Counter()

    examples_path = output / "examples.jsonl"
    with examples_path.open("w", encoding="utf-8") as examples_file:
        for transition in transitions:
            before = embed_python_source(transition.broken_source, dim=embedding_dim)
            after = embed_python_source(transition.clean_source, dim=embedding_dim)
            delta = vector_delta(after, before)
            action_name = transition.repair_action.kind.value

            before_vectors.append(before)
            after_vectors.append(after)
            deltas_by_action[action_name].append(delta)
            action_counts[action_name] += 1

            record = transition.to_record()
            record["before_embedding"] = before
            record["after_embedding"] = after
            examples_file.write(json.dumps(record, sort_keys=True) + "\n")

    model = {
        "format": MODEL_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(repo_root),
        "feature_version": FEATURE_VERSION,
        "embedding_dim": embedding_dim,
        "examples": len(transitions),
        "action_counts": dict(sorted(action_counts.items())),
        "before_centroid": mean_vector(before_vectors, dim=embedding_dim),
        "after_centroid": mean_vector(after_vectors, dim=embedding_dim),
        "action_delta_prototypes": {
            action: mean_vector(vectors, dim=embedding_dim)
            for action, vectors in sorted(deltas_by_action.items())
        },
    }

    metrics = {
        "source": str(repo_root),
        "output": str(output),
        "source_files": len(sources),
        "synthetic_examples": len(transitions),
        "embedding_dim": embedding_dim,
        "max_examples": max_examples,
        "action_counts": dict(sorted(action_counts.items())),
        "artifacts": {
            "model": "model.json",
            "metrics": "metrics.json",
            "examples": "examples.jsonl",
        },
    }

    model_path = output / "model.json"
    metrics_path = output / "metrics.json"
    model_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return TrainingResult(
        out_dir=output,
        model_path=model_path,
        metrics_path=metrics_path,
        examples_path=examples_path,
        source_files=len(sources),
        parsed_examples=len(transitions),
        action_counts=dict(sorted(action_counts.items())),
    )
