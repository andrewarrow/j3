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


def shipping_timeout_label(timeout_seconds: int = 5) -> str:
    return shipping_timeout_bucket(timeout_seconds=timeout_seconds)


def shipping_timeout_bucket(timeout_seconds: int = 5) -> str:
    return "extended" if timeout_seconds >= 30 else "standard"
