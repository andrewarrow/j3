from __future__ import annotations

import json
import shutil

from patching import PatchRankingModel, generate_candidate_patches, plan_and_maybe_apply_patch, rank_candidate_patches
from training import train_from_path


def test_patch_finds_discount_fix_without_modifying_in_dry_run(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.applied is False
    assert "price * (1 - percent / 100)" in result.selected.patched_source
    assert "return price * (percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_patch_applies_discount_fix(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=False,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.applied is True
    assert "return price * (1 - percent / 100)" in (repo / "calculator.py").read_text(encoding="utf-8")


def test_patch_uses_model_to_rank_candidates(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)
    training = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=20,
    )
    model = PatchRankingModel.load(training.model_path)

    ranked = rank_candidate_patches(generate_candidate_patches(repo), model)

    assert ranked
    assert ranked[0].model_score is not None


def test_patch_ranking_uses_mined_git_transition_exemplars(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    before = "def discount(price, percent):\n    return price * (percent / 100)\n"
    after = "def discount(price, percent):\n    return price * (1 - percent / 100)\n"
    (repo / "calculator.py").write_text(before, encoding="utf-8")
    transitions = tmp_path / "transitions.jsonl"
    transitions.write_text(
        json.dumps(
            {
                "kind": "git_transition",
                "repo": "demo",
                "commit": "b",
                "parent": "a",
                "file_path": "calculator.py",
                "before_source": before,
                "after_source": after,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    training = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=20,
        transition_paths=[transitions],
    )
    model = PatchRankingModel.load(training.model_path)

    ranked = rank_candidate_patches(generate_candidate_patches(repo), model)

    assert ranked[0].patched_source == after
    assert ranked[0].model_score is not None


def test_patch_accepts_model_path(tmp_path) -> None:
    repo = tmp_path / "greenshot_bug"
    shutil.copytree("examples/greenshot_bug", repo)
    training = train_from_path(
        data_path=repo,
        out_dir=tmp_path / "run",
        embedding_dim=32,
        max_examples=20,
    )

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_calculator.py",
        dry_run=True,
        timeout_seconds=10,
        model_path=training.model_path,
    )

    assert result.model_path == training.model_path.resolve()
    assert result.selected is not None
    assert result.selected.model_score is not None


def test_patch_uses_pytest_failure_hints_to_prioritize_literal_fix(tmp_path) -> None:
    repo = tmp_path / "greenshot_bugs"
    shutil.copytree("examples/greenshot_bugs", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_bugs.py::test_shipping_total_uses_expected_fee",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.action.target.symbol == "shipping_total"
    assert result.selected.action.params["to"] == 5
    assert result.selected.failure_hint_score > 0


def test_patch_handles_greenshot_3_actions(tmp_path) -> None:
    repo = tmp_path / "greenshot_3"
    shutil.copytree("examples/greenshot_3", repo)
    cases = [
        (
            "python -m pytest tests/test_bugs.py::test_display_name_uses_first_then_last",
            "swap_call_arg",
        ),
        (
            "python -m pytest tests/test_bugs.py::test_file_extension_uses_pathlib",
            "add_import",
        ),
        (
            "python -m pytest tests/test_bugs.py::test_invoice_total_uses_existing_attribute",
            "change_attribute",
        ),
        (
            "python -m pytest tests/test_bugs.py::test_parse_quantity_returns_zero_for_invalid_input",
            "wrap_try_except",
        ),
    ]

    for test_command, action in cases:
        result = plan_and_maybe_apply_patch(
            repo=repo,
            test_command=test_command,
            dry_run=True,
            timeout_seconds=10,
        )

        assert result.selected is not None
        assert result.candidates_tested == 1
        assert result.selected.action.kind.value == action


def test_generate_rename_symbol_candidate_for_unknown_local(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "def total_price(subtotal: int, tax: int) -> int:\n"
        "    return subtotla + tax\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "rename_symbol"
        and candidate.action.params == {"from": "subtotla", "to": "subtotal"}
        for candidate in candidates
    )


def test_generate_modify_condition_candidates_for_if_tests(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "def is_ready(enabled: bool) -> bool:\n"
        "    if not enabled:\n"
        "        return True\n"
        "    return False\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "modify_condition"
        and candidate.action.params["operation"] == "remove_not"
        and "if enabled:" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_signature_and_call_site_propagation_candidates(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "def greet(first: str) -> str:\n"
        "    return first.upper()\n\n"
        "def render() -> str:\n"
        "    return greet(name='Ada')\n\n"
        "def label(value: str) -> str:\n"
        "    return value\n\n"
        "def render_label() -> str:\n"
        "    return label(vlaue='x')\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "propagate_signature"
        and "def greet(name: str) -> str:" in candidate.patched_source
        and "return name.upper()" in candidate.patched_source
        for candidate in candidates
    )
    assert any(
        candidate.action.kind.value == "rename_symbol"
        and "label(value='x')" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_cross_module_signature_propagation_from_imported_keyword(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    package = repo / "shop"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "profiles.py").write_text(
        "def user_badge_label(name: str) -> str:\n"
        "    return f'@{name.lower()}'\n",
        encoding="utf-8",
    )
    (package / "api.py").write_text(
        "from .profiles import user_badge_label\n\n"
        "def profile_badge(username: str) -> str:\n"
        "    return user_badge_label(username=username)\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.file_path == "shop/profiles.py"
        and candidate.action.kind.value == "propagate_signature"
        and candidate.action.params == {"from": "name", "to": "username"}
        and "def user_badge_label(username: str) -> str:" in candidate.patched_source
        and "return f'@{username.lower()}'" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_missing_keyword_argument_passthrough_candidate(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    package = repo / "shop"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "shipping.py").write_text(
        "def shipping_timeout_label(timeout_seconds: int = 5) -> str:\n"
        "    return 'extended' if timeout_seconds >= 30 else 'standard'\n",
        encoding="utf-8",
    )
    (package / "api.py").write_text(
        "from .shipping import shipping_timeout_label\n\n"
        "def carrier_timeout_label(timeout_seconds: int = 30) -> str:\n"
        "    return shipping_timeout_label()\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.file_path == "shop/api.py"
        and candidate.action.kind.value == "add_keyword_arg"
        and candidate.action.params == {
            "keyword": "timeout_seconds",
            "value": "timeout_seconds",
            "callee": "shipping_timeout_label",
        }
        and "shipping_timeout_label(timeout_seconds=timeout_seconds)" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_missing_boolean_default_keyword_candidate(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    package = repo / "webcookies"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "policy.py").write_text(
        "def normalize_scope(host: str, path: str, include_path: bool = False) -> str:\n"
        "    if include_path:\n"
        "        return f'{host}{path}'\n"
        "    return host\n\n"
        "def cookie_scope_key(host: str, path: str) -> str:\n"
        "    return normalize_scope(host, path)\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.file_path == "webcookies/policy.py"
        and candidate.action.kind.value == "add_keyword_arg"
        and candidate.action.params == {
            "keyword": "include_path",
            "value": True,
            "callee": "normalize_scope",
        }
        and "normalize_scope(host, path, include_path=True)" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_fallback_warning_candidate_for_missing_setting(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.py").write_text(
        "from dataclasses import dataclass\n"
        "from pathlib import Path\n\n"
        "@dataclass\n"
        "class TrainingDataConfig:\n"
        "    data_path: Path\n"
        "    validation_fraction: float | None = None\n\n"
        "    def __post_init__(self) -> None:\n"
        "        if self.data_path.is_file() and self.validation_fraction is None:\n"
        "            raise ValueError('validation_fraction must be set')\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "add_fallback_warning"
        and candidate.action.params == {
            "attribute": "validation_fraction",
            "value": 0.05,
            "exception": "ValueError",
        }
        and "import warnings" in candidate.patched_source
        and "self.validation_fraction = 0.05" in candidate.patched_source
        and "warnings.warn(" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_state_flag_guard_candidate_for_duplicate_side_effects(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "startup.py").write_text(
        "startup_events: list[str] = []\n"
        "_startup_hooks_started = False\n\n"
        "\n"
        "def start_startup_hooks() -> list[str]:\n"
        "    startup_events.append('cart_loaded')\n"
        "    startup_events.append('payment_ready')\n"
        "    return startup_events\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "insert_guard"
        and candidate.action.params == {
            "condition": "_startup_hooks_started",
            "state_flag": "_startup_hooks_started",
            "return": "startup_events",
        }
        and "global _startup_hooks_started" in candidate.patched_source
        and "if _startup_hooks_started:" in candidate.patched_source
        and "return startup_events" in candidate.patched_source
        and "_startup_hooks_started = True" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_subscript_key_candidate_from_repo_string_literals(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "def customer_display_name(order: dict[str, str]) -> str:\n"
        "    return order['name'].title()\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_bug.py").write_text(
        "from bug import customer_display_name\n\n"
        "def test_customer_name() -> None:\n"
        "    assert customer_display_name({'customer_name': 'ada'}) == 'Ada'\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_subscript_key"
        and candidate.action.params == {"from": "name", "to": "customer_name"}
        and "order['customer_name'].title()" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_add_dict_key_candidate_from_repo_string_literals(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "def widget_payload(label: str) -> dict[str, object]:\n"
        "    return {\n"
        "        'label': label,\n"
        "        'enabled': True\n"
        "    }\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_bug.py").write_text(
        "from bug import widget_payload\n\n"
        "def test_widget_payload() -> None:\n"
        "    payload = widget_payload('Pay')\n"
        "    assert payload['disabled'] is False\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "add_dict_key"
        and candidate.action.params == {"key": "disabled", "value": False}
        and "'enabled': True," in candidate.patched_source
        and "'disabled': False," in candidate.patched_source
        for candidate in candidates
    )


def test_generate_change_dict_key_candidate_from_repo_string_literals(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "def step_metadata(icon: str) -> dict[str, object]:\n"
        "    return {\n"
        "        'label': 'checkout',\n"
        "        'icon': icon,\n"
        "    }\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_bug.py").write_text(
        "from bug import step_metadata\n\n"
        "def test_step_metadata() -> None:\n"
        "    metadata = step_metadata('card')\n"
        "    assert metadata['metadata_icon'] == 'card'\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_dict_key"
        and candidate.action.params == {"from": "icon", "to": "metadata_icon"}
        and "'metadata_icon': icon" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_same_mapping_boolean_value_with_key_rename_decoy(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "policy.py").write_text(
        "def default_partitioned_cookie_attributes() -> dict[str, bool]:\n"
        "    return {\n"
        "        'partitioned': False,\n"
        "        '__Partitioned-': False,\n"
        "    }\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_policy.py").write_text(
        "from policy import default_partitioned_cookie_attributes\n\n"
        "def test_partitioned_default() -> None:\n"
        "    attributes = default_partitioned_cookie_attributes()\n"
        "    assert attributes['partitioned'] is True\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_dict_value"
        and candidate.action.params == {"key": "partitioned", "from": False, "to": True}
        for candidate in candidates
    )
    assert any(
        candidate.action.kind.value == "change_dict_key"
        and candidate.action.params == {"from": "partitioned", "to": "__Partitioned-"}
        for candidate in candidates
    )


def test_generate_change_dict_value_candidate_from_repo_string_literals(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "metadata.py").write_text(
        "def default_project_metadata() -> dict[str, str]:\n"
        "    return {\n"
        "        'metadata_version': '2.2',\n"
        "        'name': 'demo',\n"
        "    }\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_metadata.py").write_text(
        "from metadata import default_project_metadata\n\n"
        "def test_metadata_version() -> None:\n"
        "    expected_metadata_version = '2.3'\n"
        "    assert default_project_metadata()['metadata_version'] == expected_metadata_version\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_dict_value"
        and candidate.action.params == {
            "key": "metadata_version",
            "from": "2.2",
            "to": "2.3",
        }
        and "'metadata_version': '2.3'" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_change_dict_value_candidate_for_structured_string_prefix(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "metadata.py").write_text(
        "def readme_content_type(readme_format: str) -> str:\n"
        "    content_types = {\n"
        "        'markdown': 'text/plain',\n"
        "        'rst': 'text/x-rst',\n"
        "    }\n"
        "    return content_types[readme_format]\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_metadata.py").write_text(
        "from metadata import readme_content_type\n\n"
        "def test_readme_content_type() -> None:\n"
        "    assert readme_content_type('markdown') == 'text/markdown'\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_dict_value"
        and candidate.action.params == {
            "key": "markdown",
            "from": "text/plain",
            "to": "text/markdown",
        }
        and "'markdown': 'text/markdown'" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_string_literal_candidate_from_repo_string_literals(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text(
        "VALID_MODE = 'priority'\n\n"
        "def choose_mode(mode: str) -> str:\n"
        "    return mode\n\n"
        "def shipping_label() -> str:\n"
        "    return choose_mode('priorty')\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_literal"
        and candidate.action.params == {"from": "priorty", "to": "priority"}
        and "choose_mode('priority')" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_fstring_fragment_literal_candidate_from_concrete_message(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "metadata.py").write_text(
        "class MetadataValidationError(ValueError):\n"
        "    pass\n\n"
        "def validate_dynamic_field(field: str, project: dict[str, object]) -> None:\n"
        "    if field in project:\n"
        "        raise MetadataValidationError(\n"
        "            f'Field \"project.{field}\" declared as dynamic in but is defined',\n"
        "        )\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_metadata.py").write_text(
        "import pytest\n"
        "from metadata import MetadataValidationError, validate_dynamic_field\n\n"
        "def test_dynamic_field_error() -> None:\n"
        "    with pytest.raises(\n"
        "        MetadataValidationError,\n"
        "        match='Field \"project.version\" declared as dynamic in \"project.dynamic\" but is defined',\n"
        "    ):\n"
        "        validate_dynamic_field('version', {'version': '1.0.0'})\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate.action.kind.value == "change_literal"
            and candidate.action.params
            == {
                "from": " declared as dynamic in but is defined",
                "to": ' declared as dynamic in "project.dynamic" but is defined',
            }
        ),
        None,
    )
    assert candidate is not None
    assert (
        'f\'Field "project.{field}" declared as dynamic in "project.dynamic" but is defined\''
        in candidate.patched_source
    )


def test_patch_solves_click_invalid_directory_filename_repr(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_cliformat.py::test_invalid_directory_message_escapes_newline_in_filename",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "cliformat/types.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "{name} '{filename}' is a directory.",
        "to": "{name} {filename!r} is a directory.",
    }
    assert "'{name} {filename!r} is a directory.'" in result.selected.patched_source


def test_patch_solves_litgpt_zero_temperature_greedy_condition(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_sampling.py::test_zero_temperature_forces_greedy_decoding",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "sampling/generate.py"
    assert result.selected.action.kind.value == "modify_condition"
    assert result.selected.action.params == {
        "operation": "change_bool_operator",
        "from": "or",
        "to": "and",
    }
    assert "temperature > 0.0 and top_p > 0.0" in result.selected.patched_source


def test_patch_solves_dateutil_lowercase_z_utc_suffix(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_dateparse.py::test_lowercase_z_is_accepted_as_utc_suffix",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "dateparse/isoparse.py"
    assert result.selected.action.kind.value == "change_module_constant"
    assert result.selected.action.params == {
        "name": "UTC_ZONE_NAMES",
        "from": "UTC GMT Z",
        "to": "UTC GMT Z z",
    }
    assert "UTC_ZONE_NAMES = 'UTC GMT Z z'" in result.selected.patched_source


def test_patch_solves_tornado_header_newline_forbidden_regex(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_headers.py::test_newline_is_rejected_in_header_value",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "headers/validation.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]",
        "to": r"[\x00-\x08\x0A-\x1F\x7F]",
    }
    assert "return '[\\\\x00-\\\\x08\\\\x0A-\\\\x1F\\\\x7F]'" in result.selected.patched_source


def test_patch_solves_humanize_gnu_ronna_suffix(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_filesize.py::test_gnu_filesize_supports_ronna_prefix",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "filesize/format.py"
    assert result.selected.action.kind.value == "change_dict_value"
    assert result.selected.action.params == {
        "key": "gnu",
        "from": "KMGTPEZY",
        "to": "KMGTPEZYRQ",
    }
    assert '"gnu": "KMGTPEZYRQ"' in result.selected.patched_source


def test_patch_solves_packaging_pyemscripten_platform_config_var(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_platformtags.py::test_pyemscripten_platform_version_uses_platform_config_var"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "platformtags/tags.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "PYEMSCRIPTEN_ABI_VERSION",
        "to": "PYEMSCRIPTEN_PLATFORM_VERSION",
    }
    assert "get_config_var('PYEMSCRIPTEN_PLATFORM_VERSION')" in result.selected.patched_source


def test_patch_solves_yfinance_market_data_error_typo(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_marketdata.py::test_market_data_error_spells_received",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "marketdata/market.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": ": Failed to retrieve market data and recieved faulty data.",
        "to": ": Failed to retrieve market data and received faulty data.",
    }
    assert "received faulty data" in result.selected.patched_source


def test_patch_solves_urllib3_getheader_warning_typo(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_httpresponse.py::test_getheader_deprecation_warning_names_httpresponse"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "httpresponse/response.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "HTTResponse.headers.get(name, default)",
        "to": "HTTPResponse.headers.get(name, default)",
    }
    assert "HTTPResponse.headers.get(name, default)" in result.selected.patched_source


def test_patch_solves_httpx_async_client_sync_request_article(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_httpclient.py::test_async_client_sync_request_error_message_uses_a"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "httpclient/client.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "Attempted to send an sync request with an AsyncClient instance.",
        "to": "Attempted to send a sync request with an AsyncClient instance.",
    }
    assert "Attempted to send a sync request" in result.selected.patched_source


def test_patch_solves_prettytable_missing_attribute_quote(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_tablefmt.py::test_unknown_legacy_symbol_error_closes_attribute_quote"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "tablefmt/legacy.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "module 'tablefmt.legacy' has no attribute '{name}",
        "to": "module 'tablefmt.legacy' has no attribute '{name}'",
    }
    assert "has no attribute '{name}'" in result.selected.patched_source


def test_patch_solves_rich_common_cell_width_ascii_range(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_cellwidth.py::test_common_single_cell_range_includes_all_printable_ascii"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "cellwidth/cells.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": r"^[\u0020-\u006f\u00a0\u02ff\u0370-\u0482]*$",
        "to": r"^[\u0020-\u007f\u00a0\u02ff\u0370-\u0482]*$",
    }
    assert r"\u007f" in result.selected.patched_source


def test_patch_solves_pydantic_field_regex_pattern_message(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_fieldopts.py::test_regex_keyword_error_points_to_pattern_parameter"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "fieldopts/fields.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "`regex` is removed. use `Pattern` instead",
        "to": "`regex` is removed. use `pattern` instead",
    }
    assert "use `pattern` instead" in result.selected.patched_source


def test_patch_solves_pip_list_outdated_freeze_error_message(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_piplist.py::test_outdated_freeze_format_error_matches_pip_message"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "piplist/listing.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "List format 'freeze' can not be used with the --outdated option.",
        "to": "List format 'freeze' cannot be used together with the --outdated option.",
    }
    assert "cannot be used together" in result.selected.patched_source


def test_patch_solves_chalice_control_plane_programmatically_docstring(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command=(
            "python -m pytest "
            "tests/test_apidocs.py::test_control_plane_description_spells_programmatically"
        ),
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "apidocs/api.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {
        "from": "Control plane APIs for programatically building/deploying Chalice apps.",
        "to": "Control plane APIs for programmatically building/deploying Chalice apps.",
    }
    assert "programmatically building/deploying" in result.selected.patched_source


def test_generate_membership_operator_with_literal_needle_decoy(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "policy.py").write_text(
        "def parse_request_cache_control(header: str) -> dict[str, bool]:\n"
        "    return {'no_cache': 'no-cache' in header}\n\n"
        "def should_revalidate_response(headers: dict[str, str]) -> bool:\n"
        "    cache_control = headers.get('cache-control', '').lower()\n"
        "    if 'no-cache' not in cache_control:\n"
        "        return False\n"
        "    return 'etag' in headers\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_policy.py").write_text(
        "from policy import should_revalidate_response\n\n"
        "def test_no_cache_revalidates() -> None:\n"
        "    assert should_revalidate_response({'cache-control': 'no-cache', 'etag': 'abc123'}) is False\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_operator"
        and candidate.action.target.symbol == "should_revalidate_response"
        and candidate.action.params == {"from": "not in", "to": "in"}
        and "'no-cache' in cache_control" in candidate.patched_source
        for candidate in candidates
    )
    assert any(
        candidate.action.kind.value == "change_literal"
        and candidate.action.target.symbol == "should_revalidate_response"
        and candidate.action.params == {"from": "no-cache", "to": "no_cache"}
        and "'no_cache' not in cache_control" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_membership_operator_with_failing_literal_needle_decoy(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "policy.py").write_text(
        "def parse_request_cache_control(header: str) -> dict[str, bool]:\n"
        "    return {'must_revalidate': 'must-revalidate' in header}\n\n"
        "def should_serve_stale_response(headers: dict[str, str]) -> bool:\n"
        "    cache_control = headers.get('cache-control', '').lower()\n"
        "    if 'must-revalidate' not in cache_control:\n"
        "        return False\n"
        "    return True\n",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_policy.py").write_text(
        "from policy import should_serve_stale_response\n\n"
        "def test_stale_allowed_without_must_revalidate() -> None:\n"
        "    assert should_serve_stale_response({'cache-control': 'public, max-age=60', 'etag': 'abc123'}) is True\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_operator"
        and candidate.action.target.symbol == "should_serve_stale_response"
        and candidate.action.params == {"from": "not in", "to": "in"}
        and "'must-revalidate' in cache_control" in candidate.patched_source
        for candidate in candidates
    )
    literal_decoy = next(
        candidate
        for candidate in candidates
        if candidate.action.kind.value == "change_literal"
        and candidate.action.target.symbol == "should_serve_stale_response"
        and candidate.action.params == {"from": "must-revalidate", "to": "must_revalidate"}
    )
    assert "'must_revalidate' not in cache_control" in literal_decoy.patched_source


def test_generate_module_constant_candidate(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "settings.py").write_text(
        "DEFAULT_BATCH_SIZE = 99\n\n"
        "def batch_size() -> int:\n"
        "    return DEFAULT_BATCH_SIZE\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.action.kind.value == "change_module_constant"
        and candidate.action.params == {
            "name": "DEFAULT_BATCH_SIZE",
            "from": 99,
            "to": 100,
        }
        and "DEFAULT_BATCH_SIZE = 100" in candidate.patched_source
        for candidate in candidates
    )


def test_generate_local_import_candidates_with_decoy(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    package = repo / "shop"
    package.mkdir()
    reports = package / "reports"
    reports.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (reports / "__init__.py").write_text("", encoding="utf-8")
    (package / "money.py").write_text(
        "def format_receipt_total(total_cents: int) -> str:\n"
        "    return f'{total_cents} cents'\n",
        encoding="utf-8",
    )
    (reports / "money.py").write_text(
        "def format_receipt_total(total_cents: int) -> str:\n"
        "    return f'${total_cents / 100:.2f}'\n",
        encoding="utf-8",
    )
    (reports / "summary.py").write_text(
        "def receipt_total_label(total_cents: int) -> str:\n"
        "    return format_receipt_total(total_cents)\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)
    imports = {
        candidate.action.params["import"]
        for candidate in candidates
        if candidate.file_path == "shop/reports/summary.py"
        and candidate.action.kind.value == "add_import"
    }

    assert "from shop.money import format_receipt_total" in imports
    assert "from shop.reports.money import format_receipt_total" in imports


def test_generate_import_compatibility_fallback_candidate(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    package = repo / "shop"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cache_legacy.py").write_text(
        "class CacheBackend:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (package / "cache.py").write_text(
        "def cache_backend_label() -> str:\n"
        "    from shop.cache_v2 import CacheBackend\n"
        "    return CacheBackend().__class__.__name__\n",
        encoding="utf-8",
    )

    candidates = generate_candidate_patches(repo)

    assert any(
        candidate.file_path == "shop/cache.py"
        and candidate.action.kind.value == "add_import_fallback"
        and candidate.action.params["name"] == "CacheBackend"
        and candidate.action.params["primary_module"] == "shop.cache_v2"
        and candidate.action.params["fallback_module"] == "shop.cache_legacy"
        and "try:" in candidate.patched_source
        and "from shop.cache_v2 import CacheBackend" in candidate.patched_source
        and "except ImportError:" in candidate.patched_source
        and "from shop.cache_legacy import CacheBackend" in candidate.patched_source
        for candidate in candidates
    )


def test_patch_uses_key_error_hints_to_prioritize_subscript_key_fix(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_order_customer_label_uses_customer_name_key",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.action.kind.value == "change_subscript_key"
    assert result.selected.action.params == {"from": "name", "to": "customer_name"}
    assert result.selected.failure_hint_score > 0


def test_patch_solves_cross_module_swapped_arguments(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_balance_after_store_credit_passes_arguments_to_helper",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/api.py"
    assert result.selected.action.kind.value == "swap_call_arg"
    assert result.selected.action.params == {"left": 0, "right": 1}
    assert "total_after_store_credit(total_cents, credit_cents)" in result.selected.patched_source


def test_patch_solves_helper_module_default_value(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_return_window_uses_policy_default",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/policies.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {"from": 13, "to": 14}


def test_patch_solves_module_level_config_constant(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_free_shipping_threshold_uses_module_constant",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/shipping.py"
    assert result.selected.action.kind.value == "change_module_constant"
    assert result.selected.action.params == {
        "name": "FREE_SHIPPING_MINIMUM_CENTS",
        "from": 4999,
        "to": 5000,
    }


def test_patch_solves_public_api_signature_propagation(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_profile_badge_propagates_public_api_username",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/profiles.py"
    assert result.selected.action.kind.value == "propagate_signature"
    assert result.selected.action.params == {"from": "name", "to": "username"}
    assert "def user_badge_label(username: str) -> str:" in result.selected.patched_source


def test_patch_solves_nested_module_missing_import_with_decoy(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_receipt_label_imports_nested_report_formatter",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.selected.file_path == "shop/reports/summary.py"
    assert result.selected.action.kind.value == "add_import"
    assert result.selected.action.params == {
        "name": "format_receipt_total",
        "module": "shop.reports.money",
        "import": "from shop.reports.money import format_receipt_total",
    }
    assert any(
        candidate.action.params.get("module") == "shop.money"
        for candidate in result.tested_candidates
    )


def test_patch_solves_string_mode_literal_in_caller_not_helper(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_priority_shipping_mode_literal_is_fixed_in_caller",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/api.py"
    assert result.selected.action.kind.value == "change_literal"
    assert result.selected.action.params == {"from": "priorty", "to": "priority"}


def test_patch_solves_revealed_failure_with_bounded_second_step(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_multi_step_delivery_summary_reveals_literal_after_import",
        dry_run=False,
        timeout_seconds=10,
        max_steps=2,
    )

    assert result.selected is not None
    assert result.applied is True
    assert len(result.selected_candidates) == 2
    assert [candidate.action.kind.value for candidate in result.selected_candidates] == [
        "add_import",
        "change_literal",
    ]
    assert result.selected_candidates[0].file_path == "shop/api.py"
    assert result.selected_candidates[0].action.params == {
        "name": "delivery_speed_label",
        "module": "shop.shipping",
        "import": "from shop.shipping import delivery_speed_label",
    }
    assert result.selected.file_path == "shop/api.py"
    assert result.selected.action.params == {"from": "expres", "to": "express"}
    patched_api = (repo / "shop/api.py").read_text(encoding="utf-8")
    assert "from shop.shipping import delivery_speed_label" in patched_api
    assert "return delivery_speed_label('express')" in patched_api


def test_patch_solves_missing_dictionary_output_key(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_checkout_widget_payload_includes_disabled_key",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/widgets.py"
    assert result.selected.action.kind.value == "add_dict_key"
    assert result.selected.action.params == {"key": "disabled", "value": False}
    assert '"disabled": False,' in result.selected.patched_source


def test_patch_solves_dictionary_literal_key_change(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_checkout_step_metadata_uses_metadata_icon_key",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/widgets.py"
    assert result.selected.action.kind.value == "change_dict_key"
    assert result.selected.action.params == {"from": "icon", "to": "metadata_icon"}
    assert '"metadata_icon": icon,' in result.selected.patched_source


def test_patch_solves_missing_keyword_argument_passthrough(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_carrier_timeout_label_passes_timeout_keyword",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/api.py"
    assert result.selected.action.kind.value == "add_keyword_arg"
    assert result.selected.action.params == {
        "keyword": "timeout_seconds",
        "value": "timeout_seconds",
        "callee": "shipping_timeout_label",
    }
    assert "shipping_timeout_label(timeout_seconds=timeout_seconds)" in result.selected.patched_source


def test_patch_solves_cookie_scope_include_path_keyword(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_webcookies.py::test_cookie_scope_key_includes_path_when_requested",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "webcookies/policy.py"
    assert result.selected.action.kind.value == "add_keyword_arg"
    assert result.selected.action.params == {
        "keyword": "include_path",
        "value": True,
        "callee": "normalize_scope",
    }
    assert "normalize_scope(host, path, include_path=True)" in result.selected.patched_source


def test_patch_solves_missing_setting_with_default_warning(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_training_data_file_defaults_validation_fraction_with_warning",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/data.py"
    assert result.selected.action.kind.value == "add_fallback_warning"
    assert result.selected.action.params == {
        "attribute": "validation_fraction",
        "value": 0.05,
        "exception": "ValueError",
    }
    assert "import warnings" in result.selected.patched_source
    assert "self.validation_fraction = 0.05" in result.selected.patched_source
    assert "warnings.warn(" in result.selected.patched_source


def test_patch_solves_duplicate_side_effects_with_state_flag_guard(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_checkout_startup_hooks_are_idempotent",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/startup.py"
    assert result.selected.action.kind.value == "insert_guard"
    assert result.selected.action.params == {
        "condition": "_checkout_hooks_started",
        "state_flag": "_checkout_hooks_started",
        "return": "checkout_start_events",
    }
    assert "global _checkout_hooks_started" in result.selected.patched_source
    assert "_checkout_hooks_started = True" in result.selected.patched_source


def test_patch_solves_import_compatibility_fallback(tmp_path) -> None:
    repo = tmp_path / "greenshot_5"
    shutil.copytree("examples/greenshot_5", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_shop.py::test_cache_backend_import_falls_back_to_legacy_path",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "shop/cache.py"
    assert result.selected.action.kind.value == "add_import_fallback"
    assert result.selected.action.params["name"] == "CacheBackend"
    assert result.selected.action.params["primary_module"] == "shop.cache_v2"
    assert result.selected.action.params["fallback_module"] == "shop.cache_legacy"
    assert "except ImportError:" in result.selected.patched_source


def test_patch_solves_greenshot_6_dictionary_literal_value(tmp_path) -> None:
    repo = tmp_path / "greenshot_6"
    shutil.copytree("examples/greenshot_6", repo)

    result = plan_and_maybe_apply_patch(
        repo=repo,
        test_command="python -m pytest tests/test_pkgmeta.py::test_core_metadata_uses_current_metadata_version",
        dry_run=True,
        timeout_seconds=10,
    )

    assert result.selected is not None
    assert result.candidates_tested == 1
    assert result.selected.file_path == "pkgmeta/metadata.py"
    assert result.selected.action.kind.value == "change_dict_value"
    assert result.selected.action.params == {
        "key": "metadata_version",
        "from": "2.2",
        "to": "2.3",
    }
    assert '"metadata_version": "2.3"' in result.selected.patched_source
