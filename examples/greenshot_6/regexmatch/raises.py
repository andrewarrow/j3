from __future__ import annotations


FAILURE_PREFIX = "Regex pattern did not match."


def regex_match_failure_message(pattern: str, message: str) -> str:
    regex_label = "Regex"
    message_label = "Actual message"
    return (
        f"{FAILURE_PREFIX}\n"
        f"  {regex_label}: {pattern!r}\n"
        f"  {message_label}: {message!r}"
    )
