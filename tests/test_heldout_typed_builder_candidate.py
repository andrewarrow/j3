from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from j3.heldout_typed_builder_candidate import (
    build_click_sentinel_parser_spec,
    build_click_utils_annotation_spec,
    build_flask_jinja_autoescape_spec,
    build_requests_headers_mapping_spec,
    build_requests_response_reason_spec,
    materialize_heldout_typed_builder_candidate,
)


def test_click_utils_annotation_spec_uses_reusable_action_kinds(
    tmp_path: Path,
) -> None:
    repo = _write_click_fixture_repo(tmp_path / "click")

    spec = build_click_utils_annotation_spec(repo)

    assert [action.kind for action in spec.typed_actions] == [
        "class_scope_annotation_move",
        "return_annotation_update",
        "class_scope_annotation_move",
        "type_annotation_update",
    ]
    assert spec.allowed_write_paths == ("src/click/utils.py",)
    for action in spec.typed_actions:
        assert "click_3422" not in action.kind
        assert "3422" not in action.kind


def test_materializes_click_utils_annotations_with_reusable_actions(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_click_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "click" / "utils.py").write_text(
        _click_utils_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(accepted_repo, "diff", "--", "src/click/utils.py"),
        encoding="utf-8",
    )

    repo = _write_click_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_click_utils_annotation_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == ["src/click/utils.py"]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/click/utils.py"
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert record["zero_hosted_llm_source_judgment"] is True

    action_kinds = [action["kind"] for action in record["action_records"]]
    assert action_kinds == [
        "class_scope_annotation_move",
        "return_annotation_update",
        "class_scope_annotation_move",
        "type_annotation_update",
    ]
    target_after = record["candidate_after"]["target_file"]["candidate_after"]
    assert target_after["ast_parse_ok"] is True
    assert target_after["diff_summary"]["changed_line_count"] == 20
    assert target_after["diff_summary"]["added_line_count"] == 15
    assert target_after["diff_summary"]["removed_line_count"] == 5
    diff = target_after["diff"]
    assert "+    name: str\n" in diff
    assert "-        self.name: str = os.fspath(filename)\n" in diff
    assert "+    ) -> None:\n" in diff
    assert "+    _file: t.IO[t.Any]\n" in diff
    assert "+    wrapped: t.IO[t.Any]\n" in diff


def test_click_utils_validation_command_can_pass_on_materialized_fixture(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_click_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "click" / "utils.py").write_text(
        _click_utils_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(accepted_repo, "diff", "--", "src/click/utils.py"),
        encoding="utf-8",
    )

    repo = _write_click_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_click_utils_annotation_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=True,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "validated"
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]


def test_requests_headers_mapping_spec_uses_general_typed_actions(
    tmp_path: Path,
) -> None:
    repo = _write_requests_fixture_repo(tmp_path / "requests")

    spec = build_requests_headers_mapping_spec(repo)

    assert [action.kind for action in spec.typed_actions] == [
        "type_alias_update",
        "import_member_remove",
        "type_annotation_update",
    ]
    assert spec.allowed_write_paths == (
        "src/requests/_types.py",
        "src/requests/models.py",
    )
    for action in spec.typed_actions:
        assert "requests" not in action.kind
        assert "7441" not in action.kind


def test_materializes_requests_headers_mapping_across_two_files(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "requests" / "_types.py").write_text(
        _requests_types_after(),
        encoding="utf-8",
    )
    (accepted_repo / "src" / "requests" / "models.py").write_text(
        _requests_models_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(
            accepted_repo,
            "diff",
            "--",
            "src/requests/_types.py",
            "src/requests/models.py",
        ),
        encoding="utf-8",
    )

    repo = _write_requests_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_requests_headers_mapping_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/_types.py",
        "src/requests/models.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/requests/_types.py",
        "src/requests/models.py",
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True

    files = record["candidate_after"]["files"]
    assert set(files) == {"src/requests/_types.py", "src/requests/models.py"}
    assert files["src/requests/_types.py"]["candidate_after"]["ast_parse_ok"] is True
    assert files["src/requests/models.py"]["candidate_after"]["ast_parse_ok"] is True
    candidate_diff = record["candidate_after"]["candidate_diff"]
    assert "+    HeadersType: TypeAlias = Mapping[str, str | bytes] | None\n" in candidate_diff
    assert "-    from collections.abc import MutableMapping\n" in candidate_diff
    assert "+    headers: Mapping[str, str | bytes]\n" in candidate_diff


