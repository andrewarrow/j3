from bugs import Invoice, display_name, file_extension, invoice_total, parse_quantity


def test_display_name_uses_first_then_last() -> None:
    assert display_name("Ada", "Lovelace") == "Ada Lovelace"


def test_file_extension_uses_pathlib() -> None:
    assert file_extension("archive.tar.gz") == ".gz"


def test_invoice_total_uses_existing_attribute() -> None:
    assert invoice_total(Invoice(total_cents=1250)) == 1250


def test_parse_quantity_returns_zero_for_invalid_input() -> None:
    assert parse_quantity("12") == 12
    assert parse_quantity("n/a") == 0
