import pytest

from templating import CodeGenerator, TemplateSyntaxError


def test_async_loop_filter_error_message_says_unavailable() -> None:
    compiler = CodeGenerator(async_mode=True)

    with pytest.raises(
        TemplateSyntaxError,
        match="loop filters in async mode are unavailable if the ",
    ):
        compiler.validate_loop_filter(
            uses_loop_variable=True,
            recursive=False,
            line_number=17,
        )
