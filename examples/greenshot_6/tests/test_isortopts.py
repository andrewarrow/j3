from isortopts import option_description


EXPECTED_DESCRIPTION = "apply headings to indented imports"


def test_indented_import_headings_description_is_spelled_correctly() -> None:
    assert option_description("indented_import_headings") == EXPECTED_DESCRIPTION