def test_requests_headers_mapping_validation_command_can_pass(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "requests" / "_types.py").write_text(
        _requests_types_after(),
        encoding="utf-8",
    )
    (accepted_repo / "src" / "requests" / "models.py").write_text(
        _requests_models_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(
            accepted_repo,
            "diff",
            "--",
            "src/requests/_types.py",
            "src/requests/models.py",
        ),
        encoding="utf-8",
    )

    repo = _write_requests_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_requests_headers_mapping_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=True,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "validated"
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]


def test_requests_response_reason_spec_stays_pure_typed_builder(
    tmp_path: Path,
) -> None:
    repo = _write_requests_7437_fixture_repo(tmp_path / "requests")

    spec = build_requests_response_reason_spec(repo)

    assert [action.kind for action in spec.typed_actions] == [
        "type_annotation_update",
        "assignment_type_ignore_update",
    ]
    assert spec.allowed_write_paths == ("src/requests/models.py",)
    for action in spec.typed_actions:
        assert "requests" not in action.kind
        assert "7437" not in action.kind
        assert action.kind != "statement_block_replace"


def test_materializes_requests_response_reason_without_statement_block_replace(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_7437_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "requests" / "models.py").write_text(
        _requests_7437_models_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(accepted_repo, "diff", "--", "src/requests/models.py"),
        encoding="utf-8",
    )

    repo = _write_requests_7437_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_requests_response_reason_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["mode"] == "heldout_typed_builder_one_file"
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/requests/models.py"
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/requests/models.py"
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert record["typed_builder_layer_judgment"] == {
        "schema_version": "typed-builder-layer-judgment-v1",
        "layer": "pure_typed_builder",
        "stays_pure_typed_builder_layer": True,
        "uses_statement_block_replace": False,
        "action_kinds": [
            "type_annotation_update",
            "assignment_type_ignore_update",
        ],
    }

    target_after = record["candidate_after"]["target_file"]["candidate_after"]
    assert target_after["ast_parse_ok"] is True
    assert target_after["diff_summary"]["changed_line_count"] == 4
    candidate_diff = record["candidate_after"]["candidate_diff"]
    assert "-    reason: str | None\n" in candidate_diff
    assert "+    reason: str\n" in candidate_diff
    assert "-        self.reason = None\n" in candidate_diff
    assert "+        self.reason = None  # type: ignore[assignment]\n" in candidate_diff
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert "statement_block_replace" not in action_kinds


def test_requests_response_reason_validation_command_can_pass(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_requests_7437_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "requests" / "models.py").write_text(
        _requests_7437_models_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(accepted_repo, "diff", "--", "src/requests/models.py"),
        encoding="utf-8",
    )

    repo = _write_requests_7437_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_requests_response_reason_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=True,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "validated"
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]


def test_flask_jinja_autoescape_spec_reuses_signature_update(
    tmp_path: Path,
) -> None:
    repo = _write_flask_5808_fixture_repo(tmp_path / "flask")

    spec = build_flask_jinja_autoescape_spec(repo)

    assert [action.kind for action in spec.typed_actions] == [
        "function_signature_update",
    ]
    assert spec.allowed_write_paths == ("src/flask/sansio/app.py",)
    for action in spec.typed_actions:
        assert "flask" not in action.kind
        assert "5808" not in action.kind
        assert action.kind != "statement_block_replace"


def test_materializes_flask_jinja_autoescape_without_statement_block_replace(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_flask_5808_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "flask" / "sansio" / "app.py").write_text(
        _flask_5808_app_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(accepted_repo, "diff", "--", "src/flask/sansio/app.py"),
        encoding="utf-8",
    )

    repo = _write_flask_5808_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_flask_jinja_autoescape_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["mode"] == "heldout_typed_builder_one_file"
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/flask/sansio/app.py"
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["accepted_changed_files"] == [
        "src/flask/sansio/app.py"
    ]
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True
    assert record["typed_builder_layer_judgment"] == {
        "schema_version": "typed-builder-layer-judgment-v1",
        "layer": "pure_typed_builder",
        "stays_pure_typed_builder_layer": True,
        "uses_statement_block_replace": False,
        "action_kinds": ["function_signature_update"],
    }

    target_after = record["candidate_after"]["target_file"]["candidate_after"]
    assert target_after["ast_parse_ok"] is True
    assert target_after["diff_summary"]["changed_line_count"] == 2
    candidate_diff = record["candidate_after"]["candidate_diff"]
    assert "-    def select_jinja_autoescape(self, filename: str) -> bool:\n" in candidate_diff
    assert (
        "+    def select_jinja_autoescape(self, filename: str | None) -> bool:\n"
        in candidate_diff
    )
    action_kinds = [action["kind"] for action in record["action_records"]]
    assert "statement_block_replace" not in action_kinds


