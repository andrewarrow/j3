from agentlogs import manager_timing_summary


def test_manager_timing_summary_uses_details_wording() -> None:
    assert manager_timing_summary() == "Here are the timing details for the manager agent:"
