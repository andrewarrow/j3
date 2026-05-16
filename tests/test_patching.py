from __future__ import annotations

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
