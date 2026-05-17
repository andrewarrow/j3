from __future__ import annotations

from pathlib import Path

import json

from actions import PatchAction, PatchActionKind, PatchTarget
from candidate_ranker.features import _candidate_record_features
from evaluation import (
    EvalSummary,
    RepairTask,
    TaskEvalResult,
    evaluate_tasks,
    load_tasks,
    write_candidate_outcomes,
    write_eval_diagnostics,
)
from failure_hints import AssertionComparison, PytestFailureHint
from patching import CandidatePatch, PatchPlanResult
from repair.patching.context import attach_target_context
from synth import SourceEdit
from training import train_from_path


def test_load_tasks_from_directory() -> None:
    tasks = load_tasks(Path("examples/greenshot_bugs"))

    assert len(tasks) == 5
    assert tasks[0].name == "discount_return_expr"


def test_load_greenshot_4_tasks() -> None:
    tasks = load_tasks(Path("examples/greenshot_4"))

    assert len(tasks) == 27
    assert tasks[0].name == "discount_remaining_price"
    assert tasks[-1].name == "parse_port_try_except"


def test_load_greenshot_5_tasks() -> None:
    tasks = load_tasks(Path("examples/greenshot_5"))

    by_name = {task.name: task for task in tasks}

    assert len(tasks) == 20
    assert tasks[0].name == "quote_total_helper_discount"
    assert tasks[0].family == "expression_helper"
    assert tasks[0].split in {"train", "validation", "test"}
    assert by_name["delivery_summary_multi_step_import_then_literal"].family == "multi_step_revealed_failure"
    assert by_name["delivery_summary_multi_step_import_then_literal"].max_steps == 2
    assert tasks[8].preferred_patch == {
        "file_path": "shop/policies.py",
        "action": "change_operator",
        "symbol": "express_shipping_eligible",
        "params": {"from": ">", "to": ">="},
    }
    assert by_name["training_data_file_default_warning"].preferred_patch == {
        "file_path": "shop/data.py",
        "action": "add_fallback_warning",
        "symbol": "__post_init__",
        "params": {
            "attribute": "validation_fraction",
            "value": 0.05,
            "exception": "ValueError",
        },
    }
    assert by_name["checkout_startup_idempotence_guard"].preferred_patch == {
        "file_path": "shop/startup.py",
        "action": "insert_guard",
        "symbol": "start_checkout_hooks",
        "params": {
            "condition": "_checkout_hooks_started",
            "state_flag": "_checkout_hooks_started",
            "return": "checkout_start_events",
        },
    }
    assert by_name["cache_backend_import_compatibility_fallback"].preferred_patch == {
        "file_path": "shop/cache.py",
        "action": "add_import_fallback",
        "symbol": "CacheBackend",
        "params": {
            "name": "CacheBackend",
            "primary_module": "shop.cache_v2",
            "fallback_module": "shop.cache_legacy",
        },
    }
    assert by_name["checkout_step_metadata_dict_key"].preferred_patch == {
        "file_path": "shop/widgets.py",
        "action": "change_dict_key",
        "symbol": "checkout_step_metadata",
        "params": {
            "from": "icon",
            "to": "metadata_icon",
        },
    }


