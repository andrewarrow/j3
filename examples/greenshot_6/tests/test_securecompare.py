from securecompare import constant_time_compare_note


def test_constant_time_compare_note_spells_comparison() -> None:
    assert constant_time_compare_note() == (
        "Do not use for comparison with known length targets."
    )
