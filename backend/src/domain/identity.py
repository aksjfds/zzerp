"""Stable identity rules shared by authorization and business modules."""


def can_access_department(
    actor_department: str | None,
    actor_is_system: bool,
    target_department: str,
) -> bool:
    return actor_is_system or actor_department == target_department


__all__ = ["can_access_department"]
