from __future__ import annotations


def create_logger(app_name: str) -> str:
    return f"logger:{app_name}"


def create_logger_description() -> str:
    return "Get the the Flask apps's logger and configure it if needed."