def test_flask_jinja_autoescape_validation_command_can_pass(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_flask_5808_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "flask" / "sansio" / "app.py").write_text(
        _flask_5808_app_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(accepted_repo, "diff", "--", "src/flask/sansio/app.py"),
        encoding="utf-8",
    )

    repo = _write_flask_5808_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_flask_jinja_autoescape_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=True,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "validated"
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]


def test_click_sentinel_parser_spec_uses_general_action_families(
    tmp_path: Path,
) -> None:
    repo = _write_click_3396_fixture_repo(tmp_path / "click")

    spec = build_click_sentinel_parser_spec(repo)

    assert spec.allowed_write_paths == (
        "src/click/_utils.py",
        "src/click/core.py",
        "src/click/parser.py",
    )
    assert [action.kind for action in spec.typed_actions] == [
        "assignment_annotation_update",
        "assignment_annotation_update",
        "assignment_annotation_update",
        "assignment_annotation_update",
        "boolean_condition_insert",
        "function_signature_update",
        "function_signature_update",
        "statement_block_replace",
        "statement_block_replace",
        "assignment_annotation_update",
        "function_signature_update",
        "statement_block_replace",
        "function_signature_update",
        "assignment_annotation_update",
    ]
    for action in spec.typed_actions:
        assert "click" not in action.kind
        assert "3396" not in action.kind


def test_materializes_click_sentinel_parser_typing_across_three_files(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_click_3396_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "click" / "_utils.py").write_text(
        _click_3396_utils_after(),
        encoding="utf-8",
    )
    (accepted_repo / "src" / "click" / "core.py").write_text(
        _click_3396_core_after(),
        encoding="utf-8",
    )
    (accepted_repo / "src" / "click" / "parser.py").write_text(
        _click_3396_parser_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(
            accepted_repo,
            "diff",
            "--",
            "src/click/_utils.py",
            "src/click/core.py",
            "src/click/parser.py",
        ),
        encoding="utf-8",
    )

    repo = _write_click_3396_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_click_sentinel_parser_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=False,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "materialized"
    assert record["residual_labels"] == ["candidate_validation_deferred"]
    assert record["mutation_scope"]["mode"] == "heldout_typed_builder_multi_file"
    assert record["mutation_scope"]["actual_changed_files"] == [
        "src/click/_utils.py",
        "src/click/core.py",
        "src/click/parser.py",
    ]
    assert record["mutation_scope"]["planned_write_files"] == [
        "src/click/_utils.py",
        "src/click/core.py",
        "src/click/parser.py",
    ]
    assert record["mutation_scope"]["writes_outside_allowlist"] == []
    assert record["accepted_diff_comparison"]["normalized_diff_equal"] is True

    files = record["candidate_after"]["files"]
    assert set(files) == {
        "src/click/_utils.py",
        "src/click/core.py",
        "src/click/parser.py",
    }
    assert files["src/click/_utils.py"]["candidate_after"]["ast_parse_ok"] is True
    assert files["src/click/core.py"]["candidate_after"]["ast_parse_ok"] is True
    assert files["src/click/parser.py"]["candidate_after"]["ast_parse_ok"] is True
    candidate_diff = record["candidate_after"]["candidate_diff"]
    assert "+UNSET: t.Literal[Sentinel.UNSET] = Sentinel.UNSET\n" in candidate_diff
    assert "+            and isinstance(value, cabc.Iterable)\n" in candidate_diff
    assert "+            x: list[str | T_UNSET] = [_fetch(args) for _ in range(nargs)]\n" in candidate_diff
    assert "+        value: str | cabc.Sequence[str] | T_UNSET | T_FLAG_NEEDS_VALUE\n" in candidate_diff


def test_click_sentinel_parser_validation_command_can_pass(
    tmp_path: Path,
) -> None:
    accepted_repo = _write_click_3396_fixture_repo(tmp_path / "accepted")
    (accepted_repo / "src" / "click" / "_utils.py").write_text(
        _click_3396_utils_after(),
        encoding="utf-8",
    )
    (accepted_repo / "src" / "click" / "core.py").write_text(
        _click_3396_core_after(),
        encoding="utf-8",
    )
    (accepted_repo / "src" / "click" / "parser.py").write_text(
        _click_3396_parser_after(),
        encoding="utf-8",
    )
    accepted_diff = tmp_path / "accepted.diff"
    accepted_diff.write_text(
        _git_stdout(
            accepted_repo,
            "diff",
            "--",
            "src/click/_utils.py",
            "src/click/core.py",
            "src/click/parser.py",
        ),
        encoding="utf-8",
    )

    repo = _write_click_3396_fixture_repo(tmp_path / "candidate")
    candidate = materialize_heldout_typed_builder_candidate(
        repo,
        build_click_sentinel_parser_spec(repo, base_ref=_repo_head(repo)),
        write=True,
        validate=True,
        accepted_diff_path=accepted_diff,
    )
    record = candidate.to_record()

    assert record["status"] == "validated"
    assert record["validation"]["status"] == "passed"
    assert record["residual_labels"] == ["candidate_validation_passed"]


