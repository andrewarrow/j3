from marketdata.market import market_data_error


def test_market_data_error_spells_received() -> None:
    assert (
        market_data_error("NYSE")
        == "NYSE: Failed to retrieve market data and received faulty data."
    )
