"""Probe stronger validation for passing issue/PR decoys.

VAL-002 is a validation adequacy probe, not a ranker change. It loads the
DATA-039/DATA-040 live decoy bundles, finds decoys that passed focused
validation, and runs label-safe hidden-like behavior probes against matching
accepted checkouts and passing decoy checkouts when available.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from j3.issue_pr_candidate_attempt import (
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
)


VALIDATION_STRENGTH_PROBE_SCHEMA_VERSION = "issue-pr-validation-strength-probe-v1"
DEFAULT_OUT_DIR = Path("/tmp/j3-val-002-validation-strength-probe")
DEFAULT_DECOY_BUNDLE_PATHS = (
    Path("/tmp/j3-data-039-scrapy-decoy-validation/decoy-validation-bundle.json"),
    Path("/tmp/j3-data-040-pytest-decoy-validation/decoy-validation-bundle.json"),
)

SCRAPY_PEEK_NON_MUTATING_CODE = r"""
from unittest.mock import Mock

from scrapy.core.downloader import Downloader
from scrapy.http.request import Request
from scrapy.pqueues import DownloaderAwarePriorityQueue
from scrapy.spiders import Spider
from scrapy.squeues import FifoMemoryQueue
from scrapy.utils.test import get_crawler
from tests.test_scheduler import MockDownloader

crawler = get_crawler(Spider)
crawler.engine = Mock(downloader=MockDownloader())
queue = DownloaderAwarePriorityQueue.from_crawler(
    crawler=crawler,
    downstream_queue_cls=FifoMemoryQueue,
    key="val-002/peek-non-mutating",
)
try:
    for name in ["a1", "b1", "a2", "b2"]:
        request = Request(f"https://example.org/{name}")
        request.meta[Downloader.DOWNLOAD_SLOT] = "slot-" + name[0]
        queue.push(request)
    peeked = queue.peek().meta[Downloader.DOWNLOAD_SLOT]
    popped = queue.pop().meta[Downloader.DOWNLOAD_SLOT]
    if popped != peeked:
        raise AssertionError(
            f"peek changed slot rotation: peeked {peeked!r}, popped {popped!r}"
        )
finally:
    queue.close()
"""

PYTEST_TIMEDELTA_INVALID_TOLERANCE_CODE = r"""
from datetime import timedelta
from math import nan

from pytest import approx

assert timedelta(seconds=10) == approx(timedelta(seconds=10.5), rel=0.1)
assert timedelta(seconds=10) == approx(
    timedelta(seconds=10.9),
    abs=timedelta(seconds=1),
    rel=0.01,
)
assert not (
    timedelta(seconds=10)
    == approx(timedelta(seconds=12), abs=timedelta(seconds=1), rel=0.01)
)

for kwargs in (
    {"rel": -0.1},
    {"rel": nan},
    {"abs": timedelta(seconds=-1)},
):
    try:
        timedelta(seconds=1) == approx(timedelta(seconds=1), **kwargs)
    except ValueError:
        pass
    else:
        raise AssertionError(f"expected ValueError for {kwargs!r}")
