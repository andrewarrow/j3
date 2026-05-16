"""Parse pytest output into structured repair hints."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


FAILED_TARGET_RE = re.compile(r"^FAILED\s+([^\s]+::[^\s]+)(?:\s+-\s+(.*))?")
TRACEBACK_LOCATION_RE = re.compile(r"^(?P<file>[^\s:][^:]*\.py):(?P<line>\d+):(?:\s+(?P<context>.*))?$")
TRACEBACK_CONTEXT_RE = re.compile(r"^in\s+([A-Za-z_]\w*)$")
ASSERT_OP_RE = re.compile(r"^E\s+assert\s+(.+?)\s+(==|is|in|not in)\s+(.+)$")
WHERE_CALL_RE = re.compile(r"where\s+(.+?)\s+=\s+([A-Za-z_]\w*)\(")
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\(")
EXCEPTION_RE = re.compile(r"\b([A-Za-z_][\w.]*?(?:Error|Exception|Warning))\b")
NAME_ERROR_RE = re.compile(r"NameError:\s+name '([^']+)' is not defined")
KEY_ERROR_RE = re.compile(r"KeyError:\s+(['\"])(.*?)\1")
ATTRIBUTE_ERROR_RE = re.compile(r"AttributeError:\s+.+ has no attribute '([^']+)'")
MODULE_NOT_FOUND_RE = re.compile(r"ModuleNotFoundError:\s+No module named '([^']+)'")
IMPORT_ERROR_RE = re.compile(r"ImportError:\s+cannot import name '([^']+)'")
TYPE_ERROR_NAME_RE = re.compile(r"TypeError:\s+.*(?:argument|parameter|keyword).*'([^']+)'")
PYTEST_MATCH_RE = re.compile(r"\bmatch=(['\"])(.*?)\1")
MYPY_RE = re.compile(r"^([^:\s][^:]*\.py):(\d+):\s+(error|note|warning):\s+(.+?)(?:\s+\[([-\w]+)\])?$")
RUFF_RE = re.compile(r"^([^:\s][^:]*\.py):(\d+):(\d+):\s+([A-Z]+\d+)\s+(.+)$")
RUFF_UNDEFINED_NAME_RE = re.compile(r"Undefined name [`'\"]?([A-Za-z_]\w*)[`'\"]?")

IGNORED_CALL_NAMES = {
    "assert",
    "len",
    "list",
    "dict",
    "set",
    "sum",
    "min",
    "max",
    "range",
    "print",
}


@dataclass(frozen=True, slots=True)
class TracebackLocation:
    file_path: str
    line: int
    exception_type: str | None = None


@dataclass(frozen=True, slots=True)
class AssertionComparison:
    actual: Any
    operator: str
    expected: Any

    @property
    def numeric_delta(self) -> int | float | None:
        if isinstance(self.actual, bool) or isinstance(self.expected, bool):
            return None
        if isinstance(self.actual, (int, float)) and isinstance(self.expected, (int, float)):
            return self.expected - self.actual
        return None


@dataclass(frozen=True, slots=True)
class ToolDiagnostic:
    tool: str
    file_path: str
    line: int
    message: str
    severity: str | None = None
    code: str | None = None
    column: int | None = None


@dataclass(slots=True)
class PytestFailureHint:
    nodeid: str | None = None
    summary: str | None = None
    exception_type: str | None = None
    assertions: list[AssertionComparison] = field(default_factory=list)
    traceback_locations: list[TracebackLocation] = field(default_factory=list)
    function_names: set[str] = field(default_factory=set)
    missing_names: set[str] = field(default_factory=set)
    missing_attributes: set[str] = field(default_factory=set)
    missing_modules: set[str] = field(default_factory=set)
    missing_keys: set[str] = field(default_factory=set)
    type_error_names: set[str] = field(default_factory=set)
    expected_strings: set[str] = field(default_factory=set)
    assertion_diff_lines: list[str] = field(default_factory=list)
    tool_diagnostics: list[ToolDiagnostic] = field(default_factory=list)

    @property
    def source_files(self) -> set[str]:
        traceback_files = {
            location.file_path
            for location in self.traceback_locations
            if not PurePosixPath(location.file_path).name.startswith("test_")
        }
        diagnostic_files = {
            diagnostic.file_path
            for diagnostic in self.tool_diagnostics
            if not PurePosixPath(diagnostic.file_path).name.startswith("test_")
        }
        return traceback_files | diagnostic_files


def parse_pytest_failure_hints(output: str) -> list[PytestFailureHint]:
    """Extract compact repair hints from pytest failure output."""

    hints: list[PytestFailureHint] = []
    current: PytestFailureHint | None = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        failed = FAILED_TARGET_RE.match(stripped)
        if failed:
            if current is None or current.nodeid is not None:
                current = PytestFailureHint()
                hints.append(current)
            current.nodeid = failed.group(1)
            current.summary = failed.group(2)
            _merge_summary(current, failed.group(2))
            continue

        if current is None:
            if " FAILURES " in line:
                current = PytestFailureHint()
                hints.append(current)
            elif MYPY_RE.match(stripped) or RUFF_RE.match(stripped):
                current = PytestFailureHint()
                hints.append(current)
            elif stripped.startswith((">", "E ")) or DEF_RE.match(line):
                current = PytestFailureHint()
                hints.append(current)
            else:
                continue

        _merge_line(current, line)

    return [hint for hint in hints if _has_signal(hint)]


def _merge_summary(hint: PytestFailureHint, summary: str | None) -> None:
    if not summary:
        return
    exception = EXCEPTION_RE.search(summary)
    if exception and hint.exception_type is None:
        hint.exception_type = exception.group(1)
    _collect_error_details(hint, summary)
    _collect_function_names(hint, summary)


def _merge_line(hint: PytestFailureHint, line: str) -> None:
    stripped = line.strip()
    if MYPY_RE.match(stripped) or RUFF_RE.match(stripped):
        _collect_tool_diagnostics(hint, stripped)
        return

    location = TRACEBACK_LOCATION_RE.match(stripped)
    if location:
        context = location.group("context")
        frame_context = TRACEBACK_CONTEXT_RE.match(context or "")
        if frame_context and not frame_context.group(1).startswith("test_"):
            hint.function_names.add(frame_context.group(1))
        exception = EXCEPTION_RE.fullmatch(context or "")
        exception_type = exception.group(1) if exception else None
        if exception_type and hint.exception_type is None:
            hint.exception_type = exception_type
        hint.traceback_locations.append(
            TracebackLocation(
                file_path=_normalize_path(location.group("file")),
                line=int(location.group("line")),
                exception_type=exception_type,
            )
        )
        return

    assertion = ASSERT_OP_RE.match(stripped)
    if assertion:
        hint.assertions.append(
            AssertionComparison(
                actual=_literal_value(assertion.group(1)),
                operator=assertion.group(2),
                expected=_literal_value(assertion.group(3)),
            )
        )

    if stripped.startswith("E ") and _looks_like_assertion_diff(stripped):
        hint.assertion_diff_lines.append(stripped[2:].strip())

    where = WHERE_CALL_RE.search(stripped)
    if where:
        hint.function_names.add(where.group(2))

    definition = DEF_RE.match(line)
    if definition and not definition.group(1).startswith("test_"):
        hint.function_names.add(definition.group(1))

    exception = EXCEPTION_RE.search(stripped)
    if exception and hint.exception_type is None:
        hint.exception_type = exception.group(1)
    _collect_error_details(hint, stripped)
    _collect_tool_diagnostics(hint, stripped)

    _collect_function_names(hint, stripped)


def _collect_function_names(hint: PytestFailureHint, text: str) -> None:
    for name in CALL_RE.findall(text):
        if name not in IGNORED_CALL_NAMES and not name.startswith("test_"):
            hint.function_names.add(name)


def _collect_error_details(hint: PytestFailureHint, text: str) -> None:
    name_error = NAME_ERROR_RE.search(text)
    if name_error:
        hint.missing_names.add(name_error.group(1))

    key_error = KEY_ERROR_RE.search(text)
    if key_error:
        hint.missing_keys.add(key_error.group(2))

    attribute_error = ATTRIBUTE_ERROR_RE.search(text)
    if attribute_error:
        hint.missing_attributes.add(attribute_error.group(1))

    module_not_found = MODULE_NOT_FOUND_RE.search(text)
    if module_not_found:
        hint.missing_modules.add(module_not_found.group(1))

    import_error = IMPORT_ERROR_RE.search(text)
    if import_error:
        hint.missing_names.add(import_error.group(1))

    type_error = TYPE_ERROR_NAME_RE.search(text)
    if type_error:
        hint.type_error_names.add(type_error.group(1))

    for match in PYTEST_MATCH_RE.finditer(text):
        hint.expected_strings.add(match.group(2))


def _collect_tool_diagnostics(hint: PytestFailureHint, text: str) -> None:
    mypy = MYPY_RE.match(text)
    if mypy:
        hint.tool_diagnostics.append(
            ToolDiagnostic(
                tool="mypy",
                file_path=_normalize_path(mypy.group(1)),
                line=int(mypy.group(2)),
                severity=mypy.group(3),
                message=mypy.group(4),
                code=mypy.group(5),
            )
        )
        return

    ruff = RUFF_RE.match(text)
    if ruff:
        message = ruff.group(5)
        hint.tool_diagnostics.append(
            ToolDiagnostic(
                tool="ruff",
                file_path=_normalize_path(ruff.group(1)),
                line=int(ruff.group(2)),
                column=int(ruff.group(3)),
                code=ruff.group(4),
                message=message,
            )
        )
        undefined = RUFF_UNDEFINED_NAME_RE.search(message)
        if undefined:
            hint.missing_names.add(undefined.group(1))


def _literal_value(text: str) -> Any:
    value = text.strip()
    if value.endswith(","):
        value = value[:-1]
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        if value == "True":
            return True
        if value == "False":
            return False
        if value == "None":
            return None
        return value


def _normalize_path(path: str) -> str:
    return PurePosixPath(path).as_posix()


def _has_signal(hint: PytestFailureHint) -> bool:
    return bool(
        hint.nodeid
        or hint.exception_type
        or hint.assertions
        or hint.traceback_locations
        or hint.function_names
        or hint.missing_names
        or hint.missing_attributes
        or hint.missing_modules
        or hint.missing_keys
        or hint.type_error_names
        or hint.expected_strings
        or hint.assertion_diff_lines
        or hint.tool_diagnostics
    )


def _looks_like_assertion_diff(text: str) -> bool:
    return text.startswith(
        (
            "E       - ",
            "E       + ",
            "E         ",
            "E       Differing items:",
            "E       Right contains",
            "E       Left contains",
            "E       Full diff:",
        )
    )
