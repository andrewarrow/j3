"""Normalized transition benchmark rows for local JEPA action selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

from j3.features import FEATURE_VERSION as PYTHON_SOURCE_FEATURE_VERSION
from j3.features import embed_python_source


TRANSITION_BENCH_SCHEMA_VERSION = "transition-bench-v1"
SOURCE_PROMPT_REPO_TRANSITION = "prompt_repo_transition"
SOURCE_MINED_GIT_TRANSITION = "mined_git_transition"
SOURCE_CANDIDATE_OUTCOME = "candidate_outcome"
SUPPORTED_SOURCE_KINDS = {
    SOURCE_PROMPT_REPO_TRANSITION,
    SOURCE_MINED_GIT_TRANSITION,
    SOURCE_CANDIDATE_OUTCOME,
}
HOSTED_LLM_API_TOKENS = 0
HOSTED_REPO_CONTEXT_BYTES = 0
DEFAULT_EMBEDDING_DIM = 256
MIN_EMBEDDING_DIM = 8


@dataclass(frozen=True)
class TransitionBenchNormalizationResult:
    """Rows plus structured accounting for skipped source records."""

    rows: tuple[dict[str, object], ...]
    skipped_rows: tuple[dict[str, object], ...]
    source_kind: str
    source_path: str | None
    input_row_count: int


def load_jsonl_objects(path: Path) -> tuple[dict[str, object], ...]:
    """Load JSONL objects from a source or bench fixture."""

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


def normalize_transition_bench_jsonl(
    path: Path,
    *,
    source_kind: str,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> tuple[dict[str, object], ...]:
    """Load source JSONL rows and normalize them into transition-bench rows."""

    return normalize_transition_bench_jsonl_with_report(
        path,
        source_kind=source_kind,
        embedding_dim=embedding_dim,
    ).rows


def normalize_transition_bench_jsonl_with_report(
    path: Path,
    *,
    source_kind: str,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> TransitionBenchNormalizationResult:
    """Load and normalize source JSONL rows with skipped-row accounting."""

    return normalize_transition_bench_rows_with_report(
        load_jsonl_objects(path),
        source_kind=source_kind,
        source_path=path,
        embedding_dim=embedding_dim,
    )


def normalize_transition_bench_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    source_kind: str,
    source_path: Path | None = None,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> tuple[dict[str, object], ...]:
    """Normalize one supported source row shape into transition-bench rows."""

    return normalize_transition_bench_rows_with_report(
        rows,
        source_kind=source_kind,
        source_path=source_path,
        embedding_dim=embedding_dim,
    ).rows


def normalize_transition_bench_rows_with_report(
    rows: Sequence[Mapping[str, object]],
    *,
    source_kind: str,
    source_path: Path | None = None,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> TransitionBenchNormalizationResult:
    """Normalize supported source rows and report skipped invalid source records."""

    if source_kind not in SUPPORTED_SOURCE_KINDS:
        raise ValueError(f"unsupported transition bench source kind {source_kind!r}")
    if embedding_dim < MIN_EMBEDDING_DIM:
        raise ValueError(f"embedding_dim must be >= {MIN_EMBEDDING_DIM}")

    normalized: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        if source_kind == SOURCE_PROMPT_REPO_TRANSITION:
            bench_row = normalize_prompt_repo_transition_row(
                row,
                index=index,
                source_path=source_path,
            )
        elif source_kind == SOURCE_MINED_GIT_TRANSITION:
            skip_record = _empty_mined_source_skip_record(
                row,
                index=index,
                source_kind=source_kind,
                source_path=source_path,
            )
            if skip_record is not None:
                skipped_rows.append(skip_record)
                continue
            bench_row = normalize_mined_git_transition_row(
                row,
                index=index,
                source_path=source_path,
                embedding_dim=embedding_dim,
            )
        else:
            bench_row = normalize_candidate_outcome_row(
                row,
                index=index,
                source_path=source_path,
            )
        validate_transition_bench_row(bench_row)
        normalized.append(bench_row)
    return TransitionBenchNormalizationResult(
        rows=tuple(normalized),
        skipped_rows=tuple(skipped_rows),
        source_kind=source_kind,
        source_path=_resolved_source_path(source_path),
        input_row_count=len(rows),
    )


def normalize_prompt_repo_transition_row(
    row: Mapping[str, object],
    *,
    index: int,
    source_path: Path | None = None,
) -> dict[str, object]:
    """Normalize a ``prompt-repo-transition-v1`` row."""

    if row.get("schema_version") != "prompt-repo-transition-v1":
        raise ValueError("prompt repo transition source row must use prompt-repo-transition-v1")

    row_id = _optional_str(row.get("id")) or f"prompt-repo-transition-{index:04d}"
    source = _source_record(
        kind=SOURCE_PROMPT_REPO_TRANSITION,
        row_index=index,
        source_path=source_path,
        row_id=row_id,
        schema_version=_optional_str(row.get("schema_version")),
    )
    source_outcome = _mapping(row.get("source_outcome"), field="source_outcome")
    prompt_context = _mapping(row.get("prompt_context"), field="prompt_context")
    repo_before = _mapping(row.get("repo_before"), field="repo_before")
    repo_after = _mapping(row.get("repo_after"), field="repo_after")
    structured_action = _mapping(row.get("structured_action"), field="structured_action")
    outcome = _mapping(row.get("outcome"), field="outcome")
    validation = _mapping(row.get("validation"), field="validation")
    cost = _mapping(row.get("cost"), field="cost")

    before_state = _mapping(repo_before.get("state"), field="repo_before.state")
    after_state = _mapping(repo_after.get("state"), field="repo_after.state")
    before_embedding = _repo_embedding(before_state, field="repo_before.state")
    after_embedding = _repo_embedding(after_state, field="repo_after.state")
    action_kind = _required_str(structured_action, "kind", context="structured_action")

    bench = {
        "schema_version": TRANSITION_BENCH_SCHEMA_VERSION,
        "id": _bench_id(SOURCE_PROMPT_REPO_TRANSITION, index, row_id),
        "source": source,
        "identity": {
            "source_record_kind": source_outcome.get("record_kind"),
            "source_outcome_row_id": source_outcome.get("outcome_row_id"),
            "source_outcome_row_index": source_outcome.get("outcome_row_index"),
        },
        "before": {
            "kind": "repo_state",
            "state_checksum": repo_before.get("state_checksum"),
            "state": _json_copy(before_state),
            "embedding_kind": "repo_embedding",
            "embedding_dim": len(before_embedding),
            "embedding": before_embedding,
        },
        "context": {
            "kind": "prompt_context",
            "prompt": prompt_context.get("prompt"),
            "embedding_dim": prompt_context.get("embedding_dim"),
            "embedding_checksum": prompt_context.get("embedding_checksum"),
            "embedding": _float_list(prompt_context.get("embedding", [])),
        },
        "action": {
            "kind": action_kind,
            "structured_action": _json_copy(structured_action),
        },
        "target": {
            "kind": "repo_after_embedding",
            "outcome_kind": outcome.get("kind"),
            "state_kind": repo_after.get("kind"),
            "state_checksum": repo_after.get("state_checksum"),
            "state": _json_copy(after_state),
            "embedding_kind": "repo_embedding",
            "embedding_dim": len(after_embedding),
            "embedding": after_embedding,
        },
        "validation": _validation_record(
            available=True,
            status=_optional_str(validation.get("status")),
            passed=_passed_from_validation(validation),
            details=validation,
        ),
        "cost": _cost_record(
            cost,
            before_bytes=_repo_python_bytes(before_state),
            after_bytes=_repo_python_bytes(after_state),
        ),
    }
    return bench


def normalize_mined_git_transition_row(
    row: Mapping[str, object],
    *,
    index: int,
    source_path: Path | None = None,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
) -> dict[str, object]:
    """Normalize a mined git before/after source transition row."""

    if row.get("kind") != "git_transition":
        raise ValueError("mined source row must have kind='git_transition'")
    before_source = _required_str(row, "before_source", context="git_transition")
    after_source = _required_str(row, "after_source", context="git_transition")
    file_path = _required_str(row, "file_path", context="git_transition")
    row_id = _git_row_id(row, index=index)
    diff = _optional_str(row.get("diff")) or ""
    before_embedding = embed_python_source(before_source, dim=embedding_dim)
    after_embedding = embed_python_source(after_source, dim=embedding_dim)

    return {
        "schema_version": TRANSITION_BENCH_SCHEMA_VERSION,
        "id": _bench_id(SOURCE_MINED_GIT_TRANSITION, index, row_id),
        "source": _source_record(
            kind=SOURCE_MINED_GIT_TRANSITION,
            row_index=index,
            source_path=source_path,
            row_id=row_id,
            schema_version=None,
        ),
        "identity": {
            "repo": row.get("repo"),
            "repo_path": row.get("repo_path"),
            "commit": row.get("commit"),
            "parent": row.get("parent"),
            "file_path": file_path,
        },
        "before": {
            "kind": "file_source",
            "file_path": file_path,
            "source": before_source,
            "source_sha256": _sha256_text(before_source),
            "byte_count": _utf8_len(before_source),
            "embedding_kind": PYTHON_SOURCE_FEATURE_VERSION,
            "embedding_dim": embedding_dim,
            "embedding": before_embedding,
        },
        "context": {
            "kind": "git_diff",
            "diff": diff,
            "diff_sha256": _sha256_text(diff),
            "byte_count": _utf8_len(diff),
        },
        "action": {
            "kind": "git_transition",
            "structured_action": {
                "kind": "git_transition",
                "commit": row.get("commit"),
                "parent": row.get("parent"),
                "file_path": file_path,
            },
        },
        "target": {
            "kind": "file_after_embedding",
            "file_path": file_path,
            "source": after_source,
            "source_sha256": _sha256_text(after_source),
            "byte_count": _utf8_len(after_source),
            "embedding_kind": PYTHON_SOURCE_FEATURE_VERSION,
            "embedding_dim": embedding_dim,
            "embedding": after_embedding,
        },
        "validation": _validation_record(
            available=False,
            status=None,
            passed=None,
            details={},
        ),
        "cost": _cost_record(
            {},
            before_bytes=_utf8_len(before_source),
            after_bytes=_utf8_len(after_source),
            diff_bytes=_utf8_len(diff),
            validation_command_count=0,
        ),
    }


def normalize_candidate_outcome_row(
    row: Mapping[str, object],
    *,
    index: int,
    source_path: Path | None = None,
) -> dict[str, object]:
    """Normalize one repair candidate outcome row."""

    task = _required_str(row, "task", context="candidate_outcome")
    phase = _required_str(row, "phase", context="candidate_outcome")
    action_kind = _required_str(row, "action", context="candidate_outcome")
    rank_index = _positive_int(row.get("rank_index"), field="rank_index")
    passed = row.get("passed")
    if not isinstance(passed, bool):
        raise ValueError("candidate_outcome.passed must be a bool")
    row_id = f"{task}:{phase}:{rank_index}"
    target_context = _mapping_or_empty(row.get("target_context"))
    failure_hints = _list_or_empty(row.get("failure_hints"))

    candidate_action = {
        "kind": action_kind,
        "file_path": row.get("file_path"),
        "symbol": row.get("symbol"),
        "start_line": row.get("start_line"),
        "end_line": row.get("end_line"),
        "node_kind": row.get("node_kind"),
        "params": _mapping_or_empty(row.get("params")),
        "reason": row.get("reason"),
        "rank_index": rank_index,
        "model_score": row.get("model_score"),
        "failure_hint_score": row.get("failure_hint_score"),
        "ranker_score": row.get("ranker_score"),
    }
    context_record = {
        "task": task,
        "task_family": row.get("task_family"),
        "source_type": row.get("source_type"),
        "split": row.get("split"),
        "phase": phase,
        "target_context": target_context,
        "failure_hints": failure_hints,
    }

    return {
        "schema_version": TRANSITION_BENCH_SCHEMA_VERSION,
        "id": _bench_id(SOURCE_CANDIDATE_OUTCOME, index, row_id),
        "source": _source_record(
            kind=SOURCE_CANDIDATE_OUTCOME,
            row_index=index,
            source_path=source_path,
            row_id=row_id,
            schema_version=_optional_str(row.get("schema_version")),
        ),
        "identity": {
            "task": task,
            "task_family": row.get("task_family"),
            "source_type": row.get("source_type"),
            "split": row.get("split"),
            "phase": phase,
            "file_path": row.get("file_path"),
            "rank_index": rank_index,
        },
        "before": {
            "kind": "candidate_context",
            "record": context_record,
            "record_checksum": _checksum_json(context_record),
        },
        "context": {
            "kind": "candidate_rank_context",
            "rank_index": rank_index,
            "first_passing_index": row.get("first_passing_index"),
            "passing_candidates": row.get("passing_candidates"),
            "equivalent_candidate_ranks": _list_or_empty(
                row.get("equivalent_candidate_ranks")
            ),
            "overlapping_candidate_ranks": _list_or_empty(
                row.get("overlapping_candidate_ranks")
            ),
        },
        "action": {
            "kind": action_kind,
            "candidate_action": candidate_action,
        },
        "target": {
            "kind": "validation_outcome",
            "passed": passed,
            "preferred": row.get("preferred") is True,
            "is_first_pass": row.get("is_first_pass") is True,
            "first_passing_index": row.get("first_passing_index"),
            "passing_candidates": row.get("passing_candidates"),
            "after_embedding": None,
        },
        "validation": _validation_record(
            available=True,
            status="passed" if passed else "failed",
            passed=passed,
            details={
                "failure_hints": failure_hints,
                "passed": passed,
                "preferred": row.get("preferred") is True,
            },
        ),
        "cost": _cost_record(
            {},
            candidate_rank_index=rank_index,
            validation_command_count=1,
        ),
    }


def write_transition_bench_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write validated transition-bench rows as deterministic JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            validate_transition_bench_row(row)
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def load_transition_bench_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Load and validate transition-bench JSONL rows."""

    rows = load_jsonl_objects(path)
    for row in rows:
        validate_transition_bench_row(row)
    return rows


