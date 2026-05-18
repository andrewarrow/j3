"""Deterministic repository state encoder for Python source files."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path

from j3.features import FEATURE_VERSION as PYTHON_SOURCE_FEATURE_VERSION
from j3.features import embed_python_source, mean_vector
from j3.repo import DEFAULT_EXCLUDE_DIRS
from j3.repo import PythonSource
from j3.repo import iter_python_sources


REPO_STATE_SCHEMA_VERSION = "repo-state-v1"
REPO_STATE_COVERAGE_SCHEMA_VERSION = "repo-state-coverage-v1"
REPO_STATE_AGGREGATE_KIND = "mean-python-source-embeddings-v1"
DEFAULT_REPO_STATE_EMBEDDING_DIM = 256
MIN_REPO_STATE_EMBEDDING_DIM = 8
CONFIG_FILE_NAMES = frozenset(
    {
        ".pre-commit-config.yaml",
        ".ruff.toml",
        "mypy.ini",
        "pyproject.toml",
        "pytest.ini",
        "requirements-dev.txt",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "tox.ini",
    }
)
DOC_FILE_NAMES = frozenset(
    {"README.md", "README.rst", "CHANGELOG.md", "CHANGELOG.rst"}
)
DOC_SUFFIXES = frozenset({".md", ".rst"})


@dataclass(frozen=True, slots=True)
class RepoStateFile:
    """Metadata for one Python file included in a repo-state record."""

    path: str
    sha256: str
    byte_count: int

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True, slots=True)
class RepoStateCoveredFile:
    """One repo file that contributes to coverage inspection."""

    path: str
    roles: tuple[str, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "roles": list(self.roles),
        }


@dataclass(frozen=True, slots=True)
class RepoStatePackage:
    """A Python package directory discovered from an ``__init__.py`` file."""

    name: str
    path: str

    def to_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class RepoStateImport:
    """One import statement target from a Python source file."""

    path: str
    module: str
    imported: str | None
    level: int
    line: int

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "module": self.module,
            "imported": self.imported,
            "level": self.level,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class RepoStateFunction:
    """A top-level function or class method from a Python source file."""

    path: str
    name: str
    qualname: str
    kind: str
    line: int

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "name": self.name,
            "qualname": self.qualname,
            "kind": self.kind,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class RepoStateClass:
    """A top-level class from a Python source file."""

    path: str
    name: str
    methods: tuple[str, ...]
    line: int

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "name": self.name,
            "methods": list(self.methods),
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class RepoStateTestFile:
    """Test coverage discovered from a Python test file."""

    path: str
    functions: tuple[str, ...]
    classes: tuple[str, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "functions": list(self.functions),
            "classes": list(self.classes),
        }


@dataclass(frozen=True, slots=True)
class RepoStateEntrypoint:
    """A likely executable entrypoint from source or packaging metadata."""

    path: str
    kind: str
    name: str
    target: str

    def to_record(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "name": self.name,
            "target": self.target,
        }


@dataclass(frozen=True, slots=True)
class RepoStateCoverage:
    """Inspectable repo coverage summary beside the deterministic embedding."""

    files: tuple[RepoStateCoveredFile, ...]
    packages: tuple[RepoStatePackage, ...]
    imports: tuple[RepoStateImport, ...]
    functions: tuple[RepoStateFunction, ...]
    classes: tuple[RepoStateClass, ...]
    tests: tuple[RepoStateTestFile, ...]
    configs: tuple[str, ...]
    entrypoints: tuple[RepoStateEntrypoint, ...]
    docs: tuple[str, ...]
    parse_errors: tuple[dict[str, str], ...] = ()
    schema_version: str = REPO_STATE_COVERAGE_SCHEMA_VERSION

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "files": [file.to_record() for file in self.files],
            "packages": [package.to_record() for package in self.packages],
            "imports": [item.to_record() for item in self.imports],
            "functions": [function.to_record() for function in self.functions],
            "classes": [class_.to_record() for class_ in self.classes],
            "tests": [test.to_record() for test in self.tests],
            "configs": list(self.configs),
            "entrypoints": [
                entrypoint.to_record() for entrypoint in self.entrypoints
            ],
            "docs": list(self.docs),
            "parse_errors": list(self.parse_errors),
        }


@dataclass(frozen=True, slots=True)
class RepoState:
    """Stable JSON-serializable representation of a Python repository state."""

    schema_version: str
    feature_version: str
    embedding_dim: int
    included_python_file_paths: tuple[str, ...]
    files: tuple[RepoStateFile, ...]
    repo_embedding: tuple[float, ...]
    coverage: RepoStateCoverage
    aggregate_kind: str = REPO_STATE_AGGREGATE_KIND

    @property
    def python_file_count(self) -> int:
        return len(self.files)

    @property
    def total_python_byte_count(self) -> int:
        return sum(file.byte_count for file in self.files)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "feature_version": self.feature_version,
            "embedding_dim": self.embedding_dim,
            "included_python_file_paths": list(self.included_python_file_paths),
            "files": [file.to_record() for file in self.files],
            "aggregate": {
                "kind": self.aggregate_kind,
                "python_file_count": self.python_file_count,
                "total_python_byte_count": self.total_python_byte_count,
            },
            "coverage": self.coverage.to_record(),
            "repo_embedding": list(self.repo_embedding),
        }


def encode_repo_state(
    repo_root: Path,
    *,
    embedding_dim: int = DEFAULT_REPO_STATE_EMBEDDING_DIM,
) -> RepoState:
    """Encode Python files under ``repo_root`` into a deterministic repo state."""

    if embedding_dim < MIN_REPO_STATE_EMBEDDING_DIM:
        raise ValueError(
            f"embedding_dim must be >= {MIN_REPO_STATE_EMBEDDING_DIM}"
        )

    sources = iter_python_sources(repo_root)
    file_records: list[RepoStateFile] = []
    file_embeddings: list[list[float]] = []

    for source in sources:
        raw_bytes = source.path.read_bytes()
        embedding = embed_python_source(source.text, dim=embedding_dim)
        _validate_embedding_dimension(
            embedding,
            dim=embedding_dim,
            context=f"embedding for {source.relative_path}",
        )
        file_records.append(
            RepoStateFile(
                path=source.relative_path,
                sha256=hashlib.sha256(raw_bytes).hexdigest(),
                byte_count=len(raw_bytes),
            )
        )
        file_embeddings.append(embedding)

    repo_embedding = mean_vector(file_embeddings, dim=embedding_dim)
    _validate_embedding_dimension(
        repo_embedding,
        dim=embedding_dim,
        context="repo embedding",
    )

    return RepoState(
        schema_version=REPO_STATE_SCHEMA_VERSION,
        feature_version=PYTHON_SOURCE_FEATURE_VERSION,
        embedding_dim=embedding_dim,
        included_python_file_paths=tuple(file.path for file in file_records),
        files=tuple(file_records),
        repo_embedding=tuple(repo_embedding),
        coverage=_build_repo_state_coverage(repo_root, sources=sources),
    )


def encode_repo_state_record(
    repo_root: Path,
    *,
    embedding_dim: int = DEFAULT_REPO_STATE_EMBEDDING_DIM,
) -> dict[str, object]:
    """Return a JSON-serializable repo-state record."""

    return encode_repo_state(repo_root, embedding_dim=embedding_dim).to_record()


def encode_repo_state_coverage(repo_root: Path) -> RepoStateCoverage:
    """Return inspectable repo coverage without computing embeddings."""

    sources = iter_python_sources(repo_root)
    return _build_repo_state_coverage(repo_root, sources=sources)


def _validate_embedding_dimension(
    embedding: list[float],
    *,
    dim: int,
    context: str,
) -> None:
    if len(embedding) != dim:
        raise ValueError(f"{context} must have dimension {dim}")


def _build_repo_state_coverage(
    repo_root: Path,
    *,
    sources: list[PythonSource],
) -> RepoStateCoverage:
    root = repo_root.expanduser().resolve()
    repo_files = _iter_coverage_file_paths(root)
    source_by_path = {source.relative_path: source for source in sources}
    config_paths = tuple(path for path in repo_files if _is_config_path(path))
    doc_paths = tuple(path for path in repo_files if _is_doc_path(path))

    imports: list[RepoStateImport] = []
    functions: list[RepoStateFunction] = []
    classes: list[RepoStateClass] = []
    tests: list[RepoStateTestFile] = []
    entrypoints: list[RepoStateEntrypoint] = []
    parse_errors: list[dict[str, str]] = []

    for relative_path in sorted(source_by_path):
        source = source_by_path[relative_path]
        try:
            tree = ast.parse(source.text, filename=relative_path)
        except SyntaxError as exc:
            parse_errors.append(
                {
                    "path": relative_path,
                    "message": exc.msg,
                    "line": str(exc.lineno or ""),
                }
            )
            continue
        analysis = _analyze_python_tree(relative_path, tree)
        imports.extend(analysis.imports)
        functions.extend(analysis.functions)
        classes.extend(analysis.classes)
        if analysis.test_file is not None:
            tests.append(analysis.test_file)
        entrypoints.extend(analysis.entrypoints)

    entrypoints.extend(_entrypoints_from_pyproject(root))
    covered_files = tuple(
        RepoStateCoveredFile(path=path, roles=_coverage_roles(path, source_by_path))
        for path in repo_files
    )

    return RepoStateCoverage(
        files=covered_files,
        packages=_discover_packages(source_by_path),
        imports=tuple(
            sorted(
                imports,
                key=lambda item: (
                    item.path,
                    item.line,
                    item.module,
                    item.imported or "",
                ),
            )
        ),
        functions=tuple(
            sorted(functions, key=lambda item: (item.path, item.line, item.qualname))
        ),
        classes=tuple(
            sorted(classes, key=lambda item: (item.path, item.line, item.name))
        ),
        tests=tuple(sorted(tests, key=lambda item: item.path)),
        configs=config_paths,
        entrypoints=tuple(
            sorted(entrypoints, key=lambda item: (item.path, item.kind, item.name))
        ),
        docs=doc_paths,
        parse_errors=tuple(parse_errors),
    )


@dataclass(frozen=True, slots=True)
class _PythonTreeAnalysis:
    imports: tuple[RepoStateImport, ...]
    functions: tuple[RepoStateFunction, ...]
    classes: tuple[RepoStateClass, ...]
    test_file: RepoStateTestFile | None
    entrypoints: tuple[RepoStateEntrypoint, ...]


def _analyze_python_tree(path: str, tree: ast.Module) -> _PythonTreeAnalysis:
    imports: list[RepoStateImport] = []
    functions: list[RepoStateFunction] = []
    classes: list[RepoStateClass] = []
    test_functions: list[str] = []
    test_classes: list[str] = []
    entrypoints: list[RepoStateEntrypoint] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                RepoStateImport(
                    path=path,
                    module=alias.name,
                    imported=None,
                    level=0,
                    line=node.lineno,
                )
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            imports.extend(
                RepoStateImport(
                    path=path,
                    module="." * node.level + (node.module or ""),
                    imported=alias.name,
                    level=node.level,
                    line=node.lineno,
                )
                for alias in node.names
            )

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = (
                "async_function"
                if isinstance(node, ast.AsyncFunctionDef)
                else "function"
            )
            functions.append(
                RepoStateFunction(
                    path=path,
                    name=node.name,
                    qualname=node.name,
                    kind=kind,
                    line=node.lineno,
                )
            )
            if _is_test_function(node.name):
                test_functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            method_names = tuple(
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            classes.append(
                RepoStateClass(
                    path=path,
                    name=node.name,
                    methods=method_names,
                    line=node.lineno,
                )
            )
            if _is_test_class(node.name):
                test_classes.append(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = (
                        "async_method"
                        if isinstance(child, ast.AsyncFunctionDef)
                        else "method"
                    )
                    functions.append(
                        RepoStateFunction(
                            path=path,
                            name=child.name,
                            qualname=f"{node.name}.{child.name}",
                            kind=kind,
                            line=child.lineno,
                        )
                    )
                    if _is_test_class(node.name) and _is_test_function(child.name):
                        test_functions.append(f"{node.name}.{child.name}")

    if path.endswith("/__main__.py") or path == "__main__.py":
        entrypoints.append(
            RepoStateEntrypoint(
                path=path,
                kind="module_main",
                name=Path(path).parent.name or "__main__",
                target=path,
            )
        )
    if _has_main_guard(tree):
        entrypoints.append(
            RepoStateEntrypoint(
                path=path,
                kind="main_guard",
                name=Path(path).stem,
                target=path,
            )
        )

    test_file = None
    if _is_test_path(path) or test_functions or test_classes:
        test_file = RepoStateTestFile(
            path=path,
            functions=tuple(sorted(set(test_functions))),
            classes=tuple(sorted(set(test_classes))),
        )

    return _PythonTreeAnalysis(
        imports=tuple(imports),
        functions=tuple(functions),
        classes=tuple(classes),
        test_file=test_file,
        entrypoints=tuple(entrypoints),
    )


def _iter_coverage_file_paths(root: Path) -> tuple[str, ...]:
    if not root.exists():
        raise FileNotFoundError(f"repo does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"repo is not a directory: {root}")
    paths: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if any(part in DEFAULT_EXCLUDE_DIRS for part in relative.parts):
            continue
        paths.append(relative.as_posix())
    return tuple(paths)


def _coverage_roles(
    path: str,
    source_by_path: dict[str, PythonSource],
) -> tuple[str, ...]:
    roles: list[str] = []
    if path in source_by_path:
        roles.append("python")
    if _is_test_path(path):
        roles.append("test")
    if _is_config_path(path):
        roles.append("config")
    if _is_doc_path(path):
        roles.append("doc")
    if not roles:
        roles.append("other")
    return tuple(roles)


def _discover_packages(
    source_by_path: dict[str, PythonSource],
) -> tuple[RepoStatePackage, ...]:
    packages: list[RepoStatePackage] = []
    for path in sorted(source_by_path):
        if path == "__init__.py":
            packages.append(RepoStatePackage(name="", path="."))
            continue
        if not path.endswith("/__init__.py"):
            continue
        package_path = path.removesuffix("/__init__.py")
        packages.append(
            RepoStatePackage(
                name=package_path.replace("/", "."),
                path=package_path,
            )
        )
    return tuple(packages)


def _entrypoints_from_pyproject(root: Path) -> tuple[RepoStateEntrypoint, ...]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return ()
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return ()
    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return ()
    entrypoints = []
    for name, target in scripts.items():
        if isinstance(name, str) and isinstance(target, str):
            entrypoints.append(
                RepoStateEntrypoint(
                    path="pyproject.toml",
                    kind="project_script",
                    name=name,
                    target=target,
                )
            )
    return tuple(entrypoints)


def _is_config_path(path: str) -> bool:
    name = Path(path).name
    if name in CONFIG_FILE_NAMES:
        return True
    if name.startswith("requirements") and name.endswith(".txt"):
        return True
    return False


def _is_doc_path(path: str) -> bool:
    path_obj = Path(path)
    if path_obj.name in DOC_FILE_NAMES:
        return True
    return bool(
        path_obj.parts
        and path_obj.parts[0] == "docs"
        and path_obj.suffix in DOC_SUFFIXES
    )


def _is_test_path(path: str) -> bool:
    path_obj = Path(path)
    return (
        path_obj.parts[0] == "tests"
        if path_obj.parts
        else False
    ) or path_obj.name.startswith("test_") or path_obj.name.endswith("_test.py")


def _is_test_function(name: str) -> bool:
    return name.startswith("test_")


def _is_test_class(name: str) -> bool:
    return name.startswith("Test")


def _has_main_guard(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.If) and _is_main_guard_test(node.test):
            return True
    return False


def _is_main_guard_test(node: ast.expr) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False
    if len(node.comparators) != 1:
        return False
    left = _constant_string(node.left)
    right = _constant_string(node.comparators[0])
    return {left, right} == {"__name__", "__main__"}


def _constant_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
