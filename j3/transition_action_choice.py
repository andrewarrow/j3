"""Action-choice groups built from validated repair candidate outcomes.

Candidate outcome rows currently do not always carry an explicit repair plan
identifier. In that case this module groups by task and phase plus a stable
fallback identity derived from plan-level fields that are present in every row:
task family, source type, split, language, first passing index, passing count,
and source path when a JSONL path is supplied.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

from j3.features import FEATURE_VERSION as PYTHON_SOURCE_FEATURE_VERSION
from j3.features import embed_python_source


TRANSITION_ACTION_CHOICE_SCHEMA_VERSION = "transition-action-choice-v1"
DEFAULT_EMBEDDING_DIM = 256
MIN_EMBEDDING_DIM = 8


def load_jsonl_objects(path: Path) -> tuple[dict[str, object], ...]:
    """Load JSONL objects from a candidate outcome or action-choice file."""

    rows: list[dict[str, object]] = []
    with path.expanduser().resolve().open(encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_index} must be an object")
            rows.append(value)
    return tuple(rows)


def build_transition_action_choice_groups_jsonl(
    path: Path,
    *,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> tuple[dict[str, object], ...]:
    """Load candidate outcome JSONL rows and group them for action choice."""

    return build_transition_action_choice_groups(
        load_jsonl_objects(path),
        source_path=path,
        embedding_dim=embedding_dim,
    )


def build_transition_action_choice_groups(
    rows: Sequence[Mapping[str, object]],
    *,
    source_path: Path | None = None,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> tuple[dict[str, object], ...]:
    """Convert validated candidate outcome rows into action-choice groups."""

    if embedding_dim < MIN_EMBEDDING_DIM:
        raise ValueError(f"embedding_dim must be >= {MIN_EMBEDDING_DIM}")

    grouped_rows: dict[tuple[str, str, str], list[tuple[int, Mapping[str, object]]]] = {}
    group_records: dict[tuple[str, str, str], dict[str, object]] = {}
    for row_index, row in enumerate(rows, start=1):
        task = _required_str(row, "task", context="candidate_outcome")
        phase = _required_str(row, "phase", context="candidate_outcome")
        _positive_int(row.get("rank_index"), field="rank_index")
        passed = row.get("passed")
        if not isinstance(passed, bool):
            raise ValueError("candidate_outcome.passed must be a bool")

        repair_plan = _repair_plan_identity(row, source_path=source_path)
        key = (task, phase, str(repair_plan["repair_plan_identity"]))
        grouped_rows.setdefault(key, []).append((row_index, row))
        group_records.setdefault(
            key,
            {
                "task": task,
                "phase": phase,
                "task_family": row.get("task_family"),
                "source_type": row.get("source_type"),
                "split": row.get("split"),
                "language": row.get("language"),
                **repair_plan,
            },
        )

    groups: list[dict[str, object]] = []
    for key in sorted(grouped_rows):
        source_rows = sorted(
            grouped_rows[key],
            key=lambda item: (
                _positive_int(item[1].get("rank_index"), field="rank_index"),
                item[0],
            ),
        )
        group = _choice_group(
            group_records[key],
            source_rows,
            source_path=source_path,
            embedding_dim=embedding_dim,
        )
        validate_transition_action_choice_group(group)
        groups.append(group)
    return tuple(groups)


def write_transition_action_choice_jsonl(
    groups: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write validated action-choice groups as deterministic JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for group in groups:
            validate_transition_action_choice_group(group)
            handle.write(json.dumps(group, sort_keys=True) + "\n")
    return resolved


def load_transition_action_choice_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Load and validate ``transition-action-choice-v1`` JSONL groups."""

    groups = load_jsonl_objects(path)
    for group in groups:
        validate_transition_action_choice_group(group)
    return groups