def validate_transition_bench_row(row: Mapping[str, object]) -> None:
    """Validate the common ``transition-bench-v1`` surface."""

    if row.get("schema_version") != TRANSITION_BENCH_SCHEMA_VERSION:
        raise ValueError("transition bench row must use transition-bench-v1")
    _required_str(row, "id", context="transition_bench")
    source = _mapping(row.get("source"), field="source")
    source_kind = _required_str(source, "kind", context="source")
    if source_kind not in SUPPORTED_SOURCE_KINDS:
        raise ValueError(f"unsupported transition bench source kind {source_kind!r}")
    _positive_int(source.get("row_index"), field="source.row_index")

    _mapping(row.get("identity"), field="identity")
    before = _mapping(row.get("before"), field="before")
    context = _mapping(row.get("context"), field="context")
    action = _mapping(row.get("action"), field="action")
    target = _mapping(row.get("target"), field="target")
    validation = _mapping(row.get("validation"), field="validation")
    cost = _mapping(row.get("cost"), field="cost")

    _required_str(before, "kind", context="before")
    _required_str(context, "kind", context="context")
    _required_str(action, "kind", context="action")
    _required_str(target, "kind", context="target")
    available = validation.get("available")
    if not isinstance(available, bool):
        raise ValueError("validation.available must be a bool")
    if available:
        _required_str(validation, "status", context="validation")
    _nonnegative_int(cost.get("hosted_llm_api_tokens"), field="cost.hosted_llm_api_tokens")
    _nonnegative_int(
        cost.get("hosted_repo_context_bytes"),
        field="cost.hosted_repo_context_bytes",
    )

    for label, value in (
        ("before", before),
        ("context", context),
        ("target", target),
    ):
        _validate_embedding(value, label=label)