"""


class IssuePrValidationStrengthProbeError(ValueError):
    """Raised when the VAL-002 probe input is malformed."""


@dataclass(frozen=True, slots=True)
class ValidationRecipe:
    recipe_id: str
    replay_id: str
    description: str
    label_safety: str
    leakage_risk: str
    command_kind: str

    def command_for(self, checkout: Path) -> tuple[list[str], dict[str, str]]:
        python = _python_executable(checkout)
        env = os.environ.copy()
        if self.recipe_id == "scrapy_peek_non_mutating_behavior":
            return [python, "-c", SCRAPY_PEEK_NON_MUTATING_CODE], env
        if self.recipe_id == "pytest_timedelta_invalid_tolerance_behavior":
            src = checkout / "src"
            existing = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(src) if not existing else f"{src}{os.pathsep}{existing}"
            return [python, "-c", PYTEST_TIMEDELTA_INVALID_TOLERANCE_CODE], env
        raise IssuePrValidationStrengthProbeError(
            f"unsupported validation recipe: {self.recipe_id}"
        )

    def to_record(self) -> dict[str, object]:
        return {
            "recipe_id": self.recipe_id,
            "replay_id": self.replay_id,
            "description": self.description,
            "label_safety": self.label_safety,
            "leakage_risk": self.leakage_risk,
            "command_kind": self.command_kind,
        }


RECIPES = {
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID: ValidationRecipe(
        recipe_id="scrapy_peek_non_mutating_behavior",
        replay_id=SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
        description=(
            "Issue-derived behavior probe: peek must observe the next "
            "DownloaderAwarePriorityQueue slot without advancing slot rotation."
        ),
        label_safety=(
            "Uses public queue behavior and issue semantics only; does not compare "
            "against the accepted patch or accepted test names."
        ),
        leakage_risk="low",
        command_kind="python_behavior_probe",
    ),
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID: ValidationRecipe(
        recipe_id="pytest_timedelta_invalid_tolerance_behavior",
        replay_id=PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
        description=(
            "Issue-derived behavior probe for timedelta approx relative/absolute "
            "tolerance and invalid tolerance rejection."
        ),
        label_safety=(
            "Uses public approx behavior implied by the issue. It intentionally "
            "does not check whether the candidate added the accepted regression "
            "tests, because that would leak accepted-label structure."
        ),
        leakage_risk="low",
        command_kind="python_behavior_probe",
    ),
}


def identify_passing_decoys(bundle_paths: Sequence[Path]) -> list[dict[str, object]]:
    """Return every live-validated decoy whose validation status is passed."""

    passing: list[dict[str, object]] = []
    for bundle_path in bundle_paths:
        bundle = _load_json_object(bundle_path)
        for candidate in _list_of_mappings(bundle.get("candidates")):
            validation = _mapping(candidate.get("validation"))
            if (
                candidate.get("expected_accepted") is False
                and validation.get("status") == "passed"
            ):
                record = dict(candidate)
                record["source_bundle_path"] = str(bundle_path.expanduser().resolve())
                passing.append(record)
    return passing


def build_validation_strength_probe_report(
    *,
    decoy_bundle_paths: Sequence[Path] = DEFAULT_DECOY_BUNDLE_PATHS,
    accepted_checkouts: Mapping[str, Path] | None = None,
    run_live: bool = True,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    """Build a VAL-002 report from DATA-039/DATA-040 decoy artifacts."""

    accepted_paths = {
        replay_id: path.expanduser().resolve()
        for replay_id, path in (accepted_checkouts or {}).items()
    }
    passing_decoys = identify_passing_decoys(decoy_bundle_paths)
    results = [
        _evaluate_passing_decoy(
            decoy,
            accepted_checkouts=accepted_paths,
            run_live=run_live,
            timeout_seconds=timeout_seconds,
        )
        for decoy in passing_decoys
    ]
    converted = [
        result
        for result in results
        if result.get("accepted_preserved") is True
        and result.get("passing_decoy_converted_to_failure") is True
    ]
    leakage_blocked = [
        result
        for result in results
        if result.get("product_gate_blocker")
        == "coverage_gap_decoy_indistinguishable_without_accepted_label_leakage"
    ]
    accepted_failures = [
        result for result in results if result.get("accepted_preserved") is False
    ]
    total_runtime = sum(
        _float_value(run.get("runtime_seconds"))
        for result in results
        for run in _list_of_mappings(result.get("live_runs"))
    )
    return {
        "schema_version": VALIDATION_STRENGTH_PROBE_SCHEMA_VERSION,
        "record_kind": "issue_pr_validation_strength_probe_report",
        "task_id": "VAL-002",
        "mode": "shadow_only_validation_strength_probe",
        "production_ranking_gate_changed": False,
        "hosted_llm_usage": {
            "used": False,
            "zero_hosted_usage_confirmed": True,
        },
        "summary": {
            "passing_decoy_count": len(passing_decoys),
            "recipe_count": len({result.get("recipe_id") for result in results}),
            "live_result_count": sum(
                1
                for result in results
                for run in _list_of_mappings(result.get("live_runs"))
                if run.get("status") in {"passed", "failed", "timeout"}
            ),
            "converted_passing_decoy_count": len(converted),
            "coverage_gap_blocker_count": len(leakage_blocked),
            "accepted_candidate_failure_count": len(accepted_failures),
            "runtime_seconds": round(total_runtime, 3),
            "product_gate_blockers": _sorted_unique(
                result.get("product_gate_blocker") for result in results
            ),
            "leakage_risks": _sorted_unique(
                str(result.get("leakage_risk", "")) for result in results
            ),
        },
        "recipes": [recipe.to_record() for recipe in RECIPES.values()],
        "passing_decoys": [_decoy_summary(decoy) for decoy in passing_decoys],
        "results": results,
    }


def write_validation_strength_probe_report(
    report: Mapping[str, object],
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write JSON and markdown artifacts for the VAL-002 report."""

    output = out_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_json = output / "validation-strength-report.json"
    report_md = output / "validation-strength-report.md"
    report_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_md.write_text(format_validation_strength_probe_markdown(report), encoding="utf-8")
    return {"report_json": report_json, "report_md": report_md}


