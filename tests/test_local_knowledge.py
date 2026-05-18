from __future__ import annotations

import json
from pathlib import Path

import pytest

from j3.local_knowledge import (
    CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES,
    REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES,
    build_click_replay_local_knowledge_records,
    build_knowledge_use_record,
    build_pytest_strict_addopts_local_knowledge_records,
    build_requests_replay_local_knowledge_records,
    extract_local_knowledge_records,
    validate_local_knowledge_record,
    write_local_knowledge_jsonl,
)


def _write_calibration_repo(repo: Path) -> None:
    (repo / "src" / "mini_lib").mkdir(parents=True)
    (repo / "testing").mkdir()
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "mini-lib"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
tests = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["testing"]
pythonpath = ["src"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "mini_lib" / "__init__.py").write_text(
        """from __future__ import annotations

from .slug import slugify

__all__ = ["slugify"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "mini_lib" / "slug.py").write_text(
        """from __future__ import annotations


def slugify(text: str) -> str:
    return "-".join(text.lower().split())
""",
        encoding="utf-8",
    )
    (repo / "testing" / "test_slug.py").write_text(
        """from __future__ import annotations

import pytest

from mini_lib import slugify


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello World", "hello-world"),
        ("Already slugged", "already-slugged"),
    ],
)
def test_slugify_cases(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_rejects_none() -> None:
    with pytest.raises(AttributeError):
        slugify(None)  # type: ignore[arg-type]
""",
        encoding="utf-8",
    )


def _tasks() -> list[dict[str, object]]:
    return [
        {
            "id": "mini-lib-tests-slugify",
            "task_type": "tests_only",
            "allowed_write_paths": ["testing/test_slug.py"],
            "public_validation_commands": [
                "python -m pytest testing/test_slug.py -q"
            ],
            "expected_failure_modes": ["wrong_test_location"],
        }
    ]


def _write_click_replay_repo(repo: Path) -> None:
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["flit_core<4"]
build-backend = "flit_core.buildapi"

[project]
name = "click"
version = "8.4.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
        encoding="utf-8",
    )
    (repo / "src" / "click" / "__init__.py").write_text(
        """from .core import Command, Context, Option, Parameter
""",
        encoding="utf-8",
    )
    (repo / "src" / "click" / "core.py").write_text(
        '''from __future__ import annotations

import inspect

UNSET = object()


class Context:
    show_default = None


class Command:
    pass


class Parameter:
    multiple = False
    nargs = 1
    required = False

    def consume_value(self, ctx, opts):
        default_value = self.get_default(ctx)
        if default_value is not UNSET:
            return default_value, "default"
        return UNSET, None

    def get_default(self, ctx, call=True):
        return getattr(self, "default", UNSET)

    def type_cast_value(self, ctx, value):
        if value is None:
            if self.multiple or self.nargs == -1:
                return ()
            return value
        if self.multiple:
            return tuple(self.type(x, self, ctx) for x in value)
        return self.type(value, param=self, ctx=ctx)

    def value_is_missing(self, value):
        if value is UNSET:
            return True
        if (self.nargs != 1 or self.multiple) and value == ():
            return True
        return False

    def process_value(self, ctx, value):
        if value is UNSET:
            if self.multiple or self.nargs == -1:
                value = ()
        else:
            value = self.type_cast_value(ctx, value)
        if self.required and self.value_is_missing(value):
            raise RuntimeError("missing")
        return value


class Option(Parameter):
    is_bool_flag = False
    secondary_opts = ()

    def __init__(self, opts, default=UNSET, show_default=None):
        self.opts = opts
        self.default = default
        self.show_default = show_default

    def get_default(self, ctx, call=True):
        return super().get_default(ctx, call=False)

    def get_help_extra(self, ctx):
        default_value = self.get_default(ctx, call=False)
        extra = {}
        show_default = bool(self.show_default)
        show_default_is_str = isinstance(self.show_default, str)
        if show_default_is_str or (show_default and default_value not in (None, UNSET)):
            if show_default_is_str:
                default_string = f"({self.show_default})"
            elif inspect.isfunction(default_value):
                default_string = "(dynamic)"
            elif self.is_bool_flag and not self.secondary_opts and not default_value:
                default_string = ""
            elif default_value == "":
                default_string = '""'
            else:
                default_string = str(default_value)
            if default_string:
                extra["default"] = default_string
        return extra

    def get_help_record(self, ctx):
        extra = self.get_help_extra(ctx)
        return self.opts[0], f"[default: {extra['default']}]" if extra else ""
''',
        encoding="utf-8",
    )
    (repo / "tests" / "test_options.py").write_text(
        '''from __future__ import annotations

import pytest

import click


def test_show_default_string(runner):
    opt = click.Option(["--limit"], show_default="unlimited")
    ctx = click.Context(click.Command("cli"))
    assert opt.get_help_extra(ctx) == {"default": "(unlimited)"}
    message = opt.get_help_record(ctx)[1]
    assert "[default: (unlimited)]" in message


def test_show_default_with_empty_string(runner):
    opt = click.Option(["--limit"], default="", show_default=True)
    ctx = click.Context(click.Command("cli"))
    message = opt.get_help_record(ctx)[1]
    assert '[default: ""]' in message


@pytest.mark.parametrize(
    ("ctx_value", "opt_value", "extra_value", "expect"),
    [(None, True, {"default": "1"}, True), (False, False, {}, False)],
)
def test_show_default_precedence(ctx_value, opt_value, extra_value, expect):
    assert bool(extra_value) is expect
''',
        encoding="utf-8",
    )


def _click_replay_row() -> dict[str, object]:
    return {
        "id": "pallets__click-issue-3298-pr-3299",
        "repo": "pallets/click",
        "prompt_text": (
            "Fix issue #3298: a semver.Version default causes an error. "
            "Accepted PR #3299 fixes a speculative empty string check."
        ),
        "prompt_source": {
            "issue_number": 3298,
            "issue_title": "semver.Version as default causing an error",
            "issue_url": "https://github.com/pallets/click/issues/3298",
            "pull_request_number": 3299,
            "pull_request_title": "Fix speculative empty string check",
            "pull_request_url": "https://github.com/pallets/click/pull/3299",
        },
        "repo_before_ref": {
            "provider": "github",
            "repo": "pallets/click",
            "branch": "stable",
            "sha": "04ef3a6f473deb2499721a8d11f92a7d2c0912f2",
        },
        "accepted_change": {
            "kind": "merged_pull_request",
            "pull_request_url": "https://github.com/pallets/click/pull/3299",
            "diff_url": "https://github.com/pallets/click/pull/3299.diff",
            "merge_commit_sha": "1458800409ed12076f18451889b0857db36aa522",
            "changed_files": ["src/click/core.py", "tests/test_options.py"],
        },
        "validation": {
            "command": "pytest tests/test_options.py -q",
            "source": "inferred_from_changed_tests",
            "availability": "partial",
        },
        "provenance_license": {
            "repository_url": "https://github.com/pallets/click",
            "license_spdx": "BSD-3-Clause",
            "license_url": "http://choosealicense.com/licenses/bsd-3-clause/",
            "review_status": "curated_metadata_only",
        },
        "stable_split": {
            "method": "sha256(id) % 100",
            "bucket": 30,
            "split": "train",
        },
        "initial_residual_labels": [
            "prompt_spec_parsing_gap",
            "local_knowledge_gap",
            "ranking_gap",
        ],
    }


def _write_requests_replay_repo(repo: Path) -> None:
    (repo / "src" / "requests").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        """[project]
name = "requests"
version = "3.0.0"

[project.optional-dependencies]
dev = ["pytest-httpbin==2.1.0", "httpbin~=0.10.0", "trustme"]
""",
        encoding="utf-8",
    )
    (repo / "requirements-dev.txt").write_text(
        "pytest-httpbin==2.1.0\nhttpbin~=0.10.0\ntrustme\n",
        encoding="utf-8",
    )
    (repo / "src" / "requests" / "__init__.py").write_text(
        """from .models import Request
from .sessions import Session
""",
        encoding="utf-8",
    )
    (repo / "src" / "requests" / "models.py").write_text(
        '''from __future__ import annotations

from collections.abc import Iterable, Mapping


basestring = (str, bytes)


def builtin_str(value):
    return str(value)


def super_len(value):
    return len(value)


class Request:
    pass


class PreparedRequest:
    def __init__(self):
        self.headers = {}
        self._body_position = None
        self.body = None

    def _encode_files(self, files, data):
        return b"", "multipart/form-data"

    def _encode_params(self, data):
        return data

    def prepare_body(self, data, files, json=None):
        body = None
        content_type = None
        if isinstance(data, Iterable) and not isinstance(data, (str, bytes, list, tuple, Mapping)):
            try:
                length = super_len(data)
            except (TypeError, AttributeError, OSError):
                length = None
            body = data
            if getattr(body, "tell", None) is not None:
                try:
                    self._body_position = body.tell()
                except OSError:
                    self._body_position = object()
            if length:
                self.headers["Content-Length"] = builtin_str(length)
            else:
                self.headers["Transfer-Encoding"] = "chunked"
        else:
            raw_data = data
            if files:
                body, content_type = self._encode_files(files, raw_data)
            elif raw_data:
                body = self._encode_params(raw_data)
                if isinstance(data, basestring) or hasattr(data, "read"):
                    content_type = None
                else:
                    content_type = "application/x-www-form-urlencoded"
            self.prepare_content_length(body)
            if content_type and ("content-type" not in self.headers):
                self.headers["Content-Type"] = content_type
        self.body = body

    def prepare_content_length(self, body):
        if body is not None:
            length = super_len(body)
            if length:
                self.headers["Content-Length"] = builtin_str(length)
''',
        encoding="utf-8",
    )
    (repo / "src" / "requests" / "sessions.py").write_text(
        '''from __future__ import annotations

from .utils import rewind_body


class SessionRedirectMixin:
    def resolve_redirects(self, resp, prepared_request):
        headers = prepared_request.headers
        rewindable = prepared_request._body_position is not None and (
            "Content-Length" in headers or "Transfer-Encoding" in headers
        )
        if rewindable:
            rewind_body(prepared_request)
        return prepared_request


class Session(SessionRedirectMixin):
    pass
''',
        encoding="utf-8",
    )
    (repo / "src" / "requests" / "utils.py").write_text(
        '''from __future__ import annotations

integer_types = (int,)


class UnrewindableBodyError(Exception):
    pass


def rewind_body(prepared_request):
    body_seek = getattr(prepared_request.body, "seek", None)
    if body_seek is not None and isinstance(prepared_request._body_position, integer_types):
        try:
            body_seek(prepared_request._body_position)
        except OSError:
            raise UnrewindableBodyError(
                "An error occurred when rewinding request body for redirect."
            )
    else:
        raise UnrewindableBodyError("Unable to rewind request body for redirect.")
''',
        encoding="utf-8",
    )
    (repo / "tests" / "conftest.py").write_text(
        '''from __future__ import annotations

import pytest


def prepare_url(value):
    httpbin_url = value.url.rstrip("/") + "/"

    def inner(*suffix):
        return httpbin_url + "/".join(suffix)

    return inner


@pytest.fixture(autouse=True)
def clean_proxy_environ(monkeypatch):
    monkeypatch.delenv("http_proxy", raising=False)


@pytest.fixture
def httpbin(httpbin):
    return prepare_url(httpbin)


@pytest.fixture
def httpbin_secure(httpbin_secure):
    return prepare_url(httpbin_secure)
''',
        encoding="utf-8",
    )
    (repo / "tests" / "test_requests.py").write_text(
        '''from __future__ import annotations

import io

import pytest

import requests
from requests.utils import UnrewindableBodyError


class TestRequests:
    def test_manual_redirect_with_partial_body_read(self, httpbin):
        response = requests.Session().resolve_redirects
        assert response is not None

    def test_prepare_body_position_non_stream(self):
        prep = requests.PreparedRequest()
        prep.prepare_body(b"the data", None)
        assert prep._body_position is None

    def test_rewind_body(self):
        data = io.BytesIO(b"the data")
        prep = requests.PreparedRequest()
        prep.prepare_body(data, None)
        assert prep._body_position == 0
        requests.utils.rewind_body(prep)

    def test_rewind_body_failed_seek(self):
        class BadFileObj:
            def tell(self):
                return 0

            def seek(self, pos, whence=0):
                raise OSError()

            def __iter__(self):
                return iter(())

        prep = requests.PreparedRequest()
        prep.prepare_body(BadFileObj(), None)
        with pytest.raises(UnrewindableBodyError):
            requests.utils.rewind_body(prep)
''',
        encoding="utf-8",
    )


def _requests_replay_row() -> dict[str, object]:
    return {
        "id": "psf__requests-issue-7432-pr-7433",
        "repo": "psf/requests",
        "prompt_text": (
            "Fix issue #7432: `prepare_body` stream detection regression. "
            "Accepted PR #7433 fixes stream detection for `__getattr__`-based file wrappers."
        ),
        "prompt_source": {
            "issue_number": 7432,
            "issue_title": "`prepare_body` stream detection regression",
            "issue_url": "https://github.com/psf/requests/issues/7432",
            "pull_request_number": 7433,
            "pull_request_title": (
                "Fix `prepare_body` stream detection for `__getattr__`-based file wrappers"
            ),
            "pull_request_url": "https://github.com/psf/requests/pull/7433",
        },
        "repo_before_ref": {
            "provider": "github",
            "repo": "psf/requests",
            "branch": "main",
            "sha": "0b401c76b6e80a4eecf3c690085b2553f6e261ca",
        },
        "accepted_change": {
            "kind": "merged_pull_request",
            "pull_request_url": "https://github.com/psf/requests/pull/7433",
            "diff_url": "https://github.com/psf/requests/pull/7433.diff",
            "merge_commit_sha": "6404f345e562d962abe6700a1c357ec1e7e18232",
            "changed_files": ["src/requests/models.py", "tests/test_requests.py"],
        },
        "validation": {
            "command": "pytest tests/test_requests.py -q",
            "source": "inferred_from_changed_tests",
            "availability": "partial",
        },
        "provenance_license": {
            "repository_url": "https://github.com/psf/requests",
            "license_spdx": "Apache-2.0",
        },
        "stable_split": {
            "method": "sha256(id) % 100",
            "bucket": 42,
            "split": "train",
        },
        "initial_residual_labels": [
            "prompt_spec_parsing_gap",
            "local_knowledge_gap",
            "ranking_gap",
        ],
    }


def _write_pytest_strict_repo(repo: Path) -> None:
    (repo / "src" / "_pytest" / "config").mkdir(parents=True)
    (repo / "testing").mkdir()
    (repo / "changelog").mkdir()
    (repo / "pyproject.toml").write_text(
        """[project]
name = "pytest"
version = "9.1.0.dev0"

[tool.pytest.ini_options]
addopts = [ "-rfEX", "-p", "pytester" ]
""",
        encoding="utf-8",
    )
    (repo / "AUTHORS").write_text(
        """Parth Patel
Patrick Hayes
Paul Müller
Peter Gessler
Prakhar Gurunani
Prashant Anand
""",
        encoding="utf-8",
    )
    (repo / "changelog" / "13484.bugfix.rst").write_text(
        "Fixed ``-W`` option values being duplicated.\n",
        encoding="utf-8",
    )
    (repo / "src" / "_pytest" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "_pytest" / "config" / "__init__.py").write_text(
        '''from __future__ import annotations

import copy
import os
import shlex


class UsageError(Exception):
    pass


class Config:
    def __init__(self):
        self.args = []
        self.option = object()
        self._inicfg = {}
        self._inicache = {}
        self.known_args_namespace = None

    def getini(self, name):
        return self._inicfg.get(name)

    def _validate_args(self, args, source):
        return list(args)

    def _warn_or_fail_if_strict(self, message: str) -> None:
        strict_config = self.getini("strict_config")
        if strict_config is None:
            strict_config = self.getini("strict")
        if strict_config:
            raise UsageError(message)

    def _get_unknown_ini_keys(self) -> set[str]:
        known_keys = {"addopts", "strict", "strict_config", "strict_markers"}
        return self._inicfg.keys() - known_keys

    def parse(self, args: list[str], addopts: bool = True) -> None:
        assert self.args == []
        if addopts:
            env_addopts = os.environ.get("PYTEST_ADDOPTS", "")
            if len(env_addopts):
                args[:] = self._validate_args(
                    shlex.split(env_addopts), "via PYTEST_ADDOPTS"
                ) + args

        self._parser.addini("addopts", "Extra command line options", "args")
        if addopts:
            args[:] = self._validate_args(
                self.getini("addopts"), "via addopts config"
            ) + args

        self.known_args_namespace = self._parser.parse_known_args(
            args, namespace=copy.copy(self.option)
        )
''',
        encoding="utf-8",
    )
    (repo / "testing" / "test_config.py").write_text(
        '''from __future__ import annotations

import pytest


class TestParseIni:
    @pytest.mark.parametrize("option_name", ["strict_config", "strict"])
    def test_strict_config_ini_option(
        self, pytester: pytest.Pytester, option_name: str
    ) -> None:
        pytester.makeini(
            f"""
            [pytest]
            unknown_option = 1
            {option_name} = True
            """
        )
        result = pytester.runpytest()
        result.stderr.fnmatch_lines("ERROR: Unknown config option: unknown_option")
        assert result.ret == pytest.ExitCode.USAGE_ERROR


class TestInvocationVariants:
    def test_addopts_from_ini_not_concatenated(
        self, pytester: pytest.Pytester
    ) -> None:
        pytester.makeini(
            """
            [pytest]
            addopts=-o
            """
        )
        with pytest.raises(SystemExit):
            pytester.parseconfig("cache_dir=ignored")
''',
        encoding="utf-8",
    )
    (repo / "testing" / "test_mark.py").write_text(
        '''from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "option_name", ["--strict-markers", "--strict", "strict_markers", "strict"]
)
def test_strict_prohibits_unregistered_markers(
    pytester: pytest.Pytester, option_name: str
) -> None:
    pytester.makepyfile(
        """
        import pytest
        @pytest.mark.unregisteredmark
        def test_hello():
            pass
        """
    )
    if option_name in ("strict_markers", "strict"):
        pytester.makeini(
            f"""
            [pytest]
            {option_name} = true
            """
        )
        result = pytester.runpytest()
    else:
        result = pytester.runpytest(option_name)
    assert result.ret != 0
    result.stdout.fnmatch_lines(
        ["'unregisteredmark' not found in `markers` configuration option"]
    )
''',
        encoding="utf-8",
    )


def _pytest_strict_replay_row() -> dict[str, object]:
    return {
        "id": "pytest-dev__pytest-issue-14442-pr-14443",
        "repo": "pytest-dev/pytest",
        "prompt_text": (
            "Fix issue #14442: `--strict-markers` and `--strict-config` "
            "in `addopts` silently stopped working."
        ),
        "prompt_source": {
            "issue_number": 14442,
            "issue_title": (
                "`--strict-markers` / `--strict-config` via `addopts` "
                "silently stopped working (pytest 9 regression)"
            ),
            "issue_url": "https://github.com/pytest-dev/pytest/issues/14442",
            "pull_request_number": 14443,
            "pull_request_title": "Fix strict options from addopts",
            "pull_request_url": "https://github.com/pytest-dev/pytest/pull/14443",
        },
        "repo_before_ref": {
            "provider": "github",
            "repo": "pytest-dev/pytest",
            "branch": "main",
            "sha": "8f81c76744daf72d4f77cfc8423f4bdc60733d78",
        },
        "accepted_change": {
            "kind": "merged_pull_request",
            "pull_request_url": "https://github.com/pytest-dev/pytest/pull/14443",
            "diff_url": "https://github.com/pytest-dev/pytest/pull/14443.diff",
            "merge_commit_sha": "a481f264d70ac3d053d5f7408f4ac1ec439d0c2f",
            "changed_files": [
                "AUTHORS",
                "changelog/14442.bugfix.rst",
                "src/_pytest/config/__init__.py",
                "testing/test_config.py",
                "testing/test_mark.py",
            ],
        },
        "validation": {
            "command": "pytest testing/test_config.py testing/test_mark.py -q",
            "source": "inferred_from_changed_tests",
            "availability": "partial",
        },
        "provenance_license": {
            "repository_url": "https://github.com/pytest-dev/pytest",
            "license_spdx": "MIT",
        },
        "stable_split": {
            "method": "sha256(id) % 100",
            "bucket": 33,
            "split": "train",
        },
        "initial_residual_labels": [
            "prompt_spec_parsing_gap",
            "local_knowledge_gap",
            "validation_gap",
            "ranking_gap",
        ],
    }


def test_extract_local_knowledge_records_emit_wedge_record_families(
    tmp_path: Path,
) -> None:
    _write_calibration_repo(tmp_path)

    records = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        repo_url="https://example.invalid/mini-lib",
        license="MIT",
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=["python -m pip install -e '.[tests]'"],
        baseline_validation_commands=["python -m pytest testing -q"],
        tasks=_tasks(),
        outcome_ids_by_task={
            "mini-lib-tests-slugify": ["real_repo_preflight/mini-lib-tests-slugify"]
        },
    )

    for record in records:
        validate_local_knowledge_record(record)
        assert json.loads(json.dumps(record, sort_keys=True)) == record
        assert record["split"] == "calibration"
        assert record["extracted_by"] == "local_knowledge/v1"
        assert len(record["provenance_hash"]) == 64

    by_type: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_type.setdefault(str(record["record_type"]), []).append(record)

    assert {
        "packaging_layout_record",
        "pytest_layout_record",
        "public_api_record",
        "validation_recipe_record",
        "pytest_pattern_record",
    } <= set(by_type)

    packaging = by_type["packaging_layout_record"][0]["data"]
    assert isinstance(packaging, dict)
    assert packaging["layout_kind"] == "src"
    assert packaging["source_roots"] == ["src"]
    assert packaging["package_roots"] == [
        {"package": "mini_lib", "path": "src/mini_lib", "source_root": "src"}
    ]
    assert packaging["build_backend"] == "setuptools.build_meta"

    pytest_layout = by_type["pytest_layout_record"][0]["data"]
    assert isinstance(pytest_layout, dict)
    assert pytest_layout["test_roots"] == ["testing"]
    assert pytest_layout["naming_patterns"] == {
        "files": ["test_*.py", "*_test.py"],
        "functions": ["test_*"],
        "classes": ["Test*"],
    }

    public_api = by_type["public_api_record"][0]["data"]
    assert isinstance(public_api, dict)
    assert public_api["module"] == "mini_lib"
    assert public_api["exported_names"] == ["slugify"]
    assert public_api["explicit_all"] == ["slugify"]
    assert public_api["test_import_examples"] == [
        {
            "path": "testing/test_slug.py",
            "import": "mini_lib",
            "names": ["slugify"],
            "kind": "from_import",
        }
    ]

    validation = by_type["validation_recipe_record"][0]
    assert validation["links"] == {
        "task_ids": ["mini-lib-tests-slugify"],
        "outcome_ids": ["real_repo_preflight/mini-lib-tests-slugify"],
        "residual_labels": ["wrong_test_location"],
    }
    validation_data = validation["data"]
    assert isinstance(validation_data, dict)
    assert validation_data["focused_commands"] == [
        "python -m pytest testing/test_slug.py -q"
    ]
    assert validation_data["allowed_write_paths"] == ["testing/test_slug.py"]

    pattern_data = [record["data"] for record in by_type["pytest_pattern_record"]]
    assert any(
        isinstance(data, dict)
        and data["pattern_kind"] == "parametrize"
        and data["decorator_shape"]["parametrize"]["arg_names"] == [  # type: ignore[index]
            "text",
            "expected",
        ]
        and data["decorator_shape"]["parametrize"]["case_count"] == 2  # type: ignore[index]
        for data in pattern_data
    )


def test_local_knowledge_jsonl_and_use_record_are_stable(tmp_path: Path) -> None:
    _write_calibration_repo(tmp_path)

    first = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        tasks=_tasks(),
    )
    second = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        tasks=_tasks(),
    )
    assert [record["id"] for record in first] == [record["id"] for record in second]

    record_ids_by_type = {record["record_type"]: record["id"] for record in first}
    use_record = build_knowledge_use_record(
        candidate_id="candidate-tests-only-001",
        task_id="mini-lib-tests-slugify",
        retrieved_record_ids=[
            str(record_ids_by_type["pytest_layout_record"]),
            str(record_ids_by_type["packaging_layout_record"]),
            str(record_ids_by_type["public_api_record"]),
            str(record_ids_by_type["validation_recipe_record"]),
        ],
        cited_purposes={
            "test_location": [str(record_ids_by_type["pytest_layout_record"])],
            "import_style": [str(record_ids_by_type["public_api_record"])],
            "validation": [str(record_ids_by_type["validation_recipe_record"])],
        },
        action_family="tests_only_existing_repo_pytest",
        validation_result={
            "status": "passed",
            "command": "python -m pytest testing/test_slug.py -q",
        },
        outcome_id="greenshot_7_existing_repo_tests_attempt/demo",
    )
    validate_local_knowledge_record(use_record)

    output = write_local_knowledge_jsonl([*first, use_record], tmp_path / "records.jsonl")
    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == len(first) + 1
    assert rows[-1]["record_type"] == "knowledge_use_record"
    assert rows[-1]["data"]["action_family"] == "tests_only_existing_repo_pytest"
    assert rows[-1]["links"]["task_ids"] == ["mini-lib-tests-slugify"]


def test_local_knowledge_validation_rejects_raw_source_blobs(
    tmp_path: Path,
) -> None:
    _write_calibration_repo(tmp_path)
    record = extract_local_knowledge_records(
        tmp_path,
        repo_id="mini-lib",
        repo_ref="0123456789abcdef0123456789abcdef01234567",
        split="calibration",
        tasks=_tasks(),
    )[0]
    broken = dict(record)
    broken["data"] = {"raw_source": "def leaked() -> None: pass"}

    with pytest.raises(ValueError, match="raw source blobs"):
        validate_local_knowledge_record(broken)


def test_click_replay_local_knowledge_records_cover_required_categories(
    tmp_path: Path,
) -> None:
    _write_click_replay_repo(tmp_path)

    first = build_click_replay_local_knowledge_records(
        tmp_path,
        _click_replay_row(),
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=["python -m pip install -e . pytest"],
        baseline_validation_commands=["pytest tests/test_options.py -q"],
    )
    second = build_click_replay_local_knowledge_records(
        tmp_path,
        _click_replay_row(),
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=["python -m pip install -e . pytest"],
        baseline_validation_commands=["pytest tests/test_options.py -q"],
    )

    assert [record["id"] for record in first] == [record["id"] for record in second]
    assert {record["record_type"] for record in first} == {
        "library_idiom_record",
        "pytest_pattern_record",
        "repo_changed_file_context_record",
        "validation_recipe_record",
    }

    categories = {
        record["data"]["knowledge_category"]  # type: ignore[index]
        for record in first
        if isinstance(record["data"], dict)
    }
    assert categories == set(CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES)

    for record in first:
        validate_local_knowledge_record(record)
        assert record["split"] == "train"
        assert record["links"]["task_ids"] == ["pallets__click-issue-3298-pr-3299"]
        assert record["links"]["residual_labels"] == ["local_knowledge_gap"]

    by_category = {
        record["data"]["knowledge_category"]: record
        for record in first
        if isinstance(record["data"], dict)
    }
    changed_context = by_category["repo_changed_file_context"]["data"]
    assert isinstance(changed_context, dict)
    assert changed_context["changed_files"] == [
        "src/click/core.py",
        "tests/test_options.py",
    ]

    validation = by_category["focused_validation_recipe"]["data"]
    assert isinstance(validation, dict)
    assert validation["focused_commands"] == ["pytest tests/test_options.py -q"]
    assert validation["required_knowledge_categories"] == list(
        CLICK_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES
    )

    non_string = by_category["click_non_string_default_handling"]["data"]
    assert isinstance(non_string, dict)
    source_evidence = non_string["source_evidence"]
    assert isinstance(source_evidence, dict)
    empty_check = source_evidence["empty_string_comparison"]
    assert isinstance(empty_check, dict)
    assert empty_check["unguarded_empty_string_comparison_present"] is True

    semver = by_category["third_party_semver_version_reproduction"]["data"]
    assert isinstance(semver, dict)
    assert semver["issue_pr"]["issue_number"] == 3298  # type: ignore[index]

    output = write_local_knowledge_jsonl(first, tmp_path / "click_records.jsonl")
    output_text = output.read_text(encoding="utf-8")
    assert "raw_source" not in output_text
    assert "source_text" not in output_text


def test_requests_replay_local_knowledge_records_cover_required_categories(
    tmp_path: Path,
) -> None:
    _write_requests_replay_repo(tmp_path)

    records = build_requests_replay_local_knowledge_records(
        tmp_path,
        _requests_replay_row(),
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=[
            "python -m venv .venv && .venv/bin/python -m pip install -q "
            "--upgrade pip setuptools wheel && .venv/bin/python -m pip "
            "install -q -e . pytest pytest-httpbin==2.1.0 httpbin~=0.10.0 trustme"
        ],
        baseline_validation_commands=[
            ".venv/bin/python -m pytest tests/test_requests.py -q "
            "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
        ],
    )

    assert {record["record_type"] for record in records} == {
        "library_idiom_record",
        "pytest_pattern_record",
        "repo_changed_file_context_record",
        "validation_recipe_record",
    }

    categories = {
        record["data"]["knowledge_category"]  # type: ignore[index]
        for record in records
        if isinstance(record["data"], dict)
    }
    assert categories == set(REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES)

    for record in records:
        validate_local_knowledge_record(record)
        assert record["split"] == "train"
        assert record["links"]["task_ids"] == ["psf__requests-issue-7432-pr-7433"]
        assert record["links"]["residual_labels"] == ["local_knowledge_gap"]

    by_category = {
        record["data"]["knowledge_category"]: record
        for record in records
        if isinstance(record["data"], dict)
    }
    changed_context = by_category["repo_changed_file_context"]["data"]
    assert isinstance(changed_context, dict)
    assert changed_context["changed_files"] == [
        "src/requests/models.py",
        "tests/test_requests.py",
    ]

    validation = by_category["focused_validation_recipe"]["data"]
    assert isinstance(validation, dict)
    assert validation["focused_commands"] == [
        ".venv/bin/python -m pytest tests/test_requests.py -q "
        "-k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'"
    ]
    assert validation["required_knowledge_categories"] == list(
        REQUESTS_REPLAY_REQUIRED_KNOWLEDGE_CATEGORIES
    )

    stream = by_category["requests_prepare_body_stream_detection"]["data"]
    assert isinstance(stream, dict)
    stream_evidence = stream["source_evidence"]
    assert isinstance(stream_evidence, dict)
    stream_detection = stream_evidence["stream_detection"]
    assert isinstance(stream_detection, dict)
    assert stream_detection["has_iterable_isinstance_check"] is True
    assert stream_detection["has_dunder_iter_hasattr_check"] is False

    wrapper = by_category["requests_getattr_file_wrapper_behavior"]["data"]
    assert isinstance(wrapper, dict)
    assert (
        wrapper["test_evidence"]["expected_new_test"]["name"]  # type: ignore[index]
        == "test_getattr_proxy_stream_follows_redirect"
    )

    fixtures = by_category["requests_pytest_httpbin_fixture_setup"]["data"]
    assert isinstance(fixtures, dict)
    fixture_evidence = fixtures["fixture_evidence"]
    assert isinstance(fixture_evidence, dict)
    assert fixture_evidence["dev_dependencies"] == [
        "pytest-httpbin==2.1.0",
        "httpbin~=0.10.0",
        "trustme",
    ]

    output = write_local_knowledge_jsonl(records, tmp_path / "requests_records.jsonl")
    output_text = output.read_text(encoding="utf-8")
    assert "raw_source" not in output_text
    assert "source_text" not in output_text


def test_pytest_strict_addopts_local_knowledge_records_cover_required_categories(
    tmp_path: Path,
) -> None:
    _write_pytest_strict_repo(tmp_path)

    records = build_pytest_strict_addopts_local_knowledge_records(
        tmp_path,
        _pytest_strict_replay_row(),
        retrieved_at="2026-05-18T00:00:00Z",
        setup_commands=["python -m pip install -e . pytest"],
        baseline_validation_commands=[
            "pytest testing/test_config.py testing/test_mark.py -q"
        ],
    )

    assert {record["record_type"] for record in records} == {
        "library_idiom_record",
        "pytest_pattern_record",
        "repo_changed_file_context_record",
        "validation_recipe_record",
    }

    categories = {
        record["data"]["knowledge_category"]  # type: ignore[index]
        for record in records
        if isinstance(record["data"], dict)
    }
    assert categories == set(PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES)

    for record in records:
        validate_local_knowledge_record(record)
        assert record["split"] == "train"
        assert record["links"]["task_ids"] == [
            "pytest-dev__pytest-issue-14442-pr-14443"
        ]
        assert record["links"]["residual_labels"] == ["local_knowledge_gap"]

    by_category = {
        record["data"]["knowledge_category"]: record
        for record in records
        if isinstance(record["data"], dict)
    }
    changed_context = by_category["repo_changed_file_context"]["data"]
    assert isinstance(changed_context, dict)
    assert changed_context["changed_files"] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
        "src/_pytest/config/__init__.py",
        "testing/test_config.py",
        "testing/test_mark.py",
    ]
    assert changed_context["auxiliary_files"] == [
        "AUTHORS",
        "changelog/14442.bugfix.rst",
    ]

    validation = by_category["focused_validation_recipe"]["data"]
    assert isinstance(validation, dict)
    assert validation["focused_commands"] == [
        "pytest testing/test_config.py testing/test_mark.py -q"
    ]
    assert validation["required_knowledge_categories"] == list(
        PYTEST_STRICT_ADDOPTS_REQUIRED_KNOWLEDGE_CATEGORIES
    )

    addopts = by_category["pytest_strict_addopts_behavior"]["data"]
    assert isinstance(addopts, dict)
    source_evidence = addopts["source_evidence"]
    assert isinstance(source_evidence, dict)
    override_ini = source_evidence["override_ini_handling"]
    assert isinstance(override_ini, dict)
    assert override_ini["imports_parse_override_ini"] is False
    assert override_ini["parse_calls_parse_override_ini"] is False

    semantics = by_category["pytest_strict_markers_config_semantics"]["data"]
    assert isinstance(semantics, dict)
    strict_source = semantics["source_evidence"]
    assert isinstance(strict_source, dict)
    assert strict_source["strict_ini_gets"] == ["strict", "strict_config"]

    patterns = by_category["pytest_repo_test_patterns"]["data"]
    assert isinstance(patterns, dict)
    test_evidence = patterns["test_evidence"]
    assert isinstance(test_evidence, dict)
    assert "pytester.runpytest" in test_evidence["pytester_tools"]

    changelog = by_category["pytest_changelog_fragment_convention"]["data"]
    assert isinstance(changelog, dict)
    assert changelog["changelog_evidence"]["path"] == "changelog/14442.bugfix.rst"  # type: ignore[index]
    assert changelog["changelog_evidence"]["exists_in_repo_before"] is False  # type: ignore[index]

    authors = by_category["pytest_authors_convention"]["data"]
    assert isinstance(authors, dict)
    assert authors["authors_evidence"]["expected_new_entry"] == "Praneeth Kodumagulla"  # type: ignore[index]
    assert authors["authors_evidence"]["expected_entry_present_in_repo_before"] is False  # type: ignore[index]

    output = write_local_knowledge_jsonl(records, tmp_path / "pytest_records.jsonl")
    output_text = output.read_text(encoding="utf-8")
    assert "raw_source" not in output_text
    assert "source_text" not in output_text