def _write_click_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "src" / "click" / "utils.py").write_text(
        _click_utils_before(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )
    return repo


def _write_click_3396_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "src" / "click" / "_utils.py").write_text(
        _click_3396_utils_before(),
        encoding="utf-8",
    )
    (repo / "src" / "click" / "core.py").write_text(
        _click_3396_core_before(),
        encoding="utf-8",
    )
    (repo / "src" / "click" / "parser.py").write_text(
        _click_3396_parser_before(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )
    return repo


def _write_requests_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "src" / "requests" / "_types.py").write_text(
        _requests_types_before(),
        encoding="utf-8",
    )
    (repo / "src" / "requests" / "models.py").write_text(
        _requests_models_before(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )
    return repo


def _write_requests_7437_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "src" / "requests" / "models.py").write_text(
        _requests_7437_models_before(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )
    return repo


def _write_flask_5808_fixture_repo(repo: Path) -> Path:
    (repo / "src" / "flask" / "sansio").mkdir(parents=True)
    (repo / "src" / "flask" / "sansio" / "app.py").write_text(
        _flask_5808_app_before(),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )
    return repo


def _repo_head(repo: Path) -> str:
    return _git_stdout(repo, "rev-parse", "HEAD")


def _git_stdout(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def _click_utils_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import collections.abc as cabc
        import os
        import typing as t
        from types import TracebackType


        def format_filename(name: str) -> str:
            return name


        def open_stream(*args: t.Any, **kwargs: t.Any) -> tuple[t.IO[t.Any], bool]:
            raise NotImplementedError


        class LazyFile:
            """A lazy file works like a regular file but it does not fully open
            the file but it does perform some basic checks early to see if the
            filename parameter does make sense.  This is useful for safely opening
            files for writing.
            """

            def __init__(
                self,
                filename: str | os.PathLike[str],
                mode: str = "r",
                encoding: str | None = None,
                errors: str | None = "strict",
                atomic: bool = False,
            ):
                self.name: str = os.fspath(filename)
                self.mode = mode
                self.encoding = encoding
                self.errors = errors
                self.atomic = atomic
                self._f: t.IO[t.Any] | None
                self.should_close: bool

                if self.name == "-":
                    self._f, self.should_close = open_stream(filename, mode, encoding, errors)
                else:
                    if "r" in mode:
                        open(filename, mode).close()
                    self._f = None
                    self.should_close = True

            def __getattr__(self, name: str) -> t.Any:
                return getattr(self.open(), name)

            def __repr__(self) -> str:
                if self._f is not None:
                    return repr(self._f)
                return f"<unopened file '{format_filename(self.name)}' {self.mode}>"

            def open(self) -> t.IO[t.Any]:
                if self._f is not None:
                    return self._f
                rv, self.should_close = open_stream(
                    self.name, self.mode, self.encoding, self.errors, atomic=self.atomic
                )
                self._f = rv
                return rv

            def close(self) -> None:
                if self._f is not None:
                    self._f.close()

            def __enter__(self) -> LazyFile:
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                self.close()

            def __iter__(self) -> cabc.Iterator[t.AnyStr]:
                self.open()
                return iter(self._f)  # type: ignore


        class KeepOpenFile:
            def __init__(self, file: t.IO[t.Any]) -> None:
                self._file: t.IO[t.Any] = file

            def __getattr__(self, name: str) -> t.Any:
                return getattr(self._file, name)

            def __enter__(self) -> KeepOpenFile:
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                pass

            def __repr__(self) -> str:
                return repr(self._file)

            def __iter__(self) -> cabc.Iterator[t.AnyStr]:
                return iter(self._file)


        class PacifyFlushWrapper:
            """This wrapper is used to catch and suppress BrokenPipeErrors resulting
            from ``.flush()`` being called on broken pipe during the shutdown/final-GC
            of the Python interpreter. Notably ``.flush()`` is always called on
            ``sys.stdout`` and ``sys.stderr``. So as to have minimal impact on any
            other cleanup code, and the case where the underlying file is not a broken
            pipe, all calls and attributes are proxied.
            """

            def __init__(self, wrapped: t.IO[t.Any]) -> None:
                self.wrapped = wrapped

            def flush(self) -> None:
                self.wrapped.flush()
        '''
    ).lstrip()


def _click_utils_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import collections.abc as cabc
        import os
        import typing as t
        from types import TracebackType


        def format_filename(name: str) -> str:
            return name


        def open_stream(*args: t.Any, **kwargs: t.Any) -> tuple[t.IO[t.Any], bool]:
            raise NotImplementedError


        class LazyFile:
            """A lazy file works like a regular file but it does not fully open
            the file but it does perform some basic checks early to see if the
            filename parameter does make sense.  This is useful for safely opening
            files for writing.
            """

            name: str
            mode: str
            encoding: str | None
            errors: str | None
            atomic: bool
            _f: t.IO[t.Any] | None
            should_close: bool

            def __init__(
                self,
                filename: str | os.PathLike[str],
                mode: str = "r",
                encoding: str | None = None,
                errors: str | None = "strict",
                atomic: bool = False,
            ) -> None:
                self.name = os.fspath(filename)
                self.mode = mode
                self.encoding = encoding
                self.errors = errors
                self.atomic = atomic

                if self.name == "-":
                    self._f, self.should_close = open_stream(filename, mode, encoding, errors)
                else:
                    if "r" in mode:
                        open(filename, mode).close()
                    self._f = None
                    self.should_close = True

            def __getattr__(self, name: str) -> t.Any:
                return getattr(self.open(), name)

            def __repr__(self) -> str:
                if self._f is not None:
                    return repr(self._f)
                return f"<unopened file '{format_filename(self.name)}' {self.mode}>"

            def open(self) -> t.IO[t.Any]:
                if self._f is not None:
                    return self._f
                rv, self.should_close = open_stream(
                    self.name, self.mode, self.encoding, self.errors, atomic=self.atomic
                )
                self._f = rv
                return rv

            def close(self) -> None:
                if self._f is not None:
                    self._f.close()

            def __enter__(self) -> LazyFile:
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                self.close()

            def __iter__(self) -> cabc.Iterator[t.AnyStr]:
                self.open()
                return iter(self._f)  # type: ignore


        class KeepOpenFile:
            _file: t.IO[t.Any]

            def __init__(self, file: t.IO[t.Any]) -> None:
                self._file = file

            def __getattr__(self, name: str) -> t.Any:
                return getattr(self._file, name)

            def __enter__(self) -> KeepOpenFile:
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                pass

            def __repr__(self) -> str:
                return repr(self._file)

            def __iter__(self) -> cabc.Iterator[t.AnyStr]:
                return iter(self._file)


        class PacifyFlushWrapper:
            """This wrapper is used to catch and suppress BrokenPipeErrors resulting
            from ``.flush()`` being called on broken pipe during the shutdown/final-GC
            of the Python interpreter. Notably ``.flush()`` is always called on
            ``sys.stdout`` and ``sys.stderr``. So as to have minimal impact on any
            other cleanup code, and the case where the underlying file is not a broken
            pipe, all calls and attributes are proxied.
            """

            wrapped: t.IO[t.Any]

            def __init__(self, wrapped: t.IO[t.Any]) -> None:
                self.wrapped = wrapped

            def flush(self) -> None:
                self.wrapped.flush()
        '''
    ).lstrip()


def _click_3396_utils_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import enum
        import typing as t


        class Sentinel(enum.Enum):
            UNSET = object()
            FLAG_NEEDS_VALUE = object()

            def __repr__(self) -> str:
                return f"{self.__class__.__name__}.{self.name}"


        UNSET = Sentinel.UNSET
        """Sentinel used to indicate that a value is not set."""

        FLAG_NEEDS_VALUE = Sentinel.FLAG_NEEDS_VALUE
        """Sentinel used to indicate an option was passed as a flag without a
        value but is not a flag option.

        ``Option.consume_value`` uses this to prompt or use the ``flag_value``.
        """

        T_UNSET = t.Literal[UNSET]  # type: ignore[valid-type]
        """Type hint for the :data:`UNSET` sentinel value."""

        T_FLAG_NEEDS_VALUE = t.Literal[FLAG_NEEDS_VALUE]  # type: ignore[valid-type]
        """Type hint for the :data:`FLAG_NEEDS_VALUE` sentinel value."""
        '''
    ).lstrip()


def _click_3396_utils_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import enum
        import typing as t


        class Sentinel(enum.Enum):
            UNSET = object()
            FLAG_NEEDS_VALUE = object()

            def __repr__(self) -> str:
                return f"{self.__class__.__name__}.{self.name}"


        UNSET: t.Literal[Sentinel.UNSET] = Sentinel.UNSET
        """Sentinel used to indicate that a value is not set."""

        FLAG_NEEDS_VALUE: t.Literal[Sentinel.FLAG_NEEDS_VALUE] = Sentinel.FLAG_NEEDS_VALUE
        """Sentinel used to indicate an option was passed as a flag without a
        value but is not a flag option.

        ``Option.consume_value`` uses this to prompt or use the ``flag_value``.
        """

        T_UNSET: t.TypeAlias = t.Literal[Sentinel.UNSET]
        """Type hint for the :data:`UNSET` sentinel value."""

        T_FLAG_NEEDS_VALUE: t.TypeAlias = t.Literal[Sentinel.FLAG_NEEDS_VALUE]
        """Type hint for the :data:`FLAG_NEEDS_VALUE` sentinel value."""
        '''
    ).lstrip()


