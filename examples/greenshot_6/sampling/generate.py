def decode_mode(temperature: float, top_p: float) -> str:
    if temperature > 0.0 or top_p > 0.0:
        return "sample"
    return "greedy"
