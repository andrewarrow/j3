"""Parse pytest output into structured repair hints."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


FAILED_TARGET_RE = re.compile(r"^FAILED\s+([^\s]+::[^\s]+)(?:\s+-\s+(.*))?")
TRACEBACK_LOCATION_RE = re.compile(r"^([^\s:][^:]*\.py):(\d+):(?:\s+([A-Za-z_][\w.]*))?")
ASSERT_EQ_RE = re.compile(r"^E\s+assert\s+(.+?)\s*(==|is)\s*(.+)$")
WHERE_CALL_RE = re.compile(r"where\s+(.+?)\s+=\s+([A-Za-z_]\w*)\(")
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\(")
EXCEPTION_RE = re.compile(r"\b([A-Za-z_][\w.]*?(?:Error|Exception|Warning))\b")
NAME_ERROR_RE = re.compile(r"NameError:\s+name '([^']+)' is not defined")
ATTRIBUTE_ERROR_RE = re.compile(r"AttributeError:\s+.+ has no attribute '([^']+)'")
MODULE_NOT_FOUND_RE = re.compile(r"ModuleNotFoundError:\s+No module named '([^']+)'")
IMPORT_ERROR_RE = re.compile(r"ImportError:\s+cannot import name '([^']+)'")
TYPE_ERROR_NAME_RE = re.compile(r"TypeError:\s+.*(?:argument|parameter|keyword).*'([^']+)'")

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
    type_error_names: set[str] = field(default_factory=set)

    @property
    def source_files(self) -> set[str]:
        return {
            location.file_path
            for location in self.traceback_locations
            if not PurePosixPath(location.file_path).name.startswith("test_")
        }


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
    location = TRACEBACK_LOCATION_RE.match(stripped)
    if location:
        exception_type = location.group(3)
        if exception_type and hint.exception_type is None:
            hint.exception_type = exception_type
        hint.traceback_locations.append(
            TracebackLocation(
                file_path=_normalize_path(location.group(1)),
                line=int(location.group(2)),
                exception_type=exception_type,
            )
        )
        return

    assertion = ASSERT_EQ_RE.match(stripped)
    if assertion:
        hint.assertions.append(
            AssertionComparison(
                actual=_literal_value(assertion.group(1)),
                operator=assertion.group(2),
                expected=_literal_value(assertion.group(3)),
            )
        )

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

    _collect_function_names(hint, stripped)


def _collect_function_names(hint: PytestFailureHint, text: str) -> None:
    for name in CALL_RE.findall(text):
        if name not in IGNORED_CALL_NAMES and not name.startswith("test_"):
            hint.function_names.add(name)


def _collect_error_details(hint: PytestFailureHint, text: str) -> None:
    name_error = NAME_ERROR_RE.search(text)
    if name_error:
        hint.missing_names.add(name_error.group(1))

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
        or hint.type_error_names
    )