def _click_3396_core_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import collections.abc as cabc
        from enum import IntEnum
        from typing import Any

        FLAG_NEEDS_VALUE = object()
        UNSET = object()


        class ParameterSource(IntEnum):
            COMMANDLINE = 1
            DEFAULT_MAP = 2


        class Option:
            multiple = True
            is_flag = False
            is_bool_flag = False
            flag_value: Any = None

            def consume_value(self, value: object, source: ParameterSource) -> object:
                if value is UNSET:
                    return value

                # Re-interpret a multiple option which has been sent as-is by the parser.
                # Here we replace each occurrence of value-less flags (marked by the
                # FLAG_NEEDS_VALUE sentinel) with the flag_value.
                elif (
                    self.multiple
                    and value is not UNSET
                    and source < ParameterSource.DEFAULT_MAP
                    and any(v is FLAG_NEEDS_VALUE for v in value)
                ):
                    value = [self.flag_value if v is FLAG_NEEDS_VALUE else v for v in value]
                    source = ParameterSource.COMMANDLINE

                return value
        '''
    ).lstrip()


def _click_3396_core_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import collections.abc as cabc
        from enum import IntEnum
        from typing import Any

        FLAG_NEEDS_VALUE = object()
        UNSET = object()


        class ParameterSource(IntEnum):
            COMMANDLINE = 1
            DEFAULT_MAP = 2


        class Option:
            multiple = True
            is_flag = False
            is_bool_flag = False
            flag_value: Any = None

            def consume_value(self, value: object, source: ParameterSource) -> object:
                if value is UNSET:
                    return value

                # Re-interpret a multiple option which has been sent as-is by the parser.
                # Here we replace each occurrence of value-less flags (marked by the
                # FLAG_NEEDS_VALUE sentinel) with the flag_value.
                elif (
                    self.multiple
                    and value is not UNSET
                    and isinstance(value, cabc.Iterable)
                    and source < ParameterSource.DEFAULT_MAP
                    and any(v is FLAG_NEEDS_VALUE for v in value)
                ):
                    value = [self.flag_value if v is FLAG_NEEDS_VALUE else v for v in value]
                    source = ParameterSource.COMMANDLINE

                return value
        '''
    ).lstrip()