def _source_record(
    *,
    kind: str,
    row_index: int,
    source_path: Path | None,
    row_id: str | None,
    schema_version: str | None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "kind": kind,
        "row_index": row_index,
    }
    if row_id:
        record["row_id"] = row_id
    if schema_version:
        record["schema_version"] = schema_version
    if source_path is not None:
        record["path"] = str(source_path.expanduser().resolve())
    return record


def _empty_mined_source_skip_record(
    row: Mapping[str, object],
    *,
    index: int,
    source_kind: str,
    source_path: Path | None,
) -> dict[str, object] | None:
    if row.get("kind") != "git_transition":
        return None
    before_source = row.get("before_source")
    after_source = row.get("after_source")
    empty_fields: list[str] = []
    if not isinstance(before_source, str) or not before_source:
        empty_fields.append("before_source")
    if not isinstance(after_source, str) or not after_source:
        empty_fields.append("after_source")
    if not empty_fields:
        return None

    return {
        "source_kind": source_kind,
        "source_path": _resolved_source_path(source_path),
        "row_index": index,
        "reason": "empty_" + "_and_".join(empty_fields),
        "repo": row.get("repo"),
        "file_path": row.get("file_path"),
        "commit": row.get("commit"),
    }


def _resolved_source_path(source_path: Path | None) -> str | None:
    if source_path is None:
        return None
    return str(source_path.expanduser().resolve())


