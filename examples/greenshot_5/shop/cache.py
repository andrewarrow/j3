def cache_backend_label() -> str:
    from shop.cache_v2 import CacheBackend

    backend = CacheBackend("sqlite")
    return backend.label()
