"""Stable workforce values shared without exposing workforce persistence."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkerReference:
    id: int
    worker_name: str
    department_id: int
    workshop_id: int | None


__all__ = ["WorkerReference"]
