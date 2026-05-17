from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import main
from j3.transition_action_scoring import (
    GATE_READY_FOR_GUARDED_OPT_IN,
    TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
)
from j3.transition_bench_demo import run_transition_bench_demo
from j3.transition_evidence_bundle import (
    BUNDLE_CHECKSUMS,
    BUNDLE_MANIFEST,
    BUNDLE_MATRIX_MANIFEST,
    BUNDLE_MATRIX_PRODUCT_GATES,
    BUNDLE_MATRIX_RESIDUAL_REPORT,
    BUNDLE_MATRIX_SUMMARY,
    BUNDLE_PRODUCT_GATE,
    BUNDLE_REPRODUCTION_COMMANDS,
    BUNDLE_SHADOW_ADVICE_SUMMARY,
    BUNDLE_SHADOW_SCORER_V3_REPORT,
    BUNDLE_TRANSITION_ASSETS,
    BUNDLE_TRANSITION_BENCH_REPORT,
    BUNDLE_ZERO_HOSTED_USAGE,
    TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION,
    TRANSITION_EVIDENCE_BUNDLE_VERSION,
    build_transition_matrix_evidence_bundle,
    build_transition_evidence_bundle,
)


FIXTURES = Path("examples/transition_bench")


def test_transition_evidence_bundle_contains_manifest_reports_and_checksums(
    tmp_path: Path,
) -> None:
    bench_report_path = tmp_path / "bench-report.json"
    bench_report = run_transition_bench_demo(
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
        embedding_dim=8,
        top_k=1,
        out=bench_report_path,
    )
    out = tmp_path / "bundle"

    summary = build_transition_evidence_bundle(
        bench_report=bench_report_path,
        out_dir=out,
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
    )

    assert summary["schema_version"] == TRANSITION_EVIDENCE_BUNDLE_VERSION
    assert summary["out"] == str(out.resolve())
    for name in (
        BUNDLE_MANIFEST,
        BUNDLE_CHECKSUMS,
        BUNDLE_TRANSITION_ASSETS,
        BUNDLE_TRANSITION_BENCH_REPORT,
        BUNDLE_SHADOW_ADVICE_SUMMARY,
        BUNDLE_PRODUCT_GATE,
        BUNDLE_REPRODUCTION_COMMANDS,
        "REPRODUCE.md",
    ):
        assert (out / name).is_file()

    manifest = json.loads((out / BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == TRANSITION_EVIDENCE_BUNDLE_VERSION
    assert manifest["inputs"]["bench_report"] == str(bench_report_path.resolve())
    assert manifest["hosted_usage"]["verified_zero"] is True
    assert manifest["checksums"]["algorithm"] == "sha256"
    assert manifest["schema_versions"]["transition_bench_report"] == (
        "transition-bench-demo-report-v1"
    )

    copied_bench = json.loads(
        (out / BUNDLE_TRANSITION_BENCH_REPORT).read_text(encoding="utf-8")
    )
    assert copied_bench == bench_report
    assert copied_bench["runtime"]["hosted_llm_api_calls"] == 0
    assert copied_bench["runtime"]["hosted_repo_context_bytes"] == 0

    assets = json.loads((out / BUNDLE_TRANSITION_ASSETS).read_text(encoding="utf-8"))
    assert assets["schema_version"] == "transition-asset-inventory-v1"
    assert assets["repo_root"] == str(tmp_path.resolve())

    advice = json.loads(
        (out / BUNDLE_SHADOW_ADVICE_SUMMARY).read_text(encoding="utf-8")
    )
    assert advice["schema_version"] == "transition-scorer-advice-summary-v1"
    assert advice["advice_row_count"] == 0
    assert advice["usage"]["hosted_api_tokens"] == 0

    reproduction = json.loads(
        (out / BUNDLE_REPRODUCTION_COMMANDS).read_text(encoding="utf-8")
    )
    commands = reproduction["commands"]
    assert "verify_checksums" in commands
    assert "rebuild_transition_assets" in commands
    assert "rebuild_transition_bench_report" in commands
    assert str(out / BUNDLE_CHECKSUMS) in commands["verify_checksums"][0]

    checksum_result = subprocess.run(
        ["shasum", "-a", "256", "-c", str(out / BUNDLE_CHECKSUMS)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert checksum_result.returncode == 0, checksum_result.stderr


def test_transition_evidence_bundle_packages_v3_gate_when_provided(
    tmp_path: Path,
) -> None:
    bench_report_path = tmp_path / "bench-report.json"
    run_transition_bench_demo(
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
        embedding_dim=8,
        top_k=1,
        out=bench_report_path,
    )
    v3_report = {
        "schema_version": TRANSITION_ACTION_SCORER_V3_REPORT_VERSION,
        "decision": "evaluation_only_not_wired_to_production",
        "scorer": "transition-action-future-scorer-v3",
        "available": True,
        "validation": {
            "product_readiness": {
                "schema_version": "transition-product-readiness-v1",
                "gate_result": GATE_READY_FOR_GUARDED_OPT_IN,
                "eligible_for_guarded_opt_in": True,
            }
        },
        "runtime": {
            "hosted_llm_api_calls": 0,
            "hosted_llm_prompt_tokens": 0,
            "hosted_llm_completion_tokens": 0,
            "hosted_api_tokens": 0,
            "hosted_repo_context_bytes": 0,
        },
    }
    v3_report_path = tmp_path / "v3-report.json"
    v3_report_path.write_text(
        json.dumps(v3_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    build_transition_evidence_bundle(
        bench_report=bench_report_path,
        shadow_scorer_report=v3_report_path,
        out_dir=tmp_path / "bundle",
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
    )

    gate = json.loads(
        ((tmp_path / "bundle") / BUNDLE_PRODUCT_GATE).read_text(encoding="utf-8")
    )
    assert ((tmp_path / "bundle") / BUNDLE_SHADOW_SCORER_V3_REPORT).is_file()
    assert gate["effective_source"] == BUNDLE_SHADOW_SCORER_V3_REPORT
    assert gate["effective_gate"]["gate_result"] == GATE_READY_FOR_GUARDED_OPT_IN
    assert gate["shadow_scorer_v3"]["provided"] is True


def test_transition_evidence_bundle_rejects_nonzero_hosted_usage(
    tmp_path: Path,
) -> None:
    bench_report_path = tmp_path / "bench-report.json"
    report = run_transition_bench_demo(
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
        embedding_dim=8,
        top_k=1,
        out=bench_report_path,
    )
    report["runtime"]["hosted_api_tokens"] = 4
    bench_report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="zero hosted"):
        build_transition_evidence_bundle(
            bench_report=bench_report_path,
            out_dir=tmp_path / "bundle",
            repo_root=tmp_path,
        )


def test_transition_matrix_evidence_bundle_packages_matrix_artifacts_and_checksums(
    monkeypatch,
    tmp_path: Path,
) -> None:
    matrix = _write_matrix_bundle_input(tmp_path)

    def fake_report_transition_residual_matrix(**kwargs):
        assert kwargs["matrix_dir"] == matrix
        return {
            "schema_version": "transition-residual-matrix-report-v1",
            "matrix": {"out": str(matrix), "zero_hosted_usage": True},
            "summary": {"suite_count": 1, "failure_count": 0},
            "groups": {},
            "suites": [],
            "examples": [],
            "usage": {
                "hosted_llm_api_calls": 0,
                "hosted_llm_prompt_tokens": 0,
                "hosted_llm_completion_tokens": 0,
                "hosted_api_tokens": 0,
                "hosted_repo_context_bytes": 0,
            },
            "runtime": {
                "local_runtime_ms": 1.0,
                "hosted_llm_api_calls": 0,
                "hosted_llm_prompt_tokens": 0,
                "hosted_llm_completion_tokens": 0,
                "hosted_api_tokens": 0,
                "hosted_repo_context_bytes": 0,
            },
        }

    monkeypatch.setattr(
        "j3.transition_evidence_bundle.report_transition_residual_matrix",
        fake_report_transition_residual_matrix,
    )
    out = tmp_path / "bundle"

    summary = build_transition_matrix_evidence_bundle(
        matrix_dir=matrix,
        out_dir=out,
        repo_root=tmp_path,
    )

    assert summary["schema_version"] == TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION
    for name in (
        BUNDLE_MANIFEST,
        BUNDLE_CHECKSUMS,
        BUNDLE_MATRIX_MANIFEST,
        BUNDLE_MATRIX_SUMMARY,
        BUNDLE_MATRIX_PRODUCT_GATES,
        BUNDLE_MATRIX_RESIDUAL_REPORT,
        BUNDLE_ZERO_HOSTED_USAGE,
        BUNDLE_REPRODUCTION_COMMANDS,
        "REPRODUCE.md",
    ):
        assert (out / name).is_file()
    assert not list(out.glob("*.jsonl"))

    manifest = json.loads((out / BUNDLE_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION
    assert manifest["hosted_usage"]["verified_zero"] is True
    assert manifest["checksums"]["algorithm"] == "sha256"

    gates = json.loads((out / BUNDLE_MATRIX_PRODUCT_GATES).read_text(encoding="utf-8"))
    assert gates["schema_version"] == "transition-matrix-product-gates-v1"
    assert gates["totals"]["suite_count"] == 1
    assert gates["totals"]["guarded_opt_in_eligible_suite_count"] == 0
    assert gates["suites"][0]["gate_result"] == "ready_for_shadow_mode"
    assert gates["suites"][0]["eligible_for_shadow_mode"] is True

    zero_usage = json.loads((out / BUNDLE_ZERO_HOSTED_USAGE).read_text(encoding="utf-8"))
    assert zero_usage["verified_zero"] is True
    assert "not packaged by default" in zero_usage["assertions"][2]

    checksum_result = subprocess.run(
        ["shasum", "-a", "256", "-c", str(out / BUNDLE_CHECKSUMS)],
        cwd=tmp_path.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    assert checksum_result.returncode == 0, checksum_result.stderr


def test_build_transition_evidence_bundle_cli_validates_missing_bench_report(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit, match="transition bench report does not exist"):
        main(
            [
                "build-transition-evidence-bundle",
                "--bench-report",
                str(tmp_path / "missing.json"),
                "--out",
                str(tmp_path / "bundle"),
            ]
        )


def test_build_transition_evidence_bundle_cli_prints_json_summary(
    capsys,
    tmp_path: Path,
) -> None:
    bench_report_path = tmp_path / "bench-report.json"
    run_transition_bench_demo(
        repo_root=tmp_path,
        prompt_corpus=(FIXTURES / "candidate_outcomes.jsonl").resolve(),
        embedding_dim=8,
        top_k=1,
        out=bench_report_path,
    )

    assert (
        main(
            [
                "build-transition-evidence-bundle",
                "--bench-report",
                str(bench_report_path),
                "--out",
                str(tmp_path / "bundle"),
                "--repo-root",
                str(tmp_path),
                "--prompt-corpus",
                str((FIXTURES / "candidate_outcomes.jsonl").resolve()),
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == TRANSITION_EVIDENCE_BUNDLE_VERSION
    assert output["zero_hosted_usage"] is True
    assert output["manifest"] == str((tmp_path / "bundle" / BUNDLE_MANIFEST).resolve())


def test_build_transition_evidence_bundle_cli_prints_matrix_json_summary(
    capsys,
    monkeypatch,
    tmp_path: Path,
) -> None:
    matrix = _write_matrix_bundle_input(tmp_path)

    monkeypatch.setattr(
        "j3.transition_evidence_bundle.report_transition_residual_matrix",
        lambda **_: {
            "schema_version": "transition-residual-matrix-report-v1",
            "summary": {"suite_count": 1, "failure_count": 0},
            "usage": {
                "hosted_llm_api_calls": 0,
                "hosted_llm_prompt_tokens": 0,
                "hosted_llm_completion_tokens": 0,
                "hosted_api_tokens": 0,
                "hosted_repo_context_bytes": 0,
            },
        },
    )

    assert (
        main(
            [
                "build-transition-evidence-bundle",
                "--matrix",
                str(matrix),
                "--out",
                str(tmp_path / "bundle"),
                "--repo-root",
                str(tmp_path),
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == TRANSITION_MATRIX_EVIDENCE_BUNDLE_VERSION
    assert output["zero_hosted_usage"] is True
    assert output["manifest"] == str((tmp_path / "bundle" / BUNDLE_MANIFEST).resolve())


def _write_matrix_bundle_input(tmp_path: Path) -> Path:
    matrix = tmp_path / "matrix"
    suite = matrix / "suite" / "greenshot_bugs"
    suite.mkdir(parents=True)
    suite_manifest = suite / "manifest.json"
    usage = {
        "hosted_llm_api_calls": 0,
        "hosted_llm_prompt_tokens": 0,
        "hosted_llm_completion_tokens": 0,
        "hosted_api_tokens": 0,
        "hosted_repo_context_bytes": 0,
    }
    suite_manifest.write_text(
        json.dumps(
            {
                "schema_version": "transition-shadow-suite-v1",
                "out": str(suite),
                "shadow_scorer_v3": {
                    "validation": {
                        "product_readiness": {
                            "schema_version": "transition-product-readiness-v1",
                            "gate_result": "ready_for_shadow_mode",
                            "eligible_for_shadow_mode": True,
                            "eligible_for_guarded_opt_in": False,
                            "residual_count": 0,
                            "baseline_residual_count": 0,
                        }
                    }
                },
                "usage": usage,
                "zero_hosted_usage": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    matrix_summary = {
        "schema_version": "transition-shadow-matrix-run-v1",
        "out": str(matrix),
        "suites": [
            {
                "id": "greenshot_bugs",
                "manifest": str(suite_manifest),
                "out": str(suite),
                "task_count": 5,
                "ranked_solved": 5,
                "held_out_group_count": 2,
                "v3_gate": "ready_for_shadow_mode",
                "eligible_for_shadow_mode": True,
                "eligible_for_guarded_opt_in": False,
            }
        ],
        "totals": {"suite_count": 1, "task_count": 5, "residual_count": 0},
        "usage": usage,
        "zero_hosted_usage": True,
    }
    matrix_manifest = {
        "schema_version": "transition-shadow-matrix-run-v1",
        "out": str(matrix),
        "suite_manifests": [
            {
                "id": "greenshot_bugs",
                "manifest": str(suite_manifest),
                "out": str(suite),
            }
        ],
        "summary": {
            "path": str(matrix / "matrix-summary.json"),
            "totals": matrix_summary["totals"],
            "zero_hosted_usage": True,
        },
    }
    (matrix / "matrix-summary.json").write_text(
        json.dumps(matrix_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (matrix / "matrix-manifest.json").write_text(
        json.dumps(matrix_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return matrix
