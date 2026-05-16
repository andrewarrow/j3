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
    mined_examples: int
    action_counts: dict[str, int]


def train_from_path(
    *,
    data_path: Path,
    out_dir: Path,
    embedding_dim: int = 256,
    max_examples: int = 500,
    transition_paths: list[Path] | None = None,
) -> TrainingResult:
    """Train the first prototype model from a Python repo path."""

    return train_from_paths(
        data_paths=[data_path],
        out_dir=out_dir,
        embedding_dim=embedding_dim,
        max_examples=max_examples,
        transition_paths=transition_paths,
    )


def train_from_paths(
    *,
    data_paths: list[Path],
    out_dir: Path,
    embedding_dim: int = 256,
    max_examples: int = 500,
    transition_paths: list[Path] | None = None,
) -> TrainingResult:
    """Train the first prototype model from one or more Python repo paths."""

    if embedding_dim < 8:
        raise ValueError("embedding_dim must be >= 8")
    if max_examples < 1:
        raise ValueError("max_examples must be >= 1")
    if not data_paths:
        raise ValueError("at least one data path is required")

    repo_roots = [path.expanduser().resolve() for path in data_paths]
    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    sources_by_repo = [(repo_root, iter_python_sources(repo_root)) for repo_root in repo_roots]
    transitions: list[SyntheticTransition] = []
    source_indexes = [0 for _ in sources_by_repo]
    while len(transitions) < max_examples:
        added_this_round = False
        for repo_index, (repo_root, sources) in enumerate(sources_by_repo):
            if len(transitions) >= max_examples:
                break
            source_index = source_indexes[repo_index]
            if source_index >= len(sources):
                continue

            source_indexes[repo_index] += 1
            remaining = max_examples - len(transitions)
            file_path = f"{repo_root.name}/{sources[source_index].relative_path}"
            examples = generate_transitions(
                file_path=file_path,
                source=sources[source_index].text,
                max_examples=min(remaining, 20),
            )
            transitions.extend(examples)
            added_this_round = added_this_round or bool(examples)

        if not added_this_round and all(
            source_indexes[index] >= len(sources)
            for index, (_, sources) in enumerate(sources_by_repo)
        ):
            break

    if not transitions:
        mined_preview = _load_mined_examples(transition_paths or [], limit=1)
        if not mined_preview:
            sources = ", ".join(str(root) for root in repo_roots)
            raise ValueError(f"no synthetic Python repair transitions found in {sources}")

    deltas_by_action: dict[str, list[list[float]]] = defaultdict(list)
    before_vectors: list[list[float]] = []
    after_vectors: list[list[float]] = []
    action_counts: Counter[str] = Counter()
    mined_count = 0

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

        for record in _load_mined_examples(transition_paths or [], limit=max_examples):
            before_source = str(record["before_source"])
            after_source = str(record["after_source"])
            before = embed_python_source(before_source, dim=embedding_dim)
            after = embed_python_source(after_source, dim=embedding_dim)
            delta = vector_delta(after, before)
            action_name = "git_transition"

            before_vectors.append(before)
            after_vectors.append(after)
            deltas_by_action[action_name].append(delta)
            action_counts[action_name] += 1
            mined_count += 1

            out_record = {
                "kind": "git_transition",
                "repo": record.get("repo"),
                "commit": record.get("commit"),
                "parent": record.get("parent"),
                "file_path": record.get("file_path"),
                "before_embedding": before,
                "after_embedding": after,
            }
            examples_file.write(json.dumps(out_record, sort_keys=True) + "\n")

    model = {
        "format": MODEL_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": [str(root) for root in repo_roots],
        "transition_sources": [str(path.expanduser().resolve()) for path in (transition_paths or [])],
        "feature_version": FEATURE_VERSION,
        "embedding_dim": embedding_dim,
        "examples": len(transitions) + mined_count,
        "synthetic_examples": len(transitions),
        "mined_examples": mined_count,
        "action_counts": dict(sorted(action_counts.items())),
        "before_centroid": mean_vector(before_vectors, dim=embedding_dim),
        "after_centroid": mean_vector(after_vectors, dim=embedding_dim),
        "action_delta_prototypes": {
            action: mean_vector(vectors, dim=embedding_dim)
            for action, vectors in sorted(deltas_by_action.items())
        },
    }

    metrics = {
        "sources": [str(root) for root in repo_roots],
        "output": str(output),
        "source_files": sum(len(sources) for _, sources in sources_by_repo),
        "synthetic_examples": len(transitions),
        "mined_examples": mined_count,
        "embedding_dim": embedding_dim,
        "max_examples": max_examples,
        "transition_sources": [str(path.expanduser().resolve()) for path in (transition_paths or [])],
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
        source_files=sum(len(sources) for _, sources in sources_by_repo),
        parsed_examples=len(transitions) + mined_count,
        mined_examples=mined_count,
        action_counts=dict(sorted(action_counts.items())),
    )


def _load_mined_examples(paths: list[Path], *, limit: int) -> list[dict[str, object]]:
    if limit < 1:
        return []

    examples: list[dict[str, object]] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved.is_dir():
            files = sorted(resolved.glob("*.jsonl"))
        else:
            files = [resolved]

        for file_path in files:
            if not file_path.exists():
                continue
            with file_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if len(examples) >= limit:
                        return examples
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if "before_source" in record and "after_source" in record:
                        examples.append(record)
    return examples