def validate_transition_action_choice_group(group: Mapping[str, object]) -> None:
    """Validate the common ``transition-action-choice-v1`` surface."""

    if group.get("schema_version") != TRANSITION_ACTION_CHOICE_SCHEMA_VERSION:
        raise ValueError("action-choice group must use transition-action-choice-v1")
    _required_str(group, "id", context="action_choice")
    source = _mapping(group.get("source"), field="source")
    if source.get("kind") != "candidate_outcomes":
        raise ValueError("source.kind must be candidate_outcomes")
    row_indices = _int_list(source.get("row_indices"), field="source.row_indices")
    row_count = _nonnegative_int(source.get("row_count"), field="source.row_count")
    if len(row_indices) != row_count:
        raise ValueError("source.row_count must match source.row_indices")

    grouping = _mapping(group.get("grouping"), field="grouping")
    _required_str(grouping, "task", context="grouping")
    _required_str(grouping, "phase", context="grouping")
    _required_str(grouping, "repair_plan_identity", context="grouping")
    _required_str(grouping, "repair_plan_source", context="grouping")

    candidates = group.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a non-empty list")
    candidate_count = _positive_int(group.get("candidate_count"), field="candidate_count")
    if len(candidates) != candidate_count:
        raise ValueError("candidate_count must match candidates")
    validated_count = _positive_int(
        group.get("validated_candidate_count"),
        field="validated_candidate_count",
    )
    if validated_count != len(candidates):
        raise ValueError("validated_candidate_count must match candidates")

    ranks: list[int] = []
    passing_ranks: list[int] = []
    for candidate in candidates:
        candidate_record = _mapping(candidate, field="candidate")
        rank_index = _positive_int(
            candidate_record.get("rank_index"),
            field="rank_index",
        )
        ranks.append(rank_index)
        _optional_positive_int(
            candidate_record.get("first_passing_index"),
            field="candidate.first_passing_index",
        )
        _required_str(
            _mapping(candidate_record.get("action"), field="candidate.action"),
            "kind",
            context="candidate.action",
        )
        _mapping(
            candidate_record.get("target_context"),
            field="candidate.target_context",
        )
        _validate_source_context(
            _mapping(
                candidate_record.get("source_context"),
                field="candidate.source_context",
            )
        )
        _validate_candidate_after(
            _mapping(
                candidate_record.get("candidate_after"),
                field="candidate.candidate_after",
            )
        )
        validation = _mapping(
            candidate_record.get("validation"),
            field="candidate.validation",
        )
        if validation.get("validated") is not True:
            raise ValueError("candidate.validation.validated must be true")
        passed = validation.get("passed")
        if not isinstance(passed, bool):
            raise ValueError("candidate.validation.passed must be a bool")
        _required_str(validation, "status", context="candidate.validation")
        if passed:
            passing_ranks.append(rank_index)

    if ranks != sorted(ranks):
        raise ValueError("candidates must be sorted by rank_index")
    if len(set(ranks)) != len(ranks):
        raise ValueError("candidate rank_index values must be unique within a group")

    expected_first_pass = min(passing_ranks) if passing_ranks else None
    first_passing_index = group.get("first_passing_index")
    if first_passing_index != expected_first_pass:
        raise ValueError("first_passing_index must match passing candidates")
    if (
        _int_list(group.get("passing_candidate_ranks"), field="passing_candidate_ranks")
        != passing_ranks
    ):
        raise ValueError("passing_candidate_ranks must match candidates")
    hard_negative_ranks = _int_list(
        group.get("hard_negative_candidate_ranks"),
        field="hard_negative_candidate_ranks",
    )
    if hard_negative_ranks != [rank for rank in ranks if rank not in passing_ranks]:
        raise ValueError("hard_negative_candidate_ranks must match failed candidates")


