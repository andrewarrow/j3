SERVICE_LABELS = {
    "standard": "ground",
    "priority": "air",
}


def shipping_service_label(method: str) -> str:
    return SERVICE_LABELS[method]
