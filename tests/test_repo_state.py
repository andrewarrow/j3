from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from j3.features import FEATURE_VERSION, embed_python_source
from j3.repo_state import (
    REPO_STATE_AGGREGATE_KIND,
    REPO_STATE_COVERAGE_SCHEMA_VERSION,
    REPO_STATE_SCHEMA_VERSION,
    encode_repo_state,
    encode_repo_state_coverage,
    encode_repo_state_record,
)


def test_encode_repo_state_records_stable_python_file_metadata(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "z.py").write_text("VALUE = 2\n", encoding="utf-8")
    (package / "a.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("not Python\n", encoding="utf-8")

    state = encode_repo_state(tmp_path, embedding_dim=32)
    record = state.to_record()

    assert json.loads(json.dumps(record, sort_keys=True)) == record
    assert record["schema_version"] == REPO_STATE_SCHEMA_VERSION
    assert record["feature_version"] == FEATURE_VERSION
    assert record["embedding_dim"] == 32
    assert record["included_python_file_paths"] == ["pkg/a.py", "z.py"]
    assert record["aggregate"] == {
        "kind": REPO_STATE_AGGREGATE_KIND,
        "python_file_count": 2,
        "total_python_byte_count": len(
            b"def add(left, right):\n    return left + right\n"
        )
        + len(b"VALUE = 2\n"),
    }
    assert record["files"] == [
        {
            "path": "pkg/a.py",
            "sha256": hashlib.sha256(
                b"def add(left, right):\n    return left + right\n"
            ).hexdigest(),
            "byte_count": len(b"def add(left, right):\n    return left + right\n"),
        },
        {
            "path": "z.py",
            "sha256": hashlib.sha256(b"VALUE = 2\n").hexdigest(),
            "byte_count": len(b"VALUE = 2\n"),
        },
    ]
    assert len(record["repo_embedding"]) == 32


def test_encode_repo_state_aggregates_python_embeddings_by_mean(
    tmp_path: Path,
) -> None:
    first = "def add(left, right):\n    return left + right\n"
    second = "def subtract(left, right):\n    return left - right\n"
    (tmp_path / "b.py").write_text(second, encoding="utf-8")
    (tmp_path / "a.py").write_text(first, encoding="utf-8")

    record = encode_repo_state_record(tmp_path, embedding_dim=16)

    first_embedding = embed_python_source(first, dim=16)
    second_embedding = embed_python_source(second, dim=16)
    expected = [
        (left + right) / 2
        for left, right in zip(first_embedding, second_embedding, strict=True)
    ]
    assert record["included_python_file_paths"] == ["a.py", "b.py"]
    assert record["repo_embedding"] == expected


def test_encode_repo_state_reports_fixture_repo_coverage(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    tests = tmp_path / "tests"
    tests.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (docs / "usage.md").write_text("Use the CLI.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "demo"',
                "[project.scripts]",
                'demo = "pkg.cli:main"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        "from .core import Slugifier\n",
        encoding="utf-8",
    )
    (package / "core.py").write_text(
        "\n".join(
            [
                "import re",
                "",
                "class Slugifier:",
                "    def slugify(self, text):",
                "        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')",
                "",
                "def normalize(text):",
                "    return Slugifier().slugify(text)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (package / "cli.py").write_text(
        "\n".join(
            [
                "import argparse",
                "from .core import Slugifier",
                "",
                "def main():",
                "    parser = argparse.ArgumentParser()",
                "    parser.add_argument('text')",
                "    return Slugifier().slugify(parser.parse_args().text)",
                "",
                "if __name__ == '__main__':",
                "    main()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tests / "test_core.py").write_text(
        "\n".join(
            [
                "from pkg.core import normalize",
                "",
                "def test_normalize():",
                "    assert normalize('Hello, world!') == 'hello-world'",
                "",
                "class TestCli:",
                "    def test_cli_shape(self):",
                "        assert True",
                "",
            ]
        ),
        encoding="utf-8",
    )

    record = encode_repo_state_record(tmp_path, embedding_dim=16)
    coverage = record["coverage"]

    assert coverage == encode_repo_state_coverage(tmp_path).to_record()
    assert coverage["schema_version"] == REPO_STATE_COVERAGE_SCHEMA_VERSION
    assert record["included_python_file_paths"] == [
        "pkg/__init__.py",
        "pkg/cli.py",
        "pkg/core.py",
        "tests/test_core.py",
    ]
    assert len(record["repo_embedding"]) == 16

    files_by_path = {file["path"]: file["roles"] for file in coverage["files"]}
    assert files_by_path == {
        "README.md": ["doc"],
        "docs/usage.md": ["doc"],
        "pkg/__init__.py": ["python"],
        "pkg/cli.py": ["python"],
        "pkg/core.py": ["python"],
        "pyproject.toml": ["config"],
        "tests/test_core.py": ["python", "test"],
    }
    assert coverage["packages"] == [{"name": "pkg", "path": "pkg"}]
    assert coverage["configs"] == ["pyproject.toml"]
    assert coverage["docs"] == ["README.md", "docs/usage.md"]

    import_targets = {
        (item["path"], item["module"], item["imported"])
        for item in coverage["imports"]
    }
    assert import_targets == {
        ("pkg/__init__.py", ".core", "Slugifier"),
        ("pkg/cli.py", "argparse", None),
        ("pkg/cli.py", ".core", "Slugifier"),
        ("pkg/core.py", "re", None),
        ("tests/test_core.py", "pkg.core", "normalize"),
    }
    function_qualnames = {
        (item["path"], item["qualname"], item["kind"])
        for item in coverage["functions"]
    }
    assert function_qualnames == {
        ("pkg/cli.py", "main", "function"),
        ("pkg/core.py", "Slugifier.slugify", "method"),
        ("pkg/core.py", "normalize", "function"),
        ("tests/test_core.py", "test_normalize", "function"),
        ("tests/test_core.py", "TestCli.test_cli_shape", "method"),
    }
    assert coverage["classes"] == [
        {
            "path": "pkg/core.py",
            "name": "Slugifier",
            "methods": ["slugify"],
            "line": 3,
        },
        {
            "path": "tests/test_core.py",
            "name": "TestCli",
            "methods": ["test_cli_shape"],
            "line": 6,
        },
    ]
    assert coverage["tests"] == [
        {
            "path": "tests/test_core.py",
            "functions": ["TestCli.test_cli_shape", "test_normalize"],
            "classes": ["TestCli"],
        }
    ]
    assert coverage["entrypoints"] == [
        {
            "path": "pkg/cli.py",
            "kind": "main_guard",
            "name": "cli",
            "target": "pkg/cli.py",
        },
        {
            "path": "pyproject.toml",
            "kind": "project_script",
            "name": "demo",
            "target": "pkg.cli:main",
        },
    ]
    assert coverage["parse_errors"] == []


def test_encode_empty_repo_state_uses_zero_embedding(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("empty of Python files\n", encoding="utf-8")

    record = encode_repo_state_record(tmp_path, embedding_dim=24)

    assert record["included_python_file_paths"] == []
    assert record["files"] == []
    assert record["aggregate"] == {
        "kind": REPO_STATE_AGGREGATE_KIND,
        "python_file_count": 0,
        "total_python_byte_count": 0,
    }
    assert record["repo_embedding"] == [0.0] * 24


def test_encode_repo_state_uses_repo_source_exclusions(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('included')\n", encoding="utf-8")
    excluded = tmp_path / ".venv" / "lib"
    excluded.mkdir(parents=True)
    (excluded / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "cached.py").write_text("print('ignored')\n", encoding="utf-8")

    record = encode_repo_state_record(tmp_path, embedding_dim=16)

    assert record["included_python_file_paths"] == ["app.py"]
    assert [file["path"] for file in record["files"]] == ["app.py"]  # type: ignore[index]


def test_encode_repo_state_validates_embedding_dimension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="embedding_dim must be >= 8"):
        encode_repo_state(tmp_path, embedding_dim=7)


def test_encode_repo_state_rejects_missing_repo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="repo does not exist"):
        encode_repo_state(tmp_path / "missing", embedding_dim=16)