def _choice_group(
    group_record: Mapping[str, object],
    source_rows: Sequence[tuple[int, Mapping[str, object]]],
    *,
    source_path: Path | None,
    embedding_dim: int,
) -> dict[str, object]:
    candidates = [
        _candidate_choice(
            row,
            source_row_index=row_index,
            embedding_dim=embedding_dim,
        )
        for row_index, row in source_rows
    ]
    passing_ranks: list[int] = []
    hard_negative_ranks: list[int] = []
    for candidate in candidates:
        rank_index = int(candidate["rank_index"])
        validation = _mapping(candidate["validation"], field="candidate.validation")
        if validation.get("passed") is True:
            passing_ranks.append(rank_index)
        elif validation.get("passed") is False:
            hard_negative_ranks.append(rank_index)
    first_passing_index = min(passing_ranks) if passing_ranks else None
    task = str(group_record["task"])
    phase = str(group_record["phase"])
    repair_plan_identity = str(group_record["repair_plan_identity"])

    return {
        "schema_version": TRANSITION_ACTION_CHOICE_SCHEMA_VERSION,
        "id": _group_id(task, phase, repair_plan_identity),
        "source": {
            "kind": "candidate_outcomes",
            "path": str(source_path.expanduser().resolve()) if source_path else None,
            "row_indices": [row_index for row_index, _row in source_rows],
            "row_count": len(source_rows),
        },
        "grouping": _json_copy(group_record),
        "candidate_count": len(candidates),
        "validated_candidate_count": len(candidates),
        "first_passing_index": first_passing_index,
        "passing_candidate_ranks": passing_ranks,
        "hard_negative_candidate_ranks": hard_negative_ranks,
        "validation_summary": {
            "solved": bool(passing_ranks),
            "passing_candidates": len(passing_ranks),
            "failed_candidates": len(hard_negative_ranks),
            "first_passing_index": first_passing_index,
        },
        "candidates": candidates,
    }


def _candidate_choice(
    row: Mapping[str, object],
    *,
    source_row_index: int,
    embedding_dim: int,
) -> dict[str, object]:
    rank_index = _positive_int(row.get("rank_index"), field="rank_index")
    passed = row.get("passed")
    if not isinstance(passed, bool):
        raise ValueError("candidate_outcome.passed must be a bool")
    action = _candidate_action(row, rank_index=rank_index)
    return {
        "source_row_index": source_row_index,
        "rank_index": rank_index,
        "first_passing_index": _optional_positive_int(
            row.get("first_passing_index"),
            field="first_passing_index",
        ),
        "is_first_pass": row.get("is_first_pass") is True,
        "action": action,
        "target_context": _json_copy(_mapping_or_empty(row.get("target_context"))),
        "source_context": _source_context(row, embedding_dim=embedding_dim),
        "candidate_after": _candidate_after(row, embedding_dim=embedding_dim),
        "validation": {
            "validated": True,
            "status": "passed" if passed else "failed",
            "passed": passed,
            "preferred": row.get("preferred") is True,
            "failure_hints": _json_copy(_list_or_empty(row.get("failure_hints"))),
        },
        "scores": {
            "model_score": row.get("model_score"),
            "failure_hint_score": row.get("failure_hint_score"),
            "ranker_score": row.get("ranker_score"),
        },
        "relations": {
            "equivalent_candidate_ranks": _int_list_or_empty(
                row.get("equivalent_candidate_ranks")
            ),
            "overlapping_candidate_ranks": _int_list_or_empty(
                row.get("overlapping_candidate_ranks")
            ),
            "equivalent_passing_candidate_ranks": _int_list_or_empty(
                row.get("equivalent_passing_candidate_ranks")
            ),
            "overlapping_passing_candidate_ranks": _int_list_or_empty(
                row.get("overlapping_passing_candidate_ranks")
            ),
        },
    }


def _candidate_action(row: Mapping[str, object], *, rank_index: int) -> dict[str, object]:
    action_kind = _required_str(row, "action", context="candidate_outcome")
    return {
        "kind": action_kind,
        "file_path": row.get("file_path"),
        "symbol": row.get("symbol"),
        "start_line": row.get("start_line"),
        "end_line": row.get("end_line"),
        "node_kind": row.get("node_kind"),
        "params": _json_copy(_mapping_or_empty(row.get("params"))),
        "reason": row.get("reason"),
        "rank_index": rank_index,
        "source_type": row.get("source_type"),
    }