def test_load_greenshot_6_tasks() -> None:
    tasks = load_tasks(Path("examples/greenshot_6"))
    by_name = {task.name: task for task in tasks}

    assert len(tasks) == 45
    assert tasks[0].name == "core_metadata_version_dict_value"
    assert tasks[0].family == "mapping_value"
    assert tasks[0].source_type == "mutation"
    assert tasks[0].preferred_patch == {
        "file_path": "pkgmeta/metadata.py",
        "action": "change_dict_value",
        "symbol": "default_project_metadata",
        "params": {
            "key": "metadata_version",
            "from": "2.2",
            "to": "2.3",
        },
    }
    assert by_name["apache_license_classifier_dict_value"].preferred_patch == {
        "file_path": "pkgmeta/metadata.py",
        "action": "change_dict_value",
        "symbol": "license_classifier",
        "params": {
            "key": "Apache-2.0",
            "from": "License :: OSI Approved :: Apache License",
            "to": "License :: OSI Approved :: Apache Software License",
        },
    }
    assert by_name["readme_missing_file_exception_key"].family == "exception_context"
    assert by_name["readme_missing_file_exception_key"].source_type == "git_history"
    assert by_name["readme_missing_file_exception_key"].preferred_patch == {
        "file_path": "pkgmeta/metadata.py",
        "action": "change_literal",
        "symbol": "validate_readme_file",
        "params": {
            "from": "project.license.file",
            "to": "project.readme.file",
        },
    }
    assert by_name["dynamic_field_error_message"].family == "exception_message"
    assert by_name["dynamic_field_error_message"].source_type == "git_history"
    assert by_name["dynamic_field_error_message"].preferred_patch == {
        "file_path": "pkgmeta/metadata.py",
        "action": "change_literal",
        "symbol": "validate_dynamic_field",
        "params": {
            "from": " declared as dynamic in but is defined",
            "to": ' declared as dynamic in "project.dynamic" but is defined',
        },
    }
    assert by_name["prettytable_missing_attribute_quote"].family == "table_legacy_attribute_error"
    assert by_name["prettytable_missing_attribute_quote"].source_type == "git_history"
    assert by_name["prettytable_missing_attribute_quote"].preferred_patch == {
        "file_path": "tablefmt/legacy.py",
        "action": "change_literal",
        "symbol": "resolve_legacy_symbol",
        "params": {
            "from": "module 'tablefmt.legacy' has no attribute '{name}",
            "to": "module 'tablefmt.legacy' has no attribute '{name}'",
        },
    }
    assert by_name["pip_list_outdated_freeze_error_message"].family == "pip_list_option_error"
    assert by_name["pip_list_outdated_freeze_error_message"].source_type == "git_history"
    assert by_name["pip_list_outdated_freeze_error_message"].split == "train"
    assert by_name["pip_list_outdated_freeze_error_message"].preferred_patch == {
        "file_path": "piplist/listing.py",
        "action": "change_literal",
        "symbol": "validate_list_options",
        "params": {
            "from": "List format 'freeze' can not be used with the --outdated option.",
            "to": "List format 'freeze' cannot be used together with the --outdated option.",
        },
    }
    assert by_name["chalice_control_plane_programmatically_docstring"].family == (
        "api_docstring_typo"
    )
    assert by_name["chalice_control_plane_programmatically_docstring"].source_type == (
        "git_history"
    )
    assert by_name["chalice_control_plane_programmatically_docstring"].split == "train"
    assert by_name["chalice_control_plane_programmatically_docstring"].preferred_patch == {
        "file_path": "apidocs/api.py",
        "action": "change_literal",
        "symbol": "control_plane_description",
        "params": {
            "from": "Control plane APIs for programatically building/deploying Chalice apps.",
            "to": "Control plane APIs for programmatically building/deploying Chalice apps.",
        },
    }
    assert by_name["starlette_websocket_runtime_error_allowed_messages"].family == (
        "websocket_state_error_message"
    )
    assert by_name["starlette_websocket_runtime_error_allowed_messages"].source_type == (
        "git_history"
    )
    assert by_name["starlette_websocket_runtime_error_allowed_messages"].split == "train"
    assert by_name["starlette_websocket_runtime_error_allowed_messages"].preferred_patch == {
        "file_path": "websocketstate/websockets.py",
        "action": "change_literal",
        "symbol": "connecting_send_error_message",
        "params": {
            "from": 'Expected message "websocket.connect"',
            "to": 'Expected message "websocket.accept" or "websocket.close"',
        },
    }
    assert by_name["flask_ssl_context_key_option_quote"].family == (
        "cli_ssl_error_message"
    )
    assert by_name["flask_ssl_context_key_option_quote"].source_type == "git_history"
    assert by_name["flask_ssl_context_key_option_quote"].split == "train"
    assert by_name["flask_ssl_context_key_option_quote"].preferred_patch == {
        "file_path": "flaskcli/ssl.py",
        "action": "change_literal",
        "symbol": "validate_key",
        "params": {
            "from": 'When "--cert" is an SSLContext object, "--key is not used.',
            "to": 'When "--cert" is an SSLContext object, "--key" is not used.',
        },
    }
    assert by_name["chainlit_oauth_state_logging_percent_format"].family == (
        "logging_format_string"
    )
    assert by_name["chainlit_oauth_state_logging_percent_format"].source_type == (
        "git_history"
    )
    assert by_name["chainlit_oauth_state_logging_percent_format"].split == "train"
    assert by_name["chainlit_oauth_state_logging_percent_format"].preferred_patch == {
        "file_path": "logformat/oauth.py",
        "action": "change_literal",
        "symbol": "oauth_state_log_template",
        "params": {
            "from": "Unable to validate oauth state: %1",
            "to": "Unable to validate oauth state: %s",
        },
    }
    assert by_name["django_makemessages_locale_directory_exists"].family == (
        "i18n_error_message"
    )
    assert by_name["django_makemessages_locale_directory_exists"].source_type == (
        "git_history"
    )
    assert by_name["django_makemessages_locale_directory_exists"].split == "train"
    assert by_name["django_makemessages_locale_directory_exists"].preferred_patch == {
        "file_path": "i18nmsgs/extraction.py",
        "action": "change_literal",
        "symbol": "locale_directory_hint",
        "params": {
            "from": "the 'locale' directory exist in an app",
            "to": "the 'locale' directory exists in an app",
        },
    }
    assert by_name["poetry_project_directory_unable_typo"].family == (
        "venv_error_message"
    )
    assert by_name["poetry_project_directory_unable_typo"].source_type == (
        "git_history"
    )
    assert by_name["poetry_project_directory_unable_typo"].split == "train"
    assert by_name["poetry_project_directory_unable_typo"].preferred_patch == {
        "file_path": "poetryenv/venv.py",
        "action": "change_literal",
        "symbol": "project_directory_error",
        "params": {
            "from": "Unbale to determine the project's directory",
            "to": "Unable to determine the project's directory",
        },
    }
    assert by_name["http_no_store_directive_subscript_key"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "change_subscript_key",
        "symbol": "parse_request_cache_control",
        "params": {
            "from": "no-store",
            "to": "no_store",
        },
    }
    assert by_name["http_cache_key_argument_order"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "swap_call_arg",
        "symbol": "cache_key_for_request",
        "params": {
            "left": 0,
            "right": 1,
        },
    }
    assert by_name["http_vary_preserve_case_keyword"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "add_keyword_arg",
        "symbol": "response_vary_members",
        "params": {
            "keyword": "preserve_case",
            "value": "preserve_case",
            "callee": "normalize_vary_header",
        },
    }
    assert by_name["http_no_store_response_with_etag"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "change_operator",
        "symbol": "should_store_response",
        "params": {
            "from": "not in",
            "to": "in",
        },
    }
    assert by_name["http_no_cache_revalidation_with_etag"].split == "train"
    assert by_name["http_no_cache_revalidation_with_etag"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "change_operator",
        "symbol": "should_revalidate_response",
        "params": {
            "from": "not in",
            "to": "in",
        },
    }
    assert by_name["http_stale_response_without_must_revalidate"].split == "train"
    assert by_name["http_stale_response_without_must_revalidate"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "change_operator",
        "symbol": "should_serve_stale_response",
        "params": {
            "from": "not in",
            "to": "in",
        },
    }
    assert by_name["http_range_request_bypasses_cache"].preferred_patch == {
        "file_path": "httpcache/policy.py",
        "action": "change_literal",
        "symbol": "cached_response_for_request",
        "params": {
            "from": "Content-Range",
            "to": "Range",
        },
    }
    assert by_name["click_invalid_directory_filename_repr"].split == "train"
    assert by_name["click_invalid_directory_filename_repr"].source_type == "git_history"
    assert by_name["click_invalid_directory_filename_repr"].preferred_patch == {
        "file_path": "cliformat/types.py",
        "action": "change_literal",
        "symbol": "invalid_directory_message",
        "params": {
            "from": "{name} '{filename}' is a directory.",
            "to": "{name} {filename!r} is a directory.",
        },
    }
    assert by_name["litgpt_zero_temperature_greedy_condition"].split == "train"
    assert by_name["litgpt_zero_temperature_greedy_condition"].source_type == "git_history"
    assert by_name["litgpt_zero_temperature_greedy_condition"].preferred_patch == {
        "file_path": "sampling/generate.py",
        "action": "modify_condition",
        "symbol": "decode_mode",
        "params": {
            "operation": "change_bool_operator",
            "from": "or",
            "to": "and",
        },
    }
    assert by_name["dateutil_lowercase_z_utc_suffix"].split == "train"
    assert by_name["dateutil_lowercase_z_utc_suffix"].source_type == "git_history"
    assert by_name["dateutil_lowercase_z_utc_suffix"].preferred_patch == {
        "file_path": "dateparse/isoparse.py",
        "action": "change_module_constant",
        "symbol": "UTC_ZONE_NAMES",
        "params": {
            "name": "UTC_ZONE_NAMES",
            "from": "UTC GMT Z",
            "to": "UTC GMT Z z",
        },
    }
    assert by_name["tornado_header_newline_forbidden_regex"].split == "train"
    assert by_name["tornado_header_newline_forbidden_regex"].source_type == "git_history"
    assert by_name["tornado_header_newline_forbidden_regex"].preferred_patch == {
        "file_path": "headers/validation.py",
        "action": "change_literal",
        "symbol": "forbidden_header_chars_pattern",
        "params": {
            "from": r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]",
            "to": r"[\x00-\x08\x0A-\x1F\x7F]",
        },
    }
    assert by_name["humanize_gnu_ronna_suffix"].split == "train"
    assert by_name["humanize_gnu_ronna_suffix"].source_type == "git_history"
    assert by_name["humanize_gnu_ronna_suffix"].preferred_patch == {
        "file_path": "filesize/format.py",
        "action": "change_dict_value",
        "symbol": "suffixes",
        "params": {
            "key": "gnu",
            "from": "KMGTPEZY",
            "to": "KMGTPEZYRQ",
        },
    }
    assert by_name["packaging_pyemscripten_platform_config_var"].split == "train"
    assert by_name["packaging_pyemscripten_platform_config_var"].source_type == "git_history"
    assert by_name["packaging_pyemscripten_platform_config_var"].preferred_patch == {
        "file_path": "platformtags/tags.py",
        "action": "change_literal",
        "symbol": "emscripten_platforms",
        "params": {
            "from": "PYEMSCRIPTEN_ABI_VERSION",
            "to": "PYEMSCRIPTEN_PLATFORM_VERSION",
        },
    }
    assert by_name["yfinance_market_data_error_typo"].split == "train"
    assert by_name["yfinance_market_data_error_typo"].source_type == "git_history"
    assert by_name["yfinance_market_data_error_typo"].preferred_patch == {
        "file_path": "marketdata/market.py",
        "action": "change_literal",
        "symbol": "market_data_error",
        "params": {
            "from": ": Failed to retrieve market data and recieved faulty data.",
            "to": ": Failed to retrieve market data and received faulty data.",
        },
    }
    assert by_name["urllib3_getheader_warning_typo"].split == "train"
    assert by_name["urllib3_getheader_warning_typo"].source_type == "git_history"
    assert by_name["urllib3_getheader_warning_typo"].preferred_patch == {
        "file_path": "httpresponse/response.py",
        "action": "change_literal",
        "symbol": "getheader",
        "params": {
            "from": "HTTResponse.headers.get(name, default)",
            "to": "HTTPResponse.headers.get(name, default)",
        },
    }
    assert by_name["httpx_async_client_sync_request_article"].split == "train"
    assert by_name["httpx_async_client_sync_request_article"].source_type == "git_history"
    assert by_name["httpx_async_client_sync_request_article"].preferred_patch == {
        "file_path": "httpclient/client.py",
        "action": "change_literal",
        "symbol": "send",
        "params": {
            "from": "Attempted to send an sync request with an AsyncClient instance.",
            "to": "Attempted to send a sync request with an AsyncClient instance.",
        },
    }
    assert by_name["posting_escaped_path_param_regex"].split == "train"
    assert by_name["posting_escaped_path_param_regex"].source_type == "git_history"
    assert by_name["posting_escaped_path_param_regex"].preferred_patch == {
        "file_path": "pathparams/routes.py",
        "action": "change_literal",
        "symbol": "path_param_pattern",
        "params": {
            "from": ":([A-Za-z_][A-Za-z0-9_]*)",
            "to": "(?<!:):([A-Za-z_][A-Za-z0-9_]*)",
        },
    }
    assert by_name["rich_common_cell_width_ascii_range"].split == "train"
    assert by_name["rich_common_cell_width_ascii_range"].source_type == "git_history"
    assert by_name["rich_common_cell_width_ascii_range"].preferred_patch == {
        "file_path": "cellwidth/cells.py",
        "action": "change_literal",
        "symbol": "common_single_cell_pattern",
        "params": {
            "from": r"^[\u0020-\u006f\u00a0\u02ff\u0370-\u0482]*$",
            "to": r"^[\u0020-\u007f\u00a0\u02ff\u0370-\u0482]*$",
        },
    }
    assert by_name["pydantic_field_regex_pattern_message"].split == "train"
    assert by_name["pydantic_field_regex_pattern_message"].source_type == "git_history"
    assert by_name["pydantic_field_regex_pattern_message"].preferred_patch == {
        "file_path": "fieldopts/fields.py",
        "action": "change_literal",
        "symbol": "validate_field_options",
        "params": {
            "from": "`regex` is removed. use `Pattern` instead",
            "to": "`regex` is removed. use `pattern` instead",
        },
    }
    assert by_name["dvc_pre_commit_repo_treeverse_url"].split == "train"
    assert by_name["dvc_pre_commit_repo_treeverse_url"].source_type == "git_history"
    assert by_name["dvc_pre_commit_repo_treeverse_url"].preferred_patch == {
        "file_path": "dvchooks/install.py",
        "action": "change_dict_value",
        "symbol": "pre_commit_hook_entry",
        "params": {
            "key": "repo",
            "from": "https://github.com/iterative/dvc",
            "to": "https://github.com/treeverse/dvc",
        },
    }
    assert by_name["scrapy_playwright_download_log_typo"].split == "train"
    assert by_name["scrapy_playwright_download_log_typo"].source_type == "git_history"
    assert by_name["scrapy_playwright_download_log_typo"].preferred_patch == {
        "file_path": "playwrightlog/handler.py",
        "action": "change_literal",
        "symbol": "download_wait_template",
        "params": {
            "from": "Waiting on dowload to finish for %s",
            "to": "Waiting on download to finish for %s",
        },
    }
    assert by_name["requests_prepared_request_docline_typo"].split == "train"
    assert by_name["requests_prepared_request_docline_typo"].source_type == "git_history"
    assert by_name["requests_prepared_request_docline_typo"].preferred_patch == {
        "file_path": "requestdocs/adapters.py",
        "action": "change_literal",
        "symbol": "request_parameter_description",
        "params": {
            "from": "The PreparedReqest being sent over the connection.",
            "to": "The PreparedRequest being sent over the connection.",
        },
    }
    assert by_name["cookie_default_secure_flag_dict_value"].split == "test"
    assert by_name["cookie_default_secure_flag_dict_value"].preferred_patch == {
        "file_path": "webcookies/policy.py",
        "action": "change_dict_value",
        "symbol": "default_cookie_attributes",
        "params": {
            "key": "secure",
            "from": True,
            "to": False,
        },
    }
    assert by_name["cookie_partitioned_default_dict_value"].split == "train"
    assert by_name["cookie_partitioned_default_dict_value"].preferred_patch == {
        "file_path": "webcookies/policy.py",
        "action": "change_dict_value",
        "symbol": "default_partitioned_cookie_attributes",
        "params": {
            "key": "partitioned",
            "from": False,
            "to": True,
        },
    }
    assert by_name["cookie_pair_argument_order"].preferred_patch == {
        "file_path": "webcookies/policy.py",
        "action": "swap_call_arg",
        "symbol": "render_cookie_pair",
        "params": {
            "left": 0,
            "right": 1,
        },
    }
    assert by_name["cookie_scope_include_path_keyword"].preferred_patch == {
        "file_path": "webcookies/policy.py",
        "action": "add_keyword_arg",
        "symbol": "cookie_scope_key",
        "params": {
            "keyword": "include_path",
            "value": True,
            "callee": "normalize_scope",
        },
    }


