from __future__ import annotations

import json

from training import train_from_path


def test_train_from_path_writes_model_metrics_and_examples(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calculator.py").write_text(
        """
def is_large(value):
    if value > 10:
        return True
    return False
""".lstrip(),
        encoding="utf-8",
    )

    out = tmp_path / "run"
    result = train_from_path(data_path=repo, out_dir=out, embedding_dim=32, max_examples=10)

    assert result.source_files == 1
    assert result.parsed_examples > 0
    assert result.model_path.exists()
    assert result.metrics_path.exists()
    assert result.examples_path.exists()

    model = json.loads(result.model_path.read_text(encoding="utf-8"))
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    first_example = json.loads(result.examples_path.read_text(encoding="utf-8").splitlines()[0])

    assert model["format"] == "j3.prototype-jepa.v1"
    assert model["embedding_dim"] == 32
    assert metrics["synthetic_examples"] == result.parsed_examples
    assert "repair_action" in first_example


def test_train_from_path_rejects_repos_without_examples(tmp_path) -> None:
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    out = tmp_path / "run"

    try:
        train_from_path(data_path=empty_repo, out_dir=out, embedding_dim=32, max_examples=10)
    except ValueError as error:
        assert "no synthetic Python repair transitions" in str(error)
    else:
        raise AssertionError("expected ValueError")
