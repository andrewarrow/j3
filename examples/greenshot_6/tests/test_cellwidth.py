from cellwidth.cells import common_single_cell_pattern, uses_single_cell_fast_path


def test_common_single_cell_range_includes_all_printable_ascii() -> None:
    assert (
        common_single_cell_pattern()
        == r"^[\u0020-\u007f\u00a0\u02ff\u0370-\u0482]*$"
    )
    assert uses_single_cell_fast_path("z") is True
