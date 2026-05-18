"""Extract compact local-knowledge records for the tests-only wedge."""

from __future__ import annotations

import ast
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import tomllib


LOCAL_KNOWLEDGE_SCHEMA_VERSION = "local-knowledge-record-v1"
LOCAL_KNOWLEDGE_EXTRACTOR_NAME = "local_knowledge"
LOCAL_KNOWLEDGE_EXTRACTOR_VERSION = "v1"
LOCAL_KNOWLEDGE_EXTRACTED_BY = (
    f"{LOCAL_KNOWLEDGE_EXTRACTOR_NAME}/{LOCAL_KNOWLEDGE_EXTRACTOR_VERSION}"
)

RECORD_TYPES = {
    "pytest_layout_record",
    "pytest_pattern_record",
    "packaging_layout_record",
    "public_api_record",
    "validation_recipe_record",
    "knowledge_use_record",
}
SPLITS = {"calibration", "train", "validation", "test", "heldout"}
CONFIDENCE_VALUES = {"observed", "inferred", "validated"}
RAW_BLOB_KEYS = {
    "raw_source",
    "source_text",
    "source_blob",
    "raw_blob",
    "raw_diff",
    "full_source",
}


def extract_local_knowledge_records(
    repo: Path,
    *,
    repo_id: str,
    repo_ref: str,
    split: str = "calibration",
    repo_url: str = "",
    license: str = "",
    retrieved_at: str = "unknown",
    setup_commands: Sequence[str] = (),
    baseline_validation_commands: Sequence[str] = (),
    tasks: Sequence[Mapping[str, object]] = (),
    outcome_ids_by_task: Mapping[str, Sequence[str]] | None = None,
) -> tuple[dict[str, object], ...]:
    """Extract JSONL-ready pytest, packaging, import, and validation records.

    The extractor works from a local checkout or fixture. It stores compact
    config and AST shapes plus checksums, not raw source blobs.
    """

    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"repo does not exist: {resolved}")
    _validate_split(split)

    context = {
        "repo_id": repo_id,
        "repo_ref": repo_ref,
        "split": split,
        "repo_url": repo_url,
        "license": license,
        "retrieved_at": retrieved_at,
    }
    pyproject = _load_pyproject(resolved)
    pytest_ini = _load_pytest_ini(resolved)
    python_files = _python_files(resolved)
    test_files = tuple(path for path in python_files if _is_test_file(path))

    records: list[dict[str, object]] = [
        _packaging_layout_record(resolved, context, pyproject, python_files),
        _pytest_layout_record(resolved, context, pyproject, pytest_ini, test_files),
    ]
    records.extend(_public_api_records(resolved, context, python_files))
    records.extend(
        _validation_recipe_records(
            resolved,
            context,
            setup_commands=setup_commands,
            baseline_validation_commands=baseline_validation_commands,
            tasks=tasks,
            outcome_ids_by_task=outcome_ids_by_task or {},
        )
    )
    records.extend(_pytest_pattern_records(resolved, context, test_files))

    for record in records:
        validate_local_knowledge_record(record)
    return tuple(records)


