from taskqueue import unknown_task_header_detail


def test_unknown_task_header_detail_spells_the() -> None:
    assert unknown_task_header_detail() == "The full contents of the message headers:"
