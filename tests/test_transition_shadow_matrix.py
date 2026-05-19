from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cli.handlers
from cli import main
from j3 import transition_shadow_matrix
from j3.transition_shadow_matrix import (
    MATRIX_EVIDENCE_DIR,
    MATRIX_MANIFEST,
    MATRIX_SUMMARY,
    MATRIX_SUITE_DIR,
    TRANSITION_SHADOW_MATRIX_VERSION,
    run_transition_shadow_matrix,
)


MATRIX_PATH = Path("examples/transition_shadow_matrix.json")
REQUIRED_SUITES = {
    "greenshot_bugs",
    "greenshot_3",
    "greenshot_4",
    "greenshot_5_subset",
    "greenshot_6_subset",
}
REQUIRED_PARAMETERS = {
    "max_candidates",
    "explore_after_pass",
    "timeout_seconds",
    "split_by",
    "validation_fraction",
}
VALID_SPLIT_KEYS = {"task_family", "source_file", "repo", "order"}
EXPECTED_GREENSHOT_5_SUBSET_TASK_NAMES = [
    "quote_total_helper_discount",
    "store_credit_swapped_args_across_modules",
    "uploaded_extension_module_import",
    "visible_balance_attribute_decoys",
    "profile_signature_propagation",
    "profile_badge_public_api_signature_propagation",
    "order_customer_name_dict_key_helper",
    "return_window_policy_default",
    "express_shipping_boundary_preferred_helper",
    "free_shipping_threshold_module_constant",
    "receipt_label_nested_module_import_decoy",
    "loyalty_points_wrapper_exception_handler",
]


def test_transition_shadow_matrix_manifest_shape() -> None:
    matrix = _load_matrix()

    assert matrix["schema_version"] == "transition-shadow-matrix-v1"
    assert matrix["zero_hosted_usage"] is True
    assert isinstance(matrix["description"], str)
    assert matrix["description"].strip()

    defaults = matrix["defaults"]
    assert defaults["checkpoint"] == "runs/apache-python-git/model.json"
    assert defaults["repo_root"] == "."
    assert defaults["max_steps"] == 1
    assert defaults["top_k"] >= 1
    assert defaults["embedding_dim"] >= 1

    suites = matrix["suites"]
    assert isinstance(suites, list)
    assert suites
    suite_ids = [suite["id"] for suite in suites]
    assert len(suite_ids) == len(set(suite_ids))
    assert set(suite_ids) == REQUIRED_SUITES


def test_transition_shadow_matrix_suites_reference_existing_tasks() -> None:
    matrix = _load_matrix()

    for suite in matrix["suites"]:
        tasks_path = Path(suite["tasks"])
        task_manifest = tasks_path / "tasks.json"
        assert tasks_path.is_dir(), suite["id"]
        assert task_manifest.is_file(), suite["id"]

        task_rows = json.loads(task_manifest.read_text(encoding="utf-8"))
        task_names = {row["name"] for row in task_rows}
        selected_task_names = suite.get("task_names")
        if selected_task_names is not None:
            assert isinstance(selected_task_names, list)
            assert selected_task_names
            assert len(selected_task_names) == len(set(selected_task_names))
            assert set(selected_task_names) <= task_names
            assert len(selected_task_names) < len(task_rows)


def test_transition_shadow_matrix_greenshot_5_subset_is_cautious_expansion() -> None:
    matrix = _load_matrix()
    suite = next(
        suite for suite in matrix["suites"] if suite["id"] == "greenshot_5_subset"
    )
    task_rows = json.loads(
        (Path(suite["tasks"]) / "tasks.json").read_text(encoding="utf-8")
    )
    task_order = {row["name"]: index for index, row in enumerate(task_rows)}

    assert suite["task_names"] == EXPECTED_GREENSHOT_5_SUBSET_TASK_NAMES
    assert len(suite["task_names"]) == 12
    assert len(suite["task_names"]) < len(task_rows)
    assert [task_order[name] for name in suite["task_names"]] == sorted(
        task_order[name] for name in suite["task_names"]
    )


def test_transition_shadow_matrix_per_suite_parameters_are_runner_ready() -> None:
    matrix = _load_matrix()

    for suite in matrix["suites"]:
        parameters = suite["parameters"]
        assert set(parameters) == REQUIRED_PARAMETERS
        assert isinstance(parameters["max_candidates"], int)
        assert parameters["max_candidates"] >= 1
        assert isinstance(parameters["explore_after_pass"], int)
        assert parameters["explore_after_pass"] >= 0
        assert isinstance(parameters["timeout_seconds"], int)
        assert parameters["timeout_seconds"] >= 1
        assert parameters["split_by"] in VALID_SPLIT_KEYS
        assert isinstance(parameters["validation_fraction"], float)
        assert 0.0 < parameters["validation_fraction"] < 1.0


