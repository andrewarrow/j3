"""AST and source helpers for patch generation."""

from __future__ import annotations

import ast
import difflib
import io
import tokenize

from synth import SourceEdit


def _node_edit(node: ast.AST, replacement: str) -> SourceEdit:
    return SourceEdit(
        start_line=node.lineno,
        start_col=node.col_offset,
        end_line=node.end_lineno,
        end_col=node.end_col_offset,
        replacement=replacement,
    )


def _full_source_edit(source: str) -> SourceEdit:
    lines = source.splitlines(keepends=True)
    if not lines:
        return SourceEdit(start_line=1, start_col=0, end_line=1, end_col=0, replacement="")
    return SourceEdit(
        start_line=1,
        start_col=0,
        end_line=len(lines),
        end_col=len(lines[-1]),
        replacement=source,
    )


def _render_call_with_keyword_rename(
    source: str,
    node: ast.Call,
    old_name: str,
    new_name: str,
) -> str | None:
    func = ast.get_source_segment(source, node.func)
    if not func:
        return None

    parts: list[str] = []
    for arg in node.args:
        value = ast.get_source_segment(source, arg)
        if value is None:
            return None
        parts.append(value)
    changed = False
    for keyword in node.keywords:
        value = ast.get_source_segment(source, keyword.value)
        if value is None:
            return None
        if keyword.arg is None:
            parts.append(f"**{value}")
            continue
        name = new_name if keyword.arg == old_name else keyword.arg
        changed = changed or keyword.arg == old_name
        parts.append(f"{name}={value}")
    if not changed:
        return None
    return f"{func}({', '.join(parts)})"


def _rename_identifier_in_text(source: str, old_name: str, new_name: str) -> str:
    renamed = _rename_identifier_with_tokens(source, old_name, new_name)
    if not _contains_identifier(renamed, old_name):
        return renamed
    parsed = _rename_identifier_with_ast(source, old_name, new_name)
    return parsed if parsed is not None else renamed


def _rename_identifier_with_tokens(source: str, old_name: str, new_name: str) -> str:
    tokens = []
    reader = io.StringIO(source).readline
    for token in tokenize.generate_tokens(reader):
        if token.type == tokenize.NAME and token.string == old_name:
            token = tokenize.TokenInfo(token.type, new_name, token.start, token.end, token.line)
        tokens.append(token)
    return tokenize.untokenize(tokens)


def _contains_identifier(source: str, name: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.arg) and node.arg == name:
            return True
    return False


