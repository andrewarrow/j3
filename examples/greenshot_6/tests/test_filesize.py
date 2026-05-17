from filesize import binary_naturalsize, gnu_suffixes, naturalsize


def test_binary_naturalsize_uses_binary_units() -> None:
    assert binary_naturalsize(1024) == "1.0 KiB"


def test_gnu_filesize_supports_ronna_prefix() -> None:
    assert gnu_suffixes() == "KMGTPEZYRQ"
    assert naturalsize(10**26 * 30, gnu=True) == "2.4R"
