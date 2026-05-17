from plotlabels import countplot_stat_label


def test_countplot_stat_label_is_capitalized() -> None:
    assert countplot_stat_label("count") == "Count"
