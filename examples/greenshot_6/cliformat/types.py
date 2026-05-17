def format_filename(filename: str) -> str:
    return filename


def invalid_directory_message(kind: str, filename: str) -> str:
    return "{name} '{filename}' is a directory.".format(
        name=kind.title(),
        filename=format_filename(filename),
    )
