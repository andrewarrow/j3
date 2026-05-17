from requestdocs import request_parameter_description


def test_adapter_docline_spells_prepared_request() -> None:
    assert request_parameter_description() == "The PreparedRequest being sent over the connection."
