"""Top-level candidate generation orchestration."""

from __future__ import annotations

import ast
from pathlib import Path

from repo import iter_python_sources

from ..ast_utils import (
    _class_fields,
    _function_arg_types,
    _local_symbols,
    _module_symbols,
    _string_literals,
)
from ..types import CandidatePatch
from .calls import (
    _add_keyword_arg_candidates,
    _call_signature_index,
    _swap_call_arg_candidates,
)
from .control_flow import (
    _fallback_warning_candidates,
    _guard_candidates,
    _modify_condition_candidates,
    _return_candidates,
    _state_flag_guard_candidates,
    _wrap_try_except_candidates,
)
from .data_access import (
    _add_dict_key_candidates,
    _attribute_candidates,
    _change_dict_key_candidates,
    _change_dict_value_candidates,
    _module_change_dict_value_candidates,
    _subscript_key_candidates,
)
from .imports import _add_import_candidates, _local_import_index
from .literals import (
    _compare_candidates,
    _fstring_fragment_candidates,
    _literal_candidates,
    _module_constant_candidates,
)
from .signatures import _external_signature_keyword_index, _signature_propagation_candidates
from .symbols import _rename_symbol_candidates


def generate_candidate_patches(repo: Path) -> list[CandidatePatch]:
    """Generate structured candidate edits for source files in a repo."""

    parsed_sources = []
    repo_string_literals: set[str] = set()
    for source in iter_python_sources(repo):
        try:
            tree = ast.parse(source.text)
        except SyntaxError:
            continue
        parsed_sources.append((source, tree))
        repo_string_literals.update(_string_literals(tree))

    local_imports = _local_import_index(parsed_sources)
    external_signature_keywords = _external_signature_keyword_index(parsed_sources)
    call_signatures = _call_signature_index(parsed_sources)
    candidates: list[CandidatePatch] = []
    for source, tree in parsed_sources:
        path = Path(source.relative_path)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue

        class_fields = _class_fields(tree)
        module_symbols = _module_symbols(tree)
        candidates.extend(
            _add_import_candidates(source.relative_path, source.text, tree, local_imports)
        )
        candidates.extend(
            _signature_propagation_candidates(
                source.relative_path,
                source.text,
                tree,
                external_keywords=external_signature_keywords.get(source.relative_path, {}),
            )
        )
        candidates.extend(
            _module_constant_candidates(
                source.relative_path,
                source.text,
                tree,
                repo_string_literals,
            )
        )
        candidates.extend(
            _module_change_dict_value_candidates(
                source.relative_path,
                source.text,
                tree,
                repo_string_literals,
            )
        )
        for function in [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]:
            arg_names = {arg.arg for arg in function.args.args}
            arg_types = _function_arg_types(function)
            local_symbols = module_symbols | _local_symbols(function)
            candidates.extend(_guard_candidates(source.relative_path, source.text, function, arg_names))
            candidates.extend(_state_flag_guard_candidates(source.relative_path, source.text, tree, function))
            for node in ast.walk(function):
                if isinstance(node, ast.Return) and node.value is not None:
                    candidates.extend(
                        _return_candidates(source.relative_path, source.text, function, node, arg_names)
                    )
                    candidates.extend(_wrap_try_except_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Compare):
                    candidates.extend(_compare_candidates(source.relative_path, source.text, function, node))
                elif isinstance(node, ast.Subscript):
                    candidates.extend(
                        _subscript_key_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                elif isinstance(node, ast.Dict):
                    candidates.extend(
                        _change_dict_key_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                    candidates.extend(
                        _add_dict_key_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                    candidates.extend(
                        _change_dict_value_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                elif isinstance(node, ast.Constant):
                    candidates.extend(
                        _literal_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                elif isinstance(node, ast.JoinedStr):
                    candidates.extend(
                        _fstring_fragment_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            repo_string_literals,
                        )
                    )
                elif isinstance(node, ast.If):
                    candidates.extend(_modify_condition_candidates(source.relative_path, source.text, function, node))
                    candidates.extend(
                        _fallback_warning_candidates(
                            source.relative_path,
                            source.text,
                            tree,
                            function,
                            node,
                        )
                    )
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    candidates.extend(
                        _rename_symbol_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            local_symbols,
                        )
                    )
                elif isinstance(node, ast.Call):
                    candidates.extend(_swap_call_arg_candidates(source.relative_path, source.text, function, node))
                    candidates.extend(
                        _add_keyword_arg_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            call_signatures.get(source.relative_path, {}),
                        )
                    )
                elif isinstance(node, ast.Attribute):
                    candidates.extend(
                        _attribute_candidates(
                            source.relative_path,
                            source.text,
                            function,
                            node,
                            arg_types,
                            class_fields,
                        )
                    )
    return candidates
