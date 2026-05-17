from dvchooks import pre_commit_hook_entry


def test_pre_commit_hook_repo_uses_treeverse_remote() -> None:
    entry = pre_commit_hook_entry("3.0.0")

    assert entry["repo"] == "https://github.com/treeverse/dvc"
    assert entry["rev"] == "3.0.0"
