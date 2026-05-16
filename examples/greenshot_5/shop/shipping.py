SERVICE_LABELS = {
    "standard": "ground",
    "priority": "air",
}

SPEED_LABELS = {
    "express": "air",
}


def shipping_service_label(method: str) -> str:
    return SERVICE_LABELS[method]


def delivery_speed_label(method: str) -> str:
    return SPEED_LABELS[method]
