"""Bounded GreenShot-7 runner for calculator request-to-repo fixtures."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from greenfield import (
    BuildResult,
    GreenfieldPlan,
    build_calculator_repo,
    plan_calculator_repo,
)
from request_outcomes import append_request_repo_attempt
from request_spec import RequestSpec, parse_request_to_spec


SOURCE_NAME = "j3 greenshot-7"
VALIDATION_COMMAND = "python -m pytest tests/test_calculator_cli.py -q"


def run_greenshot_7_tasks(
    tasks_path: Path,
    out_dir: Path,
    records_path: Path | None = None,
) -> dict[str, object]:
    """Run the bounded calculator request-to-repo fixture manifest."""

    tasks = _load_tasks(tasks_path)
    root = out_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, object] = {
        "total": len(tasks),
        "built": 0,
        "blocked": 0,
        "validation_passed": 0,
        "validation_failed": 0,
        "records_written": 0,
        "output_dirs": [],
        "blocked_output_dirs": [],
        "failures": [],
    }

    for task in tasks:
        _run_one_task(task, root, records_path, summary)

    return summary


def _run_one_task(
    task: dict[str, object],
    root: Path,
    records_path: Path | None,
    summary: dict[str, object],
) -> None:
    name = _task_string(task, "name")
    prompt = _task_string(task, "prompt")
    expected_action = _task_string(task, "expected_action")
    task_out_dir = root / _task_dir_name(name)

    spec = parse_request_to_spec(prompt, task_name=name)
    plan = plan_calculator_repo(spec)

    if expected_action == "emit_request_spec":
        _run_positive_fixture(
            task=task,
            spec=spec,
            plan=plan,
            task_out_dir=task_out_dir,
            records_path=records_path,
            summary=summary,
        )
        return

    if expected_action == "ask_clarification":
        _run_blocked_fixture(
            spec=spec,
            plan=plan,
            task_out_dir=task_out_dir,
            records_path=records_path,
            summary=summary,
        )
        return

    _fail(summary, name, f"unsupported expected_action: {expected_action}")


def _run_positive_fixture(
    *,
    task: dict[str, object],
    spec: RequestSpec,
    plan: GreenfieldPlan,
    task_out_dir: Path,
    records_path: Path | None,
    summary: dict[str, object],
) -> None:
    expected_features = task.get("expected_features")
    if spec.clarifications_needed:
        build_result = build_calculator_repo(plan, task_out_dir)
        validation = _blocked_validation()
        _record_if_requested(
            records_path,
            raw_prompt=spec.prompt,
            spec=spec,
            plan=plan,
            build_result=build_result,
            validation=validation,
            out_dir=task_out_dir,
            files_written=[],
            summary=summary,
        )
        _fail(summary, spec.task_name, "positive fixture produced clarification")
        return

    if isinstance(expected_features, list) and spec.features != expected_features:
        _fail(
            summary,
            spec.task_name,
            f"features {spec.features!r} did not match {expected_features!r}",
        )

    build_result = build_calculator_repo(plan, task_out_dir)
    validation = _run_generated_repo_validation(task_out_dir)

    summary["built"] = int(summary["built"]) + 1
    output_dirs = summary["output_dirs"]
    assert isinstance(output_dirs, list)
    output_dirs.append(str(task_out_dir))

    if validation["status"] == "passed":
        summary["validation_passed"] = int(summary["validation_passed"]) + 1
    else:
        summary["validation_failed"] = int(summary["validation_failed"]) + 1
        _fail(
            summary,
            spec.task_name,
            f"generated pytest failed with exit code {validation['exit_code']}",
        )

    _record_if_requested(
        records_path,
        raw_prompt=spec.prompt,
        spec=spec,
        plan=plan,
        build_result=build_result,
        validation=validation,
        out_dir=task_out_dir,
        files_written=list(build_result.files_written),
        summary=summary,
    )


def _run_blocked_fixture(
    *,
    spec: RequestSpec,
    plan: GreenfieldPlan,
    task_out_dir: Path,
    records_path: Path | None,
    summary: dict[str, object],
) -> None:
    if not spec.clarifications_needed or plan.status != "blocked":
        _fail(summary, spec.task_name, "clarification fixture was not blocked")
        return

    build_result = build_calculator_repo(plan, task_out_dir)
    validation = _blocked_validation()

    summary["blocked"] = int(summary["blocked"]) + 1
    blocked_dirs = summary["blocked_output_dirs"]
    assert isinstance(blocked_dirs, list)
    blocked_dirs.append(str(task_out_dir))

    _record_if_requested(
        records_path,
        raw_prompt=spec.prompt,
        spec=spec,
        plan=plan,
        build_result=build_result,
        validation=validation,
        out_dir=task_out_dir,
        files_written=[],
        summary=summary,
    )


def _record_if_requested(
    records_path: Path | None,
    *,
    raw_prompt: str,
    spec: RequestSpec,
    plan: GreenfieldPlan,
    build_result: BuildResult,
    validation: dict[str, object],
    out_dir: Path,
    files_written: list[str],
    summary: dict[str, object],
) -> None:
    if records_path is None:
        return

    append_request_repo_attempt(
        records_path,
        raw_prompt=raw_prompt,
        spec=spec,
        plan=plan,
        build_result=build_result,
        validation=validation,
        out_dir=out_dir,
        files_written=files_written,
        source=SOURCE_NAME,
    )
    summary["records_written"] = int(summary["records_written"]) + 1


def _load_tasks(path: Path) -> list[dict[str, object]]:
    resolved = path.expanduser().resolve()
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("GreenShot-7 tasks manifest must be a JSON array")
    tasks: list[dict[str, object]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"GreenShot-7 task {index} must be an object")
        tasks.append(item)
    return tasks


def _run_generated_repo_validation(out_dir: Path) -> dict[str, object]:
    command = ["python", "-m", "pytest", "tests/test_calculator_cli.py", "-q"]
    completed = subprocess.run(
        command,
        cwd=out_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    status = "passed" if completed.returncode == 0 else "failed"
    return {
        "status": status,
        "command": VALIDATION_COMMAND,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _blocked_validation() -> dict[str, object]:
    return {
        "status": "not_run",
        "command": None,
        "exit_code": None,
        "reason": "blocked_clarification",
    }


def _task_string(task: dict[str, object], key: str) -> str:
    value = task.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"GreenShot-7 task requires non-empty string field: {key}")
    return value


def _task_dir_name(task_name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", task_name).strip("-._")
    return name or "task"


def _fail(summary: dict[str, object], task_name: str, message: str) -> None:
    failures = summary["failures"]
    assert isinstance(failures, list)
    failures.append({"task": task_name, "message": message})


def summary_has_failures(summary: dict[str, object]) -> bool:
    """Return whether a GreenShot-7 summary contains fixture failures."""

    failures = summary.get("failures", [])
    return isinstance(failures, list) and bool(failures)
