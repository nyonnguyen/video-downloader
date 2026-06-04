from typing import Callable, Type

DOWNLOADER_REGISTRY: dict[str, Type] = {}


def register(source: str) -> Callable:
    def decorator(cls):
        DOWNLOADER_REGISTRY[source] = cls
        return cls
    return decorator


def get_downloader_class(source: str):
    return DOWNLOADER_REGISTRY.get(source) or DOWNLOADER_REGISTRY.get("generic")
