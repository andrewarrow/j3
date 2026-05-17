from __future__ import annotations


class TemplateSyntaxError(Exception):
    pass


class CodeGenerator:
    def __init__(self, *, async_mode: bool) -> None:
        self.async_mode = async_mode

    def fail(self, message: str, line_number: int) -> None:
        raise TemplateSyntaxError(f"{message} (line {line_number})")

    def validate_loop_filter(
        self,
        *,
        uses_loop_variable: bool,
        recursive: bool,
        line_number: int = 1,
    ) -> None:
        if self.async_mode and (uses_loop_variable or recursive):
            self.fail(
                (
                    "loop filters in async mode are currently if the "
                    + 'loop uses the special "loop" variable or is recursive.'
                ),
                line_number,
            )
