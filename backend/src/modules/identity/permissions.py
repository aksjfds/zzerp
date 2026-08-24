"""Canonical codec for the persisted comma-separated permission set."""


def parse_permissions(value: str) -> list[str]:
    return list(dict.fromkeys(
        permission
        for item in value.split(",")
        if (permission := item.strip())
    ))


__all__ = ["parse_permissions"]
