from __future__ import annotations

import json
import shutil

from patching import PatchRankingModel, generate_candidate_patches, plan_and_maybe_apply_patch, rank_candidate_patches
from training import train_from_path


def test_patch_finds_discount_fix_without_modifying_in_dry_run(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.applied is False
    assert "price * (1 - percent / 100)" in result.selected.patched_source
    assert "return price * (percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_patch_applies_discount_fix(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=False,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.applied is True
    assert "return price * (1 - percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_patch_uses_model_to_rank_candidates(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)
    training = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=20,
    )
    model = PatchRankingModel.load(training.model_path)

    ranked = rank_candidate_patches(generate_candidate_patches(repo), model)

    assert ranked
    assert ranked[0].model_score is not None


def test_patch_ranking_uses_mined_git_transition_exemplars(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    before = "def discount(price, percent):\n    return price * (percent / 100)\n"
    after = "def discount(price, percent):\n    return price * (1 - percent / 100)\n"
    (repo / "calculator.py").write_text(before, encoding="utf-8")
    transitions = tmp_path / "transitions.jsonl"
    transitions.write_text(
        json.dumps(
            {
                "kind": "git_transition",
                "repo": "demo",
                "commit": "b",
                "parent": "a",
                "file_path": "calculator.py",
                "before_source": before,
                "after_source": after,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    training = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=20,
        transition_paths=[transitions],
    )
    model = PatchRankingModel.load(training.model_path)

    ranked = rank_candidate_patches(generate_candidate_patches(repo), model)

    assert ranked[0].patched_source == after
    assert ranked[0].model_score is not None


def test_patch_accepts_model_path(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)
    training = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=20,
    )

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=True,
        timeout_seconds=10,
        model_path=training.model_path,
    )

    assert result.model_path == training.model_path.resolve()
    assert result.selected is not None
    assert result.selected.model_score is not None


def test_patch_uses_pytest_failure_hints_to_prioritize_literal_fix(tmp_path) -> None:
    repo = tmp_path / "greenshot_bugs"
    shutil.copytree("examples/greenshot_bugs", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_bugs.py::test_shipping_total_uses_expected_fee",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.action.target.symbol == "shipping_total"
    assert result.selected.action.params["to"] == 5
    assert result.selected.failure_hint_score > 0
