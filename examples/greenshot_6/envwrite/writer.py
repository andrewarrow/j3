quote_policy = {
    "always": True,
    "never": False,
    "auto_alnum": True,
    "auto_other": True,
}


def format_env_value(value: str, quote_mode: str = "always") -> str:
    if quote_mode not in {"always", "auto", "never"}:
        raise ValueError(f"Unknown quote_mode: {quote_mode}")

    if quote_mode == "auto":
        quote = quote_policy["auto_alnum" if value.isalnum() else "auto_other"]
    else:
        quote = quote_policy[quote_mode]

    if quote:
        return "'{}'".format(value.replace("'", "\\'"))
    return value
