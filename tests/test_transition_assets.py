from __future__ import annotations

import hashlib
import json

from j3.transition_assets import (
    format_transition_asset_inventory,
    inspect_transition_assets,
    write_transition_asset_manifest,
)


def _write_jsonl(path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_transition_asset_inventory_treats_missing_ignored_data_as_normal(tmp_path):
    manifest = inspect_transition_assets(
        repo_root=tmp_path,
        prompt_corpus=tmp_path / "missing-prompts.jsonl",
    )

    assert manifest["schema_version"] == "transition-asset-inventory-v1"
    assert manifest["repo_root"] == str(tmp_path.resolve())
    assert manifest["prompt_corpus"]["present"] is False
    assert manifest["prompt_corpus"]["rows"] is None
    assert manifest["prompt_repo_demo_artifacts"]["directory_count"] == 0
    assert manifest["mined_git_transitions"]["file_count"] == 0
    assert manifest["mined_git_transitions"]["total_rows"] == 0
    assert manifest["candidate_outcomes"]["file_count"] == 0
    assert manifest["candidate_outcomes"]["total_rows"] == 0
    assert manifest["prototype_models"]["model_count"] == 0
    assert manifest["totals"] == {
        "candidate_outcome_files": 0,
        "candidate_outcome_rows": 0,
        "mined_git_transition_files": 0,
        "mined_git_transition_rows": 0,
        "prompt_corpus_rows": 0,
        "prompt_repo_demo_directories": 0,
        "prototype_model_files": 0,
    }

    formatted = format_transition_asset_inventory(manifest)
    assert "prompt corpus: missing rows=0" in formatted
    assert "missing ignored assets: normal" in formatted


def test_transition_asset_inventory_summarizes_local_assets(tmp_path):
    prompt_text = (
        '{"id":"prompt-1","prompt":"make me a simple cli calc"}\n'
        '{"id":"prompt-2","prompt":"add exponent support"}\n'
    )
    prompt_corpus = tmp_path / "prompts" / "coding_agent_prompts_expanded_v0.jsonl"
    prompt_corpus.parent.mkdir(parents=True)
    prompt_corpus.write_text(prompt_text, encoding="utf-8")

    _write_jsonl(
        tmp_path / "data" / "transitions" / "apache-python" / "repo.jsonl",
        [
            {"kind": "git_transition", "repo": "demo", "file_path": "a.py"},
            {"kind": "git_transition", "repo": "demo", "file_path": "b.py"},
        ],
    )
    _write_jsonl(
        tmp_path / "runs" / "apache-python-git" / "greenshot-6-candidate-outcomes.jsonl",
        [
            {"task": "one", "phase": "ranked", "rank_index": 1, "passed": False},
            {"task": "one", "phase": "ranked", "rank_index": 2, "passed": True},
        ],
    )

    demo_dir = tmp_path / "runs" / "prompt-repo-demo"
    demo_dir.mkdir(parents=True)
    (demo_dir / "report.json").write_text(
        json.dumps(
            {
                "schema_version": "prompt-jepa-demo-report-v1",
                "top_k": 3,
                "embedding_dim": 64,
                "hosted_llm_api_tokens": 0,
                "hosted_repo_context_bytes": 0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        demo_dir / "transitions.jsonl",
        [
            {"schema_version": "prompt-repo-transition-v1", "id": "one"},
            {"schema_version": "prompt-repo-transition-v1", "id": "two"},
        ],
    )
    (demo_dir / "transition-model.json").write_text(
        json.dumps(
            {
                "schema_version": "prompt-repo-transition-predictor-v0",
                "decision": "evaluation-only",
                "train_rows": 2,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (tmp_path / "runs" / "apache-python-git" / "model.json").write_text(
        json.dumps(
            {
                "format": "j3.prototype-jepa.v1",
                "created_at": "2026-05-17T00:00:00+00:00",
                "feature_version": "ast-hash-v1",
                "embedding_dim": 256,
                "examples": 12,
                "synthetic_examples": 10,
                "mined_examples": 2,
                "sources": ["repo-a", "repo-b"],
                "transition_sources": ["data/transitions/apache-python"],
                "action_counts": {"git_transition": 2, "change_literal": 10},
                "before_centroid": [0.0, 1.0],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = inspect_transition_assets(
        repo_root=tmp_path,
        prompt_corpus=prompt_corpus,
    )

    assert manifest["prompt_corpus"]["present"] is True
    assert manifest["prompt_corpus"]["rows"] == 2
    assert manifest["prompt_corpus"]["sha256"] == _sha256_text(prompt_text)
    assert manifest["mined_git_transitions"]["file_count"] == 1
    assert manifest["mined_git_transitions"]["total_rows"] == 2
    assert manifest["candidate_outcomes"]["file_count"] == 1
    assert manifest["candidate_outcomes"]["total_rows"] == 2
    assert manifest["prompt_repo_demo_artifacts"]["directory_count"] == 1
    demo = manifest["prompt_repo_demo_artifacts"]["directories"][0]
    assert demo["relative_path"] == "runs/prompt-repo-demo"
    assert demo["report_metadata"]["schema_version"] == "prompt-jepa-demo-report-v1"
    assert {
        artifact["relative_path"]: artifact.get("rows")
        for artifact in demo["artifacts"]
    }["runs/prompt-repo-demo/transitions.jsonl"] == 2

    assert manifest["prototype_models"]["model_count"] == 1
    model = manifest["prototype_models"]["models"][0]
    assert model["file"]["relative_path"] == "runs/apache-python-git/model.json"
    assert model["metadata"]["format"] == "j3.prototype-jepa.v1"
    assert model["metadata"]["embedding_dim"] == 256
    assert model["metadata"]["sources_count"] == 2
    assert model["metadata"]["transition_sources_count"] == 1
    assert model["metadata"]["action_counts"] == {
        "change_literal": 10,
        "git_transition": 2,
    }

    assert manifest["totals"]["prompt_corpus_rows"] == 2
    assert manifest["totals"]["mined_git_transition_rows"] == 2
    assert manifest["totals"]["candidate_outcome_rows"] == 2
    assert manifest["totals"]["prototype_model_files"] == 1


def test_transition_asset_manifest_writer_uses_stable_json(tmp_path):
    manifest = inspect_transition_assets(
        repo_root=tmp_path,
        prompt_corpus=tmp_path / "missing.jsonl",
    )
    out_path = write_transition_asset_manifest(
        manifest,
        tmp_path / "manifests" / "transition-assets.json",
    )

    assert out_path == tmp_path / "manifests" / "transition-assets.json"
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded == manifest
    assert out_path.read_text(encoding="utf-8").endswith("\n")