def format_validation_strength_probe_markdown(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    hosted = _mapping(report.get("hosted_llm_usage"))
    lines = [
        "# VAL-002 Validation Strength Probe",
        "",
        "- Mode: shadow-only validation adequacy probe",
        "- Production ranking gate changed: false",
        f"- Hosted LLM usage: {str(hosted.get('used') is True).lower()}",
        f"- Passing decoys found: {summary.get('passing_decoy_count')}",
        f"- Converted passing decoys to failures: {summary.get('converted_passing_decoy_count')}",
        f"- Coverage-gap blockers: {summary.get('coverage_gap_blocker_count')}",
        f"- Accepted candidate failures: {summary.get('accepted_candidate_failure_count')}",
        f"- Runtime seconds: {summary.get('runtime_seconds')}",
        "",
        "| Replay | Decoy | Recipe | Accepted | Decoy | Converted | Blocker | Leakage risk |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in _list_of_mappings(report.get("results")):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result.get("replay_id", "")),
                    str(result.get("candidate_id", "")),
                    str(result.get("recipe_id", "")),
                    str(result.get("accepted_status", "")),
                    str(result.get("decoy_status", "")),
                    _yes_no(result.get("passing_decoy_converted_to_failure")),
                    str(result.get("product_gate_blocker") or ""),
                    str(result.get("leakage_risk", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            _conclusion(report),
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decoy-validation-bundle",
        action="append",
        dest="decoy_bundles",
        default=[],
        help="DATA-039/DATA-040 decoy validation bundle path. May be repeated.",
    )
    parser.add_argument(
        "--accepted-checkout",
        action="append",
        default=[],
        metavar="REPLAY_ID=PATH",
        help="Accepted candidate checkout for live behavior probes.",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--no-live", action="store_true")
    args = parser.parse_args(argv)

    bundle_paths = (
        [Path(path) for path in args.decoy_bundles]
        if args.decoy_bundles
        else list(DEFAULT_DECOY_BUNDLE_PATHS)
    )
    report = build_validation_strength_probe_report(
        decoy_bundle_paths=bundle_paths,
        accepted_checkouts=_parse_accepted_checkouts(args.accepted_checkout),
        run_live=not args.no_live,
        timeout_seconds=args.timeout_seconds,
    )
    artifacts = write_validation_strength_probe_report(report, out_dir=Path(args.out_dir))
    print(json.dumps({key: str(path) for key, path in artifacts.items()}, indent=2))
    return 0


def _evaluate_passing_decoy(
    decoy: Mapping[str, object],
    *,
    accepted_checkouts: Mapping[str, Path],
    run_live: bool,
    timeout_seconds: int,
) -> dict[str, object]:
    replay_id = str(decoy.get("replay_id", ""))
    recipe = RECIPES.get(replay_id)
    if recipe is None:
        return {
            **_decoy_summary(decoy),
            "recipe_id": None,
            "accepted_status": "not_run",
            "decoy_status": "not_run",
            "accepted_preserved": None,
            "passing_decoy_converted_to_failure": False,
            "product_gate_blocker": "no_label_safe_recipe_for_replay",
            "leakage_risk": "unknown",
            "live_runs": [],
        }
    accepted_checkout = accepted_checkouts.get(replay_id)
    decoy_checkout = Path(str(decoy.get("checkout_path", ""))).expanduser()
    live_runs: list[dict[str, object]] = []
    if run_live and accepted_checkout is not None:
        live_runs.append(
            _run_recipe(
                recipe,
                checkout=accepted_checkout,
                subject_kind="accepted_candidate",
                subject_id=f"{replay_id}:accepted",
                timeout_seconds=timeout_seconds,
            )
        )
    elif run_live:
        live_runs.append(
            _not_run(
                recipe,
                subject_kind="accepted_candidate",
                subject_id=f"{replay_id}:accepted",
                reason="accepted_checkout_unavailable",
            )
        )
    if run_live and decoy_checkout.is_dir():
        live_runs.append(
            _run_recipe(
                recipe,
                checkout=decoy_checkout,
                subject_kind="passing_decoy",
                subject_id=str(decoy.get("candidate_id", "")),
                timeout_seconds=timeout_seconds,
            )
        )
    elif run_live:
        live_runs.append(
            _not_run(
                recipe,
                subject_kind="passing_decoy",
                subject_id=str(decoy.get("candidate_id", "")),
                reason="decoy_checkout_unavailable",
            )
        )
    accepted_status = _status_for(live_runs, "accepted_candidate")
    decoy_status = _status_for(live_runs, "passing_decoy")
    accepted_preserved = accepted_status == "passed" if accepted_status != "not_run" else None
    converted = accepted_status == "passed" and decoy_status == "failed"
    product_gate_blocker = _product_gate_blocker(
        decoy=decoy,
        accepted_status=accepted_status,
        decoy_status=decoy_status,
        converted=converted,
    )
    return {
        **_decoy_summary(decoy),
        "recipe_id": recipe.recipe_id,
        "recipe_description": recipe.description,
        "accepted_status": accepted_status,
        "decoy_status": decoy_status,
        "accepted_preserved": accepted_preserved,
        "passing_decoy_converted_to_failure": converted,
        "product_gate_blocker": product_gate_blocker,
        "leakage_risk": recipe.leakage_risk,
        "label_safety": recipe.label_safety,
        "live_runs": live_runs,
    }


def _run_recipe(
    recipe: ValidationRecipe,
    *,
    checkout: Path,
    subject_kind: str,
    subject_id: str,
    timeout_seconds: int,
) -> dict[str, object]:
    command, env = recipe.command_for(checkout)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=checkout,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        runtime = time.monotonic() - started
        return {
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "checkout_path": str(checkout),
            "recipe_id": recipe.recipe_id,
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "runtime_seconds": round(runtime, 3),
            "command": _command_text(command),
            "stdout_tail": completed.stdout[-1200:],
            "stderr_tail": completed.stderr[-1200:],
        }
    except subprocess.TimeoutExpired as exc:
        runtime = time.monotonic() - started
        return {
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "checkout_path": str(checkout),
            "recipe_id": recipe.recipe_id,
            "status": "timeout",
            "returncode": None,
            "runtime_seconds": round(runtime, 3),
            "command": _command_text(command),
            "stdout_tail": (exc.stdout or "")[-1200:]
            if isinstance(exc.stdout, str)
            else "",
            "stderr_tail": (exc.stderr or "")[-1200:]
            if isinstance(exc.stderr, str)
            else "",
        }


def _product_gate_blocker(
    *,
    decoy: Mapping[str, object],
    accepted_status: str,
    decoy_status: str,
    converted: bool,
) -> str | None:
    if accepted_status == "failed":
        return "stronger_validation_breaks_accepted_candidate"
    if converted:
        return None
    labels = set(_string_list(decoy.get("residual_labels")))
    if {"coverage_gap", "test_decoy"} & labels:
        return "coverage_gap_decoy_indistinguishable_without_accepted_label_leakage"
    if accepted_status == "not_run" or decoy_status == "not_run":
        return "live_validation_recipe_not_fully_run"
    if decoy_status == "passed":
        return "semantic_decoy_still_passes_stronger_validation"
    if decoy_status == "timeout":
        return "stronger_validation_timed_out"
    return "validation_strength_probe_inconclusive"


def _not_run(
    recipe: ValidationRecipe,
    *,
    subject_kind: str,
    subject_id: str,
    reason: str,
) -> dict[str, object]:
    return {
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "recipe_id": recipe.recipe_id,
        "status": "not_run",
        "reason": reason,
        "runtime_seconds": 0.0,
    }


def _status_for(runs: Sequence[Mapping[str, object]], subject_kind: str) -> str:
    for run in runs:
        if run.get("subject_kind") == subject_kind:
            status = str(run.get("status", ""))
            return status or "not_run"
    return "not_run"


def _decoy_summary(decoy: Mapping[str, object]) -> dict[str, object]:
    validation = _mapping(decoy.get("validation"))
    return {
        "candidate_id": str(decoy.get("candidate_id", "")),
        "decoy_id": str(decoy.get("decoy_id", "")),
        "replay_id": str(decoy.get("replay_id", "")),
        "repo": str(decoy.get("repo", "")),
        "validation_status": str(validation.get("status", "")),
        "targeted_mistakes": _string_list(
            _mapping(decoy.get("decoy_evidence")).get("targeted_mistakes")
        ),
        "residual_labels": _string_list(decoy.get("residual_labels")),
        "touched_file_paths": _string_list(decoy.get("touched_file_paths")),
        "checkout_path": str(decoy.get("checkout_path", "")),
    }


def _conclusion(report: Mapping[str, object]) -> str:
    summary = _mapping(report.get("summary"))
    converted = _int_value(summary.get("converted_passing_decoy_count"))
    blockers = set(_string_list(summary.get("product_gate_blockers")))
    if converted and "coverage_gap_decoy_indistinguishable_without_accepted_label_leakage" in blockers:
        return (
            "The label-safe behavior recipe converts at least one semantic passing "
            "decoy into a failure while preserving the accepted candidate, but "
            "coverage-gap decoys remain product-gate blockers because runtime "
            "behavior matches the accepted source and failing them would require "
            "accepted-test or accepted-diff leakage."
        )
    if blockers:
        return (
            "The stronger recipes did not produce a clean accepted-versus-decoy "
            "validation set. Issue/PR ranking must remain shadow-only."
        )
    return "The stronger recipes produced no product-gate blocker."


def _parse_accepted_checkouts(values: Sequence[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise IssuePrValidationStrengthProbeError(
                f"accepted checkout must use REPLAY_ID=PATH: {value}"
            )
        replay_id, path = value.split("=", 1)
        parsed[replay_id] = Path(path)
    return parsed


def _load_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IssuePrValidationStrengthProbeError(
            f"expected JSON object in {path}"
        )
    return payload


def _python_executable(checkout: Path) -> str:
    venv_python = checkout / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def _command_text(command: Sequence[str]) -> str:
    if len(command) >= 3 and command[1] == "-c":
        return f"{command[0]} -c <{len(command[2])} chars>"
    return " ".join(command)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


def _sorted_unique(values: object) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return 0


def _yes_no(value: object) -> str:
    return "yes" if value is True else "no"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