def test_evaluate_greenshot_bugs(tmp_path) -> None:
    training = train_from_path(
        data_path=Path("examples/greenshot_bugs"),
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=80,
    )

    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_bugs"),
        model_path=training.model_path,
        timeout_seconds=10,
    )

    assert summary.total == 5
    assert summary.ranked_solved >= 4


def test_evaluate_greenshot_3() -> None:
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_3"),
        model_path=None,
        timeout_seconds=10,
    )

    assert summary.total == 4
    assert summary.ranked_solved == 4
    assert summary.ranked_pass_at_1 == 4


def test_write_eval_diagnostics(tmp_path) -> None:
    training = train_from_path(
        data_path=Path("examples/greenshot_bugs"),
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=80,
    )
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_bugs"),
        model_path=training.model_path,
        timeout_seconds=10,
        max_candidates=5,
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))

    assert payload["tasks"]
    assert "summary" in payload
    assert "ranker_paths" in payload["summary"]["ranked"]
    assert "ranker_scores_present" in payload["summary"]["ranked"]
    assert "per_action" in payload["summary"]["ranked"]
    assert "per_task_family" in payload["summary"]["ranked"]
    assert "per_source_type" in payload["summary"]["ranked"]
    assert "top_failed_candidate_reasons" in payload["summary"]["ranked"]
    assert "failure_modes" in payload["summary"]["ranked"]
    assert payload["tasks"][0]["family"] == "unclassified"
    assert payload["tasks"][0]["source_type"] == "handcrafted"
    assert payload["tasks"][0]["split"] in {"train", "validation", "test"}
    assert "summary" in payload["tasks"][0]["ranked"]
    assert "ranker_path" in payload["tasks"][0]["ranked"]["summary"]
    assert "ranker_scores_present" in payload["tasks"][0]["ranked"]["summary"]
    assert "selected_ranker_score" in payload["tasks"][0]["ranked"]["summary"]
    assert "failure_hints" in payload["tasks"][0]["ranked"]
    assert "tested_candidates" in payload["tasks"][0]["ranked"]
    assert "params" in payload["tasks"][0]["ranked"]["tested_candidates"][0]
    assert "ranker_score" in payload["tasks"][0]["ranked"]["tested_candidates"][0]
    assert "target_context" in payload["tasks"][0]["ranked"]["tested_candidates"][0]


