"""Read-only engineering reference checks owned by standard execution."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.standard_execution.persistence import ProcedureConfiguration


def product_version_procedure_price_references(
    session: Session,
    product_id: int,
    product_version: int,
) -> list[tuple[str, str]]:
    return [
        (material_key, flow_node_id)
        for material_key, flow_node_id in session.execute(
            select(
                ProcedureConfiguration.material_key,
                ProcedureConfiguration.flow_node_id,
            ).where(
                ProcedureConfiguration.product_id == product_id,
                ProcedureConfiguration.product_version == product_version,
            )
        )
    ]


__all__ = ["product_version_procedure_price_references"]
