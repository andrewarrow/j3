from __future__ import annotations

import json
from pathlib import Path

from j3.real_repo_preflight import (
    PreflightCommandResult,
    RealRepoPreflightOptions,
    check_allowed_write_paths,
    load_real_repo_ladder_manifest,
    run_real_repo_preflight,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


class RecordingRunner:
    def __init__(self, *, fail_command_fragment: str | None = None) -> None:
        self.calls: list[tuple[str, Path, int]] = []
        self.fail_command_fragment = fail_command_fragment

    def __call__(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int,
    ) -> PreflightCommandResult:
        self.calls.append((command, cwd, timeout_seconds))
        failed = (
            self.fail_command_fragment is not None
            and self.fail_command_fragment in command
        )
        return PreflightCommandResult(
            command=command,
            cwd=str(cwd),
            timeout_seconds=timeout_seconds,
            returncode=1 if failed else 0,
            stdout="",
            stderr="failed" if failed else "",
            status="failed" if failed else "passed",
        )


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_load_real_repo_ladder_manifest_reads_contract() -> None:
    manifest = load_real_repo_ladder_manifest(MANIFEST_PATH)
    repositories = manifest["repositories"]

    assert manifest["schema_version"] == "real-repo-eval-ladder-v1"
    assert isinstance(repositories, list)
    assert len(repositories) == 4


def test_preflight_uses_injected_runner_and_emits_task_rows(tmp_path: Path) -> None:
    runner = RecordingRunner()
    outcome_path = tmp_path / "outcomes.jsonl"

    rows = run_real_repo_preflight(
        RealRepoPreflightOptions(
            manifest_path=MANIFEST_PATH,
            work_root=tmp_path / "repos",
            outcome_path=outcome_path,
        ),
        command_runner=runner,
    )

    assert len(rows) == 8
    assert len(runner.calls) == 16
    assert runner.calls[0][0].startswith("git clone --no-checkout")
    assert runner.calls[1][0].startswith("git checkout --detach 77db208")
    assert "python -m pip install -e . pytest" in {call[0] for call in runner.calls}
    assert "python -m pytest testing -q" in {call[0] for call in runner.calls}

    first = rows[0]
    assert first["schema_version"] == "real-repo-preflight-outcome-v1"
    assert first["record_kind"] == "real_repo_eval_ladder_preflight"
    assert first["repo_id"] == "iniconfig"
    assert first["task_id"] == "iniconfig-tests-parse-comments"
    assert first["checkout_ref"] == "77db208ab4ae0cd2061d909fe222a1db72867850"
    assert first["blocker_label"] == "none"
    assert first["preflight_status"] == "passed"
    assert first["setup_command_results"]
    assert first["baseline_validation_command_results"]

    network_policy = first["network_policy"]
    assert isinstance(network_policy, dict)
    assert network_policy["setup_network_allowed"] is True
    assert network_policy["candidate_validation_network_allowed"] is False

    timeout_policy = first["timeout_policy"]
    assert isinstance(timeout_policy, dict)
    assert timeout_policy["per_candidate_timeout_seconds"] == 120
    assert timeout_policy["per_task_timeout_seconds"] == 600

    written = _jsonl_rows(outcome_path)
    assert len(written) == len(rows)
    assert written[0]["allowed_write_path_check"] == first["allowed_write_path_check"]


def test_allowed_write_path_violation_is_labeled_separately(tmp_path: Path) -> None:
    runner = RecordingRunner()

    rows = run_real_repo_preflight(
        RealRepoPreflightOptions(
            manifest_path=MANIFEST_PATH,
            work_root=tmp_path / "repos",
            candidate_paths_by_task={
                "h11-tests-bytesify-memoryview": [
                    "h11/tests/test_util.py",
                    "h11/_util.py",
                ]
            },
        ),
        command_runner=runner,
    )

    row = next(
        item
        for item in rows
        if item["task_id"] == "h11-tests-bytesify-memoryview"
    )
    assert row["environment_blocker_label"] == "none"
    assert row["blocker_label"] == "allowed_write_path_violation"
    assert row["preflight_status"] == "blocked"
    allowed_check = row["allowed_write_path_check"]
    assert isinstance(allowed_check, dict)
    assert allowed_check["status"] == "failed"
    assert allowed_check["violations"] == ["h11/_util.py"]


def test_validation_failure_is_environment_blocker(tmp_path: Path) -> None:
    runner = RecordingRunner(fail_command_fragment="python -m pytest testing -q")

    rows = run_real_repo_preflight(
        RealRepoPreflightOptions(
            manifest_path=MANIFEST_PATH,
            work_root=tmp_path / "repos",
        ),
        command_runner=runner,
    )

    iniconfig_rows = [row for row in rows if row["repo_id"] == "iniconfig"]
    assert {row["blocker_label"] for row in iniconfig_rows} == {
        "baseline_validation_failed"
    }
    first = iniconfig_rows[0]
    assert first["environment_blocker_label"] == "baseline_validation_failed"
    baseline_results = first["baseline_validation_command_results"]
    assert isinstance(baseline_results, list)
    assert baseline_results[0]["status"] == "failed"


def test_allowed_write_paths_reject_absolute_and_parent_paths() -> None:
    check = check_allowed_write_paths(
        ["tests/test_example.py"],
        candidate_paths=["tests/test_example.py"],
    )
    assert check.status == "passed"

    for bad_path in ("/tmp/example.py", "../example.py"):
        try:
            check_allowed_write_paths(
                ["tests/test_example.py"],
                candidate_paths=[bad_path],
            )
        except ValueError as exc:
            assert "repository-relative" in str(exc)
        else:
            raise AssertionError(f"expected {bad_path} to be rejected")
