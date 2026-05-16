from dataclasses import dataclass


def format_name(first: str, last: str) -> str:
    return f"{first} {last}"


def display_name(first: str, last: str) -> str:
    return format_name(last, first)


def file_extension(name: str) -> str:
    return Path(name).suffix


@dataclass
class Invoice:
    total_cents: int


def invoice_total(invoice: Invoice) -> int:
    return invoice.amount_cents


def parse_quantity(value: str) -> int:
    return int(value)