def test_write_eval_diagnostics_records_ranker_scores(tmp_path) -> None:
    ranker_path = tmp_path / "candidate-ranker.json"
    selected = _candidate_patch(ranker_score=1.25)
    plan = PatchPlanResult(
        repo=tmp_path,
        test_command="python -m pytest tests/test_bug.py",
        baseline_exit_code=1,
        candidates_generated=1,
        candidates_tested=1,
        selected=selected,
        applied=True,
        test_output="",
        ranker_path=ranker_path,
        tested_candidates=(selected,),
    )
    summary = EvalSummary(
        tasks=[
            TaskEvalResult(
                task=RepairTask(
                    name="ranked",
                    repo=tmp_path,
                    test_command="python -m pytest tests/test_bug.py",
                ),
                baseline=plan,
                ranked=plan,
            )
        ]
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))

    assert payload["summary"]["ranked"]["ranker_paths"] == [str(ranker_path)]
    assert payload["summary"]["ranked"]["ranker_scores_present"] is True
    assert payload["tasks"][0]["ranked"]["summary"]["ranker_path"] == str(ranker_path)
    assert payload["tasks"][0]["ranked"]["summary"]["ranker_scores_present"] is True
    assert payload["tasks"][0]["ranked"]["summary"]["selected_ranker_score"] == 1.25


