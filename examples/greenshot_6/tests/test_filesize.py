from filesize import gnu_suffixes, naturalsize


def test_gnu_filesize_supports_ronna_prefix() -> None:
    assert gnu_suffixes() == "KMGTPEZYRQ"
    assert naturalsize(10**26 * 30, gnu=True) == "2.4R"