def _click_3396_parser_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import collections.abc as cabc
        import typing as t
        from collections import deque

        FLAG_NEEDS_VALUE = object()
        T_FLAG_NEEDS_VALUE = object
        T_UNSET = object
        UNSET = object()
        V = t.TypeVar("V")


        class BadArgumentUsage(Exception):
            pass


        def _(value: str) -> str:
            return value


        class _ParsingState:
            rargs: list[str]


        class CoreArgument:
            pass


        class CoreOption:
            _flag_needs_value = False


        class _Option:
            nargs = 1
            obj = CoreOption()


        def _unpack_args(
            args: cabc.Sequence[str], nargs_spec: cabc.Sequence[int]
        ) -> tuple[cabc.Sequence[str | cabc.Sequence[str | None] | None], list[str]]:
            args = deque(args)
            nargs_spec = deque(nargs_spec)
            rv: list[str | tuple[str | T_UNSET, ...] | T_UNSET] = []
            spos: int | None = None

            def _fetch(c: deque[V]) -> V | T_UNSET:
                try:
                    if spos is None:
                        return c.popleft()
                    else:
                        return c.pop()
                except IndexError:
                    return UNSET

            while nargs_spec:
                nargs = _fetch(nargs_spec)

                if nargs is None:
                    continue

                if nargs == 1:
                    rv.append(_fetch(args))  # type: ignore[arg-type]
                elif nargs > 1:
                    x = [_fetch(args) for _ in range(nargs)]

                    if spos is not None:
                        x.reverse()

                    rv.append(tuple(x))
                elif nargs < 0:
                    if spos is not None:
                        raise TypeError("Cannot have two nargs < 0")

                    spos = len(rv)
                    rv.append(UNSET)

            if spos is not None:
                rv[spos] = tuple(args)
                args = []
                rv[spos + 1 :] = reversed(rv[spos + 1 :])

            return tuple(rv), list(args)


        class _Argument:
            def __init__(self, obj: CoreArgument, dest: str | None, nargs: int = 1):
                self.dest = dest
                self.nargs = nargs
                self.obj = obj

            def process(
                self,
                value: str | cabc.Sequence[str | None] | None | T_UNSET,
                state: _ParsingState,
            ) -> None:
                if self.nargs > 1:
                    assert isinstance(value, cabc.Sequence)
                    holes = sum(1 for x in value if x is UNSET)
                    if holes == len(value):
                        value = UNSET
                    elif holes != 0:
                        raise BadArgumentUsage(
                            _("Argument {name!r} takes {nargs} values.").format(
                                name=self.dest, nargs=self.nargs
                            )
                        )


        class _OptionParser:
            def _get_value_from_state(
                self, option_name: str, option: _Option, state: _ParsingState
            ) -> str | cabc.Sequence[str] | T_FLAG_NEEDS_VALUE:
                nargs = option.nargs

                value: str | cabc.Sequence[str] | T_FLAG_NEEDS_VALUE

                if len(state.rargs) < nargs:
                    if option.obj._flag_needs_value:
                        value = FLAG_NEEDS_VALUE
                    else:
                        value = []
                else:
                    value = tuple(state.rargs[:nargs])

                return value
        '''
    ).lstrip()


def _click_3396_parser_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import collections.abc as cabc
        import typing as t
        from collections import deque

        FLAG_NEEDS_VALUE = object()
        T_FLAG_NEEDS_VALUE = object
        T_UNSET = object
        UNSET = object()
        V = t.TypeVar("V")


        class BadArgumentUsage(Exception):
            pass


        def _(value: str) -> str:
            return value


        class _ParsingState:
            rargs: list[str]


        class CoreArgument:
            pass


        class CoreOption:
            _flag_needs_value = False


        class _Option:
            nargs = 1
            obj = CoreOption()


        def _unpack_args(
            args: cabc.Sequence[str], nargs_spec: cabc.Sequence[int]
        ) -> tuple[cabc.Sequence[str | cabc.Sequence[str | T_UNSET] | T_UNSET], list[str]]:
            args = deque(args)
            nargs_spec = deque(nargs_spec)
            rv: list[str | tuple[str | T_UNSET, ...] | T_UNSET] = []
            spos: int | None = None

            def _fetch(c: deque[str]) -> str | T_UNSET:
                try:
                    if spos is None:
                        return c.popleft()
                    else:
                        return c.pop()
                except IndexError:
                    return UNSET

            while nargs_spec:
                if spos is None:
                    nargs = nargs_spec.popleft()
                else:
                    nargs = nargs_spec.pop()

                if nargs == 1:
                    rv.append(_fetch(args))
                elif nargs > 1:
                    x: list[str | T_UNSET] = [_fetch(args) for _ in range(nargs)]

                    if spos is not None:
                        x.reverse()

                    rv.append(tuple(x))
                elif nargs < 0:
                    if spos is not None:
                        raise TypeError("Cannot have two nargs < 0")

                    spos = len(rv)
                    rv.append(UNSET)

            if spos is not None:
                rv[spos] = tuple(args)
                args = []
                rv[spos + 1 :] = reversed(rv[spos + 1 :])

            return tuple(rv), list(args)


        class _Argument:
            def __init__(self, obj: CoreArgument, dest: str | None, nargs: int = 1):
                self.dest = dest
                self.nargs = nargs
                self.obj = obj

            def process(
                self,
                value: str | cabc.Sequence[str | T_UNSET] | T_UNSET,
                state: _ParsingState,
            ) -> None:
                if self.nargs > 1:
                    assert isinstance(value, cabc.Sequence)
                    holes = sum(x is UNSET for x in value)
                    if holes == len(value):
                        value = UNSET
                    elif holes != 0:
                        raise BadArgumentUsage(
                            _("Argument {name!r} takes {nargs} values.").format(
                                name=self.dest, nargs=self.nargs
                            )
                        )


        class _OptionParser:
            def _get_value_from_state(
                self, option_name: str, option: _Option, state: _ParsingState
            ) -> str | cabc.Sequence[str] | T_UNSET | T_FLAG_NEEDS_VALUE:
                nargs = option.nargs

                value: str | cabc.Sequence[str] | T_UNSET | T_FLAG_NEEDS_VALUE

                if len(state.rargs) < nargs:
                    if option.obj._flag_needs_value:
                        value = FLAG_NEEDS_VALUE
                    else:
                        value = []
                else:
                    value = tuple(state.rargs[:nargs])

                return value
        '''
    ).lstrip()


