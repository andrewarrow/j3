from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.transition_action_choice import (
    TRANSITION_ACTION_CHOICE_SCHEMA_VERSION,
    build_transition_action_choice_groups,
    build_transition_action_choice_groups_jsonl,
    load_jsonl_objects,
    load_transition_action_choice_jsonl,
    validate_transition_action_choice_group,
    write_transition_action_choice_jsonl,
)


FIXTURES = Path(__file__).parent / "fixtures" / "transition_bench"


def test_builds_action_choice_group_from_candidate_outcomes_fixture() -> None:
    groups = build_transition_action_choice_groups_jsonl(
        FIXTURES / "candidate_outcomes.jsonl",
        embedding_dim=8,
    )

    assert len(groups) == 1
    group = groups[0]
    assert group["schema_version"] == TRANSITION_ACTION_CHOICE_SCHEMA_VERSION
    assert group["candidate_count"] == 2
    assert group["validated_candidate_count"] == 2
    assert group["first_passing_index"] == 2
    assert group["passing_candidate_ranks"] == [2]
    assert group["hard_negative_candidate_ranks"] == [1]

    grouping = group["grouping"]
    assert grouping["task"] == "calculator_add"
    assert grouping["phase"] == "ranked"
    assert grouping["repair_plan_source"] == "fallback_row_fields"
    assert str(grouping["repair_plan_identity"]).startswith("fallback:")
    assert grouping["fallback_fields"]["task_family"] == "operator_fix"

    failed, passed = group["candidates"]
    assert [candidate["rank_index"] for candidate in group["candidates"]] == [1, 2]
    assert failed["action"]["kind"] == "change_operator"
    assert failed["action"]["params"] == {"to": "-"}
    assert failed["target_context"] == {"function_name": "add", "line_span": [2, 2]}
    assert failed["validation"]["validated"] is True
    assert failed["validation"]["passed"] is False
    assert failed["source_context"]["kind"] == "candidate_context"
    assert failed["source_context"]["embedding"] is None
    assert failed["candidate_after"] == {
        "available": False,
        "kind": "unavailable",
        "source": None,
        "source_sha256": None,
        "embedding_available": False,
        "embedding_kind": None,
        "embedding_dim": None,
        "embedding": None,
        "reason": "candidate outcome row has no patched source or repo-after embedding",
    }
    assert passed["validation"]["passed"] is True
    assert passed["is_first_pass"] is True


def test_explicit_repair_plan_and_sources_are_preserved_with_embeddings() -> None:
    rows = [
        {
            **_candidate_row(rank_index=1, passed=False),
            "repair_plan_id": "plan-alpha",
            "before_source": "def add(left, right):\n    return left - right\n",
            "patched_source": "def add(left, right):\n    return left * right\n",
        },
        {
            **_candidate_row(rank_index=2, passed=True),
            "repair_plan_id": "plan-alpha",
            "before_source": "def add(left, right):\n    return left - right\n",
            "patched_source": "def add(left, right):\n    return left + right\n",
        },
    ]

    group = build_transition_action_choice_groups(rows, embedding_dim=8)[0]

    assert group["grouping"]["repair_plan_identity"] == "plan-alpha"
    assert group["grouping"]["repair_plan_source"] == "explicit_field"
    assert [candidate["rank_index"] for candidate in group["candidates"]] == [1, 2]
    first = group["candidates"][0]
    assert first["source_context"]["kind"] == "file_before_source"
    assert first["source_context"]["field"] == "before_source"
    assert first["source_context"]["embedding_kind"] == "ast-hash-v1"
    assert len(first["source_context"]["embedding"]) == 8
    assert first["candidate_after"]["kind"] == "file_after_source"
    assert first["candidate_after"]["field"] == "patched_source"
    assert first["candidate_after"]["embedding_kind"] == "ast-hash-v1"
    assert len(first["candidate_after"]["embedding"]) == 8


