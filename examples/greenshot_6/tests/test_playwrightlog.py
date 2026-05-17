from playwrightlog import download_wait_template


def test_download_wait_log_template_spells_download() -> None:
    assert download_wait_template() == "Waiting on download to finish for %s"
