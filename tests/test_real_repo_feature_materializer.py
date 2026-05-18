from __future__ import annotations

import json
from pathlib import Path

from j3.real_repo_feature_materializer import (
    CANDIDATE_VALIDATION_DEFERRED,
    H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID,
    materialize_real_repo_feature_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "examples" / "real_repo_eval_ladder.json"


def _manifest_h11_feature_rows() -> tuple[dict[str, object], dict[str, object]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    repo = next(item for item in manifest["repositories"] if item["id"] == "h11")
    task = next(
        item
        for item in repo["tasks"]
        if item["id"] == H11_BYTESIFY_OBJECT_MESSAGE_TASK_ID
    )
    return repo, task


def _write_synthetic_h11_checkout(repo: Path) -> None:
    (repo / "h11" / "tests").mkdir(parents=True)
    (repo / "h11" / "__init__.py").write_text(
        """from __future__ import annotations

from ._util import bytesify

__all__ = ["bytesify"]
""",
        encoding="utf-8",
    )
    (repo / "h11" / "_util.py").write_text(
        """from typing import Any, Dict, NoReturn, Pattern, Tuple, Type, TypeVar, Union

__all__ = [
    "bytesify",
]


def bytesify(s: Union[bytes, bytearray, memoryview, int, str]) -> bytes:
    # Fast-path:
    if type(s) is bytes:
        return s
    if isinstance(s, str):
        s = s.encode("ascii")
    if isinstance(s, int):
        raise TypeError("expected bytes-like object, not int")
    return bytes(s)
""",
        encoding="utf-8",
    )
    (repo / "h11" / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "h11" / "tests" / "test_util.py").write_text(
        """import pytest

from .._util import bytesify


def test_bytesify() -> None:
    assert bytesify(b"123") == b"123"
    assert bytesify(bytearray(b"123")) == b"123"
    assert bytesify(memoryview(b"123")) == b"123"
    assert bytesify("123") == b"123"

    with pytest.raises(UnicodeEncodeError):
        bytesify("\\u1234")

    with pytest.raises(TypeError, match="int"):
        bytesify(10)
""",
        encoding="utf-8",
    )


def test_materializes_h11_bytesify_object_message_feature(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_feature_rows()
    _write_synthetic_h11_checkout(tmp_path)
    production_before = {
        "h11/__init__.py": (tmp_path / "h11" / "__init__.py").read_bytes(),
        "h11/_util.py": (tmp_path / "h11" / "_util.py").read_bytes(),
    }
    test_before = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )

    candidate = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
        validate=True,
    )
    row = candidate.to_record()

    assert json.loads(json.dumps(row, sort_keys=True)) == row
    assert row["schema_version"] == "real-repo-feature-candidate-v1"
    assert row["record_kind"] == "real_repo_one_file_feature_candidate"
    assert row["action_family"] == "one_file_source_feature_region"
    assert row["repo_id"] == "h11"
    assert row["repo_split"] == "heldout"
    assert row["task_id"] == "h11-feature-bytesify-object-message"
    assert row["status"] == "materialized"
    assert row["target_source_file"] == "h11/_util.py"
    assert row["target_test_file"] == "h11/tests/test_util.py"
    assert row["validation"]["status"] == "passed"
    assert row["validation"]["selected_command"] == (
        "python -m pytest h11/tests/test_util.py -q"
    )
    assert row["validation"]["candidate_validation_network_allowed"] is False
    assert row["zero_hosted_usage_confirmed"] is True
    assert row["blockers"] == []
    assert row["residual_labels"] == ["candidate_validation_passed"]

    mutation_scope = row["mutation_scope"]
    assert mutation_scope["mode"] == "one_file_feature"
    assert mutation_scope["planned_write_files"] == [
        "h11/_util.py",
        "h11/tests/test_util.py",
    ]
    assert mutation_scope["files_changed"] == [
        "h11/_util.py",
        "h11/tests/test_util.py",
    ]
    assert mutation_scope["writes_outside_allowlist"] == []
    assert mutation_scope["production_files"] == ["h11/__init__.py", "h11/_util.py"]
    assert mutation_scope["production_files_changed"] == ["h11/_util.py"]
    assert mutation_scope["maximum_production_files_changed"] == 1
    assert mutation_scope["allowed_production_file"] == "h11/_util.py"
    assert mutation_scope["one_production_file_constraint_preserved"] is True

    assert row["production_file_hashes_before"]["h11/__init__.py"] == (
        row["production_file_hashes_after"]["h11/__init__.py"]
    )
    assert row["production_file_hashes_before"]["h11/_util.py"] != (
        row["production_file_hashes_after"]["h11/_util.py"]
    )
    assert (tmp_path / "h11" / "__init__.py").read_bytes() == (
        production_before["h11/__init__.py"]
    )
    assert (tmp_path / "h11" / "_util.py").read_bytes() != (
        production_before["h11/_util.py"]
    )

    source_after = row["candidate_after"]["source_file"]
    assert source_after["status"] == "materialized"
    assert source_after["target_function"] == "bytesify"
    assert source_after["touched_region"]["region_name"] == (
        "unsupported_object_type_error_message"
    )
    assert source_after["candidate_after"]["ast_parse_ok"] is True
    assert source_after["candidate_after"]["signature_preserved"] is True
    assert source_after["candidate_after"]["import_changes"] == {
        "added": [],
        "removed": [],
    }
    assert "except TypeError" in source_after["candidate_after"]["diff"]
    assert "type(s).__name__" in source_after["candidate_after"]["diff"]

    test_after = row["candidate_after"]["test_file"]
    assert test_after["planned_changed_files"] == ["h11/tests/test_util.py"]
    assert test_after["wrote_file"] is True
    assert test_after["test_case_ids"] == [
        "h11_bytesify_unsupported_object_type_name"
    ]
    assert test_after["ast_delta"]["ast_parse_ok"] is True
    assert test_after["sha256_before"] != test_after["sha256_after"]
    assert "UnsupportedThing" in test_after["diff"]

    namespace: dict[str, object] = {}
    exec((tmp_path / "h11" / "_util.py").read_text(encoding="utf-8"), namespace)
    bytesify = namespace["bytesify"]

    class UnsupportedThing:
        pass

    assert bytesify(b"abc") == b"abc"
    assert bytesify(bytearray(b"abc")) == b"abc"
    assert bytesify(memoryview(b"abc")) == b"abc"
    assert bytesify("abc") == b"abc"
    try:
        bytesify(UnsupportedThing())
    except TypeError as error:
        message = str(error)
    else:
        raise AssertionError("bytesify should reject UnsupportedThing")
    assert "UnsupportedThing" in message
    assert "bytes-like object" in message

    test_after_text = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )
    assert test_after_text != test_before
    assert "test_bytesify_rejects_unsupported_object_with_type_name" in test_after_text


