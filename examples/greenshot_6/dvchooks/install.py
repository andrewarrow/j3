def pre_commit_hook_entry(version: str) -> dict[str, object]:
    return {
        "repo": "https://github.com/iterative/dvc",
        "rev": version,
        "hooks": [
            {
                "id": "dvc-pre-commit",
                "name": "DVC pre-commit",
            }
        ],
    }
