"""Compact target context for candidate ranking records."""

from __future__ import annotations

import ast
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from repo import PythonSource, iter_python_sources

from .types import CandidatePatch


MAX_UPSTREAM_DISTANCE = 3


@dataclass(frozen=True, slots=True)
class _RepoContext:
    function_qnames: dict[tuple[str, str], str]
    calls: dict[str, frozenset[str]]
    callers: dict[str, frozenset[str]]


def attach_target_context(repo: Path, candidates: list[CandidatePatch]) -> list[CandidatePatch]:
    """Attach compact repo-local target context to generated candidates."""

    if not candidates:
        return candidates
    context = _build_repo_context(repo)
    return [
        replace(candidate, target_context=_candidate_target_context(candidate, context))
        for candidate in candidates
    ]


def _build_repo_context(repo: Path) -> _RepoContext:
    parsed_sources: list[tuple[PythonSource, ast.Module]] = []
    for source in iter_python_sources(repo):
        path = PurePosixPath(source.relative_path)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(source.text)
        except SyntaxError:
            continue
        parsed_sources.append((source, tree))

    module_paths: dict[str, str] = {}
    module_functions: dict[str, set[str]] = {}
    function_qnames: dict[tuple[str, str], str] = {}
    for source, tree in parsed_sources:
        module = _module_name_from_path(PurePosixPath(source.relative_path))
        if not module:
            continue
        module_paths[module] = source.relative_path
        function_names = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }
        module_functions[module] = function_names
        for name in function_names:
            function_qnames[(source.relative_path, name)] = f"{module}.{name}"

    calls: dict[str, frozenset[str]] = {}
    caller_sets: defaultdict[str, set[str]] = defaultdict(set)
    for source, tree in parsed_sources:
        module = _module_name_from_path(PurePosixPath(source.relative_path))
        if not module:
            continue
        local_functions = module_functions.get(module, set())
        imports = _imported_function_qnames(
            tree,
            current_module=module,
            module_paths=module_paths,
            module_functions=module_functions,
        )
        for function in [node for node in tree.body if isinstance(node, ast.FunctionDef)]:
            qname = f"{module}.{function.name}"
            callees = _called_function_qnames(
                function,
                current_module=module,
                imports=imports,
                local_functions=local_functions,
            )
            calls[qname] = frozenset(callees)
            for callee in callees:
                caller_sets[callee].add(qname)

    callers = {
        qname: frozenset(caller_sets.get(qname, set()))
        for qname in set(calls) | set(caller_sets)
    }
    return _RepoContext(
        function_qnames=function_qnames,
        calls=calls,
        callers=callers,
    )


def _candidate_target_context(
    candidate: CandidatePatch,
    context: _RepoContext,
) -> dict[str, object]:
    symbol = candidate.action.target.symbol
    qname = context.function_qnames.get((candidate.file_path, symbol or ""))
    target: dict[str, object] = {
        "role": _target_role(candidate.file_path),
    }
    if qname is None:
        return target

    target["qualified_symbol"] = qname
    target["callee_count"] = len(context.calls.get(qname, frozenset()))
    target["caller_count"] = len(context.callers.get(qname, frozenset()))
    upstream = _upstream_callers(qname, context.callers, max_distance=MAX_UPSTREAM_DISTANCE)
    if upstream:
        target["upstream_callers"] = [
            {
                "symbol": caller.rsplit(".", maxsplit=1)[-1],
                "distance": distance,
            }
            for caller, distance in upstream
        ]
    return target


def _target_role(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if "tests" in path.parts or path.name.startswith("test_"):
        return "test"
    if path.stem in {"api", "__init__"}:
        return "public_api"
    return "helper"


def _upstream_callers(
    qname: str,
    callers: dict[str, frozenset[str]],
    *,
    max_distance: int,
) -> list[tuple[str, int]]:
    distances: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((caller, 1) for caller in sorted(callers.get(qname, ())))
    while queue:
        caller, distance = queue.popleft()
        if caller in distances or distance > max_distance:
            continue
        distances[caller] = distance
        for next_caller in sorted(callers.get(caller, ())):
            queue.append((next_caller, distance + 1))
    return sorted(distances.items(), key=lambda item: (item[1], item[0]))


def _called_function_qnames(
    function: ast.FunctionDef,
    *,
    current_module: str,
    imports: dict[str, str],
    local_functions: set[str],
) -> set[str]:
    callees: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in imports:
                callees.add(imports[name])
            elif name in local_functions:
                callees.add(f"{current_module}.{name}")
    return callees


def _imported_function_qnames(
    tree: ast.Module,
    *,
    current_module: str,
    module_paths: dict[str, str],
    module_functions: dict[str, set[str]],
) -> dict[str, str]:
    imports: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolve_import_from_module(current_module, node)
        if module is None or module not in module_functions or module not in module_paths:
            continue
        for alias in node.names:
            if alias.name not in module_functions[module]:
                continue
            imports[alias.asname or alias.name] = f"{module}.{alias.name}"
    return imports


def _resolve_import_from_module(current_module: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    if not current_module:
        return node.module

    parts = current_module.split(".")
    if node.level > len(parts):
        return node.module
    base = parts[: len(parts) - node.level]
    if node.module:
        base.append(node.module)
    if not base:
        return None
    return ".".join(base)


def _module_name_from_path(path: PurePosixPath) -> str:
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)