def _source_context(
    row: Mapping[str, object],
    *,
    embedding_dim: int,
) -> dict[str, object]:
    repo_before = row.get("repo_before")
    if isinstance(repo_before, Mapping):
        embedding = _embedding_from_repo_record(repo_before)
        return {
            "available": True,
            "kind": "repo_before",
            "repo_before": _json_copy(repo_before),
            "source": None,
            "source_sha256": None,
            "embedding_available": embedding is not None,
            "embedding_kind": "repo_embedding" if embedding is not None else None,
            "embedding_dim": len(embedding) if embedding is not None else None,
            "embedding": embedding,
        }

    source_field, source = _source_text(row, ("before_source", "original_source"))
    if source is not None:
        return {
            "available": True,
            "kind": "file_before_source",
            "field": source_field,
            "source": source,
            "source_sha256": _sha256_text(source),
            "byte_count": _utf8_len(source),
            "embedding_available": True,
            "embedding_kind": PYTHON_SOURCE_FEATURE_VERSION,
            "embedding_dim": embedding_dim,
            "embedding": embed_python_source(source, dim=embedding_dim),
        }

    embedding = _first_embedding(
        row,
        ("source_embedding", "before_embedding", "candidate_context_embedding"),
    )
    if embedding is not None:
        return {
            "available": True,
            "kind": "candidate_context_embedding",
            "source": None,
            "source_sha256": None,
            "embedding_available": True,
            "embedding_kind": row.get("embedding_kind"),
            "embedding_dim": len(embedding),
            "embedding": embedding,
        }

    record = {
        "task": row.get("task"),
        "task_family": row.get("task_family"),
        "source_type": row.get("source_type"),
        "split": row.get("split"),
        "phase": row.get("phase"),
        "target_context": _mapping_or_empty(row.get("target_context")),
        "failure_hints": _list_or_empty(row.get("failure_hints")),
    }
    return {
        "available": True,
        "kind": "candidate_context",
        "record": _json_copy(record),
        "record_checksum": _checksum_json(record),
        "source": None,
        "source_sha256": None,
        "embedding_available": False,
        "embedding_kind": None,
        "embedding_dim": None,
        "embedding": None,
    }


def _candidate_after(
    row: Mapping[str, object],
    *,
    embedding_dim: int,
) -> dict[str, object]:
    repo_after = row.get("repo_after")
    if isinstance(repo_after, Mapping):
        embedding = _embedding_from_repo_record(repo_after)
        return {
            "available": True,
            "kind": "repo_after",
            "repo_after": _json_copy(repo_after),
            "source": None,
            "source_sha256": None,
            "embedding_available": embedding is not None,
            "embedding_kind": "repo_embedding" if embedding is not None else None,
            "embedding_dim": len(embedding) if embedding is not None else None,
            "embedding": embedding,
        }

    source_field, source = _source_text(row, ("patched_source", "after_source"))
    if source is not None:
        return {
            "available": True,
            "kind": "file_after_source",
            "field": source_field,
            "source": source,
            "source_sha256": _sha256_text(source),
            "byte_count": _utf8_len(source),
            "embedding_available": True,
            "embedding_kind": PYTHON_SOURCE_FEATURE_VERSION,
            "embedding_dim": embedding_dim,
            "embedding": embed_python_source(source, dim=embedding_dim),
        }

    embedding = _first_embedding(
        row,
        (
            "patched_source_embedding",
            "after_embedding",
            "repo_after_embedding",
            "candidate_repo_after_embedding",
        ),
    )
    if embedding is not None:
        return {
            "available": True,
            "kind": "candidate_after_embedding",
            "source": None,
            "source_sha256": None,
            "embedding_available": True,
            "embedding_kind": row.get("embedding_kind"),
            "embedding_dim": len(embedding),
            "embedding": embedding,
        }

    return {
        "available": False,
        "kind": "unavailable",
        "source": None,
        "source_sha256": None,
        "embedding_available": False,
        "embedding_kind": None,
        "embedding_dim": None,
        "embedding": None,
        "reason": "candidate outcome row has no patched source or repo-after embedding",
    }


def _repair_plan_identity(
    row: Mapping[str, object],
    *,
    source_path: Path | None,
) -> dict[str, object]:
    plan_id = _optional_str(row.get("repair_plan_id")) or _optional_str(row.get("plan_id"))
    if plan_id is not None:
        return {
            "repair_plan_identity": plan_id,
            "repair_plan_source": "explicit_field",
            "repair_plan": None,
            "fallback_fields": None,
        }

    for field in ("repair_plan", "patch_plan"):
        plan = row.get(field)
        if isinstance(plan, Mapping):
            plan_record = _json_copy(plan)
            return {
                "repair_plan_identity": f"{field}:{_checksum_json(plan_record)[:16]}",
                "repair_plan_source": f"explicit_{field}",
                "repair_plan": plan_record,
                "fallback_fields": None,
            }

    fallback_fields = {
        "task": row.get("task"),
        "phase": row.get("phase"),
        "task_family": row.get("task_family"),
        "source_type": row.get("source_type"),
        "split": row.get("split"),
        "language": row.get("language"),
        "first_passing_index": row.get("first_passing_index"),
        "passing_candidates": row.get("passing_candidates"),
        "source_path": str(source_path.expanduser().resolve()) if source_path else None,
    }
    return {
        "repair_plan_identity": f"fallback:{_checksum_json(fallback_fields)[:16]}",
        "repair_plan_source": "fallback_row_fields",
        "repair_plan": None,
        "fallback_fields": fallback_fields,
    }