def test_nested_candidate_after_feeds_change_context_without_source_embedding() -> None:
    row = {
        **_candidate_row(rank_index=1, passed=True),
        "repair_plan_id": "plan-wrapper-behavior",
        "task_family": "held_out_wrapper_decoy",
        "candidate_after": {
            "available": True,
            "file_path": "service.py",
            "diff_summary": {
                "added_line_count": 5,
                "removed_line_count": 1,
                "changed_line_count": 6,
            },
            "ast_delta": {
                "ast_parse_ok": True,
                "ast_delta_added_count": 7,
                "ast_delta_removed_count": 2,
                "ast_delta_net_count": 5,
                "ast_delta_added_features": {
                    "node:FunctionDef": 1,
                    "node:If": 1,
                    "call:isinstance": 1,
                },
                "ast_delta_removed_features": {"node:Pass": 1},
            },
        },
    }

    group = build_transition_action_choice_groups([row], embedding_dim=8)[0]
    candidate = group["candidates"][0]

    assert candidate["candidate_after"]["available"] is True
    assert candidate["candidate_after"]["kind"] == "candidate_after_record"
    assert candidate["candidate_after"]["embedding_available"] is False
    assert candidate["change_context"] == {
        "available": True,
        "numeric": {
            "diff_added_lines": 5,
            "diff_removed_lines": 1,
            "diff_changed_lines": 6,
            "ast_delta_added_count": 7,
            "ast_delta_removed_count": 2,
            "ast_delta_net_count": 5,
        },
        "boolean": {"ast_parse_ok": True},
        "ast_features": {
            "added": {
                "call:isinstance": 1,
                "node:FunctionDef": 1,
                "node:If": 1,
            },
            "removed": {"node:Pass": 1},
        },
    }


def test_action_choice_writer_loader_are_deterministic(tmp_path: Path) -> None:
    groups = build_transition_action_choice_groups_jsonl(
        FIXTURES / "candidate_outcomes.jsonl",
        embedding_dim=8,
    )

    first_path = write_transition_action_choice_jsonl(groups, tmp_path / "choices-a.jsonl")
    second_path = write_transition_action_choice_jsonl(groups, tmp_path / "choices-b.jsonl")

    assert first_path.read_text(encoding="utf-8") == second_path.read_text(
        encoding="utf-8"
    )
    assert load_transition_action_choice_jsonl(first_path) == groups
    assert all(
        line.startswith('{"candidate_count"')
        for line in first_path.read_text(encoding="utf-8").splitlines()
    )


def test_action_choice_validator_rejects_bad_candidate_after() -> None:
    group = build_transition_action_choice_groups_jsonl(
        FIXTURES / "candidate_outcomes.jsonl",
        embedding_dim=8,
    )[0]
    broken = json.loads(json.dumps(group))
    broken["candidates"][0]["candidate_after"]["embedding"] = [1.0]

    with pytest.raises(ValueError, match="candidate_after.embedding must be null"):
        validate_transition_action_choice_group(broken)


def test_action_choice_validator_rejects_duplicate_ranks() -> None:
    rows = list(load_jsonl_objects(FIXTURES / "candidate_outcomes.jsonl"))
    rows[1]["rank_index"] = 1

    with pytest.raises(ValueError, match="candidate rank_index values must be unique"):
        build_transition_action_choice_groups(rows, embedding_dim=8)


def _candidate_row(*, rank_index: int, passed: bool) -> dict[str, object]:
    return {
        "task": "calculator_add",
        "task_family": "operator_fix",
        "source_type": "handcrafted",
        "split": "validation",
        "language": "python",
        "phase": "ranked",
        "file_path": "calculator.py",
        "action": "change_operator",
        "symbol": "add",
        "start_line": 2,
        "end_line": 2,
        "node_kind": "BinOp",
        "params": {"to": "+" if passed else "*"},
        "reason": "try operator",
        "model_score": 0.8 if passed else 0.1,
        "failure_hint_score": 1.0 if passed else 0.0,
        "ranker_score": None,
        "target_context": {"function_name": "add", "line_span": [2, 2]},
        "passed": passed,
        "preferred": False,
        "rank_index": rank_index,
        "first_passing_index": 2,
        "is_first_pass": passed,
        "passing_candidates": 1,
        "failure_hints": [],
        "equivalent_candidate_ranks": [],
        "overlapping_candidate_ranks": [],
        "equivalent_passing_candidate_ranks": [],
        "overlapping_passing_candidate_ranks": [],
    }
