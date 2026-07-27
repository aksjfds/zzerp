"""Transaction-aware API for standard-execution pricing records."""

from sqlalchemy import select

from modules.standard_execution.persistence import ProcedureTagPrice


def copy_product_version_prices(
    session,
    *,
    product_id: int,
    source_version: int,
    target_version: int,
) -> None:
    prices = session.scalars(
        select(ProcedureTagPrice).where(
            ProcedureTagPrice.product_id == product_id,
            ProcedureTagPrice.product_version == source_version,
        )
    )
    for price in prices:
        session.add(
            ProcedureTagPrice(
                product_id=product_id,
                product_version=target_version,
                origin_flow_node_id=price.origin_flow_node_id,
                procedure_id=price.procedure_id,
                procedure_tag_id=price.procedure_tag_id,
                unit_price=price.unit_price,
            )
        )


__all__ = ["copy_product_version_prices"]
