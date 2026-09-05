"""Application read orchestration for the finished department."""

from dataclasses import asdict

from database import SessionLocal
from modules.inventory.reference_api import finished_arrival_summaries
from modules.planning.reference_api import (
    list_finished_inbound_plan_summaries,
)


def list_finished_inbound_items(page: int, page_size: int) -> dict:
    with SessionLocal() as session:
        plans, total = list_finished_inbound_plan_summaries(
            session,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        arrivals = finished_arrival_summaries(
            session,
            {(plan.product_id, plan.product_version) for plan in plans},
        )
        data = []
        for plan in plans:
            arrival = arrivals[(plan.product_id, plan.product_version)]
            data.append({
                **asdict(plan),
                "arrived_quantity": arrival.arrived_quantity,
                "pending_receipts": [
                    asdict(receipt) for receipt in arrival.pending_receipts
                ],
            })
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


__all__ = ["list_finished_inbound_items"]
