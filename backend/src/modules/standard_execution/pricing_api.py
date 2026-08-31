"""Transaction-aware API for procedure prices and work-order pay projections."""

from collections import defaultdict

from sqlalchemy import select

from modules.errors import DomainError
from modules.standard_execution.persistence import (
    ProcedureConfiguration,
    ProcedurePrice,
    WorkOrderPayDetail,
)


def copy_product_version_prices(
    session,
    *,
    product_id: int,
    source_version: int,
    target_version: int,
    bom_id_map: dict[int, int],
) -> None:
    configurations = list(session.scalars(
        select(ProcedureConfiguration).where(
            ProcedureConfiguration.product_id == product_id,
            ProcedureConfiguration.product_version == source_version,
        )
    ))
    prices_by_configuration = defaultdict(list)
    if configurations:
        for price in session.scalars(
            select(ProcedurePrice).where(
                ProcedurePrice.configuration_id.in_(
                    [item.id for item in configurations]
                )
            )
        ):
            prices_by_configuration[price.configuration_id].append(price)
    for configuration in configurations:
        material_key = configuration.material_key
        if material_key.startswith("part:"):
            source_bom_id = int(material_key.removeprefix("part:"))
            target_bom_id = bom_id_map.get(source_bom_id)
            if target_bom_id is None:
                continue
            material_key = f"part:{target_bom_id}"
        target_configuration = ProcedureConfiguration(
            product_id=product_id,
            product_version=target_version,
            material_key=material_key,
            flow_node_id=configuration.flow_node_id,
        )
        session.add(target_configuration)
        session.flush()
        for price in prices_by_configuration[configuration.id]:
            session.add(ProcedurePrice(
                configuration_id=target_configuration.id,
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
    is_temporary: bool,
) -> None:
    unit_price = None
    if not is_temporary:
        price = session.scalar(
            select(ProcedurePrice)
            .join(
                ProcedureConfiguration,
                ProcedureConfiguration.id == ProcedurePrice.configuration_id,
            )
            .where(
                ProcedureConfiguration.product_id == product_id,
                ProcedureConfiguration.product_version == product_version,
                ProcedureConfiguration.material_key == material_key,
                ProcedureConfiguration.flow_node_id == flow_node_id,
                ProcedureConfiguration.confirmed_at.is_not(None),
                ProcedurePrice.procedure_id == procedure_id,
            )
            .with_for_update()
        )
        if price is None:
            raise DomainError(
                "work_order_procedure_not_configured",
                "所选工艺不在已确认配置中",
                status_code=409,
            )
        unit_price = price.unit_price
    session.add(WorkOrderPayDetail(
        work_order_id=work_order_id,
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        unit_price=unit_price,
    ))


__all__ = ["attach_work_order_price", "copy_product_version_prices"]