def _rename_identifier_with_ast(source: str, old_name: str, new_name: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    class Renamer(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == old_name:
                return ast.copy_location(ast.Name(id=new_name, ctx=node.ctx), node)
            return node

        def visit_arg(self, node: ast.arg) -> ast.arg:
            if node.arg == old_name:
                return ast.copy_location(
                    ast.arg(arg=new_name, annotation=node.annotation, type_comment=node.type_comment),
                    node,
                )
            return node

    renamed = Renamer().visit(tree)
    ast.fix_missing_locations(renamed)
    return ast.unparse(renamed)


def _apply_node_replacements(source: str, replacements: list[tuple[ast.AST, str]]) -> str:
    lines = source.splitlines(keepends=True)
    spans = [
        (
            _offset(lines, node.lineno, node.col_offset),
            _offset(lines, node.end_lineno, node.end_col_offset),
            replacement,
        )
        for node, replacement in replacements
    ]
    patched = source
    for start, end, replacement in sorted(spans, reverse=True):
        patched = patched[:start] + replacement + patched[end:]
    return patched


def _is_valid_python(source: str) -> bool:
    try:
        ast.parse(source)
    except SyntaxError:
        return False
    return True


def _operator_text(op: ast.cmpop) -> str | None:
    table = {
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Is: "is",
        ast.IsNot: "is not",
        ast.In: "in",
        ast.NotIn: "not in",
    }
    return table.get(type(op))


def _operator_alternatives(operator: str | None) -> list[str]:
    table = {
        "==": ["!=", "<=", ">="],
        "!=": ["=="],
        "<": ["<=", ">", ">="],
        "<=": ["<", ">", ">="],
        ">": [">=", "<", "<="],
        ">=": [">", "<", "<="],
        "is": ["is not"],
        "is not": ["is"],
        "in": ["not in"],
        "not in": ["in"],
    }
    if operator is None:
        return []
    return table.get(operator, [])


def _nearby_literals(value: int | float) -> list[int | float]:
    if isinstance(value, int):
        return [value - 2, value - 1, value + 1, value + 2]
    return [round(value - 0.1, 10), round(value + 0.1, 10)]


def _string_literals(tree: ast.AST) -> set[str]:
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _looks_like_key_literal(node.value):
            values.add(node.value)
    return values


def _looks_like_key_literal(value: str) -> bool:
    return 0 < len(value) <= 80 and any(character.isalnum() for character in value)


def _subscript_key_alternatives(original: str, repo_string_literals: set[str]) -> list[str]:
    alternatives = [
        value
        for value in repo_string_literals
        if value != original and _keys_look_related(original, value)
    ]
    return sorted(alternatives, key=lambda value: (-_key_similarity(original, value), value))[:5]


def _string_literal_alternatives(original: str, repo_string_literals: set[str]) -> list[str]:
    if not _looks_like_key_literal(original):
        return []
    alternatives = [
        value
        for value in repo_string_literals
        if value != original and _keys_look_related(original, value)
    ]
    return sorted(alternatives, key=lambda value: (-_key_similarity(original, value), value))[:5]


def _keys_look_related(original: str, candidate: str) -> bool:
    normalized_original = original.casefold()
    normalized_candidate = candidate.casefold()
    if normalized_original in normalized_candidate or normalized_candidate in normalized_original:
        return True
    return _key_similarity(original, candidate) >= 0.62


def _key_similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio()


def _call_exception(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name) and node.func.id in {"int", "float"}:
        return "ValueError"
    return None


def _function_arg_types(function: ast.FunctionDef) -> dict[str, str]:
    arg_types: dict[str, str] = {}
    for arg in function.args.args:
        if isinstance(arg.annotation, ast.Name):
            arg_types[arg.arg] = arg.annotation.id
    return arg_types


def _class_fields(tree: ast.Module) -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        class_fields: set[str] = set()
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                class_fields.add(statement.target.id)
            elif isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        class_fields.add(target.id)
        fields[node.name] = class_fields
    return fields


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _module_symbols(tree: ast.Module) -> set[str]:
    return _imported_names(tree) | _defined_names(tree)


def _local_symbols(function: ast.FunctionDef) -> set[str]:
    names = {arg.arg for arg in function.args.args}
    names.update(arg.arg for arg in function.args.kwonlyargs)
    if function.args.vararg is not None:
        names.add(function.args.vararg.arg)
    if function.args.kwarg is not None:
        names.add(function.args.kwarg.arg)
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.For):
            names.update(_target_names(node.target))
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars is not None:
                    names.update(_target_names(item.optional_vars))
    return names


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in node.elts:
            names.update(_target_names(element))
        return names
    return set()


def _import_insert_line(tree: ast.Module) -> int:
    insert_line = 1
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            insert_line = (node.end_lineno or node.lineno) + 1
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_line = (node.end_lineno or node.lineno) + 1
            continue
        break
    return insert_line


def _import_module(import_line: str) -> str:
    if import_line.startswith("from "):
        return import_line.split()[1]
    if import_line.startswith("import "):
        return import_line.split()[1].split(".", maxsplit=1)[0]
    return ""


def _function_uses_len_of(function: ast.FunctionDef, arg_name: str) -> bool:
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "len"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == arg_name
        ):
            return True
    return False


def _offset(lines: list[str], line: int, col: int) -> int:
    return sum(len(value) for value in lines[: line - 1]) + col
