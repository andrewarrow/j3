from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "issue_pr_mini_replay" / "manifest.json"


def test_issue_pr_mini_replay_manifest_schema() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "issue-pr-mini-replay-v0"
    assert manifest["totals"]["records"] == 10
    assert manifest["source"]["live_api_access_required_for_manifest_use"] is False

    residual_vocabulary = set(manifest["residual_label_vocabulary"])
    required_labels = {
        "local_knowledge_gap",
        "materialization_gap",
        "validation_gap",
        "ranking_gap",
        "prompt_spec_parsing_gap",
    }
    assert residual_vocabulary == required_labels

    records = manifest["records"]
    assert len(records) == 10
    assert len({record["id"] for record in records}) == len(records)
    assert {record["provenance_license"]["license_spdx"] for record in records} <= {
        "Apache-2.0",
        "BSD-3-Clause",
        "MIT",
    }

    seen_labels: set[str] = set()
    split_counts = {"train": 0, "validation": 0, "test": 0}
    for record in records:
        assert record["id"].startswith(record["repo"].replace("/", "__"))
        assert record["prompt_text"]
        assert record["prompt_source"]["issue_url"].startswith("https://github.com/")
        assert record["prompt_source"]["pull_request_url"].startswith(
            "https://github.com/"
        )
        assert len(record["repo_before_ref"]["sha"]) == 40
        assert record["accepted_change"]["kind"] == "merged_pull_request"
        assert len(record["accepted_change"]["merge_commit_sha"]) == 40
        assert record["accepted_change"]["diff_url"].endswith(".diff")
        assert record["accepted_change"]["changed_files"]
        assert record["validation"]["command"].startswith("pytest ")
        assert record["validation"]["availability"] in {"partial", "available"}
        assert record["provenance_license"]["review_status"] == "curated_metadata_only"

        bucket = int(hashlib.sha256(record["id"].encode()).hexdigest(), 16) % 100
        assert record["stable_split"]["method"] == "sha256(id) % 100"
        assert record["stable_split"]["bucket"] == bucket
        assert record["stable_split"]["split"] == _split_for_bucket(bucket)
        split_counts[record["stable_split"]["split"]] += 1

        labels = set(record["initial_residual_labels"])
        assert labels
        assert labels <= residual_vocabulary
        seen_labels.update(labels)

    assert seen_labels == required_labels
    assert manifest["totals"]["split_counts"] == split_counts


def _split_for_bucket(bucket: int) -> str:
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"
