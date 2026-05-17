from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def _load_matrix() -> dict[str, Any]:
    assert MATRIX_PATH.is_file()
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