def test_diagnostics_records_skipped_phase(tmp_path) -> None:
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_3"),
        model_path=None,
        timeout_seconds=10,
        max_candidates=1,
        phase="ranked",
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))

    assert payload["summary"]["baseline"]["skipped"] is True
    assert payload["summary"]["baseline"]["tasks"] == 0
    assert payload["summary"]["baseline"]["skipped_tasks"] == 4
    assert payload["summary"]["ranked"]["skipped"] is False
    assert payload["tasks"][0]["baseline"] == {"skipped": True}
    assert payload["tasks"][0]["ranked"]["skipped"] is False


def test_eval_explores_after_first_passing_candidate(tmp_path) -> None:
    tasks_dir = _write_multi_pass_task(tmp_path)

    summary = evaluate_tasks(
        tasks_path=tasks_dir,
        model_path=None,
        timeout_seconds=10,
        max_candidates=3,
        phase="ranked",
        explore_after_pass=2,
    )

    plan = summary.tasks[0].ranked
    assert plan is not None
    assert plan.selected is not None
    assert plan.first_passing_index == 1
    assert plan.candidates_tested == 3
    assert len(plan.passing_candidates) == 2
    assert summary.ranked_solved == 1
    assert summary.ranked_pass_at_1 == 1


def test_eval_uses_task_level_max_steps(tmp_path) -> None:
    summary = evaluate_tasks(
        tasks_path=Path("examples/greenshot_5/tasks.json"),
        model_path=None,
        timeout_seconds=10,
        max_candidates=80,
        phase="ranked",
    )

    task = next(
        result
        for result in summary.tasks
        if result.task.name == "delivery_summary_multi_step_import_then_literal"
    )

    assert task.ranked is not None
    assert task.ranked.selected is not None
    assert len(task.ranked.selected_candidates) == 2

    outcomes = write_candidate_outcomes(summary, tmp_path / "outcomes.jsonl")
    rows = [
        json.loads(line)
        for line in outcomes.read_text(encoding="utf-8").splitlines()
        if '"delivery_summary_multi_step_import_then_literal"' in line
    ]
    assert rows[0]["failure_hints"][0]["missing_names"] == ["delivery_speed_label"]
    assert rows[-1]["failure_hints"][0]["missing_keys"] == ["expres"]


