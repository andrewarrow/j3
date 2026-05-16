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