def test_materializer_can_plan_without_writing(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_feature_rows()
    _write_synthetic_h11_checkout(tmp_path)
    source_before = (tmp_path / "h11" / "_util.py").read_text(encoding="utf-8")
    test_before = (tmp_path / "h11" / "tests" / "test_util.py").read_text(
        encoding="utf-8"
    )

    row = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
        write=False,
    ).to_record()

    assert row["status"] == "planned"
    assert row["validation"] == {
        "status": "not_run",
        "commands": ["python -m pytest h11/tests/test_util.py -q"],
        "selected_command": "python -m pytest h11/tests/test_util.py -q",
        "not_run_reason": CANDIDATE_VALIDATION_DEFERRED,
        "candidate_validation_network_allowed": False,
        "runtime_seconds": 0.0,
    }
    assert row["mutation_scope"]["files_changed"] == []
    assert row["mutation_scope"]["production_files_changed"] == []
    assert (tmp_path / "h11" / "_util.py").read_text(encoding="utf-8") == source_before
    assert (
        tmp_path / "h11" / "tests" / "test_util.py"
    ).read_text(encoding="utf-8") == test_before


def test_materializer_blocks_when_source_region_is_not_expressible(
    tmp_path: Path,
) -> None:
    repo, task = _manifest_h11_feature_rows()
    _write_synthetic_h11_checkout(tmp_path)
    (tmp_path / "h11" / "_util.py").write_text(
        """from typing import Union


def bytesify(s: Union[bytes, bytearray, memoryview, int, str]) -> bytes:
    if isinstance(s, str):
        s = s.encode("ascii")
    return bytes(s).strip()
""",
        encoding="utf-8",
    )

    row = materialize_real_repo_feature_candidate(
        tmp_path,
        repo=repo,
        task=task,
    ).to_record()

    assert row["status"] == "blocked"
    assert row["blockers"] == [
        {
            "field": "source_region",
            "reason": "target_selection",
            "message": "target source line not found:     return bytes(s)",
        }
    ]
    assert row["residual_labels"] == ["target_selection"]
    assert row["candidate_after"]["source_file"] == {
        "available": False,
        "target_source_file": "h11/_util.py",
        "not_available_reason": "target_selection",
    }
    assert row["mutation_scope"]["files_changed"] == []