def build_knowledge_use_record(
    *,
    candidate_id: str,
    task_id: str,
    retrieved_record_ids: Sequence[str],
    action_family: str,
    validation_result: Mapping[str, object],
    split: str = "calibration",
    outcome_id: str | None = None,
    residual_labels: Sequence[str] = (),
    cited_purposes: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    """Build the citation row a tests-only planner can attach to a candidate."""

    _validate_split(split)
    data = {
        "candidate_id": candidate_id,
        "retrieved_record_ids": list(retrieved_record_ids),
        "cited_purposes": {
            key: list(value) for key, value in (cited_purposes or {}).items()
        },
        "action_family": action_family,
        "validation_result": _json_copy(validation_result),
    }
    links = {
        "task_ids": [task_id],
        "outcome_ids": [outcome_id] if outcome_id else [],
        "residual_labels": list(residual_labels),
    }
    source = {
        "kind": "candidate_outcome",
        "repo": "",
        "ref": "",
        "path": candidate_id,
        "url": "",
        "license": "",
        "retrieved_at": "candidate-time",
    }
    return _record(
        record_type="knowledge_use_record",
        source=source,
        split=split,
        provenance_hash=_sha256_json({"data": data, "links": links}),
        confidence="observed",
        links=links,
        data=data,
    )


def write_local_knowledge_jsonl(
    records: Sequence[Mapping[str, object]],
    path: Path,
) -> Path:
    """Write validated local-knowledge rows to JSONL."""

    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("w", encoding="utf-8") as handle:
        for record in records:
            validate_local_knowledge_record(record)
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return resolved


def validate_local_knowledge_record(row: Mapping[str, object]) -> None:
    """Validate the stable local-knowledge schema surface."""

    if row.get("schema_version") != LOCAL_KNOWLEDGE_SCHEMA_VERSION:
        raise ValueError("local knowledge record has unsupported schema_version")
    if row.get("record_type") not in RECORD_TYPES:
        raise ValueError("local knowledge record has unsupported record_type")
    record_id = row.get("id")
    if not isinstance(record_id, str) or not _is_sha256(record_id):
        raise ValueError("local knowledge record id must be a sha256 hex digest")
    provenance_hash = row.get("provenance_hash")
    if not isinstance(provenance_hash, str) or not _is_sha256(provenance_hash):
        raise ValueError("local knowledge record provenance_hash must be sha256")
    if row.get("split") not in SPLITS:
        raise ValueError("local knowledge record has unsupported split")
    if row.get("confidence") not in CONFIDENCE_VALUES:
        raise ValueError("local knowledge record has unsupported confidence")
    if row.get("extracted_by") != LOCAL_KNOWLEDGE_EXTRACTED_BY:
        raise ValueError("local knowledge record has unsupported extracted_by")

    source = row.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("local knowledge record source must be an object")
    for field_name in ("kind", "repo", "ref", "path", "retrieved_at"):
        if not isinstance(source.get(field_name), str):
            raise ValueError(f"local knowledge source.{field_name} must be a string")

    extractor = row.get("extractor")
    if not isinstance(extractor, Mapping):
        raise ValueError("local knowledge record extractor must be an object")
    if extractor.get("name") != LOCAL_KNOWLEDGE_EXTRACTOR_NAME:
        raise ValueError("local knowledge record extractor.name is unsupported")
    if extractor.get("version") != LOCAL_KNOWLEDGE_EXTRACTOR_VERSION:
        raise ValueError("local knowledge record extractor.version is unsupported")

    links = row.get("links")
    if not isinstance(links, Mapping):
        raise ValueError("local knowledge record links must be an object")
    for field_name in ("task_ids", "outcome_ids", "residual_labels"):
        value = links.get(field_name)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"local knowledge links.{field_name} must be strings")

    if _contains_raw_blob_key(row):
        raise ValueError("local knowledge records must not contain raw source blobs")
    json.dumps(row, sort_keys=True)


def _packaging_layout_record(
    repo: Path,
    context: Mapping[str, str],
    pyproject: Mapping[str, object],
    python_files: Sequence[str],
) -> dict[str, object]:
    source_roots = ["src"] if (repo / "src").is_dir() else ["."]
    package_roots = _package_roots(repo, python_files)
    single_modules = _single_modules(python_files)
    source_paths = ["pyproject.toml"] if (repo / "pyproject.toml").exists() else list(python_files)
    data = {
        "layout_kind": "src" if "src" in source_roots else "flat",
        "source_roots": source_roots,
        "package_roots": package_roots,
        "single_modules": single_modules,
        "build_backend": _nested_str(pyproject, ("build-system", "build-backend")),
        "project_name": _nested_str(pyproject, ("project", "name")),
        "requires_python": _nested_str(pyproject, ("project", "requires-python")),
        "optional_dependency_groups": sorted(
            _nested_mapping(pyproject, ("project", "optional-dependencies")).keys()
        ),
        "editable_install_command": "python -m pip install -e .",
        "config_shape": {
            "pyproject_tables": sorted(pyproject.keys()),
            "has_setup_cfg": (repo / "setup.cfg").exists(),
            "has_setup_py": (repo / "setup.py").exists(),
        },
    }
    return _source_record(
        record_type="packaging_layout_record",
        repo=repo,
        context=context,
        source_kind="repo_config",
        source_path="pyproject.toml" if (repo / "pyproject.toml").exists() else ".",
        provenance_paths=source_paths,
        confidence="observed",
        links={"task_ids": _tests_only_task_ids(()), "outcome_ids": [], "residual_labels": []},
        data=data,
    )


