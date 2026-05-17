from attrvalidators import gt_validator_docline


def test_gt_validator_docline_names_gt_operator() -> None:
    assert gt_validator_docline() == (
        "The validator uses `operator.gt` to compare the values."
    )
