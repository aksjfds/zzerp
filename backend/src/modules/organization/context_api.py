"""Stable structural contracts for organization-owned runtime context."""

from typing import Protocol


class ProcedureContext(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def workshop_id(self) -> int: ...

    @property
    def procedure_name(self) -> str: ...


__all__ = ["ProcedureContext"]
