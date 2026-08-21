"""Transaction-aware API for procedure prices and work-order pay projections."""

from sqlalchemy import select

from modules.standard_execution.persistence import ProcedurePrice, WorkOrderPayDetail


def copy_product_version_prices(
    session,
    *,
    product_id: int,
    source_version: int,
    target_version: int,
    bom_id_map: dict[int, int],
) -> None:
    for price in session.scalars(
        select(ProcedurePrice).where(
            ProcedurePrice.product_id == product_id,
            ProcedurePrice.product_version == source_version,
        )
    ):
        material_key = price.material_key
        if material_key.startswith("part:"):
            source_bom_id = int(material_key.removeprefix("part:"))
            target_bom_id = bom_id_map.get(source_bom_id)
            if target_bom_id is None:
                continue
            material_key = f"part:{target_bom_id}"
        session.add(ProcedurePrice(
            product_id=product_id,
            product_version=target_version,
            material_key=material_key,
            flow_node_id=price.flow_node_id,
            procedure_id=price.procedure_id,
            unit_price=price.unit_price,
        ))


def attach_work_order_price(
    session,
    *,
    work_order_id: int,
    product_id: int,
    product_version: int,
    material_key: str,
    flow_node_id: str,
    procedure_id: int,
    procedure_name: str,
) -> None:
    price = session.scalar(
        select(ProcedurePrice)
        .where(
            ProcedurePrice.product_id == product_id,
            ProcedurePrice.product_version == product_version,
            ProcedurePrice.material_key == material_key,
            ProcedurePrice.flow_node_id == flow_node_id,
            ProcedurePrice.procedure_id == procedure_id,
        )
        .with_for_update()
    )
    if price is None:
        price = ProcedurePrice(
            product_id=product_id,
            product_version=product_version,
            material_key=material_key,
            flow_node_id=flow_node_id,
            procedure_id=procedure_id,
            unit_price=None,
        )
        session.add(price)
        session.flush()
    session.add(WorkOrderPayDetail(
        work_order_id=work_order_id,
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        unit_price=price.unit_price,
    ))


__all__ = ["attach_work_order_price", "copy_product_version_prices"]
