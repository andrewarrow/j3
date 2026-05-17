"""Build local transition evidence bundles for release verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from j3.transition_action_scoring import TRANSITION_ACTION_SCORER_V3_REPORT_VERSION
from j3.transition_assets import inspect_transition_assets
from j3.transition_bench_demo import TRANSITION_BENCH_DEMO_REPORT_VERSION
from j3.transition_residuals import report_transition_residual_matrix
from j3.transition_scorer_advice import summarize_transition_scorer_advice


TRANSITION_EVIDENCE_BUNDLE_VERSION = "transition-evidence-bundle-v1"
TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION = "transition-matrix-evidence-bundle-v1"
TRANSITION_SHADOW_MATRIX_VERSION = "transition-shadow-matrix-run-v1"
PRODUCT_READINESS_GATE_BUNDLE_VERSION = "transition-evidence-product-gate-v1"

BUNDLE_MANIFEST = "manifest.json"
BUNDLE_CHECKSUMS = "checksums.sha256"
BUNDLE_TRANSITION_ASSETS = "transition-assets.json"
BUNDLE_TRANSITION_BENCH_REPORT = "transition-bench-report.json"
BUNDLE_SHADOW_ADVICE_SUMMARY = "shadow-advice-summary.json"
BUNDLE_PRODUCT_GATE = "product-readiness-gate.json"
BUNDLE_REPRODUCTION_COMMANDS = "reproduction-commands.json"
BUNDLE_REPRODUCE_MD = "REPRODUCE.md"
BUNDLE_SHADOW_SCORER_V3_REPORT = "transition-shadow-scorer-v3-report.json"
BUNDLE_MATRIX_MANIFEST = "matrix-manifest.json"
BUNDLE_MATRIX_SUMMARY = "matrix-summary.json"
BUNDLE_MATRIX_PRODUCT_GATES = "matrix-product-gates.json"
BUNDLE_MATRIX_RESIDUAL_REPORT = "matrix-residual-report.json"
BUNDLE_ZERO_HOSTED_USAGE = "zero-hosted-usage.json"

_BASE_ARTIFACTS = {
    BUNDLE_MANIFEST,
    BUNDLE_CHECKSUMS,
    BUNDLE_TRANSITION_ASSETS,
    BUNDLE_TRANSITION_BENCH_REPORT,
    BUNDLE_SHADOW_ADVICE_SUMMARY,
    BUNDLE_PRODUCT_GATE,
    BUNDLE_REPRODUCTION_COMMANDS,
    BUNDLE_REPRODUCE_MD,
    BUNDLE_SHADOW_SCORER_V3_REPORT,
    BUNDLE_MATRIX_MANIFEST,
    BUNDLE_MATRIX_SUMMARY,
    BUNDLE_MATRIX_PRODUCT_GATES,
    BUNDLE_MATRIX_RESIDUAL_REPORT,
    BUNDLE_ZERO_HOSTED_USAGE,
}


def build_transition_evidence_bundle(
    *,
    bench_report: Path,
    out_dir: Path,
    repo_root: Path = Path("."),
    prompt_corpus: Path | None = None,
    advice_paths: Sequence[Path] = (),
    shadow_scorer_report: Path | None = None,
    force: bool = False,
) -> dict[str, object]:
    """Build a verifiable local transition evidence bundle directory."""

    out = out_dir.expanduser().resolve()
    _prepare_out_dir(out, force=force)

    bench_report_record = _load_json_report(
        bench_report,
        expected_schema=TRANSITION_BENCH_DEMO_REPORT_VERSION,
        label="transition bench report",
    )
    shadow_scorer_record = (
        _load_json_report(
            shadow_scorer_report,
            expected_schema=TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
            label="transition shadow scorer V3 report",
        )
        if shadow_scorer_report is not None
        else None
    )

    _assert_zero_hosted_usage(
        {
            "transition-bench-report": bench_report_record,
            **(
                {"transition-shadow-scorer-v3-report": shadow_scorer_record}
                if shadow_scorer_record is not None
                else {}
            ),
        }
    )

    repo = repo_root.expanduser().resolve()
    asset_inventory = inspect_transition_assets(
        repo_root=repo,
        prompt_corpus=prompt_corpus,
    )
    advice_summary = summarize_transition_scorer_advice(advice_paths).as_dict()
    _assert_zero_hosted_usage(
        {
            "shadow-advice-summary": advice_summary,
        }
    )

    _write_json(out / BUNDLE_TRANSITION_ASSETS, asset_inventory)
    _write_json(out / BUNDLE_TRANSITION_BENCH_REPORT, bench_report_record)
    _write_json(out / BUNDLE_SHADOW_ADVICE_SUMMARY, advice_summary)
    if shadow_scorer_record is not None:
        _write_json(out / BUNDLE_SHADOW_SCORER_V3_REPORT, shadow_scorer_record)

    gate = _product_gate_record(
        bench_report=bench_report_record,
        shadow_scorer_report=shadow_scorer_record,
    )
    _write_json(out / BUNDLE_PRODUCT_GATE, gate)

    reproduction = _reproduction_commands(
        out=out,
        repo_root=repo,
        prompt_corpus=prompt_corpus,
        bench_report=bench_report_record,
        advice_paths=advice_paths,
        shadow_scorer_report=shadow_scorer_report,
    )
    _write_json(out / BUNDLE_REPRODUCTION_COMMANDS, reproduction)
    (out / BUNDLE_REPRODUCE_MD).write_text(
        _format_reproduce_markdown(reproduction),
        encoding="utf-8",
    )

    manifest = _manifest_record(
        out=out,
        repo_root=repo,
        bench_report=bench_report,
        shadow_scorer_report=shadow_scorer_report,
        advice_paths=advice_paths,
        gate=gate,
        reproduction=reproduction,
    )
    packaged_artifacts = _artifact_records(
        out,
        exclude={BUNDLE_MANIFEST, BUNDLE_CHECKSUMS},
    )
    manifest = {
        **manifest,
        "checksums": {
            "path": BUNDLE_CHECKSUMS,
            "algorithm": "sha256",
            "artifact_count": len(packaged_artifacts) + 1,
        },
        "artifacts": packaged_artifacts,
    }
    _write_json(out / BUNDLE_MANIFEST, manifest)
    checksums = _write_checksums(out)

    return {
        "schema_version": TRANSITION_EVIDENCE_BUNDLE_VERSION,
        "out": str(out),
        "manifest": str(out / BUNDLE_MANIFEST),
        "checksums": str(out / BUNDLE_CHECKSUMS),
        "artifact_count": len(checksums),
        "product_gate": gate,
        "zero_hosted_usage": True,
    }


def build_transition_matrix_evidence_bundle(
    *,
    matrix_dir: Path,
    out_dir: Path,
    repo_root: Path = Path("."),
    residual_example_limit: int = 20,
    force: bool = False,
) -> dict[str, object]:
    """Build a verifiable transition shadow matrix evidence bundle directory."""

    out = out_dir.expanduser().resolve()
    _prepare_out_dir(out, force=force)

    matrix = matrix_dir.expanduser().resolve()
    if not matrix.exists():
        raise FileNotFoundError(f"matrix output directory does not exist: {matrix}")
    if not matrix.is_dir():
        raise NotADirectoryError(f"matrix output path is not a directory: {matrix}")

    matrix_manifest = _load_json_object(
        matrix / BUNDLE_MATRIX_MANIFEST,
        expected_schema=TRANSITION_SHADOW_MATRIX_VERSION,
        label="matrix manifest",
    )
    matrix_summary = _load_json_object(
        matrix / BUNDLE_MATRIX_SUMMARY,
        expected_schema=TRANSITION_SHADOW_MATRIX_VERSION,
        label="matrix summary",
    )
    _assert_zero_hosted_usage({"matrix-summary": matrix_summary})
    if matrix_summary.get("zero_hosted_usage") is not True:
        raise ValueError("matrix evidence bundle requires zero hosted usage")

    product_gates = _matrix_product_gates(matrix=matrix, matrix_summary=matrix_summary)
    residual_report = report_transition_residual_matrix(
        matrix_dir=matrix,
        example_limit=residual_example_limit,
    )
    zero_hosted_usage = _zero_hosted_usage_record(
        matrix_summary=matrix_summary,
        product_gates=product_gates,
        residual_report=residual_report,
    )
    if zero_hosted_usage.get("verified_zero") is not True:
        raise ValueError("matrix evidence bundle requires zero hosted usage")
    _assert_zero_hosted_usage(
        {
            "matrix-product-gates": product_gates,
            "matrix-residual-report": residual_report,
            "zero-hosted-usage": zero_hosted_usage,
        }
    )

    _write_json(out / BUNDLE_MATRIX_MANIFEST, matrix_manifest)
    _write_json(out / BUNDLE_MATRIX_SUMMARY, matrix_summary)
    _write_json(out / BUNDLE_MATRIX_PRODUCT_GATES, product_gates)
    _write_json(out / BUNDLE_MATRIX_RESIDUAL_REPORT, residual_report)
    _write_json(out / BUNDLE_ZERO_HOSTED_USAGE, zero_hosted_usage)

    reproduction = _matrix_reproduction_commands(
        out=out,
        matrix=matrix,
        repo_root=repo_root.expanduser().resolve(),
        residual_example_limit=residual_example_limit,
    )
    _write_json(out / BUNDLE_REPRODUCTION_COMMANDS, reproduction)
    (out / BUNDLE_REPRODUCE_MD).write_text(
        _format_reproduce_markdown(reproduction),
        encoding="utf-8",
    )

    manifest = _matrix_manifest_record(
        out=out,
        repo_root=repo_root.expanduser().resolve(),
        matrix=matrix,
        matrix_summary=matrix_summary,
        product_gates=product_gates,
        residual_report=residual_report,
        zero_hosted_usage=zero_hosted_usage,
        reproduction=reproduction,
    )
    packaged_artifacts = _artifact_records(
        out,
        exclude={BUNDLE_MANIFEST, BUNDLE_CHECKSUMS},
    )
    manifest = {
        **manifest,
        "checksums": {
            "path": BUNDLE_CHECKSUMS,
            "algorithm": "sha256",
            "artifact_count": len(packaged_artifacts) + 1,
        },
        "artifacts": packaged_artifacts,
    }
    _write_json(out / BUNDLE_MANIFEST, manifest)
    checksums = _write_checksums(out)

    return {
        "schema_version": TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION,
        "out": str(out),
        "manifest": str(out / BUNDLE_MANIFEST),
        "checksums": str(out / BUNDLE_CHECKSUMS),
        "artifact_count": len(checksums),
        "matrix_product_gates": product_gates,
        "zero_hosted_usage": True,
    }


def format_transition_evidence_bundle_summary(summary: Mapping[str, object]) -> str:
    """Format the bundle build result for human CLI output."""

    gate = _mapping(summary.get("product_gate"))
    matrix_gates = _mapping(summary.get("matrix_product_gates"))
    effective = _mapping(gate.get("effective_gate"))
    lines = [
        "j3 build-transition-evidence-bundle complete",
        f"out: {summary.get('out')}",
        f"manifest: {summary.get('manifest')}",
        f"checksums: {summary.get('checksums')}",
        f"artifacts: {summary.get('artifact_count')}",
        f"zero hosted usage: {str(summary.get('zero_hosted_usage')).lower()}",
    ]
    if effective:
        lines.append(f"product gate: {effective.get('gate_result')}")
        eligible = effective.get("eligible_for_guarded_opt_in")
        if eligible is not None:
            lines.append(f"guarded opt-in eligible: {str(bool(eligible)).lower()}")
    if matrix_gates:
        totals = _mapping(matrix_gates.get("totals"))
        lines.append(f"matrix suites: {totals.get('suite_count', 0)}")
        lines.append(
            "guarded opt-in eligible suites: "
            f"{totals.get('guarded_opt_in_eligible_suite_count', 0)}"
        )
    return "\n".join(lines)


def _prepare_out_dir(out: Path, *, force: bool) -> None:
    if out.exists() and not out.is_dir():
        raise NotADirectoryError(f"bundle output path is not a directory: {out}")
    if out.exists():
        entries = list(out.iterdir())
        if entries and not force:
            raise FileExistsError(
                f"bundle output directory is not empty: {out}; pass --force to overwrite bundle files"
            )
        unknown = [entry for entry in entries if entry.name not in _BASE_ARTIFACTS]
        if unknown:
            raise FileExistsError(
                "bundle output directory contains unknown files: "
                + ", ".join(str(path) for path in unknown)
            )
        for entry in entries:
            if entry.is_file():
                entry.unlink()
            else:
                raise FileExistsError(f"bundle output contains a directory: {entry}")
    out.mkdir(parents=True, exist_ok=True)


def _load_json_report(path: Path | None, *, expected_schema: str, label: str) -> dict[str, object]:
    if path is None:
        raise FileNotFoundError(f"{label} path is required")
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {resolved}")
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not valid JSON: {resolved}") from error
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be a JSON object: {resolved}")
    if loaded.get("schema_version") != expected_schema:
        raise ValueError(
            f"{label} expected schema_version {expected_schema}, got {loaded.get('schema_version')}"
        )
    return loaded


def _load_json_object(
    path: Path,
    *,
    expected_schema: str | None = None,
    label: str,
) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {resolved}")
    try:
        loaded = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not valid JSON: {resolved}") from error
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} must be a JSON object: {resolved}")
    if expected_schema is not None and loaded.get("schema_version") != expected_schema:
        raise ValueError(
            f"{label} expected schema_version {expected_schema}, got {loaded.get('schema_version')}"
        )
    return loaded


def _assert_zero_hosted_usage(reports: Mapping[str, object]) -> None:
    nonzero: list[str] = []
    for name, report in reports.items():
        for path, value in _hosted_usage_values(report):
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and value != 0:
                nonzero.append(f"{name}.{path}={value}")
    if nonzero:
        raise ValueError(
            "evidence bundle requires zero hosted API/context usage; found "
            + ", ".join(nonzero)
        )


def _hosted_usage_values(value: object, *, prefix: str = "") -> list[tuple[str, object]]:
    values: list[tuple[str, object]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.startswith("hosted_"):
                values.append((path, item))
            values.extend(_hosted_usage_values(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            values.extend(_hosted_usage_values(item, prefix=f"{prefix}[{index}]"))
    return values


def _product_gate_record(
    *,
    bench_report: Mapping[str, object],
    shadow_scorer_report: Mapping[str, object] | None,
) -> dict[str, object]:
    bench_gate = _mapping(bench_report.get("product_readiness"))
    v3_validation = _mapping(_mapping(shadow_scorer_report or {}).get("validation"))
    v3_gate = _mapping(v3_validation.get("product_readiness"))
    effective = v3_gate if v3_gate else bench_gate
    return {
        "schema_version": PRODUCT_READINESS_GATE_BUNDLE_VERSION,
        "effective_source": (
            BUNDLE_SHADOW_SCORER_V3_REPORT if v3_gate else BUNDLE_TRANSITION_BENCH_REPORT
        ),
        "effective_gate": dict(effective),
        "transition_bench": {
            "report": BUNDLE_TRANSITION_BENCH_REPORT,
            "product_readiness": dict(bench_gate),
        },
        "shadow_scorer_v3": {
            "provided": shadow_scorer_report is not None,
            "report": (
                BUNDLE_SHADOW_SCORER_V3_REPORT
                if shadow_scorer_report is not None
                else None
            ),
            "product_readiness": dict(v3_gate),
        },
        "zero_hosted_usage": True,
    }


def _reproduction_commands(
    *,
    out: Path,
    repo_root: Path,
    prompt_corpus: Path | None,
    bench_report: Mapping[str, object],
    advice_paths: Sequence[Path],
    shadow_scorer_report: Path | None,
) -> dict[str, object]:
    bench_command = _bench_rebuild_command(
        repo_root=repo_root,
        prompt_corpus=prompt_corpus,
        report=bench_report,
        out=out / BUNDLE_TRANSITION_BENCH_REPORT,
    )
    commands = {
        "verify_json": [
            f"python -m json.tool {out / BUNDLE_MANIFEST} >/dev/null",
            f"python -m json.tool {out / BUNDLE_TRANSITION_ASSETS} >/dev/null",
            f"python -m json.tool {out / BUNDLE_TRANSITION_BENCH_REPORT} >/dev/null",
            f"python -m json.tool {out / BUNDLE_PRODUCT_GATE} >/dev/null",
            f"python -m json.tool {out / BUNDLE_SHADOW_ADVICE_SUMMARY} >/dev/null",
        ],
        "verify_checksums": [
            f"shasum -a 256 -c {out / BUNDLE_CHECKSUMS}",
        ],
        "rebuild_transition_assets": [
            _shell_join(
                [
                    "python",
                    "cli.py",
                    "inspect-transition-assets",
                    "--repo-root",
                    str(repo_root),
                    "--prompt-corpus",
                    str(_resolve_prompt_corpus(prompt_corpus, repo_root)),
                    "--out",
                    str(out / BUNDLE_TRANSITION_ASSETS),
                ]
            )
        ],
        "rebuild_transition_bench_report": [bench_command],
    }
    if advice_paths:
        commands["rebuild_shadow_advice_summary"] = [
            _shell_join(
                [
                    "python",
                    "cli.py",
                    "summarize-transition-advice",
                    "--advice",
                    *(str(path.expanduser().resolve()) for path in advice_paths),
                    "--json",
                ]
            )
        ]
    if shadow_scorer_report is not None:
        commands["shadow_scorer_v3_report"] = [
            f"python -m json.tool {out / BUNDLE_SHADOW_SCORER_V3_REPORT} >/dev/null"
        ]
    return {
        "schema_version": "transition-evidence-reproduction-commands-v1",
        "working_directory": str(repo_root),
        "hosted_usage_expectation": "all commands are local and require no hosted APIs",
        "commands": commands,
    }


def _bench_rebuild_command(
    *,
    repo_root: Path,
    prompt_corpus: Path | None,
    report: Mapping[str, object],
    out: Path,
) -> str:
    parameters = _mapping(report.get("parameters"))
    sources = _mapping(report.get("sources"))
    command = [
        "python",
        "cli.py",
        "demo-transition-bench",
        "--repo-root",
        str(repo_root),
        "--prompt-corpus",
        str(_resolve_prompt_corpus(prompt_corpus, repo_root)),
        "--embedding-dim",
        str(parameters.get("embedding_dim", 256)),
        "--top-k",
        str(parameters.get("top_k", 3)),
        "--residual-limit",
        str(parameters.get("residual_limit", 10)),
    ]
    if report.get("uses_checked_in_fixtures") is False:
        command.append("--no-fixtures")
    command.extend(
        _source_args(
            "--prompt-repo-transitions",
            _list(sources.get("prompt_repo_transition_files")),
        )
    )
    command.extend(
        _source_args("--mined-transitions", _list(sources.get("mined_git_transition_files")))
    )
    command.extend(
        _source_args("--candidate-outcomes", _list(sources.get("candidate_outcome_files")))
    )
    command.extend(["--out", str(out)])
    return _shell_join(command)


def _source_args(flag: str, source_records: Sequence[object]) -> list[str]:
    paths: list[str] = []
    for record in source_records:
        if not isinstance(record, Mapping):
            continue
        path = record.get("path")
        if isinstance(path, str) and path:
            paths.append(path)
    if not paths:
        return []
    return [flag, *paths]


def _manifest_record(
    *,
    out: Path,
    repo_root: Path,
    bench_report: Path,
    shadow_scorer_report: Path | None,
    advice_paths: Sequence[Path],
    gate: Mapping[str, object],
    reproduction: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_version": TRANSITION_EVIDENCE_BUNDLE_VERSION,
        "name": "j3-transition-evidence",
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "git_commit": _git_commit(repo_root),
        "repo_root": str(repo_root),
        "bundle_path": str(out),
        "inputs": {
            "bench_report": str(bench_report.expanduser().resolve()),
            "shadow_scorer_report": (
                str(shadow_scorer_report.expanduser().resolve())
                if shadow_scorer_report is not None
                else None
            ),
            "advice_paths": [
                str(path.expanduser().resolve()) for path in advice_paths
            ],
        },
        "schema_versions": {
            "manifest": TRANSITION_EVIDENCE_BUNDLE_VERSION,
            "transition_assets": "transition-asset-inventory-v1",
            "transition_bench_report": TRANSITION_BENCH_DEMO_REPORT_VERSION,
            "shadow_advice_summary": "transition-scorer-advice-summary-v1",
            "product_gate": PRODUCT_READINESS_GATE_BUNDLE_VERSION,
            "shadow_scorer_v3_report": TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
        },
        "bundle_files": _bundle_files(out),
        "product_readiness": dict(gate),
        "reproduction": reproduction,
        "hosted_usage": {
            "verified_zero": True,
            "policy": "bundle generation and reproduction commands use local files only",
        },
        "environment_notes": [
            "Generated benchmark data, reports, and bundles should stay out of git.",
            "The bundle is verifiable with json.tool and SHA-256 checksums.",
        ],
    }


def _matrix_product_gates(
    *,
    matrix: Path,
    matrix_summary: Mapping[str, object],
) -> dict[str, object]:
    suite_records = []
    for suite in _list(matrix_summary.get("suites")):
        suite_record = _mapping(suite)
        suite_manifest = _load_matrix_suite_manifest(matrix, suite_record)
        suite_shadow = _mapping(suite_manifest.get("shadow_scorer_v3"))
        readiness = _mapping(_mapping(suite_shadow.get("validation")).get("product_readiness"))
        if not readiness:
            readiness = {
                "gate_result": suite_record.get("v3_gate"),
                "eligible_for_shadow_mode": suite_record.get("eligible_for_shadow_mode"),
                "eligible_for_guarded_opt_in": suite_record.get(
                    "eligible_for_guarded_opt_in"
                ),
                "residual_count": suite_record.get("residual_count"),
                "baseline_residual_count": suite_record.get("baseline_residual_count"),
                "metrics": {
                    "v3_vs_existing_rank_order": suite_record.get(
                        "v3_vs_existing_rank_order"
                    )
                },
            }
        usage = _mapping(suite_manifest.get("usage"))
        suite_records.append(
            {
                "suite_id": suite_record.get("id"),
                "task_count": suite_record.get("task_count"),
                "ranked_solved": suite_record.get("ranked_solved"),
                "held_out_group_count": suite_record.get("held_out_group_count"),
                "manifest": str(_matrix_suite_manifest_path(matrix, suite_record)),
                "gate_result": readiness.get("gate_result"),
                "eligible_for_shadow_mode": readiness.get("eligible_for_shadow_mode"),
                "eligible_for_guarded_opt_in": readiness.get(
                    "eligible_for_guarded_opt_in"
                ),
                "product_readiness": dict(readiness),
                "v3_vs_existing_rank_order": suite_record.get(
                    "v3_vs_existing_rank_order"
                ),
                "zero_hosted_usage": suite_manifest.get("zero_hosted_usage") is True
                and all(
                    value == 0
                    for path, value in _hosted_usage_values(usage)
                    if not isinstance(value, bool)
                ),
            }
        )
    return {
        "schema_version": "transition-matrix-product-gates-v1",
        "matrix": str(matrix),
        "matrix_summary": str(matrix / BUNDLE_MATRIX_SUMMARY),
        "suites": suite_records,
        "totals": {
            "suite_count": len(suite_records),
            "shadow_mode_eligible_suite_count": sum(
                1 for suite in suite_records if suite.get("eligible_for_shadow_mode") is True
            ),
            "guarded_opt_in_eligible_suite_count": sum(
                1
                for suite in suite_records
                if suite.get("eligible_for_guarded_opt_in") is True
            ),
        },
        "zero_hosted_usage": all(
            suite.get("zero_hosted_usage") is True for suite in suite_records
        ),
    }


def _load_matrix_suite_manifest(
    matrix: Path,
    suite_record: Mapping[str, object],
) -> dict[str, object]:
    return _load_json_object(
        _matrix_suite_manifest_path(matrix, suite_record),
        label=f"matrix suite manifest {suite_record.get('id')}",
    )


def _matrix_suite_manifest_path(
    matrix: Path,
    suite_record: Mapping[str, object],
) -> Path:
    manifest = suite_record.get("manifest")
    if isinstance(manifest, str) and manifest:
        path = Path(manifest).expanduser()
        return path if path.is_absolute() else (matrix / path).resolve()
    suite_id = str(suite_record.get("id", "")).strip()
    if not suite_id:
        raise ValueError("matrix summary suite record is missing id")
    return matrix / "suite" / suite_id / "manifest.json"


def _zero_hosted_usage_record(
    *,
    matrix_summary: Mapping[str, object],
    product_gates: Mapping[str, object],
    residual_report: Mapping[str, object],
) -> dict[str, object]:
    usage = {
        "matrix_summary": _mapping(matrix_summary.get("usage")),
        "matrix_product_gates": {
            "zero_hosted_usage": product_gates.get("zero_hosted_usage") is True,
        },
        "matrix_residual_report": _mapping(residual_report.get("usage")),
    }
    return {
        "schema_version": "transition-evidence-zero-hosted-usage-v1",
        "verified_zero": matrix_summary.get("zero_hosted_usage") is True
        and product_gates.get("zero_hosted_usage") is True
        and all(
            value == 0
            for _, value in _hosted_usage_values(residual_report)
            if not isinstance(value, bool)
        ),
        "policy": "bundle generation and reproduction commands use local files only",
        "usage": usage,
        "assertions": [
            "No hosted LLM API calls are required to build or inspect this bundle.",
            "No hosted repository-context bytes are required to reproduce matrix evidence.",
            "Generated JSONL files remain in the matrix output and are not packaged by default.",
        ],
    }


def _matrix_reproduction_commands(
    *,
    out: Path,
    matrix: Path,
    repo_root: Path,
    residual_example_limit: int,
) -> dict[str, object]:
    return {
        "schema_version": "transition-evidence-reproduction-commands-v1",
        "working_directory": str(repo_root),
        "hosted_usage_expectation": "all commands are local and require no hosted APIs",
        "commands": {
            "verify_json": [
                f"python -m json.tool {out / BUNDLE_MANIFEST} >/dev/null",
                f"python -m json.tool {out / BUNDLE_MATRIX_MANIFEST} >/dev/null",
                f"python -m json.tool {out / BUNDLE_MATRIX_SUMMARY} >/dev/null",
                f"python -m json.tool {out / BUNDLE_MATRIX_PRODUCT_GATES} >/dev/null",
                f"python -m json.tool {out / BUNDLE_MATRIX_RESIDUAL_REPORT} >/dev/null",
                f"python -m json.tool {out / BUNDLE_ZERO_HOSTED_USAGE} >/dev/null",
            ],
            "verify_checksums": [
                f"shasum -a 256 -c {out / BUNDLE_CHECKSUMS}",
            ],
            "rebuild_matrix_evidence_bundle": [
                _shell_join(
                    [
                        "python",
                        "cli.py",
                        "build-transition-evidence-bundle",
                        "--matrix",
                        str(matrix),
                        "--out",
                        str(out),
                        "--repo-root",
                        str(repo_root),
                        "--residual-example-limit",
                        str(residual_example_limit),
                        "--force",
                    ]
                )
            ],
            "rebuild_matrix_residual_report": [
                _shell_join(
                    [
                        "python",
                        "cli.py",
                        "report-transition-residuals",
                        "--matrix",
                        str(matrix),
                        "--example-limit",
                        str(residual_example_limit),
                        "--out",
                        str(out / BUNDLE_MATRIX_RESIDUAL_REPORT),
                        "--json",
                    ]
                )
            ],
        },
    }


def _matrix_manifest_record(
    *,
    out: Path,
    repo_root: Path,
    matrix: Path,
    matrix_summary: Mapping[str, object],
    product_gates: Mapping[str, object],
    residual_report: Mapping[str, object],
    zero_hosted_usage: Mapping[str, object],
    reproduction: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_version": TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION,
        "name": "j3-transition-matrix-evidence",
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "git_commit": _git_commit(repo_root),
        "repo_root": str(repo_root),
        "bundle_path": str(out),
        "inputs": {
            "matrix": str(matrix),
            "matrix_manifest": str(matrix / BUNDLE_MATRIX_MANIFEST),
            "matrix_summary": str(matrix / BUNDLE_MATRIX_SUMMARY),
        },
        "schema_versions": {
            "manifest": TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION,
            "matrix_manifest": TRANSITION_SHADOW_MATRIX_VERSION,
            "matrix_summary": TRANSITION_SHADOW_MATRIX_VERSION,
            "matrix_product_gates": "transition-matrix-product-gates-v1",
            "matrix_residual_report": str(residual_report.get("schema_version")),
            "zero_hosted_usage": str(zero_hosted_usage.get("schema_version")),
        },
        "bundle_files": _bundle_files(out),
        "matrix": {
            "totals": matrix_summary.get("totals"),
            "zero_hosted_usage": matrix_summary.get("zero_hosted_usage") is True,
        },
        "product_gates": product_gates,
        "residual_summary": residual_report.get("summary"),
        "reproduction": reproduction,
        "hosted_usage": {
            "verified_zero": zero_hosted_usage.get("verified_zero") is True,
            "policy": "bundle generation and reproduction commands use local files only",
        },
        "environment_notes": [
            "Generated JSONL files are intentionally not packaged by default.",
            "The bundle is verifiable with json.tool and SHA-256 checksums.",
        ],
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_checksums(out: Path) -> list[dict[str, object]]:
    records = _artifact_records(out, exclude={BUNDLE_CHECKSUMS})
    lines = [
        f"{record['sha256']}  {record['path']}"
        for record in records
        if isinstance(record.get("sha256"), str)
    ]
    (out / BUNDLE_CHECKSUMS).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return records


def _artifact_records(
    out: Path,
    *,
    exclude: set[str] | None = None,
) -> list[dict[str, object]]:
    excluded = exclude or set()
    records = []
    for path in sorted(out.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        stat = path.stat()
        records.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _bundle_files(out: Path) -> list[str]:
    return [path.name for path in sorted(out.iterdir()) if path.is_file()]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _resolve_prompt_corpus(path: Path | None, repo_root: Path) -> Path:
    target = path or Path("../prompts/coding_agent_prompts_expanded_v0.jsonl")
    expanded = target.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (repo_root / expanded).resolve()


def _format_reproduce_markdown(reproduction: Mapping[str, object]) -> str:
    commands = _mapping(reproduction.get("commands"))
    lines = [
        "# Reproduce j3 Transition Evidence",
        "",
        "These commands verify the bundle locally without hosted APIs.",
        "",
    ]
    for section, values in commands.items():
        lines.append(f"## {section}")
        lines.append("")
        for command in _list(values):
            if isinstance(command, str):
                lines.append("```bash")
                lines.append(command)
                lines.append("```")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _shell_join(parts: Sequence[str]) -> str:
    return " ".join(_shell_quote(str(part)) for part in parts)


def _shell_quote(value: str) -> str:
    if value and all(ch.isalnum() or ch in "@%_+=:,./-" for ch in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []
