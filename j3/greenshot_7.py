"""Bounded GreenShot-7 runner for request-to-repo fixtures."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path

from j3.existing_repo_tests import (
    ExistingRepoTestsError,
    ExistingRepoTestsPlan,
    ExistingRepoTestsResult,
    ExistingRepoTestsSpec,
    append_existing_repo_tests_attempt,
    apply_existing_repo_tests,
    blocker_from_error,
    existing_repo_tests_spec_from_request,
    plan_existing_repo_tests,
)
from j3.greenfield import (
    BuildResult,
    GreenfieldPlan,
    build_greenfield_repo,
    plan_greenfield_repo,
)
from j3.request_outcomes import append_request_repo_attempt
from j3.request_spec import RequestSpec, parse_request_to_spec


SOURCE_NAME = "j3 greenshot-7"
DEFAULT_VALIDATION_COMMAND = "python -m pytest tests/test_calculator_cli.py -q"
CLASSIFICATION_VALUES = {
    "action_coverage",
    "prompt_spec_parsing",
    "existing_repo_support",
    "greenfield_builder_support",
    "expected_clarification",
}


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
        "existing_repo_tests_built": 0,
        "blocked": 0,
        "validation_passed": 0,
        "validation_failed": 0,
        "records_written": 0,
        "output_dirs": [],
        "blocked_output_dirs": [],
        "classified_failures": [],
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

    if expected_action == "emit_existing_repo_tests":
        _run_existing_repo_tests_fixture(
            task=task,
            spec=spec,
            task_out_dir=task_out_dir,
            records_path=records_path,
            summary=summary,
        )
        return

    plan = plan_greenfield_repo(spec)

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

    if expected_action == "classify_failure":
        _run_classified_fixture(
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
            task=task,
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
        build_result = build_greenfield_repo(plan, task_out_dir)
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

    build_result = build_greenfield_repo(plan, task_out_dir)
    validation = _run_generated_repo_validation(task_out_dir, spec)

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


def _run_existing_repo_tests_fixture(
    *,
    task: dict[str, object],
    spec: RequestSpec,
    task_out_dir: Path,
    records_path: Path | None,
    summary: dict[str, object],
) -> None:
    expected_features = task.get("expected_features")
    if spec.clarifications_needed:
        _fail(summary, spec.task_name, "existing-repo tests fixture produced clarification")
        return
    if isinstance(expected_features, list) and spec.features != expected_features:
        _fail(
            summary,
            spec.task_name,
            f"features {spec.features!r} did not match {expected_features!r}",
        )
        return

    try:
        _materialize_existing_repo_fixture(task, task_out_dir)
        tests_spec = existing_repo_tests_spec_from_request(spec)
        tests_plan = plan_existing_repo_tests(tests_spec, task_out_dir)
        tests_result = apply_existing_repo_tests(tests_plan, task_out_dir)
    except ExistingRepoTestsError as error:
        blocker = blocker_from_error(error)
        validation = {
            "status": "not_run",
            "command": None,
            "exit_code": None,
            "reason": blocker.get("reason", "existing_repo_tests_blocked"),
            "blocker": blocker,
        }
        summary["blocked"] = int(summary["blocked"]) + 1
        blocked_dirs = summary["blocked_output_dirs"]
        assert isinstance(blocked_dirs, list)
        blocked_dirs.append(str(task_out_dir))
        _record_existing_repo_tests_classification(
            spec=spec,
            validation=validation,
            blocker=blocker,
            summary=summary,
        )
        _fail(
            summary,
            spec.task_name,
            f"existing-repo tests blocked: {blocker.get('reason')}",
        )
        return

    validation = tests_result.validation
    summary["built"] = int(summary["built"]) + 1
    summary["existing_repo_tests_built"] = int(summary["existing_repo_tests_built"]) + 1
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
            f"existing-repo pytest failed with exit code {validation['exit_code']}",
        )

    if tests_result.production_files_changed:
        _fail(
            summary,
            spec.task_name,
            "tests-only fixture changed production files: "
            + ", ".join(tests_result.production_files_changed),
        )
    if any(path not in tests_result.target_test_files for path in tests_result.files_changed):
        _fail(
            summary,
            spec.task_name,
            "tests-only fixture changed files outside target tests: "
            + ", ".join(tests_result.files_changed),
        )

    _record_existing_repo_tests_if_requested(
        records_path,
        raw_prompt=spec.prompt,
        request_spec=spec,
        tests_spec=tests_spec,
        tests_plan=tests_plan,
        tests_result=tests_result,
        summary=summary,
    )


def _run_blocked_fixture(
    *,
    task: dict[str, object],
    spec: RequestSpec,
    plan: GreenfieldPlan,
    task_out_dir: Path,
    records_path: Path | None,
    summary: dict[str, object],
) -> None:
    if not spec.clarifications_needed or plan.status != "blocked":
        _fail(summary, spec.task_name, "clarification fixture was not blocked")
        return

    build_result = build_greenfield_repo(plan, task_out_dir)
    validation = _blocked_validation()

    summary["blocked"] = int(summary["blocked"]) + 1
    blocked_dirs = summary["blocked_output_dirs"]
    assert isinstance(blocked_dirs, list)
    blocked_dirs.append(str(task_out_dir))
    _record_classification(
        task=task,
        spec=spec,
        plan=plan,
        validation=validation,
        summary=summary,
    )

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


def _run_classified_fixture(
    *,
    task: dict[str, object],
    spec: RequestSpec,
    plan: GreenfieldPlan,
    task_out_dir: Path,
    records_path: Path | None,
    summary: dict[str, object],
) -> None:
    if not spec.clarifications_needed and plan.status != "blocked":
        _fail(summary, spec.task_name, "classified fixture was not blocked")
        return

    build_result = build_greenfield_repo(plan, task_out_dir)
    validation = _blocked_validation()

    summary["blocked"] = int(summary["blocked"]) + 1
    blocked_dirs = summary["blocked_output_dirs"]
    assert isinstance(blocked_dirs, list)
    blocked_dirs.append(str(task_out_dir))
    _record_classification(
        task=task,
        spec=spec,
        plan=plan,
        validation=validation,
        summary=summary,
    )

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


def _record_classification(
    *,
    task: dict[str, object],
    spec: RequestSpec,
    plan: GreenfieldPlan,
    validation: dict[str, object],
    summary: dict[str, object],
) -> None:
    category = str(task.get("expected_failure_category", "expected_clarification"))
    if category not in CLASSIFICATION_VALUES:
        _fail(summary, spec.task_name, f"unsupported failure category: {category}")
        return

    classified = summary["classified_failures"]
    assert isinstance(classified, list)
    classified.append(
        {
            "task": spec.task_name,
            "category": category,
            "domain": spec.domain,
            "plan_status": plan.status,
            "validation_status": validation["status"],
        }
    )


def _record_existing_repo_tests_classification(
    *,
    spec: RequestSpec,
    validation: dict[str, object],
    blocker: dict[str, str],
    summary: dict[str, object],
) -> None:
    classified = summary["classified_failures"]
    assert isinstance(classified, list)
    classified.append(
        {
            "task": spec.task_name,
            "category": blocker.get("reason", "existing_repo_tests_blocked"),
            "domain": spec.domain,
            "plan_status": "blocked",
            "validation_status": validation["status"],
        }
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


def _record_existing_repo_tests_if_requested(
    records_path: Path | None,
    *,
    raw_prompt: str,
    request_spec: RequestSpec,
    tests_spec: ExistingRepoTestsSpec,
    tests_plan: ExistingRepoTestsPlan,
    tests_result: ExistingRepoTestsResult,
    summary: dict[str, object],
) -> None:
    if records_path is None:
        return
    append_existing_repo_tests_attempt(
        records_path,
        raw_prompt=raw_prompt,
        request_spec=request_spec,
        spec=tests_spec,
        plan=tests_plan,
        result=tests_result,
        source=SOURCE_NAME,
    )
    summary["records_written"] = int(summary["records_written"]) + 1


def _materialize_existing_repo_fixture(
    task: dict[str, object],
    task_out_dir: Path,
) -> None:
    fixture = task.get("existing_repo_fixture")
    if not isinstance(fixture, dict):
        raise ExistingRepoTestsError(
            "missing existing_repo_fixture for tests-only task",
            blocker={
                "field": "repo_state",
                "reason": "missing_repo_state_fixture",
                "message": "GreenShot-7 task did not provide an existing repo fixture.",
            },
        )
    files = fixture.get("files")
    if not isinstance(files, list) or not files:
        raise ExistingRepoTestsError(
            "existing_repo_fixture must provide files",
            blocker={
                "field": "repo_state",
                "reason": "missing_repo_state_fixture",
                "message": "GreenShot-7 existing repo fixture has no files.",
            },
        )

    task_out_dir.mkdir(parents=True, exist_ok=True)
    for item in files:
        if not isinstance(item, dict):
            raise ExistingRepoTestsError(
                "existing_repo_fixture file entries must be objects",
                blocker={
                    "field": "repo_state",
                    "reason": "invalid_repo_state_fixture",
                    "message": "GreenShot-7 existing repo fixture file is invalid.",
                },
            )
        relative_path = item.get("path")
        content = item.get("content")
        if not isinstance(relative_path, str) or not isinstance(content, str):
            raise ExistingRepoTestsError(
                "existing_repo_fixture files require path and content strings",
                blocker={
                    "field": "repo_state",
                    "reason": "invalid_repo_state_fixture",
                    "message": "GreenShot-7 existing repo fixture file is invalid.",
                },
            )
        target = _repo_path(task_out_dir, relative_path)
        if target.exists():
            raise ExistingRepoTestsError(
                f"refusing to overwrite existing fixture file: {target}",
                blocker={
                    "field": "repo_state",
                    "reason": "fixture_file_exists",
                    "message": "GreenShot-7 existing repo fixture output already exists.",
                },
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


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


def _run_generated_repo_validation(out_dir: Path, spec: RequestSpec) -> dict[str, object]:
    command_text = _validation_command(spec)
    command = shlex.split(command_text)
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
        "command": command_text,
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


def _validation_command(spec: RequestSpec) -> str:
    commands = spec.validation.get("commands", [])
    if not isinstance(commands, list) or not commands:
        return DEFAULT_VALIDATION_COMMAND
    first = commands[0]
    if not isinstance(first, str) or not first:
        return DEFAULT_VALIDATION_COMMAND
    return first


def _task_string(task: dict[str, object], key: str) -> str:
    value = task.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"GreenShot-7 task requires non-empty string field: {key}")
    return value


def _task_dir_name(task_name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", task_name).strip("-._")
    return name or "task"


def _repo_path(repo: Path, relative_path: str) -> Path:
    pure_path = Path(relative_path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        raise ExistingRepoTestsError(
            f"fixture path must be relative to the repository: {relative_path}",
            blocker={
                "field": "repo_state",
                "reason": "invalid_repo_state_fixture",
                "message": "GreenShot-7 fixture path escapes the output repo.",
            },
        )
    return repo / pure_path


def _fail(summary: dict[str, object], task_name: str, message: str) -> None:
    failures = summary["failures"]
    assert isinstance(failures, list)
    failures.append({"task": task_name, "message": message})


def summary_has_failures(summary: dict[str, object]) -> bool:
    """Return whether a GreenShot-7 summary contains fixture failures."""

    failures = summary.get("failures", [])
    return isinstance(failures, list) and bool(failures)
