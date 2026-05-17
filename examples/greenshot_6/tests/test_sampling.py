from sampling.generate import decode_mode


def test_zero_temperature_forces_greedy_decoding() -> None:
    assert decode_mode(0.0, 0.9) == "greedy"
    assert decode_mode(0.7, 0.9) == "sample"
