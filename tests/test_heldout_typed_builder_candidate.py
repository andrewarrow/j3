from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from j3.heldout_typed_builder_candidate import (
    build_click_utils_annotation_spec,
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
