"""Prompt-to-repo transition rows for Prompt+Repo JEPA experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from j3.prompt_jepa import (
    EXISTING_REPO_CHANGE_ATTEMPT_KIND,
    REQUEST_REPO_ATTEMPT_KIND,
    default_prompt_jepa_metadata,
    encode_prompt_context,
    encode_prompt_target,
)


PROMPT_REPO_TRANSITION_SCHEMA_VERSION = "prompt-repo-transition-v1"
PROMPT_REPO_TRANSITION_TARGET_SCHEMA_VERSION = "prompt-repo-transition-target-v1"
TRANSITION_ARTIFACT = "transitions.jsonl"
HOSTED_LLM_API_TOKENS = 0
HOSTED_REPO_CONTEXT_BYTES = 0


@dataclass(frozen=True, slots=True)
class PromptRepoOutcomeState:
    """Repo states observed before and, when source changed, after an outcome."""

    repo_before: Mapping[str, object]
    repo_after: Mapping[str, object] | None = None


def build_prompt_repo_transition_rows(
    outcome_rows: Sequence[Mapping[str, object]],
    outcome_states: Sequence[PromptRepoOutcomeState],
    *,
    embedding_dim: int = 256,
) -> tuple[dict[str, object], ...]:
    """Build stable transition rows from demo prompt/spec/action/outcome rows."""

    if len(outcome_rows) != len(outcome_states):
        raise ValueError("outcome_rows and outcome_states must have the same length")

    return tuple(
        build_prompt_repo_transition_row(
            row,
            outcome_states[index - 1],
            index=index,
            embedding_dim=embedding_dim,
        )
        for index, row in enumerate(outcome_rows, start=1)
    )


def build_prompt_repo_transition_row(
    outcome_row: Mapping[str, object],
    state: PromptRepoOutcomeState,
    *,
    index: int,
    embedding_dim: int = 256,
) -> dict[str, object]:
    """Build one JSON-serializable Prompt+Repo JEPA transition row."""

    metadata = default_prompt_jepa_metadata(embedding_dim=embedding_dim)
    record_kind = _required_str(outcome_row, "record_kind", index=index)
    prompt = _outcome_prompt(outcome_row, index=index)
    task_type = _task_type(outcome_row, record_kind=record_kind, index=index)
    action = _structured_action(outcome_row, record_kind=record_kind, index=index)
    validation = _validation(outcome_row, index=index)
    outcome = _outcome_summary(
        outcome_row,
        record_kind=record_kind,
        action_kind=str(action["kind"]),
        validation=validation,
        index=index,
    )
    target_summary = _target_summary(
        outcome_row,
        record_kind=record_kind,
        action=action,
        outcome=outcome,
        validation=validation,
        index=index,
    )
    tags = _transition_tags(target_summary)
    context_embedding = encode_prompt_context(
        prompt,
        dim=embedding_dim,
        source_type=record_kind,
        task_type=task_type,
        tags=tags,
    )
    target_embedding = encode_prompt_target(
        target_summary,
        dim=embedding_dim,
        tags=tags,
    )
    repo_before = _repo_state_record(state.repo_before, field="repo_before")
    after_kind = str(outcome["kind"])
    if after_kind in {"source_changed", "source_unchanged"}:
        if state.repo_after is None:
            raise ValueError(
                f"transition {index} requires repo_after for outcome kind {after_kind}"
            )
        repo_after_state = _repo_state_record(state.repo_after, field="repo_after")
    else:
        repo_after_state = repo_before

    return {
        "schema_version": PROMPT_REPO_TRANSITION_SCHEMA_VERSION,
        "id": f"prompt-repo-transition-{index:04d}",
        "source_outcome": {
            "record_kind": record_kind,
            "outcome_row_index": index,
            "outcome_row_id": _optional_str(outcome_row.get("id"))
            or _optional_str(outcome_row.get("row_id")),
        },
        "prompt_context": {
            "prompt": prompt,
            "context_encoder": metadata.context_encoder.to_record(),
            "embedding_dim": embedding_dim,
            "embedding_checksum": _checksum_json(context_embedding),
            "embedding": list(context_embedding),
        },
        "prompt_jepa_target": {
            "target_encoder": metadata.target_encoder.to_record(),
            "embedding_dim": embedding_dim,
            "embedding_checksum": _checksum_json(target_embedding),
            "summary": target_summary,
        },
        "repo_before": {
            "state_checksum": _checksum_json(repo_before),
            "state": repo_before,
        },
        "structured_action": action,
        "outcome": outcome,
        "repo_after": {
            "kind": after_kind,
            "state_checksum": _checksum_json(repo_after_state),
            "state": repo_after_state,
        },
        "validation": validation,
        "cost": _cost_record(
            repo_before=repo_before,
            repo_after=repo_after_state,
            validation=validation,
        ),
    }


def write_prompt_repo_transitions_jsonl(
    rows: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write transition rows as deterministic JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def load_prompt_repo_transition_rows(path: Path) -> tuple[dict[str, object], ...]:
    """Load transition JSONL rows."""

    rows: list[dict[str, object]] = []
    with path.expanduser().resolve().open(encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"transition row {line_index} must be an object")
            rows.append(row)
    return tuple(rows)


def _structured_action(
    row: Mapping[str, object],
    *,
    record_kind: str,
    index: int,
) -> dict[str, object]:
    if record_kind == REQUEST_REPO_ATTEMPT_KIND:
        spec = _mapping_field(row, "normalized_request_spec", index=index)
        actions = _list_field(row, "greenfield_actions", index=index)
        action_kinds = _action_kinds(actions)
        kind = "ask_clarification" if "ask_clarification" in action_kinds else "create_repo"
        return {
            "kind": kind,
            "record_kind": record_kind,
            "repo_mode": _optional_str(spec.get("repo_mode")),
            "task_type": _optional_str(spec.get("task_type")),
            "domain": _optional_str(spec.get("domain")),
            "features": _string_list(spec.get("features", [])),
            "target_files": _string_list(spec.get("artifacts", [])),
            "action_kinds": action_kinds,
            "action_count": len(action_kinds),
        }
    if record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        spec = _mapping_field(row, "existing_repo_change_spec", index=index)
        actions = _list_field(row, "existing_repo_actions", index=index)
        action_kinds = _action_kinds(actions)
        return {
            "kind": "modify_repo",
            "record_kind": record_kind,
            "repo_mode": _optional_str(spec.get("repo_mode")),
            "task_type": _optional_str(spec.get("task_type")),
            "domain": _optional_str(spec.get("domain")),
            "features": _string_list(spec.get("features_to_add", [])),
            "target_files": _string_list(spec.get("target_files", [])),
            "action_kinds": action_kinds,
            "action_count": len(action_kinds),
        }
    raise ValueError(f"transition row {index} has unsupported record_kind {record_kind!r}")


def _outcome_summary(
    row: Mapping[str, object],
    *,
    record_kind: str,
    action_kind: str,
    validation: Mapping[str, object],
    index: int,
) -> dict[str, object]:
    passed = bool(row.get("passed", False))
    failure = row.get("failure_observation")
    failure_kind = _failure_kind(failure)
    if failure_kind == "blocking_clarification" or action_kind == "ask_clarification":
        kind = "blocked_no_change"
    elif record_kind == REQUEST_REPO_ATTEMPT_KIND:
        build_result = _mapping_field(row, "build_result", index=index)
        kind = "source_changed" if build_result.get("status") == "built" else "source_unchanged"
    elif record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        change_result = _mapping_field(row, "change_result", index=index)
        changed = bool(_string_list(change_result.get("files_changed", [])))
        kind = "source_changed" if changed else "source_unchanged"
    else:
        raise ValueError(f"transition row {index} has unsupported record_kind {record_kind!r}")
    return {
        "kind": kind,
        "status": _outcome_status(row, record_kind=record_kind, index=index),
        "passed": passed,
        "failure_kind": failure_kind,
    }


def _target_summary(
    row: Mapping[str, object],
    *,
    record_kind: str,
    action: Mapping[str, object],
    outcome: Mapping[str, object],
    validation: Mapping[str, object],
    index: int,
) -> dict[str, object]:
    return _drop_none_values(
        {
            "schema_version": PROMPT_REPO_TRANSITION_TARGET_SCHEMA_VERSION,
            "record_kind": record_kind,
            "action_kind": action.get("kind"),
            "outcome_kind": outcome.get("kind"),
            "outcome_status": outcome.get("status"),
            "validation_status": validation.get("status"),
            "passed": outcome.get("passed"),
            "repo_mode": action.get("repo_mode"),
            "task_type": action.get("task_type"),
            "domain": action.get("domain"),
            "features": list(action.get("features", []))
            if isinstance(action.get("features"), list)
            else [],
            "target_files": list(action.get("target_files", []))
            if isinstance(action.get("target_files"), list)
            else [],
            "action_kinds": list(action.get("action_kinds", []))
            if isinstance(action.get("action_kinds"), list)
            else [],
            "failure_kind": outcome.get("failure_kind"),
            "clarification_fields": _clarification_fields(row, record_kind, index=index),
        }
    )


def _validation(row: Mapping[str, object], *, index: int) -> dict[str, object]:
    validation = _mapping_field(row, "validation", index=index)
    return {
        "status": _optional_str(validation.get("status")),
        "command": _optional_str(validation.get("command")),
        "exit_code": validation.get("exit_code"),
    }


def _cost_record(
    *,
    repo_before: Mapping[str, object],
    repo_after: Mapping[str, object],
    validation: Mapping[str, object],
) -> dict[str, object]:
    before_aggregate = _mapping_field(repo_before, "aggregate", index=0)
    after_aggregate = _mapping_field(repo_after, "aggregate", index=0)
    command = validation.get("command")
    return {
        "hosted_llm_api_tokens": HOSTED_LLM_API_TOKENS,
        "hosted_repo_context_bytes": HOSTED_REPO_CONTEXT_BYTES,
        "validation_command_count": 1 if isinstance(command, str) and command else 0,
        "repo_before_python_file_count": int(
            before_aggregate.get("python_file_count", 0)
        ),
        "repo_after_python_file_count": int(after_aggregate.get("python_file_count", 0)),
        "repo_before_python_byte_count": int(
            before_aggregate.get("total_python_byte_count", 0)
        ),
        "repo_after_python_byte_count": int(
            after_aggregate.get("total_python_byte_count", 0)
        ),
    }


def _repo_state_record(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    record = _json_copy(value)
    if not isinstance(record, dict):
        raise ValueError(f"{field} must be an object")
    if record.get("schema_version") != "repo-state-v1":
        raise ValueError(f"{field} must use repo-state-v1")
    return record


def _outcome_status(
    row: Mapping[str, object],
    *,
    record_kind: str,
    index: int,
) -> str | None:
    if record_kind == REQUEST_REPO_ATTEMPT_KIND:
        return _optional_str(_mapping_field(row, "build_result", index=index).get("status"))
    if record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        return _optional_str(_mapping_field(row, "change_result", index=index).get("status"))
    return None


def _task_type(
    row: Mapping[str, object],
    *,
    record_kind: str,
    index: int,
) -> str | None:
    if record_kind == REQUEST_REPO_ATTEMPT_KIND:
        return _optional_str(
            _mapping_field(row, "normalized_request_spec", index=index).get("task_type")
        )
    if record_kind == EXISTING_REPO_CHANGE_ATTEMPT_KIND:
        return _optional_str(
            _mapping_field(row, "existing_repo_change_spec", index=index).get("task_type")
        )
    return None


def _clarification_fields(
    row: Mapping[str, object],
    record_kind: str,
    *,
    index: int,
) -> list[str]:
    if record_kind != REQUEST_REPO_ATTEMPT_KIND:
        return []
    spec = _mapping_field(row, "normalized_request_spec", index=index)
    clarifications = spec.get("clarifications_needed", [])
    fields: list[str] = []
    if not isinstance(clarifications, list | tuple):
        return fields
    for item in clarifications:
        if not isinstance(item, Mapping):
            continue
        field = item.get("field")
        if isinstance(field, str) and field:
            fields.append(field)
    return fields


def _transition_tags(target_summary: Mapping[str, object]) -> tuple[str, ...]:
    tags: list[str] = ["transition"]
    for field in (
        "record_kind",
        "action_kind",
        "outcome_kind",
        "validation_status",
        "repo_mode",
        "task_type",
        "domain",
        "failure_kind",
    ):
        value = target_summary.get(field)
        if isinstance(value, str) and value:
            tags.append(value)
    tags.extend(_string_list(target_summary.get("features", [])))
    return tuple(dict.fromkeys(tags))


def _action_kinds(actions: Sequence[object]) -> list[str]:
    kinds: list[str] = []
    for action in actions:
        if not isinstance(action, Mapping):
            continue
        kind = action.get("kind")
        if isinstance(kind, str) and kind:
            kinds.append(kind)
    return kinds


def _failure_kind(value: object) -> str:
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if isinstance(kind, str) and kind:
            return kind
    return "none"


def _outcome_prompt(row: Mapping[str, object], *, index: int) -> str:
    prompt = row.get("raw_prompt", row.get("prompt"))
    if not isinstance(prompt, str) or not prompt:
        raise ValueError(f"transition row {index} has no prompt")
    return prompt


def _required_str(row: Mapping[str, object], field: str, *, index: int) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"transition row {index} field {field!r} must be a string")
    return value


def _mapping_field(
    row: Mapping[str, object],
    field: str,
    *,
    index: int,
) -> Mapping[str, object]:
    value = row.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"transition row {index} field {field!r} must be an object")
    return value


def _list_field(
    row: Mapping[str, object],
    field: str,
    *,
    index: int,
) -> list[object]:
    value = row.get(field)
    if not isinstance(value, list):
        raise ValueError(f"transition row {index} field {field!r} must be a list")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, str)]


def _drop_none_values(record: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if value is not None}


def _checksum_json(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value, sort_keys=True))
