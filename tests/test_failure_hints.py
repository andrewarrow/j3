from __future__ import annotations

from failure_hints import parse_pytest_failure_hints


def test_parse_pytest_assertion_hint() -> None:
    output = """
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_shipping_total_uses_expected_fee _____________________

    def test_shipping_total_uses_expected_fee() -> None:
>       assert shipping_total(20) == 25
E       assert 24 == 25
E        +  where 24 = shipping_total(20)

tests/test_bugs.py:13: AssertionError
=========================== short test summary info ============================
FAILED tests/test_bugs.py::test_shipping_total_uses_expected_fee - assert 24 ...
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.nodeid == "tests/test_bugs.py::test_shipping_total_uses_expected_fee"
    assert hint.function_names == {"shipping_total"}
    assert hint.assertions[0].actual == 24
    assert hint.assertions[0].expected == 25
    assert hint.assertions[0].numeric_delta == 1


def test_parse_pytest_exception_hint() -> None:
    output = """
    def test_average_empty_values_returns_zero() -> None:
>       assert average([]) == 0
               ^^^^^^^^^^^

tests/test_bugs.py:22:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

values = []

    def average(values: list[int]) -> float:
>       return sum(values) / len(values)
               ^^^^^^^^^^^^^^^^^^^^^^^^^
E       ZeroDivisionError: division by zero

bugs.py:20: ZeroDivisionError
=========================== short test summary info ============================
FAILED tests/test_bugs.py::test_average_empty_values_returns_zero - ZeroDivis...
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.nodeid == "tests/test_bugs.py::test_average_empty_values_returns_zero"
    assert hint.exception_type == "ZeroDivisionError"
    assert hint.function_names == {"average"}
    assert hint.source_files == {"bugs.py"}


def test_traceback_frame_context_does_not_become_exception_type() -> None:
    output = """
    def test_profile_heading_uses_name() -> None:
>       assert profile_heading({"name": None}) == "Ada"
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_shop.py:17:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

profile = {'name': None}

    def profile_heading(profile: dict[str, str]) -> str:
>       return profile["name"].upper()
               ^^^^^^^^^^^^^^^^^^^^^
E       TypeError: 'NoneType' object is not subscriptable

shop/api.py:20: in profile_heading
shop/api.py:20: TypeError
=========================== short test summary info ============================
FAILED tests/test_shop.py::test_profile_heading_uses_name - TypeError: 'None...
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.exception_type == "TypeError"
    assert {location.exception_type for location in hint.traceback_locations} == {None, "TypeError"}
    assert "in" not in {location.exception_type for location in hint.traceback_locations}
    assert "profile_heading" in hint.function_names
    assert hint.source_files == {"shop/api.py"}


def test_parse_name_and_attribute_error_details() -> None:
    output = """
    def file_extension(name: str) -> str:
>       return Path(name).suffix
               ^^^^
E       NameError: name 'Path' is not defined

bugs.py:13: NameError

    def invoice_total(invoice: Invoice) -> int:
>       return invoice.amount_cents
               ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'Invoice' object has no attribute 'amount_cents'

bugs.py:22: AttributeError
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.missing_names == {"Path"}
    assert hint.missing_attributes == {"amount_cents"}
    assert hint.exception_type == "NameError"


def test_parse_key_error_and_collection_assertion_diffs() -> None:
    output = """
    def test_payload() -> None:
>       assert payload["id"] == {"items": [1, 2]}
E       KeyError: 'id'
E       assert {'items': [1, 3]} == {'items': [1, 2]}
E       Differing items:
E       {'items': [1, 3]} != {'items': [1, 2]}
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.missing_keys == {"id"}
    assert hint.assertions[-1].actual == {"items": [1, 3]}
    assert hint.assertions[-1].expected == {"items": [1, 2]}
    assert hint.assertion_diff_lines


def test_parse_substring_assertion() -> None:
    output = """
    def test_message() -> None:
>       assert "ready" in message
E       assert 'ready' in 'not yet'
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.assertions[0].operator == "in"
    assert hint.assertions[0].actual == "ready"
    assert hint.assertions[0].expected == "not yet"


def test_parse_mypy_and_ruff_output() -> None:
    output = """
bugs.py:12: error: Name "subtotal" is not defined  [name-defined]
bugs.py:14:8: F821 Undefined name `Counter`
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.tool_diagnostics[0].tool == "mypy"
    assert hint.tool_diagnostics[0].code == "name-defined"
    assert hint.tool_diagnostics[1].tool == "ruff"
    assert hint.tool_diagnostics[1].code == "F821"
    assert hint.missing_names == {"Counter"}


def test_parse_pytest_warning_match_string() -> None:
    output = """
    def test_config_warns() -> None:
>       with pytest.warns(UserWarning, match="Defaulting to `validation_fraction=0.05`"):
E       Failed: DID NOT WARN. No warnings of type (<class 'UserWarning'>,) were emitted.
"""

    [hint] = parse_pytest_failure_hints(output)

    assert hint.expected_strings == {"Defaulting to `validation_fraction=0.05`"}