def _validation_record(
    *,
    available: bool,
    status: str | None,
    passed: bool | None,
    details: Mapping[str, object],
) -> dict[str, object]:
    return {
        "available": available,
        "status": status,
        "passed": passed,
        "details": _json_copy(details),
    }


def _cost_record(
    cost: Mapping[str, object],
    *,
    before_bytes: int | None = None,
    after_bytes: int | None = None,
    diff_bytes: int | None = None,
    candidate_rank_index: int | None = None,
    validation_command_count: int | None = None,
) -> dict[str, object]:
    record = dict(cost)
    record.setdefault("hosted_llm_api_tokens", HOSTED_LLM_API_TOKENS)
    record.setdefault("hosted_repo_context_bytes", HOSTED_REPO_CONTEXT_BYTES)
    if before_bytes is not None:
        record["before_bytes"] = before_bytes
    if after_bytes is not None:
        record["after_bytes"] = after_bytes
    if diff_bytes is not None:
        record["diff_bytes"] = diff_bytes
    if candidate_rank_index is not None:
        record["candidate_rank_index"] = candidate_rank_index
    if validation_command_count is not None:
        record["validation_command_count"] = validation_command_count
    return record


def _bench_id(source_kind: str, index: int, row_id: str) -> str:
    suffix = _slug(row_id)[:72]
    return f"transition-bench-{source_kind}-{index:04d}-{suffix}"


