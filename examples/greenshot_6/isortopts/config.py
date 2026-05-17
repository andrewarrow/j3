from __future__ import annotations


OPTION_DESCRIPTIONS = {
    "force_single_line": "Forces all from imports to appear on their own line.",
    "indented_import_headings": "apply headings to indended imports",
    "line_length": "The max length of an import line before wrapping.",
}


def option_description(name: str) -> str:
    return OPTION_DESCRIPTIONS[name]