def test_run_transition_shadow_matrix_runs_only_suite_and_writes_summary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run_transition_shadow_suite(**kwargs: Any) -> dict[str, object]:
        calls.append(kwargs)
        out_dir = kwargs["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        evidence_dir = out_dir / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "manifest.json").write_text('{"schema_version":"fake"}\n')
        return _fake_suite_manifest(out_dir, task_count=5, solved=4)

    monkeypatch.setattr(
        transition_shadow_matrix,
        "run_transition_shadow_suite",
        fake_run_transition_shadow_suite,
    )
    monkeypatch.setattr(
        cli.handlers,
        "run_transition_shadow_matrix",
        transition_shadow_matrix.run_transition_shadow_matrix,
    )

    out = tmp_path / "matrix"
    summary = run_transition_shadow_matrix(
        matrix_path=MATRIX_PATH,
        out_dir=out,
        only="greenshot_bugs",
    )

    assert len(calls) == 1
    assert calls[0]["tasks"] == [Path("examples/greenshot_bugs")]
    assert calls[0]["max_candidates"] == 12
    assert calls[0]["split_by"] == "order"
    assert summary["schema_version"] == TRANSITION_SHADOW_MATRIX_VERSION
    assert summary["zero_hosted_usage"] is True
    assert summary["totals"]["suite_count"] == 1
    assert summary["totals"]["task_count"] == 5
    assert summary["totals"]["ranked_solved"] == 4
    assert summary["totals"]["advice_rows"] == 5
    assert summary["totals"]["candidate_count"] == 37
    assert summary["totals"]["held_out_group_count"] == 2
    assert summary["totals"]["residual_count"] == 1
    assert summary["suites"][0]["id"] == "greenshot_bugs"
    assert summary["suites"][0]["v3_gate"] == "ready_for_shadow_mode"
    assert summary["suites"][0]["v3_vs_existing_rank_order"]["pass_at_1_delta"] == 0.25
    assert (out / MATRIX_MANIFEST).is_file()
    assert (out / MATRIX_SUMMARY).is_file()
    assert (out / MATRIX_SUITE_DIR / "greenshot_bugs" / "evidence" / "manifest.json").is_file()
    assert (out / MATRIX_EVIDENCE_DIR / "manifest.json").is_file()
    assert (out / MATRIX_EVIDENCE_DIR / "checksums.sha256").is_file()


def test_run_transition_shadow_matrix_writes_filtered_subset_manifest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run_transition_shadow_suite(**kwargs: Any) -> dict[str, object]:
        calls.append(kwargs)
        out_dir = kwargs["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "evidence").mkdir()
        (out_dir / "evidence" / "manifest.json").write_text('{"schema_version":"fake"}\n')
        return _fake_suite_manifest(out_dir, task_count=12, solved=12)

    monkeypatch.setattr(
        transition_shadow_matrix,
        "run_transition_shadow_suite",
        fake_run_transition_shadow_suite,
    )

    out = tmp_path / "matrix"
    run_transition_shadow_matrix(
        matrix_path=MATRIX_PATH,
        out_dir=out,
        only="greenshot_5_subset",
    )

    assert len(calls) == 1
    subset_manifest = calls[0]["tasks"][0] / "tasks.json"
    rows = json.loads(subset_manifest.read_text(encoding="utf-8"))
    suite = next(
        suite for suite in _load_matrix()["suites"] if suite["id"] == "greenshot_5_subset"
    )
    assert [row["name"] for row in rows] == suite["task_names"]
    assert len(rows) == 12
    assert {Path(row["repo"]).is_absolute() for row in rows} == {True}
    assert calls[0]["max_candidates"] == 10
    assert calls[0]["timeout_seconds"] == 45
    assert calls[0]["validation_fraction"] == 0.25


def test_run_transition_shadow_matrix_cli_prints_json_summary(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    def fake_run_transition_shadow_suite(**kwargs: Any) -> dict[str, object]:
        out_dir = kwargs["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "evidence").mkdir()
        (out_dir / "evidence" / "manifest.json").write_text('{"schema_version":"fake"}\n')
        return _fake_suite_manifest(out_dir, task_count=5, solved=5)

    monkeypatch.setattr(
        transition_shadow_matrix,
        "run_transition_shadow_suite",
        fake_run_transition_shadow_suite,
    )

    assert (
        main(
            [
                "run-transition-shadow-matrix",
                "--matrix",
                str(MATRIX_PATH),
                "--out",
                str(tmp_path / "matrix"),
                "--only",
                "greenshot_bugs",
                "--json",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == TRANSITION_SHADOW_MATRIX_VERSION
    assert output["totals"]["suite_count"] == 1
    assert output["zero_hosted_usage"] is True


def _load_matrix() -> dict[str, Any]:
    assert MATRIX_PATH.is_file()
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _fake_suite_manifest(
    out_dir: Path,
    *,
    task_count: int,
    solved: int,
) -> dict[str, object]:
    return {
        "schema_version": "transition-shadow-suite-v1",
        "out": str(out_dir),
        "artifacts": {
            "evidence_manifest": str(out_dir / "evidence" / "manifest.json"),
        },
        "eval": {
            "task_count": task_count,
            "ranked_solved": solved,
        },
        "advice_summary": {
            "advice_row_count": task_count,
            "candidate_count": 37,
        },
        "shadow_scorer_v3": {
            "split": {
                "validation_group_count": 2,
            },
            "validation": {
                "group_count": 2,
                "product_readiness": {
                    "gate_result": "ready_for_shadow_mode",
                    "eligible_for_shadow_mode": True,
                    "eligible_for_guarded_opt_in": False,
                    "residual_count": 1,
                    "baseline_residual_count": 2,
                    "metrics": {
                        "pass_at_1": {"delta": 0.25},
                        "top_k": {"delta": 0.0},
                        "mean_reciprocal_rank": {"delta": 0.2},
                        "average_candidates_validated_before_first_pass": {
                            "delta": -0.5
                        },
                    },
                },
            },
        },
        "usage": {
            "hosted_llm_api_calls": 0,
            "hosted_llm_prompt_tokens": 0,
            "hosted_llm_completion_tokens": 0,
            "hosted_api_tokens": 0,
            "hosted_repo_context_bytes": 0,
        },
        "zero_hosted_usage": True,
    }
