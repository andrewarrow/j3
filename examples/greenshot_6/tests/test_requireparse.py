from requireparse import parser_grammar_docstring


def test_parser_docstring_names_ebnf_grammar() -> None:
    assert parser_grammar_docstring() == (
        "Each parser docstring contains EBNF-inspired grammar."
    )
