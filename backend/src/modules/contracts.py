from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ModuleDescriptor:
    """Stable metadata describing one business module and its owned concepts."""

    name: str
    public_api: str
    owns: tuple[str, ...]
    collaborates_with: tuple[str, ...] = ()
    collaboration_apis: tuple[str, ...] = ()
    api_version: str = "1"


@dataclass(frozen=True)
class DomainEvent:
    """Serializable event envelope reserved for in-process and outbox delivery."""

    event_id: str
    event_type: str
    occurred_at: datetime
    aggregate_id: str
    payload: dict[str, Any]
