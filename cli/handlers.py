"""Command handlers for the j3 CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from actions import PatchActionKind
from candidate_ranking import train_candidate_ranker
from candidate_ranker.summary import (
    format_outcome_dataset_summary,
    summarize_candidate_outcomes,
)
from cli.progress import (
    eval_phase_solved,
    phase_summary_line,
    summary_progress,
    task_phase_status,
    verbose_progress,
)
from diagnostics_compare import compare_diagnostics, format_diagnostics_comparison
from evaluation import evaluate_tasks, write_candidate_outcomes, write_eval_diagnostics
from fixing import run_fix_workflow
from greenfield import (
    BuildResult,
    GreenfieldPlan,
    build_calculator_repo,
    plan_calculator_repo,
)
from greenshot_7 import run_greenshot_7_tasks, summary_has_failures
from mining import mine_git_transitions
from patching import plan_and_maybe_apply_patch
from request_outcomes import append_request_repo_attempt
from request_spec import RequestSpec, parse_request_to_spec
from training import train_from_paths


REQUEST_SPEC_ARTIFACT = "request-spec.json"


def handle_actions(args: argparse.Namespace) -> int:
    names = [kind.value for kind in PatchActionKind]
    if args.json:
        print(json.dumps(names, indent=2))
    else:
        for name in names:
            print(name)
    return 0


def handle_implement(args: argparse.Namespace) -> int:
    spec = parse_request_to_spec(args.prompt)
    out_dir = args.out.expanduser().resolve()
    plan = plan_calculator_repo(spec)

    if spec.clarifications_needed:
        result = build_calculator_repo(plan, out_dir)
        validation = _blocked_implement_validation()
        _record_implement_attempt(
            args.record,
            raw_prompt=args.prompt,
            spec=spec,
            plan=plan,
            build_result=result,
            validation=validation,
            out_dir=out_dir,
            files_written=[],
        )
        print("j3 implement blocked")
        print(f"task type: {spec.task_type}")
        print("status: blocked")
        print(f"domain: {spec.domain}")
        print("clarifications:")
        for clarification in spec.clarifications_needed:
            field = clarification.get("field", "request")
            question = clarification.get("question", "Clarification is required.")
            print(f"  {field}: {question}")
        return 1

    if (out_dir / REQUEST_SPEC_ARTIFACT).exists():
        raise FileExistsError(
            f"refusing to overwrite existing file: {out_dir / REQUEST_SPEC_ARTIFACT}"
        )

    result = build_calculator_repo(plan, out_dir)
    spec_artifact = _write_request_spec_artifact(spec, out_dir)

    files_written = [*result.files_written, spec_artifact.name]
    validation = (
        _run_generated_repo_validation(out_dir)
        if not args.no_validate
        else {
            "status": "skipped",
            "command": "python -m pytest tests/test_calculator_cli.py -q",
            "exit_code": None,
        }
    )
    _record_implement_attempt(
        args.record,
        raw_prompt=args.prompt,
        spec=spec,
        plan=plan,
        build_result=result,
        validation=validation,
        out_dir=out_dir,
        files_written=files_written,
    )

    print("j3 implement complete")
    print(f"task type: {spec.task_type}")
    print(f"status: {result.status}")
    print(f"domain: {spec.domain}")
    print(f"out: {out_dir}")
    print(f"features: {', '.join(spec.features)}")
    print("files written:")
    for path in files_written:
        print(f"  {path}")
    print(_format_validation_result(validation))

    if validation["status"] == "failed":
        return int(validation["exit_code"]) or 1
    return 0


def handle_greenshot_7(args: argparse.Namespace) -> int:
    summary = run_greenshot_7_tasks(
        tasks_path=args.tasks,
        out_dir=args.out,
        records_path=args.record,
    )

    print("j3 greenshot-7 complete")
    print(f"tasks: {summary['total']}")
    print(f"built: {summary['built']}")
    print(f"blocked: {summary['blocked']}")
    print(f"validation passed: {summary['validation_passed']}")
    print(f"validation failed: {summary['validation_failed']}")
    print(f"records written: {summary['records_written']}")
    print(f"out: {args.out.expanduser().resolve()}")
    if args.record:
        print(f"record: {args.record.expanduser().resolve()}")

    failures = summary["failures"]
    if failures:
        print("failures:")
        for failure in failures:
            print(f"  {failure['task']}: {failure['message']}")

    return 1 if summary_has_failures(summary) else 0


def handle_patch(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f"repo does not exist: {repo}")
    if not repo.is_dir():
        raise SystemExit(f"repo is not a directory: {repo}")

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=args.test,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        max_candidates=args.max_candidates,
        max_steps=args.max_steps,
        model_path=args.model,
        ranker_path=args.ranker,
    )

    mode = "dry run" if args.dry_run else "apply"
    print(f"j3 patch ({mode})")
    print(f"repo: {repo}")
    print(f"test: {args.test}")
    print(f"baseline exit code: {result.baseline_exit_code}")
    if result.model_path:
        print(f"model: {result.model_path}")
    if result.ranker_path:
        print(f"ranker: {result.ranker_path}")

    if result.baseline_exit_code == 0:
        print("status: test already passes; no patch generated")
        return 0

    print(f"candidates generated: {result.candidates_generated}")
    print(f"candidates tested: {result.candidates_tested}")

    if result.selected is None:
        print("status: no candidate patch made the test pass")
        return 1

    print(f"status: {'applied' if result.applied else 'found'} passing patch")
    if len(result.selected_candidates) > 1:
        print(f"repair steps: {len(result.selected_candidates)}")
        for index, candidate in enumerate(result.selected_candidates, start=1):
            print(
                f"  {index}. {candidate.action.kind.value} "
                f"{candidate.file_path} ({candidate.reason})"
            )
    print(f"action: {result.selected.action.kind.value}")
    print(f"file: {result.selected.file_path}")
    print(f"reason: {result.selected.reason}")
    if result.selected.model_score is not None:
        print(f"model score: {result.selected.model_score:.4f}")
    if result.selected.ranker_score is not None:
        print(f"ranker score: {result.selected.ranker_score:.4f}")
    print("diff:")
    print(result.selected.diff(), end="" if result.selected.diff().endswith("\n") else "\n")
    return 0


def handle_fix(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        raise SystemExit(f"repo does not exist: {repo}")
    if not repo.is_dir():
        raise SystemExit(f"repo is not a directory: {repo}")

    result = run_fix_workflow(
        repo=repo,
        test_command=args.test,
        model_path=args.model,
        ranker_path=args.ranker,
        yes=args.yes,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        max_candidates=args.max_candidates,
        confirm=_confirm,
    )

    mode = "dry run" if args.dry_run else "review"
    if args.yes and not args.dry_run:
        mode = "apply"

    print(f"j3 fix ({mode})")
    print(f"repo: {result.repo}")
    print(f"test: {result.test_command}")
    print(f"baseline exit code: {result.baseline_exit_code}")

    if result.baseline_exit_code == 0:
        print("status: tests already pass")
        return 0

    print(f"failing targets: {len(result.failing_targets)}")
    for target in result.failing_targets:
        print(f"  {target}")

    if not result.attempts:
        print("status: no patch attempts were made")
        return 1

    for attempt in result.attempts:
        print("")
        print(f"target: {attempt.target}")
        print(f"target test: {attempt.test_command}")
        print(f"candidates generated: {attempt.plan.candidates_generated}")
        print(f"candidates tested: {attempt.plan.candidates_tested}")
        if attempt.plan.selected is None:
            print("status: no passing patch found")
            continue

        print(f"status: {'applied' if attempt.applied else 'planned'} passing patch")
        print(f"action: {attempt.plan.selected.action.kind.value}")
        print(f"file: {attempt.plan.selected.file_path}")
        print(f"reason: {attempt.plan.selected.reason}")
        if attempt.plan.selected.model_score is not None:
            print(f"model score: {attempt.plan.selected.model_score:.4f}")
        if attempt.plan.selected.ranker_score is not None:
            print(f"ranker score: {attempt.plan.selected.ranker_score:.4f}")
        print("diff:")
        print(
            attempt.plan.selected.diff(),
            end="" if attempt.plan.selected.diff().endswith("\n") else "\n",
        )

    return 0 if result.solved else 1


def handle_train(args: argparse.Namespace) -> int:
    result = train_from_paths(
        data_paths=args.data,
        out_dir=args.out,
        embedding_dim=args.embedding_dim,
        max_examples=args.max_examples,
        transition_paths=args.transitions,
    )
    print("j3 train complete")
    print("data:")
    for path in args.data:
        print(f"  {path.expanduser().resolve()}")
    print(f"out: {result.out_dir}")
    print(f"source files: {result.source_files}")
    print(f"examples: {result.parsed_examples}")
    print(f"mined transitions: {result.mined_examples}")
    print("actions:")
    for action, count in result.action_counts.items():
        print(f"  {action}: {count}")
    print(f"model: {result.model_path}")
    print(f"metrics: {result.metrics_path}")
    print(f"examples: {result.examples_path}")
    return 0


def handle_train_ranker(args: argparse.Namespace) -> int:
    if not args.diagnostics and not args.candidate_outcomes:
        raise SystemExit("provide --diagnostics or --candidate-outcomes")

    result = train_candidate_ranker(
        diagnostics_paths=args.diagnostics,
        candidate_outcome_paths=args.candidate_outcomes,
        validation_diagnostics_paths=args.validation_diagnostics,
        validation_candidate_outcome_paths=args.validation_candidate_outcomes,
        holdout_tasks=args.holdout_tasks,
        holdout_task_families=args.holdout_task_families,
        out_dir=args.out,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    print("j3 train-ranker complete")
    if result.diagnostics_paths:
        print("diagnostics:")
        for path in result.diagnostics_paths:
            print(f"  {path}")
    if result.candidate_outcome_paths:
        print("candidate outcomes:")
        for path in result.candidate_outcome_paths:
            print(f"  {path}")
    if result.validation_diagnostics_paths:
        print("validation diagnostics:")
        for path in result.validation_diagnostics_paths:
            print(f"  {path}")
    if result.validation_candidate_outcome_paths:
        print("validation candidate outcomes:")
        for path in result.validation_candidate_outcome_paths:
            print(f"  {path}")
    if result.holdout_tasks:
        print(f"holdout tasks: {', '.join(result.holdout_tasks)}")
    if result.holdout_task_families:
        print(f"holdout task families: {', '.join(result.holdout_task_families)}")
    print(f"out: {result.out_dir}")
    print(f"rows: {result.rows}")
    print(f"passing rows: {result.passing_rows}")
    print(f"failing rows: {result.failing_rows}")
    print(f"tasks: {result.tasks}")
    print(f"plans: {result.plans}")
    print(f"training pairs: {result.training_pairs}")
    print(f"features: {result.features}")
    print(f"mistakes: {result.mistakes}")
    print(f"training accuracy: {result.training_accuracy:.3f}")
    print(f"margin violations: {result.margin_violations}")
    brier_score = result.calibration.get("brier_score")
    calibration_error = result.calibration.get("expected_calibration_error")
    if isinstance(brier_score, float):
        print(f"calibration brier: {brier_score:.3f}")
    if isinstance(calibration_error, float):
        print(f"calibration ece: {calibration_error:.3f}")
    validation = result.validation
    if validation.get("plans"):
        print(
            "validation: "
            f"plans={validation['plans']} "
            f"solved={validation['solved']}/{validation['plans']} "
            f"pass@1={validation['pass_at_1']}/{validation['plans']} "
            f"positive@1={validation['positive_at_1']}/{validation['plans']}"
        )
        validation_calibration = validation.get("calibration")
        if isinstance(validation_calibration, dict):
            validation_brier = validation_calibration.get("brier_score")
            validation_ece = validation_calibration.get("expected_calibration_error")
            if isinstance(validation_brier, float):
                print(f"validation calibration brier: {validation_brier:.3f}")
            if isinstance(validation_ece, float):
                print(f"validation calibration ece: {validation_ece:.3f}")
    print(f"ranker: {result.ranker_path}")
    print(f"metrics: {result.metrics_path}")
    return 0


def handle_outcome_summary(args: argparse.Namespace) -> int:
    for path in args.candidate_outcomes:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise SystemExit(f"candidate outcomes file does not exist: {resolved}")
        if not resolved.is_file():
            raise SystemExit(f"candidate outcomes path is not a file: {resolved}")
    summary = summarize_candidate_outcomes(
        paths=args.candidate_outcomes,
        phase=None if args.phase == "all" else args.phase,
    )
    if args.json:
        print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    else:
        print(format_outcome_dataset_summary(summary))
    return 0


def handle_compare_diagnostics(args: argparse.Namespace) -> int:
    comparison = compare_diagnostics(
        old_path=args.old,
        new_path=args.new,
        phase=args.phase,
        top_reasons=args.top_reasons,
    )
    print(format_diagnostics_comparison(comparison))
    return 0


def handle_mine(args: argparse.Namespace) -> int:
    result = mine_git_transitions(
        repo=args.repo,
        out_path=args.out,
        max_commits=args.max_commits,
        max_files_per_commit=args.max_files_per_commit,
    )
    print("j3 mine complete")
    print(f"repo: {result.repo}")
    print(f"out: {result.out_path}")
    print(f"commits scanned: {result.commits_scanned}")
    print(f"transitions written: {result.transitions_written}")
    return 0


def handle_eval(args: argparse.Namespace) -> int:
    progress = None if args.quiet else (verbose_progress if args.verbose else summary_progress)
    if progress is not None:
        progress("j3 eval starting")
        progress(f"tasks: {args.tasks.expanduser().resolve()}")
        progress(f"checkpoint: {args.checkpoint.expanduser().resolve()}")
        progress(f"timeout per test run: {args.timeout}s")
        progress(f"max candidates per phase: {args.max_candidates}")
        progress(f"max steps per task: {args.max_steps}")
        if args.explore_after_pass:
            progress(f"explore after pass: {args.explore_after_pass}")
        progress(f"phase: {args.phase}")
    summary = evaluate_tasks(
        tasks_path=args.tasks,
        model_path=args.checkpoint,
        ranker_path=args.ranker,
        timeout_seconds=args.timeout,
        max_candidates=args.max_candidates,
        max_steps=args.max_steps,
        phase=args.phase,
        explore_after_pass=args.explore_after_pass,
        progress=progress,
    )
    diagnostics_path = write_eval_diagnostics(summary, args.diagnostics) if args.diagnostics else None
    outcomes_path = (
        write_candidate_outcomes(summary, args.candidate_outcomes)
        if args.candidate_outcomes
        else None
    )

    print("j3 eval complete")
    print(f"tasks: {summary.total}")
    print(f"checkpoint: {args.checkpoint.expanduser().resolve()}")
    if args.ranker:
        print(f"ranker: {args.ranker.expanduser().resolve()}")
    print(
        phase_summary_line(
            "baseline",
            summary.baseline_skipped,
            summary.baseline_solved,
            summary.baseline_pass_at_1,
            summary.baseline_avg_candidates_tested,
            summary.total,
        )
    )
    print(
        phase_summary_line(
            "model-ranked",
            summary.ranked_skipped,
            summary.ranked_solved,
            summary.ranked_pass_at_1,
            summary.ranked_avg_candidates_tested,
            summary.total,
        )
    )
    print("tasks:")
    for task in summary.tasks:
        baseline_status = task_phase_status(
            skipped=task.baseline_skipped,
            solved=task.baseline_solved,
        )
        ranked_status = task_phase_status(
            skipped=task.ranked_skipped,
            solved=task.ranked_solved,
        )
        baseline_tested = task.baseline.candidates_tested if task.baseline is not None else "-"
        ranked_tested = task.ranked.candidates_tested if task.ranked is not None else "-"
        ranked_action = (
            task.ranked.selected.action.kind.value
            if task.ranked is not None and task.ranked.selected
            else "-"
        )
        print(
            f"  {task.task.name}: "
            f"baseline={baseline_status}/{baseline_tested} "
            f"model={ranked_status}/{ranked_tested} "
            f"action={ranked_action}"
        )
    if diagnostics_path:
        print(f"diagnostics: {diagnostics_path}")
    if outcomes_path:
        print(f"candidate outcomes: {outcomes_path}")
    return 0 if eval_phase_solved(summary=summary, phase=args.phase) else 1


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _write_request_spec_artifact(spec: RequestSpec, out_dir: Path) -> Path:
    path = out_dir / REQUEST_SPEC_ARTIFACT
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.write_text(
        json.dumps(spec.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


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
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _blocked_implement_validation() -> dict[str, object]:
    return {
        "status": "not_run",
        "command": None,
        "exit_code": None,
        "reason": "blocked_clarification",
    }


def _record_implement_attempt(
    record_path: Path | None,
    *,
    raw_prompt: str,
    spec: RequestSpec,
    plan: GreenfieldPlan,
    build_result: BuildResult,
    validation: dict[str, object],
    out_dir: Path,
    files_written: list[str],
) -> None:
    if record_path is None:
        return
    append_request_repo_attempt(
        record_path,
        raw_prompt=raw_prompt,
        spec=spec,
        plan=plan,
        build_result=build_result,
        validation=validation,
        out_dir=out_dir,
        files_written=files_written,
    )


def _format_validation_result(validation: dict[str, object]) -> str:
    status = validation["status"]
    command = validation["command"]
    if status == "skipped":
        return f"validation: skipped ({command})"
    if status == "passed":
        return f"validation: passed ({command})"
    return f"validation: failed exit={validation['exit_code']} ({command})"
