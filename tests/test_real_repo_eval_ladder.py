from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_real_repo_ladder_manifest_has_required_repos_and_splits() -> None:
    manifest = _load_manifest()

    assert manifest["schema_version"] == "real-repo-eval-ladder-v1"
    assert manifest["zero_hosted_usage_required"] is True

    repositories = manifest["repositories"]
    assert isinstance(repositories, list)
    assert 3 <= len(repositories) <= 5

    repo_ids = {repo["id"] for repo in repositories}
    split_policy = manifest["split_policy"]
    heldout = set(split_policy["heldout_repos"])
    calibration = set(split_policy["calibration_repos"])

    assert heldout
    assert heldout.isdisjoint(calibration)
    assert heldout | calibration == repo_ids


def test_real_repo_ladder_manifest_pins_validation_and_task_shapes() -> None:
    manifest = _load_manifest()

    for repo in manifest["repositories"]:
        assert repo["license"] in {"MIT", "BSD-3-Clause"}
        assert COMMIT_RE.match(repo["checkout_ref"])
        assert str(repo["upstream"]).startswith("https://github.com/")
        assert repo["setup_commands"]
        assert repo["baseline_validation_commands"]

        tasks = repo["tasks"]
        task_types = {task["task_type"] for task in tasks}
        assert {"tests_only", "one_file_feature"} <= task_types

        for task in tasks:
            assert task["prompt"]
            assert task["allowed_write_paths"]
            assert task["public_validation_commands"]
            assert task["hidden_like_checks"]
            assert task["expected_failure_modes"]


def test_real_repo_ladder_gates_are_falsifiable() -> None:
    manifest = _load_manifest()
    gates = manifest["gates"]

    assert gates["baseline_viability"]["minimum_repos_passing_baseline"] >= 3
    assert gates["tests_only"]["minimum_pass_at_3"] < gates["tests_only"]["total_tasks"]
    assert (
        gates["one_file_feature"]["minimum_pass_at_3"]
        < gates["one_file_feature"]["total_tasks"]
    )
    assert len(gates["falsifiers"]) >= 3
