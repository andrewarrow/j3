from __future__ import annotations


def countplot_stat_label(stat: str) -> str:
    labels = {
        "count": "count",
        "percent": "Percent",
        "proportion": "Proportion",
    }
    return labels[stat]