def _pytest_layout_record(
    repo: Path,
    context: Mapping[str, str],
    pyproject: Mapping[str, object],
    pytest_ini: Mapping[str, str],
    test_files: Sequence[str],
) -> dict[str, object]:
    configured_testpaths = _pytest_config_list(pyproject, pytest_ini, "testpaths")
    python_files = _pytest_config_list(pyproject, pytest_ini, "python_files")
    python_functions = _pytest_config_list(pyproject, pytest_ini, "python_functions")
    python_classes = _pytest_config_list(pyproject, pytest_ini, "python_classes")
    test_roots = configured_testpaths or _discovered_test_roots(test_files)
    data = {
        "test_roots": test_roots,
        "naming_patterns": {
            "files": python_files or ["test_*.py", "*_test.py"],
            "functions": python_functions or ["test_*"],
            "classes": python_classes or ["Test*"],
        },
        "config_files": [
            path
            for path in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
            if (repo / path).exists()
        ],
        "import_mode_hints": _import_mode_hints(repo, test_files),
        "adjacent_examples": _test_file_examples(repo, test_files),
    }
    source_path = "pyproject.toml" if (repo / "pyproject.toml").exists() else (
        test_files[0] if test_files else "."
    )
    provenance_paths = [source_path, *test_files[:5]]
    return _source_record(
        record_type="pytest_layout_record",
        repo=repo,
        context=context,
        source_kind="repo_test_tree",
        source_path=source_path,
        provenance_paths=provenance_paths,
        confidence="observed",
        links={"task_ids": _tests_only_task_ids(()), "outcome_ids": [], "residual_labels": []},
        data=data,
    )


