from pytestdocs import filename_discovery_sentence


def test_filename_discovery_pattern_is_not_escaped() -> None:
    assert filename_discovery_sentence() == (
        "pytest discovers files matching test_*.py or *_test.py"
    )