def test_diagnostics_records_exploration_after_pass(tmp_path) -> None:
    tasks_dir = _write_multi_pass_task(tmp_path)
    summary = evaluate_tasks(
        tasks_path=tasks_dir,
        model_path=None,
        timeout_seconds=10,
        max_candidates=3,
        phase="ranked",
        explore_after_pass=2,
    )

    diagnostics = write_eval_diagnostics(summary, tmp_path / "diagnostics.json")
    payload = json.loads(diagnostics.read_text(encoding="utf-8"))
    ranked = payload["tasks"][0]["ranked"]

    assert ranked["first_passing_index"] == 1
    assert ranked["candidates_tested_before_pass"] == 0
    assert ranked["candidates_tested_after_pass"] == 2
    assert len(ranked["passing_candidates"]) == 2
    assert [candidate["passed"] for candidate in ranked["tested_candidates"]] == [True, True, False]
    assert ranked["summary"]["first_passing_index"] == 1
    assert ranked["summary"]["passing_candidates"] == 2


def test_write_candidate_outcomes_jsonl_records_one_row_per_tested_candidate(tmp_path) -> None:
    tasks_dir = _write_multi_pass_task(tmp_path)
    summary = evaluate_tasks(
        tasks_path=tasks_dir,
        model_path=None,
        timeout_seconds=10,
        max_candidates=3,
        phase="ranked",
        explore_after_pass=2,
    )

    outcomes = write_candidate_outcomes(summary, tmp_path / "candidate_outcomes.jsonl")
    rows = [
        json.loads(line)
        for line in outcomes.read_text(encoding="utf-8").splitlines()
    ]

    assert len(rows) == 3
    assert {row["task"] for row in rows} == {"multi_pass_literal"}
    assert {row["task_family"] for row in rows} == {"unclassified"}
    assert {row["source_type"] for row in rows} == {"handcrafted"}
    assert {row["split"] for row in rows} == {"validation"}
    assert {row["language"] for row in rows} == {"python"}
    assert {row["phase"] for row in rows} == {"ranked"}
    assert [row["rank_index"] for row in rows] == [1, 2, 3]
    assert [row["passed"] for row in rows] == [True, True, False]
    assert [row["is_first_pass"] for row in rows] == [True, False, False]
    assert [row["preferred"] for row in rows] == [False, False, False]
    assert all(row["first_passing_index"] == 1 for row in rows)
    assert all(row["passing_candidates"] == 2 for row in rows)
    assert all(row["other_candidates_also_passed"] is True for row in rows)
    assert [row["equivalent_candidate_ranks"] for row in rows] == [[], [], []]
    assert [row["overlapping_candidate_ranks"] for row in rows] == [[2, 3], [1, 3], [1, 2]]
    assert [row["overlapping_passing_candidate_ranks"] for row in rows] == [[2], [1], [1, 2]]
    assert [row["has_overlapping_candidate"] for row in rows] == [True, True, True]
    assert all("failure_hints" in row for row in rows)
    assert all(isinstance(row["failure_hints"], list) for row in rows)
    assert all("target_context" in row for row in rows)
    assert {
        "file_path",
        "action",
        "params",
        "reason",
        "model_score",
        "failure_hint_score",
        "ranker_score",
        "target_context",
        "diff_added_lines",
        "diff_removed_lines",
        "diff_changed_lines",
        "edit_line_span",
        "edit_replacement_lines",
        "edit_line_delta",
        "edit_target_line_distance",
        "edit_within_target_span",
        "edit_is_single_line",
        "ast_parse_ok",
        "ast_delta_added_features",
        "ast_delta_removed_features",
        "ast_delta_added_count",
        "ast_delta_removed_count",
        "ast_delta_net_count",
        "preferred",
        "equivalent_candidate_ranks",
        "overlapping_candidate_ranks",
        "equivalent_passing_candidate_ranks",
        "overlapping_passing_candidate_ranks",
    }.issubset(rows[0])
    assert all(row["diff_changed_lines"] >= 1 for row in rows)
    assert all(row["edit_line_span"] >= 1 for row in rows)
    assert all(row["ast_parse_ok"] is True for row in rows)
    assert all(isinstance(row["ast_delta_added_features"], dict) for row in rows)
    assert any(row["ast_delta_added_features"] for row in rows)