def _public_api_records(
    repo: Path,
    context: Mapping[str, str],
    python_files: Sequence[str],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    test_files = tuple(path for path in python_files if _is_test_file(path))
    for path in python_files:
        if _is_test_file(path) or Path(path).name == "conftest.py":
            continue
        if not (path.endswith("__init__.py") or _is_public_single_module(path, python_files)):
            continue
        module = _module_name_from_path(path)
        if not module:
            continue
        tree = _parse_python(repo / path)
        exports = _public_exports(tree)
        data = {
            "module": module,
            "source_path": path,
            "exported_names": exports["exported_names"],
            "explicit_all": exports["explicit_all"],
            "re_export_paths": exports["re_export_paths"],
            "test_import_examples": _test_import_examples(repo, test_files, module),
        }
        records.append(
            _source_record(
                record_type="public_api_record",
                repo=repo,
                context=context,
                source_kind="repo_file",
                source_path=path,
                provenance_paths=[path, *test_files[:3]],
                confidence="observed",
                links={"task_ids": [], "outcome_ids": [], "residual_labels": []},
                data=data,
            )
        )
    return tuple(records)


def _validation_recipe_records(
    repo: Path,
    context: Mapping[str, str],
    *,
    setup_commands: Sequence[str],
    baseline_validation_commands: Sequence[str],
    tasks: Sequence[Mapping[str, object]],
    outcome_ids_by_task: Mapping[str, Sequence[str]],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for task in tasks:
        task_id = _required_str(task, "id")
        commands = _string_sequence(task.get("public_validation_commands", ()))
        if not commands:
            continue
        data = {
            "task_id": task_id,
            "setup_commands": list(setup_commands),
            "baseline_validation_commands": list(baseline_validation_commands),
            "focused_commands": commands,
            "allowed_write_paths": _string_sequence(task.get("allowed_write_paths", ())),
            "network_policy": {
                "setup_network_allowed": True,
                "candidate_validation_network_allowed": False,
            },
            "timeout_seconds": 600,
            "observed_result": "not_run",
        }
        links = {
            "task_ids": [task_id],
            "outcome_ids": list(outcome_ids_by_task.get(task_id, ())),
            "residual_labels": _string_sequence(task.get("expected_failure_modes", ())),
        }
        records.append(
            _source_record(
                record_type="validation_recipe_record",
                repo=repo,
                context=context,
                source_kind="repo_manifest",
                source_path="task:" + task_id,
                provenance_paths=_validation_provenance_paths(repo),
                confidence="inferred",
                links=links,
                data=data,
            )
        )
    return tuple(records)


def _pytest_pattern_records(
    repo: Path,
    context: Mapping[str, str],
    test_files: Sequence[str],
) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for path in test_files:
        tree = _parse_python(repo / path)
        imports = _imports(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            pattern = _pytest_pattern_from_function(node, imports)
            if pattern is None:
                continue
            pattern["source_path"] = path
            records.append(
                _source_record(
                    record_type="pytest_pattern_record",
                    repo=repo,
                    context=context,
                    source_kind="repo_file",
                    source_path=path,
                    provenance_paths=[path],
                    confidence="observed",
                    links={"task_ids": [], "outcome_ids": [], "residual_labels": []},
                    data=pattern,
                )
            )
    return tuple(records)


def _pytest_pattern_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    imports: Sequence[Mapping[str, str]],
) -> dict[str, object] | None:
    decorators = [_call_name(decorator) for decorator in node.decorator_list]
    tools = sorted(_pytest_tools(node))
    pattern_kind = None
    parametrize_shape: dict[str, object] | None = None
    if any(name.endswith("parametrize") for name in decorators):
        pattern_kind = "parametrize"
        parametrize_shape = _parametrize_shape(node.decorator_list)
    elif any(name.endswith("fixture") for name in decorators):
        pattern_kind = "fixture"
    elif any(tool.startswith("pytest.raises") for tool in tools):
        pattern_kind = "exception_assertion"
    elif any(tool.startswith("monkeypatch.") for tool in tools) or any(
        arg.arg == "monkeypatch" for arg in node.args.args
    ):
        pattern_kind = "monkeypatch"

    if pattern_kind is None:
        return None
    return {
        "pattern_kind": pattern_kind,
        "function_name": node.name,
        "line_span": [node.lineno, node.end_lineno or node.lineno],
        "decorator_shape": {
            "names": decorators,
            "parametrize": parametrize_shape,
        },
        "argument_names": [arg.arg for arg in node.args.args],
        "pytest_tools": tools,
        "neighboring_imports": list(imports),
    }


def _source_record(
    *,
    record_type: str,
    repo: Path,
    context: Mapping[str, str],
    source_kind: str,
    source_path: str,
    provenance_paths: Sequence[str],
    confidence: str,
    links: Mapping[str, Sequence[str]],
    data: Mapping[str, object],
) -> dict[str, object]:
    source = {
        "kind": source_kind,
        "repo": context["repo_id"],
        "ref": context["repo_ref"],
        "path": source_path,
        "url": context["repo_url"],
        "license": context["license"],
        "retrieved_at": context["retrieved_at"],
    }
    return _record(
        record_type=record_type,
        source=source,
        split=context["split"],
        provenance_hash=_provenance_hash(repo, provenance_paths),
        confidence=confidence,
        links={
            "task_ids": list(links.get("task_ids", ())),
            "outcome_ids": list(links.get("outcome_ids", ())),
            "residual_labels": list(links.get("residual_labels", ())),
        },
        data=data,
    )


def _record(
    *,
    record_type: str,
    source: Mapping[str, str],
    split: str,
    provenance_hash: str,
    confidence: str,
    links: Mapping[str, Sequence[str]],
    data: Mapping[str, object],
) -> dict[str, object]:
    payload = {
        "record_type": record_type,
        "source": dict(source),
        "split": split,
        "provenance_hash": provenance_hash,
        "confidence": confidence,
        "links": {
            "task_ids": list(links.get("task_ids", ())),
            "outcome_ids": list(links.get("outcome_ids", ())),
            "residual_labels": list(links.get("residual_labels", ())),
        },
        "data": _json_copy(data),
    }
    record_id = _sha256_json(payload)
    row = {
        "schema_version": LOCAL_KNOWLEDGE_SCHEMA_VERSION,
        "id": record_id,
        "extracted_by": LOCAL_KNOWLEDGE_EXTRACTED_BY,
        "extractor": {
            "name": LOCAL_KNOWLEDGE_EXTRACTOR_NAME,
            "version": LOCAL_KNOWLEDGE_EXTRACTOR_VERSION,
        },
        **payload,
    }
    return row


def _load_pyproject(repo: Path) -> Mapping[str, object]:
    path = repo / "pyproject.toml"
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_pytest_ini(repo: Path) -> Mapping[str, str]:
    for name in ("pytest.ini", "tox.ini", "setup.cfg"):
        path = repo / name
        if not path.exists():
            continue
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        section = "tool:pytest" if name == "setup.cfg" else "pytest"
        if parser.has_section(section):
            return dict(parser.items(section))
    return {}


def _python_files(repo: Path) -> tuple[str, ...]:
    files = []
    for path in repo.rglob("*.py"):
        if any(part.startswith(".") or part in {"__pycache__", ".tox", "build", "dist"} for part in path.parts):
            continue
        files.append(_relative_path(repo, path))
    return tuple(sorted(files))


def _package_roots(repo: Path, python_files: Sequence[str]) -> list[dict[str, str]]:
    roots = []
    for path in python_files:
        if not path.endswith("__init__.py"):
            continue
        package_path = path.removesuffix("/__init__.py")
        module_path = package_path.removeprefix("src/")
        roots.append(
            {
                "package": module_path.replace("/", "."),
                "path": package_path,
                "source_root": "src" if package_path.startswith("src/") else ".",
            }
        )
    return sorted(roots, key=lambda item: item["package"])


def _single_modules(python_files: Sequence[str]) -> list[dict[str, str]]:
    modules = []
    for path in python_files:
        parts = PurePosixPath(path).parts
        if len(parts) != 1 or path in {"setup.py", "conftest.py"}:
            continue
        name = Path(path).stem
        if not name.startswith("test_") and name != "__init__":
            modules.append({"module": name, "path": path})
    return sorted(modules, key=lambda item: item["module"])


def _is_public_single_module(path: str, python_files: Sequence[str]) -> bool:
    parts = PurePosixPath(path).parts
    if len(parts) != 1 or path in {"setup.py", "conftest.py"}:
        return False
    if Path(path).stem.startswith("test_"):
        return False
    return not any(file.endswith("__init__.py") for file in python_files)


def _module_name_from_path(path: str) -> str:
    if path.endswith("/__init__.py"):
        return path.removesuffix("/__init__.py").removeprefix("src/").replace("/", ".")
    if path.endswith(".py"):
        return path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    return ""


def _public_exports(tree: ast.Module) -> dict[str, object]:
    explicit_all: list[str] = []
    exported_names: set[str] = set()
    re_export_paths: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "__all__" in targets:
                explicit_all = _string_literal_sequence(node.value)
                exported_names.update(explicit_all)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exported_names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                if not name.startswith("_"):
                    exported_names.add(name)
                    re_export_paths.append({"name": name, "from": module})
    return {
        "explicit_all": explicit_all,
        "exported_names": sorted(exported_names),
        "re_export_paths": sorted(re_export_paths, key=lambda item: item["name"]),
    }


def _test_import_examples(
    repo: Path,
    test_files: Sequence[str],
    module: str,
) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    for path in test_files:
        tree = _parse_python(repo / path)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == module or alias.name.startswith(f"{module}."):
                        examples.append({"path": path, "import": alias.name, "kind": "import"})
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == module or node.module.startswith(f"{module}."):
                    examples.append(
                        {
                            "path": path,
                            "import": node.module,
                            "names": [alias.asname or alias.name for alias in node.names],
                            "kind": "from_import",
                        }
                    )
    return examples[:10]


def _pytest_config_list(
    pyproject: Mapping[str, object],
    pytest_ini: Mapping[str, str],
    key: str,
) -> list[str]:
    ini_options = _nested_mapping(pyproject, ("tool", "pytest", "ini_options"))
    value = ini_options.get(key)
    if isinstance(value, str):
        return value.split()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    ini_value = pytest_ini.get(key)
    if ini_value:
        return ini_value.split()
    return []


def _discovered_test_roots(test_files: Sequence[str]) -> list[str]:
    roots = set()
    for path in test_files:
        parts = PurePosixPath(path).parts
        if parts and parts[0] in {"tests", "testing"}:
            roots.add(parts[0])
        elif len(parts) > 1:
            roots.add(PurePosixPath(*parts[:-1]).as_posix())
        else:
            roots.add(".")
    return sorted(roots)


def _import_mode_hints(repo: Path, test_files: Sequence[str]) -> list[dict[str, object]]:
    hints = []
    for path in test_files[:10]:
        tree = _parse_python(repo / path)
        hints.append({"path": path, "imports": list(_imports(tree))})
    return hints


def _test_file_examples(repo: Path, test_files: Sequence[str]) -> list[dict[str, object]]:
    examples = []
    for path in test_files[:10]:
        tree = _parse_python(repo / path)
        functions = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        examples.append({"path": path, "test_functions": functions[:10]})
    return examples


def _imports(tree: ast.Module) -> tuple[dict[str, str], ...]:
    imports: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"kind": "import", "module": alias.name})
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(
                {
                    "kind": "from_import",
                    "module": node.module,
                    "names": ",".join(alias.asname or alias.name for alias in node.names),
                }
            )
    return tuple(imports)


