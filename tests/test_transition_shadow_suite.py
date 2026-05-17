from __future__ import annotations

import json
from pathlib import Path

from cli import main
from j3.transition_shadow_suite import (
    SUITE_ADVICE_SUMMARY,
    SUITE_CANDIDATE_OUTCOMES,
    SUITE_DIAGNOSTICS,
    SUITE_EVIDENCE_DIR,
    SUITE_MANIFEST,
    SUITE_SHADOW_OUTCOMES,
    SUITE_SHADOW_SCORER_REPORT,
    SUITE_TRANSITION_ADVICE,
    TRANSITION_SHADOW_SUITE_VERSION,
    run_transition_shadow_suite,
)


def test_transition_shadow_suite_writes_repeatable_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "shadow-suite"

    manifest = run_transition_shadow_suite(
        tasks=[Path("examples/greenshot_bugs")],
        out_dir=out,
        checkpoint=None,
        timeout_seconds=10,
        max_candidates=4,
        explore_after_pass=1,
        embedding_dim=8,
        epochs=6,
        residual_limit=2,
    )

    assert manifest["schema_version"] == TRANSITION_SHADOW_SUITE_VERSION
    assert manifest["zero_hosted_usage"] is True
    assert manifest["eval"]["task_count"] == 5
    assert manifest["parameters"]["allow_production_rank_feature"] is False
    assert (out / SUITE_CANDIDATE_OUTCOMES).exists()
    assert (out / SUITE_TRANSITION_ADVICE).exists()
    assert (out / SUITE_DIAGNOSTICS).exists()
    assert (out / SUITE_ADVICE_SUMMARY).exists()
    assert (out / SUITE_SHADOW_OUTCOMES).exists()
    assert (out / SUITE_SHADOW_SCORER_REPORT).exists()
    assert (out / SUITE_EVIDENCE_DIR / "manifest.json").exists()

    written = json.loads((out / SUITE_MANIFEST).read_text(encoding="utf-8"))
    scorer_report = json.loads(
        (out / SUITE_SHADOW_SCORER_REPORT).read_text(encoding="utf-8")
    )
    evidence_manifest = json.loads(
        (out / SUITE_EVIDENCE_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    shadow_rows = [
        json.loads(line)
        for line in (out / SUITE_SHADOW_OUTCOMES).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert written == manifest
    assert scorer_report["schema_version"] == "transition-action-future-scorer-v3-report-v1"
    assert scorer_report["decision"] == "evaluation_only_not_wired_to_production"
    assert evidence_manifest["schema_version"] == "transition-evidence-bundle-v1"
    assert shadow_rows
    assert {row["schema_version"] for row in shadow_rows} == {
        "transition-shadow-outcome-v1"
    }
    assert "run_suite" in manifest["commands"]
    assert manifest["usage"]["hosted_llm_api_calls"] == 0


def test_run_transition_shadow_suite_cli_prints_json_manifest(
    capsys,
    tmp_path: Path,
) -> None:
    out = tmp_path / "shadow-suite"

    assert (
        main(
            [
                "run-transition-shadow-suite",
                "--tasks",
                "examples/greenshot_bugs",
                "--out",
                str(out),
                "--no-checkpoint",
                "--timeout",
                "10",
                "--max-candidates",
                "4",
                "--embedding-dim",
                "8",
                "--epochs",
                "6",
                "--residual-limit",
                "2",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == TRANSITION_SHADOW_SUITE_VERSION
    assert output["out"] == str(out.resolve())
    assert output["zero_hosted_usage"] is True
    assert output["artifacts"]["evidence_manifest"] == str(
        (out / SUITE_EVIDENCE_DIR / "manifest.json").resolve()
    )