def _embedding_from_repo_record(record: Mapping[str, object]) -> list[float] | None:
    state = record.get("state")
    if isinstance(state, Mapping):
        embedding = _float_list_or_none(state.get("repo_embedding"))
        if embedding:
            return embedding
    embedding = _float_list_or_none(record.get("repo_embedding"))
    if embedding:
        return embedding
    embedding = _float_list_or_none(record.get("embedding"))
    if embedding:
        return embedding
    return None


def _validate_source_context(record: Mapping[str, object]) -> None:
    available = record.get("available")
    if not isinstance(available, bool):
        raise ValueError("source_context.available must be a bool")
    _required_str(record, "kind", context="source_context")
    _validate_optional_embedding(record, label="source_context")


def _validate_candidate_after(record: Mapping[str, object]) -> None:
    available = record.get("available")
    if not isinstance(available, bool):
        raise ValueError("candidate_after.available must be a bool")
    _required_str(record, "kind", context="candidate_after")
    _validate_optional_embedding(record, label="candidate_after")
    if not available:
        if record.get("kind") != "unavailable":
            raise ValueError("unavailable candidate_after must use kind=unavailable")
        if record.get("embedding") is not None:
            raise ValueError("unavailable candidate_after.embedding must be null")


def _validate_optional_embedding(record: Mapping[str, object], *, label: str) -> None:
    embedding_available = record.get("embedding_available")
    if not isinstance(embedding_available, bool):
        raise ValueError(f"{label}.embedding_available must be a bool")
    embedding = record.get("embedding")
    embedding_dim = record.get("embedding_dim")
    if not embedding_available:
        if embedding is not None:
            raise ValueError(f"{label}.embedding must be null when unavailable")
        if embedding_dim is not None:
            raise ValueError(f"{label}.embedding_dim must be null when unavailable")
        return
    vector = _float_list(embedding)
    if not isinstance(embedding_dim, int) or isinstance(embedding_dim, bool):
        raise ValueError(f"{label}.embedding_dim must be an int")
    if len(vector) != embedding_dim:
        raise ValueError(f"{label}.embedding length must match embedding_dim")


def _source_text(
    row: Mapping[str, object],
    fields: Sequence[str],
) -> tuple[str | None, str | None]:
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            return field, value
    return None, None


def _first_embedding(
    row: Mapping[str, object],
    fields: Sequence[str],
) -> list[float] | None:
    for field in fields:
        embedding = _float_list_or_none(row.get(field))
        if embedding is not None:
            return embedding
    return None


def _group_id(task: str, phase: str, repair_plan_identity: str) -> str:
    return "transition-action-choice-" + _slug(
        f"{task}:{phase}:{repair_plan_identity}"
    )[:96]


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _mapping_or_empty(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _list_or_empty(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    return []


def _required_str(row: Mapping[str, object], field: str, *, context: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}.{field} must be a non-empty string")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _positive_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be a positive int")
    return value


def _optional_positive_int(value: object, *, field: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, field=field)


def _nonnegative_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative int")
    return value


def _int_list(value: object, *, field: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{field} values must be ints")
        result.append(item)
    return result


def _int_list_or_empty(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, int) and not isinstance(item, bool)
    ]


def _float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        raise ValueError("embedding must be a list")
    result: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise ValueError("embedding values must be numeric")
        result.append(float(item))
    return result


def _float_list_or_none(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    return _float_list(value)


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _checksum_json(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _slug(value: str) -> str:
    chars = [char.lower() if char.isalnum() else "-" for char in value]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug or _sha256_text(value)[:12]