def _pytest_tools(node: ast.AST) -> set[str]:
    tools = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name.startswith("pytest.") or name.startswith("monkeypatch."):
                tools.add(name)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            if child.value.id == "monkeypatch":
                tools.add(f"monkeypatch.{child.attr}")
    return tools


def _parametrize_shape(decorators: Sequence[ast.expr]) -> dict[str, object] | None:
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if not _call_name(decorator.func).endswith("parametrize"):
            continue
        arg_names: list[str] = []
        case_count = None
        if decorator.args:
            first = decorator.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                arg_names = [part.strip() for part in first.value.split(",") if part.strip()]
        if len(decorator.args) >= 2 and isinstance(decorator.args[1], (ast.List, ast.Tuple)):
            case_count = len(decorator.args[1].elts)
        return {
            "arg_names": arg_names,
            "case_count": case_count,
            "keyword_names": [keyword.arg for keyword in decorator.keywords if keyword.arg],
        }
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _string_literal_sequence(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return []
    values = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            values.append(item.value)
    return values


def _validation_provenance_paths(repo: Path) -> list[str]:
    paths = [
        path
        for path in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
        if (repo / path).exists()
    ]
    return paths or ["."]


def _provenance_hash(repo: Path, relative_paths: Sequence[str]) -> str:
    payload = []
    for relative_path in sorted(dict.fromkeys(relative_paths)):
        if relative_path.startswith("task:"):
            payload.append({"path": relative_path, "sha256": _sha256_text(relative_path)})
            continue
        path = _repo_path(repo, relative_path)
        if path.is_file():
            payload.append({"path": relative_path, "sha256": _sha256_bytes(path.read_bytes())})
        elif path.is_dir():
            payload.append({"path": relative_path, "sha256": _tree_hash(path)})
        else:
            payload.append({"path": relative_path, "sha256": _sha256_text(relative_path)})
    return _sha256_json(payload)


def _tree_hash(path: Path) -> str:
    payload = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        payload.append(
            {
                "path": child.relative_to(path).as_posix(),
                "sha256": _sha256_bytes(child.read_bytes()),
            }
        )
    return _sha256_json(payload)


def _is_test_file(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        "tests" in pure.parts
        or "testing" in pure.parts
        or pure.name.startswith("test_")
        or pure.name.endswith("_test.py")
    )


def _nested_mapping(value: Mapping[str, object], path: Sequence[str]) -> Mapping[str, object]:
    current: object = value
    for part in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(part, {})
    return current if isinstance(current, Mapping) else {}


def _nested_str(value: Mapping[str, object], path: Sequence[str]) -> str | None:
    current: object = value
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current if isinstance(current, str) else None


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_sequence(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("expected a sequence of strings")
    result = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError("expected non-empty string entries")
        result.append(item)
    return result


def _tests_only_task_ids(tasks: Sequence[Mapping[str, object]]) -> list[str]:
    return [
        _required_str(task, "id")
        for task in tasks
        if task.get("task_type") == "tests_only"
    ]


def _repo_path(repo: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"path must be repository-relative: {relative_path}")
    if relative_path in {"", "."}:
        return repo
    return repo / Path(*pure.parts)


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _parse_python(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _json_copy(value: Any) -> object:
    return json.loads(json.dumps(value, sort_keys=True))


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate_split(split: str) -> None:
    if split not in SPLITS:
        raise ValueError(f"unsupported split: {split}")


def _contains_raw_blob_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in RAW_BLOB_KEYS:
                return True
            if _contains_raw_blob_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_raw_blob_key(item) for item in value)
    return False
