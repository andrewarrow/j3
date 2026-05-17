from __future__ import annotations

import json
from pathlib import Path

from cli import main
from j3.transition_action_scoring import GATE_READY_FOR_GUARDED_OPT_IN
from j3.transition_guarded_trial import (
    DECISION_GUARDED_OPT_IN_TRIAL,
    DECISION_REMAIN_SHADOW_ONLY,
    TRANSITION_GUARDED_TRIAL_DECISION_VERSION,
    decide_transition_guarded_trial,
)
from j3.transition_shadow_matrix import MATRIX_SUMMARY, TRANSITION_SHADOW_MATRIX_VERSION


def test_guarded_trial_decision_blocks_shadow_only_matrix(tmp_path: Path) -> None:
    matrix = _write_matrix_summary(
        tmp_path,
        suite={
            "v3_gate": "ready_for_shadow_mode",
            "eligible_for_guarded_opt_in": False,
            "residual_count": 0,
        },
        residual_count=0,
    )

    decision = decide_transition_guarded_trial(matrix_dir=matrix)

    assert decision["schema_version"] == TRANSITION_GUARDED_TRIAL_DECISION_VERSION
    assert decision["decision"] == DECISION_REMAIN_SHADOW_ONLY
    assert decision["eligible_for_guarded_opt_in_trial"] is False
    assert "all suite V3 gates must be ready_for_guarded_opt_in" in decision["blockers"]
    assert decision["summary"]["residual_count"] == 0


def test_guarded_trial_decision_allows_narrow_trial_when_matrix_gates_pass(
    tmp_path: Path,
) -> None:
    matrix = _write_matrix_summary(
        tmp_path,
        suite={
            "v3_gate": GATE_READY_FOR_GUARDED_OPT_IN,
            "eligible_for_guarded_opt_in": True,
            "residual_count": 0,
        },
        residual_count=0,
    )

    decision = decide_transition_guarded_trial(matrix_dir=matrix)

    assert decision["decision"] == DECISION_GUARDED_OPT_IN_TRIAL
    assert decision["eligible_for_guarded_opt_in_trial"] is True
    assert decision["trial_scope"] == "narrow_opt_in_transition_ranking"
    assert decision["blockers"] == []


def test_guarded_trial_decision_blocks_residuals_and_hosted_usage(
    tmp_path: Path,
) -> None:
    matrix = _write_matrix_summary(
        tmp_path,
        suite={
            "v3_gate": GATE_READY_FOR_GUARDED_OPT_IN,
            "eligible_for_guarded_opt_in": True,
            "residual_count": 1,
        },
        residual_count=1,
        hosted_api_tokens=2,
    )

    decision = decide_transition_guarded_trial(matrix_dir=matrix)

    assert decision["decision"] == DECISION_REMAIN_SHADOW_ONLY
    assert "matrix and per-suite residual counts must be zero" in decision["blockers"]
    assert "matrix evidence must assert zero hosted API/context usage" in decision[
        "blockers"
    ]


def test_decide_transition_guarded_trial_cli_writes_json_report(
    capsys,
    tmp_path: Path,
) -> None:
    matrix = _write_matrix_summary(
        tmp_path,
        suite={
            "v3_gate": "ready_for_shadow_mode",
            "eligible_for_guarded_opt_in": False,
            "residual_count": 0,
        },
        residual_count=0,
    )
    out = tmp_path / "decision.json"

    assert (
        main(
            [
                "decide-transition-guarded-trial",
                "--matrix",
                str(matrix),
                "--out",
                str(out),
                "--json",
            ]
        )
        == 0
    )

    printed = json.loads(capsys.readouterr().out)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert printed["decision"] == DECISION_REMAIN_SHADOW_ONLY
    assert written == printed


def _write_matrix_summary(
    tmp_path: Path,
    *,
    suite: dict[str, object],
    residual_count: int,
    hosted_api_tokens: int = 0,
) -> Path:
    matrix = tmp_path / "matrix"
    matrix.mkdir()
    usage = {
        "hosted_llm_api_calls": 0,
        "hosted_llm_prompt_tokens": 0,
        "hosted_llm_completion_tokens": 0,
        "hosted_api_tokens": hosted_api_tokens,
        "hosted_repo_context_bytes": 0,
    }
    suite_record = {
        "id": "greenshot_bugs",
        "held_out_group_count": 2,
        "baseline_residual_count": 2,
        "zero_hosted_usage": hosted_api_tokens == 0,
        **suite,
    }
    summary = {
        "schema_version": TRANSITION_SHADOW_MATRIX_VERSION,
        "out": str(matrix),
        "suites": [suite_record],
        "totals": {
            "suite_count": 1,
            "task_count": 5,
            "held_out_group_count": 2,
            "residual_count": residual_count,
            "baseline_residual_count": 2,
        },
        "usage": usage,
        "zero_hosted_usage": hosted_api_tokens == 0,
    }
    (matrix / MATRIX_SUMMARY).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return matrix
