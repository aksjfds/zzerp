"""Immutable piece-rate details used by workforce reporting."""

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.standard_execution.persistence import WorkOrderPayDetail


@dataclass(frozen=True, slots=True)
class PayDetailView:
    id: int
    work_order_id: int
    tag_name: str
    unit_price: Decimal


def list_pay_details(
    session: Session,
    work_order_ids: Collection[int],
) -> list[PayDetailView]:
    if not work_order_ids:
        return []
    rows = session.execute(
        select(
            WorkOrderPayDetail.id,
            WorkOrderPayDetail.work_order_id,
            WorkOrderPayDetail.tag_name,
            WorkOrderPayDetail.unit_price,
        )
        .where(WorkOrderPayDetail.work_order_id.in_(work_order_ids))
        .order_by(WorkOrderPayDetail.tag_name, WorkOrderPayDetail.id)
    )
    return [
        PayDetailView(
            id=row.id,
            work_order_id=row.work_order_id,
            tag_name=row.tag_name,
            unit_price=row.unit_price,
        )
        for row in rows
    ]


__all__ = ["PayDetailView", "list_pay_details"]
