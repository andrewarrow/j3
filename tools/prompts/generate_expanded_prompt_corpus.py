#!/usr/bin/env python3
"""Generate a deterministic expanded coding-agent prompt corpus.

The generated rows are synthetic template rows authored for j3 Prompt-JEPA
experiments. They are intentionally tagged by provenance and are not meant to
masquerade as human prompts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


TEMPLATE_VERSION = "prompt-corpus-template-v0"
GENERATION_DATE = "2026-05-17"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_WORKSPACE = REPO_ROOT.parent / "prompts"
DEFAULT_SEED = PROMPTS_WORKSPACE / "coding_agent_prompts_seed.jsonl"
DEFAULT_OUT = PROMPTS_WORKSPACE / "coding_agent_prompts_expanded_v0.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED,
        help="seed prompt JSONL path (default: ../prompts/coding_agent_prompts_seed.jsonl)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="expanded prompt JSONL path (default: ../prompts/coding_agent_prompts_expanded_v0.jsonl)",
    )
    args = parser.parse_args()

    seed_rows = _load_jsonl(args.seed)
    generated_rows = _generated_rows(
        start=1,
        existing_prompts={_normalize_prompt(str(row["prompt"])) for row in seed_rows},
    )
    rows = [*seed_rows, *generated_rows]
    _validate(rows)
    _write_jsonl(args.out, rows)
    print("generated prompt corpus")
    print(f"seed rows: {len(seed_rows)}")
    print(f"synthetic rows: {len(generated_rows)}")
    print(f"total rows: {len(rows)}")
    print(f"out: {args.out.resolve()}")
    return 0


def _generated_rows(*, start: int, existing_prompts: set[str]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    specs.extend(_create_cli_specs())
    specs.extend(_create_library_specs())
    specs.extend(_existing_feature_specs())
    specs.extend(_bugfix_specs())
    specs.extend(_tests_only_specs())
    specs.extend(_refactor_specs())
    specs.extend(_config_docs_specs())
    specs.extend(_clarification_specs())

    rows: list[dict[str, object]] = []
    next_id = start
    seen_prompts = set(existing_prompts)
    for spec in specs:
        family = str(spec["family"])
        split = _split_for_family(family)
        prompts = spec["prompts"]
        assert isinstance(prompts, list)
        for prompt in prompts:
            normalized_prompt = _normalize_prompt(str(prompt))
            if normalized_prompt in seen_prompts:
                continue
            seen_prompts.add(normalized_prompt)
            row_id = f"synth-{next_id:04d}"
            next_id += 1
            rows.append(
                {
                    "id": row_id,
                    "split": split,
                    "source_type": "synthetic_template_v0",
                    "task_type": spec["task_type"],
                    "repo_mode": spec["repo_mode"],
                    "domain": spec["domain"],
                    "prompt": prompt,
                    "expected": {
                        "action": spec["action"],
                        "features": spec.get("features", []),
                        "artifacts": spec.get("artifacts", []),
                        "interfaces": spec.get("interfaces", []),
                        "inferred": spec.get("inferred", []),
                        "clarify": spec.get("clarify", False),
                        "clarification_fields": spec.get("clarification_fields", []),
                        "unsupported_requirements": spec.get(
                            "unsupported_requirements", []
                        ),
                    },
                    "tags": [
                        *spec.get("tags", []),
                        "synthetic",
                        TEMPLATE_VERSION,
                    ],
                    "prompt_family": family,
                    "generation": {
                        "generated_by": "codex",
                        "generation_date": GENERATION_DATE,
                        "template_version": TEMPLATE_VERSION,
                        "review_status": "unreviewed_synthetic",
                    },
                }
            )
    return rows


def _create_cli_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "create_cli:calculator_basic",
            "create_app",
            "new_repo",
            "calculator",
            ["add", "subtract", "multiply", "divide"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "calculator", "implicit_defaults"],
            [
                "make me a simple cli calc",
                "make cli takes as params two numbers and operator",
                "create a python script where I can run calc 2 + 3",
                "make a tiny calculator cli with plus minus times and divide",
            ],
        ),
        _positive(
            "create_cli:bookmark_cli",
            "create_app",
            "new_repo",
            "bookmark_cli",
            ["add_bookmark", "list_bookmarks", "tag_bookmark", "search_bookmarks"],
            ["cli", "storage", "tests"],
            ["cli"],
            ["greenfield", "cli", "storage", "search"],
            [
                "build a bookmark cli that saves links, tags them, and lets me search",
                "make a local bookmarks command with add, list, tag, and search",
                "create a small cli for keeping urls with tags in a json file",
                "write a bookmarks tool for the terminal with search support",
            ],
        ),
        _positive(
            "create_cli:habit_tracker",
            "create_app",
            "new_repo",
            "habit_tracker",
            ["add_habit", "check_in", "streaks", "list_habits"],
            ["cli", "storage", "tests"],
            ["cli"],
            ["greenfield", "cli", "stateful"],
            [
                "make a habit tracker cli with add, check-in, list, and streaks",
                "create a terminal habit app that records daily checkins",
                "build a simple local habit tracker with streak counts",
                "write a cli where I can track habits and see current streaks",
            ],
        ),
        _positive(
            "create_cli:recipe_box",
            "create_app",
            "new_repo",
            "recipe_box",
            ["add_recipe", "list_recipes", "search_ingredients", "show_recipe"],
            ["cli", "storage", "tests"],
            ["cli"],
            ["greenfield", "cli", "search"],
            [
                "build a recipe box cli where I can add recipes and search ingredients",
                "make a tiny recipe command with add list show and search",
                "create an offline recipe manager using a local json file",
                "write a command line recipe notebook with ingredient search",
            ],
        ),
        _positive(
            "create_cli:markdown_toc",
            "create_app",
            "new_repo",
            "markdown",
            ["extract_headings", "generate_toc", "write_stdout"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "markdown"],
            [
                "make a markdown toc generator cli",
                "create a command that reads markdown headings and prints a table of contents",
                "build a small script to generate a toc from a markdown file",
                "write a cli that outputs links for h2 and h3 markdown headings",
            ],
        ),
        _positive(
            "create_cli:log_filter",
            "create_app",
            "new_repo",
            "logs",
            ["filter_level", "contains_text", "count_matches"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "logs"],
            [
                "create a log filter cli that can filter by level and text",
                "make a command line tool for finding error lines in logs",
                "build a small log grepper with level filters and match counts",
                "write a cli that reads a log file and prints matching entries",
            ],
        ),
        _positive(
            "create_cli:json_pretty",
            "create_app",
            "new_repo",
            "json_tool",
            ["pretty_print", "minify", "validate_json"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "json"],
            [
                "make a json cli that can pretty print, minify, and validate input",
                "create a command line json formatter with compact output option",
                "build a small json tool that reports invalid json clearly",
                "write a json pretty printer script with tests",
            ],
        ),
        _positive(
            "create_cli:word_count",
            "create_app",
            "new_repo",
            "text",
            ["count_words", "count_lines", "count_characters"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "text"],
            [
                "make a word count cli for words lines and characters",
                "create a wc-like python command with simple text stats",
                "build a small terminal tool that counts words and lines",
                "write a script that prints word line and character counts",
            ],
        ),
        _positive(
            "create_cli:color_converter",
            "create_app",
            "new_repo",
            "colors",
            ["hex_to_rgb", "rgb_to_hex", "validate_color"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "converter"],
            [
                "build a color converter cli for hex and rgb",
                "make a command that converts #ff00aa to rgb values and back",
                "create a tiny color utility with validation errors",
                "write a terminal color conversion script with tests",
            ],
        ),
        _positive(
            "create_cli:invoice_total",
            "create_app",
            "new_repo",
            "billing",
            ["parse_items", "subtotal", "tax", "grand_total"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "money"],
            [
                "make an invoice total cli that adds line items and tax",
                "create a billing helper command for subtotal tax and total",
                "build a script that calculates invoice totals from item prices",
                "write a small invoice calculator with tests",
            ],
        ),
        _positive(
            "create_cli:flashcards",
            "create_app",
            "new_repo",
            "flashcards",
            ["add_card", "quiz_mode", "score", "shuffle_cards"],
            ["cli", "storage", "tests"],
            ["interactive_cli"],
            ["greenfield", "cli", "interactive"],
            [
                "create a flashcard terminal app with quiz mode and scoring",
                "build a small cli for adding flashcards and practicing them",
                "make an offline flashcard tool that shuffles cards",
                "write a terminal study app with add card and quiz commands",
            ],
        ),
        _positive(
            "create_cli:backup_manifest",
            "create_app",
            "new_repo",
            "filesystem",
            ["scan_directory", "file_sizes", "checksum", "write_manifest"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "filesystem"],
            [
                "make a backup manifest cli that lists files sizes and checksums",
                "create a command to scan a directory and write a manifest json",
                "build a simple file inventory tool with checksums",
                "write a terminal backup manifest generator",
            ],
        ),
        _positive(
            "create_cli:http_status_stub",
            "create_app",
            "new_repo",
            "http",
            ["lookup_status_code", "offline_data", "search_phrase"],
            ["cli", "tests"],
            ["cli"],
            ["greenfield", "cli", "offline"],
            [
                "make an offline http status code lookup cli",
                "create a command that explains 404 500 and other http codes from local data",
                "build a no-network status code helper",
                "write a cli for searching http status phrases without calling the web",
            ],
        ),
    ]


def _create_library_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "create_library:slug_tools",
            "create_library",
            "new_repo",
            "strings",
            ["slugify", "deslugify_title", "normalize_whitespace"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "strings"],
            [
                "make string helpers for slugify deslugify title and whitespace cleanup",
                "create a small slug utility module with tests",
                "write python functions for URL slugs and normalized titles",
                "build a strings module with slug helpers",
            ],
        ),
        _positive(
            "create_library:stats_percentiles",
            "create_library",
            "new_repo",
            "math",
            ["mean", "median", "percentile", "standard_deviation"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "stats"],
            [
                "create stats helpers for mean median percentile and stddev",
                "make a small statistics module with tests for percentiles",
                "write math utilities for common summary stats",
                "build a python stats library without dependencies",
            ],
        ),
        _positive(
            "create_library:email_utils",
            "create_library",
            "new_repo",
            "email",
            ["normalize_email", "mask_email", "validate_email"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "validation"],
            [
                "write email utilities for normalize mask and validate",
                "create a small email helper module with tests",
                "make python functions that validate and hide email addresses",
                "build email formatting helpers",
            ],
        ),
        _positive(
            "create_library:url_utils",
            "create_library",
            "new_repo",
            "url",
            ["parse_query", "build_query", "ensure_scheme"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "url"],
            [
                "create url helpers for query strings and default schemes",
                "make a tiny URL utility module with parse and build query",
                "write helpers to add https when a url has no scheme",
                "build a python module for common url operations",
            ],
        ),
        _positive(
            "create_library:duration_parse",
            "create_library",
            "new_repo",
            "time",
            ["parse_duration", "format_duration", "seconds_total"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "time"],
            [
                "make duration parsing helpers for strings like 1h 30m",
                "create a time utility module that formats seconds nicely",
                "write parse_duration and format_duration with tests",
                "build a tiny duration library",
            ],
        ),
        _positive(
            "create_library:env_config",
            "create_library",
            "new_repo",
            "config",
            ["read_env", "typed_defaults", "required_keys"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "config"],
            [
                "create env config helpers with defaults and required keys",
                "make a module that reads settings from environment variables",
                "write typed config loading helpers with tests",
                "build a small environment config library",
            ],
        ),
        _positive(
            "create_library:retry_policy",
            "create_library",
            "new_repo",
            "retry",
            ["fixed_backoff", "exponential_backoff", "max_attempts"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "retry"],
            [
                "write retry policy helpers for fixed and exponential backoff",
                "create a small retry utilities module with max attempts",
                "make python helpers that compute retry delays",
                "build a dependency-free retry policy library",
            ],
        ),
        _positive(
            "create_library:table_format",
            "create_library",
            "new_repo",
            "formatting",
            ["format_table", "align_columns", "truncate_cells"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "formatting"],
            [
                "make a plain text table formatter with column alignment",
                "create table formatting helpers for terminal output",
                "write a module that formats rows into aligned columns",
                "build text table utilities with truncation support",
            ],
        ),
        _positive(
            "create_library:token_bucket",
            "create_library",
            "new_repo",
            "rate_limit",
            ["allow_request", "refill_tokens", "remaining_tokens"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "rate_limit"],
            [
                "create a token bucket rate limiter class with tests",
                "make an in-memory rate limit helper using token buckets",
                "write a small rate limiter module",
                "build a python token bucket implementation",
            ],
        ),
        _positive(
            "create_library:csv_schema",
            "create_library",
            "new_repo",
            "csv",
            ["validate_headers", "required_columns", "row_errors"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "csv"],
            [
                "write csv schema validation helpers for required columns",
                "create a module that checks csv headers and reports row errors",
                "make csv validation utilities with tests",
                "build a small csv schema checker",
            ],
        ),
        _positive(
            "create_library:tree_walk",
            "create_library",
            "new_repo",
            "filesystem",
            ["walk_files", "ignore_patterns", "relative_paths"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "filesystem"],
            [
                "make filesystem walk helpers with ignore patterns",
                "create a module that yields relative file paths under a root",
                "write tree walking utilities with tests",
                "build a tiny file discovery library",
            ],
        ),
        _positive(
            "create_library:roman_numerals",
            "create_library",
            "new_repo",
            "numbers",
            ["to_roman", "from_roman", "validate_range"],
            ["module", "tests"],
            ["python_api"],
            ["greenfield", "library", "numbers"],
            [
                "create roman numeral conversion helpers",
                "make a module for converting integers to roman numerals and back",
                "write roman numeral utilities with validation",
                "build a small numbers library for roman numerals",
            ],
        ),
    ]


def _existing_feature_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "feature:cli:quiet_flag",
            "add_feature",
            "existing_repo",
            "cli",
            ["quiet_flag", "suppress_non_error_output"],
            ["cli", "tests"],
            ["cli"],
            ["existing_repo", "feature", "cli"],
            [
                "add a --quiet flag that only prints errors",
                "make the existing command support quiet mode",
                "add quiet output to the cli without changing default output",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:api:status_endpoint",
            "add_feature",
            "existing_repo",
            "api",
            ["status_endpoint", "uptime_field"],
            ["route", "tests"],
            ["http_api"],
            ["existing_repo", "feature", "api"],
            [
                "add a status endpoint like the other api routes",
                "create an uptime status route following the existing pattern",
                "make the service expose /status with ok and uptime fields",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:serialization:include_id",
            "add_feature",
            "existing_repo",
            "serialization",
            ["include_id", "preserve_existing_fields"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "serialization"],
            [
                "include the object's id in the serialized response",
                "add id to the serializer without removing existing fields",
                "make profile serialization include the id field",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:pagination:cursor",
            "add_feature",
            "existing_repo",
            "pagination",
            ["cursor_pagination", "next_cursor", "backcompat_default"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "pagination"],
            [
                "add cursor pagination while keeping the old list behavior",
                "support next_cursor in the listing api",
                "make list results optionally use cursor pagination",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:cache:ttl_option",
            "add_feature",
            "existing_repo",
            "cache",
            ["ttl_option", "expire_entries"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "cache"],
            [
                "add a ttl option to the cache and expire old entries",
                "make cached values support time to live",
                "add cache expiration without changing non-ttl values",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:export:yaml",
            "add_feature",
            "existing_repo",
            "export",
            ["yaml_export", "preserve_json_export"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "export"],
            [
                "let the exporter write yaml as well as json",
                "add yaml export support and keep json working",
                "make report export support a yaml format option",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:validation:max_length",
            "add_feature",
            "existing_repo",
            "validation",
            ["max_length_validation", "clear_error_message"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "validation"],
            [
                "reject names longer than 80 characters with a clear error",
                "add max length validation to the existing name validator",
                "make validation fail cleanly for too-long labels",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:logging:request_id",
            "add_feature",
            "existing_repo",
            "logging",
            ["request_id_logging", "preserve_secret_redaction"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "logging"],
            [
                "include request id in logs but keep secrets redacted",
                "add request_id to retry log messages",
                "make debug logs carry the request id",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:auth:bearer",
            "add_feature",
            "existing_repo",
            "auth",
            ["bearer_token_auth", "follow_existing_auth_style"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "feature", "auth"],
            [
                "add bearer token auth following the existing auth style",
                "support Authorization Bearer headers in the client",
                "make the client accept a bearer token option",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:config:config_file",
            "add_feature",
            "existing_repo",
            "config",
            ["config_file_option", "default_config_path"],
            ["cli", "tests"],
            ["cli"],
            ["existing_repo", "feature", "config"],
            [
                "add a --config option and use the default config path when omitted",
                "make the cli read settings from a config file",
                "support a config file path without breaking env var overrides",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:calculator:power",
            "add_feature",
            "existing_repo",
            "calculator",
            ["power"],
            ["module", "tests"],
            ["cli"],
            ["existing_repo", "feature", "calculator"],
            [
                "add exponent support",
                "support power operator in the calculator",
                "make calculator.py handle 2 ^ 3",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "feature:calculator:modulo",
            "add_feature",
            "existing_repo",
            "calculator",
            ["modulo"],
            ["module", "tests"],
            ["cli"],
            ["existing_repo", "feature", "calculator"],
            [
                "add modulo support to the calculator",
                "support the percent operator for remainder",
                "make the calc handle 7 % 3",
            ],
            action="emit_existing_repo_change_spec",
        ),
    ]


def _bugfix_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "bugfix:dates:leap_year",
            "bugfix",
            "existing_repo",
            "dates",
            ["leap_year_feb_29"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "edge_case"],
            [
                "fix date validation for february 29 on leap years",
                "the date parser rejects leap day incorrectly",
                "make feb 29 valid only in leap years",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:csv:quoted_commas",
            "bugfix",
            "existing_repo",
            "csv",
            ["quoted_commas", "preserve_plain_fields"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "parser"],
            [
                "fix csv parsing when quoted fields contain commas",
                "quoted commas are splitting rows incorrectly",
                "handle commas inside csv quotes without breaking simple rows",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:cache:falsey",
            "bugfix",
            "existing_repo",
            "cache",
            ["cache_false_values", "cache_zero_values"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "falsey"],
            [
                "fix the cache so false and zero values are not treated as misses",
                "cached false values should be returned instead of recomputed",
                "make cache lookup distinguish missing from falsey values",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:paths:tilde",
            "bugfix",
            "existing_repo",
            "paths",
            ["expand_user_paths"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "filesystem"],
            [
                "fix path handling so ~/config expands before checking existence",
                "the file loader fails on tilde paths",
                "expand user paths in the config file lookup",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:http:case_insensitive_headers",
            "bugfix",
            "existing_repo",
            "http",
            ["case_insensitive_headers"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "http"],
            [
                "header lookup should be case insensitive",
                "fix response headers so content-type and Content-Type both work",
                "make http header matching ignore case",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:money:rounding",
            "bugfix",
            "existing_repo",
            "money",
            ["round_half_up", "avoid_float_error"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "money"],
            [
                "fix cents rounding so 10.005 rounds correctly",
                "money formatting has a float rounding bug",
                "avoid binary float errors in dollars to cents conversion",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:cli:exit_code",
            "bugfix",
            "existing_repo",
            "cli",
            ["nonzero_exit_on_error", "preserve_success_exit_zero"],
            ["cli", "tests"],
            ["cli"],
            ["existing_repo", "bugfix", "cli"],
            [
                "make the command exit nonzero when validation fails",
                "the cli prints an error but still exits 0",
                "fix error exit codes without changing successful runs",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:json:empty_file",
            "bugfix",
            "existing_repo",
            "json",
            ["empty_file_error", "no_traceback_for_user"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "json"],
            [
                "handle empty json files with a clear error",
                "the config loader crashes on empty json",
                "fix empty json input so users get a helpful message",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:unicode:width",
            "bugfix",
            "existing_repo",
            "formatting",
            ["unicode_width", "align_columns"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "unicode"],
            [
                "fix table alignment when names contain emoji or wide characters",
                "unicode text is breaking column widths",
                "make table formatting handle wide unicode characters",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "bugfix:imports:fallback",
            "bugfix",
            "existing_repo",
            "imports",
            ["new_import_path", "old_import_fallback"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "bugfix", "compatibility"],
            [
                "support the new import path but fall back to the old one",
                "fix imports after the dependency renamed its package",
                "try the new module name first and keep old versions working",
            ],
            action="emit_existing_repo_change_spec",
        ),
    ]


def _tests_only_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "tests:parser:comments",
            "add_tests",
            "existing_repo",
            "parser",
            ["test_comments", "test_blank_lines"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "tests_only", "parser"],
            [
                "add tests for parser comments and blank lines",
                "cover the config parser behavior for comment lines",
                "write pytest cases for blank and commented config entries",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "tests:calculator:divide_by_zero",
            "add_tests",
            "existing_repo",
            "calculator",
            ["test_divide_by_zero"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "tests_only", "calculator"],
            [
                "add tests for divide by zero in the calculator",
                "cover calculator errors when the divisor is zero",
                "write pytest cases for division error handling",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "tests:cli:help",
            "add_tests",
            "existing_repo",
            "cli",
            ["test_help_output", "test_invalid_args"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "tests_only", "cli"],
            [
                "add tests for --help and invalid cli arguments",
                "cover command help output without changing implementation",
                "write cli tests for usage text and bad inputs",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "tests:cache:expiry",
            "add_tests",
            "existing_repo",
            "cache",
            ["test_ttl_expiry", "test_non_expired_value"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "tests_only", "cache"],
            [
                "add tests for cache ttl expiry",
                "cover expired and non-expired cache values",
                "write cache tests around time based expiration",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "tests:serialization:missing_fields",
            "add_tests",
            "existing_repo",
            "serialization",
            ["test_missing_optional_fields"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "tests_only", "serialization"],
            [
                "add tests for serialization when optional fields are missing",
                "cover profile serializer missing display name",
                "write tests for partial serialization input",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "tests:docs:examples",
            "add_tests",
            "existing_repo",
            "docs",
            ["test_readme_examples"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "tests_only", "docs"],
            [
                "add tests that the readme usage examples still run",
                "cover documented examples with pytest",
                "write smoke tests for the docs snippets",
            ],
            action="emit_existing_repo_change_spec",
        ),
    ]


def _refactor_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "refactor:errors:helper",
            "refactor",
            "existing_repo",
            "errors",
            ["shared_error_helper", "preserve_messages"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "refactor"],
            [
                "extract the repeated validation error formatting into one helper",
                "dedupe error message formatting without changing text",
                "refactor validation errors to share a helper function",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "refactor:cli:commands",
            "refactor",
            "existing_repo",
            "cli",
            ["split_command_handlers", "preserve_cli_behavior"],
            ["module", "tests"],
            ["cli"],
            ["existing_repo", "refactor", "cli"],
            [
                "split the large cli command function into smaller handlers",
                "refactor cli subcommands without changing output",
                "move command handling into separate functions",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "refactor:config:dataclass",
            "refactor",
            "existing_repo",
            "config",
            ["config_dataclass", "preserve_keys"],
            ["module", "tests"],
            ["python_api"],
            ["existing_repo", "refactor", "config"],
            [
                "turn the config dict into a dataclass but keep the same keys",
                "refactor settings into a dataclass with backwards compatible access",
                "clean up config handling using a typed settings object",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "refactor:imports:module_split",
            "refactor",
            "existing_repo",
            "package",
            ["split_module", "preserve_public_imports"],
            ["package", "tests"],
            ["python_api"],
            ["existing_repo", "refactor", "package"],
            [
                "split this big module but keep the public imports working",
                "move helpers into a package without breaking import paths",
                "refactor the module layout and preserve the public API",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "refactor:tests:fixtures",
            "refactor",
            "existing_repo",
            "testing",
            ["shared_fixtures", "preserve_assertions"],
            ["tests"],
            ["pytest"],
            ["existing_repo", "refactor", "tests"],
            [
                "dedupe repeated test setup into pytest fixtures",
                "refactor the tests to share fixture setup",
                "clean up duplicate arrange code in the test suite",
            ],
            action="emit_existing_repo_change_spec",
        ),
    ]


def _config_docs_specs() -> list[dict[str, object]]:
    return [
        _positive(
            "config:ruff:pyproject",
            "config_change",
            "existing_repo",
            "lint",
            ["ruff_config", "line_length_100"],
            ["pyproject"],
            ["ruff_config"],
            ["existing_repo", "config", "lint"],
            [
                "add ruff config with line length 100",
                "configure ruff in pyproject and ignore generated files",
                "set up lint config for ruff",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "config:pytest:markers",
            "config_change",
            "existing_repo",
            "testing",
            ["pytest_markers", "slow_marker"],
            ["pyproject_or_pytest_ini"],
            ["pytest_config"],
            ["existing_repo", "config", "pytest"],
            [
                "add pytest markers for slow and integration tests",
                "configure pytest so the slow marker is registered",
                "update test config with custom markers",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "config:ci:matrix",
            "config_change",
            "existing_repo",
            "ci",
            ["python_version_matrix", "run_pytest"],
            ["ci_config"],
            ["github_actions"],
            ["existing_repo", "config", "ci"],
            [
                "add github actions that runs pytest on python 3.11 and 3.12",
                "create a ci workflow with a python version matrix",
                "configure CI to install and run tests on pushes",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "docs:readme:cli_usage",
            "docs_change",
            "existing_repo",
            "readme",
            ["readme_cli_usage", "examples"],
            ["readme"],
            ["docs"],
            ["existing_repo", "docs"],
            [
                "update the readme with cli usage examples",
                "document the new command line flags in the readme",
                "add a short usage section to README for the cli",
            ],
            action="emit_existing_repo_change_spec",
        ),
        _positive(
            "docs:api:parameter",
            "docs_change",
            "existing_repo",
            "api_docs",
            ["document_parameter", "preserve_examples"],
            ["docs"],
            ["docs"],
            ["existing_repo", "docs", "api"],
            [
                "document the timeout parameter in the api docs",
                "update docs for the new client option",
                "add parameter docs for timeout and default behavior",
            ],
            action="emit_existing_repo_change_spec",
        ),
    ]


def _clarification_specs() -> list[dict[str, object]]:
    return [
        _clarify(
            "clarify:auth:new_app",
            "clarify",
            "new_repo",
            "auth",
            ["auth_method", "app_type"],
            ["ambiguous", "clarification", "auth"],
            [
                "make an app with auth",
                "build auth for this new project",
                "add login stuff",
            ],
        ),
        _clarify(
            "clarify:database:unknown",
            "clarify",
            "unknown",
            "database",
            ["database_engine", "persistence_scope", "repo_target"],
            ["ambiguous", "clarification", "database"],
            [
                "add database support",
                "make it use a database",
                "hook this up to persistent storage",
            ],
        ),
        _clarify(
            "clarify:frontend:dashboard",
            "clarify",
            "new_repo",
            "frontend",
            ["data_source", "metrics", "target_user"],
            ["ambiguous", "clarification", "frontend"],
            [
                "make a dashboard for this",
                "build an admin dashboard",
                "create a nice analytics screen",
            ],
        ),
        _clarify(
            "clarify:performance:vague",
            "clarify",
            "existing_repo",
            "performance",
            ["slow_path", "metric", "acceptable_change_scope"],
            ["ambiguous", "clarification", "performance"],
            [
                "optimize it",
                "make this faster",
                "speed up the code",
            ],
        ),
        _clarify(
            "clarify:security:vague",
            "clarify",
            "existing_repo",
            "security",
            ["threat_model", "specific_failure", "auth_scheme"],
            ["ambiguous", "clarification", "security"],
            [
                "make the auth secure",
                "harden the security",
                "fix the security issues",
            ],
        ),
        _clarify(
            "clarify:scientific_calculator",
            "clarify",
            "new_repo",
            "calculator",
            ["feature_scope", "operations"],
            ["ambiguous", "clarification", "calculator", "unsupported"],
            [
                "make a scientific calculator",
                "build a complex calculator app",
                "create a graphing calculator thing",
                "make me a complex calc for spaceships",
                "make a calculator app with UI controls",
            ],
            unsupported=["scientific_operations_unspecified"],
        ),
        _clarify(
            "clarify:agent:vague",
            "clarify",
            "new_repo",
            "agent",
            ["tools", "permissions", "success_criteria"],
            ["ambiguous", "clarification", "agent"],
            [
                "build an agent that does my work",
                "make a coding bot for everything",
                "create an automation agent",
            ],
        ),
        _clarify(
            "clarify:api:usual_endpoints",
            "clarify",
            "existing_repo",
            "api",
            ["resource", "operations"],
            ["ambiguous", "clarification", "implicit_scope"],
            [
                "add the usual endpoints",
                "make the standard api routes",
                "add CRUD for this",
            ],
        ),
        _clarify(
            "clarify:tests:vague",
            "clarify",
            "existing_repo",
            "testing",
            ["target_behavior", "test_type"],
            ["ambiguous", "clarification", "tests"],
            [
                "add more tests",
                "improve the test coverage",
                "write tests for the important stuff",
            ],
        ),
        _clarify(
            "clarify:refactor:vague",
            "clarify",
            "existing_repo",
            "quality",
            ["goal", "scope", "behavior_change_allowed"],
            ["ambiguous", "clarification", "refactor"],
            [
                "clean up the code",
                "make this nicer",
                "refactor everything",
            ],
        ),
    ]


def _positive(
    family: str,
    task_type: str,
    repo_mode: str,
    domain: str,
    features: list[str],
    artifacts: list[str],
    interfaces: list[str],
    tags: list[str],
    prompts: list[str],
    *,
    action: str | None = None,
) -> dict[str, object]:
    if action is None:
        action = "emit_request_spec" if repo_mode == "new_repo" else "emit_existing_repo_change_spec"
    return {
        "family": family,
        "task_type": task_type,
        "repo_mode": repo_mode,
        "domain": domain,
        "action": action,
        "features": features,
        "artifacts": artifacts,
        "interfaces": interfaces,
        "tags": tags,
        "prompts": prompts,
    }


def _clarify(
    family: str,
    task_type: str,
    repo_mode: str,
    domain: str,
    clarification_fields: list[str],
    tags: list[str],
    prompts: list[str],
    *,
    unsupported: list[str] | None = None,
) -> dict[str, object]:
    return {
        "family": family,
        "task_type": task_type,
        "repo_mode": repo_mode,
        "domain": domain,
        "action": "ask_clarification",
        "features": [],
        "artifacts": [],
        "interfaces": [],
        "clarify": True,
        "clarification_fields": clarification_fields,
        "unsupported_requirements": unsupported or [],
        "tags": tags,
        "prompts": prompts,
    }


def _split_for_family(family: str) -> str:
    digest = hashlib.blake2b(family.encode("utf-8"), digest_size=2).digest()
    bucket = int.from_bytes(digest, "big") % 10
    if bucket < 7:
        return "train"
    if bucket < 8:
        return "validation"
    return "test"


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} must contain JSON objects")
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def _validate(rows: list[dict[str, object]]) -> None:
    ids: set[str] = set()
    prompts: set[str] = set()
    required = {
        "id",
        "split",
        "source_type",
        "task_type",
        "repo_mode",
        "domain",
        "prompt",
        "expected",
        "tags",
    }
    for index, row in enumerate(rows):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"row {index} missing fields: {sorted(missing)}")
        row_id = str(row["id"])
        prompt = str(row["prompt"])
        normalized = _normalize_prompt(prompt)
        if row_id in ids:
            raise ValueError(f"duplicate id {row_id}")
        if normalized in prompts:
            raise ValueError(f"duplicate prompt {prompt!r}")
        ids.add(row_id)
        prompts.add(normalized)


def _normalize_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.strip().lower())


if __name__ == "__main__":
    raise SystemExit(main())