def _requests_types_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        from collections.abc import Mapping, MutableMapping
        from typing import TYPE_CHECKING, TypeAlias

        if TYPE_CHECKING:
            class _ValidatedRequest:
                pass

            HeadersType: TypeAlias = MutableMapping[str, str | bytes] | None
        '''
    ).lstrip()


def _requests_types_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        from collections.abc import Mapping, MutableMapping
        from typing import TYPE_CHECKING, TypeAlias

        if TYPE_CHECKING:
            class _ValidatedRequest:
                pass

            HeadersType: TypeAlias = Mapping[str, str | bytes] | None
        '''
    ).lstrip()


def _requests_models_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        from collections.abc import Mapping
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from collections.abc import MutableMapping
            from http.cookiejar import CookieJar


        class RequestHooksMixin:
            pass


        class Request(RequestHooksMixin):
            method: str | None
            headers: MutableMapping[str, str | bytes]
        '''
    ).lstrip()


def _requests_models_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        from collections.abc import Mapping
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from http.cookiejar import CookieJar


        class RequestHooksMixin:
            pass


        class Request(RequestHooksMixin):
            method: str | None
            headers: Mapping[str, str | bytes]
        '''
    ).lstrip()


def _requests_7437_models_before() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import datetime


        def cookiejar_from_dict(value: dict[str, str]) -> object:
            return object()


        class PreparedRequest:
            pass


        class RequestsCookieJar:
            pass


        class Response:
            url: str
            encoding: str | None
            history: list[Response]
            reason: str | None
            cookies: RequestsCookieJar
            elapsed: datetime.timedelta
            request: PreparedRequest

            def __init__(self) -> None:
                self.url = ""
                self.encoding = None
                self.history = []

                #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
                self.reason = None

                #: A CookieJar of Cookies the server sent back.
                self.cookies = cookiejar_from_dict({})
        '''
    ).lstrip()


def _requests_7437_models_after() -> str:
    return dedent(
        '''
        from __future__ import annotations

        import datetime


        def cookiejar_from_dict(value: dict[str, str]) -> object:
            return object()


        class PreparedRequest:
            pass


        class RequestsCookieJar:
            pass


        class Response:
            url: str
            encoding: str | None
            history: list[Response]
            reason: str
            cookies: RequestsCookieJar
            elapsed: datetime.timedelta
            request: PreparedRequest

            def __init__(self) -> None:
                self.url = ""
                self.encoding = None
                self.history = []

                #: Textual reason of responded HTTP Status, e.g. "Not Found" or "OK".
                self.reason = None  # type: ignore[assignment]

                #: A CookieJar of Cookies the server sent back.
                self.cookies = cookiejar_from_dict({})
        '''
    ).lstrip()


def _flask_5808_app_before() -> str:
    return dedent(
        '''
        from __future__ import annotations


        class DispatchingJinjaLoader:
            def __init__(self, app: App) -> None:
                self.app = app


        class Scaffold:
            pass


        class App(Scaffold):
            def create_global_jinja_loader(self) -> DispatchingJinjaLoader:
                """Creates the loader for the Jinja environment."""
                return DispatchingJinjaLoader(self)

            def select_jinja_autoescape(self, filename: str) -> bool:
                """Returns ``True`` if autoescaping should be active for the given
                template name. If no template name is given, returns `True`.
                """
                if filename is None:
                    return True
                return filename.endswith((".html", ".htm", ".xml", ".xhtml", ".svg"))
        '''
    ).lstrip()


def _flask_5808_app_after() -> str:
    return dedent(
        '''
        from __future__ import annotations


        class DispatchingJinjaLoader:
            def __init__(self, app: App) -> None:
                self.app = app


        class Scaffold:
            pass


        class App(Scaffold):
            def create_global_jinja_loader(self) -> DispatchingJinjaLoader:
                """Creates the loader for the Jinja environment."""
                return DispatchingJinjaLoader(self)

            def select_jinja_autoescape(self, filename: str | None) -> bool:
                """Returns ``True`` if autoescaping should be active for the given
                template name. If no template name is given, returns `True`.
                """
                if filename is None:
                    return True
                return filename.endswith((".html", ".htm", ".xml", ".xhtml", ".svg"))
        '''
    ).lstrip()