def test_write_candidate_outcomes_preserves_scalar_dict_value_assertion_delta(tmp_path) -> None:
    preferred = _cookie_host_prefix_candidate(to="__Host-")
    false = _cookie_host_prefix_candidate(to="host")
    hint = PytestFailureHint(
        assertions=[
            AssertionComparison(actual="__Host", operator="==", expected="__Host-"),
        ],
    )
    plan = PatchPlanResult(
        repo=tmp_path,
        test_command="python -m pytest tests/test_policy.py",
        baseline_exit_code=1,
        candidates_generated=2,
        candidates_tested=2,
        selected=preferred,
        applied=True,
        test_output="",
        tested_candidates=(preferred, false),
        failure_hints=(hint,),
        tested_candidate_hints=((hint,), (hint,)),
        first_passing_index=1,
        passing_candidates=(preferred,),
        selected_candidates=(preferred,),
    )
    summary = EvalSummary(
        tasks=[
            TaskEvalResult(
                task=RepairTask(
                    name="cookie_host_prefix_dict_value",
                    repo=tmp_path,
                    test_command="python -m pytest tests/test_policy.py",
                    split="test",
                ),
                baseline=None,
                ranked=plan,
            )
        ]
    )

    outcomes = write_candidate_outcomes(summary, tmp_path / "candidate_outcomes.jsonl")
    rows = [
        json.loads(line)
        for line in outcomes.read_text(encoding="utf-8").splitlines()
    ]
    preferred_features = _candidate_record_features(rows[0], rows[0]["failure_hints"])
    false_features = _candidate_record_features(rows[1], rows[1]["failure_hints"])

    assert rows[0]["failure_hints"][0]["assertions"] == [
        {
            "actual": "__Host",
            "operator": "==",
            "expected": "__Host-",
            "numeric_delta": None,
        }
    ]
    assert preferred_features["dict_value_scalar_assertion_delta_matches"] == 1.0
    assert (
        false_features["dict_value_scalar_assertion_delta_from_matches_actual_only"]
        == 1.0
    )
    assert "dict_value_scalar_assertion_delta_matches" not in false_features


def test_write_candidate_outcomes_preserves_swap_call_role_metadata(tmp_path) -> None:
    source = (
        "def normalize_scope(host, path):\n"
        "    return host, path\n\n"
        "def cookie_scope_key(host, path):\n"
        "    return normalize_scope(host, path)\n"
    )
    (tmp_path / "cookies.py").write_text(source, encoding="utf-8")
    candidate = CandidatePatch(
        file_path="cookies.py",
        action=PatchAction(
            kind=PatchActionKind.SWAP_CALL_ARG,
            target=PatchTarget(
                file_path="cookies.py",
                start_line=5,
                end_line=5,
                symbol="cookie_scope_key",
                node_kind="Call",
            ),
            params={"left": 0, "right": 1},
        ),
        edit=SourceEdit(
            start_line=5,
            start_col=11,
            end_line=5,
            end_col=38,
            replacement="normalize_scope(path, host)",
        ),
        original_source=source,
        patched_source=source.replace(
            "normalize_scope(host, path)",
            "normalize_scope(path, host)",
            1,
        ),
        reason="swap call arguments 0 and 1",
    )
    [candidate] = attach_target_context(tmp_path, [candidate])
    plan = PatchPlanResult(
        repo=tmp_path,
        test_command="pytest",
        baseline_exit_code=1,
        candidates_generated=1,
        candidates_tested=1,
        selected=None,
        applied=False,
        test_output="",
        tested_candidates=(candidate,),
        passing_candidates=(),
        first_passing_index=None,
    )
    summary = EvalSummary(
        tasks=[
            TaskEvalResult(
                task=RepairTask(
                    name="cookie_scope_include_path_keyword",
                    repo=tmp_path,
                    test_command="pytest",
                    split="test",
                ),
                baseline=None,
                ranked=plan,
            )
        ]
    )

    outcomes = write_candidate_outcomes(summary, tmp_path / "candidate_outcomes.jsonl")
    row = json.loads(outcomes.read_text(encoding="utf-8"))

    assert row["target_context"]["swap_call_breaks_name_alignment"] is True
    assert row["target_context"]["swap_call_name_alignment_before"] == "preserved"
    assert row["target_context"]["swap_call_name_alignment_after"] == "broken"


