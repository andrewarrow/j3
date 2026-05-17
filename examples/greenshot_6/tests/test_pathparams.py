from pathparams import find_path_params, path_param_pattern


def test_escaped_colon_path_params_are_ignored() -> None:
    assert path_param_pattern() == r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)"
    assert find_path_params("/literal/::org/:repo/issues/:issue_id") == [
        "repo",
        "issue_id",
    ]
