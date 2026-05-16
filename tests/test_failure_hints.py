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
