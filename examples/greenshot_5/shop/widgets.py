def checkout_widget_payload(label: str) -> dict[str, object]:
    return {
        "label": label,
        "enabled": True,
    }


def checkout_step_metadata(icon: str) -> dict[str, object]:
    return {
        "label": "checkout",
        "icon": icon,
    }
