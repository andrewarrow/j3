from __future__ import annotations

import json

from j3.training import train_from_path, train_from_paths


def test_train_from_path_writes_model_metrics_and_examples(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calculator.py").write_text(
        """
def is_large(value):
    if value > 10:
        return True
    return False


def double(value):
    return value * 2
""".lstrip(),
        encoding="utf-8",
    )

    out = tmp_path / "run"
    result = train_from_path(data_path=repo, out_dir=out, embedding_dim=32, max_examples=10)

    assert result.source_files == 1
    assert result.parsed_examples > 0
    assert result.mined_examples == 0
    assert result.model_path.exists()
    assert result.metrics_path.exists()
    assert result.examples_path.exists()

    model = json.loads(result.model_path.read_text(encoding="utf-8"))
    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    first_example = json.loads(result.examples_path.read_text(encoding="utf-8").splitlines()[0])

    assert model["format"] == "j3.prototype-jepa.v1"
    assert model["embedding_dim"] == 32
    assert "replace_expr" in model["action_delta_prototypes"]
    assert "replace_expr" in model["action_delta_exemplars"]
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


def test_train_from_paths_combines_multiple_repos(tmp_path) -> None:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    (repo_a / "first.py").write_text("def a(value):\n    return value > 1\n", encoding="utf-8")
    (repo_b / "second.py").write_text("def b():\n    return True\n", encoding="utf-8")

    result = train_from_paths(
        data_paths=[repo_a, repo_b],
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=10,
    )

    assert result.source_files == 2
    assert result.parsed_examples >= 2


def test_train_includes_mined_transitions(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "source.py").write_text("def local():\n    return 1\n", encoding="utf-8")
    transitions = tmp_path / "transitions.jsonl"
    transitions.write_text(
        json.dumps(
            {
                "kind": "git_transition",
                "repo": "demo",
                "commit": "b",
                "parent": "a",
                "file_path": "source.py",
                "before_source": "def value():\n    return 1\n",
                "after_source": "def value():\n    return 2\n",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=10,
        transition_paths=[transitions],
    )

    metrics = json.loads(result.metrics_path.read_text(encoding="utf-8"))
    assert result.mined_examples == 1
    assert metrics["mined_examples"] == 1
    assert "git_transition" in result.action_counts

    model = json.loads(result.model_path.read_text(encoding="utf-8"))
    assert len(model["action_delta_exemplars"]["git_transition"]) == 1
