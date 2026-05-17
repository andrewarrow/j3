from __future__ import annotations

import pytest

from j3.actions import PatchAction, PatchActionKind, PatchTarget


def test_patch_action_serializes_to_record() -> None:
    action = PatchAction(
        kind=PatchActionKind.CHANGE_OPERATOR,
        target=PatchTarget(
            file_path="src/example.py",
            start_line=12,
            end_line=12,
            symbol="is_allowed",
            node_kind="Compare",
        ),
        params={"from": ">", "to": ">="},
    )

    assert action.to_record() == {
        "kind": "change_operator",
        "target": {
            "file_path": "src/example.py",
            "start_line": 12,
            "end_line": 12,
            "symbol": "is_allowed",
            "node_kind": "Compare",
        },
        "params": {"from": ">", "to": ">="},
    }


def test_patch_target_rejects_absolute_paths() -> None:
    with pytest.raises(ValueError, match="file_path must be relative"):
        PatchTarget(file_path="/tmp/example.py", start_line=1, end_line=1)


def test_patch_target_rejects_invalid_line_range() -> None:
    with pytest.raises(ValueError, match="end_line must be >= start_line"):
        PatchTarget(file_path="example.py", start_line=3, end_line=2)
