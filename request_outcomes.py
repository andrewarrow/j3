"""Prompt/spec/action/outcome JSONL rows for GreenShot-7 attempts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from greenfield import BuildResult, GreenfieldPlan
from request_spec import RequestSpec


ROW_SCHEMA_VERSION = "request-repo-attempt-v1"
ROW_KIND = "greenshot_7_request_to_repo_attempt"


def request_repo_attempt_row(
    *,
    raw_prompt: str,
    spec: RequestSpec,
    plan: GreenfieldPlan,
    build_result: BuildResult,
    validation: dict[str, object],
    out_dir: Path,
    files_written: list[str],
) -> dict[str, object]:
    """Return a JSON-compatible prompt/spec/action/outcome attempt row."""

    spec_record = spec.to_record()
    plan_record = plan.to_record()
    build_record = build_result.to_record()
    build_record["cli_files_written"] = list(files_written)
    validation_record = _json_copy(validation)
    clarification_status = "blocked" if spec.clarifications_needed else "not_needed"
    failure_observation = _failure_observation(
        spec=spec,
        build_result=build_result,
        validation=validation,
    )

    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "record_kind": ROW_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "source": "j3 implement",
            "request_schema_version": spec.schema_version,
            "plan_schema_version": plan.schema_version,
            "build_schema_version": build_result.schema_version,
        },
        "raw_prompt": raw_prompt,
        "normalized_request_spec": spec_record,
        "inferred_defaults": list(spec_record["inferred_defaults"]),  # type: ignore[index]
        "clarification_decision": {
            "status": clarification_status,
            "clarifications_needed": list(
                spec_record["clarifications_needed"]  # type: ignore[index]
            ),
        },
        "greenfield_plan": plan_record,
        "greenfield_actions": list(plan_record["actions"]),  # type: ignore[index]
        "build_result": build_record,
        "validation": validation_record,
        "passed": failure_observation is None,
        "failure_observation": failure_observation,
        "output_repo_path": str(out_dir),
    }


def append_request_repo_attempt(
    path: Path,
    *,
    raw_prompt: str,
    spec: RequestSpec,
    plan: GreenfieldPlan,
    build_result: BuildResult,
    validation: dict[str, object],
    out_dir: Path,
    files_written: list[str],
) -> Path:
    """Append one prompt/spec/action/outcome row to a JSONL file."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    row = request_repo_attempt_row(
        raw_prompt=raw_prompt,
        spec=spec,
        plan=plan,
        build_result=build_result,
        validation=validation,
        out_dir=out_dir,
        files_written=files_written,
    )
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return resolved


def _failure_observation(
    *,
    spec: RequestSpec,
    build_result: BuildResult,
    validation: dict[str, object],
) -> dict[str, object] | None:
    if spec.clarifications_needed:
        return {
            "kind": "blocking_clarification",
            "clarifications_needed": [
                dict(clarification) for clarification in spec.clarifications_needed
            ],
        }
    if build_result.status != "built":
        return {
            "kind": "build_not_completed",
            "status": build_result.status,
            "blockers": [dict(blocker) for blocker in build_result.blockers],
        }
    if validation.get("status") == "failed":
        return {
            "kind": "validation_failed",
            "command": validation.get("command"),
            "exit_code": validation.get("exit_code"),
            "stdout": validation.get("stdout", ""),
            "stderr": validation.get("stderr", ""),
        }
    return None


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value))