def _git_row_id(row: Mapping[str, object], *, index: int) -> str:
    commit = _optional_str(row.get("commit")) or f"row-{index}"
    parent = _optional_str(row.get("parent")) or "unknown-parent"
    file_path = _optional_str(row.get("file_path")) or "unknown.py"
    return f"{parent[:12]}:{commit[:12]}:{file_path}"


def _passed_from_validation(validation: Mapping[str, object]) -> bool | None:
    status = _optional_str(validation.get("status"))
    if status is None:
        return None
    if status in {"passed", "validated"}:
        return True
    if status in {"failed", "blocked", "not_run"}:
        return False
    return None


def _repo_embedding(state: Mapping[str, object], *, field: str) -> list[float]:
    embedding = _float_list(state.get("repo_embedding", []))
    if not embedding:
        raise ValueError(f"{field}.repo_embedding must be a non-empty list")
    dim = state.get("embedding_dim")
    if isinstance(dim, int) and not isinstance(dim, bool) and dim != len(embedding):
        raise ValueError(f"{field}.embedding_dim does not match repo_embedding")
    return embedding


def _repo_python_bytes(state: Mapping[str, object]) -> int:
    aggregate = state.get("aggregate")
    if isinstance(aggregate, Mapping):
        value = aggregate.get("total_python_byte_count")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    files = state.get("files")
    if isinstance(files, list):
        total = 0
        for file_record in files:
            if isinstance(file_record, Mapping):
                value = file_record.get("byte_count")
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    total += value
        return total
    return 0


def _validate_embedding(record: Mapping[str, object], *, label: str) -> None:
    if "embedding" not in record:
        return
    embedding = _float_list(record.get("embedding", []))
    dim = record.get("embedding_dim")
    if not isinstance(dim, int) or isinstance(dim, bool) or dim < 1:
        raise ValueError(f"{label}.embedding_dim must be a positive int")
    if len(embedding) != dim:
        raise ValueError(f"{label}.embedding length must match embedding_dim")


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


def _nonnegative_int(value: object, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative int")
    return value


def _float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        raise ValueError("embedding must be a list")
    result: list[float] = []
    for item in value:
        if not isinstance(item, int | float) or isinstance(item, bool):
            raise ValueError("embedding values must be numeric")
        result.append(float(item))
    return result


def _json_copy(value: Mapping[str, object]) -> dict[str, object]:
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