def test_candidate_outcomes_record_equivalent_candidate_metadata(tmp_path) -> None:
    first = _candidate_patch(to=2, ranker_score=1.0)
    equivalent = _candidate_patch(to=2, ranker_score=0.5)
    overlapping = _candidate_patch(to=3, ranker_score=0.25)
    plan = PatchPlanResult(
        repo=tmp_path,
        test_command="python -m pytest",
        baseline_exit_code=1,
        candidates_generated=3,
        candidates_tested=3,
        selected=first,
        applied=True,
        test_output="",
        tested_candidates=(first, equivalent, overlapping),
        first_passing_index=1,
        passing_candidates=(first, equivalent),
    )
    summary = EvalSummary(
        tasks=[
            TaskEvalResult(
                task=RepairTask(
                    name="equivalent_candidates",
                    repo=tmp_path,
                    test_command="python -m pytest",
                ),
                baseline=None,
                ranked=plan,
            )
        ]
    )

    outcomes = write_candidate_outcomes(summary, tmp_path / "candidate_outcomes.jsonl")
    rows = [
        json.loads(line)
        for line in outcomes.read_text(encoding="utf-8").splitlines()
    ]

    assert [row["passed"] for row in rows] == [True, True, False]
    assert [row["equivalent_candidate_ranks"] for row in rows] == [[2], [1], []]
    assert [row["equivalent_passing_candidate_ranks"] for row in rows] == [[2], [1], []]
    assert [row["overlapping_candidate_ranks"] for row in rows] == [[3], [3], [1, 2]]
    assert [row["overlapping_passing_candidate_ranks"] for row in rows] == [[], [], [1, 2]]
    assert [row["has_equivalent_passing_candidate"] for row in rows] == [True, True, False]


def _candidate_patch(*, to: int = 2, ranker_score: float | None) -> CandidatePatch:
    source = "def answer() -> int:\n    return 1\n"
    patched = f"def answer() -> int:\n    return {to}\n"
    return CandidatePatch(
        file_path="bug.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_LITERAL,
            target=PatchTarget(
                file_path="bug.py",
                start_line=2,
                end_line=2,
                symbol="answer",
                node_kind="Constant",
            ),
            params={"from": 1, "to": to},
        ),
        edit=SourceEdit(start_line=2, start_col=11, end_line=2, end_col=12, replacement=str(to)),
        original_source=source,
        patched_source=patched,
        reason=f"try nearby literal {to}",
        ranker_score=ranker_score,
    )


def _cookie_host_prefix_candidate(*, to: str) -> CandidatePatch:
    source = (
        "PREFIXES = {\n"
        "    'host': '__Host',\n"
        "    'secure': '__Secure-',\n"
        "}\n"
    )
    patched = source.replace("'host': '__Host'", f"'host': {to!r}")
    return CandidatePatch(
        file_path="webcookies/policy.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_DICT_VALUE,
            target=PatchTarget(
                file_path="webcookies/policy.py",
                start_line=2,
                end_line=2,
                symbol="PREFIXES",
                node_kind="Dict",
            ),
            params={"key": "host", "from": "__Host", "to": to},
        ),
        edit=SourceEdit(
            start_line=2,
            start_col=12,
            end_line=2,
            end_col=20,
            replacement=repr(to),
        ),
        original_source=source,
        patched_source=patched,
        reason=f"try dictionary value 'host'={to!r}",
        failure_hint_score=100.0,
    )


def _write_multi_pass_task(tmp_path) -> Path:
    repo = tmp_path / "multi_pass"
    tests = repo / "tests"
    tests.mkdir(parents=True)
    (repo / "bug.py").write_text(
        "def lucky() -> int:\n"
        "    return 10\n",
        encoding="utf-8",
    )
    (tests / "test_bug.py").write_text(
        "from bug import lucky\n\n"
        "def test_accepts_two_repairs() -> None:\n"
        "    assert 7 < lucky() < 10\n",
        encoding="utf-8",
    )
    (repo / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "name": "multi_pass_literal",
                    "repo": ".",
                    "test": "python -m pytest tests/test_bug.py -q",
                    "split": "validation",
                }
            ]
        ),
        encoding="utf-8",
    )
    return repo
