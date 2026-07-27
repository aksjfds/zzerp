"""Immutable worker references exposed to collaborating modules."""

from dataclasses import dataclass

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.workforce.persistence import Worker


@dataclass(frozen=True, slots=True)
class WorkerReference:
    id: int
    worker_name: str
    department_id: int
    workshop_id: int | None


def get_worker_reference(
    session: Session,
    worker_id: int,
) -> WorkerReference | None:
    worker = session.get(Worker, worker_id)
    if worker is None:
        return None
    return WorkerReference(
        id=worker.id,
        worker_name=worker.worker_name,
        department_id=worker.department_id,
        workshop_id=worker.workshop_id,
    )


def get_worker_references(
    session: Session,
    worker_ids: Collection[int],
) -> dict[int, WorkerReference]:
    if not worker_ids:
        return {}
    return {
        worker.id: WorkerReference(
            id=worker.id,
            worker_name=worker.worker_name,
            department_id=worker.department_id,
            workshop_id=worker.workshop_id,
        )
        for worker in session.scalars(
            select(Worker).where(Worker.id.in_(worker_ids))
        )
    }


__all__ = [
    "WorkerReference",
    "get_worker_reference",
    "get_worker_references",
]
